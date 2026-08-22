from datetime import date, datetime, time, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import require_admin
from app.security import hash_password
from app.services import audit_user_change, public_user, role_permissions

router = APIRouter(prefix="/usuarios", tags=["Usuários"])
PERMISSION_FIELDS = tuple(role_permissions("FUNCIONARIO"))


def _snapshot(user: models.Usuario) -> dict:
    return {
        "nome": user.nome,
        "usuario_login": user.usuario_login,
        "email": user.email,
        "telefone": user.telefone,
        "tipo_usuario": user.tipo_usuario,
        "ativo": user.ativo,
        "tentativas_login": user.tentativas_login,
        "bloqueado_ate": user.bloqueado_ate,
        **{field: bool(getattr(user, field)) for field in PERMISSION_FIELDS},
    }


def _validate_role_change(actor: models.Usuario, target_role: str, confirmed: bool) -> None:
    if actor.tipo_usuario == "DESENVOLVEDOR":
        return
    if target_role == "DESENVOLVEDOR" and not confirmed:
        raise HTTPException(
            status_code=409,
            detail="Confirme explicitamente a criação do perfil Desenvolvedor",
        )


def _permission_values(payload, role: str, actor: models.Usuario) -> dict:
    values = role_permissions(role)
    supplied = payload.model_fields_set
    for field in PERMISSION_FIELDS:
        if field in supplied:
            values[field] = getattr(payload, field)
    if role == "DESENVOLVEDOR":
        values = role_permissions(role)
    if actor.tipo_usuario != "DESENVOLVEDOR" and role != "DESENVOLVEDOR":
        values["pode_acessar_docs"] = False
    return values


@router.post("/", response_model=schemas.UsuarioResponse, status_code=201)
def criar_usuario(
    usuario: schemas.UsuarioCreate,
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(require_admin),
):
    login = usuario.usuario_login.strip().lower()
    if db.query(models.Usuario).filter(models.Usuario.usuario_login == login).first():
        raise HTTPException(status_code=400, detail="Este login já existe")
    _validate_role_change(atual, usuario.tipo_usuario, usuario.confirmar_desenvolvedor)
    permissions = _permission_values(usuario, usuario.tipo_usuario, atual)
    novo = models.Usuario(
        nome=usuario.nome.strip(),
        usuario_login=login,
        senha_hash=hash_password(usuario.senha),
        email=usuario.email.lower() if usuario.email else None,
        telefone=usuario.telefone,
        tipo_usuario=usuario.tipo_usuario,
        ativo=usuario.ativo,
        **permissions,
    )
    db.add(novo)
    db.flush()
    audit_user_change(db, atual, "CRIADO", novo, after=_snapshot(novo))
    db.commit()
    db.refresh(novo)
    return public_user(novo)


@router.get("/", response_model=List[schemas.UsuarioResponse])
def listar_usuarios(
    incluir_inativos: bool = Query(default=True),
    db: Session = Depends(get_db),
    _: models.Usuario = Depends(require_admin),
):
    query = db.query(models.Usuario)
    if not incluir_inativos:
        query = query.filter(models.Usuario.ativo.is_(True))
    return [public_user(usuario) for usuario in query.order_by(models.Usuario.nome).all()]


