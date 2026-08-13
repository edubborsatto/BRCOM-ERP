from datetime import date, datetime, time, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import require_permission
from app.services import audit

router = APIRouter(prefix="/agenda", tags=["Agenda"])
agenda_access = require_permission("pode_acessar_agenda")


@router.post("/", response_model=schemas.CompromissoResponse, status_code=201)
def criar_compromisso(comp: schemas.CompromissoCreate, db: Session = Depends(get_db), usuario=Depends(agenda_access)):
    novo = models.Compromisso(**comp.model_dump(), criado_por_id=usuario.id)
    db.add(novo)
    db.flush()
    audit(db, usuario, "AGENDA", "CRIAR", "agenda", novo.id, after=comp.model_dump())
    db.commit()
    db.refresh(novo)
    return novo


@router.get("/", response_model=List[schemas.CompromissoResponse])
def listar_compromissos(db: Session = Depends(get_db), _=Depends(agenda_access)):
    return db.query(models.Compromisso).order_by(models.Compromisso.data_hora.asc()).all()


@router.get("/eventos")
def eventos(data_inicial: date | None = None, data_final: date | None = None,
            db: Session = Depends(get_db), _=Depends(agenda_access)):
    inicio = datetime.combine(data_inicial, time.min) if data_inicial else datetime.min
    fim = datetime.combine(data_final + timedelta(days=1), time.min) if data_final else datetime.max
    result = [{"origem": "AGENDA", "id": c.id, "titulo": c.titulo, "data_hora": c.data_hora, "status": None, "detalhes": c.descricao}
              for c in db.query(models.Compromisso).filter(models.Compromisso.data_hora >= inicio, models.Compromisso.data_hora < fim)]
    pedidos = db.query(models.PedidoFuturo).filter(models.PedidoFuturo.cancelado_em.is_(None), models.PedidoFuturo.data_entrega >= inicio, models.PedidoFuturo.data_entrega < fim)
    result += [{"origem": "PEDIDO", "tipo": p.modalidade_entrega if p.venda_id and p.modalidade_entrega else "PEDIDO", "id": p.id, "titulo": f"{('Entrega' if p.modalidade_entrega == 'ENTREGA' else 'Retirada') if p.venda_id else 'Pedido'} #{p.id} — {p.cliente_nome}", "data_hora": p.data_entrega, "status": p.status, "detalhes": f"{p.produto_nome} · {p.quantidade}"}
               for p in pedidos]
    result += [{"origem": "OS", "tipo": "OS", "id": o.id, "titulo": f"{o.numero} — {o.cliente.nome}", "data_hora": datetime.combine(o.data_limite, time.min), "status": o.status, "detalhes": o.atividade}
               for o in db.query(models.OrdemServico).filter(models.OrdemServico.data_limite.is_not(None), models.OrdemServico.data_limite >= inicio.date(), models.OrdemServico.data_limite <= (fim - timedelta(days=1)).date())]
    return sorted(result, key=lambda row: row["data_hora"])


@router.put("/{comp_id}", response_model=schemas.CompromissoResponse)
def atualizar_compromisso(comp_id: int, dados: schemas.CompromissoCreate, db: Session = Depends(get_db), usuario=Depends(agenda_access)):
    comp = db.query(models.Compromisso).filter(models.Compromisso.id == comp_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Compromisso não encontrado")
    before = {"titulo": comp.titulo, "descricao": comp.descricao, "data_hora": comp.data_hora, "local": comp.local}
    for key, value in dados.model_dump().items():
        setattr(comp, key, value)
    audit(db, usuario, "AGENDA", "EDITAR", "agenda", comp.id, before=before, after=dados.model_dump())
    db.commit()
    db.refresh(comp)
    return comp


@router.delete("/{comp_id}")
def excluir_compromisso(comp_id: int, db: Session = Depends(get_db), usuario=Depends(agenda_access)):
    comp = db.query(models.Compromisso).filter(models.Compromisso.id == comp_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="Compromisso não encontrado")
    audit(db, usuario, "AGENDA", "EXCLUIR", "agenda", comp.id, before={"titulo": comp.titulo, "data_hora": comp.data_hora})
    db.delete(comp)
    db.commit()
    return {"status": "success"}
