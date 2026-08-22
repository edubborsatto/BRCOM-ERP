import os

import httpx


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


def test_chat_de_sugestao_conversa_com_openai_e_preserva_historico_local(
    admin_client, monkeypatch,
):
    captured = {}

    def fake_openai_post(url, headers, json, timeout):
        captured.update({"url": url, "headers": headers, "json": json, "timeout": timeout})
        request = httpx.Request("POST", url)
        return httpx.Response(200, request=request, json={
            "output": [{
                "content": [{
                    "type": "output_text",
                    "text": "{\"assistant_message\":\"Qual etapa deve melhorar?\","
                    "\"ready\":false,\"title\":null,\"module\":null,\"summary\":null}",
                }],
            }],
        })

    monkeypatch.setenv("OPENAI_API_KEY", "chave-somente-de-teste")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-4.1-mini")
    monkeypatch.setattr("app.ai_suggestions.httpx.post", fake_openai_post)
    draft = admin_client.post("/sugestoes/").json()
    response = admin_client.post(
        f"/sugestoes/{draft['id']}/mensagens",
        json={"conteudo": "Quero tornar a separação mais rápida."},
    )

    assert response.status_code == 200
    assert response.json()["ai_available"] is True
    assert response.json()["assistant_message"] == "Qual etapa deve melhorar?"
    assert captured["url"] == "https://api.openai.com/v1/responses"
    assert captured["json"]["store"] is False
    assert "chave-somente-de-teste" not in str(captured["json"])
    saved = admin_client.get(f"/sugestoes/{draft['id']}").json()
    assert [message["autor_tipo"] for message in saved["mensagens"]] == ["USUARIO", "IA"]
    assert saved["mensagens"][1]["conteudo"] == "Qual etapa deve melhorar?"


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
    app = admin_client.get("/static/js/app.js").text
    styles = admin_client.get("/static/css/app.css").text
    assert 'id="agendaMonth"' in page and 'id="agendaYear"' in page
    assert 'id="sugestoesTab"' in page and 'id="notificacoesTab"' in page
    assert 'id="suggestionChat"' in page and 'id="suggestionChatMinimize"' in page
    assert 'data-open-suggestion-chat' in page and 'data-theme-toggle' in page
    assert 'id="criticalActionPassword"' in page
    assert "data-open-agenda-record" in administration
    assert "/sugestoes/" in suggestions and "/notificacoes/" in suggestions
    assert "openSuggestionChat" in suggestions and "minimizeChat" in suggestions
    assert "brcom-theme" in app and "applyTheme" in app
    assert ".suggestion-chat.minimized" in styles
    assert 'html[data-theme="dark"]' in styles


def test_modulos_javascript_compartilham_a_mesma_versao_da_api(admin_client):
    module_names = [
        "app.js", "catalog.js", "operations.js", "administration.js",
        "imports.js", "sales-sheets.js", "suggestions.js",
    ]
    for module_name in module_names:
        source = admin_client.get(f"/static/js/{module_name}").text
        if "./api.js?v=" in source:
            assert "./api.js?v=5.2.0" in source
            assert "./api.js?v=5.1.0" not in source
            assert "./api.js?v=6.0.0" not in source
