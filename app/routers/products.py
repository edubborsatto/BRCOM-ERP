from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import current_user, require_admin, require_permission
from app.inventory import record_movement

router = APIRouter(prefix="/produtos", tags=["Produtos"])


def _produto_publico(produto: models.Produto, usuario: models.Usuario) -> dict:
    dados = schemas.ProdutoResponse.model_validate(produto).model_dump()
    if not usuario.pode_alterar_custos:
        dados["preco_custo"] = Decimal("0")
    return dados


@router.post("/", response_model=schemas.ProdutoResponse, status_code=201)
def criar_produto(
    dados: schemas.ProdutoCreate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_permission("pode_movimentar_estoque")),
):
    if dados.codigo == "AUTO":
        dados.codigo = f"AUTO-{db.query(models.Produto).count() + 1:05d}"
    if not usuario.pode_alterar_custos and dados.preco_custo:
        raise HTTPException(status_code=403, detail="Sem permissão para definir custos")
    conflito = db.query(models.Produto).filter(
        (models.Produto.nome == dados.nome) | (models.Produto.codigo == dados.codigo)
    ).first()
    if conflito:
        raise HTTPException(status_code=400, detail="Nome ou código já cadastrado")
    novo = models.Produto(**dados.model_dump())
    db.add(novo)
    db.flush()
    if dados.quantidade_atual:
        quantidade = dados.quantidade_atual
        novo.quantidade_atual = 0
        record_movement(db, novo, "ENTRADA", quantidade, usuario, "Estoque inicial", "CADASTRO")
    db.commit()
    db.refresh(novo)
    return _produto_publico(novo, usuario)


@router.get("/", response_model=list[schemas.ProdutoResponse])
def listar_produtos(
    tipo_item: str | None = Query(default=None),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(current_user),
):
    query = db.query(models.Produto)
    if tipo_item:
        query = query.filter(models.Produto.tipo_item == tipo_item)
    return [_produto_publico(p, usuario) for p in query.order_by(models.Produto.nome).all()]


@router.put("/{produto_id}", response_model=schemas.ProdutoResponse)
def atualizar_produto(
    produto_id: int,
    dados: schemas.ProdutoUpdate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_permission("pode_movimentar_estoque")),
):
    produto = db.get(models.Produto, produto_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    conflito = db.query(models.Produto).filter(
        models.Produto.id != produto_id,
        ((models.Produto.nome == dados.nome) | (models.Produto.codigo == dados.codigo)),
    ).first()
    if conflito:
        raise HTTPException(status_code=400, detail="Nome ou código já cadastrado")
    valores = dados.model_dump(exclude={"quantidade_atual"})
    if not usuario.pode_alterar_custos:
        valores.pop("preco_custo", None)
    for campo, valor in valores.items():
        setattr(produto, campo, valor)
    db.commit()
    db.refresh(produto)
    return _produto_publico(produto, usuario)


@router.delete("/{produto_id}")
def excluir_produto(
    produto_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_admin),
):
    produto = db.get(models.Produto, produto_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    if produto.formula or db.query(models.FormulaComponente).filter(
        models.FormulaComponente.materia_prima_id == produto_id
    ).first():
        raise HTTPException(status_code=409, detail="Produto vinculado a uma fórmula")
    db.add(models.HistoricoEstoque(
        produto_id=None, produto_nome=produto.nome, tipo_movimentacao="EXCLUSAO",
        quantidade=produto.quantidade_atual, saldo_anterior=produto.quantidade_atual,
        saldo_apos=0, motivo="Cadastro excluído pelo administrador",
        usuario_id=usuario.id, usuario_responsavel=usuario.nome,
    ))
    db.delete(produto)
    db.commit()
    return {"status": "success"}
