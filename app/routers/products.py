from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import current_user, require_admin, require_permission
from app.inventory import record_movement
from app.services import audit

router = APIRouter(prefix="/produtos", tags=["Produtos"])


def _produto_publico(produto: models.Produto, usuario: models.Usuario) -> dict:
    dados = schemas.ProdutoResponse.model_validate(produto).model_dump()
    if not usuario.pode_alterar_custos:
        dados["preco_custo"] = Decimal("0")
        dados["preco_venda"] = Decimal("0")
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
    else:
        db.add(models.HistoricoEstoque(
            produto_id=novo.id, produto_nome=novo.nome, tipo_movimentacao="CADASTRO",
            quantidade=0, saldo_anterior=0, saldo_apos=0,
            motivo="Produto cadastrado", usuario_id=usuario.id,
            usuario_responsavel=usuario.nome,
        ))
    audit(db, usuario, "PRODUTOS", "CRIAR", "produtos", novo.id, after={"codigo": novo.codigo, "nome": novo.nome})
    db.commit()
    db.refresh(novo)
    return _produto_publico(novo, usuario)


@router.get("/", response_model=list[schemas.ProdutoResponse])
def listar_produtos(
    tipo_item: str | None = Query(default=None),
    busca: str | None = Query(default=None),
    familia: str | None = Query(default=None),
    tipo: str | None = Query(default=None),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(current_user),
):
    query = db.query(models.Produto).filter(models.Produto.ativo.is_(True))
    if tipo_item:
        query = query.filter(models.Produto.tipo_item == tipo_item)
    if busca:
        termo = f"%{busca.strip()}%"
        query = query.filter(or_(
            models.Produto.codigo.ilike(termo), models.Produto.nome.ilike(termo),
            models.Produto.tipo.ilike(termo), models.Produto.familia.ilike(termo),
            models.Produto.localizacao.ilike(termo),
        ))
    if familia:
        query = query.filter(models.Produto.familia == familia)
    if tipo:
        query = query.filter(models.Produto.tipo == tipo)
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
        valores.pop("preco_venda", None)
    alteracoes = []
    for campo, valor in valores.items():
        anterior = getattr(produto, campo)
        if anterior != valor:
            alteracoes.append(f"{campo}: {anterior or '—'} → {valor or '—'}")
        setattr(produto, campo, valor)
    if alteracoes:
        db.add(models.HistoricoEstoque(
            produto_id=produto.id, produto_nome=produto.nome,
            tipo_movimentacao="EDICAO", quantidade=0,
            saldo_anterior=produto.quantidade_atual, saldo_apos=produto.quantidade_atual,
            motivo="; ".join(alteracoes), usuario_id=usuario.id,
            usuario_responsavel=usuario.nome,
        ))
        audit(db, usuario, "PRODUTOS", "EDITAR", "produtos", produto.id, before={"alteracoes": alteracoes}, after=valores)
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
    possui_vinculos = bool(
        produto.formula
        or db.query(models.FormulaComponente).filter(models.FormulaComponente.materia_prima_id == produto_id).first()
        or db.query(models.OrcamentoItem).filter(models.OrcamentoItem.produto_id == produto_id).first()
        or db.query(models.PedidoFuturoItem).filter(models.PedidoFuturoItem.produto_id == produto_id).first()
        or db.query(models.PedidoFuturoMateriaPrima).filter(models.PedidoFuturoMateriaPrima.materia_prima_id == produto_id).first()
    )
    db.add(models.HistoricoEstoque(
        produto_id=None, produto_nome=produto.nome, tipo_movimentacao="EXCLUSAO",
        quantidade=produto.quantidade_atual, saldo_anterior=produto.quantidade_atual,
        saldo_apos=0, motivo="Cadastro excluído pelo administrador",
        usuario_id=usuario.id, usuario_responsavel=usuario.nome,
    ))
    acao = "ARQUIVAR_COM_HISTORICO" if possui_vinculos else "EXCLUIR"
    audit(db, usuario, "PRODUTOS", acao, "produtos", produto.id, before={"codigo": produto.codigo, "nome": produto.nome, "possui_vinculos": possui_vinculos})
    if possui_vinculos:
        produto.ativo = False
    else:
        db.delete(produto)
    db.commit()
    return {"status": "success", "modo": "arquivado" if possui_vinculos else "excluido"}
