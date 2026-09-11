"""Os dois comandos, e a simulação que é padrão em ambos."""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from cargas.models import ExecucaoCarga, FonteDados, RegraPrecedencia
from resultados.models import Contrato, Fonte as FonteEspelho
from cargas.models import Fonte as FonteCarga

pytestmark = pytest.mark.django_db


def _rodar(*args, **kwargs) -> str:
    saida = StringIO()
    call_command(*args, stdout=saida, stderr=saida, **kwargs)
    return saida.getvalue()


# ── semear_fontes ───────────────────────────────────────────────────


def test_semear_fontes_simula_por_padrao(db):
    saida = _rodar("semear_fontes")

    assert "SIMULAÇÃO" in saida
    assert not FonteDados.objects.exists()


def test_semear_fontes_cria_as_cinco_e_as_regras(db):
    _rodar("semear_fontes", "--aplicar")

    assert FonteDados.objects.count() == 5
    assert RegraPrecedencia.objects.count() == 4


def test_semear_de_novo_nao_duplica(db):
    _rodar("semear_fontes", "--aplicar")
    _rodar("semear_fontes", "--aplicar")

    assert FonteDados.objects.count() == 5
    assert RegraPrecedencia.objects.count() == 4


def test_semear_nao_reativa_fonte_desligada_a_mao(db):
    """Desativar uma fonte é decisão de quem opera, quase sempre no meio de um
    incidente. A semeadora não pode desfazê-la ao rodar de novo no deploy
    seguinte — que é justamente quando ela roda."""
    _rodar("semear_fontes", "--aplicar")
    FonteDados.objects.filter(chave=FonteCarga.MONDAY).update(ativa=False)

    _rodar("semear_fontes", "--aplicar")

    assert FonteDados.objects.get(chave=FonteCarga.MONDAY).ativa is False


# ── carregar_fonte ──────────────────────────────────────────────────


def test_carregar_simula_por_padrao(fontes, conector, contrato_bruto):
    conector("csv", [contrato_bruto()])

    saida = _rodar("carregar_fonte", "csv")

    assert "SIMULAÇÃO" in saida
    assert not Contrato.objects.exists()
    assert ExecucaoCarga.objects.get().simulacao is True


def test_carregar_relata_o_que_ignorou(fontes, conector, contrato_bruto):
    """`ignorados` é o número que o operador olha depois de rodar duas vezes."""
    conector("csv", [contrato_bruto()])
    _rodar("carregar_fonte", "csv", "--aplicar")

    saida = _rodar("carregar_fonte", "csv", "--aplicar")

    assert "ignorados 1" in saida


@pytest.mark.parametrize(
    ("competencia", "ultimo_dia"),
    [("2026-02", 28), ("2028-02", 29), ("2026-04", 30), ("2026-08", 31)],
)
def test_janela_vira_o_mes_inteiro(fontes, conector, contrato_bruto, competencia, ultimo_dia):
    """Mês inteiro e não "do dia 1 até hoje".

    Uma janela que terminasse hoje faria a carga do dia 30 trazer menos que a do
    dia 31, e o mesmo comando produziria números diferentes conforme a hora em
    que rodou — que é o pior defeito possível num relatório de fechamento.

    Fevereiro bissexto entra porque o último dia sai de `calendar.monthrange`, e
    um `28` escrito à mão passaria em 2026 e erraria em 2028.
    """
    falso = conector("csv", [contrato_bruto()])

    _rodar("carregar_fonte", "csv", "--janela", competencia, "--aplicar")

    janela = falso.janelas[0]
    assert (janela.de.day, janela.ate.day) == (1, ultimo_dia)


@pytest.mark.parametrize("texto", ["2026", "agosto", "2026-13-01"])
def test_janela_malformada_para_o_comando(fontes, conector, texto):
    conector("csv", [])

    with pytest.raises(CommandError):
        _rodar("carregar_fonte", "csv", "--janela", texto)


def test_fonte_desconhecida_nem_e_aceita_pelo_argparse(db):
    with pytest.raises(CommandError):
        _rodar("carregar_fonte", "tabelinha_do_excel")


# ── As duas listas de fonte ─────────────────────────────────────────


def test_as_duas_listas_de_fonte_batem():
    """`resultados` não importa `cargas`, então a lista está escrita duas vezes.

    Cinco linhas duplicadas é o preço de manter a direção da dependência. O que
    não dá para pagar é a divergência: uma fonte que existe de um lado e não do
    outro grava `fonte="monday"` num campo cujo `choices` não a conhece, e o
    erro só aparece no `/admin/`, muito depois.
    """
    assert dict(FonteCarga.choices) == dict(FonteEspelho.choices)
