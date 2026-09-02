"""A layer — e a diferença entre "pequeno" e "ainda não dá para saber".

O benchmark converte porte em OBRIGAÇÃO: Layer 3 deve apresentação de resultado,
as outras não. É por isso que "sem amostra" não pode virar Layer 1 — um contrato
novo de R$ 90 mil/mês nasceria dispensado da obrigação que ele provavelmente terá
em março.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from resultados import services as svc

pytestmark = pytest.mark.django_db


def test_contrato_com_um_mes_nao_recebe_layer_1(contrato, competencia):
    """O teste que mais protege este arquivo.

    Layer 1 quer dizer "pequeno, e por isso dispensado". "Sem amostra" quer
    dizer "ainda não sei". Chamar o segundo de primeiro é como um contrato
    grande e novo escapa da apresentação no trimestre em que mais precisaria.
    """
    c = contrato()
    competencia(c, mes=1, receita="90000")

    layer = svc.layer_de(c)

    assert layer.valor == svc.SEM_AMOSTRA
    assert not layer.tem_amostra
    assert not layer.deve_apresentacao
    assert str(layer) == "sem amostra"


def test_dois_meses_ja_bastam_para_avaliar(contrato, competencia):
    c = contrato()
    competencia(c, mes=1, receita="90000")
    competencia(c, mes=2, receita="90000")

    assert svc.layer_de(c).valor == "1"


@pytest.mark.parametrize(
    ("mensal", "esperada"),
    [
        ("40000", "1"),    # ROB 240k — até 300k
        ("50000", "1"),    # ROB 300k — o limite ainda é Layer 1
        ("60000", "2"),    # ROB 360k
        ("100000", "2"),   # ROB 600k — o limite ainda é Layer 2
        ("150000", "3"),   # ROB 900k
    ],
)
def test_a_faixa_sai_da_rob_de_seis_meses(contrato, competencia, mensal, esperada):
    c = contrato()
    for mes in range(1, 7):
        competencia(c, mes=mes, receita=mensal)

    assert svc.layer_de(c).valor == esperada


def test_so_a_layer_3_deve_apresentacao(contrato, competencia):
    """Cobrar apresentação de quem não tem histórico é cobrar de quem ainda não
    tem o que apresentar. A pendência dele é ganhar histórico."""
    c = contrato()
    for mes in range(1, 7):
        competencia(c, mes=mes, receita="150000")

    assert svc.layer_de(c).deve_apresentacao is True


def test_a_janela_conta_meses_com_lancamento_e_nao_de_calendario(contrato, competencia):
    """Um contrato que existe há um ano e faturou em dois meses tem DOIS meses de
    amostra. A pergunta é quanto ele fatura, não há quanto tempo ele existe."""
    c = contrato()
    competencia(c, ano=2025, mes=3, receita="10000")
    competencia(c, ano=2026, mes=8, receita="10000")

    assert svc.layer_de(c).meses == 2


def test_a_janela_respeita_a_competencia_pedida(contrato, competencia):
    """A layer de agosto não pode enxergar setembro.

    Sem o corte, reabrir um relatório antigo mostraria a layer de hoje — e o
    número da reunião passada deixaria de bater com a ata.
    """
    c = contrato()
    competencia(c, ano=2026, mes=8, receita="10000")
    competencia(c, ano=2026, mes=9, receita="900000")

    assert svc.layer_de(c, ate=date(2026, 8, 31)).rob == Decimal("10000")


def test_pega_apenas_os_seis_meses_mais_recentes(contrato, competencia):
    c = contrato()
    for mes in range(1, 13):
        competencia(c, mes=mes, receita="10000")

    assert svc.layer_de(c).meses == svc.MESES_DA_ROB


# ── Margem ──────────────────────────────────────────────────────────


def test_margem_sem_receita_e_none_e_nao_zero(contrato, competencia):
    """Zero apareceria no bloco de deficitários.

    Um contrato sem lançamento não é um contrato no vermelho — e o bloco de
    deficitários é justamente onde ninguém pode aparecer por engano.
    """
    c = contrato()
    competencia(c, mes=1, receita="0")

    assert svc.margem_pct(list(c.competencias.all())) is None


def test_margem_negativa_e_deficitario(contrato, competencia):
    c = contrato()
    competencia(c, mes=1, receita="100000", margem_contribuicao=Decimal("-5000"))

    assert svc.margem_pct(list(c.competencias.all())) == Decimal("-5.00")
