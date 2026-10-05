"""Testes dos guardrails e do acesso ao banco. Não chamam o modelo (não gastam cota)."""

import sqlite3

import pytest

from cinedata import banco
from cinedata.banco import BancoIndisponivel, TABELAS_PERMITIDAS, executar_consulta
from cinedata.guardrails import validar_sql


@pytest.fixture
def db(tmp_path):
    """Cria um banco temporário pequeno, com as 10 tabelas permitidas e a alembic_version."""
    caminho = tmp_path / "teste.db"
    conn = sqlite3.connect(caminho)
    for tabela in TABELAS_PERMITIDAS:
        conn.execute(f"CREATE TABLE {tabela} (id INTEGER, nome TEXT)")
    conn.executemany("INSERT INTO dim_movies VALUES (?, ?)", [(i, f"Filme {i}") for i in range(1, 121)])
    conn.execute("CREATE TABLE alembic_version (version_num TEXT)")
    conn.execute("INSERT INTO alembic_version VALUES ('0001')")
    conn.commit()
    conn.close()
    return caminho


# ------------------------------------------------------------------ validar_sql


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT * FROM dim_movies",
        "select * from dim_movies;",
        "  WITH x AS (SELECT 1) SELECT * FROM x",
        "-- comentário\nSELECT 1",
        "/* bloco */ SELECT 1",
    ],
)
def test_validar_aceita_leitura(sql):
    assert validar_sql(sql) is None


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO dim_movies VALUES (1, 'x')",
        "UPDATE dim_movies SET nome = 'x'",
        "DELETE FROM dim_movies",
        "DROP TABLE dim_movies",
        "PRAGMA table_info(dim_movies)",
        "ATTACH DATABASE 'x.db' AS x",
        "-- SELECT disfarçado\nDELETE FROM dim_movies",
        "",
        "   ;  ",
    ],
)
def test_validar_barra_o_resto(sql):
    assert validar_sql(sql) is not None


# ------------------------------------------------------------------ executar_consulta


def test_consulta_simples(db):
    r = executar_consulta("SELECT id, nome FROM dim_movies WHERE id <= 3 ORDER BY id", caminho=db)
    assert r["colunas"] == ["id", "nome"]
    assert r["linhas"] == [[1, "Filme 1"], [2, "Filme 2"], [3, "Filme 3"]]
    assert r["truncado"] is False


def test_limite_de_linhas_trunca(db):
    r = executar_consulta("SELECT id FROM dim_movies", caminho=db, limite=50)
    assert len(r["linhas"]) == 50
    assert r["truncado"] is True


def test_cte_e_funcoes_funcionam(db):
    sql = "WITH t AS (SELECT id FROM dim_movies) SELECT ROUND(AVG(id), 1), date('now') FROM t"
    r = executar_consulta(sql, caminho=db)
    assert r["linhas"][0][0] == 60.5


def test_cte_recursiva_funciona(db):
    sql = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c LIMIT 5) SELECT COUNT(*) FROM c"
    assert executar_consulta(sql, caminho=db)["linhas"][0][0] == 5


def test_cte_nao_serve_para_burlar_a_lista(db):
    sql = "WITH c AS (SELECT * FROM alembic_version) SELECT * FROM c"
    with pytest.raises(sqlite3.DatabaseError):
        executar_consulta(sql, caminho=db)


@pytest.mark.parametrize("tabela", ["alembic_version", "sqlite_master"])
def test_tabela_fora_da_lista_e_negada(db, tabela):
    with pytest.raises(sqlite3.DatabaseError):
        executar_consulta(f"SELECT * FROM {tabela}", caminho=db)


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO dim_movies VALUES (999, 'x')",
        "DELETE FROM dim_movies",
        "DROP TABLE dim_movies",
        "WITH x AS (SELECT 1) DELETE FROM dim_movies",
    ],
)
def test_escrita_e_barrada_pelo_banco(db, sql):
    """Mesmo sem passar pelo validar_sql, o banco recusa e nada muda."""
    with pytest.raises(sqlite3.DatabaseError):
        executar_consulta(sql, caminho=db)
    r = executar_consulta("SELECT COUNT(*) FROM dim_movies", caminho=db)
    assert r["linhas"][0][0] == 120


def test_varios_comandos_de_uma_vez_sao_recusados(db):
    with pytest.raises(sqlite3.Error):
        executar_consulta("SELECT 1; DELETE FROM dim_movies", caminho=db)


def test_timeout_aborta_consulta_lenta(db, monkeypatch):
    monkeypatch.setattr(banco, "TIMEOUT_CONSULTA_S", 0.5)
    lenta = "WITH RECURSIVE c(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM c) SELECT COUNT(*) FROM c"
    with pytest.raises(sqlite3.OperationalError):
        executar_consulta(lenta, caminho=db)


def test_banco_ausente_da_mensagem_clara(tmp_path):
    with pytest.raises(BancoIndisponivel, match="data/"):
        executar_consulta("SELECT 1", caminho=tmp_path / "nao_existe.db")
