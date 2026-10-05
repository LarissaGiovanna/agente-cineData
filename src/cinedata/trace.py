"""Visualização do que o agente fez por dentro (ciclo ReAct)."""

from pydantic_ai import AgentRunResult
from pydantic_ai.messages import (
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)


def mostrar_trace(result: AgentRunResult) -> None:
    """Imprime passo a passo a conversa entre usuário, modelo e tools."""
    for msg in result.all_messages():
        for part in msg.parts:
            if isinstance(part, SystemPromptPart):
                continue
            if isinstance(part, UserPromptPart):
                print(f"[USUÁRIO]      {part.content}")
            elif isinstance(part, ToolCallPart) and part.tool_name.startswith("final_result"):
                print(f"[SAÍDA FINAL]  {part.args_as_dict()}")
            elif isinstance(part, ToolCallPart):
                print(f"[MODELO→TOOL]  {part.tool_name}({part.args_as_dict()})")
            elif isinstance(part, ToolReturnPart):
                if not part.tool_name.startswith("final_result"):
                    print(f"[TOOL→MODELO]  {part.tool_name} retornou: {part.content}")
            elif isinstance(part, RetryPromptPart):
                print(f"[RETRY]        {str(part.content).splitlines()[0][:200]}")
            elif isinstance(part, TextPart) and part.content.strip():
                print(f"[MODELO]       {part.content.strip()[:300]}")
    u = result.usage
    print(f"\n-- {u.requests} chamada(s) ao modelo | tokens entrada={u.input_tokens} saída={u.output_tokens}")
