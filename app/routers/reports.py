from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.dependencies import current_user, require_permission
from app.inventory import decimal

router = APIRouter(prefix="/relatorios", tags=["Relatórios"])


@router.get("/resumo")
def resumo(
    db: Session = Depends(get_db), usuario: models.Usuario = Depends(current_user)
):
    materias = db.query(models.Produto).filter_by(tipo_item="MATERIA_PRIMA").all()
    acabados = db.query(models.Produto).filter_by(tipo_item="PRODUTO_ACABADO").all()
    vendas = db.query(models.Venda).all()
    financeiro = usuario.pode_alterar_custos
    return {
        "clientes": db.query(models.Cliente).count(),
        "produtos": db.query(models.Produto).count(),
        "materias_primas": len(materias),
        "produtos_acabados": len(acabados),
        "valor_estoque_materias_primas": sum((decimal(p.quantidade_atual) * decimal(p.preco_custo) for p in materias), Decimal("0")) if financeiro else 0,
        "valor_estoque_produtos_acabados": sum((decimal(p.quantidade_atual) * decimal(p.preco_custo) for p in acabados), Decimal("0")) if financeiro else 0,
        "total_vendas": sum((decimal(v.valor_total) for v in vendas), Decimal("0")) if financeiro else 0,
        "vendas_recibo": sum((decimal(v.valor_total) for v in vendas if v.tipo_documento == "RECIBO"), Decimal("0")) if financeiro else 0,
        "vendas_nota_fiscal": sum((decimal(v.valor_total) for v in vendas if v.tipo_documento == "NOTA_FISCAL"), Decimal("0")) if financeiro else 0,
        "orcamentos_pendentes": db.query(models.Orcamento).filter_by(status="RASCUNHO").count(),
        "ordens_abertas": db.query(models.OrdemServico).filter_by(status="ABERTA").count(),
    }


@router.get("/vendas")
def vendas_por_documento(
    db: Session = Depends(get_db),
    _=Depends(require_permission("pode_alterar_custos")),
):
    linhas = db.query(
        models.Venda.tipo_documento,
        func.count(models.Venda.id),
        func.sum(models.Venda.valor_total),
    ).group_by(models.Venda.tipo_documento).all()
    return [{"tipo_documento": tipo, "quantidade": qtd, "total": total} for tipo, qtd, total in linhas]


@router.get("/produtos")
def produtos(db: Session = Depends(get_db), _=Depends(current_user)):
    return [{
        "codigo": p.codigo, "nome": p.nome, "tipo_item": p.tipo_item,
        "familia": p.familia, "quantidade": p.quantidade_atual,
        "estoque_minimo": p.estoque_minimo,
    } for p in db.query(models.Produto).order_by(models.Produto.tipo_item, models.Produto.nome)]


@router.get("/clientes")
def clientes(db: Session = Depends(get_db), _=Depends(current_user)):
    vendas = dict(db.query(models.Venda.cliente_id, func.sum(models.Venda.valor_total)).group_by(models.Venda.cliente_id).all())
    return [{"id": c.id, "nome": c.nome, "documento": c.documento, "total_vendas": vendas.get(c.id, 0)} for c in db.query(models.Cliente).all()]


@router.get("/custos")
def custos(db: Session = Depends(get_db), _=Depends(require_permission("pode_alterar_custos"))):
    return [{
        "codigo": p.codigo, "nome": p.nome, "tipo_item": p.tipo_item,
        "preco_custo": p.preco_custo, "preco_venda": p.preco_venda,
        "valor_em_estoque": decimal(p.preco_custo) * decimal(p.quantidade_atual),
    } for p in db.query(models.Produto).order_by(models.Produto.nome)]
