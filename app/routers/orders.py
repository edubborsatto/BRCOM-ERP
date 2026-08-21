from datetime import date, datetime
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.database import get_db
from app.dependencies import confirm_critical_action, current_user, require_admin, require_permission
from app.inventory import decimal, record_movement
from app.services import audit

router = APIRouter(prefix="/pedidos", tags=["Pedidos futuros"])


def _query(db: Session):
    return db.query(models.PedidoFuturo).options(
        joinedload(models.PedidoFuturo.itens).joinedload(models.PedidoFuturoItem.produto),
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
    cliente = db.get(models.Cliente, dados.cliente_id) if dados.cliente_id else None
    if dados.cliente_id and not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    if dados.itens:
        produto_nome, quantidade = _resumo(dados.itens)
    else:
        produto_nome, quantidade = dados.produto_nome, dados.quantidade
    novo = models.PedidoFuturo(
        cliente_id=cliente.id if cliente else None,
        cliente_nome=cliente.nome if cliente else dados.cliente_nome.strip(),
        produto_nome=produto_nome,
        quantidade=quantidade,
        data_entrega=dados.data_entrega,
        status="PENDENTE",
        fila_posicao=_proxima_posicao(db),
        prioridade=dados.prioridade,
        observacoes=dados.observacoes,
    )
    try:
        db.add(novo)
        db.flush()
        if dados.itens:
            _reservar_itens(db, novo, dados.itens, usuario)
        audit(db, usuario, "PEDIDOS", "CRIAR", "pedidos_futuros", novo.id, after={"cliente_id": novo.cliente_id, "status": novo.status})
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
    usuario=Depends(require_permission("pode_criar_orcamentos")),
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
    audit(db, usuario, "PEDIDOS", "REORDENAR_FILA", "pedidos_futuros", after={"pedidos_ids": dados.pedidos_ids})
    db.commit()
    return _query(db).order_by(
        models.PedidoFuturo.cancelado_em.is_not(None),
        models.PedidoFuturo.fila_posicao.asc(),
        models.PedidoFuturo.data_entrega.asc(),
    ).all()


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
        cliente = db.get(models.Cliente, dados.cliente_id) if dados.cliente_id else None
        if dados.cliente_id and not cliente:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
        anterior = {"cliente_id": pedido.cliente_id, "status": pedido.status, "data_entrega": pedido.data_entrega}
        pedido.cliente_id = cliente.id if cliente else None
        pedido.cliente_nome = cliente.nome if cliente else dados.cliente_nome.strip()
        pedido.data_entrega = dados.data_entrega
        pedido.prioridade = dados.prioridade
        pedido.observacoes = dados.observacoes
        if dados.itens:
            _reservar_itens(db, pedido, dados.itens, usuario)
        else:
            pedido.produto_nome = dados.produto_nome
            pedido.quantidade = dados.quantidade
        audit(db, usuario, "PEDIDOS", "EDITAR", "pedidos_futuros", pedido.id, before=anterior, after={"cliente_id": pedido.cliente_id, "data_entrega": pedido.data_entrega})
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _pedido(db, pedido_id)


@router.post("/{pedido_id}/prioridade", response_model=schemas.PedidoFuturoResponse)
def alternar_prioridade(
    pedido_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(require_permission("pode_criar_orcamentos")),
):
    pedido = _pedido(db, pedido_id)
    if pedido.confirmado_em or pedido.cancelado_em:
        raise HTTPException(status_code=409, detail="Pedido fora da fila ativa")
    pedido.prioridade = not pedido.prioridade
    audit(db, usuario, "PEDIDOS", "ALTERAR_PRIORIDADE", "pedidos_futuros", pedido.id, after={"prioridade": pedido.prioridade})
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
    if pedido.status != "PRONTO":
        raise HTTPException(status_code=409, detail="Somente pedido PRONTO pode virar venda")
    if not pedido.cliente_id:
        raise HTTPException(status_code=409, detail="Relacione o pedido a um cliente cadastrado antes da venda")
    duplicado = db.query(models.Venda).filter(models.Venda.tipo_documento == dados.tipo_documento, models.Venda.numero_documento == dados.numero_documento, models.Venda.status == "ATIVA").first()
    if duplicado:
        raise HTTPException(status_code=409, detail="Número de documento já usado neste tipo")
    pedido.tipo_documento = dados.tipo_documento
    pedido.numero_documento = dados.numero_documento
    pedido.modalidade_entrega = dados.modalidade_entrega
    valor = sum((decimal(i.quantidade_total) * decimal(i.produto.preco_venda) for i in pedido.itens), Decimal("0"))
    if valor <= 0:
        raise HTTPException(status_code=409, detail="Os produtos do pedido precisam ter preço de venda")
    venda = models.Venda(
        numero=f"VEN-{date.today().year}-{db.query(models.Venda).count() + 1:05d}",
        cliente_id=pedido.cliente_id, pedido_futuro_id=pedido.id,
        orcamento_id=pedido.orcamento_id, ordem_servico_id=pedido.ordem_servico_id,
        tipo_documento=dados.tipo_documento, numero_documento=dados.numero_documento,
        valor_total=valor, data_venda=date.today(), status="ATIVA",
        observacoes=f"Venda originada do pedido #{pedido.id}",
    )
    db.add(venda)
    db.flush()
    pedido.venda_id = venda.id
    # A emissão do documento cria a venda, mas entrega/retirada continua sendo
    # uma etapa operacional explícita e auditável.
    pedido.status = "PRONTO"
    pedido.confirmado_em = datetime.now()
    pedido.confirmado_por_id = usuario.id
    pedido.confirmado_por_nome = usuario.nome
    audit(db, usuario, "VENDAS", "CRIAR_DE_PEDIDO", "vendas", venda.id, after={"pedido_id": pedido.id, "valor_total": valor, "documento": dados.numero_documento, "modalidade_entrega": dados.modalidade_entrega})
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
        status_anterior = pedido.status
        pedido.status = "Cancelado"
        pedido.cancelado_em = datetime.now()
        pedido.cancelado_por_id = usuario.id
        pedido.cancelado_por_nome = usuario.nome
        audit(db, usuario, "PEDIDOS", "CANCELAR", "pedidos_futuros", pedido.id, before={"status": status_anterior}, after={"status": "Cancelado"})
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _pedido(db, pedido_id)


@router.post("/{pedido_id}/excluir-definitivamente")
def excluir_pedido_definitivamente(
    pedido_id: int,
    dados: schemas.ConfirmacaoCritica,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_admin),
):
    confirm_critical_action(usuario, dados.senha)
    pedido = _pedido(db, pedido_id)
    try:
        if not pedido.cancelado_em:
            _devolver_reservas(db, pedido, usuario, "Exclusão definitiva")
        vendas = db.query(models.Venda).filter(
            (models.Venda.pedido_futuro_id == pedido.id) | (models.Venda.id == pedido.venda_id)
        ).all()
        for venda in vendas:
            audit(db, usuario, "VENDAS", "EXCLUIR_COM_PEDIDO", "vendas", venda.id,
                  before={"numero": venda.numero, "valor_total": venda.valor_total},
                  after={"motivo": dados.motivo})
            db.delete(venda)
        audit(db, usuario, "PEDIDOS", "EXCLUIR_DEFINITIVAMENTE", "pedidos_futuros", pedido.id,
              before={"cliente_id": pedido.cliente_id, "status": pedido.status,
                      "data_entrega": pedido.data_entrega}, after={"motivo": dados.motivo})
        db.delete(pedido)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"status": "success"}


