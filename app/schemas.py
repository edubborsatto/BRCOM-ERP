from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UsuarioPermissions(BaseModel):
    pode_gerenciar_usuarios: bool = False
    pode_alterar_custos: bool = False
    pode_movimentar_estoque: bool = False
    pode_gerenciar_clientes: bool = False
    pode_acessar_agenda: bool = False
    pode_acessar_docs: bool = False
    pode_gerenciar_historico: bool = False
    pode_criar_orcamentos: bool = True
    pode_aprovar_orcamentos: bool = False
    pode_registrar_vendas: bool = True
    pode_importar_planilhas: bool = False
    pode_editar_planilhas: bool = False
    pode_ver_faturamento: bool = False


class UsuarioBase(UsuarioPermissions):
    nome: str
    usuario_login: str
    tipo_usuario: Literal["DESENVOLVEDOR", "DONO", "FUNCIONARIO"] = "FUNCIONARIO"
    ativo: bool = True


class UsuarioCreate(UsuarioBase):
    senha: str = Field(min_length=12, max_length=128)
    confirmar_desenvolvedor: bool = False


class UsuarioUpdate(UsuarioBase):
    senha: Optional[str] = Field(default=None, min_length=12, max_length=128)
    confirmar_desenvolvedor: bool = False


class UsuarioResponse(UsuarioBase, OrmModel):
    id: int


class AuditoriaSistemaResponse(OrmModel):
    id: int
    categoria: str
    acao: str
    entidade: str
    entidade_id: Optional[int] = None
    dados_anteriores: Optional[str] = None
    dados_novos: Optional[str] = None
    usuario_nome: str
    criado_em: datetime


