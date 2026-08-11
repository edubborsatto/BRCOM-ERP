from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import current_user
from app.security import COOKIE_NAME, cookie_is_secure, create_access_token, verify_password
from app.services import public_user

router = APIRouter(prefix="/api", tags=["Autenticação"])


@router.post("/login", response_model=schemas.LoginResponse)
def login(dados: schemas.LoginRequest, response: Response, db: Session = Depends(get_db)):
    usuario = (
        db.query(models.Usuario)
        .filter(
            models.Usuario.usuario_login == dados.usuario_login.strip().lower(),
            models.Usuario.ativo.is_(True),
        )
        .first()
    )
    if not usuario or not verify_password(dados.senha, usuario.senha_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário ou senha incorretos")
    response.set_cookie(
        key=COOKIE_NAME,
        value=create_access_token(usuario.id),
        httponly=True,
        secure=cookie_is_secure(),
        samesite="lax",
        max_age=8 * 60 * 60,
        path="/",
    )
    return {"status": "success", "usuario": public_user(usuario)}


@router.get("/me", response_model=schemas.UsuarioResponse)
def me(usuario: models.Usuario = Depends(current_user)):
    return public_user(usuario)


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "success"}
