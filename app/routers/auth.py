import json
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.account_recovery import RecoveryDeliveryUnavailable, send_recovery_code
from app.database import get_db
from app.dependencies import current_user
from app.security import (
    COOKIE_NAME,
    cookie_is_secure,
    create_access_token,
    recovery_code_digest,
    verify_password,
    verify_recovery_code,
)
from app.services import public_user

router = APIRouter(prefix="/api", tags=["Autenticação"])


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _integer_setting(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        return max(minimum, min(int(os.getenv(name, str(default))), maximum))
    except ValueError:
        return default


def _max_attempts() -> int:
    return _integer_setting("LOGIN_MAX_ATTEMPTS", 5, 3, 20)


def _lock_minutes() -> int:
    return _integer_setting("LOGIN_LOCK_MINUTES", 30, 1, 1440)


def _recovery_minutes() -> int:
    return _integer_setting("RECOVERY_CODE_MINUTES", 10, 5, 60)


def _request_context(request: Request) -> dict[str, str]:
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",", 1)[0].strip() if forwarded else ""
    if not ip and request.client:
        ip = request.client.host
    return {
        "ip": (ip or "não identificado")[:80],
        "navegador": request.headers.get("user-agent", "não identificado")[:300],
    }


def _audit_access(db: Session, user: models.Usuario, action: str, request: Request, extra=None) -> None:
    details = {**_request_context(request), **(extra or {})}
    verified_actions = {"LOGIN_SUCESSO", "CONTA_DESBLOQUEADA_POR_CODIGO"}
    db.add(models.AuditoriaSistema(
        categoria="SEGURANCA",
        acao=action,
        entidade="usuarios",
        entidade_id=user.id,
        dados_novos=json.dumps(details, ensure_ascii=False, default=str),
        usuario_id=user.id,
        usuario_nome=(
            user.nome if action in verified_actions
            else f"Sistema de segurança — conta {user.usuario_login}"
        ),
    ))


def _notify_security_admins(db: Session, user: models.Usuario, title: str, message: str) -> None:
    admins = db.query(models.Usuario).filter(
        models.Usuario.ativo.is_(True),
        or_(
            models.Usuario.tipo_usuario.in_(("DONO", "DESENVOLVEDOR")),
            models.Usuario.pode_gerenciar_usuarios.is_(True),
        ),
    ).all()
    for admin in admins:
        db.add(models.Notificacao(
            usuario_id=admin.id,
            tipo="SEGURANCA",
            titulo=title,
            mensagem=message,
            entidade="usuarios",
            entidade_id=user.id,
        ))


def _locked_detail(user: models.Usuario, now: datetime) -> dict:
    remaining = max(1, int(((user.bloqueado_ate or now) - now).total_seconds()))
    recovery_available = bool(user.email)
    return {
        "code": "ACCOUNT_LOCKED",
        "message": (
            "Acesso temporariamente bloqueado por segurança. Solicite um código no e-mail cadastrado."
            if recovery_available else
            "Acesso temporariamente bloqueado por segurança. Procure um administrador para desbloquear sua conta."
        ),
        "remaining_seconds": remaining,
        "recovery_available": recovery_available,
    }


@router.post("/login", response_model=schemas.LoginResponse)
def login(
    dados: schemas.LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    now = _now()
    usuario = (
        db.query(models.Usuario)
        .filter(models.Usuario.usuario_login == dados.usuario_login.strip().lower())
        .with_for_update()
        .first()
    )
    if not usuario or not usuario.ativo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Usuário ou senha incorretos"},
        )

    if usuario.bloqueado_ate and usuario.bloqueado_ate > now:
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=_locked_detail(usuario, now))
    if usuario.bloqueado_ate:
        usuario.bloqueado_ate = None
        usuario.tentativas_login = 0

    if not verify_password(dados.senha, usuario.senha_hash):
        usuario.tentativas_login = int(usuario.tentativas_login or 0) + 1
        usuario.ultima_falha_login_em = now
        remaining = max(0, _max_attempts() - usuario.tentativas_login)
        _audit_access(
            db, usuario, "LOGIN_FALHA", request,
            {"tentativa": usuario.tentativas_login, "restantes": remaining},
        )
        if remaining == 0:
            usuario.bloqueado_ate = now + timedelta(minutes=_lock_minutes())
            _notify_security_admins(
                db,
                usuario,
                "Conta bloqueada após tentativas de acesso",
                f"A conta de {usuario.nome} ({usuario.usuario_login}) foi bloqueada após {_max_attempts()} senhas incorretas. IP informado: {_request_context(request)['ip']}.",
            )
            _audit_access(db, usuario, "LOGIN_BLOQUEADO", request, {"bloqueado_ate": usuario.bloqueado_ate})
            db.commit()
            raise HTTPException(status_code=status.HTTP_423_LOCKED, detail=_locked_detail(usuario, now))
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "code": "INVALID_CREDENTIALS",
                "message": "Usuário ou senha incorretos",
                "remaining_attempts": remaining,
            },
        )

    usuario.tentativas_login = 0
    usuario.bloqueado_ate = None
    usuario.ultima_falha_login_em = None
    usuario.codigo_recuperacao_hash = None
    usuario.codigo_recuperacao_expira_em = None
    usuario.codigo_recuperacao_tentativas = 0
    usuario.ultimo_login_em = now
    _audit_access(db, usuario, "LOGIN_SUCESSO", request)
    db.commit()
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_access_token(usuario.id),
        httponly=True,
        secure=cookie_is_secure(),
        samesite="lax",
        max_age=_integer_setting("SESSION_HOURS", 8, 1, 168) * 60 * 60,
        path="/",
    )
    return {"status": "success", "usuario": public_user(usuario)}


