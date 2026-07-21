"""Estrutura industrial, orçamentos, ordens de serviço e vendas.

Revision ID: 20260721_01
Revises:
"""
from alembic import op
import sqlalchemy as sa

from app.database import Base
from app import models  # noqa: F401

revision = "20260721_01"
down_revision = None
branch_labels = None
depends_on = None


def _columns(inspector, table):
    return {column["name"] for column in inspector.get_columns(table)}


def _add_missing(table, definitions):
    inspector = sa.inspect(op.get_bind())
    existing = _columns(inspector, table)
    for name, column in definitions:
        if name not in existing:
            op.add_column(table, column)


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "produtos" not in inspector.get_table_names():
        Base.metadata.create_all(bind=bind)
        return

    _add_missing("produtos", [
        ("codigo", sa.Column("codigo", sa.String(40), nullable=True)),
        ("tipo_item", sa.Column("tipo_item", sa.String(20), nullable=False, server_default="PRODUTO_ACABADO")),
        ("familia", sa.Column("familia", sa.String(80), nullable=True)),
        ("variacao", sa.Column("variacao", sa.String(120), nullable=True)),
        ("comprimento", sa.Column("comprimento", sa.Numeric(12, 3), nullable=True)),
        ("largura", sa.Column("largura", sa.Numeric(12, 3), nullable=True)),
        ("resistencia", sa.Column("resistencia", sa.Numeric(14, 3), nullable=True)),
        ("fator_seguranca", sa.Column("fator_seguranca", sa.Numeric(8, 2), nullable=True)),
        ("especificacoes", sa.Column("especificacoes", sa.Text(), nullable=True)),
    ])
    if bind.dialect.name == "postgresql":
        op.execute("UPDATE produtos SET codigo = 'LEG-' || id WHERE codigo IS NULL")
        op.alter_column("produtos", "codigo", nullable=False)
        op.alter_column("produtos", "quantidade_atual", type_=sa.Numeric(14, 4), postgresql_using="quantidade_atual::numeric")
        op.alter_column("produtos", "estoque_minimo", type_=sa.Numeric(14, 4), postgresql_using="estoque_minimo::numeric")
        op.alter_column("produtos", "preco_custo", type_=sa.Numeric(14, 2), postgresql_using="preco_custo::numeric")
        op.alter_column("produtos", "preco_venda", type_=sa.Numeric(14, 2), postgresql_using="preco_venda::numeric")
    else:
        op.execute("UPDATE produtos SET codigo = 'LEG-' || id WHERE codigo IS NULL")
    indexes = {index["name"] for index in sa.inspect(bind).get_indexes("produtos")}
    if "ix_produtos_codigo" not in indexes:
        op.create_index("ix_produtos_codigo", "produtos", ["codigo"], unique=True)

    _add_missing("historico_estoque", [
        ("produto_id", sa.Column("produto_id", sa.Integer(), nullable=True)),
        ("saldo_anterior", sa.Column("saldo_anterior", sa.Numeric(14, 4), nullable=True)),
        ("motivo", sa.Column("motivo", sa.Text(), nullable=True)),
        ("referencia", sa.Column("referencia", sa.String(80), nullable=True)),
        ("usuario_id", sa.Column("usuario_id", sa.Integer(), nullable=True)),
    ])

    for name in [
        "formulas_produto", "formula_componentes", "orcamentos", "orcamento_itens",
        "ordens_servico", "vendas",
    ]:
        Base.metadata.tables[name].create(bind=bind, checkfirst=True)


def downgrade():
    for name in ["vendas", "ordens_servico", "orcamento_itens", "orcamentos", "formula_componentes", "formulas_produto"]:
        op.drop_table(name)
