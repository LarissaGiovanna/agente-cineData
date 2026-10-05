"""Agente Text-to-SQL do CineData (PydanticAI).

- 1 tool `consultar_banco(sql)`: valida (camada 2) e executa (camada 3).
  Erro de SQL volta como texto para o modelo corrigir e tentar de novo
  (retry, até 3 tentativas via `retries=2`). Não troca de modelo nesse caso.
- Troca de modelo só pelo FallbackModel (provider lotado), definido em modelos.py.
- `perguntar()`: usa o cache só quando NÃO há histórico; nunca guarda recusa/erro.
"""

import sqlite3

from pydantic_ai import Agent

from cinedata import banco
from cinedata.cache import consultar_cache, guardar_cache
from cinedata.guardrails import validar_sql
from cinedata.modelos import criar_modelo_com_fallback
from cinedata.prompt import montar_prompt

TENTATIVAS_MAX = 3  # 1 tentativa + 2 retries de SQL


def criar_agente() -> Agent:
    """Monta o agente com prompt, fallback de modelos e a tool de SQL."""
    agente = Agent(
        criar_modelo_com_fallback(),
        instructions=montar_prompt(),
        retries=TENTATIVAS_MAX - 1,
    )

    @agente.tool_plain
    def consultar_banco(sql: str) -> str:
        """Executa um SELECT no catálogo de filmes e devolve o resultado como texto.

        Use esta ferramenta para responder qualquer pergunta sobre filmes.
        Se voltar "recusado" ou "erro", corrija o SQL e tente de novo.
        """
        problema = validar_sql(sql)
        if problema is not None:
            return f"SQL recusado: {problema}"
        try:
            r = banco.executar_consulta(sql)
        except sqlite3.Error as erro:
            return f"Erro de SQL: {erro}. Corrija e tente de novo."
        texto = f"colunas: {r['colunas']}\n"
        texto += f"linhas ({len(r['linhas'])}): {r['linhas']}"
        if r["truncado"]:
            texto += f"\n(Mostrando {banco.LIMITE_LINHAS} de mais; refine com LIMIT.)"
        return texto

    return agente


def perguntar(pergunta: str, historico: list | None = None):
    """Versão síncrona, para o terminal (cli.py). No notebook, use perguntar_async.

    Devolve (resposta, resultado). Sem histórico: olha o cache (hit = 0 requests).
    """
    sem_historico = not historico
    if sem_historico:
        achou = consultar_cache(pergunta)
        if achou is not None:
            return achou, None
    agente = criar_agente()
    resultado = agente.run_sync(pergunta, message_history=historico or [])
    resposta = str(resultado.output)
    if sem_historico:
        guardar_cache(pergunta, resposta)
    return resposta, resultado


async def perguntar_async(pergunta: str, historico: list | None = None):
    """Versão assíncrona, para o notebook (await). Mesma regra de cache da sync."""
    sem_historico = not historico
    if sem_historico:
        achou = consultar_cache(pergunta)
        if achou is not None:
            return achou, None
    agente = criar_agente()
    resultado = await agente.run(pergunta, message_history=historico or [])
    resposta = str(resultado.output)
    if sem_historico:
        guardar_cache(pergunta, resposta)
    return resposta, resultado
