"""O seeder de centros de custo — e o buraco que ele fecha.

`Lotacao.centro_custo_codigo` era semeado; `CentroCusto` não era. O ambiente
ficava num estado que confunde: toda pessoa com um código, nenhum código
existindo. A consequência aparecia longe daqui, na bandeja de aprovação —
"o CC 1042 não tem orçamento mensal definido, não consigo calcular o impacto
desta aprovação" —, e quem estava testando o fluxo concluía que a barra de
orçamento estava quebrada. Não estava: não havia o que ler.

Os códigos saem das LOTAÇÕES que existem no banco, e não de uma lista escrita
no comando. Lista fixa divergiria do organograma no dia seguinte ao primeiro
CSV importado.
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command

from financas.models import CentroCusto
from identidade.tests import fabricas as f

pytestmark = pytest.mark.django_db


def _com_codigo(nome, codigo):
    pessoa = f.pessoa(nome)
    f.lotar(pessoa, centro_custo_codigo=codigo)
    return pessoa


def test_sem_aplicar_nao_grava():
    """Todo seeder do produto roda em simulação. Sem a flag, ele mostra o que
    faria e desfaz a transação."""
    _com_codigo("ana", "1042")

    call_command("semear_centros_custo", stdout=StringIO())

    assert not CentroCusto.objects.exists()


def test_cria_um_centro_por_codigo_usado():
    _com_codigo("ana", "1042")
    _com_codigo("bia", "1055")

    call_command("semear_centros_custo", "--aplicar", stdout=StringIO())

    assert set(CentroCusto.objects.values_list("codigo", flat=True)) == {"1042", "1055"}


def test_o_codigo_repetido_vira_um_centro_so():
    _com_codigo("ana", "1042")
    _com_codigo("bia", "1042")

    call_command("semear_centros_custo", "--aplicar", stdout=StringIO())

    assert CentroCusto.objects.filter(codigo="1042").count() == 1


def test_e_reexecutavel():
    _com_codigo("ana", "1042")
    call_command("semear_centros_custo", "--aplicar", stdout=StringIO())

    saida = StringIO()
    call_command("semear_centros_custo", "--aplicar", stdout=saida)

    assert CentroCusto.objects.filter(codigo="1042").count() == 1
    assert "já existiam  1" in saida.getvalue()


def test_lotacao_sem_centro_de_custo_nao_vira_linha():
    """String vazia não é um código. Criar um `CentroCusto` de nome vazio
    encheria a lista de escolha com uma opção que não significa nada."""
    _com_codigo("ana", "")

    call_command("semear_centros_custo", "--aplicar", stdout=StringIO())

    assert not CentroCusto.objects.exists()


def test_o_orcamento_nasce_indefinido():
    """`None` e não zero: é decisão do Financeiro, e "não definido" é o que a
    bandeja precisa dizer enquanto ninguém decidiu. Um número aqui inventaria
    folga que a empresa não tem."""
    _com_codigo("ana", "1042")

    call_command("semear_centros_custo", "--aplicar", stdout=StringIO())

    assert CentroCusto.objects.get(codigo="1042").orcamento_mensal is None


def test_o_codigo_conhecido_ganha_nome_legivel():
    _com_codigo("ana", "1042")

    call_command("semear_centros_custo", "--aplicar", stdout=StringIO())

    assert CentroCusto.objects.get(codigo="1042").nome == "Operações · Matriz"


def test_o_codigo_desconhecido_usa_o_proprio_codigo_como_nome():
    """Feio e correto — o R.H. renomeia na tela de Pessoas. Pular o código
    seria deixar a lotação apontando para o nada de novo."""
    _com_codigo("ana", "7777")

    call_command("semear_centros_custo", "--aplicar", stdout=StringIO())

    assert CentroCusto.objects.get(codigo="7777").nome == "7777"
