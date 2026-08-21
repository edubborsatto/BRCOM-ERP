from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from app import models, schemas
from app.database import get_db
from app.dependencies import require_admin, require_permission
from app.inventory import formula_cost
from app.services import audit

router = APIRouter(prefix="/formulas", tags=["Fórmulas de produção"])


def _formula_dict(formula: models.FormulaProduto) -> dict:
    return {
        "id": formula.id,
        "produto_id": formula.produto_id,
        "mao_de_obra": formula.mao_de_obra,
        "custos_adicionais": formula.custos_adicionais,
        "markup_percentual": formula.markup_percentual,
        "observacoes": formula.observacoes,
        "componentes": formula.componentes,
        **formula_cost(formula),
    }


def _query(db: Session):
    return db.query(models.FormulaProduto).options(
        joinedload(models.FormulaProduto.componentes)
        .joinedload(models.FormulaComponente.materia_prima)
    )


@router.get("/", response_model=list[schemas.FormulaResponse])
def listar(
    db: Session = Depends(get_db),
    _=Depends(require_permission("pode_alterar_custos")),
):
    return [_formula_dict(f) for f in _query(db).join(models.Produto).filter(models.Produto.ativo.is_(True)).all()]


@router.get("/{produto_id}", response_model=schemas.FormulaResponse)
def obter(
    produto_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission("pode_alterar_custos")),
):
    formula = _query(db).filter(models.FormulaProduto.produto_id == produto_id).first()
    if not formula:
        raise HTTPException(status_code=404, detail="Fórmula não encontrada")
    return _formula_dict(formula)


@router.put("/{produto_id}", response_model=schemas.FormulaResponse)
def salvar(
    produto_id: int,
    dados: schemas.FormulaCreate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("pode_alterar_custos")),
):
    if dados.produto_id != produto_id:
        raise HTTPException(status_code=400, detail="Produto divergente")
    produto = db.get(models.Produto, produto_id)
    if not produto or not produto.ativo or produto.tipo_item != "PRODUTO_ACABADO":
        raise HTTPException(status_code=400, detail="Fórmula exige um produto acabado")
    ids = [c.materia_prima_id for c in dados.componentes]
    materias = db.query(models.Produto).filter(models.Produto.id.in_(ids)).all()
    if len(set(ids)) != len(ids) or len(materias) != len(ids):
        raise HTTPException(status_code=400, detail="Matérias-primas inválidas ou repetidas")
    if any(p.tipo_item != "MATERIA_PRIMA" for p in materias):
        raise HTTPException(status_code=400, detail="A fórmula aceita somente matérias-primas")
    formula = db.query(models.FormulaProduto).filter_by(produto_id=produto_id).first()
    if not formula:
        formula = models.FormulaProduto(produto_id=produto_id)
        db.add(formula)
        db.flush()
    formula.mao_de_obra = dados.mao_de_obra
    formula.custos_adicionais = dados.custos_adicionais
    formula.markup_percentual = dados.markup_percentual
    formula.observacoes = dados.observacoes
    formula.componentes.clear()
    for componente in dados.componentes:
        formula.componentes.append(models.FormulaComponente(**componente.model_dump()))
    db.commit()
    formula = _query(db).filter_by(produto_id=produto_id).first()
    custos = formula_cost(formula)
    produto.preco_custo = custos["custo_total"]
    produto.preco_venda = custos["preco_sugerido"]
    db.commit()
    return _formula_dict(formula)


@router.delete("/{produto_id}")
def excluir(
    produto_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(require_admin),
):
    formula = db.query(models.FormulaProduto).filter_by(produto_id=produto_id).first()
    if not formula:
        raise HTTPException(status_code=404, detail="Fórmula não encontrada")
    audit(db, usuario, "FORMULAS", "EXCLUIR", "formulas_produto", formula.id,
          before={"produto_id": produto_id, "componentes": len(formula.componentes)})
    db.delete(formula)
    db.commit()
    return {"status": "success"}
