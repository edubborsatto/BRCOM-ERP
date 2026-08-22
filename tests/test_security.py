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


def test_cinco_erros_bloqueiam_recuperacao_por_email_e_alertam_admin(
    client, admin_client, monkeypatch,
):
    password = "SenhaBloqueioTeste123"
    created = admin_client.post(
        "/usuarios/",
        json={
            "nome": "Funcionário Protegido",
            "usuario_login": "func-protegido",
            "email": "protegido@brcom.test",
            "senha": password,
            "tipo_usuario": "FUNCIONARIO",
        },
    )
    assert created.status_code == 201
    admin_client.post("/api/logout")

    for attempt in range(1, 6):
        denied = client.post(
            "/api/login",
            json={"usuario_login": "func-protegido", "senha": "senha-errada"},
        )
        assert denied.status_code == (423 if attempt == 5 else 401)
    assert denied.json()["detail"]["code"] == "ACCOUNT_LOCKED"
    assert denied.json()["detail"]["recovery_available"] is True
    assert client.post(
        "/api/login",
        json={"usuario_login": "func-protegido", "senha": password},
    ).status_code == 423

    delivered = {}
    monkeypatch.setattr(
        "app.routers.auth.send_recovery_code",
        lambda email, code: delivered.update({"email": email, "code": code}),
    )
    requested = client.post(
        "/api/recuperacao/solicitar",
        json={"usuario_login": "func-protegido", "email": "protegido@brcom.test"},
    )
    assert requested.status_code == 202
    assert delivered["email"] == "protegido@brcom.test"
    assert len(delivered["code"]) == 6
    unlocked = client.post(
        "/api/recuperacao/confirmar",
        json={"usuario_login": "func-protegido", "codigo": delivered["code"]},
    )
    assert unlocked.status_code == 200
    assert client.post(
        "/api/login",
        json={"usuario_login": "func-protegido", "senha": password},
    ).status_code == 200
    client.post("/api/logout")

    assert client.post(
        "/api/login",
        json={"usuario_login": "admin", "senha": "SenhaSeguraTeste123"},
    ).status_code == 200
    notices = client.get("/notificacoes/").json()
    assert any("bloqueada" in item["titulo"].lower() for item in notices)
    audit = client.get("/historico/sistema?modulo=SEGURANCA").json()
    assert any(item["acao"] == "LOGIN_BLOQUEADO" for item in audit)


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
        json={"nome": "Cliente criado pelo funcionário"},
    ).status_code == 403
    assert client.post("/pedidos/", json={}).status_code == 403
    assert client.get("/relatorios/vendas").status_code == 403
    client.post("/api/logout")


def test_tres_perfis_e_confirmacao_especial(client, admin_client):
    owner = admin_client.post(
        "/usuarios/",
        json={
            "nome": "Dono Teste",
            "usuario_login": "dono",
            "senha": "SenhaDonoTeste123",
            "tipo_usuario": "DONO",
        },
    )
    assert owner.status_code == 201
    assert owner.json()["pode_ver_faturamento"] is True
    admin_client.post("/api/logout")
    assert client.post(
        "/api/login",
        json={"usuario_login": "dono", "senha": "SenhaDonoTeste123"},
    ).status_code == 200
    denied = client.post(
        "/usuarios/",
        json={
            "nome": "Desenvolvedor sem confirmação",
            "usuario_login": "dev-sem-confirmacao",
            "senha": "SenhaDevTeste123",
            "tipo_usuario": "DESENVOLVEDOR",
        },
    )
    assert denied.status_code == 409
    confirmed = client.post(
        "/usuarios/",
        json={
            "nome": "Desenvolvedor Confirmado",
            "usuario_login": "dev-confirmado",
            "senha": "SenhaDevTeste123",
            "tipo_usuario": "DESENVOLVEDOR",
            "confirmar_desenvolvedor": True,
        },
    )
    assert confirmed.status_code == 201
    assert confirmed.json()["pode_acessar_docs"] is True
    client.post("/api/logout")


def test_desativacao_preserva_usuario_e_bloqueia_login(client, admin_client):
    created = admin_client.post(
        "/usuarios/",
        json={
            "nome": "Usuário para desativar",
            "usuario_login": "inativo",
            "senha": "SenhaInativoTeste123",
            "tipo_usuario": "FUNCIONARIO",
        },
    ).json()
    assert admin_client.delete(f"/usuarios/{created['id']}").status_code == 200
    users = admin_client.get("/usuarios/").json()
    assert next(user for user in users if user["id"] == created["id"])["ativo"] is False
    audit = admin_client.get("/usuarios/auditoria").json()
    assert any(item["acao"] == "DESATIVADO" for item in audit)
    admin_client.post("/api/logout")
    assert client.post(
        "/api/login",
        json={"usuario_login": "inativo", "senha": "SenhaInativoTeste123"},
    ).status_code == 401


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