class ProdutoBase(BaseModel):
    codigo: str = Field(default="AUTO", min_length=2, max_length=40)
    nome: str = Field(min_length=2)
    tipo_item: Literal["MATERIA_PRIMA", "PRODUTO_ACABADO"] = "PRODUTO_ACABADO"
    tipo: Optional[str] = None
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
    localizacao: Optional[str] = Field(default=None, max_length=255)
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
    numero_documento: str = Field(min_length=1, max_length=80)
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

    @field_validator("numero_documento")
    @classmethod
    def validar_numero_documento(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Informe o número da nota fiscal ou do recibo")
        return value


class VendaResponse(VendaCreate, OrmModel):
    id: int
    numero: str
    cliente: ClienteResponse


class RegistroImportadoUpdate(BaseModel):
    descricao_padronizada: str = Field(min_length=2)
    produto_id: Optional[int] = None
    familia: Optional[str] = None
    aplicacao: Optional[str] = None
    material: Optional[str] = None
    largura: Optional[Decimal] = Field(default=None, ge=0)
    capacidade: Optional[Decimal] = Field(default=None, ge=0)
    comprimento: Optional[Decimal] = Field(default=None, ge=0)
    gancho: Optional[str] = None
    reforco: Optional[str] = None
    costura: Optional[str] = None
    impressao: Optional[str] = None
    status_padronizacao: Literal["REVISAR", "PADRONIZADO"] = "PADRONIZADO"
    observacoes: Optional[str] = None


class RegistroImportadoResponse(OrmModel):
    id: int
    importacao_id: int
    linha_origem: int
    status_importacao: str
    decisao_duplicidade: Optional[str] = None
    origem_duplicidade: Optional[str] = None
    tipo_documento: str
    numero_documento: Optional[str] = None
    data_venda: date
    cliente_nome: str
    cliente_codigo: Optional[str] = None
    contato: Optional[str] = None
    quantidade: Decimal
    descricao_original: str
    descricao_padronizada: str
    produto_id: Optional[int] = None
    familia: Optional[str] = None
    aplicacao: Optional[str] = None
    material: Optional[str] = None
    largura: Optional[Decimal] = None
    capacidade: Optional[Decimal] = None
    comprimento: Optional[Decimal] = None
    gancho: Optional[str] = None
    reforco: Optional[str] = None
    costura: Optional[str] = None
    impressao: Optional[str] = None
    valor_unitario: Decimal
    valor_total: Decimal
    desconto: Decimal
    percentual_desconto: Decimal
    status_padronizacao: str
    observacoes: Optional[str] = None
    ativo: bool = True
    criado_manual: bool = False
    atualizado_em: Optional[datetime] = None
    atualizado_por_nome: Optional[str] = None


class PlanilhaVendaCreate(BaseModel):
    tipo_documento: Literal["RECIBO", "NOTA_FISCAL"]
    numero_documento: Optional[str] = None
    data_venda: date
    cliente_nome: str = Field(min_length=2, max_length=255)
    cliente_codigo: Optional[str] = None
    contato: Optional[str] = None
    quantidade: Decimal = Field(gt=0)
    descricao_original: str = Field(min_length=2)
    descricao_padronizada: Optional[str] = None
    familia: Optional[str] = None
    valor_unitario: Decimal = Field(default=Decimal("0"), ge=0)
    valor_total: Decimal = Field(gt=0)
    desconto: Decimal = Field(default=Decimal("0"), ge=0)
    percentual_desconto: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    observacoes: Optional[str] = None


class PlanilhaVendaUpdate(BaseModel):
    numero_documento: Optional[str] = None
    data_venda: Optional[date] = None
    cliente_nome: Optional[str] = Field(default=None, min_length=2, max_length=255)
    cliente_codigo: Optional[str] = None
    contato: Optional[str] = None
    quantidade: Optional[Decimal] = Field(default=None, gt=0)
    descricao_original: Optional[str] = Field(default=None, min_length=2)
    descricao_padronizada: Optional[str] = Field(default=None, min_length=2)
    familia: Optional[str] = None
    valor_unitario: Optional[Decimal] = Field(default=None, ge=0)
    valor_total: Optional[Decimal] = Field(default=None, gt=0)
    desconto: Optional[Decimal] = Field(default=None, ge=0)
    percentual_desconto: Optional[Decimal] = Field(default=None, ge=0, le=100)
    observacoes: Optional[str] = None


class HistoricoPlanilhaResponse(OrmModel):
    id: int
    registro_id: int
    acao: str
    dados_anteriores: Optional[str] = None
    dados_novos: Optional[str] = None
    usuario_nome: str
    criado_em: datetime


class ImportacaoResponse(OrmModel):
    id: int
    nome_arquivo: str
    tipo_documento: str
    aba_origem: str
    status: str
    total_linhas: int
    linhas_novas: int
    linhas_duplicadas: int
    linhas_revisao: int
    usuario_nome: str
    criado_em: datetime
    confirmado_em: Optional[datetime] = None


class DecisaoDuplicidade(BaseModel):
    decisao: Literal["IGNORAR", "IMPORTAR"]


class CompromissoBase(BaseModel):
    titulo: str
    descricao: Optional[str] = None
    data_hora: datetime
    local: Optional[str] = None


class CompromissoCreate(CompromissoBase):
    pass


class CompromissoResponse(CompromissoBase, OrmModel):
    id: int


class PedidoMateriaPrimaCreate(BaseModel):
    materia_prima_id: int
    quantidade: Decimal = Field(gt=0)


class PedidoMateriaPrimaResponse(OrmModel):
    id: int
    materia_prima_id: int
    materia_prima_nome: str
    quantidade_reservada: Decimal


class PedidoItemCreate(BaseModel):
    produto_id: int
    quantidade_total: Decimal = Field(gt=0)
    quantidade_estoque: Decimal = Field(default=Decimal("0"), ge=0)
    quantidade_fabricar: Decimal = Field(default=Decimal("0"), ge=0)
    materias_primas: list[PedidoMateriaPrimaCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validar_divisao(self):
        if self.quantidade_estoque + self.quantidade_fabricar != self.quantidade_total:
            raise ValueError(
                "Quantidade do estoque + quantidade a fabricar deve ser igual à quantidade total"
            )
        if self.quantidade_fabricar > 0 and not self.materias_primas:
            raise ValueError("Informe as matérias-primas da quantidade a fabricar")
        if self.quantidade_fabricar == 0 and self.materias_primas:
            raise ValueError("Matérias-primas só podem ser informadas quando houver fabricação")
        return self


class PedidoItemResponse(OrmModel):
    id: int
    produto_id: int
    produto_nome: str
    quantidade_total: Decimal
    quantidade_estoque: Decimal
    quantidade_fabricar: Decimal
    materias_primas: list[PedidoMateriaPrimaResponse] = Field(default_factory=list)


class PedidoFuturoCreate(BaseModel):
    cliente_nome: str = Field(min_length=2, max_length=255)
    data_entrega: datetime
    prioridade: bool = False
    itens: list[PedidoItemCreate] = Field(default_factory=list)
    # Campos legados mantidos para aceitar cadastros da v4.6.1 durante a transição.
    produto_nome: Optional[str] = None
    quantidade: Optional[Decimal] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validar_itens_ou_legado(self):
        if not self.itens and not (self.produto_nome and self.quantidade):
            raise ValueError("Inclua pelo menos um produto no pedido")
        return self


class PedidoFuturoResponse(OrmModel):
    id: int
    cliente_nome: str
    produto_nome: str
    quantidade: Decimal
    data_entrega: datetime
    status: str
    fila_posicao: int = 0
    prioridade: bool = False
    tipo_documento: Optional[Literal["RECIBO", "NOTA_FISCAL"]] = None
    numero_documento: Optional[str] = None
    confirmado_em: Optional[datetime] = None
    confirmado_por_nome: Optional[str] = None
    cancelado_em: Optional[datetime] = None
    cancelado_por_nome: Optional[str] = None
    itens: list[PedidoItemResponse] = Field(default_factory=list)


class ReordenarFilaPedidos(BaseModel):
    pedidos_ids: list[int] = Field(min_length=1)

    @field_validator("pedidos_ids")
    @classmethod
    def ids_unicos(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("A fila não pode conter pedidos repetidos")
        return value


class ConfirmacaoVendaPedido(BaseModel):
    tipo_documento: Literal["RECIBO", "NOTA_FISCAL"]
    numero_documento: str = Field(min_length=1, max_length=80)

    @field_validator("numero_documento")
    @classmethod
    def limpar_numero_documento(cls, value: str) -> str:
        return value.strip()


class LoginRequest(BaseModel):
    usuario_login: str
    senha: str


class LoginResponse(BaseModel):
    status: str
    usuario: UsuarioResponse
