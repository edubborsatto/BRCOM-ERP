"""Regras compartilhadas pela API."""

import json
import os
import secrets

from sqlalchemy.orm import Session

from app import models
from app.security import hash_password, is_password_hash


ROLE_PERMISSIONS = {
    "DESENVOLVEDOR": {
        "pode_gerenciar_usuarios": True,
        "pode_alterar_custos": True,
        "pode_movimentar_estoque": True,
        "pode_gerenciar_clientes": True,
        "pode_acessar_agenda": True,
        "pode_acessar_docs": True,
        "pode_gerenciar_historico": True,
        "pode_criar_orcamentos": True,
        "pode_aprovar_orcamentos": True,
        "pode_registrar_vendas": True,
        "pode_importar_planilhas": True,
        "pode_editar_planilhas": True,
        "pode_ver_faturamento": True,
    },
    "DONO": {
        "pode_gerenciar_usuarios": True,
        "pode_alterar_custos": True,
        "pode_movimentar_estoque": True,
        "pode_gerenciar_clientes": True,
        "pode_acessar_agenda": True,
        "pode_acessar_docs": False,
        "pode_gerenciar_historico": True,
        "pode_criar_orcamentos": True,
        "pode_aprovar_orcamentos": True,
        "pode_registrar_vendas": True,
        "pode_importar_planilhas": True,
        "pode_editar_planilhas": True,
        "pode_ver_faturamento": True,
    },
    "FUNCIONARIO": {
        "pode_gerenciar_usuarios": False,
        "pode_alterar_custos": False,
        "pode_movimentar_estoque": True,
        "pode_gerenciar_clientes": True,
        "pode_acessar_agenda": True,
        "pode_acessar_docs": False,
        "pode_gerenciar_historico": False,
        "pode_criar_orcamentos": True,
        "pode_aprovar_orcamentos": False,
        "pode_registrar_vendas": True,
        "pode_importar_planilhas": False,
        "pode_editar_planilhas": False,
        "pode_ver_faturamento": False,
    },
}


def role_permissions(role: str) -> dict:
    return ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS["FUNCIONARIO"]).copy()


def audit_user_change(db: Session, actor, action: str, target, before=None, after=None) -> None:
    db.add(models.AuditoriaSistema(
        categoria="USUARIOS",
        acao=action,
        entidade="usuarios",
        entidade_id=target.id,
        dados_anteriores=json.dumps(before, ensure_ascii=False) if before else None,
        dados_novos=json.dumps(after, ensure_ascii=False) if after else None,
        usuario_id=actor.id,
        usuario_nome=actor.nome,
    ))


def public_user(usuario: models.Usuario) -> dict:
    return {
        "id": usuario.id,
        "nome": usuario.nome,
        "usuario_login": usuario.usuario_login,
        "tipo_usuario": usuario.tipo_usuario,
        "ativo": usuario.ativo,
        "pode_gerenciar_usuarios": usuario.pode_gerenciar_usuarios,
        "pode_alterar_custos": usuario.pode_alterar_custos,
        "pode_movimentar_estoque": usuario.pode_movimentar_estoque,
        "pode_gerenciar_clientes": usuario.pode_gerenciar_clientes,
        "pode_acessar_agenda": usuario.pode_acessar_agenda,
        "pode_acessar_docs": usuario.pode_acessar_docs,
        "pode_gerenciar_historico": usuario.pode_gerenciar_historico,
        "pode_criar_orcamentos": usuario.pode_criar_orcamentos,
        "pode_aprovar_orcamentos": usuario.pode_aprovar_orcamentos,
        "pode_registrar_vendas": usuario.pode_registrar_vendas,
        "pode_importar_planilhas": usuario.pode_importar_planilhas,
        "pode_editar_planilhas": usuario.pode_editar_planilhas,
        "pode_ver_faturamento": usuario.pode_ver_faturamento,
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
        usuario.tipo_usuario = "DESENVOLVEDOR"
        usuario.ativo = True
        for permission, allowed in role_permissions("DESENVOLVEDOR").items():
            setattr(usuario, permission, allowed)
    db.commit()
