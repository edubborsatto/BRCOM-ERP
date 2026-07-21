def test_rota_privada_exige_login(client):
    assert client.get("/produtos/").status_code == 401
    assert client.get("/clientes/").status_code == 401


def test_login_cria_sessao_http_only(client):
    resposta = client.post(
        "/api/login",
        json={"usuario_login": "admin", "senha": "SenhaSeguraTeste123"},
    )
    assert resposta.status_code == 200
    assert "HttpOnly" in resposta.headers["set-cookie"]
    assert client.get("/api/me").json()["usuario_login"] == "admin"
    client.post("/api/logout")


def test_login_incorreto_e_rejeitado(client):
    resposta = client.post(
        "/api/login",
        json={"usuario_login": "admin", "senha": "senha-incorreta"},
    )
    assert resposta.status_code == 401


def test_senha_nunca_e_retornada(admin_client):
    resposta = admin_client.post(
        "/usuarios/",
        json={
            "nome": "Colaborador Teste",
            "usuario_login": "colaborador",
            "senha": "SenhaColaborador123",
            "pode_movimentar_estoque": False,
        },
    )
    assert resposta.status_code == 201
    assert "senha" not in resposta.json()

    lista = admin_client.get("/usuarios/")
    assert lista.status_code == 200
    assert all("senha_hash" not in usuario for usuario in lista.json())


def test_permissoes_sao_aplicadas_no_servidor(client, admin_client):
    admin_client.post("/api/logout")
    login = client.post(
        "/api/login",
        json={"usuario_login": "colaborador", "senha": "SenhaColaborador123"},
    )
    assert login.status_code == 200
    assert client.get("/usuarios/").status_code == 403
    assert client.post(
        "/clientes/",
        json={"nome": "Cliente bloqueado"},
    ).status_code == 403
    client.post("/api/logout")


def test_auditoria_usa_identidade_da_sessao(admin_client):
    produto = admin_client.post(
        "/produtos/?usuario_resp=Nome%20Forjado",
        json={
            "nome": "Produto de teste de segurança",
            "unidade_medida": "UN",
            "quantidade_atual": 2,
            "estoque_minimo": 1,
            "preco_custo": 10,
            "preco_venda": 20,
        },
    )
    assert produto.status_code == 201
    historico = admin_client.get("/historico/").json()
    assert historico[0]["usuario_responsavel"] == "Administrador"
