from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import confirm_critical_action, current_user, require_admin, require_permission
from app.inventory import record_movement
from app.services import audit

router = APIRouter(prefix="/clientes", tags=["Clientes"])


@router.post("/", response_model=schemas.ClienteResponse, status_code=201)
def criar_cliente(cliente: schemas.ClienteCreate, db: Session = Depends(get_db), usuario=Depends(require_permission("pode_gerenciar_clientes"))):
    if cliente.documento and db.query(models.Cliente).filter(models.Cliente.documento == cliente.documento).first():
        raise HTTPException(status_code=400, detail="Documento já cadastrado")
    novo = models.Cliente(**cliente.model_dump())
    db.add(novo)
    db.flush()
    audit(db, usuario, "CLIENTES", "CRIAR", "clientes", novo.id, after=cliente.model_dump())
    db.commit()
    db.refresh(novo)
    return novo


@router.get("/", response_model=List[schemas.ClienteResponse])
def listar_clientes(db: Session = Depends(get_db), _=Depends(current_user)):
    return db.query(models.Cliente).all()


@router.put("/{cliente_id}", response_model=schemas.ClienteResponse)
def atualizar_cliente(cliente_id: int, dados: schemas.ClienteCreate, db: Session = Depends(get_db), usuario=Depends(require_permission("pode_gerenciar_clientes"))):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    before = {"nome": cliente.nome, "documento": cliente.documento, "telefone": cliente.telefone, "email": cliente.email}
    for key, value in dados.model_dump().items():
        setattr(cliente, key, value)
    audit(db, usuario, "CLIENTES", "EDITAR", "clientes", cliente.id, before=before, after=dados.model_dump())
    db.commit()
    db.refresh(cliente)
    return cliente


@router.delete("/{cliente_id}")
def excluir_cliente(cliente_id: int, db: Session = Depends(get_db), usuario=Depends(require_admin)):
    cliente = db.query(models.Cliente).filter(models.Cliente.id == cliente_id).first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    if db.query(models.PedidoFuturo).filter(models.PedidoFuturo.cliente_id == cliente_id).first() or db.query(models.Venda).filter(models.Venda.cliente_id == cliente_id).first():
        raise HTTPException(status_code=409, detail="Cliente possui histórico e não pode ser excluído")
    audit(db, usuario, "CLIENTES", "EXCLUIR", "clientes", cliente.id, before={"nome": cliente.nome, "documento": cliente.documento})
    db.delete(cliente)
    db.commit()
    return {"status": "success"}


@router.post("/{cliente_id}/excluir-definitivamente")
def excluir_cliente_com_historico(
    cliente_id: int,
    dados: schemas.ConfirmacaoCritica,
    db: Session = Depends(get_db),
    usuario=Depends(require_admin),
):
    """Remove um cadastro criado por engano e desfaz sua cadeia operacional."""
    from app.routers.orders import _devolver_reservas, _query as order_query

    confirm_critical_action(usuario, dados.senha)
    cliente = db.get(models.Cliente, cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    pedidos = order_query(db).filter(models.PedidoFuturo.cliente_id == cliente_id).all()
    ordens = db.query(models.OrdemServico).filter(models.OrdemServico.cliente_id == cliente_id).all()
    vendas = db.query(models.Venda).filter(models.Venda.cliente_id == cliente_id).all()
    orcamentos = db.query(models.Orcamento).filter(models.Orcamento.cliente_id == cliente_id).all()
    try:
        for pedido in pedidos:
            if not pedido.cancelado_em:
                _devolver_reservas(db, pedido, usuario, "Exclusão definitiva do cliente")
            pedido.venda_id = None
        for venda in vendas:
            venda.pedido_futuro_id = None
        db.flush()
        for venda in vendas:
            audit(db, usuario, "VENDAS", "EXCLUIR_COM_CLIENTE", "vendas", venda.id,
                  before={"numero": venda.numero, "valor_total": venda.valor_total}, after={"motivo": dados.motivo})
            db.delete(venda)
        for pedido in pedidos:
            audit(db, usuario, "PEDIDOS", "EXCLUIR_COM_CLIENTE", "pedidos_futuros", pedido.id,
                  before={"status": pedido.status}, after={"motivo": dados.motivo})
            db.delete(pedido)
        for ordem in ordens:
            movimentos = db.query(models.HistoricoEstoque).filter(
                models.HistoricoEstoque.referencia == ordem.numero,
                models.HistoricoEstoque.produto_id.is_not(None),
            ).order_by(models.HistoricoEstoque.id.desc()).all()
            for mov in movimentos:
                produto = db.get(models.Produto, mov.produto_id)
                if produto:
                    inverso = "ENTRADA" if mov.tipo_movimentacao in {"SAIDA", "PERDA", "CONSUMO_PRODUCAO"} else "SAIDA"
                    record_movement(db, produto, inverso, mov.quantidade, usuario,
                                    f"Estorno pela exclusão da {ordem.numero}", f"EXCLUSAO-{ordem.numero}")
            audit(db, usuario, "ORDENS_SERVICO", "EXCLUIR_COM_CLIENTE", "ordens_servico", ordem.id,
                  before={"numero": ordem.numero, "status": ordem.status}, after={"motivo": dados.motivo})
            db.delete(ordem)
        db.flush()
        for orcamento in orcamentos:
            audit(db, usuario, "ORCAMENTOS", "EXCLUIR_COM_CLIENTE", "orcamentos", orcamento.id,
                  before={"numero": orcamento.numero, "status": orcamento.status}, after={"motivo": dados.motivo})
            db.delete(orcamento)
        audit(db, usuario, "CLIENTES", "EXCLUIR_DEFINITIVAMENTE", "clientes", cliente.id,
              before={"nome": cliente.nome, "documento": cliente.documento,
                      "pedidos": len(pedidos), "vendas": len(vendas), "ordens": len(ordens),
                      "orcamentos": len(orcamentos)}, after={"motivo": dados.motivo})
        db.delete(cliente)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {"status": "success"}
