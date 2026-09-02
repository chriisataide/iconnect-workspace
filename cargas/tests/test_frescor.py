"""O contrato de frescor, finalmente respondido.

A Onda 1 construiu o carimbo com o contrato vazio: toda faixa dizia
"Workspace · em tempo real" porque todo número era do próprio produto. Este
arquivo prova que o carimbo passa a dizer "Sankhya · há 6 h" **sem nenhuma view
mudar** — que era o ponto de o contrato existir antes do primeiro conector.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from cargas.models import ExecucaoCarga, StatusCarga
from cargas.providers import FrescorDasCargas
from workspace.providers import frescor as contrato
from workspace.services import frescor as servico

pytestmark = pytest.mark.django_db


@pytest.fixture
def provedor(fontes):
    """O provedor registrado, e desregistrado ao fim.

    O registro é estado de processo: sem devolver, o provedor sobreviveria para
    os testes da Onda 1, que afirmam "sem registro de carga".
    """
    anterior = contrato.obter()
    contrato.registrar(FrescorDasCargas())
    yield
    contrato.limpar()
    if anterior is not None:
        contrato.registrar(anterior)


def _carga(fonte, *, status=StatusCarga.SUCESSO, ha=timedelta(hours=6), erro=""):
    instante = timezone.now() - ha
    return ExecucaoCarga.objects.create(
        fonte=fonte, iniciada_em=instante, terminada_em=instante,
        status=status, erro_resumo=erro,
    )


def test_o_carimbo_passa_a_dizer_a_idade_de_verdade(fontes, provedor):
    _carga(fontes["sankhya"])

    carimbo = servico.de("sankhya")

    assert carimbo.rotulo == "Sankhya"
    assert "há 6 h" in carimbo.texto
    assert not carimbo.alerta
    assert carimbo.conhecido


def test_carga_que_falhou_nao_avanca_o_relogio_do_dado(fontes, provedor):
    """O teste que mais importa aqui.

    A última carga BEM-SUCEDIDA data o dado que está na tela; a última TENTATIVA
    diz se a fonte está de pé. Se a falha avançasse o relógio, uma fonte
    quebrada há três dias pareceria fresca — o carimbo mentiroso que a Onda 1
    existe para impedir.
    """
    _carga(fontes["monday"], ha=timedelta(hours=6))
    _carga(fontes["monday"], ha=timedelta(minutes=5), status=StatusCarga.FALHA,
           erro="tempo esgotado ao coletar o board 4412")

    carimbo = servico.de("monday")

    assert "há 6 h" in carimbo.texto, "a idade é a do último dado BOM"
    assert carimbo.alerta
    assert carimbo.motivo == "tempo esgotado ao coletar o board 4412"


def test_fonte_velha_alem_do_que_ela_mesma_declarou_vira_alerta(fontes, provedor):
    """A idade máxima é da FONTE: duas horas é velho para o monday e é novo
    para a folha do Sankhya."""
    _carga(fontes["monday"], ha=timedelta(hours=5))
    _carga(fontes["sankhya"], ha=timedelta(hours=5))

    assert servico.de("monday").alerta is True
    assert servico.de("sankhya").alerta is False


def test_fonte_sem_carga_nenhuma_nao_finge_ter_carregado(fontes, provedor):
    carimbo = servico.de("sankhya")

    assert carimbo.idade == ""
    assert carimbo.conhecido, "a fonte É conhecida — o que falta é a carga"


def test_fonte_que_nao_existe_continua_sem_registro_de_carga(fontes, provedor):
    """`None` do provedor = "não sei nada sobre esta fonte".

    Diferente de "a fonte falhou", e a tela precisa dizer coisas diferentes.
    """
    carimbo = servico.de("erp_que_nao_temos")

    assert not carimbo.conhecido
    assert "sem registro de carga" in carimbo.texto


def test_a_competencia_pedida_vira_a_janela_do_carimbo(fontes, provedor):
    """"competência AGO/2026" diz mais do que qualquer descrição de cadência —
    é a leitura que muda o número."""
    from datetime import date

    _carga(fontes["sankhya"])

    assert "competência AGO/2026" in servico.de("sankhya", date(2026, 8, 1)).texto


def test_sem_competencia_vale_a_cadencia_prometida(fontes, provedor):
    _carga(fontes["monday"])

    assert "a cada 15 minutos" in servico.de("monday").texto


def test_o_carimbo_nativo_continua_sem_relogio(fontes, provedor):
    """Dado do próprio Workspace não ganha instante nem com provedor registrado.

    Relógio convida a comparar com dado que tem carga: "Workspace · 08:45" ao
    lado de "Sankhya · há 6 h" sugere que os dois são a mesma espécie de
    afirmação, e não são.
    """
    assert servico.de(servico.NATIVO).texto == "Workspace · em tempo real"
