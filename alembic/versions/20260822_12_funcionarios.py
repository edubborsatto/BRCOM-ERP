"""Cadastro protegido de funcionários e vínculo com contas.

Revision ID: 20260822_12
Revises: 20260822_11
"""
from alembic import op
import sqlalchemy as sa


revision = "20260822_12"
down_revision = "20260822_11"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("usuarios")}
    if "pode_gerenciar_funcionarios" not in user_columns:
        op.add_column(
            "usuarios",
            sa.Column(
                "pode_gerenciar_funcionarios",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
    op.execute(
        "UPDATE usuarios SET pode_gerenciar_funcionarios=true "
        "WHERE tipo_usuario IN ('DONO','DESENVOLVEDOR')"
    )

    if "funcionarios" in set(inspector.get_table_names()):
        return
    op.create_table(
        "funcionarios",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("usuario_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("matricula", sa.String(40), nullable=True),
        sa.Column("nome_completo", sa.String(160), nullable=False),
        sa.Column("nome_social", sa.String(160), nullable=True),
        sa.Column("cpf", sa.String(11), nullable=False),
        sa.Column("rg", sa.String(30), nullable=False),
        sa.Column("orgao_emissor_rg", sa.String(30), nullable=True),
        sa.Column("uf_rg", sa.String(2), nullable=True),
        sa.Column("data_nascimento", sa.Date(), nullable=False),
        sa.Column("email_pessoal", sa.String(255), nullable=False),
        sa.Column("email_corporativo", sa.String(255), nullable=True),
        sa.Column("celular", sa.String(20), nullable=False),
        sa.Column("telefone", sa.String(20), nullable=True),
        sa.Column("cep", sa.String(8), nullable=False),
        sa.Column("logradouro", sa.String(255), nullable=False),
        sa.Column("numero", sa.String(30), nullable=False),
        sa.Column("complemento", sa.String(120), nullable=True),
        sa.Column("bairro", sa.String(120), nullable=False),
        sa.Column("cidade", sa.String(120), nullable=False),
        sa.Column("uf", sa.String(2), nullable=False),
        sa.Column("pis_pasep", sa.String(20), nullable=True),
        sa.Column("ctps_numero", sa.String(30), nullable=True),
        sa.Column("ctps_serie", sa.String(20), nullable=True),
        sa.Column("ctps_uf", sa.String(2), nullable=True),
        sa.Column("departamento", sa.String(120), nullable=False),
        sa.Column("cargo", sa.String(120), nullable=False),
        sa.Column("tipo_contrato", sa.String(30), nullable=False, server_default="CLT"),
        sa.Column("data_admissao", sa.Date(), nullable=False),
        sa.Column("salario_base", sa.Numeric(14, 2), nullable=True),
        sa.Column("jornada_semanal", sa.Numeric(5, 2), nullable=True),
        sa.Column("gestor", sa.String(160), nullable=True),
        sa.Column("contato_emergencia_nome", sa.String(160), nullable=False),
        sa.Column("contato_emergencia_parentesco", sa.String(80), nullable=False),
        sa.Column("contato_emergencia_telefone", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ATIVO"),
        sa.Column("data_desligamento", sa.Date(), nullable=True),
        sa.Column("motivo_desligamento", sa.Text(), nullable=True),
        sa.Column("observacoes", sa.Text(), nullable=True),
        sa.Column("criado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("atualizado_em", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("criado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("criado_por_nome", sa.String(120), nullable=False),
        sa.Column("atualizado_por_id", sa.Integer(), sa.ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True),
        sa.Column("atualizado_por_nome", sa.String(120), nullable=False),
        sa.UniqueConstraint("usuario_id", name="uq_funcionarios_usuario_id"),
        sa.UniqueConstraint("matricula", name="uq_funcionarios_matricula"),
        sa.UniqueConstraint("cpf", name="uq_funcionarios_cpf"),
        sa.UniqueConstraint("pis_pasep", name="uq_funcionarios_pis_pasep"),
    )
    for name, columns in (
        ("ix_funcionarios_usuario_id", ["usuario_id"]),
        ("ix_funcionarios_matricula", ["matricula"]),
        ("ix_funcionarios_nome_completo", ["nome_completo"]),
        ("ix_funcionarios_cpf", ["cpf"]),
        ("ix_funcionarios_rg", ["rg"]),
        ("ix_funcionarios_email_pessoal", ["email_pessoal"]),
        ("ix_funcionarios_email_corporativo", ["email_corporativo"]),
        ("ix_funcionarios_cidade", ["cidade"]),
        ("ix_funcionarios_uf", ["uf"]),
        ("ix_funcionarios_departamento", ["departamento"]),
        ("ix_funcionarios_cargo", ["cargo"]),
        ("ix_funcionarios_tipo_contrato", ["tipo_contrato"]),
        ("ix_funcionarios_data_admissao", ["data_admissao"]),
        ("ix_funcionarios_status", ["status"]),
        ("ix_funcionarios_data_desligamento", ["data_desligamento"]),
        ("ix_funcionarios_criado_em", ["criado_em"]),
        ("ix_funcionarios_atualizado_em", ["atualizado_em"]),
    ):
        op.create_index(name, "funcionarios", columns)


def downgrade():
    op.drop_table("funcionarios")
    op.drop_column("usuarios", "pode_gerenciar_funcionarios")
