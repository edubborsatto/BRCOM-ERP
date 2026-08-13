"""Integra módulos, permissões operacionais e cancelamento lógico.

Revision ID: 20260812_08
Revises: 20260811_07
"""
from alembic import op
import sqlalchemy as sa

revision = "20260812_08"
down_revision = "20260811_07"
branch_labels = None
depends_on = None


def upgrade():
    # Os testes criam o metadata atual antes de percorrer o histórico Alembic.
    # Nesse cenário a estrutura já está completa e a revisão só precisa ser marcada.
    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("usuarios")}
    order_columns = {column["name"] for column in inspector.get_columns("pedidos_futuros")}
    sale_columns = {column["name"] for column in inspector.get_columns("vendas")}
    if {"pode_iniciar_producao", "pode_concluir_tarefa"} <= user_columns and \
       {"cliente_id", "venda_id"} <= order_columns and \
       {"status", "pedido_futuro_id"} <= sale_columns:
        return
    for name in (
        "pode_iniciar_producao", "pode_concluir_producao", "pode_separar_pedido",
        "pode_marcar_pronto", "pode_registrar_perda", "pode_concluir_tarefa",
    ):
        op.add_column("usuarios", sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("""UPDATE usuarios SET
        pode_iniciar_producao=true, pode_concluir_producao=true,
        pode_separar_pedido=true, pode_marcar_pronto=true,
        pode_registrar_perda=true, pode_concluir_tarefa=true""")
    op.execute("""UPDATE usuarios SET
        pode_movimentar_estoque=false, pode_gerenciar_clientes=false,
        pode_criar_orcamentos=false, pode_registrar_vendas=false
        WHERE tipo_usuario='FUNCIONARIO'""")

    op.add_column("agenda", sa.Column("criado_por_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_agenda_usuario", "agenda", "usuarios", ["criado_por_id"], ["id"], ondelete="SET NULL")

    op.add_column("pedidos_futuros", sa.Column("cliente_id", sa.Integer(), nullable=True))
    op.add_column("pedidos_futuros", sa.Column("orcamento_id", sa.Integer(), nullable=True))
    op.add_column("pedidos_futuros", sa.Column("ordem_servico_id", sa.Integer(), nullable=True))
    op.add_column("pedidos_futuros", sa.Column("venda_id", sa.Integer(), nullable=True))
    op.add_column("pedidos_futuros", sa.Column("observacoes", sa.Text(), nullable=True))
    op.add_column("pedidos_futuros", sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()))
    op.create_foreign_key("fk_pedido_cliente", "pedidos_futuros", "clientes", ["cliente_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_pedido_orcamento", "pedidos_futuros", "orcamentos", ["orcamento_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_pedido_os", "pedidos_futuros", "ordens_servico", ["ordem_servico_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_pedidos_futuros_cliente_id", "pedidos_futuros", ["cliente_id"])
    op.create_index("ix_pedidos_futuros_status_entrega", "pedidos_futuros", ["status", "data_entrega"])

    op.add_column("vendas", sa.Column("pedido_futuro_id", sa.Integer(), nullable=True))
    op.add_column("vendas", sa.Column("status", sa.String(20), nullable=False, server_default="ATIVA"))
    op.add_column("vendas", sa.Column("cancelada_em", sa.DateTime(), nullable=True))
    op.add_column("vendas", sa.Column("cancelada_por_id", sa.Integer(), nullable=True))
    op.add_column("vendas", sa.Column("cancelada_por_nome", sa.String(120), nullable=True))
    op.add_column("vendas", sa.Column("motivo_cancelamento", sa.Text(), nullable=True))
    op.create_foreign_key("fk_venda_pedido", "vendas", "pedidos_futuros", ["pedido_futuro_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_venda_cancelada_por", "vendas", "usuarios", ["cancelada_por_id"], ["id"], ondelete="SET NULL")
    op.create_unique_constraint("uq_venda_pedido", "vendas", ["pedido_futuro_id"])
    op.create_index("ix_vendas_status_data", "vendas", ["status", "data_venda"])

    # Relaciona clientes legados apenas quando o nome identifica um único cadastro.
    op.execute("""UPDATE pedidos_futuros p SET cliente_id = c.id
        FROM clientes c WHERE p.cliente_id IS NULL AND lower(trim(p.cliente_nome))=lower(trim(c.nome))
        AND (SELECT count(*) FROM clientes c2 WHERE lower(trim(c2.nome))=lower(trim(p.cliente_nome)))=1""")

    op.create_foreign_key("fk_pedido_venda", "pedidos_futuros", "vendas", ["venda_id"], ["id"], ondelete="SET NULL")
    op.create_unique_constraint("uq_pedido_venda", "pedidos_futuros", ["venda_id"])


def downgrade():
    op.drop_constraint("uq_pedido_venda", "pedidos_futuros", type_="unique")
    op.drop_constraint("fk_pedido_venda", "pedidos_futuros", type_="foreignkey")
    op.drop_index("ix_vendas_status_data", table_name="vendas")
    op.drop_constraint("uq_venda_pedido", "vendas", type_="unique")
    op.drop_constraint("fk_venda_cancelada_por", "vendas", type_="foreignkey")
    op.drop_constraint("fk_venda_pedido", "vendas", type_="foreignkey")
    for name in ("motivo_cancelamento", "cancelada_por_nome", "cancelada_por_id", "cancelada_em", "status", "pedido_futuro_id"):
        op.drop_column("vendas", name)
    op.drop_index("ix_pedidos_futuros_status_entrega", table_name="pedidos_futuros")
    op.drop_index("ix_pedidos_futuros_cliente_id", table_name="pedidos_futuros")
    for constraint in ("fk_pedido_os", "fk_pedido_orcamento", "fk_pedido_cliente"):
        op.drop_constraint(constraint, "pedidos_futuros", type_="foreignkey")
    for name in ("atualizado_em", "observacoes", "venda_id", "ordem_servico_id", "orcamento_id", "cliente_id"):
        op.drop_column("pedidos_futuros", name)
    op.drop_constraint("fk_agenda_usuario", "agenda", type_="foreignkey")
    op.drop_column("agenda", "criado_por_id")
    for name in ("pode_concluir_tarefa", "pode_registrar_perda", "pode_marcar_pronto", "pode_separar_pedido", "pode_concluir_producao", "pode_iniciar_producao"):
        op.drop_column("usuarios", name)
