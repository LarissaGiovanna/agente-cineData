"""Guardrails no código (camada 2): validação do SQL antes de executar.

As três camadas são:
  1. o prompt (pede só SELECT e recusa o resto)
  2. esta validação (barra o que não parece uma consulta de leitura, com mensagem clara)
  3. o banco (conexão somente leitura + autorizador, em banco.py)
"""

import re

# Comentários SQL: `-- até o fim da linha` e `/* bloco */`
_COMENTARIOS = re.compile(r"--[^\n]*|/\*.*?\*/", re.DOTALL)

# Uma consulta de leitura começa com SELECT, ou com WITH (CTE) seguido de um SELECT.
_INICIOS_PERMITIDOS = {"SELECT", "WITH"}

MENSAGEM_SOMENTE_LEITURA = (
    "Só consultas de leitura são permitidas: o SQL deve começar com SELECT (ou WITH ... SELECT). "
    "Não é possível inserir, alterar ou apagar dados."
)


def validar_sql(sql: str) -> str | None:
    """Devolve None se o SQL é aceitável, ou uma mensagem explicando o problema.

    Não procuramos palavras como DELETE no meio do texto: isso daria falso alarme em
    consultas legítimas (ex.: títulos de filme que contêm "Drop" ou "Delete"). O que
    realmente barra escritas escondidas, como `WITH x AS (...) DELETE ...`, é o banco
    somente leitura com autorizador.
    """
    limpo = _COMENTARIOS.sub(" ", sql).strip().rstrip(";").strip()
    if not limpo:
        return "O SQL está vazio."
    primeira_palavra = limpo.split(None, 1)[0].upper()
    if primeira_palavra not in _INICIOS_PERMITIDOS:
        return MENSAGEM_SOMENTE_LEITURA
    return None
