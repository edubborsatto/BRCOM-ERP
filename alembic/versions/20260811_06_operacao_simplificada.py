"""Produtos simplificados, localização livre e confirmação de pedidos.

Revision ID: 20260811_06
Revises: 20260804_05
"""
from alembic import op
import sqlalchemy as sa


revision = "20260811_06"
down_revision = "20260804_05"
branch_labels = None
depends_on = None


def _columns(inspector, table):
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    product_columns = _columns(inspector, "produtos")
    with op.batch_alter_table("produtos") as batch:
        if "tipo" not in product_columns:
            batch.add_column(sa.Column("tipo", sa.String(120), nullable=True))
        if "localizacao" not in product_columns:
            batch.add_column(sa.Column("localizacao", sa.String(255), nullable=True))
    product_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("produtos")}
    if "ix_produtos_tipo" not in product_indexes:
        op.create_index("ix_produtos_tipo", "produtos", ["tipo"])

    order_columns = _columns(sa.inspect(bind), "pedidos_futuros")
    definitions = (
        ("tipo_documento", sa.Column("tipo_documento", sa.String(20), nullable=True)),
        ("numero_documento", sa.Column("numero_documento", sa.String(80), nullable=True)),
        ("confirmado_em", sa.Column("confirmado_em", sa.DateTime(), nullable=True)),
        ("confirmado_por_id", sa.Column(
            "confirmado_por_id", sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
        )),
        ("confirmado_por_nome", sa.Column("confirmado_por_nome", sa.String(120), nullable=True)),
    )
    with op.batch_alter_table("pedidos_futuros") as batch:
        for name, column in definitions:
            if name not in order_columns:
                batch.add_column(column)
    order_indexes = {index["name"] for index in sa.inspect(bind).get_indexes("pedidos_futuros")}
    if "ix_pedidos_futuros_numero_documento" not in order_indexes:
        op.create_index(
            "ix_pedidos_futuros_numero_documento",
            "pedidos_futuros", ["numero_documento"],
        )


def downgrade():
    with op.batch_alter_table("pedidos_futuros") as batch:
        batch.drop_index("ix_pedidos_futuros_numero_documento")
        for column in (
            "confirmado_por_nome", "confirmado_por_id", "confirmado_em",
            "numero_documento", "tipo_documento",
        ):
            batch.drop_column(column)
    with op.batch_alter_table("produtos") as batch:
        batch.drop_index("ix_produtos_tipo")
        batch.drop_column("localizacao")
        batch.drop_column("tipo")
