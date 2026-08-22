"""Integração isolada com a OpenAI para coleta de sugestões."""
import json
import os

import httpx


SYSTEM_PROMPT = """Você entrevista um usuário do BRCom ERP para definir uma sugestão de melhoria.
Faça uma pergunta objetiva por vez e não encerre antes de entender: problema, mudança desejada,
módulo, usuários afetados, funcionamento esperado, resultado, exemplos e exceções.
Responda SOMENTE em JSON válido com as chaves assistant_message, ready, title, module e summary.
ready deve ser false enquanto faltar informação. Quando ready for true, assistant_message deve
pedir confirmação explícita do resumo. Não invente dados nem solicite informações confidenciais."""


class SuggestionAIUnavailable(RuntimeError):
    pass


def continue_interview(messages: list[dict[str, str]]) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SuggestionAIUnavailable(
            "A IA de sugestões ainda não está configurada. O restante do BRCom continua disponível."
        )
    payload = {
        "model": os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        "instructions": SYSTEM_PROMPT,
        "input": messages,
        "temperature": 0.2,
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
    except (httpx.HTTPError, ValueError, json.JSONDecodeError, KeyError) as exc:
        raise SuggestionAIUnavailable(
            "A IA de sugestões está temporariamente indisponível. Sua conversa foi preservada."
        ) from exc
