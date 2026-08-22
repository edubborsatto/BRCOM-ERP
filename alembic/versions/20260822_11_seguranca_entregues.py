"""Proteção de acesso e histórico de pedidos concluídos.

Revision ID: 20260822_11
Revises: 20260821_10
"""
from alembic import op
import sqlalchemy as sa

revision = "20260822_11"
down_revision = "20260821_10"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("usuarios")}
    additions = (
        ("email", sa.Column("email", sa.String(255), nullable=True)),
        ("telefone", sa.Column("telefone", sa.String(40), nullable=True)),
        ("tentativas_login", sa.Column("tentativas_login", sa.Integer(), nullable=False, server_default="0")),
        ("bloqueado_ate", sa.Column("bloqueado_ate", sa.DateTime(), nullable=True)),
        ("ultima_falha_login_em", sa.Column("ultima_falha_login_em", sa.DateTime(), nullable=True)),
        ("ultimo_login_em", sa.Column("ultimo_login_em", sa.DateTime(), nullable=True)),
        ("codigo_recuperacao_hash", sa.Column("codigo_recuperacao_hash", sa.String(64), nullable=True)),
        ("codigo_recuperacao_expira_em", sa.Column("codigo_recuperacao_expira_em", sa.DateTime(), nullable=True)),
        ("codigo_recuperacao_tentativas", sa.Column("codigo_recuperacao_tentativas", sa.Integer(), nullable=False, server_default="0")),
        ("recuperacao_solicitada_em", sa.Column("recuperacao_solicitada_em", sa.DateTime(), nullable=True)),
    )
    for name, column in additions:
        if name not in user_columns:
            op.add_column("usuarios", column)

    indexes = {index["name"] for index in inspector.get_indexes("usuarios")}
    if "ix_usuarios_email" not in indexes:
        op.create_index("ix_usuarios_email", "usuarios", ["email"])
    if "ix_usuarios_bloqueado_ate" not in indexes:
        op.create_index("ix_usuarios_bloqueado_ate", "usuarios", ["bloqueado_ate"])

    order_columns = {column["name"] for column in inspector.get_columns("pedidos_futuros")}
    if "concluido_em" not in order_columns:
        op.add_column("pedidos_futuros", sa.Column("concluido_em", sa.DateTime(), nullable=True))
    if "concluido_por_id" not in order_columns:
        op.add_column("pedidos_futuros", sa.Column(
            "concluido_por_id", sa.Integer(),
            sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True,
        ))
    if "concluido_por_nome" not in order_columns:
        op.add_column("pedidos_futuros", sa.Column("concluido_por_nome", sa.String(120), nullable=True))
    order_indexes = {index["name"] for index in inspector.get_indexes("pedidos_futuros")}
    if "ix_pedidos_futuros_concluido_em" not in order_indexes:
        op.create_index("ix_pedidos_futuros_concluido_em", "pedidos_futuros", ["concluido_em"])
    op.execute(
        "UPDATE pedidos_futuros SET concluido_em = atualizado_em "
        "WHERE concluido_em IS NULL AND UPPER(status) IN ('ENTREGUE', 'RETIRADO')"
    )


def downgrade():
    op.drop_index("ix_pedidos_futuros_concluido_em", table_name="pedidos_futuros")
    op.drop_column("pedidos_futuros", "concluido_por_nome")
    op.drop_column("pedidos_futuros", "concluido_por_id")
    op.drop_column("pedidos_futuros", "concluido_em")
    op.drop_index("ix_usuarios_bloqueado_ate", table_name="usuarios")
    op.drop_index("ix_usuarios_email", table_name="usuarios")
    for column in (
        "recuperacao_solicitada_em", "codigo_recuperacao_tentativas",
        "codigo_recuperacao_expira_em", "codigo_recuperacao_hash",
        "ultimo_login_em", "ultima_falha_login_em", "bloqueado_ate",
        "tentativas_login", "telefone", "email",
    ):
        op.drop_column("usuarios", column)
