from datetime import datetime
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.database import get_db
from app.dependencies import current_user, require_permission
from app.inventory import decimal, record_movement

router = APIRouter(prefix="/pedidos", tags=["Pedidos futuros"])


def _query(db: Session):
    return db.query(models.PedidoFuturo).options(
        joinedload(models.PedidoFuturo.itens)
        .joinedload(models.PedidoFuturoItem.materias_primas)
    )


def _pedido(db: Session, pedido_id: int) -> models.PedidoFuturo:
    pedido = _query(db).filter(models.PedidoFuturo.id == pedido_id).first()
    if not pedido:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    return pedido


def _proxima_posicao(db: Session) -> int:
    atual = db.query(func.max(models.PedidoFuturo.fila_posicao)).scalar() or 0
    return int(atual) + 1


def _resumo(itens: list[schemas.PedidoItemCreate]) -> tuple[str, Decimal]:
    nomes = []
    total = Decimal("0")
    for item in itens:
        produto = item.produto_id
        nomes.append(str(produto))
        total += item.quantidade_total
    return f"{len(nomes)} produto(s)", total


def _reservar_itens(
    db: Session,
    pedido: models.PedidoFuturo,
    itens: list[schemas.PedidoItemCreate],
    usuario: models.Usuario,
) -> None:
    produtos_ids = [item.produto_id for item in itens]
    if len(produtos_ids) != len(set(produtos_ids)):
        raise HTTPException(status_code=422, detail="Cada produto deve aparecer uma única vez no pedido")
    produtos = {
        produto.id: produto
        for produto in db.query(models.Produto)
        .filter(models.Produto.id.in_(produtos_ids)).with_for_update().all()
    }
    if len(produtos) != len(produtos_ids):
        raise HTTPException(status_code=404, detail="Um dos produtos do pedido não foi encontrado")
    if any(produto.tipo_item != "PRODUTO_ACABADO" for produto in produtos.values()):
        raise HTTPException(status_code=422, detail="O pedido aceita somente produtos prontos")

    materia_ids = [
        materia.materia_prima_id
        for item in itens
        for materia in item.materias_primas
    ]
    materias = {
        produto.id: produto
        for produto in db.query(models.Produto)
        .filter(models.Produto.id.in_(materia_ids)).with_for_update().all()
    } if materia_ids else {}
    if len(materias) != len(set(materia_ids)):
        raise HTTPException(status_code=404, detail="Uma das matérias-primas não foi encontrada")
    if any(produto.tipo_item != "MATERIA_PRIMA" for produto in materias.values()):
        raise HTTPException(status_code=422, detail="Selecione apenas itens cadastrados como matéria-prima")

    referencia = f"PEDIDO-{pedido.id}"
    for dados in itens:
        produto = produtos[dados.produto_id]
        item = models.PedidoFuturoItem(
            pedido=pedido,
            produto_id=produto.id,
            produto_nome=produto.nome,
            quantidade_total=dados.quantidade_total,
            quantidade_estoque=dados.quantidade_estoque,
            quantidade_fabricar=dados.quantidade_fabricar,
        )
        db.add(item)
        if dados.quantidade_estoque:
            record_movement(
                db, produto, "SAIDA", dados.quantidade_estoque, usuario,
                f"Reserva de produto pronto para o pedido #{pedido.id}", referencia,
            )
        vistos = set()
        for material in dados.materias_primas:
            if material.materia_prima_id in vistos:
                raise HTTPException(
                    status_code=422,
                    detail=f"Matéria-prima repetida no produto {produto.nome}",
                )
            vistos.add(material.materia_prima_id)
            materia = materias[material.materia_prima_id]
            record_movement(
                db, materia, "CONSUMO_PRODUCAO", material.quantidade, usuario,
                f"Reserva para fabricar {produto.nome} no pedido #{pedido.id}", referencia,
            )
            db.add(models.PedidoFuturoMateriaPrima(
                item=item,
                materia_prima_id=materia.id,
                materia_prima_nome=materia.nome,
                quantidade_reservada=material.quantidade,
            ))
    primeiro = produtos[itens[0].produto_id]
    pedido.produto_nome = primeiro.nome if len(itens) == 1 else f"{len(itens)} produtos"
    pedido.quantidade = sum((item.quantidade_total for item in itens), Decimal("0"))


def _devolver_reservas(
    db: Session,
    pedido: models.PedidoFuturo,
    usuario: models.Usuario,
    motivo: str,
) -> None:
    referencia = f"PEDIDO-{pedido.id}"
    for item in pedido.itens:
        produto = db.get(models.Produto, item.produto_id)
        if produto and decimal(item.quantidade_estoque) > 0:
            record_movement(
                db, produto, "ENTRADA", item.quantidade_estoque, usuario,
                f"{motivo}: produto pronto do pedido #{pedido.id}", referencia,
            )
        for reserva in item.materias_primas:
            materia = db.get(models.Produto, reserva.materia_prima_id)
            if materia:
                record_movement(
                    db, materia, "ENTRADA", reserva.quantidade_reservada, usuario,
                    f"{motivo}: matéria-prima do pedido #{pedido.id}", referencia,
                )


