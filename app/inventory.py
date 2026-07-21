from decimal import Decimal, ROUND_HALF_UP

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app import models


ZERO = Decimal("0")
CENT = Decimal("0.01")


def decimal(value) -> Decimal:
    return Decimal(str(value or 0))


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def formula_cost(formula: models.FormulaProduto) -> dict[str, Decimal]:
    materias = ZERO
    for componente in formula.componentes:
        quantidade = decimal(componente.quantidade)
        perda = decimal(componente.perda_percentual) / Decimal("100")
        materias += decimal(componente.materia_prima.preco_custo) * quantidade * (1 + perda)
    total = materias + decimal(formula.mao_de_obra) + decimal(formula.custos_adicionais)
    preco = total * (1 + decimal(formula.markup_percentual) / Decimal("100"))
    return {
        "custo_materia_prima": money(materias),
        "custo_total": money(total),
        "preco_sugerido": money(preco),
    }


def record_movement(
    db: Session,
    produto: models.Produto,
    tipo: str,
    quantidade: Decimal,
    usuario: models.Usuario,
    motivo: str,
    referencia: str | None = None,
    saldo_final: Decimal | None = None,
) -> models.HistoricoEstoque:
    anterior = decimal(produto.quantidade_atual)
    quantidade = decimal(quantidade)
    if tipo in {"SAIDA", "PERDA", "CONSUMO_PRODUCAO"}:
        posterior = anterior - quantidade
    elif tipo == "ENTRADA":
        posterior = anterior + quantidade
    elif tipo == "AJUSTE":
        if saldo_final is None:
            raise HTTPException(status_code=400, detail="Informe o saldo final do ajuste")
        posterior = decimal(saldo_final)
        quantidade = abs(posterior - anterior)
    else:
        raise HTTPException(status_code=400, detail="Tipo de movimentação inválido")
    if posterior < ZERO:
        raise HTTPException(
            status_code=409,
            detail=f"Estoque insuficiente de {produto.nome}. Disponível: {anterior}",
        )
    produto.quantidade_atual = posterior
    registro = models.HistoricoEstoque(
        produto_id=produto.id,
        produto_nome=produto.nome,
        tipo_movimentacao=tipo,
        quantidade=quantidade,
        saldo_anterior=anterior,
        saldo_apos=posterior,
        motivo=motivo,
        referencia=referencia,
        usuario_id=usuario.id,
        usuario_responsavel=usuario.nome,
    )
    db.add(registro)
    return registro
