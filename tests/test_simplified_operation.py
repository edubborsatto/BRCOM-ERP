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
    order = admin_client.post(
        "/pedidos/",
        json={
            "cliente_nome": "Cliente futuro",
            "produto_nome": "Cinta especial",
            "quantidade": 3,
            "data_entrega": delivery,
        },
    )
    assert order.status_code == 201
    assert order.json()["numero_documento"] is None

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
    assert confirmed.json()["status"] == "Venda confirmada"
    assert confirmed.json()["numero_documento"] == "NF-460"

    second = admin_client.post(
        "/pedidos/",
        json={
            "cliente_nome": "Outro cliente",
            "produto_nome": "Outro produto",
            "quantidade": 1,
            "data_entrega": delivery,
        },
    )
    duplicate = admin_client.post(
        f"/pedidos/{second.json()['id']}/confirmar-venda",
        json={"tipo_documento": "NOTA_FISCAL", "numero_documento": "NF-460"},
    )
    assert duplicate.status_code == 409
