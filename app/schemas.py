from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    codigo: str = Field(default="AUTO", min_length=2, max_length=40)
    nome: str = Field(min_length=2)
    tipo_item: Literal["MATERIA_PRIMA", "PRODUTO_ACABADO"] = "PRODUTO_ACABADO"
    familia: Optional[str] = None
    variacao: Optional[str] = None
    unidade_medida: str
    quantidade_atual: Decimal = Field(default=Decimal("0"), ge=0)
    estoque_minimo: Decimal = Field(default=Decimal("0"), ge=0)
    preco_custo: Decimal = Field(default=Decimal("0"), ge=0)
    preco_venda: Decimal = Field(default=Decimal("0"), ge=0)
    comprimento: Optional[Decimal] = Field(default=None, ge=0)
    largura: Optional[Decimal] = Field(default=None, ge=0)
    resistencia: Optional[Decimal] = Field(default=None, ge=0)
    fator_seguranca: Optional[Decimal] = Field(default=None, ge=0)
    especificacoes: Optional[str] = None

    @field_validator("codigo")
    @classmethod
    def normalizar_codigo(cls, value: str) -> str:
        return value.strip().upper()


class ProdutoCreate(ProdutoBase):
    pass


class ProdutoUpdate(ProdutoBase):
    quantidade_atual: Optional[Decimal] = None


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


class MovimentacaoCreate(BaseModel):
    produto_id: int
    tipo_movimentacao: Literal["ENTRADA", "SAIDA", "AJUSTE", "PERDA", "CONSUMO_PRODUCAO"]
    quantidade: Decimal = Field(gt=0)
    motivo: str = Field(min_length=3)
    referencia: Optional[str] = None
    saldo_final_ajuste: Optional[Decimal] = Field(default=None, ge=0)


class HistoricoResponse(OrmModel):
    id: int
    produto_id: Optional[int] = None
    produto_nome: str
    tipo_movimentacao: str
    quantidade: Decimal
    saldo_anterior: Optional[Decimal] = None
    saldo_apos: Decimal
    motivo: Optional[str] = None
    referencia: Optional[str] = None
    usuario_responsavel: str
    data_hora: datetime


class FormulaComponenteCreate(BaseModel):
    materia_prima_id: int
    quantidade: Decimal = Field(gt=0)
    perda_percentual: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class FormulaCreate(BaseModel):
    produto_id: int
    mao_de_obra: Decimal = Field(default=Decimal("0"), ge=0)
    custos_adicionais: Decimal = Field(default=Decimal("0"), ge=0)
    markup_percentual: Decimal = Field(default=Decimal("0"), ge=0)
    observacoes: Optional[str] = None
    componentes: list[FormulaComponenteCreate] = Field(min_length=1)


class FormulaComponenteResponse(FormulaComponenteCreate, OrmModel):
    id: int
    materia_prima: ProdutoResponse


class FormulaResponse(OrmModel):
    id: int
    produto_id: int
    mao_de_obra: Decimal
    custos_adicionais: Decimal
    markup_percentual: Decimal
    observacoes: Optional[str] = None
    componentes: list[FormulaComponenteResponse]
    custo_materia_prima: Decimal
    custo_total: Decimal
    preco_sugerido: Decimal


class OrcamentoItemCreate(BaseModel):
    produto_id: int
    quantidade: Decimal = Field(gt=0)
    descricao: Optional[str] = None
    preco_unitario: Optional[Decimal] = Field(default=None, ge=0)


class OrcamentoCreate(BaseModel):
    cliente_id: int
    validade: Optional[date] = None
    observacoes: Optional[str] = None
    desconto: Decimal = Field(default=Decimal("0"), ge=0)
    itens: list[OrcamentoItemCreate] = Field(min_length=1)


class OrcamentoItemResponse(OrmModel):
    id: int
    produto_id: int
    descricao: Optional[str] = None
    quantidade: Decimal
    custo_unitario: Decimal
    preco_unitario: Decimal
    total: Decimal
    produto: ProdutoResponse


class OrcamentoResponse(OrmModel):
    id: int
    numero: str
    cliente_id: int
    status: str
    validade: Optional[date] = None
    observacoes: Optional[str] = None
    subtotal: Decimal
    desconto: Decimal
    total: Decimal
    criado_em: datetime
    aprovado_em: Optional[datetime] = None
    cliente: ClienteResponse
    itens: list[OrcamentoItemResponse]
    ordem_servico_id: Optional[int] = None


class AprovacaoOrcamento(BaseModel):
    data_limite: Optional[date] = None
    atividade: Optional[str] = None


class OrdemServicoResponse(OrmModel):
    id: int
    numero: str
    orcamento_id: int
    cliente_id: int
    atividade: str
    status: str
    data_emissao: date
    data_limite: Optional[date] = None
    concluida_em: Optional[datetime] = None
    cliente: ClienteResponse


class VendaCreate(BaseModel):
    cliente_id: int
    orcamento_id: Optional[int] = None
    ordem_servico_id: Optional[int] = None
    tipo_documento: Literal["RECIBO", "NOTA_FISCAL"]
    numero_documento: Optional[str] = None
    arquivo_documento: Optional[str] = None
    valor_total: Decimal = Field(gt=0)
    data_venda: date
    observacoes: Optional[str] = None

    @field_validator("arquivo_documento")
    @classmethod
    def validar_link_documento(cls, value: Optional[str]) -> Optional[str]:
        if value and not value.lower().startswith(("https://", "http://")):
            raise ValueError("O arquivo deve ser um link iniciado por http:// ou https://")
        return value


class VendaResponse(VendaCreate, OrmModel):
    id: int
    numero: str
    cliente: ClienteResponse


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
    quantidade: Decimal
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
