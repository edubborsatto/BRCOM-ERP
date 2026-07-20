from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from datetime import datetime
from app.database import Base

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

class Produto(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True, index=True, nullable=False)
    unidade_medida = Column(String, nullable=False)
    quantidade_atual = Column(Float, default=0.0)
    estoque_minimo = Column(Float, default=0.0)
    preco_custo = Column(Float, nullable=False)
    preco_venda = Column(Float, nullable=False)

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
    produto_nome = Column(String, nullable=False)
    tipo_movimentacao = Column(String, nullable=False)
    quantidade = Column(Float, nullable=False)
    saldo_apos = Column(Float, nullable=False)
    usuario_responsavel = Column(String, nullable=False)
    data_hora = Column(DateTime, default=datetime.now)

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
    quantidade = Column(Float, nullable=False)
    data_entrega = Column(DateTime, nullable=False)
    status = Column(String, default="Pendente")
