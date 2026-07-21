from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.database import get_db
from app.dependencies import require_permission

router = APIRouter(prefix="/vendas", tags=["Vendas e documentos"])


def _query(db: Session):
    return db.query(models.Venda).options(joinedload(models.Venda.cliente))


def _next_number(db: Session) -> str:
    return f"VEN-{date.today().year}-{db.query(models.Venda).count() + 1:05d}"


@router.post("/", response_model=schemas.VendaResponse, status_code=201)
def criar(
    dados: schemas.VendaCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("pode_alterar_custos")),
):
    if not db.get(models.Cliente, dados.cliente_id):
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    if dados.orcamento_id and not db.get(models.Orcamento, dados.orcamento_id):
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    if dados.ordem_servico_id and not db.get(models.OrdemServico, dados.ordem_servico_id):
        raise HTTPException(status_code=404, detail="OS não encontrada")
    venda = models.Venda(numero=_next_number(db), **dados.model_dump())
    db.add(venda)
    db.commit()
    return _query(db).filter(models.Venda.id == venda.id).first()


@router.get("/", response_model=list[schemas.VendaResponse])
def listar(
    db: Session = Depends(get_db),
    _=Depends(require_permission("pode_alterar_custos")),
):
    return _query(db).order_by(models.Venda.data_venda.desc()).all()