@router.put("/{usuario_id}", response_model=schemas.UsuarioResponse)
def atualizar_usuario(
    usuario_id: int,
    dados: schemas.UsuarioUpdate,
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(require_admin),
):
    usuario = db.get(models.Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if atual.tipo_usuario != "DESENVOLVEDOR" and usuario.tipo_usuario == "DESENVOLVEDOR":
        raise HTTPException(status_code=403, detail="Somente Desenvolvedor pode alterar outro Desenvolvedor")
    _validate_role_change(atual, dados.tipo_usuario, dados.confirmar_desenvolvedor)
    before = _snapshot(usuario)
    if atual.id == usuario.id:
        protected = dados.tipo_usuario != usuario.tipo_usuario or dados.ativo != usuario.ativo
        permission_changed = any(
            field in dados.model_fields_set and getattr(dados, field) != getattr(usuario, field)
            for field in PERMISSION_FIELDS
        )
        if protected or permission_changed:
            raise HTTPException(status_code=400, detail="Você não pode alterar o próprio perfil ou permissões")
    login = dados.usuario_login.strip().lower()
    duplicate = db.query(models.Usuario).filter(
        models.Usuario.usuario_login == login,
        models.Usuario.id != usuario.id,
    ).first()
    if duplicate:
        raise HTTPException(status_code=400, detail="Este login já existe")
    usuario.nome = dados.nome.strip()
    usuario.usuario_login = login
    usuario.email = dados.email.lower() if dados.email else None
    usuario.telefone = dados.telefone
    usuario.tipo_usuario = dados.tipo_usuario
    usuario.ativo = dados.ativo
    for field, value in _permission_values(dados, dados.tipo_usuario, atual).items():
        setattr(usuario, field, value)
    if dados.senha:
        usuario.senha_hash = hash_password(dados.senha)
        usuario.tentativas_login = 0
        usuario.bloqueado_ate = None
        usuario.codigo_recuperacao_hash = None
        usuario.codigo_recuperacao_expira_em = None
    audit_user_change(db, atual, "ATUALIZADO", usuario, before, _snapshot(usuario))
    db.commit()
    db.refresh(usuario)
    return public_user(usuario)


@router.post("/{usuario_id}/desbloquear", response_model=schemas.UsuarioResponse)
def desbloquear_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(require_admin),
):
    usuario = db.get(models.Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if atual.tipo_usuario != "DESENVOLVEDOR" and usuario.tipo_usuario == "DESENVOLVEDOR":
        raise HTTPException(status_code=403, detail="Somente Desenvolvedor pode desbloquear outro Desenvolvedor")
    before = _snapshot(usuario)
    usuario.tentativas_login = 0
    usuario.bloqueado_ate = None
    usuario.codigo_recuperacao_hash = None
    usuario.codigo_recuperacao_expira_em = None
    usuario.codigo_recuperacao_tentativas = 0
    audit_user_change(db, atual, "DESBLOQUEADO_ADMIN", usuario, before, _snapshot(usuario))
    db.add(models.Notificacao(
        usuario_id=usuario.id,
        tipo="SEGURANCA",
        titulo="Acesso desbloqueado",
        mensagem=f"Seu acesso foi desbloqueado por {atual.nome}.",
        entidade="usuarios",
        entidade_id=usuario.id,
    ))
    db.commit()
    db.refresh(usuario)
    return public_user(usuario)


@router.delete("/{usuario_id}")
def desativar_usuario(
    usuario_id: int,
    db: Session = Depends(get_db),
    atual: models.Usuario = Depends(require_admin),
):
    if atual.id == usuario_id:
        raise HTTPException(status_code=400, detail="Você não pode desativar o próprio usuário")
    usuario = db.get(models.Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if atual.tipo_usuario != "DESENVOLVEDOR" and usuario.tipo_usuario == "DESENVOLVEDOR":
        raise HTTPException(status_code=403, detail="Somente Desenvolvedor pode desativar outro Desenvolvedor")
    before = _snapshot(usuario)
    usuario.ativo = False
    audit_user_change(db, atual, "DESATIVADO", usuario, before, _snapshot(usuario))
    db.commit()
    return {"status": "success"}


@router.get("/auditoria", response_model=list[schemas.AuditoriaSistemaResponse])
def listar_auditoria(
    limite: int = Query(default=200, ge=1, le=1000),
    data_inicial: date | None = None,
    data_final: date | None = None,
    usuario_id: int | None = None,
    modulo: str | None = None,
    acao: str | None = None,
    db: Session = Depends(get_db),
    _: models.Usuario = Depends(require_admin),
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
    return query.order_by(
        models.AuditoriaSistema.criado_em.desc()
    ).limit(limite).all()
