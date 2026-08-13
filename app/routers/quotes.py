from datetime import date, datetime, time
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.database import get_db
from app.dependencies import current_user, require_permission
from app.inventory import decimal, formula_cost, money
from app.services import audit

router = APIRouter(prefix="/orcamentos", tags=["Orçamentos"])


def _query(db: Session):
    return db.query(models.Orcamento).options(
        joinedload(models.Orcamento.cliente),
        joinedload(models.Orcamento.itens).joinedload(models.OrcamentoItem.produto),
        joinedload(models.Orcamento.ordem_servico),
    )


def _serialize(orcamento: models.Orcamento, show_cost: bool = True) -> dict:
    dados = schemas.OrcamentoResponse.model_validate(
        orcamento, from_attributes=True
    ).model_dump(exclude={"ordem_servico_id"})
    dados["ordem_servico_id"] = orcamento.ordem_servico.id if orcamento.ordem_servico else None
    if not show_cost:
        for item in dados["itens"]:
            item["custo_unitario"] = Decimal("0")
            item["produto"]["preco_custo"] = Decimal("0")
    return dados


def _next_number(db: Session, model, prefix: str) -> str:
    year = date.today().year
    count = db.query(model).count() + 1
    return f"{prefix}-{year}-{count:05d}"


@router.post("/", response_model=schemas.OrcamentoResponse, status_code=201)
def criar(
    dados: schemas.OrcamentoCreate,
    db: Session = Depends(get_db),
    usuario=Depends(require_permission("pode_criar_orcamentos")),
):
    if not db.get(models.Cliente, dados.cliente_id):
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    orcamento = models.Orcamento(
        numero=_next_number(db, models.Orcamento, "ORC"),
        cliente_id=dados.cliente_id,
        validade=dados.validade,
        observacoes=dados.observacoes,
        desconto=dados.desconto,
    )
    subtotal = Decimal("0")
    for item in dados.itens:
        produto = db.get(models.Produto, item.produto_id)
        if not produto or produto.tipo_item != "PRODUTO_ACABADO":
            raise HTTPException(status_code=400, detail="Item deve ser produto acabado")
        custo = decimal(produto.preco_custo)
        sugerido = decimal(produto.preco_venda)
        if produto.formula:
            custos = formula_cost(produto.formula)
            custo, sugerido = custos["custo_total"], custos["preco_sugerido"]
        preco = item.preco_unitario if item.preco_unitario is not None else sugerido
        total = money(decimal(preco) * item.quantidade)
        subtotal += total
        orcamento.itens.append(models.OrcamentoItem(
            produto_id=produto.id, descricao=item.descricao,
            quantidade=item.quantidade, custo_unitario=custo,
            preco_unitario=preco, total=total,
        ))
    if dados.desconto > subtotal:
        raise HTTPException(status_code=400, detail="Desconto maior que o subtotal")
    orcamento.subtotal = money(subtotal)
    orcamento.total = money(subtotal - dados.desconto)
    db.add(orcamento)
    db.flush()
    audit(db, usuario, "ORCAMENTOS", "CRIAR", "orcamentos", orcamento.id, after={"cliente_id": orcamento.cliente_id, "total": orcamento.total})
    db.commit()
    return _serialize(_query(db).filter(models.Orcamento.id == orcamento.id).first())


@router.get("/", response_model=list[schemas.OrcamentoResponse])
def listar(
    db: Session = Depends(get_db), usuario: models.Usuario = Depends(current_user)
):
    return [
        _serialize(o, usuario.pode_alterar_custos)
        for o in _query(db).order_by(models.Orcamento.id.desc()).all()
    ]


@router.post("/{orcamento_id}/aprovar", response_model=schemas.OrcamentoResponse)
def aprovar(
    orcamento_id: int,
    dados: schemas.AprovacaoOrcamento,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_permission("pode_aprovar_orcamentos")),
):
    orcamento = _query(db).filter(models.Orcamento.id == orcamento_id).first()
    if not orcamento:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    if orcamento.status != "RASCUNHO":
        raise HTTPException(status_code=409, detail="Orçamento já processado")
    sem_formula = [i.produto.nome for i in orcamento.itens if not i.produto.formula]
    if sem_formula:
        raise HTTPException(status_code=409, detail="Produtos sem fórmula: " + ", ".join(sem_formula))
    orcamento.status = "APROVADO"
    orcamento.aprovado_em = datetime.now()
    orcamento.aprovado_por_id = usuario.id
    atividade = dados.atividade or "Produzir: " + "; ".join(
        f"{i.quantidade} x {i.produto.nome}" for i in orcamento.itens
    )
    os = models.OrdemServico(
        numero=_next_number(db, models.OrdemServico, "OS"),
        orcamento_id=orcamento.id,
        cliente_id=orcamento.cliente_id,
        atividade=atividade,
        data_emissao=date.today(),
        data_limite=dados.data_limite,
    )
    db.add(os)
    db.flush()
    pedido = models.PedidoFuturo(
        cliente_id=orcamento.cliente_id, cliente_nome=orcamento.cliente.nome,
        orcamento_id=orcamento.id, ordem_servico_id=os.id,
        produto_nome=orcamento.itens[0].produto.nome if len(orcamento.itens) == 1 else f"{len(orcamento.itens)} produtos",
        quantidade=sum((i.quantidade for i in orcamento.itens), Decimal("0")),
        data_entrega=datetime.combine(dados.data_limite or date.today(), time(hour=17)),
        status="AGUARDANDO_PRODUCAO",
        fila_posicao=int(db.query(func.max(models.PedidoFuturo.fila_posicao)).scalar() or 0) + 1,
        observacoes=f"Gerado automaticamente pelo orçamento {orcamento.numero}",
    )
    db.add(pedido)
    db.flush()
    for item in orcamento.itens:
        db.add(models.PedidoFuturoItem(
            pedido_id=pedido.id, produto_id=item.produto_id,
            produto_nome=item.produto.nome, quantidade_total=item.quantidade,
            quantidade_estoque=Decimal("0"), quantidade_fabricar=item.quantidade,
        ))
    audit(db, usuario, "ORDENS_SERVICO", "CRIAR_DE_ORCAMENTO", "ordens_servico", os.id, after={"orcamento_id": orcamento.id, "pedido_id": pedido.id})
    audit(db, usuario, "PEDIDOS", "CRIAR_DE_ORCAMENTO", "pedidos_futuros", pedido.id, after={"orcamento_id": orcamento.id, "ordem_servico_id": os.id})
    audit(db, usuario, "ORCAMENTOS", "APROVAR", "orcamentos", orcamento.id, before={"status": "RASCUNHO"}, after={"status": "APROVADO", "ordem_servico_id": os.id, "pedido_id": pedido.id})
    db.commit()
    return _serialize(_query(db).filter(models.Orcamento.id == orcamento_id).first())


@router.post("/{orcamento_id}/rejeitar", response_model=schemas.OrcamentoResponse)
def rejeitar(
    orcamento_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(require_permission("pode_aprovar_orcamentos")),
):
    orcamento = _query(db).filter(models.Orcamento.id == orcamento_id).first()
    if not orcamento:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    if orcamento.status != "RASCUNHO":
        raise HTTPException(status_code=409, detail="Orçamento já processado")
    orcamento.status = "REJEITADO"
    audit(db, usuario, "ORCAMENTOS", "REJEITAR", "orcamentos", orcamento.id, before={"status": "RASCUNHO"}, after={"status": "REJEITADO"})
    db.commit()
    return _serialize(orcamento)
