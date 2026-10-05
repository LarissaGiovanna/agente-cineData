"""Loop do terminal: `cinedata` (ou `python -m cinedata.cli`).

Visual estilo opencode, só com stdlib (sem dependência nova):
- cores ANSI (desligam com NO_COLOR ou sem tty), spinner de loading em thread
  enquanto o modelo busca/pensa, atalhos /ajuda /limpar /sair e Ctrl+C.
- Guarda as últimas 4 trocas como histórico (janela 3-5 aprovada).
- Sem histórico usa o cache (resposta mostra "(do cache)", 0 requests).
"""

import itertools
import os
import sys
import threading
import time

from cinedata.agente import perguntar
from cinedata.cache import limpar_cache
from cinedata.config import carregar_ambiente
from cinedata.modelos import MENSAGEM_COTA, limite_da_conta

JANELA_TROCAS = 4  # 4 trocas = até 8 mensagens no histórico
MENSAGENS_POR_TROCA = 2

_COR = sys.stdout.isatty() and not os.getenv("NO_COLOR")
_RESET, _CIANO, _VERDE, _AMARELO, _CINZA, _VERMELHO = (
    ("", "", "", "", "", "")
    if not _COR
    else ("\033[0m", "\033[36m", "\033[32m", "\033[33m", "\033[90m", "\033[31m")
)


class Spinner:
    """Indicador 'pensando...' em thread separada (o perguntar() bloqueia)."""

    def __init__(self, texto: str = "buscando no catálogo...") -> None:
        self._texto = texto
        self._parar = threading.Event()
        self._t: threading.Thread | None = None

    def __enter__(self):
        if not _COR:  # sem tty: imprime linha simples, sem animação
            print(self._texto, flush=True)
            return self
        self._t = threading.Thread(target=self._rodar, daemon=True)
        self._t.start()
        return self

    def _rodar(self) -> None:
        for ch in itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"):
            if self._parar.is_set():
                break
            sys.stdout.write(f"\r{_CINZA}{ch} {self._texto}{_RESET}")
            sys.stdout.flush()
            time.sleep(0.08)
        sys.stdout.write("\r" + " " * (len(self._texto) + 4) + "\r")
        sys.stdout.flush()

    def __exit__(self, *args) -> None:
        self._parar.set()
        if self._t is not None:
            self._t.join()


def _ajuda() -> None:
    print(
        f"{_CIANO}Comandos:{_RESET}\n"
        "  /ajuda   mostra esta ajuda\n"
        "  /limpar  apaga o cache e zera o histórico\n"
        "  /sair    encerra (vale /exit, /quit e Ctrl+C)"
    )


def main() -> None:
    carregar_ambiente()
    historico: list = []
    print(f"{_CIANO}◆ CineData{_RESET} — pergunte sobre o catálogo de filmes. {_CINZA}(digite /ajuda){_RESET}")
    while True:
        try:
            texto = input(f"\n{_VERDE}❯{_RESET} ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{_AMARELO}Até logo!{_RESET}")
            break
        if not texto:
            continue
        baixo = texto.lower()
        if baixo in {"/sair", "/exit", "/quit"}:
            print(f"\n{_AMARELO}Até logo!{_RESET}")
            break
        if baixo == "/ajuda":
            _ajuda()
            continue
        if baixo == "/limpar":
            print("Cache apagado." if limpar_cache() else "Cache já estava vazio.")
            historico = []
            continue
        try:
            with Spinner():
                resposta, resultado = perguntar(texto, historico=historico)
        except Exception as erro:
            if limite_da_conta(erro):
                print(f"{_VERMELHO}{MENSAGEM_COTA}{_RESET}")
                continue
            print(f"{_VERMELHO}Falhou: {type(erro).__name__}: {str(erro)[:300]}{_RESET}")
            continue
        if resultado is None:
            print(f"{_AMARELO}{resposta}{_RESET}\n{_CINZA}(do cache, 0 requests){_RESET}")
        else:
            print(f"{_AMARELO}{resposta}{_RESET}")
            historico = resultado.all_messages()[-(JANELA_TROCAS * MENSAGENS_POR_TROCA):]


if __name__ == "__main__":
    main()
