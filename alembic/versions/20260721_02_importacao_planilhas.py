"""Importação contínua de notas fiscais e recibos.

Revision ID: 20260721_02
Revises: 20260721_01
"""
from alembic import op
import sqlalchemy as sa


revision = "20260721_02"
down_revision = "20260721_01"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()
    if "importacoes_planilha" not in tables:
        op.create_table(
            "importacoes_planilha",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("nome_arquivo", sa.String(255), nullable=False),
            sa.Column("tipo_documento", sa.String(20), nullable=False),
            sa.Column("aba_origem", sa.String(80), nullable=False),
            sa.Column("hash_arquivo", sa.String(64), nullable=False),
            sa.Column("status", sa.String(20), nullable=False, server_default="PREVIA"),
            sa.Column("total_linhas", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("linhas_novas", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("linhas_duplicadas", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("linhas_revisao", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
            sa.Column("usuario_nome", sa.String(120), nullable=False),
            sa.Column("criado_em", sa.DateTime(), nullable=False),
            sa.Column("confirmado_em", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_importacoes_planilha_hash_arquivo", "importacoes_planilha", ["hash_arquivo"], unique=True)
    if "registros_venda_importados" not in tables:
        op.create_table(
            "registros_venda_importados",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("importacao_id", sa.Integer(), sa.ForeignKey("importacoes_planilha.id", ondelete="CASCADE"), nullable=False),
            sa.Column("linha_origem", sa.Integer(), nullable=False),
            sa.Column("hash_registro", sa.String(64), nullable=False),
            sa.Column("tipo_documento", sa.String(20), nullable=False),
            sa.Column("numero_documento", sa.String(80), nullable=True),
            sa.Column("data_venda", sa.Date(), nullable=False),
            sa.Column("cliente_nome", sa.String(255), nullable=False),
            sa.Column("cliente_codigo", sa.String(80), nullable=True),
            sa.Column("contato", sa.String(180), nullable=True),
            sa.Column("quantidade", sa.Numeric(14, 4), nullable=False, server_default="0"),
            sa.Column("descricao_original", sa.Text(), nullable=False),
            sa.Column("descricao_padronizada", sa.Text(), nullable=False),
            sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id", ondelete="SET NULL"), nullable=True),
            sa.Column("familia", sa.String(80), nullable=True),
            sa.Column("aplicacao", sa.String(100), nullable=True),
            sa.Column("material", sa.String(100), nullable=True),
            sa.Column("largura", sa.Numeric(12, 3), nullable=True),
            sa.Column("capacidade", sa.Numeric(14, 3), nullable=True),
            sa.Column("comprimento", sa.Numeric(12, 3), nullable=True),
            sa.Column("gancho", sa.String(100), nullable=True),
            sa.Column("reforco", sa.String(100), nullable=True),
            sa.Column("costura", sa.String(100), nullable=True),
            sa.Column("impressao", sa.String(100), nullable=True),
            sa.Column("valor_unitario", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("valor_total", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("desconto", sa.Numeric(14, 2), nullable=False, server_default="0"),
            sa.Column("percentual_desconto", sa.Numeric(8, 2), nullable=False, server_default="0"),
            sa.Column("status_padronizacao", sa.String(20), nullable=False, server_default="REVISAR"),
            sa.Column("observacoes", sa.Text(), nullable=True),
            sa.UniqueConstraint("importacao_id", "hash_registro", name="uq_registro_venda_importacao_hash"),
        )
        for column in ("importacao_id", "hash_registro", "tipo_documento", "numero_documento", "data_venda", "cliente_nome", "familia", "aplicacao", "status_padronizacao"):
            op.create_index(f"ix_registros_venda_importados_{column}", "registros_venda_importados", [column])


def downgrade():
    op.drop_table("registros_venda_importados")
    op.drop_table("importacoes_planilha")
