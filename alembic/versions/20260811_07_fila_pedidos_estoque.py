"""Fila de pedidos, itens e reservas de estoque.

Revision ID: 20260811_07
Revises: 20260811_06
"""
from alembic import op
import sqlalchemy as sa


revision = "20260811_07"
down_revision = "20260811_06"
branch_labels = None
depends_on = None


def _columns(inspector, table):
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    order_columns = _columns(inspector, "pedidos_futuros")
    definitions = (
        ("fila_posicao", sa.Column("fila_posicao", sa.Integer(), nullable=False, server_default="0")),
        ("prioridade", sa.Column("prioridade", sa.Boolean(), nullable=False, server_default=sa.false())),
        ("cancelado_em", sa.Column("cancelado_em", sa.DateTime(), nullable=True)),
        ("cancelado_por_id", sa.Column(
            "cancelado_por_id", sa.Integer(),
            sa.ForeignKey(
                "usuarios.id", ondelete="SET NULL",
                name="fk_pedidos_futuros_cancelado_por_id_usuarios",
            ), nullable=True,
        )),
        ("cancelado_por_nome", sa.Column("cancelado_por_nome", sa.String(120), nullable=True)),
    )
    with op.batch_alter_table("pedidos_futuros") as batch:
        for name, column in definitions:
            if name not in order_columns:
                batch.add_column(column)

    pedidos = bind.execute(
        sa.text("SELECT id FROM pedidos_futuros ORDER BY data_entrega, id")
    ).fetchall()
    for position, row in enumerate(pedidos, start=1):
        bind.execute(
            sa.text("UPDATE pedidos_futuros SET fila_posicao=:position WHERE id=:id"),
            {"position": position, "id": row[0]},
        )

    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("pedidos_futuros")}
    if "ix_pedidos_futuros_fila_posicao" not in indexes:
        op.create_index("ix_pedidos_futuros_fila_posicao", "pedidos_futuros", ["fila_posicao"])
    if "ix_pedidos_futuros_prioridade" not in indexes:
        op.create_index("ix_pedidos_futuros_prioridade", "pedidos_futuros", ["prioridade"])

    tables = set(sa.inspect(bind).get_table_names())
    if "pedido_futuro_itens" not in tables:
        op.create_table(
            "pedido_futuro_itens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "pedido_id", sa.Integer(),
                sa.ForeignKey("pedidos_futuros.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column("produto_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=False),
            sa.Column("produto_nome", sa.String(255), nullable=False),
            sa.Column("quantidade_total", sa.Numeric(14, 4), nullable=False),
            sa.Column("quantidade_estoque", sa.Numeric(14, 4), nullable=False, server_default="0"),
            sa.Column("quantidade_fabricar", sa.Numeric(14, 4), nullable=False, server_default="0"),
        )
        op.create_index("ix_pedido_futuro_itens_pedido_id", "pedido_futuro_itens", ["pedido_id"])
        op.create_index("ix_pedido_futuro_itens_produto_id", "pedido_futuro_itens", ["produto_id"])

    if "pedido_futuro_materias_primas" not in tables:
        op.create_table(
            "pedido_futuro_materias_primas",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "pedido_item_id", sa.Integer(),
                sa.ForeignKey("pedido_futuro_itens.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column("materia_prima_id", sa.Integer(), sa.ForeignKey("produtos.id"), nullable=False),
            sa.Column("materia_prima_nome", sa.String(255), nullable=False),
            sa.Column("quantidade_reservada", sa.Numeric(14, 4), nullable=False),
        )
        op.create_index(
            "ix_pedido_futuro_materias_primas_pedido_item_id",
            "pedido_futuro_materias_primas", ["pedido_item_id"],
        )
        op.create_index(
            "ix_pedido_futuro_materias_primas_materia_prima_id",
            "pedido_futuro_materias_primas", ["materia_prima_id"],
        )


def downgrade():
    op.drop_table("pedido_futuro_materias_primas")
    op.drop_table("pedido_futuro_itens")
    with op.batch_alter_table("pedidos_futuros") as batch:
        batch.drop_index("ix_pedidos_futuros_prioridade")
        batch.drop_index("ix_pedidos_futuros_fila_posicao")
        for column in (
            "cancelado_por_nome", "cancelado_por_id", "cancelado_em",
            "prioridade", "fila_posicao",
        ):
            batch.drop_column(column)
