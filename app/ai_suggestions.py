"""Integração isolada com a OpenAI para coleta de sugestões."""

import json
import logging
import os

import httpx

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Você entrevista um usuário do BRCom ERP para definir uma sugestão de melhoria.
Faça uma pergunta objetiva por vez e não encerre antes de entender: problema, mudança desejada,
módulo, usuários afetados, funcionamento esperado, resultado, exemplos e exceções.
Não invente dados nem solicite informações confidenciais."""

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "assistant_message": {"type": "string"},
        "ready": {"type": "boolean"},
        "title": {"type": ["string", "null"]},
        "module": {"type": ["string", "null"]},
        "summary": {"type": ["string", "null"]},
    },
    "required": ["assistant_message", "ready", "title", "module", "summary"],
    "additionalProperties": False,
}


class SuggestionAIUnavailable(RuntimeError):
    def __init__(self, message: str, code: str, diagnostic: str, request_id: str | None = None):
        super().__init__(message)
        self.code = code
        self.diagnostic = diagnostic
        self.request_id = request_id


def _http_failure(exc: httpx.HTTPStatusError) -> SuggestionAIUnavailable:
    response = exc.response
    request_id = response.headers.get("x-request-id")
    try:
        error = response.json().get("error", {})
    except (ValueError, AttributeError):
        error = {}
    api_code = error.get("code") or error.get("type") or f"http_{response.status_code}"
    diagnostic = f"OpenAI HTTP {response.status_code} · {api_code}"
    if request_id:
        diagnostic += f" · requisição {request_id}"
    logger.warning("Falha no assistente de sugestões: %s", diagnostic)

    if response.status_code in {401, 403}:
        message = "A integração da IA precisa de revisão administrativa. Sua conversa foi preservada."
        code = "authentication_or_permission"
    elif response.status_code == 429:
        message = "A IA atingiu um limite de uso ou saldo. Sua conversa foi preservada."
        code = "usage_limit"
    elif response.status_code >= 500:
        message = "O serviço de IA está instável no momento. Sua conversa foi preservada."
        code = "openai_unavailable"
    else:
        message = "A IA não conseguiu processar esta mensagem. Sua conversa foi preservada."
        code = "request_rejected"
    return SuggestionAIUnavailable(message, code, diagnostic, request_id)


def continue_interview(messages: list[dict[str, str]]) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SuggestionAIUnavailable(
            "A IA de sugestões ainda não está configurada. O restante do BRCom continua disponível.",
            "not_configured",
            "OPENAI_API_KEY ausente no servidor",
        )
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "instructions": SYSTEM_PROMPT,
        "input": messages,
        "temperature": 0.2,
        "text": {
            "format": {
                "type": "json_schema",
                "name": "brcom_suggestion_interview",
                "strict": True,
                "schema": OUTPUT_SCHEMA,
            }
        },
        # O histórico oficial fica no banco do BRCom, não duplicado na OpenAI.
        "store": False,
    }
    try:
        response = httpx.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise _http_failure(exc) from exc
    except httpx.RequestError as exc:
        diagnostic = f"Falha de rede ao acessar OpenAI: {type(exc).__name__}"
        logger.warning("Falha no assistente de sugestões: %s", diagnostic)
        raise SuggestionAIUnavailable(
            "Não foi possível alcançar o serviço de IA. Sua conversa foi preservada.",
            "network_error",
            diagnostic,
        ) from exc

    try:
        data = response.json()
        text = data.get("output_text")
        if not text:
            text = "".join(
                item.get("text", "")
                for output in data.get("output", [])
                for item in output.get("content", [])
                if item.get("type") == "output_text"
            )
        result = json.loads(text)
        if not isinstance(result.get("assistant_message"), str):
            raise ValueError("Resposta da IA sem mensagem")
        return result
    except (ValueError, json.JSONDecodeError, KeyError, TypeError) as exc:
        request_id = response.headers.get("x-request-id")
        diagnostic = "Resposta da OpenAI fora do formato esperado"
        if request_id:
            diagnostic += f" · requisição {request_id}"
        logger.warning("Falha no assistente de sugestões: %s", diagnostic)
        raise SuggestionAIUnavailable(
            "A resposta da IA não pôde ser interpretada. Sua conversa foi preservada.",
            "invalid_response",
            diagnostic,
            request_id,
        ) from exc
