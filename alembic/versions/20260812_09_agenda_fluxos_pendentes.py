"""Agenda mensal e conclusão dos fluxos integrados.

Revision ID: 20260812_09
Revises: 20260812_08
"""
from alembic import op
import sqlalchemy as sa

revision = "20260812_09"
down_revision = "20260812_08"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("usuarios")}
    for name in ("pode_informar_falta_material", "pode_colocar_observacao"):
        if name not in user_columns:
            op.add_column("usuarios", sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.true()))
    columns = {column["name"] for column in inspector.get_columns("pedidos_futuros")}
    if "modalidade_entrega" not in columns:
        op.add_column(
            "pedidos_futuros",
            sa.Column("modalidade_entrega", sa.String(20), nullable=True),
        )
    op.create_index(
        "ix_pedidos_futuros_data_modalidade",
        "pedidos_futuros", ["data_entrega", "modalidade_entrega"],
        if_not_exists=True,
    )


def downgrade():
    op.drop_index("ix_pedidos_futuros_data_modalidade", table_name="pedidos_futuros")
    op.drop_column("pedidos_futuros", "modalidade_entrega")
    op.drop_column("usuarios", "pode_colocar_observacao")
    op.drop_column("usuarios", "pode_informar_falta_material")
