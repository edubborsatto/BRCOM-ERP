from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# USUÁRIO
class UsuarioBase(BaseModel):
    nome: str
    usuario_login: str
    pode_gerenciar_usuarios: bool = False
    pode_alterar_custos: bool = False
    pode_movimentar_estoque: bool = False
    pode_gerenciar_clientes: bool = False

class UsuarioCreate(UsuarioBase):
    senha: str

class UsuarioResponse(UsuarioBase):
    id: int
    class Config:
        from_attributes = True

# PRODUTO
class ProdutoBase(BaseModel):
    nome: str
    unidade_medida: str
    quantidade_atual: float
    estoque_minimo: float
    preco_custo: float
    preco_venda: float

class ProdutoCreate(ProdutoBase):
    pass

class ProdutoResponse(ProdutoBase):
    id: int
    class Config:
        from_attributes = True

# CLIENTE
class ClienteBase(BaseModel):
    nome: str
    documento: Optional[str] = None
    telefone: Optional[str] = None
    email: Optional[str] = None

class ClienteCreate(ClienteBase):
    pass

class ClienteResponse(ClienteBase):
    id: int
    class Config:
        from_attributes = True

# HISTÓRICO ESTOQUE
class HistoricoResponse(BaseModel):
    id: int
    produto_nome: str
    tipo_movimentacao: str
    quantidade: float
    saldo_apos: float
    usuario_responsavel: str
    data_hora: datetime
    class Config:
        from_attributes = True

# COMPROMISSO AGENDA
class CompromissoBase(BaseModel):
    titulo: str
    descricao: Optional[str] = None
    data_hora: datetime
    local: Optional[str] = None

class CompromissoCreate(CompromissoBase):
    pass

class CompromissoResponse(CompromissoBase):
    id: int
    class Config:
        from_attributes = True

# PEDIDOS FUTUROS
class PedidoFuturoBase(BaseModel):
    cliente_nome: str
    produto_nome: str
    quantidade: float
    data_entrega: datetime
    status: str = "Pendente"

class PedidoFuturoCreate(PedidoFuturoBase):
    pass

class PedidoFuturoResponse(PedidoFuturoBase):
    id: int
    class Config:
        from_attributes = True

# LOGIN
class LoginRequest(BaseModel):
    usuario_login: str
    senha: str
