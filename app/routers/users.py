from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import require_permission
from app.security import hash_password
from app.services import public_user

router = APIRouter(prefix="/usuarios", tags=["Usuários"])
manage_users = require_permission("pode_gerenciar_usuarios")


@router.post("/", response_model=schemas.UsuarioResponse, status_code=201)
def criar_usuario(usuario: schemas.UsuarioCreate, db: Session = Depends(get_db), _=Depends(manage_users)):
    login = usuario.usuario_login.strip().lower()
    if db.query(models.Usuario).filter(models.Usuario.usuario_login == login).first():
        raise HTTPException(status_code=400, detail="Este login já existe")
    dados = usuario.model_dump(exclude={"senha"})
    dados["usuario_login"] = login
    novo = models.Usuario(**dados, senha_hash=hash_password(usuario.senha))
    db.add(novo)
    db.commit()
    db.refresh(novo)
    return public_user(novo)


@router.get("/", response_model=List[schemas.UsuarioResponse])
def listar_usuarios(db: Session = Depends(get_db), _=Depends(manage_users)):
    return [public_user(usuario) for usuario in db.query(models.Usuario).all()]


@router.put("/{usuario_id}", response_model=schemas.UsuarioResponse)
def atualizar_usuario(usuario_id: int, dados: schemas.UsuarioUpdate, db: Session = Depends(get_db), _=Depends(manage_users)):
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    atualizacao = dados.model_dump(exclude={"senha"})
    atualizacao["usuario_login"] = dados.usuario_login.strip().lower()
    for key, value in atualizacao.items():
        setattr(usuario, key, value)
    if dados.senha:
        usuario.senha_hash = hash_password(dados.senha)
    db.commit()
    db.refresh(usuario)
    return public_user(usuario)


@router.delete("/{usuario_id}")
def excluir_usuario(usuario_id: int, db: Session = Depends(get_db), atual=Depends(manage_users)):
    if atual.id == usuario_id:
        raise HTTPException(status_code=400, detail="Você não pode excluir seu próprio usuário")
    usuario = db.query(models.Usuario).filter(models.Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    db.delete(usuario)
    db.commit()
    return {"status": "success"}
