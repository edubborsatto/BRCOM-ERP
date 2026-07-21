from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import current_user, require_permission

router = APIRouter(prefix="/produtos", tags=["Produtos"])


def _produto_publico(produto: models.Produto, usuario: models.Usuario) -> dict:
    dados = schemas.ProdutoResponse.model_validate(produto).model_dump()
    if not usuario.pode_alterar_custos:
        dados["preco_custo"] = 0.0
    return dados


@router.post("/", response_model=schemas.ProdutoResponse, status_code=201)
def criar_produto(
    produto: schemas.ProdutoCreate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_permission("pode_movimentar_estoque")),
):
    if not usuario.pode_alterar_custos and produto.preco_custo:
        raise HTTPException(status_code=403, detail="Sem permissão para definir custos")
    if db.query(models.Produto).filter(models.Produto.nome == produto.nome).first():
        raise HTTPException(status_code=400, detail="Este produto já está cadastrado")
    novo = models.Produto(**produto.model_dump())
    db.add(novo)
    db.flush()
    db.add(models.HistoricoEstoque(
        produto_nome=novo.nome, tipo_movimentacao="CADASTRO",
        quantidade=novo.quantidade_atual, saldo_apos=novo.quantidade_atual,
        usuario_responsavel=usuario.nome,
    ))
    db.commit()
    db.refresh(novo)
    return _produto_publico(novo, usuario)


@router.get("/", response_model=List[schemas.ProdutoResponse])
def listar_produtos(
    db: Session = Depends(get_db), usuario: models.Usuario = Depends(current_user)
):
    return [_produto_publico(p, usuario) for p in db.query(models.Produto).all()]


@router.put("/{produto_id}", response_model=schemas.ProdutoResponse)
def atualizar_produto(
    produto_id: int,
    dados: schemas.ProdutoCreate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_permission("pode_movimentar_estoque")),
):
    produto = db.query(models.Produto).filter(models.Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    qtd_anterior = produto.quantidade_atual
    custo_anterior = produto.preco_custo
    for key, value in dados.model_dump().items():
        if key == "preco_custo" and not usuario.pode_alterar_custos:
            continue
        setattr(produto, key, value)
    if qtd_anterior != produto.quantidade_atual:
        diferenca = produto.quantidade_atual - qtd_anterior
        db.add(models.HistoricoEstoque(
            produto_nome=produto.nome,
            tipo_movimentacao="ENTRADA" if diferenca > 0 else "SAÍDA",
            quantidade=abs(diferenca), saldo_apos=produto.quantidade_atual,
            usuario_responsavel=usuario.nome,
        ))
    if not usuario.pode_alterar_custos:
        produto.preco_custo = custo_anterior
    db.commit()
    db.refresh(produto)
    return _produto_publico(produto, usuario)


@router.delete("/{produto_id}")
def excluir_produto(
    produto_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_permission("pode_movimentar_estoque")),
):
    produto = db.query(models.Produto).filter(models.Produto.id == produto_id).first()
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    db.add(models.HistoricoEstoque(
        produto_nome=produto.nome, tipo_movimentacao="EXCLUSÃO",
        quantidade=produto.quantidade_atual, saldo_apos=0.0,
        usuario_responsavel=usuario.nome,
    ))
    db.delete(produto)
    db.commit()
    return {"status": "success"}
