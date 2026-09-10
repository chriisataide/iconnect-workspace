"""As safras — C5. "As perdas de 2023 ainda estão pesando?"

A safra é DERIVADA do ano de entrada (`C`) ou de saída (`P`). Nenhum campo novo
no espelho: a data já está lá, e um terceiro lugar guardando o mesmo fato
divergiria dela sem ninguém saber qual das duas está certa.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from workspace.services import resultados as svc


class _Contrato:
    def __init__(self, codigo, inicio=None, fim=None, status="ativo"):
        self.codigo = codigo
        self.inicio_vigencia = inicio
        self.fim_vigencia = fim
        self.status = status


class _Linha:
    def __init__(self, ano, mes, receita, contrato):
        self.ano, self.mes = ano, mes
        self.receita_bruta = Decimal(receita)
        self.contrato = contrato


def test_conquista_sai_do_ano_de_ENTRADA():
    c = _Contrato("A", inicio=date(2023, 4, 1))

    assert svc._safra_de(c) == "C2023"


def test_perda_sai_do_ano_de_SAIDA():
    c = _Contrato("A", inicio=date(2019, 1, 1), fim=date(2023, 8, 1),
                  status="encerrado")

    assert svc._safra_de(c) == "P2023"


def test_encerrado_e_PERDA_mesmo_tendo_data_de_entrada():
    """Um contrato que entrou em 2019 e saiu em 2023 pesa como perda de 2023 —
    é essa a pergunta que a safra responde."""
    c = _Contrato("A", inicio=date(2019, 1, 1), fim=date(2023, 8, 1),
                  status="encerrado")

    assert svc._safra_de(c).startswith("P")


def test_contrato_sem_data_nao_tem_safra():
    assert svc._safra_de(_Contrato("A")) is None


def test_a_lista_sai_do_que_EXISTE_na_carteira():
    """`C2016…C2026` fixo ofereceria safras vazias, e um filtro que devolve
    vazio parece quebrado."""
    carteira = [
        _Contrato("A", inicio=date(2024, 1, 1)),
        _Contrato("B", inicio=date(2024, 6, 1)),
        _Contrato("C", inicio=date(2020, 1, 1), fim=date(2026, 2, 1),
                  status="encerrado"),
    ]

    safras = svc.safras_da_carteira(carteira)

    assert [s["chave"] for s in safras] == ["P2026", "C2024"]
    assert dict((s["chave"], s["quantos"]) for s in safras)["C2024"] == 2


def test_a_safra_de_perda_e_marcada_ALEM_do_prefixo():
    """A lista mistura `C2023` e `P2023`, e a letra sozinha exige leitura atenta
    de uma lista de vinte chips."""
    carteira = [
        _Contrato("A", inicio=date(2020, 1, 1), fim=date(2023, 2, 1),
                  status="encerrado"),
    ]

    assert svc.safras_da_carteira(carteira)[0]["perda"] is True


# ── O gráfico ───────────────────────────────────────────────────────


def _filtros():
    return svc.ler_filtros({"mes": "2026-09"}, hoje=date(2026, 9, 1))


def test_o_grafico_soma_SO_os_contratos_da_safra():
    carteira = [
        _Contrato("A", inicio=date(2024, 3, 1)),
        _Contrato("B", inicio=date(2025, 3, 1)),
    ]
    serie = [
        _Linha(2026, 9, "100", "A"),
        _Linha(2026, 9, "999", "B"),
    ]

    bloco = svc.grafico_da_safra(serie, carteira, "C2024", _filtros())

    assert bloco.linhas[0][1] == "R$ 100,00"


def test_a_tendencia_e_contra_o_MESMO_MES_do_ano_anterior():
    """Uma safra é um fenômeno de doze meses. Comparar agosto com julho dentro
    dela mede sazonalidade em vez de tendência."""
    carteira = [_Contrato("A", inicio=date(2024, 3, 1))]
    serie = [_Linha(2025, 9, "100", "A"), _Linha(2026, 9, "150", "A")]

    bloco = svc.grafico_da_safra(serie, carteira, "C2024", _filtros())

    assert bloco.linhas[-1][-1] == "150,0%"


def test_sem_o_mesmo_mes_do_ano_anterior_a_tendencia_e_TRACO():
    """Inventar 100% faria o primeiro ano de uma safra parecer crescimento
    infinito."""
    carteira = [_Contrato("A", inicio=date(2026, 3, 1))]
    serie = [_Linha(2026, 9, "100", "A")]

    bloco = svc.grafico_da_safra(serie, carteira, "C2026", _filtros())

    assert bloco.linhas[-1][-1] == "—"


def test_safra_sem_contrato_nao_desenha():
    assert svc.grafico_da_safra([], [], "C2024", _filtros()) is None


def test_safra_sem_receita_na_janela_nao_desenha():
    carteira = [_Contrato("A", inicio=date(2024, 3, 1))]

    assert svc.grafico_da_safra([], carteira, "C2024", _filtros()) is None


def test_o_filtro_normaliza_a_caixa():
    assert svc.ler_filtros({"safra": "c2023"}).safra == "C2023"