STATUS_TRANSITIONS = {
    "PENDENTE": {"AGUARDANDO_PRODUCAO"},
    "AGUARDANDO_PRODUCAO": {"EM_PRODUCAO"},
    "EM_PRODUCAO": {"PRODUCAO_CONCLUIDA"},
    "PRODUCAO_CONCLUIDA": {"SEPARADO"},
    "SEPARADO": {"PRONTO"},
    "PRONTO": {"ENTREGUE", "RETIRADO"},
}
STATUS_PERMISSION = {
    "EM_PRODUCAO": "pode_iniciar_producao",
    "PRODUCAO_CONCLUIDA": "pode_concluir_producao",
    "SEPARADO": "pode_separar_pedido",
    "PRONTO": "pode_marcar_pronto",
    "ENTREGUE": "pode_concluir_tarefa", "RETIRADO": "pode_concluir_tarefa",
}


@router.post("/{pedido_id}/status", response_model=schemas.PedidoFuturoResponse)
def alterar_status(pedido_id: int, dados: schemas.AlteracaoStatusPedido,
                   db: Session = Depends(get_db), usuario: models.Usuario = Depends(current_user)):
    pedido = _pedido(db, pedido_id)
    atual = pedido.status.upper().replace(" ", "_")
    if dados.status not in STATUS_TRANSITIONS.get(atual, set()):
        raise HTTPException(status_code=409, detail=f"Transição inválida: {atual} → {dados.status}")
    if atual == "PRONTO" and dados.status in {"ENTREGUE", "RETIRADO"}:
        if not pedido.venda_id:
            raise HTTPException(status_code=409, detail="Confirme a venda antes de concluir a entrega ou retirada")
        esperado = "ENTREGUE" if pedido.modalidade_entrega == "ENTREGA" else "RETIRADO"
        if dados.status != esperado:
            raise HTTPException(status_code=409, detail=f"Este pedido está programado para {pedido.modalidade_entrega.lower()}")
    permissao = STATUS_PERMISSION.get(dados.status)
    if usuario.tipo_usuario != "DESENVOLVEDOR" and permissao and not getattr(usuario, permissao, False):
        raise HTTPException(status_code=403, detail="Sem permissão para executar esta etapa")
    pedido.status = dados.status
    if dados.observacao:
        pedido.observacoes = (pedido.observacoes + "\n" if pedido.observacoes else "") + dados.observacao
    audit(db, usuario, "PEDIDOS", "ALTERAR_STATUS", "pedidos_futuros", pedido.id, before={"status": atual}, after={"status": dados.status, "observacao": dados.observacao})
    db.commit()
    return _pedido(db, pedido.id)


