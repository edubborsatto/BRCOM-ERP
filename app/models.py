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
    tipo_usuario = Column(String(20), nullable=False, default="FUNCIONARIO", index=True)
    ativo = Column(Boolean, nullable=False, default=True, index=True)
    pode_gerenciar_usuarios = Column(Boolean, default=False)
    pode_alterar_custos = Column(Boolean, default=False)
    pode_movimentar_estoque = Column(Boolean, default=False)
    pode_gerenciar_clientes = Column(Boolean, default=False)
    pode_acessar_agenda = Column(Boolean, default=False)
    pode_acessar_docs = Column(Boolean, default=False)
    pode_gerenciar_historico = Column(Boolean, default=False)
    pode_criar_orcamentos = Column(Boolean, default=True)
    pode_aprovar_orcamentos = Column(Boolean, default=False)
    pode_registrar_vendas = Column(Boolean, default=True)
    pode_importar_planilhas = Column(Boolean, default=False)
    pode_editar_planilhas = Column(Boolean, default=False)
    pode_ver_faturamento = Column(Boolean, default=False)
    pode_iniciar_producao = Column(Boolean, default=False)
    pode_concluir_producao = Column(Boolean, default=False)
    pode_separar_pedido = Column(Boolean, default=False)
    pode_marcar_pronto = Column(Boolean, default=False)
    pode_registrar_perda = Column(Boolean, default=False)
    pode_concluir_tarefa = Column(Boolean, default=False)
    pode_informar_falta_material = Column(Boolean, default=False)
    pode_colocar_observacao = Column(Boolean, default=False)


class AuditoriaSistema(Base):
    __tablename__ = "auditoria_sistema"

    id = Column(Integer, primary_key=True)
    categoria = Column(String(40), nullable=False, index=True)
    acao = Column(String(40), nullable=False, index=True)
    entidade = Column(String(80), nullable=False)
    entidade_id = Column(Integer, nullable=True, index=True)
    dados_anteriores = Column(Text, nullable=True)
    dados_novos = Column(Text, nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    usuario_nome = Column(String(120), nullable=False)
    criado_em = Column(DateTime, default=datetime.now, nullable=False, index=True)


class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True)
    codigo = Column(String(40), unique=True, index=True, nullable=False)
    nome = Column(String, unique=True, index=True, nullable=False)
    tipo_item = Column(String(20), nullable=False, default="PRODUTO_ACABADO")
    tipo = Column(String(120), nullable=True, index=True)
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
    localizacao = Column(String(255), nullable=True)
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
    pedido_futuro_id = Column(Integer, ForeignKey("pedidos_futuros.id", ondelete="SET NULL"), nullable=True, unique=True)
    status = Column(String(20), nullable=False, default="ATIVA", index=True)
    cancelada_em = Column(DateTime, nullable=True)
    cancelada_por_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    cancelada_por_nome = Column(String(120), nullable=True)
    motivo_cancelamento = Column(Text, nullable=True)

    cliente = relationship("Cliente")


class ImportacaoPlanilha(Base):
    __tablename__ = "importacoes_planilha"

    id = Column(Integer, primary_key=True)
    nome_arquivo = Column(String(255), nullable=False)
    tipo_documento = Column(String(20), nullable=False)
    aba_origem = Column(String(80), nullable=False)
    hash_arquivo = Column(String(64), index=True, nullable=False)
    status = Column(String(20), nullable=False, default="PREVIA")
    total_linhas = Column(Integer, nullable=False, default=0)
    linhas_novas = Column(Integer, nullable=False, default=0)
    linhas_duplicadas = Column(Integer, nullable=False, default=0)
    linhas_revisao = Column(Integer, nullable=False, default=0)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    usuario_nome = Column(String(120), nullable=False)
    criado_em = Column(DateTime, default=datetime.now, nullable=False)
    confirmado_em = Column(DateTime, nullable=True)

    registros = relationship(
        "RegistroVendaImportado", back_populates="importacao",
        cascade="all, delete-orphan",
    )


