"""Configuração compartilhada: chave de API, modelos e limites."""

import os
from getpass import getpass

from dotenv import load_dotenv

# Ordem de prioridade: se o provider do primeiro estiver lotado, tenta o segundo.
# Teste tool-calling em 05/10/2026: nemotron OK; z-ai/glm-5.2:free deu 404
# ("unavailable for free", slug aposentado) e foi removido; gemma deu 429
# upstream (provider lotado = caso que ativa o fallback).
MODELOS = [
    "nvidia/nemotron-3.5-lightning:free",
    "google/gemma-4-26b-a4b-it:free",
]

LIMITE_LINHAS = 50  # máximo de linhas que uma consulta devolve ao modelo
TIMEOUT_CONSULTA_S = 20  # segundos até abortar uma consulta lenta


def carregar_ambiente() -> None:
    """Carrega o `.env` e garante que a OPENROUTER_API_KEY exista.

    Se a chave não estiver no `.env`, pede para colar no terminal (mesmo padrão da aula).
    """
    load_dotenv()
    os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
    if not os.getenv("OPENROUTER_API_KEY"):
        os.environ["OPENROUTER_API_KEY"] = getpass("Cole sua OPENROUTER_API_KEY: ")
