"""Centro de custo, lançamento e a normalização da competência.

O provider em si é testado em `workspace/tests/test_orcamento.py`, junto com a
barra tripla que o consome — é lá que o contrato se prova. Aqui ficam os models
e as duas regras que só este app conhece.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from financas.models import CentroCusto, Lancamento, competencia_de


@pytest.mark.django_db
def test_orcamento_vazio_e_diferente_de_zero():
    """`None` é "ninguém definiu"; `0` é "definiram zero".

    O campo do projeto anterior era obrigatório, então "não definido" era gravado
    como zero e o provider traduzia `0 → None` para não mostrar 0% ao aprovador —
    que ele leria como "tem folga". Nulo permite dizer as duas coisas.
    """
    sem = CentroCusto.objects.create(codigo="NULO", nome="Sem definir")
    zero = CentroCusto.objects.create(
        codigo="ZERO", nome="Zero", orcamento_mensal=Decimal("0")
    )

    assert sem.orcamento_mensal is None
    assert zero.orcamento_mensal == Decimal("0")


@pytest.mark.django_db
def test_codigo_e_unico():
    """É a chave de ligação com a lotação da pessoa. Duplicado dividiria o
    orçamento em dois lugares sem ninguém notar."""
    from django.db import IntegrityError

    CentroCusto.objects.create(codigo="1042", nome="Comercial")
    with pytest.raises(IntegrityError):
        CentroCusto.objects.create(codigo="1042", nome="Outro")


@pytest.mark.django_db
def test_ativos_filtra_encerrados():
    CentroCusto.objects.create(codigo="VIVO", nome="Ativo")
    CentroCusto.objects.create(codigo="MORTO", nome="Encerrado", ativo=False)

    assert {c.codigo for c in CentroCusto.objects.ativos()} == {"VIVO"}


@pytest.mark.django_db
def test_str_mostra_codigo_e_nome():
    """O admin lista centros de custo por aqui, e código sem nome não se escolhe."""
    cc = CentroCusto.objects.create(codigo="1042", nome="Comercial")
    assert str(cc) == "1042 · Comercial"


# ── A competência é o mês, não o dia ────────────────────────────────


@pytest.mark.parametrize(
    ("informada", "esperada"),
    [
        (date(2026, 8, 1), date(2026, 8, 1)),
        (date(2026, 8, 31), date(2026, 8, 1)),
        (date(2024, 2, 29), date(2024, 2, 1)),
        (date(2026, 12, 31), date(2026, 12, 1)),
    ],
)
def test_competencia_de_normaliza_para_o_dia_um(informada, esperada):
    assert competencia_de(informada) == esperada


@pytest.mark.django_db
def test_lancamento_normaliza_na_gravacao_e_nao_so_na_consulta():
    """Onde o risco de virada de mês passou a morar.

    Sem esta normalização, duas linhas do mesmo mês com dias diferentes somam em
    buckets distintos e o realizado sai menor do que é — o aprovador vê folga que
    não existe. Dezembro e fevereiro bissexto são os pontos onde cálculo de mês
    quebra, e estão cobertos no parametrize acima.
    """
    cc = CentroCusto.objects.create(codigo="1008", nome="TI")
    lancamento = Lancamento.objects.create(
        centro_custo=cc, valor=Decimal("100"), competencia=date(2026, 8, 27)
    )

    lancamento.refresh_from_db()
    assert lancamento.competencia == date(2026, 8, 1)


@pytest.mark.django_db
def test_do_mes_soma_o_mes_inteiro_independente_do_dia_informado():
    cc = CentroCusto.objects.create(codigo="1008", nome="TI")
    for dia in (1, 15, 31):
        Lancamento.objects.create(
            centro_custo=cc, valor=Decimal("10"), competencia=date(2026, 8, dia)
        )
    Lancamento.objects.create(
        centro_custo=cc, valor=Decimal("999"), competencia=date(2026, 7, 10)
    )

    do_mes = Lancamento.objects.do_mes("1008", date(2026, 8, 20))
    assert do_mes.count() == 3, "o dia informado na consulta também é normalizado"


@pytest.mark.django_db
def test_centro_de_custo_com_lancamento_nao_pode_ser_apagado():
    """`PROTECT` e não `CASCADE`: apagar o centro de custo levaria embora o
    histórico de gasto, que é justamente o que a auditoria procura."""
    from django.db.models import ProtectedError

    cc = CentroCusto.objects.create(codigo="1008", nome="TI")
    Lancamento.objects.create(centro_custo=cc, valor=Decimal("10"), competencia=date(2026, 8, 1))

    with pytest.raises(ProtectedError):
        cc.delete()


@pytest.mark.django_db
def test_str_do_lancamento_diz_centro_valor_e_mes():
    cc = CentroCusto.objects.create(codigo="1008", nome="TI")
    lancamento = Lancamento.objects.create(
        centro_custo=cc, valor=Decimal("1500.00"), competencia=date(2026, 8, 1)
    )
    assert str(lancamento) == "1008 · R$ 1500.00 · 08/2026"