class RegistroVendaImportado(Base):
    __tablename__ = "registros_venda_importados"

    id = Column(Integer, primary_key=True)
    importacao_id = Column(
        Integer, ForeignKey("importacoes_planilha.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    linha_origem = Column(Integer, nullable=False)
    hash_registro = Column(String(64), nullable=False, index=True)
    hash_duplicidade = Column(String(64), nullable=True, index=True)
    status_importacao = Column(String(20), nullable=False, default="NOVO", index=True)
    decisao_duplicidade = Column(String(20), nullable=True, index=True)
    origem_duplicidade = Column(String(30), nullable=True)
    tipo_documento = Column(String(20), nullable=False, index=True)
    numero_documento = Column(String(80), nullable=True, index=True)
    data_venda = Column(Date, nullable=False, index=True)
    cliente_nome = Column(String(255), nullable=False, index=True)
    cliente_codigo = Column(String(80), nullable=True)
    contato = Column(String(180), nullable=True)
    quantidade = Column(QUANTITY, nullable=False, default=0)
    descricao_original = Column(Text, nullable=False)
    descricao_padronizada = Column(Text, nullable=False)
    produto_id = Column(Integer, ForeignKey("produtos.id", ondelete="SET NULL"), nullable=True)
    familia = Column(String(80), nullable=True, index=True)
    aplicacao = Column(String(100), nullable=True, index=True)
    material = Column(String(100), nullable=True)
    largura = Column(Numeric(12, 3), nullable=True)
    capacidade = Column(Numeric(14, 3), nullable=True)
    comprimento = Column(Numeric(12, 3), nullable=True)
    gancho = Column(String(100), nullable=True)
    reforco = Column(String(100), nullable=True)
    costura = Column(String(100), nullable=True)
    impressao = Column(String(100), nullable=True)
    valor_unitario = Column(MONEY, nullable=False, default=0)
    valor_total = Column(MONEY, nullable=False, default=0)
    desconto = Column(MONEY, nullable=False, default=0)
    percentual_desconto = Column(Numeric(8, 2), nullable=False, default=0)
    status_padronizacao = Column(String(20), nullable=False, default="PADRONIZADO", index=True)
    observacoes = Column(Text, nullable=True)
    ativo = Column(Boolean, nullable=False, default=True, index=True)
    criado_manual = Column(Boolean, nullable=False, default=False)
    atualizado_em = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    atualizado_por_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    atualizado_por_nome = Column(String(120), nullable=True)

    importacao = relationship("ImportacaoPlanilha", back_populates="registros")
    produto = relationship("Produto")


class HistoricoPlanilhaVenda(Base):
    __tablename__ = "historico_planilhas_vendas"

    id = Column(Integer, primary_key=True)
    registro_id = Column(
        Integer,
        ForeignKey("registros_venda_importados.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    acao = Column(String(30), nullable=False, index=True)
    dados_anteriores = Column(Text, nullable=True)
    dados_novos = Column(Text, nullable=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    usuario_nome = Column(String(120), nullable=False)
    criado_em = Column(DateTime, default=datetime.now, nullable=False, index=True)

    registro = relationship("RegistroVendaImportado")


class Compromisso(Base):
    __tablename__ = "agenda"

    id = Column(Integer, primary_key=True, index=True)
    titulo = Column(String, nullable=False)
    descricao = Column(String, nullable=True)
    data_hora = Column(DateTime, nullable=False)
    local = Column(String, nullable=True)
    criado_por_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)


class PedidoFuturo(Base):
    __tablename__ = "pedidos_futuros"

    id = Column(Integer, primary_key=True, index=True)
    cliente_nome = Column(String, nullable=False)
    cliente_id = Column(Integer, ForeignKey("clientes.id", ondelete="RESTRICT"), nullable=True, index=True)
    orcamento_id = Column(Integer, ForeignKey("orcamentos.id", ondelete="SET NULL"), nullable=True, index=True)
    ordem_servico_id = Column(Integer, ForeignKey("ordens_servico.id", ondelete="SET NULL"), nullable=True, index=True)
    venda_id = Column(Integer, ForeignKey("vendas.id", ondelete="SET NULL"), nullable=True, unique=True)
    produto_nome = Column(String, nullable=False)
    quantidade = Column(QUANTITY, nullable=False)
    data_entrega = Column(DateTime, nullable=False)
    status = Column(String, default="Pendente")
    tipo_documento = Column(String(20), nullable=True)
    numero_documento = Column(String(80), nullable=True, index=True)
    modalidade_entrega = Column(String(20), nullable=True)
    confirmado_em = Column(DateTime, nullable=True)
    confirmado_por_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    confirmado_por_nome = Column(String(120), nullable=True)
    fila_posicao = Column(Integer, nullable=False, default=0, index=True)
    prioridade = Column(Boolean, nullable=False, default=False, index=True)
    cancelado_em = Column(DateTime, nullable=True)
    cancelado_por_id = Column(Integer, ForeignKey("usuarios.id", ondelete="SET NULL"), nullable=True)
    cancelado_por_nome = Column(String(120), nullable=True)
    observacoes = Column(Text, nullable=True)
    atualizado_em = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    cliente = relationship("Cliente")
    venda = relationship("Venda", foreign_keys=[venda_id])

    itens = relationship(
        "PedidoFuturoItem", back_populates="pedido", cascade="all, delete-orphan",
        order_by="PedidoFuturoItem.id",
    )


class PedidoFuturoItem(Base):
    __tablename__ = "pedido_futuro_itens"

    id = Column(Integer, primary_key=True)
    pedido_id = Column(
        Integer, ForeignKey("pedidos_futuros.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False, index=True)
    produto_nome = Column(String(255), nullable=False)
    quantidade_total = Column(QUANTITY, nullable=False)
    quantidade_estoque = Column(QUANTITY, nullable=False, default=0)
    quantidade_fabricar = Column(QUANTITY, nullable=False, default=0)

    pedido = relationship("PedidoFuturo", back_populates="itens")
    produto = relationship("Produto", foreign_keys=[produto_id])
    materias_primas = relationship(
        "PedidoFuturoMateriaPrima", back_populates="item",
        cascade="all, delete-orphan", order_by="PedidoFuturoMateriaPrima.id",
    )


class PedidoFuturoMateriaPrima(Base):
    __tablename__ = "pedido_futuro_materias_primas"

    id = Column(Integer, primary_key=True)
    pedido_item_id = Column(
        Integer, ForeignKey("pedido_futuro_itens.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    materia_prima_id = Column(Integer, ForeignKey("produtos.id"), nullable=False, index=True)
    materia_prima_nome = Column(String(255), nullable=False)
    quantidade_reservada = Column(QUANTITY, nullable=False)

    item = relationship("PedidoFuturoItem", back_populates="materias_primas")
    materia_prima = relationship("Produto", foreign_keys=[materia_prima_id])