@router.post("/{pedido_id}/observacao", response_model=schemas.PedidoFuturoResponse)
def registrar_observacao(pedido_id: int, dados: schemas.RegistroOperacionalPedido,
                         db: Session = Depends(get_db), usuario: models.Usuario = Depends(current_user)):
    if usuario.tipo_usuario != "DESENVOLVEDOR" and not usuario.pode_colocar_observacao:
        raise HTTPException(status_code=403, detail="Sem permissão para registrar observação")
    pedido = _pedido(db, pedido_id)
    pedido.observacoes = (pedido.observacoes + "\n" if pedido.observacoes else "") + dados.texto
    audit(db, usuario, "PEDIDOS", "ADICIONAR_OBSERVACAO", "pedidos_futuros", pedido.id, after={"texto": dados.texto})
    db.commit()
    return _pedido(db, pedido.id)


@router.post("/{pedido_id}/falta-material", response_model=schemas.PedidoFuturoResponse)
def informar_falta_material(pedido_id: int, dados: schemas.RegistroOperacionalPedido,
                            db: Session = Depends(get_db), usuario: models.Usuario = Depends(current_user)):
    if usuario.tipo_usuario != "DESENVOLVEDOR" and not usuario.pode_informar_falta_material:
        raise HTTPException(status_code=403, detail="Sem permissão para informar falta de material")
    pedido = _pedido(db, pedido_id)
    texto = f"FALTA DE MATERIAL: {dados.texto}"
    pedido.observacoes = (pedido.observacoes + "\n" if pedido.observacoes else "") + texto
    audit(db, usuario, "PEDIDOS", "FALTA_MATERIAL", "pedidos_futuros", pedido.id, after={"texto": dados.texto})
    db.commit()
    return _pedido(db, pedido.id)
