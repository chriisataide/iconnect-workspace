"""O comparativo trimestral — F2.

O ponto do bloco é o trimestre PARCIAL. Comparar um trimestre de dois meses com
um de três, sem avisar, é o erro que mais gera decisão errada em reunião de
resultado: a barra menor é lida como queda, e a queda não existe.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from workspace.services import resultados as svc


class _Linha:
    def __init__(self, ano, mes, receita):
        self.ano, self.mes = ano, mes
        self.receita_bruta = Decimal(receita)


def _bloco(linhas, mes="2026-09"):
    return svc.trimestral(
        linhas, svc.ler_filtros({"mes": mes}, hoje=date(2026, 9, 1))
    )


def _cheio(ano, trimestre, valor="100"):
    base = (trimestre - 1) * 3 + 1
    return [_Linha(ano, base + i, valor) for i in range(3)]


def test_agrupa_por_trimestre_e_por_ano():
    bloco = _bloco(_cheio(2026, 1) + _cheio(2025, 1))

    assert [c.titulo for c in bloco.colunas] == ["Período", "2026", "2025"]
    assert bloco.linhas[0] == ["T1", "R$ 300,00", "R$ 300,00"]


def test_o_trimestre_PARCIAL_diz_quantos_meses_entraram():
    """"Parcial" sozinho não deixa ninguém corrigir de cabeça."""
    linhas = _cheio(2025, 1) + [_Linha(2026, 1, "100"), _Linha(2026, 2, "100")]

    bloco = _bloco(linhas)

    assert "parcial — 2 de 3 meses" in bloco.linhas[0][1]
    assert "parcial" not in bloco.linhas[0][2], "o ano completo não é marcado"


def test_um_mes_no_singular():
    linhas = _cheio(2025, 1) + [_Linha(2026, 1, "100")]

    assert "parcial — 1 de 3 mês" in _bloco(linhas).linhas[0][1]


def test_o_aviso_vai_para_a_TABELA_irma():
    """Sem JavaScript a tabela é o conteúdo, e um "parcial" que só existe no
    gráfico não existe."""
    linhas = _cheio(2025, 1) + [_Linha(2026, 1, "100"), _Linha(2026, 2, "100")]

    bloco = _bloco(linhas)

    assert any("parcial" in celula for linha in bloco.linhas for celula in linha)


def test_a_barra_parcial_e_marcada_ALEM_da_cor():
    """Opacidade e tracejado somem em preto-e-branco. O texto é o que sobra."""
    linhas = _cheio(2025, 1) + [_Linha(2026, 1, "100")]

    serie = _bloco(linhas).option["series"][0]
    barra = serie["data"][0]

    assert barra["itemStyle"]["borderType"] == "dashed"
    assert barra["itemStyle"]["opacity"] < 1
    assert "parcial" in barra["label"]["formatter"]


# ── Quando o bloco NÃO aparece ──────────────────────────────────────


def test_um_ano_so_NAO_vira_comparativo():
    assert _bloco(_cheio(2026, 1)) is None


def test_dois_anos_SEM_trimestre_em_comum_nao_viram_comparativo():
    """O defeito medido antes de o bloco buscar a própria janela: com doze
    meses havia 2026 e 2025, e nenhum trimestre tinha os dois — eram quatro
    barras de um ano ao lado de uma de outro."""
    assert _bloco(_cheio(2026, 1) + _cheio(2025, 4)) is None


def test_sem_serie_nao_ha_bloco():
    assert _bloco([]) is None


def test_sem_serie_nao_estoura():
    assert svc.trimestral(None, svc.ler_filtros({})) is None


# ── A janela ────────────────────────────────────────────────────────


def test_a_janela_longa_e_de_24_meses():
    """O seletor de período governa os gráficos mensais, e com a série dele
    nenhum trimestre tinha os dois anos.

    A busca dos vinte e quatro meses mora na faixa do dinheiro e é lida também
    pela tendência da safra (C5) — antes cada um buscava a sua, e a safra não
    buscava nenhuma."""
    assert svc.MESES_DO_TRIMESTRAL == 24


def test_mostra_no_maximo_tres_anos():
    """A quarta barra por trimestre não cabe com rótulo, e comparar quatro anos
    de uma vez não é pergunta que alguém faça de pé numa reunião."""
    linhas = sum((_cheio(ano, 1) for ano in (2026, 2025, 2024, 2023)), [])

    bloco = _bloco(linhas)

    assert [c.titulo for c in bloco.colunas] == ["Período", "2026", "2025", "2024"]
