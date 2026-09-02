"""Os contratos respondidos — e o recorte de escopo, que é onde o vazamento mora.

O erro caro deste app não é um número errado: é o número CERTO da empresa
inteira aparecendo para quem só pode ver a própria regional. Vazamento em soma
não deixa rastro na tela — some dentro de um total plausível.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from resultados.models import AvaliacaoCliente, Classificacao, Fonte, StatusContrato
from resultados.providers import EspelhoLocal
from workspace.providers.resultados import Escopo

pytestmark = pytest.mark.django_db


@pytest.fixture
def espelho():
    return EspelhoLocal()


@pytest.fixture
def duas_regionais(contrato, competencia):
    sudeste = contrato("C-SE", regional="Sudeste", centro_custo="1042")
    sul = contrato("C-SU", regional="Sul", centro_custo="2050")
    competencia(sudeste, ano=2026, mes=8, receita="100000")
    competencia(sul, ano=2026, mes=8, receita="70000")
    return sudeste, sul


# ── Escopo ──────────────────────────────────────────────────────────


def test_gerente_de_uma_regional_nao_enxerga_a_outra(espelho, duas_regionais):
    escopo = Escopo(regionais=("Sudeste",))

    linhas = espelho.serie_competencia(escopo, date(2026, 1, 1), date(2026, 12, 31))

    assert [l.receita_bruta for l in linhas] == [Decimal("100000")]


def test_escopo_vazio_e_a_empresa_inteira(espelho, duas_regionais):
    linhas = espelho.serie_competencia(Escopo(), date(2026, 1, 1), date(2026, 12, 31))

    assert len(linhas) == 2


def test_a_linha_de_centro_de_custo_sem_contrato_entra_pelo_proprio_codigo(
    espelho, competencia
):
    """O rateio não pertence a cliente nenhum.

    Filtrar competência por `contrato__centro_custo` deixaria essa linha fora de
    todo recorte — e o total do centro de custo passaria a ser MENOR que a soma
    dos seus contratos.
    """
    competencia(None, ano=2026, mes=8, receita="30000", centro_custo="1042")

    linhas = espelho.serie_competencia(
        Escopo(centros_custo=("1042",)), date(2026, 1, 1), date(2026, 12, 31)
    )

    assert [l.receita_bruta for l in linhas] == [Decimal("30000")]
    assert linhas[0].contrato == ""


def test_a_serie_respeita_a_janela(espelho, contrato, competencia):
    c = contrato()
    competencia(c, ano=2025, mes=12, receita="1")
    competencia(c, ano=2026, mes=1, receita="2")
    competencia(c, ano=2026, mes=2, receita="3")

    linhas = espelho.serie_competencia(Escopo(), date(2026, 1, 1), date(2026, 1, 31))

    assert [l.receita_bruta for l in linhas] == [Decimal("2")]


# ── Consolidado ─────────────────────────────────────────────────────


def test_consolidado_sem_linha_e_none_e_nao_zero(espelho, duas_regionais):
    """Zero seria lido como "a empresa não faturou".

    A faixa precisa dizer "—" e o motivo. É a mesma regra do painel de
    indicadores: sem amostra, "—" e não "0".
    """
    assert espelho.consolidado(Escopo(), date(2026, 1, 1)) is None


def test_consolidado_conta_as_linhas_que_somou(espelho, duas_regionais):
    """"Deu zero" e "não tem dado" têm a mesma aparência num painel.

    A contagem é o que separa os dois.
    """
    consolidado = espelho.consolidado(Escopo(), date(2026, 8, 1))

    assert consolidado.receita_bruta == Decimal("170000")
    assert consolidado.linhas == 2


def test_a_procedencia_de_uma_soma_cita_a_carga_mais_ANTIGA(
    espelho, contrato, competencia
):
    """Citar a mais recente faria um consolidado com uma linha de ontem parecer
    inteiro de hoje.

    O que limita a confiança no total é a linha mais velha, não a mais nova.
    """
    # Dois CONTRATOS, e não duas linhas do mesmo: a constraint de competência
    # duplicada impede a segunda — e é ela que evita a receita do mês dobrar.
    velha = competencia(contrato("C-A"), ano=2026, mes=8, receita="1")
    competencia(contrato("C-B"), ano=2026, mes=8, receita="2")
    ontem = timezone.now() - timedelta(days=1)
    type(velha).objects.filter(pk=velha.pk).update(importado_em=ontem)

    consolidado = espelho.consolidado(Escopo(), date(2026, 8, 1))

    assert consolidado.procedencia.carregado_em.date() == ontem.date()


def test_soma_de_fontes_diferentes_nao_finge_ter_uma_fonte_so(
    espelho, contrato, competencia
):
    competencia(contrato("C-A"), ano=2026, mes=8, receita="1", fonte=Fonte.SANKHYA)
    competencia(contrato("C-B"), ano=2026, mes=8, receita="2", fonte=Fonte.CSV)

    consolidado = espelho.consolidado(Escopo(), date(2026, 8, 1))

    assert consolidado.procedencia.fonte == "múltiplas"


# ── Procedência por linha ───────────────────────────────────────────


def test_toda_linha_sabe_dizer_de_onde_veio(espelho, duas_regionais):
    """Espelho sem procedência é boato com aparência de relatório.

    `chave_externa` é o que torna "de onde vem esse número" uma pergunta com
    resposta acionável: com ela dá para abrir o Sankhya e conferir a linha.
    """
    (linha,) = espelho.serie_competencia(
        Escopo(regionais=("Sudeste",)), date(2026, 1, 1), date(2026, 12, 31)
    )

    assert linha.procedencia.fonte == Fonte.SANKHYA
    assert linha.procedencia.chave_externa
    assert linha.procedencia.carregado_em is not None


# ── Carteira ────────────────────────────────────────────────────────


def test_vencimentos_pega_a_faixa_e_ignora_o_que_ja_venceu(espelho, contrato):
    hoje = timezone.localdate()
    contrato("C-30", fim_vigencia=hoje + timedelta(days=30))
    contrato("C-200", fim_vigencia=hoje + timedelta(days=200))
    contrato("C-ONTEM", fim_vigencia=hoje - timedelta(days=1))

    codigos = [c.codigo for c in espelho.vencimentos(Escopo(), 90)]

    assert codigos == ["C-30"]


def test_contrato_de_um_mes_nao_entra_na_regra_dos_dez_por_cento(
    espelho, contrato, competencia
):
    """Sem amostra, ele não recebe layer nem margem comparável.

    Cobrar justificativa de margem baixa de um contrato que faturou uma vez é
    cobrar de quem ainda não tem o que explicar.
    """
    c = contrato()
    competencia(c, mes=1, receita="10000", margem_contribuicao=Decimal("500"))

    (dto,) = espelho.contratos(Escopo())

    assert dto.layer == "sem_amostra"
    assert dto.deficitario is False


def test_deficitario_e_margem_negativa_e_nao_margem_ausente(
    espelho, contrato, competencia
):
    c = contrato()
    competencia(c, mes=1, receita="10000", margem_contribuicao=Decimal("-500"))
    competencia(c, mes=2, receita="10000", margem_contribuicao=Decimal("-500"))

    (dto,) = espelho.contratos(Escopo())

    assert dto.deficitario is True


def test_movimentacoes_separa_conquista_de_perda(espelho, contrato):
    contrato("C-NOVO", inicio_vigencia=date(2026, 8, 10))
    contrato(
        "C-PERDIDO", inicio_vigencia=date(2024, 1, 1),
        fim_vigencia=date(2026, 8, 20), status=StatusContrato.ENCERRADO,
    )

    mov = espelho.movimentacoes(Escopo(), date(2026, 8, 1), date(2026, 8, 31))

    assert [c.codigo for c in mov.conquistas] == ["C-NOVO"]
    assert [c.codigo for c in mov.perdas] == ["C-PERDIDO"]


# ── Satisfação ──────────────────────────────────────────────────────


def test_detrator_sem_tratativa_e_o_que_a_tela_precisa_destacar(espelho, contrato):
    c = contrato()
    AvaliacaoCliente.objects.create(
        fonte=Fonte.PLATFORM, chave_externa="av-1", contrato=c,
        data=date(2026, 8, 10), nota=3, classificacao=Classificacao.DETRATOR,
        comentario="Atendimento demorou", tratativa_aberta=False,
    )

    (dto,) = espelho.avaliacoes(Escopo(), date(2026, 8, 1), date(2026, 8, 31))

    assert dto.detrator_sem_tratativa is True


def test_avaliacao_de_outra_regional_nao_atravessa_o_escopo(espelho, contrato):
    sul = contrato("C-SU", regional="Sul")
    AvaliacaoCliente.objects.create(
        fonte=Fonte.PLATFORM, chave_externa="av-1", contrato=sul,
        data=date(2026, 8, 10), nota=9, classificacao=Classificacao.PROMOTOR,
    )

    assert espelho.avaliacoes(
        Escopo(regionais=("Sudeste",)), date(2026, 8, 1), date(2026, 8, 31)
    ) == []


# ── Projetos e marcos ───────────────────────────────────────────────


@pytest.fixture
def projeto(db, contrato):
    from resultados.models import Projeto, SituacaoProjeto

    def _criar(codigo="P-1", contrato_obj=None, **campos):
        return Projeto.objects.create(
            fonte=campos.pop("fonte", Fonte.MONDAY),
            chave_externa=campos.pop("chave_externa", f"mon-{codigo}"),
            codigo=codigo,
            nome=campos.pop("nome", "Projeto Fictício"),
            contrato=contrato_obj,
            situacao=campos.pop("situacao", SituacaoProjeto.EM_ANDAMENTO),
            **campos,
        )

    return _criar


def test_projetos_filtram_por_situacao(espelho, projeto):
    from resultados.models import SituacaoProjeto

    projeto("P-1")
    projeto("P-2", situacao=SituacaoProjeto.CONCLUIDO)

    andando = espelho.projetos(Escopo(), situacao=SituacaoProjeto.EM_ANDAMENTO)

    assert [p.codigo for p in andando] == ["P-1"]


def test_projeto_interno_nao_finge_ter_contrato(espelho, projeto):
    """Projeto sem contrato é caso normal — obra interna existe.

    Uma FK obrigatória obrigaria a inventar um contrato-guarda-chuva, e a faixa
    de projetos passaria a mostrar um cliente que não existe.
    """
    projeto("P-INTERNO")

    (dto,) = espelho.projetos(Escopo())

    assert dto.contrato == ""


def test_projeto_de_outra_regional_nao_atravessa_o_escopo(espelho, projeto, contrato):
    sul = contrato("C-SU", regional="Sul")
    projeto("P-SUL", contrato_obj=sul)

    assert espelho.projetos(Escopo(regionais=("Sudeste",))) == []


def test_marcos_em_risco_ignoram_o_que_ja_foi_concluido(espelho, projeto):
    from resultados.models import MarcoProjeto

    p = projeto("P-1")
    hoje = timezone.localdate()
    MarcoProjeto.objects.create(
        fonte=Fonte.MONDAY, chave_externa="m-1", projeto=p,
        titulo="Homologação", prazo=hoje + timedelta(days=5),
    )
    MarcoProjeto.objects.create(
        fonte=Fonte.MONDAY, chave_externa="m-2", projeto=p,
        titulo="Kickoff", prazo=hoje + timedelta(days=5), concluido_em=hoje,
    )

    titulos = [m.titulo for m in espelho.marcos_em_risco(Escopo(), 15)]

    assert titulos == ["Homologação"]


def test_marco_vencido_se_declara_vencido(espelho, projeto):
    """`vencido` é derivado da data, e não gravado.

    Gravado, ele viraria a resposta do dia da carga — e um marco venceria sem
    ninguém carregar nada, que é justamente quando ele precisa aparecer.
    """
    from resultados.models import MarcoProjeto

    p = projeto("P-1")
    MarcoProjeto.objects.create(
        fonte=Fonte.MONDAY, chave_externa="m-1", projeto=p,
        titulo="Atrasado", prazo=timezone.localdate() - timedelta(days=3),
    )

    (dto,) = espelho.marcos_em_risco(Escopo(), 15)

    assert dto.vencido is True


# ── Pessoas e jornada ───────────────────────────────────────────────


@pytest.fixture
def quadro(db):
    from resultados.models import QuadroPessoas

    def _criar(centro_custo="1042", ano=2026, mes=8, **campos):
        return QuadroPessoas.objects.create(
            fonte=Fonte.SANKHYA,
            chave_externa=f"q-{centro_custo}-{ano}-{mes}",
            centro_custo=centro_custo, ano=ano, mes=mes, **campos,
        )

    return _criar


def test_quadro_responde_pela_competencia_pedida(espelho, quadro):
    quadro(mes=7, efetivo_ativo=100)
    quadro(mes=8, efetivo_ativo=118)

    assert espelho.quadro(Escopo(), date(2026, 8, 1)).efetivo_ativo == 118


def test_quadro_sem_competencia_e_none_e_nao_zerado(espelho, quadro):
    """Zerado diria "a empresa não tem ninguém"."""
    assert espelho.quadro(Escopo(), date(2026, 1, 1)) is None


def test_quadro_respeita_o_centro_de_custo_do_escopo(espelho, quadro):
    quadro(centro_custo="2050", efetivo_ativo=9)

    assert espelho.quadro(Escopo(centros_custo=("1042",)), date(2026, 8, 1)) is None


def test_movimentacao_soma_a_janela(espelho, quadro):
    quadro(mes=7, admissoes=3, rescisoes=1)
    quadro(mes=8, admissoes=2, rescisoes=4)

    mov = espelho.movimentacao(Escopo(), date(2026, 7, 1), date(2026, 8, 31))

    assert (mov.admissoes, mov.rescisoes) == (5, 5)


def test_apontamento_traz_a_hora_extra_por_classificacao(espelho):
    """HE total sozinha não muda comportamento nenhum.

    O que muda é saber quanto dela é INEFICIÊNCIA — cobertura de ausência,
    escala mal feita — contra serviço extra, que é receita.
    """
    from decimal import Decimal as D

    from resultados.models import Apontamento

    Apontamento.objects.create(
        fonte=Fonte.SANKHYA, chave_externa="a-1", centro_custo="1042",
        ano=2026, mes=8, horas_normais=D("18000"), he_total=D("1200"),
        he_ineficiencia=D("900"), he_servico_extra=D("300"),
    )

    dto = espelho.apontamentos(Escopo(), date(2026, 8, 1))

    assert dto.he_ineficiencia == D("900")
    assert dto.procedencia.fonte == Fonte.SANKHYA


def test_apontamento_sem_competencia_e_none(espelho):
    assert espelho.apontamentos(Escopo(), date(2026, 1, 1)) is None


def test_apontamento_respeita_o_escopo(espelho):
    from resultados.models import Apontamento

    Apontamento.objects.create(
        fonte=Fonte.SANKHYA, chave_externa="a-1", centro_custo="2050",
        ano=2026, mes=8,
    )

    assert espelho.apontamentos(Escopo(centros_custo=("1042",)), date(2026, 8, 1)) is None


# ── Contratos por código ────────────────────────────────────────────


def test_escopo_por_contrato_recorta_a_carteira(espelho, contrato):
    contrato("C-A")
    contrato("C-B")

    assert [c.codigo for c in espelho.contratos(Escopo(contratos=("C-A",)))] == ["C-A"]
