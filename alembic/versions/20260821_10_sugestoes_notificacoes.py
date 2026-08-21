"""Sugestões assistidas, notificações e permissões.

Revision ID: 20260821_10
Revises: 20260812_09
"""
from alembic import op
import sqlalchemy as sa

revision = "20260821_10"
down_revision = "20260812_09"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    product_columns = {column["name"] for column in inspector.get_columns("produtos")}
    user_columns = {column["name"] for column in inspector.get_columns("usuarios")}
    if "ativo" not in product_columns:
        op.add_column("produtos", sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()))
        op.create_index("ix_produtos_ativo", "produtos", ["ativo"])
    if "pode_enviar_sugestoes" not in user_columns:
        op.add_column("usuarios", sa.Column("pode_enviar_sugestoes", sa.Boolean(), nullable=False, server_default=sa.true()))
    if "pode_administrar_sugestoes" not in user_columns:
        op.add_column("usuarios", sa.Column("pode_administrar_sugestoes", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE usuarios SET pode_administrar_sugestoes=true WHERE tipo_usuario IN ('DONO','DESENVOLVEDOR')")
    tables = set(inspector.get_table_names())
    if "sugestoes" in tables:
        return
    op.create_table(
        "sugestoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("numero", sa.String(30), nullable=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("titulo", sa.String(255), nullable=True),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("modulo", sa.String(80), nullable=True),
        sa.Column("resumo_ia", sa.Text(), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="COLETANDO_IDEIA"),
        sa.Column("prioridade", sa.String(20), nullable=False, server_default="NORMAL"),
        sa.Column("resposta_administrativa", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("numero", name="uq_sugestoes_numero"),
    )
    op.create_index("ix_sugestoes_usuario_id", "sugestoes", ["usuario_id"])
    op.create_index("ix_sugestoes_status", "sugestoes", ["status"])
    op.create_index("ix_sugestoes_modulo", "sugestoes", ["modulo"])
    op.create_index("ix_sugestoes_prioridade", "sugestoes", ["prioridade"])
    op.create_index("ix_sugestoes_criado_em", "sugestoes", ["criado_em"])
    op.create_index("ix_sugestoes_atualizado_em", "sugestoes", ["atualizado_em"])
    op.create_table(
        "mensagens_sugestao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sugestao_id", sa.Integer(), sa.ForeignKey("sugestoes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("autor_tipo", sa.String(20), nullable=False),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("conteudo", sa.Text(), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_mensagens_sugestao_sugestao_id", "mensagens_sugestao", ["sugestao_id"])
    op.create_index("ix_mensagens_sugestao_criado_em", "mensagens_sugestao", ["criado_em"])
    op.create_table(
        "historico_status_sugestao",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sugestao_id", sa.Integer(), sa.ForeignKey("sugestoes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status_anterior", sa.String(40), nullable=True),
        sa.Column("status_novo", sa.String(40), nullable=False),
        sa.Column("observacao", sa.Text(), nullable=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("usuario_nome", sa.String(120), nullable=False),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_historico_status_sugestao_sugestao_id", "historico_status_sugestao", ["sugestao_id"])
    op.create_index("ix_historico_status_sugestao_criado_em", "historico_status_sugestao", ["criado_em"])
    op.create_table(
        "notificacoes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(40), nullable=False),
        sa.Column("titulo", sa.String(255), nullable=False),
        sa.Column("mensagem", sa.Text(), nullable=False),
        sa.Column("entidade", sa.String(80), nullable=True),
        sa.Column("entidade_id", sa.Integer(), nullable=True),
        sa.Column("lida_em", sa.DateTime(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notificacoes_usuario_lida", "notificacoes", ["usuario_id", "lida_em"])
    op.create_index("ix_notificacoes_usuario_id", "notificacoes", ["usuario_id"])
    op.create_index("ix_notificacoes_tipo", "notificacoes", ["tipo"])
    op.create_index("ix_notificacoes_entidade_id", "notificacoes", ["entidade_id"])
    op.create_index("ix_notificacoes_lida_em", "notificacoes", ["lida_em"])
    op.create_index("ix_notificacoes_criado_em", "notificacoes", ["criado_em"])


def downgrade():
    op.drop_table("notificacoes")
    op.drop_table("historico_status_sugestao")
    op.drop_table("mensagens_sugestao")
    op.drop_table("sugestoes")
    op.drop_column("usuarios", "pode_administrar_sugestoes")
    op.drop_column("usuarios", "pode_enviar_sugestoes")
    op.drop_index("ix_produtos_ativo", table_name="produtos")
    op.drop_column("produtos", "ativo")
