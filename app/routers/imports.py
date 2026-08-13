import csv
import hashlib
import io
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import case, extract, func, or_
from sqlalchemy.orm import Session
from openpyxl import Workbook

from app import models, schemas
from app.database import get_db
from app.dependencies import require_permission
from app.import_service import parse_workbook
from app.services import audit

router = APIRouter(prefix="/importacoes", tags=["Importação de vendas"])


@router.get("/modelo/{tipo_documento}.xlsx")
def baixar_modelo(
    tipo_documento: str,
    _: models.Usuario = Depends(require_permission("pode_importar_planilhas")),
):
    workbook = Workbook()
    sheet = workbook.active
    if tipo_documento == "NOTA_FISCAL":
        sheet.title = "GERAL"
        sheet.append(["CLIENTE", "NUM. N.F.", "DATA", "QTD.", "PRODUTO", "VALOR IND.", "VALOR TOTAL"])
        sheet.append(["CLIENTE EXEMPLO", "NF-001", "01/07/2026", 2, "CINTA EXEMPLO 3M", 50, 100])
        filename = "modelo-notas-fiscais.xlsx"
    elif tipo_documento == "RECIBO":
        sheet.title = "PRINCIPAL"
        sheet.append(["transaction_date", "customer_id", "customer_name", "contact_person", "quantity", "item_description", "unit_price", "total_price"])
        sheet.append(["01/07/2026", "C-001", "CLIENTE EXEMPLO", "CONTATO", 2, "CINTA EXEMPLO 3M", 50, 100])
        filename = "modelo-recibos.xlsx"
    else:
        raise HTTPException(404, "Modelo não encontrado")
    output = io.BytesIO()
    workbook.save(output)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


def _confirmed_hashes(db: Session) -> set[str]:
    return {
        value for value, in db.query(
            func.coalesce(
                models.RegistroVendaImportado.hash_duplicidade,
                models.RegistroVendaImportado.hash_registro,
            )
        )
        .join(models.ImportacaoPlanilha)
        .filter(
            models.ImportacaoPlanilha.status == "CONFIRMADA",
            or_(
                models.RegistroVendaImportado.status_importacao == "NOVO",
                models.RegistroVendaImportado.decisao_duplicidade == "IMPORTAR",
            ),
        )
    }


@router.post("/previsualizar", response_model=schemas.ImportacaoResponse, status_code=201)
async def previsualizar(
    tipo_documento: str = Query(pattern="^(NOTA_FISCAL|RECIBO)$"),
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
    usuario: models.Usuario = Depends(require_permission("pode_importar_planilhas")),
):
    filename = arquivo.filename or "planilha.xlsx"
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(422, "Envie uma planilha no formato .xlsx")
    content = await arquivo.read(15 * 1024 * 1024 + 1)
    if len(content) > 15 * 1024 * 1024:
        raise HTTPException(413, "A planilha deve ter no máximo 15 MB")
    file_hash = hashlib.sha256(content).hexdigest()
    previous = db.query(models.ImportacaoPlanilha).filter_by(
        hash_arquivo=file_hash,
        status="PREVIA",
    ).order_by(models.ImportacaoPlanilha.id.desc()).first()
    if previous:
        return previous
    sheet, rows = parse_workbook(content, tipo_documento, db)
    confirmed = _confirmed_hashes(db)
    seen, prepared_rows, duplicated = set(), [], 0
    occurrences = {}
    for row in rows:
        duplicate_hash = row["hash_registro"]
        occurrence = occurrences.get(duplicate_hash, 0)
        occurrences[duplicate_hash] = occurrence + 1
        is_duplicate = duplicate_hash in confirmed or duplicate_hash in seen
        row["hash_duplicidade"] = duplicate_hash
        row["status_importacao"] = "DUPLICADO" if is_duplicate else "NOVO"
        row["decisao_duplicidade"] = "PENDENTE" if is_duplicate else None
        row["origem_duplicidade"] = (
            "JA_IMPORTADO" if duplicate_hash in confirmed
            else "MESMO_ARQUIVO" if duplicate_hash in seen
            else None
        )
        if occurrence:
            unique_value = f'{duplicate_hash}|{row["linha_origem"]}|{occurrence}'
            row["hash_registro"] = hashlib.sha256(unique_value.encode()).hexdigest()
        if is_duplicate:
            duplicated += 1
        seen.add(duplicate_hash)
        prepared_rows.append(row)
    import_batch = models.ImportacaoPlanilha(
        nome_arquivo=filename, tipo_documento=tipo_documento, aba_origem=sheet,
        hash_arquivo=file_hash, status="PREVIA", total_linhas=len(rows),
        linhas_novas=len(prepared_rows) - duplicated, linhas_duplicadas=duplicated,
        linhas_revisao=duplicated,
        usuario_id=usuario.id, usuario_nome=usuario.nome,
    )
    db.add(import_batch)
    db.flush()
    db.add_all(models.RegistroVendaImportado(importacao_id=import_batch.id, **row) for row in prepared_rows)
    audit(db, usuario, "IMPORTACOES", "PREVISUALIZAR", "importacoes_planilha", import_batch.id,
          after={"arquivo": filename, "tipo_documento": tipo_documento, "linhas": len(rows)})
    db.commit()
    db.refresh(import_batch)
    return import_batch


