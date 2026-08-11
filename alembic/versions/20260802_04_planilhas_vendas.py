"""Planilhas de vendas editáveis e histórico.

Revision ID: 20260802_04
Revises: 20260722_03
"""
from alembic import op
import sqlalchemy as sa


revision = "20260802_04"
down_revision = "20260722_03"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {
        column["name"]
        for column in inspector.get_columns("registros_venda_importados")
    }
    with op.batch_alter_table("registros_venda_importados") as batch:
        if "ativo" not in columns:
            batch.add_column(sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.true()))
        if "criado_manual" not in columns:
            batch.add_column(sa.Column("criado_manual", sa.Boolean(), nullable=False, server_default=sa.false()))
        if "atualizado_em" not in columns:
            batch.add_column(sa.Column("atualizado_em", sa.DateTime(), nullable=True))
        if "atualizado_por_id" not in columns:
            batch.add_column(sa.Column("atualizado_por_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                "fk_registro_venda_atualizado_por",
                "usuarios", ["atualizado_por_id"], ["id"], ondelete="SET NULL",
            )
        if "atualizado_por_nome" not in columns:
            batch.add_column(sa.Column("atualizado_por_nome", sa.String(120), nullable=True))
    op.execute("UPDATE registros_venda_importados SET atualizado_em = CURRENT_TIMESTAMP WHERE atualizado_em IS NULL")
    indexes = {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes("registros_venda_importados")
    }
    if "ix_registros_venda_importados_ativo" not in indexes:
        op.create_index("ix_registros_venda_importados_ativo", "registros_venda_importados", ["ativo"])

    if "historico_planilhas_vendas" not in inspector.get_table_names():
        op.create_table(
            "historico_planilhas_vendas",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("registro_id", sa.Integer(), sa.ForeignKey("registros_venda_importados.id", ondelete="CASCADE"), nullable=False),
            sa.Column("acao", sa.String(30), nullable=False),
            sa.Column("dados_anteriores", sa.Text(), nullable=True),
            sa.Column("dados_novos", sa.Text(), nullable=True),
            sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
            sa.Column("usuario_nome", sa.String(120), nullable=False),
            sa.Column("criado_em", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_historico_planilhas_vendas_registro_id", "historico_planilhas_vendas", ["registro_id"])
        op.create_index("ix_historico_planilhas_vendas_acao", "historico_planilhas_vendas", ["acao"])
        op.create_index("ix_historico_planilhas_vendas_criado_em", "historico_planilhas_vendas", ["criado_em"])


def downgrade():
    op.drop_table("historico_planilhas_vendas")
    op.drop_index("ix_registros_venda_importados_ativo", table_name="registros_venda_importados")
    with op.batch_alter_table("registros_venda_importados") as batch:
        batch.drop_constraint("fk_registro_venda_atualizado_por", type_="foreignkey")
        for column in ("atualizado_por_nome", "atualizado_por_id", "atualizado_em", "criado_manual", "ativo"):
            batch.drop_column(column)
