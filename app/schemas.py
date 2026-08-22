import re
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UsuarioPermissions(BaseModel):
    pode_gerenciar_usuarios: bool = False
    pode_gerenciar_funcionarios: bool = False
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
    pode_iniciar_producao: bool = False
    pode_concluir_producao: bool = False
    pode_separar_pedido: bool = False
    pode_marcar_pronto: bool = False
    pode_registrar_perda: bool = False
    pode_concluir_tarefa: bool = False
    pode_informar_falta_material: bool = False
    pode_colocar_observacao: bool = False
    pode_enviar_sugestoes: bool = True
    pode_administrar_sugestoes: bool = False


class UsuarioBase(UsuarioPermissions):
    nome: str
    usuario_login: str
    email: Optional[str] = Field(default=None, max_length=255)
    telefone: Optional[str] = Field(default=None, max_length=40)
    tipo_usuario: Literal["DESENVOLVEDOR", "DONO", "FUNCIONARIO"] = "FUNCIONARIO"
    ativo: bool = True

    @field_validator("email", "telefone")
    @classmethod
    def limpar_contato(cls, value: Optional[str]) -> Optional[str]:
        return value.strip() if value and value.strip() else None


class UsuarioCreate(UsuarioBase):
    senha: str = Field(min_length=12, max_length=128)
    confirmar_desenvolvedor: bool = False


class UsuarioUpdate(UsuarioBase):
    senha: Optional[str] = Field(default=None, min_length=12, max_length=128)
    confirmar_desenvolvedor: bool = False


class UsuarioResponse(UsuarioBase, OrmModel):
    id: int
    bloqueado_ate: Optional[datetime] = None
    ultimo_login_em: Optional[datetime] = None


def _somente_digitos(value: str) -> str:
    return re.sub(r"\D", "", value)


def _cpf_valido(cpf: str) -> bool:
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[indice]) * (tamanho + 1 - indice) for indice in range(tamanho))
        digito = (soma * 10 % 11) % 10
        if digito != int(cpf[tamanho]):
            return False
    return True


