from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import current_user

router = APIRouter(prefix="/pedidos", tags=["Pedidos futuros"])


@router.post("/", response_model=schemas.PedidoFuturoResponse, status_code=201)
def criar_pedido(pedido: schemas.PedidoFuturoCreate, db: Session = Depends(get_db), _=Depends(current_user)):
    novo = models.PedidoFuturo(**pedido.model_dump())
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


@router.get("/", response_model=List[schemas.PedidoFuturoResponse])
def listar_pedidos(db: Session = Depends(get_db), _=Depends(current_user)):
    return db.query(models.PedidoFuturo).order_by(models.PedidoFuturo.data_entrega.asc()).all()


@router.put("/{pedido_id}", response_model=schemas.PedidoFuturoResponse)
def atualizar_pedido(pedido_id: int, dados: schemas.PedidoFuturoCreate, db: Session = Depends(get_db), _=Depends(current_user)):
    pedido = db.query(models.PedidoFuturo).filter(models.PedidoFuturo.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    for key, value in dados.model_dump().items():
        setattr(pedido, key, value)
    db.commit()
    db.refresh(pedido)
    return pedido


@router.put("/{pedido_id}/status")
def atualizar_status_pedido(pedido_id: int, status_novo: str, db: Session = Depends(get_db), _=Depends(current_user)):
    pedido = db.query(models.PedidoFuturo).filter(models.PedidoFuturo.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    pedido.status = status_novo
    db.commit()
    return {"status": "success"}


@router.delete("/{pedido_id}")
def excluir_pedido(pedido_id: int, db: Session = Depends(get_db), _=Depends(current_user)):
    pedido = db.query(models.PedidoFuturo).filter(models.PedidoFuturo.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    db.delete(pedido)
    db.commit()
    return {"status": "success"}
