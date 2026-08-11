from datetime import datetime, timedelta


def product(code, name, kind, quantity):
    return {
        "codigo": code,
        "nome": name,
        "tipo_item": kind,
        "tipo": "Teste fila",
        "familia": "Pedidos",
        "unidade_medida": "UN",
        "quantidade_atual": quantity,
        "estoque_minimo": 1,
        "preco_custo": 1,
        "preco_venda": 2,
        "localizacao": "QA fila",
    }


def order_payload(finished_id, material_id, stock=3, make=5, material_quantity=12.5):
    return {
        "cliente_nome": "Cliente da fila",
        "data_entrega": (datetime.now() + timedelta(days=10)).isoformat(),
        "prioridade": False,
        "itens": [{
            "produto_id": finished_id,
            "quantidade_total": stock + make,
            "quantidade_estoque": stock,
            "quantidade_fabricar": make,
            "materias_primas": [{
                "materia_prima_id": material_id,
                "quantidade": material_quantity,
            }],
        }],
    }


def test_pedido_reserva_edita_e_devolve_estoques(admin_client):
    finished = admin_client.post(
        "/produtos/", json=product("PA-FILA-01", "Produto da fila 01", "PRODUTO_ACABADO", 10)
    ).json()
    material = admin_client.post(
        "/produtos/", json=product("MP-FILA-01", "Matéria da fila 01", "MATERIA_PRIMA", 100)
    ).json()

    created = admin_client.post(
        "/pedidos/", json=order_payload(finished["id"], material["id"])
    )
    assert created.status_code == 201
    order = created.json()
    assert len(order["itens"]) == 1
    assert float(order["itens"][0]["quantidade_estoque"]) == 3
    assert float(order["itens"][0]["quantidade_fabricar"]) == 5
    assert float(order["itens"][0]["materias_primas"][0]["quantidade_reservada"]) == 12.5

    products = {row["codigo"]: row for row in admin_client.get("/produtos/").json()}
    assert float(products["PA-FILA-01"]["quantidade_atual"]) == 7
    assert float(products["MP-FILA-01"]["quantidade_atual"]) == 87.5

    edited_payload = order_payload(
        finished["id"], material["id"], stock=1, make=7, material_quantity=20
    )
    edited = admin_client.put(f"/pedidos/{order['id']}", json=edited_payload)
    assert edited.status_code == 200
    products = {row["codigo"]: row for row in admin_client.get("/produtos/").json()}
    assert float(products["PA-FILA-01"]["quantidade_atual"]) == 9
    assert float(products["MP-FILA-01"]["quantidade_atual"]) == 80

    cancelled = admin_client.delete(f"/pedidos/{order['id']}")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "Cancelado"
    products = {row["codigo"]: row for row in admin_client.get("/produtos/").json()}
    assert float(products["PA-FILA-01"]["quantidade_atual"]) == 10
    assert float(products["MP-FILA-01"]["quantidade_atual"]) == 100
    history = admin_client.get(f"/historico/?busca=PEDIDO-{order['id']}").json()
    assert {row["tipo_movimentacao"] for row in history} >= {"SAIDA", "CONSUMO_PRODUCAO", "ENTRADA"}


def test_validacao_divisao_saldo_e_materia_prima(admin_client):
    finished = admin_client.post(
        "/produtos/", json=product("PA-FILA-02", "Produto da fila 02", "PRODUTO_ACABADO", 2)
    ).json()
    material = admin_client.post(
        "/produtos/", json=product("MP-FILA-02", "Matéria da fila 02", "MATERIA_PRIMA", 3)
    ).json()
    payload = order_payload(finished["id"], material["id"], stock=3, make=1, material_quantity=1)
    insufficient_finished = admin_client.post("/pedidos/", json=payload)
    assert insufficient_finished.status_code == 409

    payload = order_payload(finished["id"], material["id"], stock=1, make=3, material_quantity=4)
    insufficient_material = admin_client.post("/pedidos/", json=payload)
    assert insufficient_material.status_code == 409

    payload = order_payload(finished["id"], material["id"])
    payload["itens"][0]["quantidade_total"] = 99
    invalid_split = admin_client.post("/pedidos/", json=payload)
    assert invalid_split.status_code == 422


def test_fila_reordenavel_e_prioridade(admin_client):
    finished = admin_client.post(
        "/produtos/", json=product("PA-FILA-03", "Produto da fila 03", "PRODUTO_ACABADO", 20)
    ).json()
    material = admin_client.post(
        "/produtos/", json=product("MP-FILA-03", "Matéria da fila 03", "MATERIA_PRIMA", 20)
    ).json()
    first = admin_client.post(
        "/pedidos/", json=order_payload(finished["id"], material["id"], 1, 1, 1)
    ).json()
    second_payload = order_payload(finished["id"], material["id"], 1, 1, 1)
    second_payload["cliente_nome"] = "Segundo cliente da fila"
    second = admin_client.post("/pedidos/", json=second_payload).json()

    active = [
        row for row in admin_client.get("/pedidos/").json()
        if not row["confirmado_em"] and not row["cancelado_em"]
    ]
    reordered_ids = [row["id"] for row in active]
    reordered_ids.remove(second["id"])
    reordered_ids.insert(0, second["id"])
    reordered = admin_client.put("/pedidos/fila", json={"pedidos_ids": reordered_ids})
    assert reordered.status_code == 200
    active_after = [
        row for row in reordered.json()
        if not row["confirmado_em"] and not row["cancelado_em"]
    ]
    assert [row["id"] for row in active_after] == reordered_ids

    priority = admin_client.post(f"/pedidos/{first['id']}/prioridade")
    assert priority.status_code == 200
    assert priority.json()["prioridade"] is True


def test_interface_de_pedidos_tem_divisao_materiais_e_fila(client):
    page = client.get("/").text
    script = client.get("/static/js/administration.js").text
    assert 'id="orderItems"' in page
    assert 'id="addOrderItem"' in page
    assert "order-material-list" in script
    assert "data-move-order" in script
    assert "dragstart" in script
    assert "/pedidos/fila" in script
    assert '/static/js/app.js?v=4.7.0' in page
