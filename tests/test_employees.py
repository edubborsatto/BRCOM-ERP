def employee_payload(**overrides):
    data = {
        "nome_completo": "Marina da Silva",
        "nome_social": "Marina Silva",
        "cpf": "529.982.247-25",
        "rg": "48.123.456-7",
        "orgao_emissor_rg": "SSP",
        "uf_rg": "SP",
        "data_nascimento": "1992-05-10",
        "email_pessoal": "marina.pessoal@example.com",
        "email_corporativo": "marina@brcom.test",
        "celular": "(19) 99999-1000",
        "telefone": "(19) 3400-1000",
        "cep": "13468-871",
        "logradouro": "Rua Fortunata Isaura Salvador",
        "numero": "174",
        "complemento": "Sala 2",
        "bairro": "Jardim Terramérica 3",
        "cidade": "Americana",
        "uf": "SP",
        "pis_pasep": "123.45678.90-1",
        "ctps_numero": "1234567",
        "ctps_serie": "0012",
        "ctps_uf": "SP",
        "departamento": "Comercial",
        "cargo": "Analista de vendas",
        "tipo_contrato": "CLT",
        "data_admissao": "2024-02-01",
        "salario_base": 4200,
        "jornada_semanal": 44,
        "gestor": "Diretoria Comercial",
        "contato_emergencia_nome": "Carlos da Silva",
        "contato_emergencia_parentesco": "Irmão",
        "contato_emergencia_telefone": "(19) 98888-2000",
        "status": "ATIVO",
        "observacoes": "Cadastro funcional de teste",
    }
    data.update(overrides)
    return data


def test_funcionario_completo_sincroniza_acesso_e_preserva_historico(client, admin_client):
    linked_user = admin_client.post(
        "/usuarios/",
        json={
            "nome": "Nome anterior",
            "usuario_login": "marina-funcionario",
            "email": "anterior@brcom.test",
            "telefone": "19911112222",
            "senha": "SenhaMarinaTeste123",
            "tipo_usuario": "FUNCIONARIO",
        },
    )
    assert linked_user.status_code == 201

    created = admin_client.post(
        "/funcionarios/",
        json=employee_payload(usuario_id=linked_user.json()["id"]),
    )
    assert created.status_code == 201, created.text
    employee = created.json()
    assert employee["matricula"].startswith("FUNC-")
    assert employee["cpf"] == "52998224725"
    assert employee["celular"] == "19999991000"
    assert employee["usuario_login"] == "marina-funcionario"

    users = admin_client.get("/usuarios/").json()
    linked = next(item for item in users if item["id"] == linked_user.json()["id"])
    assert linked["nome"] == "Marina da Silva"
    assert linked["email"] == "marina@brcom.test"
    assert linked["telefone"] == "19999991000"

    listing = admin_client.get("/funcionarios/?busca=24725")
    assert listing.status_code == 200
    assert listing.json()[0]["cpf_mascarado"] == "***.***.***-25"
    assert "cpf" not in listing.json()[0]
    assert admin_client.get(f"/funcionarios/{employee['id']}").json()["rg"] == "48.123.456-7"

    duplicate = admin_client.post(
        "/funcionarios/",
        json=employee_payload(nome_completo="Outra pessoa", pis_pasep=None),
    )
    assert duplicate.status_code == 409

    terminated = admin_client.post(
        f"/funcionarios/{employee['id']}/status",
        json={
            "status": "DESLIGADO",
            "data_desligamento": "2026-08-22",
            "motivo": "Encerramento do vínculo de teste",
        },
    )
    assert terminated.status_code == 200
    assert terminated.json()["status"] == "DESLIGADO"
    admin_client.post("/api/logout")
    assert client.post(
        "/api/login",
        json={"usuario_login": "marina-funcionario", "senha": "SenhaMarinaTeste123"},
    ).status_code == 401
    assert client.post(
        "/api/login",
        json={"usuario_login": "admin", "senha": "SenhaSeguraTeste123"},
    ).status_code == 200

    reactivated = client.post(
        f"/funcionarios/{employee['id']}/status",
        json={"status": "ATIVO"},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["usuario_ativo"] is False
    client.post(
        f"/funcionarios/{employee['id']}/status",
        json={"status": "DESLIGADO", "motivo": "Cadastro criado para teste"},
    )
    assert client.post(
        f"/funcionarios/{employee['id']}/excluir-definitivamente",
        json={"senha": "senha-incorreta", "motivo": "Duplicidade"},
    ).status_code == 403
    deleted = client.post(
        f"/funcionarios/{employee['id']}/excluir-definitivamente",
        json={"senha": "SenhaSeguraTeste123", "motivo": "Duplicidade de teste"},
    )
    assert deleted.status_code == 200
    history = client.get("/historico/sistema?modulo=FUNCIONARIOS").json()
    assert any(item["acao"] == "EXCLUIDO_DEFINITIVAMENTE" for item in history)
    assert "52998224725" not in str(history)


def test_funcionario_sem_permissao_nao_acessa_dados(client, admin_client):
    created = admin_client.post(
        "/usuarios/",
        json={
            "nome": "Sem acesso ao RH",
            "usuario_login": "sem-acesso-rh",
            "email": "sem-rh@brcom.test",
            "senha": "SenhaSemAcessoRh123",
            "tipo_usuario": "FUNCIONARIO",
        },
    )
    assert created.status_code == 201
    assert created.json()["pode_gerenciar_funcionarios"] is False
    admin_client.post("/api/logout")
    assert client.post(
        "/api/login",
        json={"usuario_login": "sem-acesso-rh", "senha": "SenhaSemAcessoRh123"},
    ).status_code == 200
    assert client.get("/funcionarios/").status_code == 403
    assert client.get("/funcionarios/resumo").status_code == 403
    client.post("/api/logout")


def test_interface_exibe_funcionarios_e_logo_oficial(admin_client):
    page = admin_client.get("/")
    assert page.status_code == 200
    assert page.text.count('/static/img/brasil-comercial-logo.svg') == 2
    assert 'id="funcionariosTab"' in page.text
    assert 'id="employeeForm"' in page.text
    assert 'id="perm_employees"' in page.text
    assert '/static/js/app.js?v=5.4.0' in page.text
    assert "fa-boxes-stacked" not in page.text
    with open("static/js/app.js", encoding="utf-8") as app_source:
        assert "./employees.js?v=5.4.0" in app_source.read()