@router.post("/", response_model=schemas.PedidoFuturoResponse, status_code=201)
def criar_pedido(
    dados: schemas.PedidoFuturoCreate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_permission("pode_criar_orcamentos")),
):
    if dados.itens:
        produto_nome, quantidade = _resumo(dados.itens)
    else:
        produto_nome, quantidade = dados.produto_nome, dados.quantidade
    novo = models.PedidoFuturo(
        cliente_nome=dados.cliente_nome.strip(),
        produto_nome=produto_nome,
        quantidade=quantidade,
        data_entrega=dados.data_entrega,
        status="Pendente",
        fila_posicao=_proxima_posicao(db),
        prioridade=dados.prioridade,
    )
    try:
        db.add(novo)
        db.flush()
        if dados.itens:
            _reservar_itens(db, novo, dados.itens, usuario)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _pedido(db, novo.id)


@router.get("/", response_model=List[schemas.PedidoFuturoResponse])
def listar_pedidos(db: Session = Depends(get_db), _=Depends(current_user)):
    return _query(db).order_by(
        models.PedidoFuturo.cancelado_em.is_not(None),
        models.PedidoFuturo.fila_posicao.asc(),
        models.PedidoFuturo.data_entrega.asc(),
    ).all()


@router.put("/fila", response_model=List[schemas.PedidoFuturoResponse])
def reordenar_fila(
    dados: schemas.ReordenarFilaPedidos,
    db: Session = Depends(get_db),
    _=Depends(require_permission("pode_criar_orcamentos")),
):
    ativos = db.query(models.PedidoFuturo).filter(
        models.PedidoFuturo.cancelado_em.is_(None),
        models.PedidoFuturo.confirmado_em.is_(None),
    ).all()
    ativos_ids = {pedido.id for pedido in ativos}
    if set(dados.pedidos_ids) != ativos_ids:
        raise HTTPException(
            status_code=409,
            detail="A fila mudou. Atualize a página antes de reorganizar novamente",
        )
    for posicao, pedido_id in enumerate(dados.pedidos_ids, start=1):
        next(p for p in ativos if p.id == pedido_id).fila_posicao = posicao
    db.commit()
    return listar_pedidos(db, _)


@router.put("/{pedido_id}", response_model=schemas.PedidoFuturoResponse)
def atualizar_pedido(
    pedido_id: int,
    dados: schemas.PedidoFuturoCreate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_permission("pode_criar_orcamentos")),
):
    pedido = _pedido(db, pedido_id)
    if pedido.confirmado_em or pedido.cancelado_em:
        raise HTTPException(status_code=409, detail="Pedido confirmado ou cancelado não pode ser editado")
    try:
        _devolver_reservas(db, pedido, usuario, "Revisão do pedido")
        pedido.itens.clear()
        db.flush()
        pedido.cliente_nome = dados.cliente_nome.strip()
        pedido.data_entrega = dados.data_entrega
        pedido.prioridade = dados.prioridade
        if dados.itens:
            _reservar_itens(db, pedido, dados.itens, usuario)
        else:
            pedido.produto_nome = dados.produto_nome
            pedido.quantidade = dados.quantidade
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _pedido(db, pedido_id)


@router.post("/{pedido_id}/prioridade", response_model=schemas.PedidoFuturoResponse)
def alternar_prioridade(
    pedido_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission("pode_criar_orcamentos")),
):
    pedido = _pedido(db, pedido_id)
    if pedido.confirmado_em or pedido.cancelado_em:
        raise HTTPException(status_code=409, detail="Pedido fora da fila ativa")
    pedido.prioridade = not pedido.prioridade
    db.commit()
    return _pedido(db, pedido_id)


@router.post("/{pedido_id}/confirmar-venda", response_model=schemas.PedidoFuturoResponse)
def confirmar_venda(
    pedido_id: int,
    dados: schemas.ConfirmacaoVendaPedido,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_permission("pode_registrar_vendas")),
):
    pedido = _pedido(db, pedido_id)
    if pedido.confirmado_em:
        raise HTTPException(status_code=409, detail="Venda deste pedido já foi confirmada")
    if pedido.cancelado_em:
        raise HTTPException(status_code=409, detail="Pedido cancelado não pode ser confirmado")
    duplicado = db.query(models.PedidoFuturo).filter(
        models.PedidoFuturo.id != pedido_id,
        models.PedidoFuturo.tipo_documento == dados.tipo_documento,
        models.PedidoFuturo.numero_documento == dados.numero_documento,
    ).first()
    if duplicado:
        raise HTTPException(status_code=409, detail="Número de documento já usado neste tipo")
    pedido.tipo_documento = dados.tipo_documento
    pedido.numero_documento = dados.numero_documento
    pedido.status = "Venda confirmada"
    pedido.confirmado_em = datetime.now()
    pedido.confirmado_por_id = usuario.id
    pedido.confirmado_por_nome = usuario.nome
    db.commit()
    return _pedido(db, pedido_id)


@router.delete("/{pedido_id}", response_model=schemas.PedidoFuturoResponse)
def cancelar_pedido(
    pedido_id: int,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_permission("pode_criar_orcamentos")),
):
    pedido = _pedido(db, pedido_id)
    if pedido.confirmado_em:
        raise HTTPException(status_code=409, detail="Venda confirmada não pode ser cancelada por esta tela")
    if pedido.cancelado_em:
        raise HTTPException(status_code=409, detail="Pedido já cancelado")
    try:
        _devolver_reservas(db, pedido, usuario, "Cancelamento")
        pedido.status = "Cancelado"
        pedido.cancelado_em = datetime.now()
        pedido.cancelado_por_id = usuario.id
        pedido.cancelado_por_nome = usuario.nome
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _pedido(db, pedido_id)
