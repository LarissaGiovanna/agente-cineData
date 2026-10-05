"""Modelos do OpenRouter e a regra de fallback entre eles.

Regra combinada: só troca de modelo quando o PROVIDER do modelo está lotado (erro 429 que vem
do provider). Não troca quando:
  - a cota do dia ou do minuto da conta acabou (vale para todos os modelos, trocar não adianta);
  - a chave é inválida (401);
  - o SQL veio errado (isso é retry de SQL, resolvido no agente, não troca de modelo).
"""

import os

from openai import AsyncOpenAI
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

from cinedata.config import MODELOS

OPENROUTER_URL = "https://openrouter.ai/api/v1"

MENSAGEM_COTA = (
    "A cota gratuita do OpenRouter acabou (limite por dia ou por minuto da conta). "
    "Trocar de modelo não resolve. A cota diária zera às 21h (horário de Brasília)."
)


def limite_da_conta(exc: Exception) -> bool:
    """True se o 429 veio do próprio OpenRouter por limite de uso da conta.

    Esse erro traz no corpo a mensagem "Rate limit exceeded: free-models-per-day" (ou "per-minute").
    """
    return (
        isinstance(exc, ModelHTTPError)
        and exc.status_code == 429
        and "free-models-per" in str(exc.body).lower()
    )


def provider_lotado(exc: Exception) -> bool:
    """True se é um 429 do provider do modelo (lotado). É o único gatilho do fallback."""
    return isinstance(exc, ModelHTTPError) and exc.status_code == 429 and not limite_da_conta(exc)


def criar_modelo(nome: str) -> OpenRouterModel:
    """Cria um modelo do OpenRouter SEM retries automáticos.

    O cliente da OpenAI repete sozinho as chamadas que falham, e cada repetição conta na cota
    de 50 requests por dia. Com `max_retries=0`, uma falha gasta uma request só.
    """
    cliente = AsyncOpenAI(
        base_url=OPENROUTER_URL,
        api_key=os.environ["OPENROUTER_API_KEY"],
        max_retries=0,
    )
    return OpenRouterModel(nome, provider=OpenRouterProvider(openai_client=cliente))


def criar_modelo_com_fallback(nomes: list[str] | None = None) -> FallbackModel:
    """Monta o modelo final: tenta o primeiro da lista e, se o provider estiver lotado, o próximo."""
    modelos = [criar_modelo(nome) for nome in (nomes or MODELOS)]
    return FallbackModel(*modelos, fallback_on=provider_lotado)
