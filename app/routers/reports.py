from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.dependencies import current_user, require_permission
from app.inventory import decimal

router = APIRouter(prefix="/relatorios", tags=["Relatórios"])


def _imported_sales(db: Session):
    return db.query(models.RegistroVendaImportado).join(models.ImportacaoPlanilha).filter(
        models.ImportacaoPlanilha.status == "CONFIRMADA",
        models.RegistroVendaImportado.ativo.is_(True),
        or_(
            models.RegistroVendaImportado.status_importacao == "NOVO",
            models.RegistroVendaImportado.decisao_duplicidade == "IMPORTAR",
        ),
    )


@router.get("/resumo")
def resumo(
    db: Session = Depends(get_db), usuario: models.Usuario = Depends(current_user)
):
    materias = db.query(models.Produto).filter_by(tipo_item="MATERIA_PRIMA").all()
    acabados = db.query(models.Produto).filter_by(tipo_item="PRODUTO_ACABADO").all()
    vendas = db.query(models.Venda).all()
    importados = _imported_sales(db).all()
    financeiro = usuario.tipo_usuario == "DESENVOLVEDOR" or usuario.pode_ver_faturamento
    return {
        "clientes": db.query(models.Cliente).count(),
        "produtos": db.query(models.Produto).count(),
        "materias_primas": len(materias),
        "produtos_acabados": len(acabados),
        "valor_estoque_materias_primas": sum((decimal(p.quantidade_atual) * decimal(p.preco_custo) for p in materias), Decimal("0")) if financeiro else 0,
        "valor_estoque_produtos_acabados": sum((decimal(p.quantidade_atual) * decimal(p.preco_custo) for p in acabados), Decimal("0")) if financeiro else 0,
        "total_vendas": sum((decimal(v.valor_total) for v in vendas + importados), Decimal("0")) if financeiro else 0,
        "vendas_recibo": sum((decimal(v.valor_total) for v in vendas + importados if v.tipo_documento == "RECIBO"), Decimal("0")) if financeiro else 0,
        "vendas_nota_fiscal": sum((decimal(v.valor_total) for v in vendas + importados if v.tipo_documento == "NOTA_FISCAL"), Decimal("0")) if financeiro else 0,
        "orcamentos_pendentes": db.query(models.Orcamento).filter_by(status="RASCUNHO").count(),
        "pedidos_futuros_pendentes": db.query(models.PedidoFuturo).filter(
            models.PedidoFuturo.confirmado_em.is_(None)
        ).count(),
        "ordens_abertas": db.query(models.OrdemServico).filter_by(status="ABERTA").count(),
    }


@router.get("/vendas")
def vendas_por_documento(
    db: Session = Depends(get_db),
    _=Depends(require_permission("pode_ver_faturamento")),
):
    linhas = db.query(
        models.Venda.tipo_documento,
        func.count(models.Venda.id),
        func.sum(models.Venda.valor_total),
    ).group_by(models.Venda.tipo_documento).all()
    totals = {tipo: {"quantidade": qtd, "total": decimal(total)} for tipo, qtd, total in linhas}
    imported = _imported_sales(db).all()
    for tipo in ("NOTA_FISCAL", "RECIBO"):
        selected = [row for row in imported if row.tipo_documento == tipo]
        if not selected:
            continue
        qtd = len(selected)
        total = sum((decimal(row.valor_total) for row in selected), Decimal("0"))
        current = totals.setdefault(tipo, {"quantidade": 0, "total": Decimal("0")})
        current["quantidade"] += qtd
        current["total"] += decimal(total)
    return [{"tipo_documento": tipo, **values} for tipo, values in totals.items()]


@router.get("/faturamento")
def faturamento_periodico(
    ano: int | None = None,
    mes: int | None = Query(default=None, ge=1, le=12),
    tipo_documento: str | None = Query(
        default=None, pattern="^(NOTA_FISCAL|RECIBO)?$"
    ),
    db: Session = Depends(get_db),
    _=Depends(require_permission("pode_ver_faturamento")),
):
    """Faturamento mensal e anual de vendas manuais e importadas."""
    rows = [
        (sale.data_venda, sale.tipo_documento, decimal(sale.valor_total))
        for sale in db.query(models.Venda).all()
    ]
    rows.extend(
        (sale.data_venda, sale.tipo_documento, decimal(sale.valor_total))
        for sale in _imported_sales(db).all()
    )
    if ano:
        rows = [row for row in rows if row[0].year == ano]
    if mes:
        rows = [row for row in rows if row[0].month == mes]
    if tipo_documento:
        rows = [row for row in rows if row[1] == tipo_documento]

    def empty_period():
        return {"nota_fiscal": Decimal("0"), "recibo": Decimal("0"), "total": Decimal("0")}

    monthly, yearly = {}, {}
    totals = empty_period()
    for sale_date, document_type, value in rows:
        month_key = (sale_date.year, sale_date.month)
        year_key = sale_date.year
        month_values = monthly.setdefault(month_key, empty_period())
        year_values = yearly.setdefault(year_key, empty_period())
        field = "nota_fiscal" if document_type == "NOTA_FISCAL" else "recibo"
        for target in (totals, month_values, year_values):
            target[field] += value
            target["total"] += value
    return {
        **totals,
        "registros": len(rows),
        "mensal": [
            {"ano": year, "mes": month, **values}
            for (year, month), values in sorted(monthly.items(), reverse=True)
        ],
        "anual": [
            {"ano": year, **values}
            for year, values in sorted(yearly.items(), reverse=True)
        ],
    }


@router.get("/produtos")
def produtos(db: Session = Depends(get_db), _=Depends(current_user)):
    return [{
        "codigo": p.codigo, "nome": p.nome, "tipo_item": p.tipo_item,
        "familia": p.familia, "quantidade": p.quantidade_atual,
        "estoque_minimo": p.estoque_minimo,
    } for p in db.query(models.Produto).order_by(models.Produto.tipo_item, models.Produto.nome)]


@router.get("/clientes")
def clientes(db: Session = Depends(get_db), _=Depends(require_permission("pode_ver_faturamento"))):
    vendas = dict(db.query(models.Venda.cliente_id, func.sum(models.Venda.valor_total)).group_by(models.Venda.cliente_id).all())
    return [{"id": c.id, "nome": c.nome, "documento": c.documento, "total_vendas": vendas.get(c.id, 0)} for c in db.query(models.Cliente).all()]


@router.get("/custos")
def custos(db: Session = Depends(get_db), _=Depends(require_permission("pode_alterar_custos"))):
    return [{
        "codigo": p.codigo, "nome": p.nome, "tipo_item": p.tipo_item,
        "preco_custo": p.preco_custo, "preco_venda": p.preco_venda,
        "valor_em_estoque": decimal(p.preco_custo) * decimal(p.quantidade_atual),
    } for p in db.query(models.Produto).order_by(models.Produto.nome)]
