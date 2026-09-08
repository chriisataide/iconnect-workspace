"""Fixtures das cargas."""

from __future__ import annotations

from datetime import date

import pytest

from cargas.conectores import Janela, Registro, registro as reg
from cargas.conectores.base import ConectorBase
from cargas.models import Fonte, FonteDados


@pytest.fixture
def fontes(db):
    """As quatro fontes cadastradas, como `semear_fontes --aplicar` deixaria."""
    from django.core.management import call_command

    call_command("semear_fontes", "--aplicar", verbosity=0)
    return {f.chave: f for f in FonteDados.objects.all()}


class ConectorFalso(ConectorBase):
    """Um conector que devolve o que lhe deram.

    Existe para o teste do CARREGADOR não depender de nenhuma API. O que ele
    prova é o comportamento comum — idempotência, contagem, precedência,
    parcial —, e esse comportamento é o mesmo para os quatro conectores de
    verdade justamente porque nenhum deles grava.
    """

    def __init__(
        self, chave: str, registros, *, quebra_em=None,
        quebra_normalizando=None, disponivel=True, erro=None,
    ):
        self.chave = chave
        self._registros = list(registros)
        self._quebra_em = quebra_em
        # QUAL exceção a fonte levanta. O padrão é um `RuntimeError` genérico,
        # que é o caso comum; passar uma específica serve para os testes que
        # conferem COMO cada classe de erro é traduzida para a tela.
        self._erro = erro
        self._quebra_normalizando = quebra_normalizando
        self._disponivel = disponivel
        self.janelas = []

    def disponivel(self) -> bool:
        return self._disponivel

    def coletar(self, janela: Janela):
        self.janelas.append(janela)
        for i, registro in enumerate(self._registros):
            if self._quebra_em is not None and i == self._quebra_em:
                raise self._erro or RuntimeError("a fonte caiu no meio da coleta")
            yield {"_i": i, "registro": registro}

    def normalizar(self, bruto):
        for item in bruto:
            if self._quebra_normalizando is not None and item["_i"] == self._quebra_normalizando:
                # O defeito de programação típico: a fonte mudou um campo de
                # nome e o `normalizar` continua indexando o antigo.
                raise KeyError("coluna_que_sumiu")
            yield item["registro"]


@pytest.fixture
def conector():
    """Registra um conector falso e o remove ao fim.

    O registro é estado de PROCESSO. Sem devolver, o conector inventado aqui
    sobreviveria para os testes seguintes — e o próximo a falhar culparia o
    carregador.
    """
    criados = []

    def _criar(chave: str, registros, **kwargs):
        falso = ConectorFalso(chave, registros, **kwargs)
        reg.registrar(falso, substituir=True)
        criados.append(chave)
        return falso

    guardados = reg.todos()
    yield _criar
    reg.limpar()
    for conector in guardados.values():
        reg.registrar(conector, substituir=True)


@pytest.fixture
def contrato_bruto():
    def _fazer(codigo="C-100", **campos):
        dados = {
            "codigo": codigo,
            "nome_cliente": "Cliente Fictício",
            "servico": "cftv",
            "centro_custo": "1042",
            "regional": "Sudeste",
            "inicio_vigencia": date(2026, 1, 1),
            "fim_vigencia": date(2026, 12, 31),
            "valor_mensal": 12000,
            "status": "ativo",
            **campos,
        }
        return Registro(entidade="contrato", chave_externa=f"ext-{codigo}", dados=dados)

    return _fazer


@pytest.fixture
def rede_monday(monkeypatch):
    """Uma fila de respostas gravadas. Vale para qualquer conector — o nome ficou
    do primeiro uso, e renomeá-lo agora custaria mais do que vale."""
    import io
    import json

    from cargas import transporte

    class _Resposta(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def _preparar(*respostas):
        pedidos = []

        def _falso(requisicao, timeout=None):
            pedidos.append(requisicao)
            corpo = respostas[min(len(pedidos) - 1, len(respostas) - 1)]
            return _Resposta(json.dumps(corpo).encode())

        monkeypatch.setattr(transporte.urllib.request, "urlopen", _falso)
        return pedidos

    return _preparar


@pytest.fixture
def sankhya_env(settings):
    settings.SANKHYA_BASE_URL = "https://api.sankhya.com.br"
    settings.SANKHYA_CLIENT_ID = "cid"
    settings.SANKHYA_CLIENT_SECRET = "seg"
    settings.SANKHYA_TOKEN = "xtok"
    settings.SANKHYA_CONSULTAS = {
        "competencia": {
            "rootEntity": "VW_RESULTADO_CC",
            "campos": ("CHAVE", "CODCENCUS", "ANO", "MES"),
            "campo_data": "DTREF",
        }
    }
    return settings
