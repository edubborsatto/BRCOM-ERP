from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.database import Base


MONEY = Numeric(14, 2)
QUANTITY = Numeric(14, 4)


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    usuario_login = Column(String, unique=True, index=True, nullable=False)
    senha_hash = Column(String, nullable=False)
    pode_gerenciar_usuarios = Column(Boolean, default=False)
    pode_alterar_custos = Column(Boolean, default=False)
    pode_movimentar_estoque = Column(Boolean, default=False)
    pode_gerenciar_clientes = Column(Boolean, default=False)
    pode_acessar_agenda = Column(Boolean, default=False)
    pode_acessar_docs = Column(Boolean, default=False)
    pode_gerenciar_historico = Column(Boolean, default=False)


class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(40), unique=True, index=True, nullable=False)
    nome = Column(String, unique=True, index=True, nullable=False)
    tipo_item = Column(String(20), nullable=False, default="PRODUTO_ACABADO")
    familia = Column(String(80), nullable=True)
    variacao = Column(String(120), nullable=True)
    unidade_medida = Column(String(20), nullable=False)
    quantidade_atual = Column(QUANTITY, default=0)
    estoque_minimo = Column(QUANTITY, default=0)
    preco_custo = Column(MONEY, nullable=False, default=0)
    preco_venda = Column(MONEY, nullable=False, default=0)
    comprimento = Column(Numeric(12, 3), nullable=True)
    largura = Column(Numeric(12, 3), nullable=True)
    resistencia = Column(Numeric(14, 3), nullable=True)
    fator_seguranca = Column(Numeric(8, 2), nullable=True)
    especificacoes = Column(Text, nullable=True)

    formula = relationship(
        "FormulaProduto", back_populates="produto", uselist=False,
        cascade="all, delete-orphan", foreign_keys="FormulaProduto.produto_id",
    )


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    documento = Column(String, unique=True, index=True, nullable=True)
    telefone = Column(String, nullable=True)
    email = Column(String, nullable=True)


class HistoricoEstoque(Base):
    __tablename__ = "historico_estoque"

    id = Column(Integer, primary_key=True, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="SET NULL"), nullable=True)
    produto_nome = Column(String, nullable=False)
    tipo_movimentacao = Column(String(30), nullable=False)
    quantidade = Column(QUANTITY, nullable=False)
    saldo_anterior = Column(QUANTITY, nullable=True)
    saldo_apos = Column(QUANTITY, nullable=False)
    motivo = Column(Text, nullable=True)
    referencia = Column(String(80), nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    usuario_responsavel = Column(String, nullable=False)
    data_hora = Column(DateTime, default=datetime.now, nullable=False)

    produto = relationship("Produto")


class FormulaProduto(Base):
    __tablename__ = "formulas_produto"

    id = Column(Integer, primary_key=True)
    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="CASCADE"), unique=True, nullable=False)
    mao_de_obra = Column(MONEY, nullable=False, default=0)
    custos_adicionais = Column(MONEY, nullable=False, default=0)
    markup_percentual = Column(Numeric(8, 2), nullable=False, default=0)
    observacoes = Column(Text, nullable=True)

    produto = relationship("Produto", back_populates="formula", foreign_keys=[produto_id])
    componentes = relationship("FormulaComponente", back_populates="formula", cascade="all, delete-orphan")


class FormulaComponente(Base):
    __tablename__ = "formula_componentes"

    id = Column(Integer, primary_key=True)
    formula_id = Column(Integer, ForeignKey("formulas_produto.id", ondelete="CASCADE"), nullable=False)
    materia_prima_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    quantidade = Column(QUANTITY, nullable=False)
    perda_percentual = Column(Numeric(8, 2), nullable=False, default=0)

    formula = relationship("FormulaProduto", back_populates="componentes")
    materia_prima = relationship("Produto", foreign_keys=[materia_prima_id])


class Orcamento(Base):
    __tablename__ = "orcamentos"

    id = Column(Integer, primary_key=True)
    numero = Column(String(30), unique=True, index=True, nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    status = Column(String(20), nullable=False, default="RASCUNHO")
    validade = Column(Date, nullable=True)
    observacoes = Column(Text, nullable=True)
    subtotal = Column(MONEY, nullable=False, default=0)
    desconto = Column(MONEY, nullable=False, default=0)
    total = Column(MONEY, nullable=False, default=0)
    criado_em = Column(DateTime, default=datetime.now, nullable=False)
    aprovado_em = Column(DateTime, nullable=True)
    aprovado_por_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)

    cliente = relationship("Cliente")
    itens = relationship("OrcamentoItem", back_populates="orcamento", cascade="all, delete-orphan")
    ordem_servico = relationship("OrdemServico", back_populates="orcamento", uselist=False)


class OrcamentoItem(Base):
    __tablename__ = "orcamento_itens"

    id = Column(Integer, primary_key=True)
    orcamento_id = Column(Integer, ForeignKey("orcamentos.id", ondelete="CASCADE"), nullable=False)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    descricao = Column(Text, nullable=True)
    quantidade = Column(QUANTITY, nullable=False)
    custo_unitario = Column(MONEY, nullable=False)
    preco_unitario = Column(MONEY, nullable=False)
    total = Column(MONEY, nullable=False)

    orcamento = relationship("Orcamento", back_populates="itens")
    produto = relationship("Produto")


class OrdemServico(Base):
    __tablename__ = "ordens_servico"

    id = Column(Integer, primary_key=True)
    numero = Column(String(30), unique=True, index=True, nullable=False)
    orcamento_id = Column(Integer, ForeignKey("orcamentos.id"), unique=True, nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    atividade = Column(Text, nullable=False)
    status = Column(String(20), nullable=False, default="ABERTA")
    data_emissao = Column(Date, nullable=False)
    data_limite = Column(Date, nullable=True)
    concluida_em = Column(DateTime, nullable=True)

    orcamento = relationship("Orcamento", back_populates="ordem_servico")
    cliente = relationship("Cliente")


class Venda(Base):
    __tablename__ = "vendas"

    id = Column(Integer, primary_key=True)
    numero = Column(String(30), unique=True, index=True, nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    orcamento_id = Column(Integer, ForeignKey("orcamentos.id"), nullable=True)
    ordem_servico_id = Column(Integer, ForeignKey("ordens_servico.id"), nullable=True)
    tipo_documento = Column(String(20), nullable=False)
    numero_documento = Column(String(80), nullable=True)
    arquivo_documento = Column(String(500), nullable=True)
    valor_total = Column(MONEY, nullable=False)
    data_venda = Column(Date, nullable=False)
    observacoes = Column(Text, nullable=True)

    cliente = relationship("Cliente")


class Compromisso(Base):
    __tablename__ = "agenda"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, nullable=False)
    descricao = Column(String, nullable=True)
    data_hora = Column(DateTime, nullable=False)
    local = Column(String, nullable=True)


class PedidoFuturo(Base):
    __tablename__ = "pedidos_futuros"

    id = Column(Integer, primary_key=True, index=True)
    cliente_nome = Column(String, nullable=False)
    produto_nome = Column(String, nullable=False)
    quantidade = Column(QUANTITY, nullable=False)
    data_entrega = Column(DateTime, nullable=False)
    status = Column(String, default="Pendente")
