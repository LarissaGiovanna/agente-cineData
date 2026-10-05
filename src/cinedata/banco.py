"""Acesso ao banco SQLite (camada Gold) em modo somente leitura.

Camada 3 dos guardrails: mesmo que o modelo gere um SQL perigoso e a validação do código
falhe, o próprio banco recusa qualquer escrita.
"""

import os
import sqlite3
import time
from pathlib import Path

from cinedata.config import LIMITE_LINHAS, TIMEOUT_CONSULTA_S

# O banco acompanha o pacote, em `src/cinedata/data`, independentemente do diretório atual.
CAMINHO_PADRAO = Path(__file__).resolve().parent / "data" / "cinerocket.db"
if os.getenv("CINEDATA_DB"):
    CAMINHO_PADRAO = Path(os.environ["CINEDATA_DB"])

# Só estas tabelas podem ser lidas (a `alembic_version` e as tabelas internas do SQLite ficam de fora).
TABELAS_PERMITIDAS = {
    "bridge_movie_company",
    "bridge_movie_genre",
    "bridge_movie_person",
    "dim_companies",
    "dim_genres",
    "dim_movies",
    "dim_people",
    "dim_reviews",
    "fact_movies_performance",
    "movie_reviews",
}


class BancoIndisponivel(FileNotFoundError):
    """O arquivo do banco não foi encontrado."""


def _criar_autorizador(tabelas_reais: set[str]):
    """Monta o autorizador. O SQLite chama a função devolvida para CADA operação de uma consulta.

    Só liberamos leitura das tabelas permitidas. Qualquer outra coisa (INSERT, UPDATE, DELETE,
    DROP, PRAGMA, ATTACH, leitura de tabela fora da lista...) é negada.

    `tabelas_reais` são as tabelas que existem de fato no arquivo. Numa consulta com WITH
    RECURSIVE o SQLite também "lê" o nome da própria CTE, que não é uma tabela real; por isso
    só negamos nomes que são tabelas reais fora da lista (ou tabelas internas `sqlite_*`).
    """

    def autorizador(acao, arg1, arg2, banco, origem):
        if acao == sqlite3.SQLITE_SELECT:
            return sqlite3.SQLITE_OK
        if acao == sqlite3.SQLITE_READ:  # arg1 = nome da tabela, arg2 = nome da coluna
            nome = (arg1 or "").lower()
            if nome in TABELAS_PERMITIDAS:
                return sqlite3.SQLITE_OK
            if nome in tabelas_reais or nome.startswith("sqlite_"):
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK  # nome de CTE
        if acao in (sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE):  # AVG, ROUND, date()...
            return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    return autorizador


def conectar(caminho: str | Path | None = None) -> sqlite3.Connection:
    """Abre o banco em modo somente leitura e instala o autorizador."""
    caminho = Path(caminho or CAMINHO_PADRAO).resolve()
    if not caminho.exists():
        raise BancoIndisponivel(
            f"Banco não encontrado em {caminho}. Baixe o cinerocket.db e coloque na pasta data/."
        )
    conn = sqlite3.connect(f"{caminho.as_uri()}?mode=ro", uri=True)  # mode=ro = só leitura
    # lista as tabelas reais ANTES de instalar o autorizador (depois, ler sqlite_master seria negado)
    tabelas_reais = {
        linha[0].lower() for linha in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    conn.set_authorizer(_criar_autorizador(tabelas_reais))
    return conn


def executar_consulta(
    sql: str, caminho: str | Path | None = None, limite: int = LIMITE_LINHAS
) -> dict:
    """Executa um SELECT e devolve {"colunas", "linhas", "truncado"}.

    - Devolve no máximo `limite` linhas (para não encher o contexto do modelo).
    - Aborta consultas que passarem de TIMEOUT_CONSULTA_S segundos.
    - Erros de SQL (sqlite3.Error) sobem para quem chamou tratar.
    """
    conn = conectar(caminho)
    inicio = time.monotonic()

    def _estourou() -> int:
        # o SQLite chama isto de tempos em tempos; devolver 1 interrompe a consulta
        return 1 if time.monotonic() - inicio > TIMEOUT_CONSULTA_S else 0

    conn.set_progress_handler(_estourou, 10_000)
    try:
        cur = conn.execute(sql)
        linhas = cur.fetchmany(limite + 1)  # pede uma a mais só para saber se havia mais
        colunas = [d[0] for d in cur.description]
    finally:
        conn.close()
    return {
        "colunas": colunas,
        "linhas": [list(linha) for linha in linhas[:limite]],
        "truncado": len(linhas) > limite,
    }
