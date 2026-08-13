from datetime import date, datetime, time, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import current_user

router = APIRouter(prefix="/historico", tags=["Histórico de estoque"])


@router.get("/sistema", response_model=List[schemas.AuditoriaSistemaResponse])
def listar_auditoria_sistema(
    data_inicial: date | None = None, data_final: date | None = None,
    usuario_id: int | None = None, modulo: str | None = None,
    acao: str | None = None, limite: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db), _=Depends(current_user),
):
    query = db.query(models.AuditoriaSistema)
    if data_inicial:
        query = query.filter(models.AuditoriaSistema.criado_em >= datetime.combine(data_inicial, time.min))
    if data_final:
        query = query.filter(models.AuditoriaSistema.criado_em < datetime.combine(data_final + timedelta(days=1), time.min))
    if usuario_id:
        query = query.filter(models.AuditoriaSistema.usuario_id == usuario_id)
    if modulo:
        query = query.filter(models.AuditoriaSistema.categoria == modulo.upper())
    if acao:
        query = query.filter(models.AuditoriaSistema.acao == acao.upper())
    return query.order_by(models.AuditoriaSistema.criado_em.desc()).limit(limite).all()


@router.get("/", response_model=List[schemas.HistoricoResponse])
def listar_historico(
    busca: str | None = Query(default=None),
    data_inicial: date | None = Query(default=None),
    data_final: date | None = Query(default=None),
    produto_id: int | None = Query(default=None),
    operacao: str | None = Query(default=None),
    responsavel: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _=Depends(current_user),
):
    query = db.query(models.HistoricoEstoque)
    if busca:
        termo = f"%{busca.strip()}%"
        query = query.filter(or_(
            models.HistoricoEstoque.produto_nome.ilike(termo),
            models.HistoricoEstoque.tipo_movimentacao.ilike(termo),
            models.HistoricoEstoque.motivo.ilike(termo),
            models.HistoricoEstoque.referencia.ilike(termo),
            models.HistoricoEstoque.usuario_responsavel.ilike(termo),
        ))
    if data_inicial:
        query = query.filter(models.HistoricoEstoque.data_hora >= datetime.combine(data_inicial, time.min))
    if data_final:
        query = query.filter(models.HistoricoEstoque.data_hora < datetime.combine(data_final + timedelta(days=1), time.min))
    if produto_id:
        query = query.filter(models.HistoricoEstoque.produto_id == produto_id)
    if operacao:
        query = query.filter(models.HistoricoEstoque.tipo_movimentacao == operacao)
    if responsavel:
        query = query.filter(models.HistoricoEstoque.usuario_responsavel == responsavel)
    return query.order_by(models.HistoricoEstoque.data_hora.desc()).limit(1000).all()


@router.delete("/{hist_id}", include_in_schema=False)
def bloquear_exclusao_registro(hist_id: int, _=Depends(current_user)):
    raise HTTPException(status_code=405, detail="A auditoria é permanente e não pode ser excluída")


@router.delete("/", include_in_schema=False)
def bloquear_limpeza_historico(_=Depends(current_user)):
    raise HTTPException(status_code=405, detail="A auditoria é permanente e não pode ser apagada")