@router.get("/", response_model=list[schemas.ImportacaoResponse])
def listar(
    db: Session = Depends(get_db),
    _=Depends(require_permission("pode_importar_planilhas")),
):
    return db.query(models.ImportacaoPlanilha).order_by(models.ImportacaoPlanilha.criado_em.desc()).all()


def _records_query(db: Session, incluir_previa=False):
    query = db.query(models.RegistroVendaImportado).join(models.ImportacaoPlanilha)
    if not incluir_previa:
        query = query.filter(
            models.ImportacaoPlanilha.status == "CONFIRMADA",
            models.RegistroVendaImportado.ativo.is_(True),
            or_(
                models.RegistroVendaImportado.status_importacao == "NOVO",
                models.RegistroVendaImportado.decisao_duplicidade == "IMPORTAR",
            ),
        )
    return query


@router.get("/registros", response_model=list[schemas.RegistroImportadoResponse])
def registros(
    importacao_id: int | None = None,
    tipo_documento: str | None = None,
    status: str | None = None,
    situacao: str | None = Query(
        default=None,
        pattern="^(NOVO|DUPLICADO|PENDENTE|REVISADA)$",
    ),
    busca: str | None = None,
    ano: int | None = None,
    mes: int | None = Query(default=None, ge=1, le=12),
    ordenar_por: str = Query(
        default="data",
        pattern="^(data|valor|cliente|produto|origem|situacao|linha)$",
    ),
    ordem: str = Query(default="desc", pattern="^(asc|desc)$"),
    limite: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
    _=Depends(require_permission("pode_importar_planilhas")),
):
    query = _records_query(db, incluir_previa=importacao_id is not None)
    if importacao_id:
        query = query.filter(models.RegistroVendaImportado.importacao_id == importacao_id)
    if tipo_documento:
        query = query.filter(models.RegistroVendaImportado.tipo_documento == tipo_documento)
    if status:
        if status in {"NOVO", "DUPLICADO"}:
            query = query.filter(models.RegistroVendaImportado.status_importacao == status)
        else:
            query = query.filter(models.RegistroVendaImportado.status_padronizacao == status)
    if situacao == "NOVO":
        query = query.filter(
            models.RegistroVendaImportado.status_importacao == "NOVO"
        )
    elif situacao == "DUPLICADO":
        query = query.filter(
            models.RegistroVendaImportado.status_importacao == "DUPLICADO"
        )
    elif situacao == "PENDENTE":
        query = query.filter(
            models.RegistroVendaImportado.status_importacao == "DUPLICADO",
            models.RegistroVendaImportado.decisao_duplicidade == "PENDENTE",
        )
    elif situacao == "REVISADA":
        query = query.filter(
            models.RegistroVendaImportado.status_importacao == "DUPLICADO",
            models.RegistroVendaImportado.decisao_duplicidade.in_(
                ("IGNORAR", "IMPORTAR")
            ),
        )
    if ano:
        query = query.filter(extract("year", models.RegistroVendaImportado.data_venda) == ano)
    if mes:
        query = query.filter(extract("month", models.RegistroVendaImportado.data_venda) == mes)
    if busca:
        like = f"%{busca.strip()}%"
        query = query.filter(or_(
            models.RegistroVendaImportado.cliente_nome.ilike(like),
            models.RegistroVendaImportado.descricao_original.ilike(like),
            models.RegistroVendaImportado.descricao_padronizada.ilike(like),
            models.RegistroVendaImportado.numero_documento.ilike(like),
        ))
    sort_fields = {
        "data": models.RegistroVendaImportado.data_venda,
        "valor": models.RegistroVendaImportado.valor_total,
        "cliente": models.RegistroVendaImportado.cliente_nome,
        "produto": models.RegistroVendaImportado.descricao_padronizada,
        "origem": models.RegistroVendaImportado.tipo_documento,
        "situacao": models.RegistroVendaImportado.status_importacao,
        "linha": models.RegistroVendaImportado.linha_origem,
    }
    selected_sort = sort_fields[ordenar_por]
    selected_order = (
        selected_sort.asc() if ordem == "asc" else selected_sort.desc()
    )
    ordering = []
    if importacao_id:
        # Em toda prévia, cópias ainda sem decisão permanecem agrupadas no topo.
        ordering.append(case(
            (
                (
                    models.RegistroVendaImportado.status_importacao
                    == "DUPLICADO"
                )
                & (
                    models.RegistroVendaImportado.decisao_duplicidade
                    == "PENDENTE"
                ),
                0,
            ),
            else_=1,
        ).asc())
    ordering.extend((selected_order, models.RegistroVendaImportado.id.asc()))
    return query.order_by(*ordering).limit(limite).all()