@router.post("/recuperacao/solicitar", status_code=202)
def solicitar_recuperacao(
    dados: schemas.RecuperacaoAcessoSolicitar,
    request: Request,
    db: Session = Depends(get_db),
):
    generic = {
        "status": "accepted",
        "message": "Se os dados conferirem e a conta estiver bloqueada, o código será enviado ao e-mail cadastrado.",
    }
    now = _now()
    usuario = db.query(models.Usuario).filter(
        models.Usuario.usuario_login == dados.usuario_login,
        models.Usuario.ativo.is_(True),
    ).with_for_update().first()
    if not usuario or not usuario.email or usuario.email.strip().lower() != dados.email:
        return generic
    if not usuario.bloqueado_ate or usuario.bloqueado_ate <= now:
        return generic
    if usuario.recuperacao_solicitada_em and usuario.recuperacao_solicitada_em > now - timedelta(seconds=60):
        return generic

    code = f"{secrets.randbelow(1_000_000):06d}"
    usuario.codigo_recuperacao_hash = recovery_code_digest(usuario.id, code)
    usuario.codigo_recuperacao_expira_em = now + timedelta(minutes=_recovery_minutes())
    usuario.codigo_recuperacao_tentativas = 0
    usuario.recuperacao_solicitada_em = now
    try:
        send_recovery_code(usuario.email, code)
    except RecoveryDeliveryUnavailable:
        user_id = usuario.id
        db.rollback()
        usuario = db.query(models.Usuario).filter(models.Usuario.id == user_id).first()
        _notify_security_admins(
            db,
            usuario,
            "Falha no envio do código de acesso",
            f"{usuario.nome} solicitou desbloqueio, mas o envio por e-mail não está configurado ou falhou.",
        )
        _audit_access(db, usuario, "RECUPERACAO_ENVIO_FALHOU", request)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "RECOVERY_DELIVERY_UNAVAILABLE",
                "message": "Não foi possível enviar o código agora. Procure um administrador para desbloquear sua conta.",
            },
        ) from None
    _audit_access(db, usuario, "RECUPERACAO_SOLICITADA", request)
    db.commit()
    return generic


@router.post("/recuperacao/confirmar")
def confirmar_recuperacao(
    dados: schemas.RecuperacaoAcessoConfirmar,
    request: Request,
    db: Session = Depends(get_db),
):
    now = _now()
    usuario = db.query(models.Usuario).filter(
        models.Usuario.usuario_login == dados.usuario_login,
        models.Usuario.ativo.is_(True),
    ).with_for_update().first()
    invalid = {"code": "INVALID_RECOVERY_CODE", "message": "Código inválido ou expirado"}
    if (
        not usuario
        or not usuario.codigo_recuperacao_hash
        or not usuario.codigo_recuperacao_expira_em
        or usuario.codigo_recuperacao_expira_em <= now
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=invalid)
    if not verify_recovery_code(usuario.id, dados.codigo, usuario.codigo_recuperacao_hash):
        usuario.codigo_recuperacao_tentativas = int(usuario.codigo_recuperacao_tentativas or 0) + 1
        if usuario.codigo_recuperacao_tentativas >= 5:
            usuario.codigo_recuperacao_hash = None
            usuario.codigo_recuperacao_expira_em = None
            _notify_security_admins(
                db, usuario, "Código de desbloqueio invalidado",
                f"A recuperação da conta de {usuario.nome} foi invalidada após cinco códigos incorretos.",
            )
        _audit_access(db, usuario, "RECUPERACAO_CODIGO_INVALIDO", request, {"tentativa": usuario.codigo_recuperacao_tentativas})
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=invalid)

    usuario.tentativas_login = 0
    usuario.bloqueado_ate = None
    usuario.codigo_recuperacao_hash = None
    usuario.codigo_recuperacao_expira_em = None
    usuario.codigo_recuperacao_tentativas = 0
    _audit_access(db, usuario, "CONTA_DESBLOQUEADA_POR_CODIGO", request)
    _notify_security_admins(
        db, usuario, "Conta desbloqueada com código",
        f"{usuario.nome} confirmou o código enviado ao e-mail e recuperou o acesso.",
    )
    db.commit()
    return {"status": "success", "message": "Conta desbloqueada. Você já pode entrar com sua senha."}


@router.get("/me", response_model=schemas.UsuarioResponse)
def me(usuario: models.Usuario = Depends(current_user)):
    return public_user(usuario)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "success"}
