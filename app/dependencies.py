"""Dependências de autenticação e autorização das rotas."""

from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.security import COOKIE_NAME, decode_access_token


def current_user(request: Request, db: Session = Depends(get_db)) -> models.Usuario:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Faça login")
    try:
        user_id = decode_access_token(token)
    except (jwt.PyJWTError, ValueError, RuntimeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão inválida ou expirada",
        ) from None
    usuario = db.query(models.Usuario).filter(models.Usuario.id == user_id).first()
    if not usuario or not usuario.ativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário inválido")
    return usuario


def require_permission(permission: str) -> Callable:
    def dependency(usuario: models.Usuario = Depends(current_user)) -> models.Usuario:
        if usuario.tipo_usuario != "DESENVOLVEDOR" and not getattr(usuario, permission, False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Você não possui permissão para esta ação",
            )
        return usuario

    return dependency


def require_admin(usuario: models.Usuario = Depends(current_user)) -> models.Usuario:
    """Administrador é quem pode gerenciar usuários e configurações críticas."""
    if usuario.tipo_usuario not in {"DESENVOLVEDOR", "DONO"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ação permitida somente para administrador",
        )
    return usuario
