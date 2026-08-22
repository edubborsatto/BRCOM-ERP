from datetime import datetime, timedelta


def test_historico_de_pedidos_entregues_reutiliza_o_pedido_original(admin_client):
    client_record = admin_client.post(
        "/clientes/", json={"nome": "Cliente Histórico Entregas"}
    ).json()
    product = admin_client.post(
        "/produtos/",
        json={
            "codigo": "ENT-530",
            "nome": "Produto Entregue 5.3",
            "tipo_item": "PRODUTO_ACABADO",
            "unidade_medida": "UN",
            "quantidade_atual": 4,
            "estoque_minimo": 0,
            "preco_custo": 10,
            "preco_venda": 20,
        },
    ).json()
    order = admin_client.post(
        "/pedidos/",
        json={
            "cliente_id": client_record["id"],
            "data_entrega": (datetime.now() + timedelta(days=2)).isoformat(),
            "itens": [{
                "produto_id": product["id"],
                "quantidade_total": 2,
                "quantidade_estoque": 2,
                "quantidade_fabricar": 0,
            }],
        },
    ).json()
    for next_status in (
        "AGUARDANDO_PRODUCAO", "EM_PRODUCAO", "PRODUCAO_CONCLUIDA", "SEPARADO", "PRONTO",
    ):
        assert admin_client.post(
            f"/pedidos/{order['id']}/status", json={"status": next_status}
        ).status_code == 200
    assert admin_client.post(
        f"/pedidos/{order['id']}/confirmar-venda",
        json={
            "tipo_documento": "NOTA_FISCAL",
            "numero_documento": "NF-ENT-530",
            "modalidade_entrega": "ENTREGA",
        },
    ).status_code == 200
    completed = admin_client.post(
        f"/pedidos/{order['id']}/status", json={"status": "ENTREGUE"}
    )
    assert completed.status_code == 200
    assert completed.json()["concluido_em"]
    assert completed.json()["concluido_por_nome"] == "Administrador"

    history = admin_client.get("/pedidos/entregues?busca=NF-ENT-530&modalidade=ENTREGA")
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == [order["id"]]
    assert history.json()[0]["itens"][0]["produto_nome"] == "Produto Entregue 5.3"