@router.patch("/registros/{registro_id}", response_model=schemas.RegistroImportadoResponse)
def atualizar_registro(
    registro_id: int,
    dados: schemas.RegistroImportadoUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_permission("pode_importar_planilhas")),
):
    record = db.get(models.RegistroVendaImportado, registro_id)
    if not record:
        raise HTTPException(404, "Registro não encontrado")
    if dados.produto_id and not db.get(models.Produto, dados.produto_id):
        raise HTTPException(404, "Produto não encontrado")
    for key, value in dados.model_dump().items():
        setattr(record, key, value)
    db.flush()
    batch = db.get(models.ImportacaoPlanilha, record.importacao_id)
    batch.linhas_revisao = db.query(models.RegistroVendaImportado).filter_by(
        importacao_id=batch.id, status_importacao="DUPLICADO",
        decisao_duplicidade="PENDENTE",
    ).count()
    db.commit()
    db.refresh(record)
    return record


def _refresh_pending_duplicates(db: Session, batch: models.ImportacaoPlanilha):
    batch.linhas_revisao = db.query(models.RegistroVendaImportado).filter_by(
        importacao_id=batch.id,
        status_importacao="DUPLICADO",
        decisao_duplicidade="PENDENTE",
    ).count()


@router.patch(
    "/registros/{registro_id}/duplicidade",
    response_model=schemas.RegistroImportadoResponse,
)
def decidir_duplicidade(
    registro_id: int,
    dados: schemas.DecisaoDuplicidade,
    db: Session = Depends(get_db),
    _=Depends(require_permission("pode_importar_planilhas")),
):
    record = db.get(models.RegistroVendaImportado, registro_id)
    if not record:
        raise HTTPException(404, "Registro não encontrado")
    batch = db.get(models.ImportacaoPlanilha, record.importacao_id)
    if batch.status != "PREVIA":
        raise HTTPException(409, "A decisão só pode ser alterada antes da confirmação")
    if record.status_importacao != "DUPLICADO":
        raise HTTPException(422, "Este registro é novo e já está aceito automaticamente")
    record.decisao_duplicidade = dados.decisao
    _refresh_pending_duplicates(db, batch)
    db.commit()
    db.refresh(record)
    return record


@router.post("/{importacao_id}/duplicidades/ignorar", response_model=schemas.ImportacaoResponse)
def ignorar_duplicidades(
    importacao_id: int,
    db: Session = Depends(get_db),
    _=Depends(require_permission("pode_importar_planilhas")),
):
    batch = db.get(models.ImportacaoPlanilha, importacao_id)
    if not batch:
        raise HTTPException(404, "Importação não encontrada")
    if batch.status != "PREVIA":
        raise HTTPException(409, "Esta importação já foi finalizada")
    db.query(models.RegistroVendaImportado).filter_by(
        importacao_id=batch.id,
        status_importacao="DUPLICADO",
        decisao_duplicidade="PENDENTE",
    ).update({"decisao_duplicidade": "IGNORAR"}, synchronize_session=False)
    _refresh_pending_duplicates(db, batch)
    db.commit()
    db.refresh(batch)
    return batch


