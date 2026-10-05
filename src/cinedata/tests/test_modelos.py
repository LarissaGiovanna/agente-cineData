"""Testes da regra de fallback com modelos falsos (não chamam o OpenRouter, não gastam cota)."""

import pytest
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.fallback import FallbackModel
from pydantic_ai.models.function import FunctionModel

from cinedata.modelos import limite_da_conta, provider_lotado

CORPO_PROVIDER = {"error": {"message": "Provider returned error", "code": 429,
                            "metadata": {"provider_name": "Google AI Studio", "raw": "overloaded"}}}
CORPO_COTA_DIA = {"error": {"message": "Rate limit exceeded: free-models-per-day. Add 10 credits...",
                            "code": 429, "metadata": {"provider_name": None}}}
CORPO_COTA_MINUTO = {"error": {"message": "Rate limit exceeded: free-models-per-min.", "code": 429}}


def erro(status, corpo):
    return ModelHTTPError(status, "modelo-falso", corpo)


def test_classificacao_dos_erros():
    assert provider_lotado(erro(429, CORPO_PROVIDER))
    assert not limite_da_conta(erro(429, CORPO_PROVIDER))
    assert limite_da_conta(erro(429, CORPO_COTA_DIA)) and not provider_lotado(erro(429, CORPO_COTA_DIA))
    assert limite_da_conta(erro(429, CORPO_COTA_MINUTO))
    assert not provider_lotado(erro(401, {"error": {"message": "invalid key"}}))
    assert not provider_lotado(erro(500, "falha"))
    assert not provider_lotado(ValueError("qualquer outra coisa"))


def _modelo(resposta=None, falha=None):
    def funcao(mensagens, info):
        if falha is not None:
            raise falha
        return ModelResponse(parts=[TextPart(resposta)])

    return FunctionModel(funcao)


def test_provider_lotado_troca_para_o_proximo():
    modelo = FallbackModel(
        _modelo(falha=erro(429, CORPO_PROVIDER)), _modelo(resposta="veio do segundo"),
        fallback_on=provider_lotado,
    )
    assert Agent(modelo).run_sync("oi").output == "veio do segundo"


@pytest.mark.parametrize("corpo", [CORPO_COTA_DIA, CORPO_COTA_MINUTO])
def test_cota_da_conta_nao_troca_de_modelo(corpo):
    modelo = FallbackModel(
        _modelo(falha=erro(429, corpo)), _modelo(resposta="NÃO deveria chegar aqui"),
        fallback_on=provider_lotado,
    )
    with pytest.raises(ModelHTTPError):
        Agent(modelo).run_sync("oi")


def test_chave_invalida_nao_troca_de_modelo():
    modelo = FallbackModel(
        _modelo(falha=erro(401, {"error": {"message": "invalid key"}})), _modelo(resposta="não"),
        fallback_on=provider_lotado,
    )
    with pytest.raises(ModelHTTPError):
        Agent(modelo).run_sync("oi")
