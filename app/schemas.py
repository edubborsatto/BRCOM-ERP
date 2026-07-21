from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UsuarioBase(BaseModel):
    nome: str
    usuario_login: str
    pode_gerenciar_usuarios: bool = False
    pode_alterar_custos: bool = False
    pode_movimentar_estoque: bool = False
    pode_gerenciar_clientes: bool = False
    pode_acessar_agenda: bool = False
    pode_acessar_docs: bool = False
    pode_gerenciar_historico: bool = False


class UsuarioCreate(UsuarioBase):
    senha: str = Field(min_length=12, max_length=128)


class UsuarioUpdate(UsuarioBase):
    senha: Optional[str] = Field(default=None, min_length=12, max_length=128)


class UsuarioResponse(UsuarioBase, OrmModel):
    id: int


class ProdutoBase(BaseModel):
    nome: str
    unidade_medida: str
    quantidade_atual: float
    estoque_minimo: float
    preco_custo: float
    preco_venda: float


class ProdutoCreate(ProdutoBase):
    pass


class ProdutoResponse(ProdutoBase, OrmModel):
    id: int


class ClienteBase(BaseModel):
    nome: str
    documento: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None


class ClienteCreate(ClienteBase):
    pass


class ClienteResponse(ClienteBase, OrmModel):
    id: int


class HistoricoResponse(OrmModel):
    id: int
    produto_nome: str
    tipo_movimentacao: str
    quantidade: float
    saldo_apos: float
    usuario_responsavel: str
    data_hora: datetime


class CompromissoBase(BaseModel):
    titulo: str
    descricao: Optional[str] = None
    data_hora: datetime
    local: Optional[str] = None


class CompromissoCreate(CompromissoBase):
    pass


class CompromissoResponse(CompromissoBase, OrmModel):
    id: int


class PedidoFuturoBase(BaseModel):
    cliente_nome: str
    produto_nome: str
    quantidade: float
    data_entrega: datetime
    status: str = "Pendente"


class PedidoFuturoCreate(PedidoFuturoBase):
    pass


class PedidoFuturoResponse(PedidoFuturoBase, OrmModel):
    id: int


class LoginRequest(BaseModel):
    usuario_login: str
    senha: str


class LoginResponse(BaseModel):
    status: str
    usuario: UsuarioResponse
