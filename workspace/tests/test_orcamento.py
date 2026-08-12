"""`Compromisso` e a barra tripla de orçamento.

O problema que isto resolve: dois gestores aprovam R$ 12.000 cada no mesmo dia,
num CC com R$ 15.000 de saldo. Os dois veem "58% consumido" e os dois aprovam de
boa-fé. Sem `Compromisso`, o estouro só aparece no fechamento.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.models import Compromisso, RegraAprovacao, SituacaoCompromisso, TipoAprovador
from workspace.models.orcamento import competencia_de
from workspace.providers import orcamento as provedor
from workspace.providers.orcamento import OrcamentoProvider
from workspace.services import aprovacao as apr
from workspace.services import orcamento as orc


# ── Provider falso ──────────────────────────────────────────────────


class ProviderFalso(OrcamentoProvider):
    key = "falso"

    def __init__(self, orcamento=None, realizado=Decimal("0")):
        self._orcamento = orcamento
        self._realizado = realizado

    def orcamento_mensal(self, centro_custo_codigo):
        return self._orcamento

    def realizado_no_mes(self, centro_custo_codigo, competencia):
        return self._realizado

    def centro_custo_existe(self, centro_custo_codigo):
        return True


@pytest.fixture
def sem_provider():
    """O provider é estado de processo, registrado no ready() do dashboard."""
    anterior = provedor.obter()
    provedor.limpar()
    yield
    provedor.limpar()
    if anterior is not None:
        provedor.registrar(anterior)


@pytest.fixture
def com_provider(sem_provider):
    def registrar(orcamento=None, realizado=Decimal("0")):
        return provedor.registrar(ProviderFalso(orcamento, realizado))

    return registrar


# ── Registro do provider ────────────────────────────────────────────


@pytest.mark.django_db
def test_dashboard_registra_o_provider_no_boot():
    """O provider real é registrado pelo ready() do dashboard."""
    provider = provedor.obter()
    assert provider is not None
    assert provider.key == "dashboard"


def test_registro_recusa_objeto_que_nao_e_provider(sem_provider):
    with pytest.raises(TypeError, match="não é um OrcamentoProvider"):
        provedor.registrar(object())


def test_registro_recusa_provider_sem_key(sem_provider):
    class SemKey(OrcamentoProvider):
        key = ""

    with pytest.raises(ValueError, match="precisa declarar `key`"):
        provedor.registrar(SemKey())


def test_um_provider_substitui_o_outro(sem_provider):
    """Um só, não uma lista: "quanto sobrou no CC" tem UMA resposta."""
    provedor.registrar(ProviderFalso())
    segundo = provedor.registrar(ProviderFalso())
    assert provedor.obter() is segundo


def test_contrato_base_devolve_vazio():
    """Provider que não implementa nada não explode — degrada."""
    base = OrcamentoProvider()
    assert base.orcamento_mensal("X") is None
    assert base.realizado_no_mes("X", date(2026, 8, 1)) == Decimal("0")
    assert base.centro_custo_existe("X") is False


# ── Competência ─────────────────────────────────────────────────────


def test_competencia_e_o_primeiro_dia_do_mes():
    assert competencia_de(date(2026, 8, 17)) == date(2026, 8, 1)


def test_competencia_sem_argumento_usa_hoje():
    assert competencia_de() == timezone.localdate().replace(day=1)


# ── Os três números ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_resumo_soma_realizado_e_comprometido(com_provider):
    com_provider(orcamento=Decimal("38000"), realizado=Decimal("22100"))
    Compromisso.objects.create(
        dominio="com.requisicao", descricao="Notebooks",
        centro_custo_codigo="1008", valor=Decimal("3200"),
        competencia=competencia_de(),
    )

    r = orc.resumo("1008")
    assert r.orcamento == Decimal("38000")
    assert r.realizado == Decimal("22100")
    assert r.comprometido == Decimal("3200")
    assert r.consumido == Decimal("25300")
    assert r.disponivel == Decimal("12700")


@pytest.mark.django_db
def test_percentual_com_e_sem_o_pedido_em_decisao(com_provider):
    """A barra tripla: o aprovador vê o efeito ANTES de decidir."""
    com_provider(orcamento=Decimal("38000"), realizado=Decimal("22100"))
    Compromisso.objects.create(
        dominio="x", descricao="d", centro_custo_codigo="1008",
        valor=Decimal("3200"), competencia=competencia_de(),
    )

    r = orc.resumo("1008")
    assert r.percentual() == Decimal("66.6")
    assert r.percentual(Decimal("12400")) == Decimal("99.2"), "após aprovar"


@pytest.mark.django_db
def test_o_cenario_dos_dois_gestores(com_provider):
    """O bug que este modelo existe para impedir."""
    com_provider(orcamento=Decimal("15000"), realizado=Decimal("0"))

    # Primeiro gestor aprova R$ 12.000.
    Compromisso.objects.create(
        dominio="x", descricao="pedido A", centro_custo_codigo="CC",
        valor=Decimal("12000"), competencia=competencia_de(),
    )

    # O segundo, no mesmo dia, agora VÊ o comprometido.
    r = orc.resumo("CC")
    assert r.comprometido == Decimal("12000")
    assert r.disponivel == Decimal("3000")
    assert r.cabe(Decimal("12000")) is False, "o segundo pedido não cabe mais"


@pytest.mark.django_db
def test_sem_orcamento_definido_e_diferente_de_zero(com_provider):
    """`None` significa "não definido". A tela precisa dizer isso, não 0%."""
    com_provider(orcamento=None, realizado=Decimal("5000"))

    r = orc.resumo("SEM_ORC")
    assert r.orcamento is None
    assert r.tem_orcamento is False
    assert r.disponivel is None
    assert r.percentual() is None


@pytest.mark.django_db
def test_orcamento_zero_tambem_conta_como_indefinido(com_provider):
    com_provider(orcamento=Decimal("0"))
    assert orc.resumo("CC").tem_orcamento is False
    assert orc.resumo("CC").percentual() is None


@pytest.mark.django_db
def test_sem_orcamento_tudo_cabe(com_provider):
    """O Workspace não barra por falta de cadastro — barrar esconderia o problema
    real, que é o CC sem orçamento."""
    com_provider(orcamento=None)
    assert orc.resumo("CC").cabe(Decimal("999999")) is True


@pytest.mark.django_db
def test_sem_provider_registrado_nao_quebra(sem_provider):
    Compromisso.objects.create(
        dominio="x", descricao="d", centro_custo_codigo="CC",
        valor=Decimal("500"), competencia=competencia_de(),
    )
    r = orc.resumo("CC")
    assert r.orcamento is None
    assert r.realizado == Decimal("0")
    assert r.comprometido == Decimal("500"), "o comprometido é nosso, não do provider"


@pytest.mark.django_db
def test_resumo_isola_por_centro_de_custo(com_provider):
    com_provider(orcamento=Decimal("10000"))
    for cc, valor in [("A", "1000"), ("B", "2000")]:
        Compromisso.objects.create(
            dominio="x", descricao="d", centro_custo_codigo=cc,
            valor=Decimal(valor), competencia=competencia_de(),
        )

    assert orc.resumo("A").comprometido == Decimal("1000")
    assert orc.resumo("B").comprometido == Decimal("2000")


@pytest.mark.django_db
def test_resumo_isola_por_competencia(com_provider):
    com_provider(orcamento=Decimal("10000"))
    mes_passado = (timezone.localdate().replace(day=1) - timedelta(days=1)).replace(day=1)
    Compromisso.objects.create(
        dominio="x", descricao="antigo", centro_custo_codigo="CC",
        valor=Decimal("5000"), competencia=mes_passado,
    )
    Compromisso.objects.create(
        dominio="x", descricao="atual", centro_custo_codigo="CC",
        valor=Decimal("1000"), competencia=competencia_de(),
    )

    assert orc.resumo("CC").comprometido == Decimal("1000")
    assert orc.resumo("CC", competencia=mes_passado).comprometido == Decimal("5000")


@pytest.mark.django_db
def test_baixado_e_cancelado_saem_do_comprometido(com_provider):
    com_provider(orcamento=Decimal("10000"))
    ativo = Compromisso.objects.create(
        dominio="x", descricao="ativo", centro_custo_codigo="CC",
        valor=Decimal("100"), competencia=competencia_de(),
    )
    for situacao in (SituacaoCompromisso.BAIXADO, SituacaoCompromisso.CANCELADO):
        Compromisso.objects.create(
            dominio="x", descricao=situacao, centro_custo_codigo="CC",
            valor=Decimal("900"), competencia=competencia_de(), situacao=situacao,
        )

    assert orc.resumo("CC").comprometido == Decimal("100")
    assert ativo.situacao == SituacaoCompromisso.ATIVO


# ── Escrituração pela aprovação ─────────────────────────────────────


@pytest.fixture
def equipe():
    diretor, gestor, ana = (f.pessoa(n) for n in ("diretor", "gestor", "ana"))
    f.lotar(diretor)
    f.lotar(gestor, gestor=diretor)
    f.lotar(ana, gestor=gestor)
    RegraAprovacao.objects.create(dominio="*", tipo=TipoAprovador.GESTOR_DIRETO, ordem=10)
    return {"ana": ana, "gestor": gestor, "diretor": diretor}


@pytest.mark.django_db
def test_aprovar_escritura_o_compromisso(equipe):
    """A costura: APR não conhece Compromisso; o sinal liga os dois."""
    s = apr.criar(
        dominio="fin.reembolso", titulo="Viagem SP", solicitante=equipe["ana"],
        valor=Decimal("840"), centro_custo_codigo="1042",
    )
    assert Compromisso.objects.count() == 0, "só na aprovação"

    apr.decidir(s, equipe["gestor"], apr.Decisao.APROVAR)

    comp = Compromisso.objects.get()
    assert comp.valor == Decimal("840")
    assert comp.centro_custo_codigo == "1042"
    assert comp.dominio == "fin.reembolso"
    assert comp.situacao == SituacaoCompromisso.ATIVO
    assert comp.criado_por == equipe["gestor"]


@pytest.mark.django_db
def test_devolver_nao_escritura(equipe):
    s = apr.criar(
        dominio="fin.reembolso", titulo="X", solicitante=equipe["ana"],
        valor=Decimal("840"), centro_custo_codigo="1042",
    )
    apr.decidir(s, equipe["gestor"], apr.Decisao.DEVOLVER, "faltou nota")
    assert Compromisso.objects.count() == 0


@pytest.mark.django_db
def test_cancelar_antes_de_aprovar_nao_deixa_residuo(equipe):
    s = apr.criar(
        dominio="com.requisicao", titulo="X", solicitante=equipe["ana"],
        valor=Decimal("5000"), centro_custo_codigo="1008",
    )
    apr.decidir(s, equipe["ana"], apr.Decisao.CANCELAR)
    assert Compromisso.objects.count() == 0


@pytest.mark.django_db
def test_dominio_libera_orcamento_de_pedido_aprovado_que_morreu(equipe):
    """O caso real: a requisição foi aprovada, o compromisso está reservado, e
    depois o pedido é cancelado — fornecedor sem estoque, projeto suspenso.

    Não passa por `decidir()`: a solicitação já está APROVADA e a guarda de
    idempotência recusa nova decisão, corretamente. Quem cancela é o domínio,
    chamando `orc.cancelar()` — senão o orçamento fica reservado para sempre.
    """
    s = apr.criar(
        dominio="com.requisicao", titulo="X", solicitante=equipe["ana"],
        valor=Decimal("5000"), centro_custo_codigo="1008",
    )
    apr.decidir(s, equipe["gestor"], apr.Decisao.APROVAR)
    assert orc.resumo("1008").comprometido == Decimal("5000")

    liberados = orc.cancelar(s)

    assert liberados == 1
    assert orc.resumo("1008").comprometido == Decimal("0")
    assert Compromisso.objects.get().situacao == SituacaoCompromisso.CANCELADO


@pytest.mark.django_db
def test_decidir_recusa_cancelar_o_que_ja_foi_aprovado(equipe):
    """Documenta a fronteira: a guarda de idempotência vem antes."""
    s = apr.criar(
        dominio="com.requisicao", titulo="X", solicitante=equipe["ana"],
        valor=Decimal("5000"), centro_custo_codigo="1008",
    )
    apr.decidir(s, equipe["gestor"], apr.Decisao.APROVAR)

    with pytest.raises(apr.AprovacaoError, match="já está aprovada"):
        apr.decidir(s, equipe["ana"], apr.Decisao.CANCELAR)


@pytest.mark.django_db
def test_ferias_nao_escrituram_nada(equipe):
    """Solicitação sem valor é legítima e não toca orçamento."""
    s = apr.criar(
        dominio="rh.ferias", titulo="18-29/09", solicitante=equipe["ana"], valor=None
    )
    apr.decidir(s, equipe["gestor"], apr.Decisao.APROVAR)
    assert Compromisso.objects.count() == 0


@pytest.mark.django_db
def test_sem_centro_de_custo_nao_escritura(equipe):
    s = apr.criar(
        dominio="fin.reembolso", titulo="X", solicitante=equipe["ana"],
        valor=Decimal("840"), centro_custo_codigo="",
    )
    apr.decidir(s, equipe["gestor"], apr.Decisao.APROVAR)
    assert Compromisso.objects.count() == 0


@pytest.mark.django_db
def test_valor_zero_nao_escritura(equipe):
    s = apr.criar(
        dominio="fin.reembolso", titulo="X", solicitante=equipe["ana"],
        valor=Decimal("0"), centro_custo_codigo="1042",
    )
    apr.decidir(s, equipe["gestor"], apr.Decisao.APROVAR)
    assert Compromisso.objects.count() == 0


@pytest.mark.django_db
def test_escriturar_e_idempotente(equipe):
    """Retry do sinal não pode dobrar o comprometido."""
    s = apr.criar(
        dominio="fin.reembolso", titulo="X", solicitante=equipe["ana"],
        valor=Decimal("840"), centro_custo_codigo="1042",
    )
    apr.decidir(s, equipe["gestor"], apr.Decisao.APROVAR)

    orc.escriturar(s)
    orc.escriturar(s)
    assert Compromisso.objects.count() == 1


@pytest.mark.django_db
def test_constraint_impede_dois_compromissos_da_mesma_solicitacao(equipe):
    s = apr.criar(
        dominio="fin.reembolso", titulo="X", solicitante=equipe["ana"],
        valor=Decimal("840"), centro_custo_codigo="1042",
    )
    apr.decidir(s, equipe["gestor"], apr.Decisao.APROVAR)

    with pytest.raises(IntegrityError), transaction.atomic():
        Compromisso.objects.create(
            solicitacao=s, dominio="x", descricao="duplicado",
            centro_custo_codigo="1042", valor=Decimal("840"),
            competencia=competencia_de(),
        )


@pytest.mark.django_db
def test_compromissos_sem_solicitacao_podem_coexistir():
    """A constraint é condicional: lançamento manual não é limitado a um."""
    for i in range(2):
        Compromisso.objects.create(
            dominio="manual", descricao=f"lançamento {i}",
            centro_custo_codigo="CC", valor=Decimal("100"),
            competencia=competencia_de(),
        )
    assert Compromisso.objects.count() == 2


# ── Baixa ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_baixar_move_para_realizado(com_provider):
    com_provider(orcamento=Decimal("10000"))
    comp = Compromisso.objects.create(
        dominio="x", descricao="d", centro_custo_codigo="CC",
        valor=Decimal("500"), competencia=competencia_de(),
    )
    assert orc.resumo("CC").comprometido == Decimal("500")

    orc.baixar(comp, movimentacao_id="9912")

    comp.refresh_from_db()
    assert comp.situacao == SituacaoCompromisso.BAIXADO
    assert comp.movimentacao_id == "9912"
    assert comp.baixado_em is not None
    assert orc.resumo("CC").comprometido == Decimal("0")


@pytest.mark.django_db
def test_baixar_nao_apaga_o_historico():
    """"O que foi comprometido em setembro" é o dado que explica o fechamento."""
    comp = Compromisso.objects.create(
        dominio="x", descricao="d", centro_custo_codigo="CC",
        valor=Decimal("500"), competencia=competencia_de(),
    )
    orc.baixar(comp)
    assert Compromisso.objects.filter(pk=comp.pk).exists()


@pytest.mark.django_db
def test_baixar_duas_vezes_e_inofensivo():
    comp = Compromisso.objects.create(
        dominio="x", descricao="d", centro_custo_codigo="CC",
        valor=Decimal("500"), competencia=competencia_de(),
    )
    orc.baixar(comp, "111")
    orc.baixar(comp, "222")
    comp.refresh_from_db()
    assert comp.movimentacao_id == "111", "a primeira baixa vale"


@pytest.mark.django_db
def test_cancelar_sem_compromisso_devolve_zero(equipe):
    s = apr.criar(dominio="rh.ferias", titulo="X", solicitante=equipe["ana"], valor=None)
    assert orc.cancelar(s) == 0


# ── Validação ───────────────────────────────────────────────────────


@pytest.mark.django_db
@pytest.mark.parametrize("valor", [Decimal("0"), Decimal("-1")])
def test_compromisso_recusa_valor_nao_positivo(valor):
    comp = Compromisso(
        dominio="x", descricao="d", centro_custo_codigo="CC",
        valor=valor, competencia=competencia_de(),
    )
    with pytest.raises(ValidationError, match="zero ou negativo"):
        comp.clean()


@pytest.mark.django_db
def test_compromisso_exige_centro_de_custo():
    comp = Compromisso(
        dominio="x", descricao="d", centro_custo_codigo="",
        valor=Decimal("10"), competencia=competencia_de(),
    )
    with pytest.raises(ValidationError, match="Obrigatório"):
        comp.clean()


@pytest.mark.django_db
def test_compromisso_valido_passa():
    Compromisso(
        dominio="x", descricao="d", centro_custo_codigo="CC",
        valor=Decimal("10"), competencia=competencia_de(),
    ).clean()


@pytest.mark.django_db
def test_str_do_compromisso():
    comp = Compromisso.objects.create(
        dominio="x", descricao="d", centro_custo_codigo="1042",
        valor=Decimal("840"), competencia=competencia_de(),
    )
    assert "1042" in str(comp)
    assert "840" in str(comp)


@pytest.mark.django_db
def test_queryset_total_de_vazio_e_zero():
    assert Compromisso.objects.none().total() == Decimal("0")


# ── O provider real do dashboard ────────────────────────────────────


@pytest.mark.django_db
def test_provider_real_le_o_orcamento_do_centro_de_custo():
    from dashboard.models import CentroCusto
    from dashboard.workspace_provider import OrcamentoDoDashboard

    CentroCusto.objects.create(
        codigo="1042", nome="Comercial", departamento="Comercial",
        orcamento_mensal=Decimal("38000"), status="ativo",
    )
    provider = OrcamentoDoDashboard()

    assert provider.orcamento_mensal("1042") == Decimal("38000")
    assert provider.centro_custo_existe("1042") is True
    assert provider.centro_custo_existe("INEXISTENTE") is False


@pytest.mark.django_db
def test_provider_real_trata_cc_inexistente_e_sem_orcamento():
    from dashboard.models import CentroCusto
    from dashboard.workspace_provider import OrcamentoDoDashboard

    CentroCusto.objects.create(
        codigo="ZERO", nome="Sem orçamento", departamento="X",
        orcamento_mensal=Decimal("0"), status="ativo",
    )
    provider = OrcamentoDoDashboard()

    assert provider.orcamento_mensal("INEXISTENTE") is None
    assert provider.orcamento_mensal("ZERO") is None, "zero é 'não definido'"


@pytest.mark.django_db
def test_provider_real_ignora_cc_inativo():
    from dashboard.models import CentroCusto
    from dashboard.workspace_provider import OrcamentoDoDashboard

    CentroCusto.objects.create(
        codigo="MORTO", nome="Encerrado", departamento="X",
        orcamento_mensal=Decimal("5000"), status="inativo",
    )
    assert OrcamentoDoDashboard().orcamento_mensal("MORTO") is None


@pytest.mark.django_db
def test_provider_real_soma_realizado_do_mes():
    from dashboard.models import CategoriaFinanceira, CentroCusto, MovimentacaoFinanceira
    from dashboard.workspace_provider import OrcamentoDoDashboard

    cc = CentroCusto.objects.create(
        codigo="1008", nome="TI", departamento="TI",
        orcamento_mensal=Decimal("38000"), status="ativo",
    )
    categoria = CategoriaFinanceira.objects.create(nome="Material", tipo="despesa")
    usuario = f.pessoa("lancador")
    hoje = timezone.localdate()
    mes = hoje.replace(day=1)

    for dia, valor in [(1, "1000"), (15, "2000")]:
        MovimentacaoFinanceira.objects.create(
            categoria=categoria, descricao="compra", tipo="despesa",
            valor=Decimal(valor), data_movimentacao=mes.replace(day=dia),
            usuario=usuario, centro_custo=cc,
        )
    # Mês anterior não entra.
    MovimentacaoFinanceira.objects.create(
        categoria=categoria, descricao="antiga", tipo="despesa",
        valor=Decimal("9999"), data_movimentacao=mes - timedelta(days=1),
        usuario=usuario, centro_custo=cc,
    )

    assert OrcamentoDoDashboard().realizado_no_mes("1008", mes) == Decimal("3000")


@pytest.mark.django_db
def test_provider_real_sem_movimentacao_e_zero():
    from dashboard.workspace_provider import OrcamentoDoDashboard

    assert OrcamentoDoDashboard().realizado_no_mes("VAZIO", date(2026, 8, 1)) == Decimal("0")


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("competencia", "ultimo_dia"),
    [
        (date(2026, 1, 1), date(2026, 1, 31)),
        (date(2026, 2, 1), date(2026, 2, 28)),
        (date(2024, 2, 1), date(2024, 2, 29)),
        (date(2026, 4, 1), date(2026, 4, 30)),
        (date(2026, 12, 1), date(2026, 12, 31)),
    ],
)
def test_fim_do_mes_cobre_dezembro_e_ano_bissexto(competencia, ultimo_dia):
    """Dezembro e fevereiro bissexto são onde cálculo de fim de mês quebra."""
    from dashboard.workspace_provider import _fim_do_mes

    assert _fim_do_mes(competencia) == ultimo_dia


# ── Ponta a ponta ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_fluxo_completo_com_o_provider_real(equipe):
    """Aprovar → comprometer → ver a barra tripla → baixar."""
    from dashboard.models import CentroCusto

    CentroCusto.objects.create(
        codigo="1008", nome="TI", departamento="TI",
        orcamento_mensal=Decimal("38000"), status="ativo",
    )

    s = apr.criar(
        dominio="com.requisicao", titulo="4 notebooks", solicitante=equipe["ana"],
        valor=Decimal("12400"), centro_custo_codigo="1008",
    )
    r = orc.resumo("1008")
    assert r.percentual() == Decimal("0.0")
    assert r.percentual(Decimal("12400")) == Decimal("32.6"), "efeito antes de decidir"

    apr.decidir(s, equipe["gestor"], apr.Decisao.APROVAR)

    r = orc.resumo("1008")
    assert r.comprometido == Decimal("12400")
    assert r.percentual() == Decimal("32.6"), "agora está reservado"

    orc.baixar(Compromisso.objects.get(), movimentacao_id="777")
    assert orc.resumo("1008").comprometido == Decimal("0")
