"""O espelho visto de perto — como as linhas se apresentam, e o que o `/admin/`
deixa fazer com elas.

Estes testes parecem pequenos e não são: `__str__` é o que aparece no seletor do
`/admin/`, na mensagem de erro do carregador e na linha da divergência. Um
`Contrato object (17)` numa tela de conferência não responde nada a ninguém.

E a permissão do `/admin/` é o único freio real hoje contra alguém "corrigir" o
espelho à mão — a tela de fontes só chega na Onda 3.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.test import RequestFactory

from resultados import admin as adm
from resultados.models import (
    Apontamento,
    AvaliacaoCliente,
    Classificacao,
    Fonte,
    MarcoProjeto,
    Projeto,
    QuadroPessoas,
)

pytestmark = pytest.mark.django_db


def test_o_contrato_se_apresenta_por_codigo_e_cliente(contrato):
    assert str(contrato("C-100")) == "C-100 · Cliente Fictício"


def test_a_competencia_de_contrato_cita_o_contrato(contrato, competencia):
    linha = competencia(contrato("C-100"), ano=2026, mes=8)

    assert str(linha) == "C-100 · 08/2026"


def test_a_competencia_de_rateio_cita_o_centro_de_custo(competencia):
    """A linha sem contrato é o rateio, e ela precisa dizer de qual CC.

    Caindo no `__str__` do contrato, ela apareceria como "None · 08/2026" — que
    é como uma linha legítima passa por defeito numa conferência.
    """
    linha = competencia(None, ano=2026, mes=8, centro_custo="1042")

    assert str(linha) == "1042 · 08/2026"


def test_a_competencia_sabe_dizer_se_tem_orcado(contrato, competencia):
    """`None` e `Decimal("0")` produzem leituras opostas: a primeira é uma
    conciliação a resolver, a segunda é um teto de fato."""
    sem = competencia(contrato("C-A"), ano=2026, mes=8)
    com = competencia(contrato("C-B"), ano=2026, mes=8, receita_orcada=Decimal("1"))

    assert sem.tem_orcado is False
    assert com.tem_orcado is True


def test_projeto_marco_quadro_e_apontamento_se_apresentam(contrato):
    projeto = Projeto.objects.create(
        fonte=Fonte.MONDAY, chave_externa="p1", codigo="P-1", nome="Obra Fictícia"
    )
    marco = MarcoProjeto.objects.create(
        fonte=Fonte.MONDAY, chave_externa="m1", projeto=projeto, titulo="Kickoff"
    )
    quadro = QuadroPessoas.objects.create(
        fonte=Fonte.SANKHYA, chave_externa="q1", centro_custo="1042", ano=2026, mes=8
    )
    apontamento = Apontamento.objects.create(
        fonte=Fonte.SANKHYA, chave_externa="a1", centro_custo="1042", ano=2026, mes=8
    )
    avaliacao = AvaliacaoCliente.objects.create(
        fonte=Fonte.PLATFORM, chave_externa="av1", contrato=contrato("C-1"),
        data=date(2026, 8, 1), nota=3, classificacao=Classificacao.DETRATOR,
    )

    assert str(projeto) == "P-1 · Obra Fictícia"
    assert str(marco) == "P-1 · Kickoff"
    assert str(quadro) == "1042 · 08/2026"
    assert str(apontamento) == "1042 · 08/2026"
    assert str(avaliacao) == "C-1 · Detrator"


# ── O `/admin/` ─────────────────────────────────────────────────────


def _admins_do_espelho():
    """Os `ModelAdmin` registrados de verdade, lidos do site padrão.

    Do REGISTRO e não de uma lista escrita à mão: uma lista à mão nasce
    desatualizada no dia em que alguém acrescentar um model — e o model novo
    seria justamente o que entraria editável sem ninguém notar.
    """
    from django.contrib import admin as django_admin

    from resultados import models as m

    do_espelho = {
        m.Contrato, m.CompetenciaResultado, m.Projeto, m.MarcoProjeto,
        m.QuadroPessoas, m.Apontamento, m.AvaliacaoCliente,
    }
    registrados = {
        modelo: instancia
        for modelo, instancia in django_admin.site._registry.items()
        if modelo in do_espelho
    }
    faltando = do_espelho - set(registrados)
    assert not faltando, f"model do espelho fora do /admin/: {faltando}"
    return registrados


def test_nenhum_model_do_espelho_e_editavel_no_admin(django_user_model):
    """Nem criar, nem editar, nem apagar — nem para superusuário.

    Editar aqui criaria uma segunda verdade sobre a mesma linha, e a próxima
    carga a desfaria em silêncio. Apagar é pior: a carga traria a linha de
    volta, e a exclusão pareceria um bug do produto.
    """
    requisicao = RequestFactory().get("/admin/")
    requisicao.user = django_user_model.objects.create_superuser(
        "chefe@icodev.com.br", password="x"
    )

    for modelo, instancia in _admins_do_espelho().items():
        assert instancia.has_add_permission(requisicao) is False, modelo
        assert instancia.has_change_permission(requisicao) is False, modelo
        assert instancia.has_delete_permission(requisicao) is False, modelo


def test_a_procedencia_aparece_e_e_somente_leitura():
    """De onde veio a linha precisa estar VISÍVEL na conferência.

    Esconder `chave_externa` deixaria "de onde vem esse número" sem resposta
    acionável — sobraria a marca da fonte, e não o id para conferir lá.
    """
    assert "chave_externa" in adm.ContratoAdmin.readonly_fields
    assert "importado_em" in adm.ContratoAdmin.readonly_fields


def test_o_lancamento_por_conta_se_identifica_pelo_codigo_e_mes(db):
    """`__str__` aparece no admin e em log de carga. Sem ele, "objeto (17)" não
    diz qual lançamento é."""
    from decimal import Decimal

    from resultados.models import ResultadoPorConta

    linha = ResultadoPorConta(
        codigo_origem="41101001", ano=2026, mes=9,
        valor_realizado=Decimal("100"),
    )

    assert str(linha) == "41101001 · 09/2026"


def test_o_edital_se_identifica_pelo_numero_de_controle(db):
    """O número do PNCP é único no país — é ele que identifica o edital em
    qualquer lugar, e o objeto truncado diz do que se trata."""
    from resultados.models import EditalPublico

    edital = EditalPublico(
        numero_controle="00509968000148-1-004225/2025",
        objeto="Contratação de serviços de vigilância armada para o campus",
    )

    assert str(edital).startswith("00509968000148-1-004225/2025 · ")
    assert "vigilância" in str(edital)
