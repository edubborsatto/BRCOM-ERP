from datetime import datetime
from decimal import Decimal
from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.database import get_db
from app.dependencies import current_user, require_permission
from app.inventory import decimal, record_movement

router = APIRouter(prefix="/ordens-servico", tags=["Ordens de serviço"])


def _query(db: Session):
    return db.query(models.OrdemServico).options(
        joinedload(models.OrdemServico.cliente),
        joinedload(models.OrdemServico.orcamento)
        .joinedload(models.Orcamento.itens)
        .joinedload(models.OrcamentoItem.produto)
        .joinedload(models.Produto.formula)
        .joinedload(models.FormulaProduto.componentes)
        .joinedload(models.FormulaComponente.materia_prima),
    )


@router.get("/", response_model=list[schemas.OrdemServicoResponse])
def listar(db: Session = Depends(get_db), _=Depends(current_user)):
    return _query(db).order_by(models.OrdemServico.id.desc()).all()


@router.post("/{ordem_id}/concluir", response_model=schemas.OrdemServicoResponse)
def concluir(
    ordem_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_permission("pode_movimentar_estoque")),
):
    ordem = _query(db).filter(models.OrdemServico.id == ordem_id).first()
    if not ordem:
        raise HTTPException(status_code=404, detail="Ordem de serviço não encontrada")
    if ordem.status != "ABERTA":
        raise HTTPException(status_code=409, detail="Ordem de serviço já processada")

    consumos: dict[int, tuple[models.Produto, Decimal]] = {}
    for item in ordem.orcamento.itens:
        formula = item.produto.formula
        if not formula:
            raise HTTPException(status_code=409, detail=f"{item.produto.nome} está sem fórmula")
        for componente in formula.componentes:
            perda = decimal(componente.perda_percentual) / Decimal("100")
            necessario = decimal(item.quantidade) * decimal(componente.quantidade) * (1 + perda)
            atual = consumos.get(componente.materia_prima_id, (componente.materia_prima, Decimal("0")))[1]
            consumos[componente.materia_prima_id] = (componente.materia_prima, atual + necessario)
    faltas = [
        f"{produto.nome}: precisa {qtd}, disponível {produto.quantidade_atual}"
        for produto, qtd in consumos.values()
        if decimal(produto.quantidade_atual) < qtd
    ]
    if faltas:
        raise HTTPException(status_code=409, detail="Estoque insuficiente: " + "; ".join(faltas))

    for produto, quantidade in consumos.values():
        record_movement(
            db, produto, "CONSUMO_PRODUCAO", quantidade, usuario,
            f"Consumo automático da {ordem.numero}", ordem.numero,
        )
    for item in ordem.orcamento.itens:
        record_movement(
            db, item.produto, "ENTRADA", decimal(item.quantidade), usuario,
            f"Produção concluída na {ordem.numero}", ordem.numero,
        )
    ordem.status = "CONCLUIDA"
    ordem.concluida_em = datetime.now()
    db.commit()
    return ordem


@router.get("/{ordem_id}/imprimir", response_class=HTMLResponse)
def imprimir(ordem_id: int, db: Session = Depends(get_db), _=Depends(current_user)):
    ordem = _query(db).filter(models.OrdemServico.id == ordem_id).first()
    if not ordem:
        raise HTTPException(status_code=404, detail="Ordem de serviço não encontrada")
    limite = ordem.data_limite.strftime("%d/%m/%Y") if ordem.data_limite else "Não informada"
    itens = "".join(
        f"<li>{item.quantidade} {escape(item.produto.unidade_medida)} — {escape(item.produto.nome)}</li>"
        for item in ordem.orcamento.itens
    )
    return HTMLResponse(f"""<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>
    <meta name='viewport' content='width=device-width'><title>{ordem.numero}</title><style>
    @page {{ size: A5 portrait; margin: 10mm; }} body {{ font: 14px Arial; color:#111; }}
    header {{ border-bottom:2px solid #059669; margin-bottom:16px; }} h1 {{ margin:0 0 6px; }}
    .box {{ border:1px solid #bbb; border-radius:6px; padding:10px; margin:10px 0; }}
    button {{ padding:10px 16px; background:#059669; color:white; border:0; border-radius:5px; }}
    @media print {{ button {{ display:none; }} }} </style></head><body>
    <header><h1>BRCom ERP — Ordem de Serviço</h1><strong>{ordem.numero}</strong></header>
    <div class='box'><b>Cliente:</b> {escape(ordem.cliente.nome)}<br><b>Emissão:</b> {ordem.data_emissao.strftime('%d/%m/%Y')}<br>
    <b>Data limite:</b> {limite}<br><b>Status:</b> {ordem.status}</div>
    <div class='box'><b>Atividade:</b><p>{escape(ordem.atividade)}</p><b>Itens:</b><ul>{itens}</ul></div>
    <p>Responsável: ______________________________</p><p>Conclusão: ____/____/________</p>
    <button onclick='window.print()'>Imprimir A5</button></body></html>""")
