from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import current_user, require_admin, require_permission

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.post("/", response_model=schemas.ClienteResponse, status_code=201)
def criar_cliente(cliente: schemas.ClienteCreate, db: Session = Depends(get_db), _=Depends(require_permission("pode_gerenciar_clientes"))):
    if cliente.documento and db.query(models.Cliente).filter(models.Cliente.documento == cliente.documento).first():
        raise HTTPException(status_code=400, detail="Documento já cadastrado")
    novo = models.Cliente(**cliente.model_dump())
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


@router.get("/", response_model=List[schemas.ClienteResponse])
def listar_clientes(db: Session = Depends(get_db), _=Depends(current_user)):
    return db.query(models.Cliente).all()


@router.put("/{cliente_id}", response_model=schemas.ClienteResponse)
def atualizar_cliente(cliente_id: int, dados: schemas.ClienteCreate, db: Session = Depends(get_db), _=Depends(require_permission("pode_gerenciar_clientes"))):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    for key, value in dados.model_dump().items():
        setattr(cliente, key, value)
    db.commit()
    db.refresh(cliente)
    return cliente


@router.delete("/{cliente_id}")
def excluir_cliente(cliente_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    db.delete(cliente)
    db.commit()
    return {"status": "success"}
