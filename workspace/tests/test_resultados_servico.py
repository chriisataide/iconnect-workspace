"""O serviço de resultados, sem passar pela tela.

Aqui ficam os caminhos que a tela não exercita porque eles nunca acontecem ao
mesmo tempo: cada faixa sem a sua fonte, cada filtro sozinho, e a aritmética
que decide entre "—" e um número.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from workspace.providers import resultados as contrato
from workspace.services import resultados as svc

HOJE = date(2026, 9, 15)
COMPETENCIA = date(2026, 9, 1)


@pytest.fixture
def sem_provedores(monkeypatch):
    """Nenhum domínio registrado — o estado de uma instalação sem o espelho."""
    monkeypatch.setattr(contrato, "obter", lambda tipo: None)


# ── Cada faixa sem a sua fonte ──────────────────────────────────────


@pytest.mark.parametrize(
    ("montador", "fonte"),
    [
        (svc.dinheiro, "Sankhya"),
        (svc.contratos, "iConnect Platform"),
        (svc.vencimentos, "iConnect Platform"),
        (svc.projetos, "monday.com"),
        (svc.pessoas, "Sankhya"),
        (svc.satisfacao, "iConnect Platform"),
    ],
)
def test_faixa_sem_fonte_explica_qual_fonte_falta(sem_provedores, montador, fonte):
    """Nomear a FONTE, e não dizer "sem dados".

    Quem lê a tela precisa saber o que ligar. "Sem dados" mandaria a pessoa
    procurar o problema no lugar errado — ou, pior, concluir que a empresa não
    tem projeto nenhum.
    """
    faixa = montador(contrato.Escopo(), svc.Filtros(competencia=COMPETENCIA))

    assert faixa.disponivel is False
    assert fonte in faixa.motivo
    assert "não está conectada" in faixa.motivo


@pytest.mark.django_db
def test_a_faixa_sem_fonte_ainda_carimba(sem_provedores):
    """O carimbo diz "sem registro de carga", que é informação — e não um
    espaço em branco.

    Precisa de banco: o carimbo pergunta ao provedor de frescor, que consulta
    `FonteDados`. É o único ponto deste arquivo que toca a base.
    """
    faixa = svc.dinheiro(contrato.Escopo(), svc.Filtros(competencia=COMPETENCIA))

    assert faixa.carimbo.fonte == "sankhya"


@pytest.mark.django_db
def test_sem_nenhuma_fonte_os_destaques_ficam_quietos(sem_provedores):
    """Sem faixa disponível não há regra para disparar — e "nenhum destaque"
    é boa notícia, não falha de carregamento. A tela diz isso."""
    filtros = svc.Filtros(competencia=COMPETENCIA)
    faixas = {chave: m(contrato.Escopo(), filtros) for chave, m in svc.MONTADORES}

    destaques = svc.destaques(faixas, filtros)

    assert destaques.disponivel is False
    assert "Nenhuma regra disparou" in destaques.motivo


# ── Filtros ─────────────────────────────────────────────────────────


def test_a_janela_da_serie_tem_treze_meses(monkeypatch):
    """Doze não bastam: a comparação com o mesmo mês do ano passado é a única
    que separa crescimento de sazonalidade."""
    filtros = svc.Filtros(competencia=date(2026, 9, 1))

    assert filtros.de == date(2025, 9, 1)
    assert filtros.ate == date(2026, 9, 30)


def test_a_janela_fecha_no_ultimo_dia_do_mes_inclusive_em_fevereiro():
    assert svc.Filtros(competencia=date(2026, 2, 1)).ate == date(2026, 2, 28)
    assert svc.Filtros(competencia=date(2028, 2, 1)).ate == date(2028, 2, 29)


@pytest.mark.parametrize("texto", ["", None, "abacaxi", "2026", "9999-99", "2026-13"])
def test_competencia_impossivel_cai_no_padrao_e_nao_em_erro(texto):
    """`?competencia=9999-99` é uma URL digitada errada, e não um ataque.

    Responder 500 a ela ensinaria a não brincar com a barra de endereço — que é
    justamente o que a tela quer que as pessoas façam.
    """
    filtros = svc.ler_filtros({"competencia": texto}, hoje=HOJE)

    assert filtros.competencia == COMPETENCIA


def test_os_filtros_de_texto_sao_truncados():
    """Uma query string de dez mil caracteres não vira um `LIKE` de dez mil."""
    filtros = svc.ler_filtros({"regional": "x" * 500, "cc": "y" * 500}, hoje=HOJE)

    assert len(filtros.regional) == 60
    assert len(filtros.centro_custo) == 20


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [("1", True), ("true", True), ("sim", True), ("0", False), (None, False)],
)
def test_o_filtro_de_deficitario_e_explicito(valor, esperado):
    assert svc.ler_filtros({"deficitario": valor}, hoje=HOJE).deficitario is esperado


def test_o_filtro_estreita_quando_a_pessoa_ja_pode_ver():
    escopo = contrato.Escopo(regionais=("Sudeste", "Sul"))
    filtros = svc.Filtros(competencia=COMPETENCIA, regional="Sul")

    assert filtros.aplicar(escopo).regionais == ("Sul",)


def test_o_filtro_nao_alarga_quando_a_pessoa_nao_pode():
    """O que a pessoa não pode ver não volta por uma query string."""
    escopo = contrato.Escopo(regionais=("Sudeste",))
    filtros = svc.Filtros(competencia=COMPETENCIA, regional="Sul")

    assert filtros.aplicar(escopo).regionais == ("Sudeste",)


def test_o_filtro_de_quem_ve_tudo_recorta_de_verdade():
    filtros = svc.Filtros(competencia=COMPETENCIA, centro_custo="1042", contrato="C-1")

    recorte = filtros.aplicar(contrato.Escopo())

    assert recorte.centros_custo == ("1042",)
    assert recorte.contratos == ("C-1",)


def test_o_seletor_de_competencia_anda_para_TRAS_a_partir_da_atual():
    """Quem abriu agosto e volta ao seletor tem de encontrar julho ao lado, e
    não descobrir que a lista pulou para o mês de hoje."""
    meses = svc._competencias_oferecidas(date(2026, 2, 1), quantas=3)

    assert meses == [date(2026, 2, 1), date(2026, 1, 1), date(2025, 12, 1)]


# ── Aritmética ──────────────────────────────────────────────────────


def test_percentual_sem_base_e_none_e_nao_zero():
    """Dividir por zero para exibir "0%" faria um mês sem lançamento parecer um
    mês de margem zero — duas leituras opostas com a mesma aparência."""
    assert svc._sobre(Decimal("10"), Decimal("0")) is None
    assert svc._sobre(Decimal("10"), Decimal("-5")) is None
    assert svc._sobre(Decimal("25"), Decimal("100")) == Decimal("25.0")


def test_percentual_de_orcado_ausente_e_none():
    assert svc._percentual(Decimal("100"), None) is None
    assert svc._percentual(Decimal("100"), Decimal("0")) is None
    assert svc._percentual(Decimal("103"), Decimal("100")) == Decimal("103.0")


def test_horas_sem_apontamento_nao_inventa_tabela():
    assert svc._horas(None) == []


# ── Filtro da carteira ──────────────────────────────────────────────


class _Falso:
    def __init__(self, **campos):
        self.__dict__.update(campos)


def test_a_carteira_filtra_por_servico_status_e_deficitario():
    carteira = [
        _Falso(codigo="A", servico="cftv", status="ativo", deficitario=False),
        _Falso(codigo="B", servico="alarme", status="ativo", deficitario=True),
        _Falso(codigo="C", servico="cftv", status="encerrado", deficitario=False),
    ]
    base = svc.Filtros(competencia=COMPETENCIA)

    def _codigos(**campos):
        from dataclasses import replace

        return [c.codigo for c in svc._filtrar_carteira(carteira, replace(base, **campos))]

    assert _codigos(servico="cftv") == ["A", "C"]
    assert _codigos(status="encerrado") == ["C"]
    assert _codigos(deficitario=True) == ["B"]
    assert _codigos() == ["A", "B", "C"]


@pytest.mark.django_db
def test_fonte_nunca_ligada_nao_vira_cartao_de_desatualizada(sem_provedores):
    """"Não sei nada sobre esta fonte" não é "a fonte está desatualizada".

    Fonte sem registro de carga é fonte que ninguém ligou — e a própria faixa já
    diz isso, com o nome dela. Um cartão de "desatualizada" mandaria alguém
    procurar uma carga que nunca existiu, num ambiente onde não existir é o
    estado normal.
    """
    filtros = svc.Filtros(competencia=COMPETENCIA)
    faixas = {chave: m(contrato.Escopo(), filtros) for chave, m in svc.MONTADORES}

    cartoes = svc.destaques(faixas, filtros).conteudo["cartoes"]

    assert [c for c in cartoes if c.chave.startswith("fonte-")] == []
