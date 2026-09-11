"""O catálogo de equipamentos e o escopo do contrato — §H1.

A lista foi conferida com o dono do produto em 09/09/2026, e as quatro dúvidas
que eu tinha viraram estes testes: se alguém remover LPR, térmica ou cerca
elétrica achando que a ADB não vende, o teste reprova com a data da conferência
na docstring.
"""

from __future__ import annotations

import pytest

from resultados import equipamentos as eqp


def test_LPR_e_TERMICA_estao_no_catalogo():
    """Conferido: a ADB vende as duas. Eram a primeira dúvida da lista."""
    cftv = eqp.CATALOGO["CFTV"]

    assert any("LPR" in item for item in cftv)
    assert any("térmica" in item for item in cftv)


def test_CERCA_ELETRICA_e_escopo_da_empresa():
    """Conferido: não fica com terceiro."""
    assert "Cerca elétrica" in eqp.CATALOGO["Alarme e perimetral"]


def test_ECLUSA_e_TORNIQUETE_sao_itens_DIFERENTES():
    """Conferido: não são dois nomes da mesma coisa."""
    acesso = eqp.CATALOGO["Controle de acesso"]

    assert "Eclusa" in acesso and "Torniquete" in acesso


def test_a_central_de_monitoramento_e_PROPRIA():
    """Muda a conta em que o custo cai: `41101 Pessoal` e não `41401 Serviços
    PJ`. É a diferença entre um contrato que parece caro em gente e um que
    parece caro em terceiro."""
    assert any("própria" in item for item in eqp.CATALOGO["Monitoramento"])


def test_o_kit_de_neblina_e_ABERTO_item_a_item():
    """Cada ponto são vinte e nove itens que existem, são comprados e quebram.
    "3 pontos de neblina" esconderia todos eles."""
    total = sum(quantidade for quantidade, _ in eqp.KIT_DE_NEBLINA)

    assert total == 29
    assert dict((nome, q) for q, nome in eqp.KIT_DE_NEBLINA)["sensores sísmicos"] == 15


# ── O escopo em texto ───────────────────────────────────────────────


def test_o_predial_traz_os_numeros_reais():
    frase = eqp.escopo_predial(1.0)

    assert "800 câmeras" in frase
    assert "30 switches PoE" in frase
    assert "R$ 35.000" in frase


def test_a_rede_multiplica_por_unidade():
    """43 câmeras, 2 DVR e 3 kits por agência — os números reais."""
    frase = eqp.escopo_de_rede(100)

    assert "4.300 câmeras" in frase
    assert "200 DVR" in frase
    assert "300 pontos de neblina" in frase


def test_o_milhar_usa_PONTO_e_a_frase_mantem_as_virgulas():
    """Um `replace(",", ".")` global trocava as vírgulas da frase junto com os
    separadores — "800 câmeras. 30 switches" em vez de "800 câmeras, 30
    switches"."""
    frase = eqp.escopo_predial(1.0)

    assert "R$ 35.000 de cabeamento" in frase
    assert "câmeras, 30" in frase, "a vírgula da frase sobreviveu"


def test_os_dois_arquetipos_sao_DIFERENTES_em_formato():
    """Não diferem só em tamanho: o predial concentra num endereço e pesa em
    infraestrutura; a rede multiplica por unidade e pesa em deslocamento. Sem
    essa diferença todo contrato tem a mesma cara e o detalhamento por conta
    contábil não ensina nada."""
    predial = eqp.escopo_predial(1.0)
    rede = eqp.escopo_de_rede(340)

    assert "unidades" in rede and "unidades" not in predial
    assert "infraestrutura" in predial and "infraestrutura" not in rede


@pytest.mark.django_db
def test_a_massa_grava_o_escopo_nos_dois_formatos():
    from io import StringIO

    from django.core.management import call_command

    from resultados.models import Contrato

    saida = StringIO()
    call_command("semear_fontes", "--aplicar", stdout=saida)
    call_command("semear_plano_de_contas", "--aplicar", stdout=saida)
    call_command("semear_resultados", "--aplicar", stdout=saida)

    escopos = list(Contrato.objects.values_list("escopo", flat=True))

    assert all(escopos), "nenhum contrato sem escopo"
    assert any("unidades" in e for e in escopos), "falta um de rede"
    assert any("infraestrutura" in e for e in escopos), "falta um predial"
