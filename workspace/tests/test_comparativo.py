"""A comparação com o período anterior — F1.

## Por que ela deixou de ser opcional

A série da tela tinha **treze** meses, e o décimo terceiro existia por um motivo
escrito: comparar com o mesmo mês do ano passado é a única leitura que separa
crescimento de sazonalidade.

Ao adotar o período nomeado (A2), o padrão passou a doze — e essa capacidade
**foi removida**. Ela não podia ficar em falta esperando uma fase seguinte: quem
abrisse a tela entre uma coisa e outra perderia a comparação sem que nada na
tela dissesse que ela existiu.

## O que estes testes protegem

- a janela comparada recua a JANELA INTEIRA, e não só o mês;
- a série antiga é alinhada por POSIÇÃO, porque os meses têm nomes diferentes;
- a variação aparece POR ESCRITO — duas curvas não dizem de quanto foi;
- sem período anterior não há variação, em vez de uma variação contra zero.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.services import resultados as svc


HOJE = date(2026, 9, 1)


@pytest.fixture
def espelho(db):
    """VINTE E QUATRO meses — e é o número que importa.

    As fixtures que já existem têm treze, o bastante para estreitar a janela.
    Aqui não basta: com treze meses a janela comparada cai fora do espelho, e
    todo teste da comparação passaria mostrando "sem período anterior" — que é
    o caso VAZIO, não o caso que estes testes existem para provar.

    Cenário pobre é a forma mais silenciosa de um teste não proteger.
    """
    from resultados.models import CompetenciaResultado, Contrato, Fonte

    contrato = Contrato.objects.create(
        fonte=Fonte.PLATFORM, chave_externa="plt-C-1", codigo="C-1",
        nome_cliente="Cliente 1", servico="monitoramento",
        centro_custo="1042", regional="Sudeste",
        valor_mensal=Decimal("100000"),
    )
    for atras in range(24):
        total = HOJE.year * 12 + (HOJE.month - 1) - atras
        ano, mes = total // 12, total % 12 + 1
        CompetenciaResultado.objects.create(
            fonte=Fonte.SANKHYA,
            chave_externa=f"snk-C-1-{ano}{mes:02d}",
            contrato=contrato, centro_custo="1042", ano=ano, mes=mes,
            # CRESCENTE: o mês mais recente vale mais que o de um ano atrás,
            # então a variação dá positivo e o teste distingue "subiu" de
            # "caiu". Com valor constante ela daria 0,0% e os dois casos
            # ficariam iguais.
            receita_bruta=Decimal("1000000") + Decimal("10000") * (24 - atras),
            receita_orcada=Decimal("1200000"),
            margem_contribuicao=Decimal("50000"),
            ebitda=Decimal("30000"),
        )
    return contrato


@pytest.fixture
def diretoria(db):
    pessoa = f.pessoa("diretor_comp", nome="Diretor")
    f.lotar(pessoa, centro_custo_codigo="1042")
    f.atribuir(
        pessoa,
        f.papel("diretoria_comparativo", ["eco.ler.global"], escopo="global"),
        escopo="global",
    )
    return pessoa


def _filtros(**parametros) -> svc.Filtros:
    return svc.ler_filtros(parametros, hoje=HOJE)


# ── A janela comparada ──────────────────────────────────────────────


def test_sem_comparacao_e_o_padrao():
    """Comparação que não se desliga acaba ficando ligada sem ninguém lembrar de
    a ter pedido."""
    assert _filtros().comparar == ""
    assert _filtros().de_comparado is None
    assert _filtros().ate_comparado is None


def test_o_ano_anterior_recua_a_janela_inteira():
    """Comparar seis meses de 2026 com UM mês de 2025 seria comparar coisas
    diferentes com a mesma altura na tela."""
    f = _filtros(comparar="ano_anterior", periodo="6m")

    assert (f.de, f.ate) == (date(2026, 4, 1), date(2026, 9, 30))
    assert (f.de_comparado, f.ate_comparado) == (date(2025, 4, 1), date(2025, 9, 30))


def test_dois_anos_recua_vinte_e_quatro_meses():
    f = _filtros(comparar="dois_anos")

    assert f.de_comparado == date(2023, 10, 1)
    assert f.ate_comparado == date(2024, 9, 30)


def test_a_janela_comparada_fecha_no_ultimo_dia_do_mes():
    """Fevereiro é onde um `dia=30` fixo quebraria."""
    f = svc.ler_filtros({"comparar": "ano_anterior"}, hoje=date(2026, 2, 1))

    assert f.ate_comparado == date(2025, 2, 28)


def test_comparacao_impossivel_cai_em_nenhuma_e_nao_em_erro():
    assert _filtros(comparar="abacaxi").comparar == ""
    assert _filtros(comparar="abacaxi").de_comparado is None


def test_a_comparacao_viaja_na_url():
    """Sem isso, mandar o link com a comparação ligada entregaria a tela sem
    ela — e as duas pessoas discutiriam números diferentes."""
    url = svc._url_com("/x", _filtros(comparar="ano_anterior"))

    assert "comparar=ano_anterior" in url


# ── O alinhamento por posição ───────────────────────────────────────


class _Linha:
    def __init__(self, ano, mes, valor):
        self.ano, self.mes = ano, mes
        self.receita_bruta = Decimal(valor)


def test_alinha_por_posicao_e_nao_por_rotulo():
    """09/25 e 09/26 são rótulos diferentes: casar por nome não casaria nada.

    A posição é o que faz "o primeiro mês da janela" encontrar "o primeiro mês
    da janela anterior".
    """
    atual = [_Linha(2026, 8, "10"), _Linha(2026, 9, "20")]
    antes = [_Linha(2025, 8, "1"), _Linha(2025, 9, "2")]

    assert svc._alinhar_por_posicao(atual, antes, "receita_bruta") == [
        Decimal("1"), Decimal("2")
    ]


def test_mes_sem_par_vira_ponto_AUSENTE_e_nao_zero():
    """Janelas de tamanhos diferentes acontecem quando o espelho não tem todos
    os meses do período anterior. Zero seria lido como "não faturou nada"."""
    atual = [_Linha(2026, 7, "10"), _Linha(2026, 8, "20"), _Linha(2026, 9, "30")]
    antes = [_Linha(2025, 7, "1")]

    assert svc._alinhar_por_posicao(atual, antes, "receita_bruta") == [
        Decimal("1"), None, None
    ]


def test_sobra_do_periodo_anterior_e_cortada():
    """Mais meses antes que agora não pode empurrar a linha para fora do
    gráfico."""
    atual = [_Linha(2026, 9, "10")]
    antes = [_Linha(2025, 8, "1"), _Linha(2025, 9, "2")]

    assert svc._alinhar_por_posicao(atual, antes, "receita_bruta") == [Decimal("1")]


# ── A variação, por escrito ─────────────────────────────────────────


def test_a_variacao_e_calculada_e_formatada_com_sinal():
    """Em variação a DIREÇÃO é a informação: "+2,3%" e "2,3%" não dizem a mesma
    coisa, e a segunda não diz nada."""
    atual = [_Linha(2026, 9, "110")]
    antes = [_Linha(2025, 9, "100")]

    texto = svc._comparacao_em_texto(atual, antes, _filtros(comparar="ano_anterior"))

    assert texto["variacao"] == Decimal("10.0")
    assert texto["variacao_texto"] == "+10,0%"
    assert texto["subiu"] is True


def test_a_queda_vem_com_sinal_negativo():
    texto = svc._comparacao_em_texto(
        [_Linha(2026, 9, "90")], [_Linha(2025, 9, "100")],
        _filtros(comparar="ano_anterior"),
    )

    assert texto["variacao_texto"] == "-10,0%"
    assert texto["subiu"] is False


def test_sem_periodo_anterior_NAO_ha_variacao():
    """Uma variação contra zero é sempre "+∞%", e mostrá-la seria pior que não
    mostrar nada.

    Medido na massa real: `?comparar=dois_anos` cai aqui, porque o espelho tem
    vinte e quatro meses e não há o que comparar antes deles.
    """
    assert svc._comparacao_em_texto([_Linha(2026, 9, "100")], [], _filtros()) is None
    assert (
        svc._comparacao_em_texto(
            [_Linha(2026, 9, "100")], [_Linha(2025, 9, "0")],
            _filtros(comparar="ano_anterior"),
        )
        is None
    )


def test_os_tres_numeros_aparecem_juntos():
    """A variação sozinha esconde a escala: +40% sobre um mês fraco e +40% sobre
    um mês forte pedem decisões diferentes."""
    texto = svc._comparacao_em_texto(
        [_Linha(2026, 9, "140")], [_Linha(2025, 9, "100")],
        _filtros(comparar="ano_anterior"),
    )

    assert texto["atual_texto"] and texto["anterior_texto"] and texto["variacao_texto"]


# ── Na tela ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_o_grafico_ganha_a_terceira_serie(client, espelho, diretoria):
    import json
    import re

    client.force_login(diretoria)
    html = client.get(
        reverse("workspace:resultados") + "?comparar=ano_anterior"
    ).content.decode()
    opcao = json.loads(
        re.search(r'id="grafico-dados-receita"[^>]*>(.*?)</script>', html, re.S).group(1)
    )

    assert [s["name"] for s in opcao["series"]] == [
        "Realizado", "Orçado", "Ano anterior", "% do orçado"
    ]


@pytest.mark.django_db
def test_a_terceira_serie_e_TRACEJADA_e_nao_so_de_outra_cor(client, espelho, diretoria):
    """"Isto não é deste período" precisa sobreviver à escala de cinza — a mesma
    razão que faz o trimestre parcial ser hachurado."""
    import json
    import re

    client.force_login(diretoria)
    html = client.get(
        reverse("workspace:resultados") + "?comparar=ano_anterior"
    ).content.decode()
    opcao = json.loads(
        re.search(r'id="grafico-dados-receita"[^>]*>(.*?)</script>', html, re.S).group(1)
    )
    comparada = next(s for s in opcao["series"] if s["name"] == "Ano anterior")

    assert comparada["lineStyle"]["type"] == "dashed"


@pytest.mark.django_db
def test_a_terceira_serie_fica_no_eixo_da_ESQUERDA(client, espelho, diretoria):
    """Ela está em reais, como as barras. No eixo direito — o do percentual —
    ela teria outra escala, e duas alturas iguais na tela significariam valores
    diferentes."""
    import json
    import re

    client.force_login(diretoria)
    html = client.get(
        reverse("workspace:resultados") + "?comparar=ano_anterior"
    ).content.decode()
    opcao = json.loads(
        re.search(r'id="grafico-dados-receita"[^>]*>(.*?)</script>', html, re.S).group(1)
    )
    comparada = next(s for s in opcao["series"] if s["name"] == "Ano anterior")
    razao = next(s for s in opcao["series"] if s["name"] == "% do orçado")

    assert comparada.get("yAxisIndex", 0) == 0
    assert razao["yAxisIndex"] == 1


@pytest.mark.django_db
def test_a_tabela_irma_ganha_a_coluna_junto(client, espelho, diretoria):
    """Sem JavaScript o gráfico não existe, e a tabela é o conteúdo. A
    comparação sumir ali seria perdê-la para quem mais depende dela."""
    client.force_login(diretoria)

    corpo = client.get(
        reverse("workspace:resultados") + "?comparar=ano_anterior"
    ).content.decode()

    assert "Ano anterior" in corpo


@pytest.mark.django_db
def test_sem_comparacao_o_grafico_tem_so_as_tres_series_de_sempre(
    client, espelho, diretoria
):
    """A comparação não pode aparecer sem ser pedida — ela dobra a informação do
    gráfico, e um gráfico que muda sozinho é um gráfico em que não se confia."""
    import json
    import re

    client.force_login(diretoria)
    html = client.get(reverse("workspace:resultados")).content.decode()
    opcao = json.loads(
        re.search(r'id="grafico-dados-receita"[^>]*>(.*?)</script>', html, re.S).group(1)
    )

    assert [s["name"] for s in opcao["series"]] == ["Realizado", "Orçado", "% do orçado"]


# ── O período no título — A2 ────────────────────────────────────────


def test_o_titulo_do_grafico_carrega_o_periodo():
    """O gráfico é o que a pessoa fotografa e cola numa mensagem. Fora da tela
    ele perde o recorte, e um de seis meses lido como se fosse de doze é o tipo
    de erro que ninguém percebe porque nada parece errado."""
    assert svc._titulo("Receita bruta", _filtros(periodo="6m")) == (
        "Receita bruta — últimos 6 meses"
    )
    assert svc._titulo("Receita bruta", _filtros(periodo="mes")) == (
        "Receita bruta — no mês"
    )
