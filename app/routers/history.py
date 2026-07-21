from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import current_user, require_admin

router = APIRouter(prefix="/historico", tags=["Histórico de estoque"])


@router.get("/", response_model=List[schemas.HistoricoResponse])
def listar_historico(db: Session = Depends(get_db), _=Depends(current_user)):
    return db.query(models.HistoricoEstoque).order_by(models.HistoricoEstoque.data_hora.desc()).all()


@router.delete("/{hist_id}")
def excluir_registro(hist_id: int, db: Session = Depends(get_db), _=Depends(require_admin)):
    registro = db.query(models.HistoricoEstoque).filter(models.HistoricoEstoque.id == hist_id).first()
    if not registro:
        raise HTTPException(status_code=404, detail="Registro não encontrado")
    db.delete(registro)
    db.commit()
    return {"status": "success"}


@router.delete("/")
def limpar_historico(db: Session = Depends(get_db), _=Depends(require_admin)):
    db.query(models.HistoricoEstoque).delete()
    db.commit()
    return {"status": "success"}