@router.post("/{importacao_id}/confirmar", response_model=schemas.ImportacaoResponse)
def confirmar(
    importacao_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(require_permission("pode_importar_planilhas")),
):
    batch = db.get(models.ImportacaoPlanilha, importacao_id)
    if not batch:
        raise HTTPException(404, "Importação não encontrada")
    if batch.status != "PREVIA":
        raise HTTPException(409, "Esta importação já foi finalizada")
    _refresh_pending_duplicates(db, batch)
    if batch.linhas_revisao:
        db.rollback()
        raise HTTPException(
            422,
            f"Ainda existem {batch.linhas_revisao} cópia(s) para revisar",
        )
    batch.status = "CONFIRMADA"
    batch.confirmado_em = datetime.now()
    audit(db, usuario, "IMPORTACOES", "CONFIRMAR", "importacoes_planilha", batch.id,
          before={"status": "PREVIA"}, after={"status": "CONFIRMADA", "total_linhas": batch.total_linhas})
    db.commit()
    db.refresh(batch)
    return batch


@router.delete("/{importacao_id}", status_code=204)
def cancelar_previa(
    importacao_id: int,
    db: Session = Depends(get_db),
    usuario=Depends(require_permission("pode_importar_planilhas")),
):
    batch = db.get(models.ImportacaoPlanilha, importacao_id)
    if not batch:
        raise HTTPException(404, "Importação não encontrada")
    if batch.status != "PREVIA":
        raise HTTPException(409, "Importações confirmadas não podem ser apagadas")
    audit(db, usuario, "IMPORTACOES", "CANCELAR", "importacoes_planilha", batch.id,
          before={"arquivo": batch.nome_arquivo, "status": batch.status})
    db.delete(batch)
    db.commit()


@router.get("/analise/resumo")
def resumo(
    ano: int | None = None,
    mes: int | None = Query(default=None, ge=1, le=12),
    tipo_documento: str | None = None,
    db: Session = Depends(get_db),
    _=Depends(require_permission("pode_ver_faturamento")),
):
    query = _records_query(db)
    if ano:
        query = query.filter(extract("year", models.RegistroVendaImportado.data_venda) == ano)
    if mes:
        query = query.filter(extract("month", models.RegistroVendaImportado.data_venda) == mes)
    if tipo_documento:
        query = query.filter(models.RegistroVendaImportado.tipo_documento == tipo_documento)
    total, quantity, records, clients = query.with_entities(
        func.coalesce(func.sum(models.RegistroVendaImportado.valor_total), 0),
        func.coalesce(func.sum(models.RegistroVendaImportado.quantidade), 0),
        func.count(models.RegistroVendaImportado.id),
        func.count(func.distinct(models.RegistroVendaImportado.cliente_nome)),
    ).one()
    products = query.with_entities(
        models.RegistroVendaImportado.descricao_padronizada,
        func.sum(models.RegistroVendaImportado.quantidade).label("quantidade"),
        func.sum(models.RegistroVendaImportado.valor_total).label("faturamento"),
    ).group_by(models.RegistroVendaImportado.descricao_padronizada).order_by(
        func.sum(models.RegistroVendaImportado.quantidade).desc()
    ).limit(20).all()
    return {
        "faturamento": total, "quantidade": quantity, "registros": records,
        "clientes": clients,
        "produtos": [{"produto": name, "quantidade": qty, "faturamento": value} for name, qty, value in products],
    }


@router.get("/exportar.csv")
def exportar(
    tipo_documento: str | None = None,
    ano: int | None = None,
    mes: int | None = Query(default=None, ge=1, le=12),
    db: Session = Depends(get_db),
    _=Depends(require_permission("pode_ver_faturamento")),
):
    query = _records_query(db)
    if tipo_documento:
        query = query.filter(models.RegistroVendaImportado.tipo_documento == tipo_documento)
    if ano:
        query = query.filter(extract("year", models.RegistroVendaImportado.data_venda) == ano)
    if mes:
        query = query.filter(extract("month", models.RegistroVendaImportado.data_venda) == mes)
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["Data", "Origem", "Documento", "Cliente", "Quantidade", "Produto original", "Produto padronizado", "Família", "Valor unitário", "Valor total", "Status"])
    for row in query.order_by(models.RegistroVendaImportado.data_venda).all():
        writer.writerow([row.data_venda.strftime("%d/%m/%Y"), row.tipo_documento, row.numero_documento or "", row.cliente_nome, row.quantidade, row.descricao_original, row.descricao_padronizada, row.familia or "", row.valor_unitario, row.valor_total, row.status_padronizacao])
    data = output.getvalue().encode("utf-8-sig")
    return StreamingResponse(iter([data]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=brcom-vendas.csv"})
