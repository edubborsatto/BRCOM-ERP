"""Revisão exclusiva de duplicidades na importação.

Revision ID: 20260722_03
Revises: 20260721_02
"""
from alembic import op
import sqlalchemy as sa


revision = "20260722_03"
down_revision = "20260721_02"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    import_indexes = {
        index["name"]: index
        for index in inspector.get_indexes("importacoes_planilha")
    }
    file_hash_index = import_indexes.get("ix_importacoes_planilha_hash_arquivo")
    if file_hash_index and file_hash_index.get("unique"):
        op.drop_index(
            "ix_importacoes_planilha_hash_arquivo",
            table_name="importacoes_planilha",
        )
        op.create_index(
            "ix_importacoes_planilha_hash_arquivo",
            "importacoes_planilha",
            ["hash_arquivo"],
            unique=False,
        )
    columns = {column["name"] for column in inspector.get_columns("registros_venda_importados")}
    with op.batch_alter_table("registros_venda_importados") as batch:
        if "hash_duplicidade" not in columns:
            batch.add_column(sa.Column("hash_duplicidade", sa.String(64), nullable=True))
        if "status_importacao" not in columns:
            batch.add_column(sa.Column("status_importacao", sa.String(20), nullable=False, server_default="NOVO"))
        if "decisao_duplicidade" not in columns:
            batch.add_column(sa.Column("decisao_duplicidade", sa.String(20), nullable=True))
        if "origem_duplicidade" not in columns:
            batch.add_column(sa.Column("origem_duplicidade", sa.String(30), nullable=True))
    op.execute("UPDATE registros_venda_importados SET hash_duplicidade = hash_registro WHERE hash_duplicidade IS NULL")
    inspector = sa.inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("registros_venda_importados")}
    for column in ("hash_duplicidade", "status_importacao", "decisao_duplicidade"):
        name = f"ix_registros_venda_importados_{column}"
        if name not in indexes:
            op.create_index(name, "registros_venda_importados", [column])


def downgrade():
    with op.batch_alter_table("registros_venda_importados") as batch:
        for column in ("decisao_duplicidade", "status_importacao", "hash_duplicidade"):
            batch.drop_index(f"ix_registros_venda_importados_{column}")
        for column in ("origem_duplicidade", "decisao_duplicidade", "status_importacao", "hash_duplicidade"):
            batch.drop_column(column)
    op.drop_index(
        "ix_importacoes_planilha_hash_arquivo",
        table_name="importacoes_planilha",
    )
    op.create_index(
        "ix_importacoes_planilha_hash_arquivo",
        "importacoes_planilha",
        ["hash_arquivo"],
        unique=True,
    )
