"""Regras compartilhadas pela API."""

import os
import secrets

from sqlalchemy.orm import Session

from app import models
from app.security import hash_password, is_password_hash


def public_user(usuario: models.Usuario) -> dict:
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "usuario_login": usuario.usuario_login,
        "pode_gerenciar_usuarios": usuario.pode_gerenciar_usuarios,
        "pode_alterar_custos": usuario.pode_alterar_custos,
        "pode_movimentar_estoque": usuario.pode_movimentar_estoque,
        "pode_gerenciar_clientes": usuario.pode_gerenciar_clientes,
        "pode_acessar_agenda": usuario.pode_acessar_agenda,
        "pode_acessar_docs": usuario.pode_acessar_docs,
        "pode_gerenciar_historico": usuario.pode_gerenciar_historico,
    }


def bootstrap_security(db: Session) -> None:
    """Invalida senhas legadas em texto puro e configura o administrador seguro."""
    for usuario in db.query(models.Usuario).all():
        if not is_password_hash(usuario.senha_hash):
            usuario.senha_hash = hash_password(secrets.token_urlsafe(32))

    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD")
    if password:
        if len(password) < 12:
            raise RuntimeError("BOOTSTRAP_ADMIN_PASSWORD deve ter pelo menos 12 caracteres")
        login = os.getenv("BOOTSTRAP_ADMIN_LOGIN", "eduardo").strip().lower()
        usuario = (
            db.query(models.Usuario)
            .filter(models.Usuario.usuario_login == login)
            .first()
        )
        if not usuario:
            usuario = models.Usuario(
                nome=os.getenv("BOOTSTRAP_ADMIN_NAME", "Administrador"),
                usuario_login=login,
            )
            db.add(usuario)
        usuario.senha_hash = hash_password(password)
        usuario.pode_gerenciar_usuarios = True
        usuario.pode_alterar_custos = True
        usuario.pode_movimentar_estoque = True
        usuario.pode_gerenciar_clientes = True
        usuario.pode_acessar_agenda = True
        usuario.pode_acessar_docs = True
        usuario.pode_gerenciar_historico = True
    db.commit()
