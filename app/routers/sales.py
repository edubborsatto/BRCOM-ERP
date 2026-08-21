from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.database import get_db
from app.dependencies import confirm_critical_action, require_admin, require_permission
from app.services import audit

router = APIRouter(prefix="/vendas", tags=["Vendas e documentos"])


def _query(db: Session):
    return db.query(models.Venda).options(joinedload(models.Venda.cliente))


def _next_number(db: Session) -> str:
    return f"VEN-{date.today().year}-{db.query(models.Venda).count() + 1:05d}"


@router.post("/", response_model=schemas.VendaResponse, status_code=201)
def criar(
    dados: schemas.VendaCreate,
    db: Session = Depends(get_db),
    usuario=Depends(require_permission("pode_registrar_vendas")),
):
    dados.numero_documento = (dados.numero_documento or "").strip()
    if not dados.numero_documento:
        raise HTTPException(status_code=422, detail="Informe o número da nota fiscal ou do recibo")
    duplicada = db.query(models.Venda).filter(
        models.Venda.status == "ATIVA",
        models.Venda.tipo_documento == dados.tipo_documento,
        models.Venda.numero_documento == dados.numero_documento,
    ).first()
    if duplicada:
        raise HTTPException(status_code=409, detail="Número de documento já usado neste tipo")
    if not db.get(models.Cliente, dados.cliente_id):
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    if dados.orcamento_id and not db.get(models.Orcamento, dados.orcamento_id):
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    if dados.ordem_servico_id and not db.get(models.OrdemServico, dados.ordem_servico_id):
        raise HTTPException(status_code=404, detail="OS não encontrada")
    venda = models.Venda(numero=_next_number(db), **dados.model_dump())
    db.add(venda)
    db.flush()
    audit(db, usuario, "VENDAS", "CRIAR", "vendas", venda.id, after=dados.model_dump())
    db.commit()
    return _query(db).filter(models.Venda.id == venda.id).first()


@router.get("/", response_model=list[schemas.VendaResponse])
def listar(
    db: Session = Depends(get_db),
    _=Depends(require_permission("pode_registrar_vendas")),
):
    return _query(db).order_by(models.Venda.data_venda.desc()).all()


@router.patch("/{venda_id}", response_model=schemas.VendaResponse)
def editar(venda_id: int, dados: schemas.VendaUpdate, db: Session = Depends(get_db),
           usuario=Depends(require_admin)):
    venda = _query(db).filter(models.Venda.id == venda_id).first()
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada")
    if venda.status == "CANCELADA":
        raise HTTPException(status_code=409, detail="Venda cancelada não pode ser editada")
    before = {c.name: getattr(venda, c.name) for c in models.Venda.__table__.columns if c.name not in {"arquivo_documento"}}
    changes = dados.model_dump(exclude_unset=True)
    tipo = changes.get("tipo_documento", venda.tipo_documento)
    numero = changes.get("numero_documento", venda.numero_documento)
    if db.query(models.Venda).filter(models.Venda.id != venda_id, models.Venda.status == "ATIVA", models.Venda.tipo_documento == tipo, models.Venda.numero_documento == numero).first():
        raise HTTPException(status_code=409, detail="Número de documento já usado neste tipo")
    for key, value in changes.items():
        setattr(venda, key, value)
    audit(db, usuario, "VENDAS", "EDITAR", "vendas", venda.id, before=before, after=changes)
    db.commit()
    return venda


@router.post("/{venda_id}/cancelar", response_model=schemas.VendaResponse)
def cancelar(venda_id: int, dados: schemas.CancelamentoVenda, db: Session = Depends(get_db),
             usuario=Depends(require_admin)):
    venda = _query(db).filter(models.Venda.id == venda_id).first()
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada")
    if venda.status == "CANCELADA":
        raise HTTPException(status_code=409, detail="Venda já cancelada")
    venda.status = "CANCELADA"
    venda.cancelada_em = datetime.now()
    venda.cancelada_por_id = usuario.id
    venda.cancelada_por_nome = usuario.nome
    venda.motivo_cancelamento = dados.motivo
    if venda.pedido_futuro_id:
        pedido = db.get(models.PedidoFuturo, venda.pedido_futuro_id)
        if pedido:
            pedido.confirmado_em = None
            pedido.confirmado_por_id = None
            pedido.confirmado_por_nome = None
            pedido.status = "PRONTO"
            pedido.venda_id = None
    audit(db, usuario, "VENDAS", "CANCELAR", "vendas", venda.id, before={"status": "ATIVA"}, after={"status": "CANCELADA", "motivo": dados.motivo})
    db.commit()
    return venda


@router.post("/{venda_id}/excluir-definitivamente")
def excluir_definitivamente(
    venda_id: int,
    dados: schemas.ConfirmacaoCritica,
    db: Session = Depends(get_db),
    usuario=Depends(require_admin),
):
    confirm_critical_action(usuario, dados.senha)
    venda = db.get(models.Venda, venda_id)
    if not venda:
        raise HTTPException(status_code=404, detail="Venda não encontrada")
    pedido = db.query(models.PedidoFuturo).filter(
        (models.PedidoFuturo.venda_id == venda.id)
        | (models.PedidoFuturo.id == venda.pedido_futuro_id)
    ).first()
    if pedido:
        pedido.venda_id = None
        pedido.confirmado_em = None
        pedido.confirmado_por_id = None
        pedido.confirmado_por_nome = None
        if not pedido.cancelado_em:
            pedido.status = "PRONTO"
    audit(db, usuario, "VENDAS", "EXCLUIR_DEFINITIVAMENTE", "vendas", venda.id,
          before={"numero": venda.numero, "documento": venda.numero_documento,
                  "valor_total": venda.valor_total, "status": venda.status},
          after={"motivo": dados.motivo})
    db.delete(venda)
    db.commit()
    return {"status": "success"}
