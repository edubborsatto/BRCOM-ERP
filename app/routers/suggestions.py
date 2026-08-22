from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.ai_suggestions import SuggestionAIUnavailable, continue_interview
from app.database import get_db
from app.dependencies import current_user
from app.services import audit

router = APIRouter(prefix="/sugestoes", tags=["Sugestões de melhoria"])


def _query(db: Session):
    return db.query(models.Sugestao).options(
        joinedload(models.Sugestao.mensagens), joinedload(models.Sugestao.historico)
    )


def _get(db: Session, suggestion_id: int):
    item = _query(db).filter(models.Sugestao.id == suggestion_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Sugestão não encontrada")
    return item


def _can_manage(user):
    return user.tipo_usuario in {"DONO", "DESENVOLVEDOR"} or user.pode_administrar_sugestoes


def _status_label(value: str) -> str:
    return {
        "EM_ANALISE": "Em análise", "AGUARDANDO_INFORMACAO": "Aguardando informação",
        "EM_ATENDIMENTO": "Em atendimento", "IMPLEMENTADA": "Implementada",
        "RESPONDIDA": "Respondida", "FINALIZADA": "Finalizada", "APROVADA": "Aprovada",
        "RECUSADA": "Recusada", "ARQUIVADA": "Arquivada",
    }.get(value, value.replace("_", " ").title())


def _notify_admins(db, suggestion, title, message):
    admins = db.query(models.Usuario).filter(
        models.Usuario.ativo.is_(True),
        models.Usuario.pode_administrar_sugestoes.is_(True),
    ).all()
    for admin in admins:
        db.add(models.Notificacao(
            usuario_id=admin.id, tipo="SUGESTAO", titulo=title, mensagem=message,
            entidade="sugestoes", entidade_id=suggestion.id,
        ))


def _notify_ai_failure(db, suggestion, exc):
    admins = db.query(models.Usuario).filter(
        models.Usuario.ativo.is_(True),
        models.Usuario.pode_administrar_sugestoes.is_(True),
    ).all()
    for admin in admins:
        already_open = db.query(models.Notificacao).filter(
            models.Notificacao.usuario_id == admin.id,
            models.Notificacao.tipo == "IA_ERRO",
            models.Notificacao.entidade == "sugestoes",
            models.Notificacao.entidade_id == suggestion.id,
            models.Notificacao.lida_em.is_(None),
        ).first()
        if not already_open:
            db.add(models.Notificacao(
                usuario_id=admin.id,
                tipo="IA_ERRO",
                titulo="Falha no assistente de sugestões",
                mensagem=exc.diagnostic,
                entidade="sugestoes",
                entidade_id=suggestion.id,
            ))


@router.post("/", response_model=schemas.SugestaoResponse, status_code=201)
def iniciar(db: Session = Depends(get_db), user=Depends(current_user)):
    if not user.pode_enviar_sugestoes:
        raise HTTPException(status_code=403, detail="Sem permissão para enviar sugestões")
    item = models.Sugestao(usuario_id=user.id)
    db.add(item)
    db.flush()
    db.add(models.HistoricoStatusSugestao(
        sugestao_id=item.id, status_novo="COLETANDO_IDEIA",
        usuario_id=user.id, usuario_nome=user.nome,
    ))
    audit(db, user, "SUGESTOES", "INICIAR", "sugestoes", item.id)
    db.commit()
    return _get(db, item.id)


@router.post("/{suggestion_id}/mensagens")
def conversar(suggestion_id: int, data: schemas.MensagemSugestaoCreate,
              db: Session = Depends(get_db), user=Depends(current_user)):
    item = _get(db, suggestion_id)
    if item.usuario_id != user.id or item.status != "COLETANDO_IDEIA":
        raise HTTPException(status_code=403, detail="Esta conversa não pode ser alterada")
    db.add(models.MensagemSugestao(
        sugestao_id=item.id, autor_tipo="USUARIO", usuario_id=user.id,
        conteudo=data.conteudo,
    ))
    db.flush()
    conversation = [
        {"role": "user" if m.autor_tipo == "USUARIO" else "assistant", "content": m.conteudo}
        for m in item.mensagens
    ]
    try:
        result = continue_interview(conversation)
    except SuggestionAIUnavailable as exc:
        _notify_ai_failure(db, item, exc)
        audit(
            db, user, "SUGESTOES", "IA_INDISPONIVEL", "sugestoes", item.id,
            after={"codigo": exc.code, "request_id": exc.request_id},
        )
        db.commit()
        response = {
            "ai_available": False,
            "message": str(exc),
            "ready": False,
            "error_code": exc.code,
        }
        if _can_manage(user):
            response["diagnostic"] = exc.diagnostic
        return response
    db.add(models.MensagemSugestao(
        sugestao_id=item.id, autor_tipo="IA", conteudo=result["assistant_message"],
    ))
    if result.get("ready"):
        item.titulo = result.get("title") or item.titulo
        item.modulo = result.get("module") or item.modulo
        item.resumo_ia = result.get("summary") or item.resumo_ia
    db.commit()
    return {"ai_available": True, **result}


@router.post("/{suggestion_id}/confirmar", response_model=schemas.SugestaoResponse)
def confirmar(suggestion_id: int, data: schemas.ConfirmacaoSugestao,
              db: Session = Depends(get_db), user=Depends(current_user)):
    item = _get(db, suggestion_id)
    if item.usuario_id != user.id or item.status != "COLETANDO_IDEIA":
        raise HTTPException(status_code=403, detail="Sugestão não pode ser confirmada")
    item.numero = f"SUG-{date.today().year}-{item.id:05d}"
    item.titulo, item.descricao = data.titulo, data.descricao
    item.modulo, item.resumo_ia = data.modulo, data.resumo_ia
    item.status = "ENVIADA"
    db.add(models.HistoricoStatusSugestao(
        sugestao_id=item.id, status_anterior="COLETANDO_IDEIA", status_novo="ENVIADA",
        usuario_id=user.id, usuario_nome=user.nome,
    ))
    _notify_admins(db, item, f"Nova sugestão {item.numero}", item.titulo)
    audit(db, user, "SUGESTOES", "ENVIAR", "sugestoes", item.id, after={"numero": item.numero})
    db.commit()
    return _get(db, item.id)


@router.get("/", response_model=list[schemas.SugestaoResponse])
def listar(status: str | None = None, usuario_id: int | None = None,
           modulo: str | None = None, prioridade: str | None = None,
           data_inicial: date | None = None, data_final: date | None = None,
           db: Session = Depends(get_db), user=Depends(current_user)):
    query = _query(db)
    if not _can_manage(user):
        query = query.filter(models.Sugestao.usuario_id == user.id)
    elif usuario_id:
        query = query.filter(models.Sugestao.usuario_id == usuario_id)
    if status:
        query = query.filter(models.Sugestao.status == status)
    if modulo:
        query = query.filter(models.Sugestao.modulo == modulo)
    if prioridade:
        query = query.filter(models.Sugestao.prioridade == prioridade)
    if data_inicial:
        query = query.filter(models.Sugestao.criado_em >= datetime.combine(data_inicial, time.min))
    if data_final:
        query = query.filter(models.Sugestao.criado_em < datetime.combine(data_final + timedelta(days=1), time.min))
    return query.order_by(models.Sugestao.atualizado_em.desc()).all()


@router.get("/{suggestion_id}", response_model=schemas.SugestaoResponse)
def obter(suggestion_id: int, db: Session = Depends(get_db), user=Depends(current_user)):
    item = _get(db, suggestion_id)
    if item.usuario_id != user.id and not _can_manage(user):
        raise HTTPException(status_code=403, detail="Sem acesso a esta sugestão")
    return item


@router.patch("/{suggestion_id}", response_model=schemas.SugestaoResponse)
def administrar(suggestion_id: int, data: schemas.AtualizacaoSugestaoAdmin,
                db: Session = Depends(get_db), user=Depends(current_user)):
    if not _can_manage(user):
        raise HTTPException(status_code=403, detail="Sem permissão para administrar sugestões")
    item = _get(db, suggestion_id)
    old = item.status
    item.status, item.prioridade = data.status, data.prioridade
    if data.resposta:
        item.resposta_administrativa = data.resposta
        db.add(models.MensagemSugestao(
            sugestao_id=item.id, autor_tipo="ADMIN", usuario_id=user.id,
            conteudo=data.resposta,
        ))
    db.add(models.HistoricoStatusSugestao(
        sugestao_id=item.id, status_anterior=old, status_novo=item.status,
        observacao=data.resposta, usuario_id=user.id, usuario_nome=user.nome,
    ))
    db.add(models.Notificacao(
        usuario_id=item.usuario_id, tipo="SUGESTAO",
        titulo=f"Atualização da sugestão {item.numero}",
        mensagem=f"Status: {_status_label(item.status)}",
        entidade="sugestoes", entidade_id=item.id,
    ))
    audit(db, user, "SUGESTOES", "ALTERAR_STATUS", "sugestoes", item.id,
          before={"status": old}, after={"status": item.status, "prioridade": item.prioridade})
    db.commit()
    return _get(db, item.id)
