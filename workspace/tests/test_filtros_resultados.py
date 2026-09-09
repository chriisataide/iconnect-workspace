"""Os filtros da Apresentação de Resultados — mês, período, área e serviço.

Escrito com a FASE 2 do plano de Resultados e Indicadores, em 08/09/2026.

## O que estes testes protegem

- **Link já compartilhado não quebra.** `?competencia=` e `?janela=` continuam
  sendo lidos por uma versão.
- **A caixa não encolhe.** Escolher uma área não pode apagar as outras da
  lista de opções — senão nunca dá para acrescentar a segunda.
- **A opção não revela o que a pessoa não alcança.** As opções saem do escopo
  dela, não do espelho inteiro.
- **A frase descreve o recorte.** É o que alguém lê ao receber o link.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.urls import reverse

from workspace.services import resultados as svc


COMPETENCIA = date(2026, 9, 1)


def _filtros(**parametros) -> svc.Filtros:
    return svc.ler_filtros(parametros, hoje=COMPETENCIA)


# ── A1 · competência vira mês, sem quebrar link ─────────────────────


def test_o_mes_e_lido_do_nome_novo():
    assert _filtros(mes="2026-07").competencia == date(2026, 7, 1)


def test_o_nome_ANTIGO_continua_sendo_lido():
    """Links de 2026 já circularam. Quebrá-los faria alguém abrir a tela no mês
    errado sem perceber — pior que o nome ruim que motivou a troca."""
    assert _filtros(competencia="2026-07").competencia == date(2026, 7, 1)


def test_com_os_dois_o_nome_novo_vence():
    """Quem monta a URL com os dois quis o que digitou por último, e o que
    digitou por último é o nome que a tela oferece hoje."""
    assert _filtros(mes="2026-07", competencia="2026-03").competencia == date(
        2026, 7, 1
    )


def test_a_url_GERADA_usa_o_nome_novo():
    """Ler o antigo e também PRODUZI-LO faria a compatibilidade nunca
    envelhecer, e nunca sair."""
    url = svc._url_com("/x", _filtros(mes="2026-07"))

    assert "mes=2026-07" in url
    assert "competencia=" not in url


# ── A2 · a janela vira período nomeado ──────────────────────────────


@pytest.mark.parametrize(
    "valor,meses", [("mes", 1), ("3m", 3), ("6m", 6), ("9m", 9), ("12m", 12)]
)
def test_cada_periodo_tem_o_tamanho_que_diz(valor, meses):
    assert _filtros(periodo=valor).meses == meses


def test_o_padrao_e_doze_meses():
    """Doze e não treze. Os treze existiam para o mesmo mês do ano anterior
    caber na série; a comparação anual passou a ser explícita, e a série volta a
    ter o tamanho que a pessoa pediu."""
    assert _filtros().periodo == "12m"
    assert _filtros().meses == 12


def test_periodo_impossivel_cai_no_padrao_e_nao_em_erro():
    """`?periodo=abacaxi` é URL digitada errada, não ataque — e responder 500
    ensinaria a não brincar com a barra de endereço, que é o contrário do que a
    tela quer."""
    assert _filtros(periodo="abacaxi").meses == 12


def test_a_janela_antiga_traduz_para_o_periodo_equivalente():
    """`?janela=6` já circulou em link. O número traduz direto."""
    assert _filtros(janela="6").periodo == "6m"
    assert _filtros(janela="3").periodo == "3m"


def test_janela_antiga_sem_periodo_exato_cai_no_menor_que_cabe():
    """`?janela=7` era aceito pelo inteiro livre — um recorte que a tela
    oferecia sem oferecer. Ele vira o maior período que não passa dele."""
    assert _filtros(janela="7").periodo == "6m"


def test_o_mes_atual_NAO_desenha_serie():
    """A regra antiga continua certa: abaixo de três meses o gráfico é uma
    comparação, e comparação se lê melhor em tabela. `so_o_mes` é o que faz a
    tela mostrar a tabela em vez de desenhar uma barra sozinha."""
    assert _filtros(periodo="mes").so_o_mes
    assert not _filtros(periodo="3m").so_o_mes


def test_o_periodo_entra_no_titulo_do_grafico():
    """No título e não só na barra: o gráfico é o que a pessoa fotografa e cola
    numa mensagem, e fora da tela ele perde o recorte."""
    assert _filtros(periodo="6m").rotulo_do_periodo == "últimos 6 meses"
    assert _filtros(periodo="mes").rotulo_do_periodo == "no mês"


# ── A5 · multi-seleção ──────────────────────────────────────────────


def test_area_e_servico_aceitam_varios_valores():
    from django.http import QueryDict

    parametros = QueryDict("area=area-01&area=area-03&servico=monitoramento")
    filtros = svc.ler_filtros(parametros, hoje=COMPETENCIA)

    assert filtros.area == ("area-01", "area-03")
    assert filtros.servico == ("monitoramento",)


def test_o_valor_repetido_entra_uma_vez_so():
    from django.http import QueryDict

    filtros = svc.ler_filtros(
        QueryDict("area=area-01&area=area-01"), hoje=COMPETENCIA
    )

    assert filtros.area == ("area-01",)


def test_a_ordem_da_escolha_e_preservada():
    """Ela aparece na frase do recorte. Ordenar mudaria o texto sozinho a cada
    recarga, e a pessoa acharia que a tela está reescrevendo o que ela pediu."""
    from django.http import QueryDict

    filtros = svc.ler_filtros(
        QueryDict("area=area-03&area=area-01"), hoje=COMPETENCIA
    )

    assert filtros.area == ("area-03", "area-01")


def test_ha_teto_para_uma_url_forjada():
    from django.http import QueryDict

    bruto = "&".join(f"area=a{n}" for n in range(200))
    filtros = svc.ler_filtros(QueryDict(bruto), hoje=COMPETENCIA)

    assert len(filtros.area) == svc.MAXIMO_MULTI


def test_dict_comum_tambem_funciona():
    """`ler_filtros` recebe `QueryDict` da tela e `dict` dos testes. Sem esse
    cuidado a mesma função devolveria coisas diferentes conforme quem chama — e
    o teste passaria enquanto a tela não funcionaria."""
    assert _filtros(area="area-01").area == ("area-01",)
    assert _filtros(area=["area-01", "area-03"]).area == ("area-01", "area-03")


def test_a_url_expande_cada_valor(monkeypatch):
    """`area=a&area=b` é a forma que `getlist` lê de volta. O par tem de casar,
    senão o link que a pessoa manda por e-mail abre com um filtro só."""
    from django.http import QueryDict

    filtros = svc.ler_filtros(
        QueryDict("area=area-01&area=area-03"), hoje=COMPETENCIA
    )
    url = svc._url_com("/x", filtros)

    assert url.count("area=") == 2
    assert svc.ler_filtros(
        QueryDict(url.split("?", 1)[1]), hoje=COMPETENCIA
    ).area == ("area-01", "area-03")


# ── A6 · a frase do recorte ─────────────────────────────────────────


AREAS = [
    {"codigo": "area-01", "nome": "Área 01"},
    {"codigo": "area-03", "nome": "Área 03"},
]


def test_a_frase_descreve_o_recorte_inteiro():
    from django.http import QueryDict

    filtros = svc.ler_filtros(
        QueryDict("area=area-01&area=area-03&servico=monitoramento&periodo=6m"),
        hoje=COMPETENCIA,
    )

    assert svc.recorte_em_texto(filtros, AREAS) == (
        "Área 01 e Área 03 · monitoramento · últimos 6 meses até 09/2026"
    )


def test_a_frase_usa_o_NOME_da_area_e_nao_o_codigo():
    """"area-03" não diz nada a quem recebe o link."""
    filtros = _filtros(area="area-03")

    assert "Área 03" in svc.recorte_em_texto(filtros, AREAS)
    assert "area-03" not in svc.recorte_em_texto(filtros, AREAS)


def test_sem_filtro_a_frase_diz_so_o_periodo():
    """Ela nunca some: o período é sempre um recorte, e não dizê-lo faria a
    pessoa supor o padrão errado."""
    assert svc.recorte_em_texto(_filtros(), AREAS) == (
        "últimos 12 meses até 09/2026"
    )


def test_a_frase_usa_E_e_nao_virgula_no_fim():
    from django.http import QueryDict

    filtros = svc.ler_filtros(
        QueryDict("servico=a&servico=b&servico=c"), hoje=COMPETENCIA
    )

    assert "a, b e c" in svc.recorte_em_texto(filtros, AREAS)
