"""`semear_areas` — o cadastro comercial, e não massa de demonstração.

A distinção decide o teste: `semear_resultados` enche o banco de dado fictício
para alguém conseguir olhar a tela, e some quando a massa é limpa. As cinco
áreas existem na empresa real, e são **idempotentes por código** — rodar de novo
atualiza nome e descrição sem duplicar nada.
"""

from __future__ import annotations

import pytest
from django.core.management import call_command

from cargas.management.commands.semear_areas import AREAS
from resultados.models import Area


def _rodar(*args) -> str:
    from io import StringIO

    saida = StringIO()
    call_command("semear_areas", *args, stdout=saida)
    return saida.getvalue()


@pytest.mark.django_db
def test_sem_aplicar_NAO_grava():
    """Simulação é o padrão em todo comando de carga deste produto: quem digita
    o nome errado num terminal de produção não deve descobrir gravando."""
    saida = _rodar()

    assert Area.objects.count() == 0
    assert "SIMULAÇÃO" in saida
    assert "5 criada(s)" in saida


@pytest.mark.django_db
def test_aplicar_cria_as_cinco():
    _rodar("--aplicar")

    assert Area.objects.count() == len(AREAS) == 5
    assert list(Area.objects.values_list("codigo", flat=True)) == [
        "area-01", "area-02", "area-03", "area-04", "area-05"
    ]


@pytest.mark.django_db
def test_a_descricao_diz_quais_clientes():
    """"Área 03" não diz nada a ninguém. Um filtro que exige conhecimento
    prévio é um filtro que só o autor usa."""
    _rodar("--aplicar")

    assert Area.objects.get(codigo="area-04").descricao == "Lojas Americanas"
    assert "Bradesco" in Area.objects.get(codigo="area-03").descricao


@pytest.mark.django_db
def test_rodar_de_novo_nao_duplica_e_nao_reescreve():
    _rodar("--aplicar")
    saida = _rodar("--aplicar")

    assert Area.objects.count() == 5
    assert "0 criada(s) · 0 atualizada(s) · 5 sem mudança" in saida


@pytest.mark.django_db
def test_atualiza_o_que_mudou_sem_recriar():
    """O agrupamento comercial muda com a estratégia de vendas, e o comando é o
    caminho de aplicar essa mudança sem migration.

    A CHAVE é o código: recriar a área mudaria o `pk` e soltaria todo contrato
    apontado para ela — `SET_NULL` faria a carteira inteira cair em "Sem área"
    em silêncio.
    """
    _rodar("--aplicar")
    area = Area.objects.get(codigo="area-01")
    pk_original = area.pk
    area.descricao = "outra coisa"
    area.save(update_fields=["descricao"])

    saida = _rodar("--aplicar")

    area.refresh_from_db()
    assert area.pk == pk_original, "a mesma linha, não uma nova"
    assert area.descricao == "Santander"
    assert "1 atualizada(s)" in saida


@pytest.mark.django_db
def test_o_contrato_agrupado_sobrevive_a_um_novo_semeio():
    """O que o teste acima protege, visto do outro lado."""
    from decimal import Decimal

    from resultados.models import Contrato, Fonte

    _rodar("--aplicar")
    contrato = Contrato.objects.create(
        fonte=Fonte.PLATFORM, chave_externa="x", codigo="C-1",
        nome_cliente="Cliente", servico="monitoramento", centro_custo="1042",
        area=Area.objects.get(codigo="area-01"), valor_mensal=Decimal("1"),
    )

    _rodar("--aplicar")

    contrato.refresh_from_db()
    assert contrato.area is not None
    assert contrato.area.codigo == "area-01"


@pytest.mark.django_db
def test_a_ordem_e_a_da_diretoria_e_nao_a_alfabetica():
    _rodar("--aplicar")

    assert [a.ordem for a in Area.objects.order_by("ordem")] == [1, 2, 3, 4, 5]
