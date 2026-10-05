"""Loop do terminal: `cinedata` (ou `python -m cinedata.cli`).

- Guarda as últimas 4 trocas como histórico (janela 3-5 aprovada).
- /limpar apaga o cache; /sair encerra. Ctrl+C também encerra.
- Sem histórico usa o cache (resposta mostra "(do cache)", 0 requests).
"""

from cinedata.agente import perguntar
from cinedata.cache import limpar_cache
from cinedata.config import carregar_ambiente
from cinedata.modelos import MENSAGEM_COTA, limite_da_conta

JANELA_TROCAS = 4  # 4 trocas = até 8 mensagens no histórico
MENSAGENS_POR_TROCA = 2


def main() -> None:
    carregar_ambiente()
    historico: list = []
    print("CineData — pergunte sobre o catálogo de filmes. (/limpar apaga o cache, /sair sai)")
    while True:
        try:
            texto = input("\n> ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAté logo!")
            break
        if not texto:
            continue
        if texto.lower() in {"/sair", "/exit", "/quit"}:
            print("Até logo!")
            break
        if texto.lower() == "/limpar":
            print("Cache apagado." if limpar_cache() else "Cache já estava vazio.")
            historico = []
            continue
        try:
            resposta, resultado = perguntar(texto, historico=historico)
        except Exception as erro:
            if limite_da_conta(erro):
                print(MENSAGEM_COTA)
                continue
            print(f"Falhou: {type(erro).__name__}: {str(erro)[:300]}")
            continue
        if resultado is None:
            print(f"{resposta}\n(do cache, 0 requests)")
        else:
            print(resposta)
            historico = resultado.all_messages()[-(JANELA_TROCAS * MENSAGENS_POR_TROCA):]


if __name__ == "__main__":
    main()
