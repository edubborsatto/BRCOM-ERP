"""Perfis oficiais, permissões operacionais e auditoria de usuários.

Revision ID: 20260804_05
Revises: 20260802_04
"""
from alembic import op
import sqlalchemy as sa


revision = "20260804_05"
down_revision = "20260802_04"
branch_labels = None
depends_on = None


def _columns(inspector, table):
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = _columns(inspector, "usuarios")
    definitions = (
        ("tipo_usuario", sa.Column("tipo_usuario", sa.String(20), nullable=False, server_default="FUNCIONARIO")),
        ("ativo", sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true())),
        ("pode_criar_orcamentos", sa.Column("pode_criar_orcamentos", sa.Boolean(), nullable=False, server_default=sa.true())),
        ("pode_aprovar_orcamentos", sa.Column("pode_aprovar_orcamentos", sa.Boolean(), nullable=False, server_default=sa.false())),
        ("pode_registrar_vendas", sa.Column("pode_registrar_vendas", sa.Boolean(), nullable=False, server_default=sa.true())),
        ("pode_importar_planilhas", sa.Column("pode_importar_planilhas", sa.Boolean(), nullable=False, server_default=sa.false())),
        ("pode_editar_planilhas", sa.Column("pode_editar_planilhas", sa.Boolean(), nullable=False, server_default=sa.false())),
        ("pode_ver_faturamento", sa.Column("pode_ver_faturamento", sa.Boolean(), nullable=False, server_default=sa.false())),
    )
    with op.batch_alter_table("usuarios") as batch:
        for name, column in definitions:
            if name not in existing:
                batch.add_column(column)

    op.execute(
        "UPDATE usuarios SET tipo_usuario = 'DESENVOLVEDOR' "
        "WHERE pode_gerenciar_usuarios = TRUE AND pode_acessar_docs = TRUE "
        "AND tipo_usuario = 'FUNCIONARIO'"
    )
    op.execute(
        "UPDATE usuarios SET tipo_usuario = 'DONO' "
        "WHERE pode_gerenciar_usuarios = TRUE AND tipo_usuario = 'FUNCIONARIO'"
    )
    op.execute(
        "UPDATE usuarios SET "
        "pode_criar_orcamentos = TRUE, pode_registrar_vendas = TRUE, "
        "pode_aprovar_orcamentos = pode_alterar_custos, "
        "pode_importar_planilhas = pode_alterar_custos, "
        "pode_editar_planilhas = pode_alterar_custos, "
        "pode_ver_faturamento = pode_alterar_custos"
    )

    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("usuarios")}
    if "ix_usuarios_tipo_usuario" not in indexes:
        op.create_index("ix_usuarios_tipo_usuario", "usuarios", ["tipo_usuario"])
    if "ix_usuarios_ativo" not in indexes:
        op.create_index("ix_usuarios_ativo", "usuarios", ["ativo"])

    if "auditoria_sistema" not in inspector.get_table_names():
        op.create_table(
            "auditoria_sistema",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("categoria", sa.String(40), nullable=False),
            sa.Column("acao", sa.String(40), nullable=False),
            sa.Column("entidade", sa.String(80), nullable=False),
            sa.Column("entidade_id", sa.Integer(), nullable=True),
            sa.Column("dados_anteriores", sa.Text(), nullable=True),
            sa.Column("dados_novos", sa.Text(), nullable=True),
            sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
            sa.Column("usuario_nome", sa.String(120), nullable=False),
            sa.Column("criado_em", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_auditoria_sistema_categoria", "auditoria_sistema", ["categoria"])
        op.create_index("ix_auditoria_sistema_acao", "auditoria_sistema", ["acao"])
        op.create_index("ix_auditoria_sistema_entidade_id", "auditoria_sistema", ["entidade_id"])
        op.create_index("ix_auditoria_sistema_criado_em", "auditoria_sistema", ["criado_em"])


def downgrade():
    op.drop_table("auditoria_sistema")
    with op.batch_alter_table("usuarios") as batch:
        batch.drop_index("ix_usuarios_ativo")
        batch.drop_index("ix_usuarios_tipo_usuario")
        for column in (
            "pode_ver_faturamento", "pode_editar_planilhas",
            "pode_importar_planilhas", "pode_registrar_vendas",
            "pode_aprovar_orcamentos", "pode_criar_orcamentos",
            "ativo", "tipo_usuario",
        ):
            batch.drop_column(column)
