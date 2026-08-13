from datetime import datetime, timedelta


def test_venda_cancelada_sai_do_faturamento_e_audita(admin_client):
    cliente = admin_client.post("/clientes/", json={"nome": "Cliente integrado"}).json()
    venda = admin_client.post("/vendas/", json={
        "cliente_id": cliente["id"], "tipo_documento": "RECIBO",
        "numero_documento": "INT-001", "valor_total": 250,
        "data_venda": datetime.now().date().isoformat(),
    }).json()
    antes = admin_client.get("/relatorios/faturamento").json()["total"]
    cancelada = admin_client.post(
        f"/vendas/{venda['id']}/cancelar", json={"motivo": "Registro em duplicidade"}
    )
    assert cancelada.status_code == 200
    assert cancelada.json()["status"] == "CANCELADA"
    depois = admin_client.get("/relatorios/faturamento").json()["total"]
    assert float(antes) - float(depois) == 250
    auditoria = admin_client.get("/historico/sistema?modulo=VENDAS&acao=CANCELAR").json()
    assert any(row["entidade_id"] == venda["id"] for row in auditoria)


def test_agenda_operacional_reune_origens(admin_client):
    cliente = admin_client.post("/clientes/", json={"nome": "Cliente agenda"}).json()
    entrega = datetime.now() + timedelta(days=3)
    admin_client.post("/agenda/", json={
        "titulo": "Reunião de produção", "data_hora": entrega.isoformat(),
    })
    admin_client.post("/pedidos/", json={
        "cliente_id": cliente["id"], "produto_nome": "Legado agenda",
        "quantidade": 1, "data_entrega": entrega.isoformat(),
    })
    dia = entrega.date().isoformat()
    eventos = admin_client.get(f"/agenda/eventos?data_inicial={dia}&data_final={dia}").json()
    assert {evento["origem"] for evento in eventos} >= {"AGENDA", "PEDIDO"}


def test_interface_agenda_mensal_e_edicao_de_vendas(client):
    page = client.get("/").text
    assert 'id="agendaMonth"' in page
    assert 'id="agendaYear"' in page
    assert 'id="agendaCalendarView"' in page
    assert 'id="agendaListView"' in page
    assert 'id="agendaDayDialog"' in page
    assert 'id="sale_id"' in page
    js = client.get("/static/js/operations.js").text
    assert 'data-edit-sale="${v.id}"' in js


def test_venda_confirma_modalidade_e_conclusao_separada(admin_client):
    client = admin_client.post("/clientes/", json={"nome": "Cliente retirada"}).json()
    product = admin_client.post("/produtos/", json={
        "codigo": "PA-RET", "nome": "Produto retirada", "tipo_item": "PRODUTO_ACABADO",
        "unidade_medida": "UN", "quantidade_atual": 2, "estoque_minimo": 0,
        "preco_custo": 10, "preco_venda": 20,
    }).json()
    order = admin_client.post("/pedidos/", json={
        "cliente_id": client["id"], "data_entrega": (datetime.now() + timedelta(days=1)).isoformat(),
        "itens": [{"produto_id": product["id"], "quantidade_total": 1,
                   "quantidade_estoque": 1, "quantidade_fabricar": 0}],
    }).json()
    assert admin_client.post(
        f"/pedidos/{order['id']}/observacao", json={"texto": "Separar embalagem reforçada"}
    ).status_code == 200
    assert admin_client.post(
        f"/pedidos/{order['id']}/falta-material", json={"texto": "Etiqueta técnica"}
    ).status_code == 200
    for status in ("AGUARDANDO_PRODUCAO", "EM_PRODUCAO", "PRODUCAO_CONCLUIDA", "SEPARADO", "PRONTO"):
        assert admin_client.post(f"/pedidos/{order['id']}/status", json={"status": status}).status_code == 200
    sold = admin_client.post(f"/pedidos/{order['id']}/confirmar-venda", json={
        "tipo_documento": "RECIBO", "numero_documento": "RET-1", "modalidade_entrega": "RETIRADA",
    }).json()
    assert sold["status"] == "PRONTO"
    assert admin_client.post(f"/pedidos/{order['id']}/status", json={"status": "ENTREGUE"}).status_code == 409
    assert admin_client.post(f"/pedidos/{order['id']}/status", json={"status": "RETIRADO"}).status_code == 200
    audit = admin_client.get("/historico/sistema?modulo=PEDIDOS&acao=FALTA_MATERIAL").json()
    assert any(row["entidade_id"] == order["id"] for row in audit)
