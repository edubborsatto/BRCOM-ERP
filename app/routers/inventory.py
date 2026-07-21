from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import models, schemas
from app.database import get_db
from app.dependencies import require_permission
from app.inventory import record_movement

router = APIRouter(prefix="/estoque", tags=["Estoque"])


@router.post("/movimentacoes", response_model=schemas.HistoricoResponse, status_code=201)
def movimentar(
    dados: schemas.MovimentacaoCreate,
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_permission("pode_movimentar_estoque")),
):
    produto = db.get(models.Produto, dados.produto_id)
    if not produto:
        raise HTTPException(status_code=404, detail="Produto não encontrado")
    registro = record_movement(
        db, produto, dados.tipo_movimentacao, dados.quantidade, usuario,
        dados.motivo, dados.referencia, dados.saldo_final_ajuste,
    )
    db.commit()
    db.refresh(registro)
    return registro
