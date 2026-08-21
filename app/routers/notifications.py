from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import current_user

router = APIRouter(prefix="/notificacoes", tags=["Notificações"])


@router.get("/", response_model=list[schemas.NotificacaoResponse])
def listar(apenas_nao_lidas: bool = False, db: Session = Depends(get_db), user=Depends(current_user)):
    query = db.query(models.Notificacao).filter(models.Notificacao.usuario_id == user.id)
    if apenas_nao_lidas:
        query = query.filter(models.Notificacao.lida_em.is_(None))
    return query.order_by(models.Notificacao.criado_em.desc()).limit(500).all()


@router.get("/nao-lidas")
def contar(db: Session = Depends(get_db), user=Depends(current_user)):
    return {"quantidade": db.query(models.Notificacao).filter(
        models.Notificacao.usuario_id == user.id, models.Notificacao.lida_em.is_(None)
    ).count()}


@router.post("/{notification_id}/ler", response_model=schemas.NotificacaoResponse)
def ler(notification_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    item = db.query(models.Notificacao).filter(
        models.Notificacao.id == notification_id,
        models.Notificacao.usuario_id == user.id,
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Notificação não encontrada")
    item.lida_em = item.lida_em or datetime.now()
    db.commit()
    db.refresh(item)
    return item


@router.post("/ler-todas")
def ler_todas(db: Session = Depends(get_db), user=Depends(current_user)):
    db.query(models.Notificacao).filter(
        models.Notificacao.usuario_id == user.id, models.Notificacao.lida_em.is_(None)
    ).update({"lida_em": datetime.now()}, synchronize_session=False)
    db.commit()
    return {"status": "success"}
