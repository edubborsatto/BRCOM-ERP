from datetime import datetime, timedelta


def product_payload(code="PA-460", name="Produto simplificado"):
    return {
        "codigo": code,
        "nome": name,
        "tipo_item": "PRODUTO_ACABADO",
        "tipo": "Sling",
        "familia": "Elevação",
        "unidade_medida": "UN",
        "quantidade_atual": 8,
        "estoque_minimo": 2,
        "preco_custo": 40,
        "preco_venda": 75,
        "localizacao": "Galpão 2 — Prateleira A — Caixa 5",
        "especificacoes": "Texto livre",
    }


def test_produto_simplificado_busca_e_auditoria(admin_client):
    created = admin_client.post("/produtos/", json=product_payload())
    assert created.status_code == 201
    product = created.json()
    assert product["tipo"] == "Sling"
    assert product["localizacao"] == "Galpão 2 — Prateleira A — Caixa 5"

    result = admin_client.get("/produtos/?busca=Prateleira&familia=Elevação&tipo=Sling")
    assert result.status_code == 200
    assert [row["id"] for row in result.json()] == [product["id"]]

    updated = product_payload(name="Produto simplificado editado")
    updated["localizacao"] = "Local livre B-12"
    assert admin_client.put(f"/produtos/{product['id']}", json=updated).status_code == 200
    audit = admin_client.get(
        f"/historico/?produto_id={product['id']}&operacao=EDICAO&busca=localizacao"
    )
    assert audit.status_code == 200
    assert audit.json()[0]["usuario_responsavel"] == "Administrador"


def test_funcionario_nao_recebe_custo_nem_venda(client, admin_client):
    created = admin_client.post(
        "/produtos/", json=product_payload("PA-SIGILO", "Produto com preço sigiloso")
    )
    assert created.status_code == 201
    user = admin_client.post(
        "/usuarios/",
        json={
            "nome": "Operador de estoque",
            "usuario_login": "operador460",
            "senha": "SenhaOperador460!",
            "pode_movimentar_estoque": True,
        },
    )
    assert user.status_code == 201
    admin_client.post("/api/logout")
    assert client.post(
        "/api/login", json={"usuario_login": "operador460", "senha": "SenhaOperador460!"}
    ).status_code == 200
    product = next(row for row in client.get("/produtos/").json() if row["codigo"] == "PA-SIGILO")
    assert float(product["preco_custo"]) == 0
    assert float(product["preco_venda"]) == 0


def test_pedido_exige_documento_apenas_ao_confirmar(admin_client):
    delivery = (datetime.now() + timedelta(days=7)).isoformat()
    client = admin_client.post("/clientes/", json={"nome": "Cliente futuro"}).json()
    product = admin_client.post(
        "/produtos/", json=product_payload("PA-PEDIDO-460", "Cinta especial")
    ).json()
    order = admin_client.post(
        "/pedidos/",
        json={
            "cliente_id": client["id"],
            "itens": [{
                "produto_id": product["id"], "quantidade_total": 3,
                "quantidade_estoque": 3, "quantidade_fabricar": 0,
            }],
            "data_entrega": delivery,
        },
    )
    assert order.status_code == 201
    assert order.json()["numero_documento"] is None

    for status in ("AGUARDANDO_PRODUCAO", "EM_PRODUCAO", "PRODUCAO_CONCLUIDA", "SEPARADO", "PRONTO"):
        advanced = admin_client.post(
            f"/pedidos/{order.json()['id']}/status", json={"status": status}
        )
        assert advanced.status_code == 200

    empty = admin_client.post(
        f"/pedidos/{order.json()['id']}/confirmar-venda",
        json={"tipo_documento": "NOTA_FISCAL", "numero_documento": ""},
    )
    assert empty.status_code == 422
    confirmed = admin_client.post(
        f"/pedidos/{order.json()['id']}/confirmar-venda",
        json={"tipo_documento": "NOTA_FISCAL", "numero_documento": "NF-460"},
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "PRONTO"
    assert confirmed.json()["modalidade_entrega"] == "ENTREGA"
    delivered = admin_client.post(
        f"/pedidos/{order.json()['id']}/status", json={"status": "ENTREGUE"}
    )
    assert delivered.status_code == 200
    assert delivered.json()["status"] == "ENTREGUE"
    assert confirmed.json()["numero_documento"] == "NF-460"
    sale = admin_client.get("/vendas/").json()[-1]
    assert sale["pedido_futuro_id"] == order.json()["id"]

    second_product = admin_client.post(
        "/produtos/", json=product_payload("PA-PEDIDO-461", "Outro produto")
    ).json()
    second = admin_client.post(
        "/pedidos/",
        json={
            "cliente_id": client["id"],
            "itens": [{
                "produto_id": second_product["id"], "quantidade_total": 1,
                "quantidade_estoque": 1, "quantidade_fabricar": 0,
            }],
            "data_entrega": delivery,
        },
    )
    for status in ("AGUARDANDO_PRODUCAO", "EM_PRODUCAO", "PRODUCAO_CONCLUIDA", "SEPARADO", "PRONTO"):
        assert admin_client.post(
            f"/pedidos/{second.json()['id']}/status", json={"status": status}
        ).status_code == 200
    duplicate = admin_client.post(
        f"/pedidos/{second.json()['id']}/confirmar-venda",
        json={"tipo_documento": "NOTA_FISCAL", "numero_documento": "NF-460"},
    )
    assert duplicate.status_code == 409
