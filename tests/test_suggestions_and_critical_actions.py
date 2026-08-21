import os


ADMIN_PASSWORD = "SenhaSeguraTeste123"


def _login(client, usuario, senha):
    client.post("/api/logout")
    response = client.post("/api/login", json={"usuario_login": usuario, "senha": senha})
    assert response.status_code == 200


def test_sugestao_funciona_sem_ia_e_notifica_admin_e_autor(admin_client):
    employee_password = "SenhaFuncionario123"
    created = admin_client.post("/usuarios/", json={
        "nome": "Funcionário Sugestões",
        "usuario_login": "func-sugestoes",
        "senha": employee_password,
        "tipo_usuario": "FUNCIONARIO",
    })
    assert created.status_code == 201

    _login(admin_client, "func-sugestoes", employee_password)
    draft = admin_client.post("/sugestoes/")
    assert draft.status_code == 201
    suggestion_id = draft.json()["id"]
    os.environ.pop("OPENAI_API_KEY", None)
    conversation = admin_client.post(
        f"/sugestoes/{suggestion_id}/mensagens",
        json={"conteudo": "Quero melhorar a conferência de estoque."},
    )
    assert conversation.status_code == 200
    assert conversation.json()["ai_available"] is False
    sent = admin_client.post(f"/sugestoes/{suggestion_id}/confirmar", json={
        "titulo": "Melhorar conferência de estoque",
        "descricao": "Criar uma conferência guiada para reduzir erros.",
        "modulo": "ESTOQUE",
        "resumo_ia": "Conferência guiada de estoque para os operadores.",
    })
    assert sent.status_code == 200
    assert sent.json()["numero"].startswith("SUG-")
    assert sent.json()["status"] == "ENVIADA"

    _login(admin_client, "admin", ADMIN_PASSWORD)
    notices = admin_client.get("/notificacoes/").json()
    assert any(item["entidade_id"] == suggestion_id for item in notices)
    updated = admin_client.patch(f"/sugestoes/{suggestion_id}", json={
        "status": "EM_ANALISE", "prioridade": "ALTA", "resposta": "Vamos avaliar o fluxo.",
    })
    assert updated.status_code == 200

    _login(admin_client, "func-sugestoes", employee_password)
    notices = admin_client.get("/notificacoes/").json()
    assert any("Em análise" in item["mensagem"] for item in notices)


def test_exclusao_definitiva_de_venda_revalida_senha(admin_client):
    client_record = admin_client.post("/clientes/", json={"nome": "Cliente Exclusão Venda"}).json()
    sale = admin_client.post("/vendas/", json={
        "cliente_id": client_record["id"],
        "tipo_documento": "RECIBO",
        "numero_documento": "TESTE-EXCLUSAO-001",
        "valor_total": 10,
        "data_venda": "2026-08-21",
    })
    assert sale.status_code == 201
    sale_id = sale.json()["id"]
    denied = admin_client.post(f"/vendas/{sale_id}/excluir-definitivamente", json={
        "senha": "senha-errada", "motivo": "Registro de teste criado por engano",
    })
    assert denied.status_code == 403
    deleted = admin_client.post(f"/vendas/{sale_id}/excluir-definitivamente", json={
        "senha": ADMIN_PASSWORD, "motivo": "Registro de teste criado por engano",
    })
    assert deleted.status_code == 200
    assert all(item["id"] != sale_id for item in admin_client.get("/vendas/").json())
    history = admin_client.get("/historico/sistema?modulo=VENDAS&acao=EXCLUIR_DEFINITIVAMENTE").json()
    assert any(item["entidade_id"] == sale_id for item in history)


def test_interface_expoe_agenda_sugestoes_notificacoes_e_confirmacao_critica(admin_client):
    page = admin_client.get("/").text
    administration = admin_client.get("/static/js/administration.js").text
    suggestions = admin_client.get("/static/js/suggestions.js").text
    assert 'id="agendaMonth"' in page and 'id="agendaYear"' in page
    assert 'id="sugestoesTab"' in page and 'id="notificacoesTab"' in page
    assert 'id="criticalActionPassword"' in page
    assert "data-open-agenda-record" in administration
    assert "/sugestoes/" in suggestions and "/notificacoes/" in suggestions