class FuncionarioBase(BaseModel):
    matricula: Optional[str] = Field(default=None, max_length=40)
    usuario_id: Optional[int] = Field(default=None, ge=1)
    nome_completo: str = Field(min_length=2, max_length=160)
    nome_social: Optional[str] = Field(default=None, max_length=160)
    cpf: str = Field(min_length=11, max_length=18)
    rg: str = Field(min_length=3, max_length=30)
    orgao_emissor_rg: Optional[str] = Field(default=None, max_length=30)
    uf_rg: Optional[str] = Field(default=None, min_length=2, max_length=2)
    data_nascimento: date
    email_pessoal: str = Field(min_length=5, max_length=255)
    email_corporativo: Optional[str] = Field(default=None, max_length=255)
    celular: str = Field(min_length=10, max_length=20)
    telefone: Optional[str] = Field(default=None, max_length=20)
    cep: str = Field(min_length=8, max_length=10)
    logradouro: str = Field(min_length=2, max_length=255)
    numero: str = Field(min_length=1, max_length=30)
    complemento: Optional[str] = Field(default=None, max_length=120)
    bairro: str = Field(min_length=2, max_length=120)
    cidade: str = Field(min_length=2, max_length=120)
    uf: str = Field(min_length=2, max_length=2)
    pis_pasep: Optional[str] = Field(default=None, max_length=20)
    ctps_numero: Optional[str] = Field(default=None, max_length=30)
    ctps_serie: Optional[str] = Field(default=None, max_length=20)
    ctps_uf: Optional[str] = Field(default=None, min_length=2, max_length=2)
    departamento: str = Field(min_length=2, max_length=120)
    cargo: str = Field(min_length=2, max_length=120)
    tipo_contrato: Literal["CLT", "PJ", "ESTAGIO", "TEMPORARIO", "APRENDIZ", "OUTRO"] = "CLT"
    data_admissao: date
    salario_base: Optional[Decimal] = Field(default=None, ge=0)
    jornada_semanal: Optional[Decimal] = Field(default=None, ge=0, le=60)
    gestor: Optional[str] = Field(default=None, max_length=160)
    contato_emergencia_nome: str = Field(min_length=2, max_length=160)
    contato_emergencia_parentesco: str = Field(min_length=2, max_length=80)
    contato_emergencia_telefone: str = Field(min_length=10, max_length=20)
    status: Literal["ATIVO", "DESLIGADO"] = "ATIVO"
    data_desligamento: Optional[date] = None
    motivo_desligamento: Optional[str] = Field(default=None, max_length=2000)
    observacoes: Optional[str] = Field(default=None, max_length=5000)

    @field_validator(
        "matricula", "nome_completo", "nome_social", "rg", "orgao_emissor_rg",
        "logradouro", "numero", "complemento", "bairro", "cidade", "departamento",
        "cargo", "gestor", "contato_emergencia_nome", "contato_emergencia_parentesco",
        "motivo_desligamento", "observacoes",
        mode="before",
    )
    @classmethod
    def limpar_textos(cls, value):
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("matricula")
    @classmethod
    def normalizar_matricula(cls, value: Optional[str]) -> Optional[str]:
        return value.upper() if value else None

    @field_validator("cpf")
    @classmethod
    def validar_cpf(cls, value: str) -> str:
        digits = _somente_digitos(value)
        if not _cpf_valido(digits):
            raise ValueError("CPF inválido")
        return digits

    @field_validator("cep")
    @classmethod
    def validar_cep(cls, value: str) -> str:
        digits = _somente_digitos(value)
        if len(digits) != 8:
            raise ValueError("CEP deve ter 8 dígitos")
        return digits

    @field_validator("celular", "telefone", "contato_emergencia_telefone")
    @classmethod
    def validar_telefone(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        digits = _somente_digitos(value)
        if len(digits) not in {10, 11}:
            raise ValueError("Telefone deve conter DDD e 10 ou 11 dígitos")
        return digits

    @field_validator("pis_pasep")
    @classmethod
    def validar_pis(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        digits = _somente_digitos(value)
        if len(digits) != 11:
            raise ValueError("PIS/PASEP deve ter 11 dígitos")
        return digits

    @field_validator("email_pessoal", "email_corporativo")
    @classmethod
    def validar_email(cls, value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        cleaned = value.strip().lower()
        if not re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", cleaned):
            raise ValueError("E-mail inválido")
        return cleaned

    @field_validator("uf", "uf_rg", "ctps_uf")
    @classmethod
    def normalizar_uf(cls, value: Optional[str]) -> Optional[str]:
        return value.strip().upper() if value else None

    @model_validator(mode="after")
    def validar_vinculo_e_datas(self):
        today = date.today()
        age = today.year - self.data_nascimento.year - (
            (today.month, today.day) < (self.data_nascimento.month, self.data_nascimento.day)
        )
        if age < 14:
            raise ValueError("O funcionário deve ter pelo menos 14 anos")
        if self.data_admissao < self.data_nascimento:
            raise ValueError("Data de admissão não pode ser anterior ao nascimento")
        if self.status == "DESLIGADO":
            if not self.data_desligamento or not self.motivo_desligamento:
                raise ValueError("Informe data e motivo do desligamento")
            if self.data_desligamento < self.data_admissao:
                raise ValueError("Data de desligamento não pode ser anterior à admissão")
            if self.data_desligamento > today:
                raise ValueError("Data de desligamento não pode ser futura")
        else:
            self.data_desligamento = None
            self.motivo_desligamento = None
        return self


class FuncionarioCreate(FuncionarioBase):
    pass


class FuncionarioUpdate(FuncionarioBase):
    pass


class FuncionarioStatusUpdate(BaseModel):
    status: Literal["ATIVO", "DESLIGADO"]
    data_desligamento: Optional[date] = None
    motivo: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validar_desligamento(self):
        if self.status == "DESLIGADO" and not self.motivo:
            raise ValueError("Informe o motivo do desligamento")
        return self


class FuncionarioResumo(OrmModel):
    id: int
    matricula: str
    nome_completo: str
    nome_social: Optional[str] = None
    cpf_mascarado: str
    celular: str
    email_corporativo: Optional[str] = None
    departamento: str
    cargo: str
    tipo_contrato: str
    status: str
    data_admissao: date
    data_desligamento: Optional[date] = None
    usuario_id: Optional[int] = None
    usuario_login: Optional[str] = None
    usuario_ativo: Optional[bool] = None
    atualizado_em: datetime


class FuncionarioResponse(FuncionarioBase, OrmModel):
    id: int
    matricula: str
    usuario_nome: Optional[str] = None
    usuario_login: Optional[str] = None
    usuario_ativo: Optional[bool] = None
    criado_em: datetime
    atualizado_em: datetime
    criado_por_nome: str
    atualizado_por_nome: str


class UsuarioVinculavelResponse(BaseModel):
    id: int
    nome: str
    usuario_login: str
    ativo: bool
    funcionario_id: Optional[int] = None


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
    pedido_futuro_id: Optional[int] = None
    status: str = "ATIVA"
    cancelada_em: Optional[datetime] = None
    cancelada_por_nome: Optional[str] = None
    motivo_cancelamento: Optional[str] = None


class VendaUpdate(BaseModel):
    tipo_documento: Optional[Literal["RECIBO", "NOTA_FISCAL"]] = None
    numero_documento: Optional[str] = Field(default=None, min_length=1, max_length=80)
    arquivo_documento: Optional[str] = None
    valor_total: Optional[Decimal] = Field(default=None, gt=0)
    data_venda: Optional[date] = None
    observacoes: Optional[str] = None


class CancelamentoVenda(BaseModel):
    motivo: str = Field(min_length=3, max_length=500)


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
    cliente_id: Optional[int] = None
    cliente_nome: Optional[str] = Field(default=None, min_length=2, max_length=255)
    data_entrega: datetime
    prioridade: bool = False
    observacoes: Optional[str] = None
    itens: list[PedidoItemCreate] = Field(default_factory=list)
    # Campos legados mantidos para aceitar cadastros da v4.6.1 durante a transição.
    produto_nome: Optional[str] = None
    quantidade: Optional[Decimal] = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validar_itens_ou_legado(self):
        if not self.cliente_id and not self.cliente_nome:
            raise ValueError("Selecione um cliente cadastrado")
        if not self.itens and not (self.produto_nome and self.quantidade):
            raise ValueError("Inclua pelo menos um produto no pedido")
        return self


class PedidoFuturoResponse(OrmModel):
    id: int
    cliente_nome: str
    cliente_id: Optional[int] = None
    orcamento_id: Optional[int] = None
    ordem_servico_id: Optional[int] = None
    venda_id: Optional[int] = None
    produto_nome: str
    quantidade: Decimal
    data_entrega: datetime
    status: str
    fila_posicao: int = 0
    prioridade: bool = False
    tipo_documento: Optional[Literal["RECIBO", "NOTA_FISCAL"]] = None
    numero_documento: Optional[str] = None
    modalidade_entrega: Optional[Literal["ENTREGA", "RETIRADA"]] = None
    confirmado_em: Optional[datetime] = None
    confirmado_por_nome: Optional[str] = None
    cancelado_em: Optional[datetime] = None
    cancelado_por_nome: Optional[str] = None
    itens: list[PedidoItemResponse] = Field(default_factory=list)
    observacoes: Optional[str] = None
    concluido_em: Optional[datetime] = None
    concluido_por_nome: Optional[str] = None


class AlteracaoStatusPedido(BaseModel):
    status: Literal[
        "PENDENTE", "AGUARDANDO_PRODUCAO", "EM_PRODUCAO",
        "PRODUCAO_CONCLUIDA", "SEPARADO", "PRONTO", "ENTREGUE", "RETIRADO",
    ]
    observacao: Optional[str] = Field(default=None, max_length=1000)


class RegistroOperacionalPedido(BaseModel):
    texto: str = Field(min_length=3, max_length=1000)


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
    modalidade_entrega: Literal["ENTREGA", "RETIRADA"] = "ENTREGA"

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


class RecuperacaoAcessoSolicitar(BaseModel):
    usuario_login: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=255)

    @field_validator("usuario_login", "email")
    @classmethod
    def limpar_campos(cls, value: str) -> str:
        return value.strip().lower()


class RecuperacaoAcessoConfirmar(BaseModel):
    usuario_login: str = Field(min_length=2, max_length=120)
    codigo: str = Field(pattern=r"^\d{6}$")

    @field_validator("usuario_login")
    @classmethod
    def limpar_login(cls, value: str) -> str:
        return value.strip().lower()


class ConfirmacaoCritica(BaseModel):
    senha: str = Field(min_length=1, max_length=128)
    motivo: str = Field(min_length=3, max_length=500)


class MensagemSugestaoCreate(BaseModel):
    conteudo: str = Field(min_length=2, max_length=5000)


class MensagemSugestaoResponse(OrmModel):
    id: int
    autor_tipo: str
    usuario_id: Optional[int] = None
    conteudo: str
    criado_em: datetime


class HistoricoStatusSugestaoResponse(OrmModel):
    id: int
    status_anterior: Optional[str] = None
    status_novo: str
    observacao: Optional[str] = None
    usuario_nome: str
    criado_em: datetime


class SugestaoResponse(OrmModel):
    id: int
    numero: Optional[str] = None
    usuario_id: int
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    modulo: Optional[str] = None
    resumo_ia: Optional[str] = None
    status: str
    prioridade: str
    resposta_administrativa: Optional[str] = None
    criado_em: datetime
    atualizado_em: datetime
    mensagens: list[MensagemSugestaoResponse] = Field(default_factory=list)
    historico: list[HistoricoStatusSugestaoResponse] = Field(default_factory=list)


class ConfirmacaoSugestao(BaseModel):
    titulo: str = Field(min_length=3, max_length=255)
    descricao: str = Field(min_length=5, max_length=10000)
    modulo: str = Field(min_length=2, max_length=80)
    resumo_ia: str = Field(min_length=5, max_length=10000)


class AtualizacaoSugestaoAdmin(BaseModel):
    status: Literal[
        "EM_ANALISE", "AGUARDANDO_INFORMACAO", "APROVADA", "EM_ATENDIMENTO",
        "IMPLEMENTADA", "RESPONDIDA", "FINALIZADA", "RECUSADA", "ARQUIVADA",
    ]
    prioridade: Literal["BAIXA", "NORMAL", "ALTA", "URGENTE"] = "NORMAL"
    resposta: Optional[str] = Field(default=None, max_length=10000)


class NotificacaoResponse(OrmModel):
    id: int
    usuario_id: int
    tipo: str
    titulo: str
    mensagem: str
    entidade: Optional[str] = None
    entidade_id: Optional[int] = None
    lida_em: Optional[datetime] = None
    criado_em: datetime
