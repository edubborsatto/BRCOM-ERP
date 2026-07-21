from datetime import date, timedelta


def produto(codigo, nome, tipo, quantidade, custo, venda=0):
    return {
        "codigo": codigo,
        "nome": nome,
        "tipo_item": tipo,
        "familia": "Teste operacional",
        "unidade_medida": "UN",
        "quantidade_atual": quantidade,
        "estoque_minimo": 1,
        "preco_custo": custo,
        "preco_venda": venda,
    }


def test_fluxo_orcamento_producao_venda_e_relatorios(admin_client):
    cliente = admin_client.post("/clientes/", json={"nome": "Cliente Fluxo"})
    assert cliente.status_code == 201

    materia = admin_client.post(
        "/produtos/",
        json=produto("MP-TESTE", "Matéria-prima Fluxo", "MATERIA_PRIMA", 100, 5),
    )
    acabado = admin_client.post(
        "/produtos/",
        json=produto("PA-TESTE", "Produto Acabado Fluxo", "PRODUTO_ACABADO", 0, 0),
    )
    assert materia.status_code == acabado.status_code == 201

    formula = admin_client.put(
        f"/formulas/{acabado.json()['id']}",
        json={
            "produto_id": acabado.json()["id"],
            "mao_de_obra": 10,
            "custos_adicionais": 2,
            "markup_percentual": 50,
            "componentes": [{
                "materia_prima_id": materia.json()["id"],
                "quantidade": 2,
                "perda_percentual": 10,
            }],
        },
    )
    assert formula.status_code == 200
    assert float(formula.json()["custo_total"]) == 23
    assert float(formula.json()["preco_sugerido"]) == 34.5

    orcamento = admin_client.post(
        "/orcamentos/",
        json={
            "cliente_id": cliente.json()["id"],
            "desconto": 3,
            "itens": [{"produto_id": acabado.json()["id"], "quantidade": 3}],
        },
    )
    assert orcamento.status_code == 201
    assert float(orcamento.json()["total"]) == 100.5

    aprovado = admin_client.post(
        f"/orcamentos/{orcamento.json()['id']}/aprovar",
        json={"data_limite": str(date.today() + timedelta(days=7))},
    )
    assert aprovado.status_code == 200
    assert aprovado.json()["ordem_servico_id"]

    os_id = aprovado.json()["ordem_servico_id"]
    conclusao = admin_client.post(f"/ordens-servico/{os_id}/concluir")
    assert conclusao.status_code == 200
    assert conclusao.json()["status"] == "CONCLUIDA"

    produtos = {p["codigo"]: p for p in admin_client.get("/produtos/").json()}
    assert float(produtos["MP-TESTE"]["quantidade_atual"]) == 93.4
    assert float(produtos["PA-TESTE"]["quantidade_atual"]) == 3

    venda = admin_client.post(
        "/vendas/",
        json={
            "cliente_id": cliente.json()["id"],
            "orcamento_id": orcamento.json()["id"],
            "ordem_servico_id": os_id,
            "tipo_documento": "NOTA_FISCAL",
            "numero_documento": "NF-TESTE",
            "valor_total": 100.5,
            "data_venda": str(date.today()),
        },
    )
    assert venda.status_code == 201
    resumo = admin_client.get("/relatorios/resumo").json()
    assert float(resumo["vendas_nota_fiscal"]) >= 100.5


def test_ajuste_e_exclusao_de_auditoria_exigem_regras(admin_client):
    produto_id = admin_client.get("/produtos/").json()[0]["id"]
    ajuste = admin_client.post(
        "/estoque/movimentacoes",
        json={
            "produto_id": produto_id,
            "tipo_movimentacao": "AJUSTE",
            "quantidade": 1,
            "saldo_final_ajuste": 7,
            "motivo": "Inventário de conferência",
        },
    )
    assert ajuste.status_code == 201
    assert float(ajuste.json()["saldo_apos"]) == 7


def test_historico_so_pode_ser_excluido_por_administrador(client, admin_client):
    registro_id = admin_client.get("/historico/").json()[0]["id"]
    criado = admin_client.post(
        "/usuarios/",
        json={
            "nome": "Auditor sem administração",
            "usuario_login": "auditor",
            "senha": "SenhaAuditorTeste123",
            "pode_gerenciar_historico": True,
        },
    )
    assert criado.status_code == 201
    admin_client.post("/api/logout")
    assert client.post(
        "/api/login",
        json={"usuario_login": "auditor", "senha": "SenhaAuditorTeste123"},
    ).status_code == 200
    assert client.delete(f"/historico/{registro_id}").status_code == 403
    client.post("/api/logout")


def test_interface_tem_menu_movel_e_arquivos_modulares(client):
    pagina = client.get("/")
    assert pagina.status_code == 200
    assert 'id="openMenu"' in pagina.text
    assert 'id="menuBackdrop"' in pagina.text
    assert '/static/js/app.js' in pagina.text
    assert client.get("/static/css/app.css").status_code == 200
