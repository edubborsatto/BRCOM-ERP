import io
from datetime import date

from openpyxl import Workbook


def spreadsheet(sheet_name, headers, rows):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = sheet_name
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    content = io.BytesIO()
    workbook.save(content)
    return content.getvalue()


def upload(client, document_type, content, filename):
    return client.post(
        f"/importacoes/previsualizar?tipo_documento={document_type}",
        files={"arquivo": (filename, content, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )


def test_importa_notas_da_aba_geral_e_evitar_duplicidade(admin_client):
    headers = ["CLIENTE", "NUM. N.F.", "DATA", "QTD.", "PRODUTO", "VALOR IND.", "VALOR TOTAL", "% DE DESC."]
    row = ["BALL EMBALAGENS LTDA", "382", date(2021, 3, 2), 2, "CORRENTE ALLOY 10MM", 100, 200, 0]
    first_file = spreadsheet("GERAL", headers, [row])
    preview = upload(admin_client, "NOTA_FISCAL", first_file, "notas.xlsx")
    assert preview.status_code == 201, preview.text
    assert preview.json()["linhas_novas"] == 1
    assert preview.json()["aba_origem"] == "GERAL"
    batch_id = preview.json()["id"]
    records = admin_client.get(f"/importacoes/registros?importacao_id={batch_id}").json()
    assert records[0]["numero_documento"] == "382"
    assert records[0]["cliente_nome"] == "BALL EMBALAGENS LTDA"
    assert float(records[0]["valor_total"]) == 200
    assert records[0]["status_importacao"] == "NOVO"
    assert records[0]["status_padronizacao"] == "PADRONIZADO"
    assert records[0]["status_importacao"] == "NOVO"
    assert records[0]["decisao_duplicidade"] is None
    assert admin_client.post(f"/importacoes/{batch_id}/confirmar").status_code == 200

    same_file = upload(admin_client, "NOTA_FISCAL", first_file, "notas.xlsx")
    assert same_file.status_code == 201
    assert same_file.json()["linhas_novas"] == 0
    assert same_file.json()["linhas_duplicadas"] == 1
    ignored = admin_client.post(
        f"/importacoes/{same_file.json()['id']}/duplicidades/ignorar"
    )
    assert ignored.status_code == 200
    assert ignored.json()["linhas_revisao"] == 0
    assert admin_client.post(
        f"/importacoes/{same_file.json()['id']}/confirmar"
    ).status_code == 200

    updated_file = spreadsheet("GERAL", headers, [
        row,
        ["NOVO CLIENTE", "383", date(2021, 4, 2), 3, "CINTA ELEVAÇÃO MOD. SLING 3M", 50, 150, 0],
    ])
    second = upload(admin_client, "NOTA_FISCAL", updated_file, "notas-atualizadas.xlsx")
    assert second.status_code == 201, second.text
    assert second.json()["linhas_novas"] == 1
    assert second.json()["linhas_duplicadas"] == 1
    assert second.json()["linhas_revisao"] == 1
    second_records = admin_client.get(
        f"/importacoes/registros?importacao_id={second.json()['id']}"
    ).json()
    duplicate = next(row for row in second_records if row["status_importacao"] == "DUPLICADO")
    assert duplicate["decisao_duplicidade"] == "PENDENTE"
    assert duplicate["origem_duplicidade"] == "JA_IMPORTADO"
    blocked = admin_client.post(f"/importacoes/{second.json()['id']}/confirmar")
    assert blocked.status_code == 422
    decision = admin_client.patch(
        f"/importacoes/registros/{duplicate['id']}/duplicidade",
        json={"decisao": "IGNORAR"},
    )
    assert decision.status_code == 200
    assert admin_client.post(f"/importacoes/{second.json()['id']}/confirmar").status_code == 200

    report = admin_client.get("/importacoes/analise/resumo?ano=2021").json()
    assert report["registros"] == 2
    assert float(report["faturamento"]) == 350
    assert float(report["quantidade"]) == 5

    revenue = admin_client.get("/relatorios/faturamento?ano=2021").json()
    assert float(revenue["total"]) == 350
    assert float(revenue["nota_fiscal"]) == 350
    assert float(revenue["recibo"]) == 0
    assert [(row["ano"], row["mes"]) for row in revenue["mensal"]] == [
        (2021, 4), (2021, 3),
    ]
    assert revenue["anual"][0]["ano"] == 2021


def test_importa_recibos_da_aba_principal(admin_client):
    content = spreadsheet("PRINCIPAL", [
        "transaction_date", "customer_id", "customer_name", "contact_person",
        "quantity", "item_description", "unit_price", "total_price",
    ], [[date(2025, 3, 19), "C-01", "CLIENTE RECIBO", "MARIA", 4, "CINTA ELEVAÇÃO MOD. SLING", 25, 100]])
    preview = upload(admin_client, "RECIBO", content, "recibos.xlsx")
    assert preview.status_code == 201, preview.text
    assert preview.json()["aba_origem"] == "PRINCIPAL"
    assert admin_client.post(f"/importacoes/{preview.json()['id']}/confirmar").status_code == 200
    records = admin_client.get("/importacoes/registros?tipo_documento=RECIBO").json()
    assert any(row["numero_documento"] == "C-01" for row in records)
    assert any(row["cliente_codigo"] == "C-01" and row["contato"] == "MARIA" for row in records)


def test_documento_usa_coluna_b_com_cabecalho_nota_ou_recibo(admin_client):
    note = spreadsheet("GERAL", [
        "DATA", "NOTA", "CLIENTE", "QTD.", "PRODUTO", "VALOR TOTAL",
    ], [[
        date(2026, 9, 16), "NF-4587", "LSL TRANSPORTES LTDA.", 30,
        "CINTA AMARRAÇÃO", 900,
    ]])
    note_preview = upload(admin_client, "NOTA_FISCAL", note, "notas-coluna-b.xlsx")
    assert note_preview.status_code == 201, note_preview.text
    note_rows = admin_client.get(
        f"/importacoes/registros?importacao_id={note_preview.json()['id']}"
    ).json()
    assert note_rows[0]["numero_documento"] == "NF-4587"

    receipt = spreadsheet("PRINCIPAL", [
        "DATA", "RECIBO", "CLIENTE", "QTD.", "PRODUTO", "VALOR TOTAL",
    ], [[
        date(2026, 9, 17), "R-8910", "CLIENTE RECIBO", 2,
        "CINTA TUBULAR", 250,
    ]])
    receipt_preview = upload(
        admin_client, "RECIBO", receipt, "recibos-coluna-b.xlsx"
    )
    assert receipt_preview.status_code == 201, receipt_preview.text
    receipt_rows = admin_client.get(
        f"/importacoes/registros?importacao_id={receipt_preview.json()['id']}"
    ).json()
    assert receipt_rows[0]["numero_documento"] == "R-8910"


def test_revisa_apenas_copias_e_permite_importar_uma_copia(admin_client):
    headers = ["data", "recibo", "cliente", "responsavel da compra", "quantidade", "produto", "valor", "$ prod. c/ desc.", "valor und. c/ desc."]
    row = [date(2026, 6, 3), "3339", "GRUPO FUTURA", "SR. TONINHO", 5, "CINTA PES 50MM 5TONS. 9MTS.", 53.8, 244.39, 48.878]
    content = spreadsheet("PRINCIPAL", headers, [row, row])
    preview = upload(admin_client, "RECIBO", content, "recibos-com-copia.xlsx")
    assert preview.status_code == 201, preview.text
    assert preview.json()["linhas_novas"] == 1
    assert preview.json()["linhas_duplicadas"] == 1
    records = admin_client.get(
        f"/importacoes/registros?importacao_id={preview.json()['id']}"
    ).json()
    assert len(records) == 2
    assert records[0]["status_importacao"] == "DUPLICADO"
    assert all(row["status_padronizacao"] == "PADRONIZADO" for row in records)
    duplicate = next(row for row in records if row["status_importacao"] == "DUPLICADO")
    assert duplicate["origem_duplicidade"] == "MESMO_ARQUIVO"
    assert float(duplicate["valor_total"]) == 244.39
    assert admin_client.patch(
        f"/importacoes/registros/{duplicate['id']}/duplicidade",
        json={"decisao": "IMPORTAR"},
    ).status_code == 200
    assert admin_client.post(f"/importacoes/{preview.json()['id']}/confirmar").status_code == 200
    revenue = admin_client.get("/relatorios/faturamento?ano=2026&mes=6&tipo_documento=RECIBO").json()
    assert float(revenue["recibo"]) == 488.78


def test_filtra_e_ordena_previa_sem_tirar_copias_pendentes_do_topo(
    admin_client,
):
    headers = [
        "data", "recibo", "cliente", "quantidade", "produto",
        "valor", "$ prod. c/ desc.",
    ]
    repeated = [
        date(2026, 6, 3), "3339", "CLIENTE B", 5,
        "CINTA PES 50MM 5TONS. 9MTS.", 53.8, 244.39,
    ]
    newer = [
        date(2026, 7, 10), "3340", "CLIENTE A", 1,
        "CINTA TUBULAR 2TONS 3MTS", 500, 500,
    ]
    content = spreadsheet("PRINCIPAL", headers, [repeated, repeated, newer])
    preview = upload(admin_client, "RECIBO", content, "ordenacao.xlsx").json()
    batch_id = preview["id"]

    by_value = admin_client.get(
        f"/importacoes/registros?importacao_id={batch_id}"
        "&ordenar_por=valor&ordem=desc"
    ).json()
    assert by_value[0]["status_importacao"] == "DUPLICADO"
    assert float(by_value[1]["valor_total"]) == 500

    pending = admin_client.get(
        f"/importacoes/registros?importacao_id={batch_id}"
        "&situacao=PENDENTE"
    ).json()
    assert len(pending) == 1
    assert pending[0]["decisao_duplicidade"] == "PENDENTE"

    reviewed_before = admin_client.get(
        f"/importacoes/registros?importacao_id={batch_id}"
        "&situacao=REVISADA"
    ).json()
    assert reviewed_before == []
    admin_client.patch(
        f"/importacoes/registros/{pending[0]['id']}/duplicidade",
        json={"decisao": "IGNORAR"},
    )
    reviewed_after = admin_client.get(
        f"/importacoes/registros?importacao_id={batch_id}"
        "&situacao=REVISADA"
    ).json()
    assert len(reviewed_after) == 1
    assert reviewed_after[0]["decisao_duplicidade"] == "IGNORAR"


def test_reenvio_do_mesmo_arquivo_lista_copia_para_revisao(admin_client):
    headers = ["CLIENTE", "NUM. N.F.", "DATA", "QTD.", "PRODUTO", "VALOR TOTAL"]
    content = spreadsheet("GERAL", headers, [[
        "CLIENTE TESTE", "NF-2026", date(2026, 7, 1), 1,
        "CINTA TUBULAR 2TONS 3MTS", 125,
    ]])
    first = upload(admin_client, "NOTA_FISCAL", content, "julho.xlsx")
    assert admin_client.post(f"/importacoes/{first.json()['id']}/confirmar").status_code == 200

    repeated = upload(admin_client, "NOTA_FISCAL", content, "julho.xlsx")
    assert repeated.status_code == 201, repeated.text
    assert repeated.json()["linhas_novas"] == 0
    assert repeated.json()["linhas_duplicadas"] == 1
    records = admin_client.get(
        f"/importacoes/registros?importacao_id={repeated.json()['id']}"
    ).json()
    assert records[0]["status_importacao"] == "DUPLICADO"
    assert records[0]["decisao_duplicidade"] == "PENDENTE"
    ignored = admin_client.post(
        f"/importacoes/{repeated.json()['id']}/duplicidades/ignorar"
    )
    assert ignored.status_code == 200
    assert ignored.json()["linhas_revisao"] == 0
    assert admin_client.post(
        f"/importacoes/{repeated.json()['id']}/confirmar"
    ).status_code == 200


def test_importa_formato_legado_de_nf_com_produto_na_coluna_cliente(admin_client):
    content = spreadsheet("GERAL", [
        "CLIENTE", "NUM. N.F.", "DATA", "QTD.", "VALOR IND.",
        "VALOR TOTAL", "VALOR IND. C/ DESC.", "VALOR PROD. C/ DESC.",
    ], [
        ["CLIENTE CABEÇALHO", "NF-900", date(2024, 1, 10), None, None, 999, None, None],
        ["CORRENTE ALLOY 10MM", None, None, 2, 100, None, 90, 180],
    ])
    preview = upload(admin_client, "NOTA_FISCAL", content, "notas-legado.xlsx")
    assert preview.status_code == 201, preview.text
    records = admin_client.get(f"/importacoes/registros?importacao_id={preview.json()['id']}").json()
    assert records[0]["cliente_nome"] == "CLIENTE CABEÇALHO"
    assert records[0]["descricao_original"] == "CORRENTE ALLOY 10MM"
    assert float(records[0]["valor_unitario"]) == 90
    assert float(records[0]["valor_total"]) == 180


def test_rejeita_aba_errada_e_exige_permissao(client, admin_client):
    assert admin_client.get("/importacoes/modelo/NOTA_FISCAL.xlsx").status_code == 200
    assert admin_client.get("/importacoes/modelo/RECIBO.xlsx").status_code == 200
    wrong = spreadsheet("TOTAL", ["CLIENTE", "DATA", "QTD.", "PRODUTO", "VALOR TOTAL"], [])
    response = upload(admin_client, "RECIBO", wrong, "errado.xlsx")
    assert response.status_code == 422
    assert "PRINCIPAL" in response.json()["detail"]

    admin_client.post("/api/logout")
    assert client.get("/importacoes/").status_code == 401
