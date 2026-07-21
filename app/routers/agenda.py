from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import require_permission

router = APIRouter(prefix="/agenda", tags=["Agenda"])
agenda_access = require_permission("pode_acessar_agenda")


@router.post("/", response_model=schemas.CompromissoResponse, status_code=201)
def criar_compromisso(comp: schemas.CompromissoCreate, db: Session = Depends(get_db), _=Depends(agenda_access)):
    novo = models.Compromisso(**comp.model_dump())
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return novo


@router.get("/", response_model=List[schemas.CompromissoResponse])
def listar_compromissos(db: Session = Depends(get_db), _=Depends(agenda_access)):
    return db.query(models.Compromisso).order_by(models.Compromisso.data_hora.asc()).all()


@router.put("/{comp_id}", response_model=schemas.CompromissoResponse)
def atualizar_compromisso(comp_id: int, dados: schemas.CompromissoCreate, db: Session = Depends(get_db), _=Depends(agenda_access)):
    comp = db.query(models.Compromisso).filter(models.Compromisso.id == comp_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Compromisso não encontrado")
    for key, value in dados.model_dump().items():
        setattr(comp, key, value)
    db.commit()
    db.refresh(comp)
    return comp


@router.delete("/{comp_id}")
def excluir_compromisso(comp_id: int, db: Session = Depends(get_db), _=Depends(agenda_access)):
    comp = db.query(models.Compromisso).filter(models.Compromisso.id == comp_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Compromisso não encontrado")
    db.delete(comp)
    db.commit()
    return {"status": "success"}
