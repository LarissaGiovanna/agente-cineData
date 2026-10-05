"""Teste mínimo de tool calling nos modelos da lista.

Gasta cerca de 2 requests por modelo (uma para o modelo pedir a ferramenta, outra para responder).
Rodar:  python scripts/teste_tool_calling.py
"""

from pydantic_ai import Agent
from pydantic_ai.messages import ToolCallPart

from cinedata.config import MODELOS, carregar_ambiente
from cinedata.modelos import criar_modelo, limite_da_conta
from cinedata.trace import mostrar_trace


def chamou_a_ferramenta(resultado) -> bool:
    """True se, em algum momento da conversa, o modelo pediu a ferramenta `somar`."""
    return any(
        isinstance(parte, ToolCallPart) and parte.tool_name == "somar"
        for mensagem in resultado.all_messages()
        for parte in mensagem.parts
    )


def testar(nome: str) -> None:
    agente = Agent(
        criar_modelo(nome),
        instructions="Responda em português, em uma frase. Para qualquer conta, use a ferramenta somar.",
    )

    @agente.tool_plain
    def somar(a: int, b: int) -> int:
        """Soma dois números inteiros."""
        return a + b

    try:
        resultado = agente.run_sync("Quanto é 17 + 25?")
    except Exception as erro:  # queremos ver qualquer falha, de qualquer modelo
        if limite_da_conta(erro):
            print("PARE: cota da conta esgotada (vale para todos os modelos).")
            raise SystemExit(1)
        print(f"FALHOU: {type(erro).__name__}: {str(erro)[:300]}")
        return

    mostrar_trace(resultado)
    if chamou_a_ferramenta(resultado):
        print("OK: o modelo chamou a ferramenta.")
    else:
        print("ATENÇÃO: o modelo respondeu SEM chamar a ferramenta.")


def main() -> None:
    carregar_ambiente()
    for nome in MODELOS:
        print("=" * 70)
        print(nome)
        testar(nome)


if __name__ == "__main__":
    main()
