"""Cache de perguntas repetidas + normalização.

Regras aprovadas:
- Normalizar: minúsculas, sem espaços extras, sem acentos, sem pontuação final (?!.).
- Guarda só pergunta normalizada -> resposta final, em `data/cache.json` (JSON simples).
- Só usa/grava cache quando a pergunta foi feita SEM histórico (quem chama garante).
- Erros e a recusa fora de escopo nunca entram no cache.
- `limpar_cache()` apaga o arquivo: é o que o comando /limpar chama.
"""

import json
import os
import re
import unicodedata
from pathlib import Path

CAMINHO_PADRAO = Path(__file__).resolve().parent / "data" / "cache.json"
if os.getenv("CINEDATA_CACHE"):
    CAMINHO_PADRAO = Path(os.environ["CINEDATA_CACHE"])

# A recusa fora de escopo (definida no prompt) nunca vai para o cache.
MARCADOR_RECUSA = "Só sei responder perguntas sobre o catálogo de filmes."


def normalizar_pergunta(pergunta: str) -> str:
    """Padroniza a pergunta para comparar repetições.

    Ex.: "  Qual o FILME mais LONGO?? " -> "qual o filme mais longo"
    """
    texto = pergunta.lower().strip()
    texto = re.sub(r"\s+", " ", texto)  # espaços extras e quebras de linha viram 1 espaço
    texto = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )  # tira acentos: é -> e
    return texto.rstrip("?!.,;:").strip()


def _carregar_tudo(caminho: str | Path | None = None) -> dict:
    caminho = Path(caminho or CAMINHO_PADRAO)
    if not caminho.exists():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def consultar_cache(pergunta: str, caminho: str | Path | None = None) -> str | None:
    """Devolve a resposta guardada, ou None se a pergunta nunca foi feita."""
    return _carregar_tudo(caminho).get(normalizar_pergunta(pergunta))


def deve_cachear(resposta: str) -> bool:
    """False para o que não pode ir ao cache: vazio, recusa ou mensagem de erro."""
    texto = (resposta or "").strip()
    if not texto:
        return False
    if MARCADOR_RECUSA in texto:
        return False
    if texto.startswith(("Desculpe, ", "Erro ")):
        return False
    return True


def guardar_cache(pergunta: str, resposta: str, caminho: str | Path | None = None) -> bool:
    """Guarda pergunta -> resposta final. Devolve False se a resposta não é cacheável."""
    if not deve_cachear(resposta):
        return False
    caminho = Path(caminho or CAMINHO_PADRAO)
    dados = _carregar_tudo(caminho)
    dados[normalizar_pergunta(pergunta)] = resposta
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
    return True


def limpar_cache(caminho: str | Path | None = None) -> bool:
    """Apaga o arquivo de cache. Devolve True se apagou, False se nem existia."""
    caminho = Path(caminho or CAMINHO_PADRAO)
    if caminho.exists():
        caminho.unlink()
        return True
    return False
