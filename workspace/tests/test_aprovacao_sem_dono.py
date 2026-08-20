"""APR — o pedido que para num papel que ninguém ocupa.

Era o jeito mais silencioso de o produto perder um pedido. A cadeia manda para
"Compras", ninguém tem o papel de Compras, e a etapa **não aparece na bandeja
de pessoa nenhuma**: o contador da bandeja de todo mundo continua zerado.

Do lado de quem pediu: "aguardando aprovação", para sempre. Do outro lado não
havia lado.

O que estes testes protegem:

1. **Quem pode conceder o papel é avisado.** É a única pessoa capaz de tirar o
   pedido dali, e o aviso leva à tela de papéis — não à bandeja, porque quem
   recebe não tem o que decidir.
2. **Quem pediu vê o motivo da parada.** Não pode consertar, mas silêncio é o
   que faz a pessoa mandar e-mail perguntando.

## A segunda metade, de agosto

A etapa por papel COM titular também era silenciosa, e isso era decisão
explícita: "Financeiro" são três pessoas, e três avisos significariam que
aprovar um deixaria dois órfãos apontando para um pedido já decidido.

O relato do testador mostrou o custo: *pedi um adiantamento, o gestor aprovou,
fui no Financeiro e não tinha nada*. Estava lá — na etapa por papel do
Financeiro, sem que ninguém tivesse sido avisado. Quem pediu achou que o pedido
sumiu; o Financeiro não sabia que tinha um.

A resposta para a notificação órfã não é calar. É `encerrar_avisos_da_vez()`,
que marca as irmãs como lidas assim que o degrau anda — e é a última seção
deste arquivo que a mantém honesta.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.models import AtribuicaoPapel, Lotacao
from identidade.services.administracao import quem_administra
from identidade.tests import fabricas as f
from workspace.models import (
    GrupoCatalogo,
    ItemCatalogo,
    Notificacao,
    RegraAprovacao,
    TipoAprovador,
    TipoNotificacao,
)
from workspace.services import catalogo as svc
from workspace.services import mapa_aprovacao as mapa

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    ana, admin = (f.pessoa(n) for n in ("ana", "admin"))
    f.lotar(ana)
    f.lotar(admin)
    f.atribuir(admin, f.papel("rh_admin", ["rh.admin.global"], escopo="global"))

    compras = f.papel("compras", ["apr.aprovar.global"], escopo="global")
    item = ItemCatalogo.objects.create(
        chave="cadeira", nome="Cadeira nova", grupo=GrupoCatalogo.EQUIPAMENTO,
        dominio="com.requisicao", exige_valor=True, limite_auto_aprovacao=None,
        campos=[{"chave": "o_que", "rotulo": "O quê", "obrigatorio": True}],
    )
    RegraAprovacao.objects.create(
        dominio="com.", tipo=TipoAprovador.PAPEL, papel=compras, ordem=15
    )
    return {"ana": ana, "admin": admin, "compras": compras, "item": item}


def pedir(cenario):
    return svc.solicitar(
        cenario["item"], cenario["ana"], {"o_que": "Cadeira"}, valor=Decimal("900")
    )


# ── O mapa dos papéis vagos ─────────────────────────────────────────


def test_papel_de_regra_sem_titular_e_orfao(cenario):
    assert mapa.papeis_sem_titular() == {cenario["compras"].pk}


def test_papel_com_titular_nao_e_orfao(cenario):
    f.atribuir(cenario["ana"], cenario["compras"])

    assert mapa.papeis_sem_titular() == set()


def test_papel_que_nao_aprova_nada_nao_conta(cenario):
    """Papel sem titular que não aparece em regra nenhuma não trava pedido, e
    listá-lo transformaria a marca de "parado" em ruído."""
    f.papel("clube_do_bolinha", ["nada.fazer"])

    assert mapa.papeis_sem_titular() == {cenario["compras"].pk}


def test_titular_com_vigencia_encerrada_nao_ocupa(cenario):
    """Papel que expirou é papel vago — a vigência existe justamente para isso."""
    atribuicao = f.atribuir(cenario["ana"], cenario["compras"])
    AtribuicaoPapel.objects.filter(pk=atribuicao.pk).update(
        vigencia_fim=timezone.localdate() - timedelta(days=1)
    )

    assert mapa.papeis_sem_titular() == {cenario["compras"].pk}


# ── O aviso, e para quem ele vai ────────────────────────────────────


def test_quem_concede_papel_e_avisado(cenario):
    pedir(cenario)

    aviso = Notificacao.objects.de(cenario["admin"]).get(
        tipo=TipoNotificacao.APROVACAO_SEM_DONO
    )
    assert "Compras" in aviso.titulo
    assert aviso.url == reverse("workspace:pessoas"), "leva a conceder, não a decidir"


def test_papel_com_titular_nao_gera_aviso(cenario):
    """O aviso é para o defeito, não para o funcionamento normal."""
    f.atribuir(cenario["ana"], cenario["compras"])

    pedir(cenario)

    assert not Notificacao.objects.filter(
        tipo=TipoNotificacao.APROVACAO_SEM_DONO
    ).exists()


def test_quem_pediu_nao_recebe_o_aviso(cenario):
    """Ela não tem o que fazer com ele — o aviso é para quem concede."""
    pedir(cenario)

    assert not Notificacao.objects.de(cenario["ana"]).filter(
        tipo=TipoNotificacao.APROVACAO_SEM_DONO
    ).exists()


def test_etapa_nominal_continua_avisando_o_aprovador(cenario):
    """A mudança não pode ter roubado o caminho normal."""
    gestor = f.pessoa("gestor")
    f.lotar(gestor)
    Lotacao.objects.filter(user=cenario["ana"]).update(gestor=gestor)
    RegraAprovacao.objects.create(
        dominio="com.", tipo=TipoAprovador.GESTOR_DIRETO, ordem=10
    )

    pedir(cenario)

    assert Notificacao.objects.de(gestor).filter(
        tipo=TipoNotificacao.VEZ_DE_APROVAR
    ).exists()


def test_sem_ninguem_para_avisar_nada_estoura(cenario):
    """Empresa sem `rh.admin` cadastrado: o pedido para do mesmo jeito, e o
    produto não pode quebrar por causa disso."""
    AtribuicaoPapel.objects.all().delete()

    pedir(cenario)  # não levanta

    assert Notificacao.objects.filter(
        tipo=TipoNotificacao.APROVACAO_SEM_DONO
    ).count() == 0


# ── Quem administra ─────────────────────────────────────────────────


def test_quem_administra_encontra_o_rh(cenario):
    assert list(quem_administra()) == [cenario["admin"]]


def test_superusuario_entra_na_conta(cenario):
    """É a saída de emergência do Django, e tirá-la faria a empresa sem R.H.
    cadastrado não ter ninguém a quem avisar."""
    chefe = f.pessoa("chefe", is_superuser=True)

    assert chefe in quem_administra()


def test_quem_nao_administra_fica_de_fora(cenario):
    assert cenario["ana"] not in quem_administra()


# ── A tela de quem pediu ────────────────────────────────────────────


def test_a_tela_diz_por_que_o_pedido_esta_parado(client, cenario):
    """Quem lê não pode consertar. Mas silêncio é o que faz a pessoa mandar
    e-mail perguntando — que é o que o Workspace existe para substituir."""
    pedir(cenario)

    client.force_login(cenario["ana"])
    corpo = client.get(reverse("workspace:minhas_solicitacoes")).content.decode()

    assert "ninguém tem este papel hoje" in corpo


def test_pedido_com_aprovador_de_verdade_nao_ganha_a_marca(client, cenario):
    f.atribuir(cenario["ana"], cenario["compras"])
    pedir(cenario)

    client.force_login(cenario["ana"])
    corpo = client.get(reverse("workspace:minhas_solicitacoes")).content.decode()

    assert "ninguém tem este papel hoje" not in corpo


# ── A etapa por papel deixou de ser silenciosa ──────────────────────
#
# Era silêncio de propósito, e a razão era boa: "Financeiro" são três pessoas, e
# três notificações significariam que aprovar uma deixaria duas órfãs apontando
# para um pedido já decidido. O aviso seria o contador da bandeja.
#
# A rodada de testes de agosto mostrou que o contador não basta. Relato do
# testador: pedi um adiantamento, o gestor aprovou, fui no Financeiro e não
# tinha nada. Estava lá — na etapa por papel do Financeiro, sem que ninguém
# tivesse sido avisado. Os dois lados concluíram que o pedido se perdeu.
#
# A resposta para a notificação órfã não é calar: é limpar as irmãs quando o
# degrau anda.


def test_quem_tem_o_papel_e_avisado(cenario):
    titular = f.pessoa("titular")
    f.lotar(titular)
    f.atribuir(titular, cenario["compras"])

    pedir(cenario)

    assert Notificacao.objects.de(titular).filter(
        tipo=TipoNotificacao.VEZ_DE_APROVAR
    ).exists()


def test_todos_os_titulares_sao_avisados(cenario):
    """A etapa não é de ninguém em particular — é de quem tiver o crachá.
    Avisar só um faria a fila depender de quem o acaso escolheu."""
    titulares = []
    for nome in ("um", "dois", "tres"):
        pessoa = f.pessoa(nome)
        f.lotar(pessoa)
        f.atribuir(pessoa, cenario["compras"])
        titulares.append(pessoa)

    pedir(cenario)

    for titular in titulares:
        assert Notificacao.objects.de(titular).filter(
            tipo=TipoNotificacao.VEZ_DE_APROVAR
        ).exists(), titular


def test_decidir_apaga_o_aviso_dos_outros_titulares(cenario):
    """A objeção original ao aviso por papel, resolvida: quem não clicou não
    fica com "espera sua decisão" apontando para um pedido já decidido."""
    from workspace.services import aprovacao as apr

    quem_decide, o_outro = f.pessoa("decide"), f.pessoa("outro")
    for pessoa in (quem_decide, o_outro):
        f.lotar(pessoa)
        f.atribuir(pessoa, cenario["compras"])
    pedido = pedir(cenario)

    apr.decidir(pedido.aprovacao, quem_decide, "aprovar")

    assert not Notificacao.objects.de(o_outro).nao_lidas().filter(
        tipo=TipoNotificacao.VEZ_DE_APROVAR
    ).exists()


def test_o_aviso_da_vez_anda_junto_com_a_cadeia(cenario):
    """Dois degraus: o aviso do primeiro é encerrado e o do segundo nasce.

    É o caso do adiantamento — gestor direto, depois o papel da área —, e é
    onde o silêncio doeu.
    """
    from workspace.models import RegraAprovacao, TipoAprovador
    from workspace.services import aprovacao as apr

    gestor, titular = f.pessoa("gestor"), f.pessoa("titular")
    f.lotar(gestor)
    f.lotar(titular)
    f.atribuir(titular, cenario["compras"])
    Lotacao.objects.filter(user=cenario["ana"]).update(gestor=gestor)
    RegraAprovacao.objects.create(
        dominio="com.", tipo=TipoAprovador.GESTOR_DIRETO, ordem=10
    )

    pedido = pedir(cenario)
    assert Notificacao.objects.de(gestor).nao_lidas().filter(
        tipo=TipoNotificacao.VEZ_DE_APROVAR
    ).exists(), "o primeiro degrau avisa"
    assert not Notificacao.objects.de(titular).nao_lidas().filter(
        tipo=TipoNotificacao.VEZ_DE_APROVAR
    ).exists(), "o segundo degrau ainda não é a vez de ninguém"

    apr.decidir(pedido.aprovacao, gestor, "aprovar")

    assert not Notificacao.objects.de(gestor).nao_lidas().filter(
        tipo=TipoNotificacao.VEZ_DE_APROVAR
    ).exists(), "o gestor já decidiu — o aviso dele não vale mais"
    assert Notificacao.objects.de(titular).nao_lidas().filter(
        tipo=TipoNotificacao.VEZ_DE_APROVAR
    ).exists(), "agora é a vez do papel, e o papel precisa saber"


def test_a_fase_diz_de_quem_e_a_vez(cenario):
    """"Aguardando aprovação" sozinho é a mesma frase antes e depois de o
    gestor aprovar — e quem pediu conclui que o clique dele não fez nada."""
    from workspace.models import RegraAprovacao, TipoAprovador
    from workspace.services import aprovacao as apr

    gestor = f.pessoa("gestor")
    f.lotar(gestor)
    f.atribuir(f.pessoa("titular"), cenario["compras"])
    Lotacao.objects.filter(user=cenario["ana"]).update(gestor=gestor)
    RegraAprovacao.objects.create(
        dominio="com.", tipo=TipoAprovador.GESTOR_DIRETO, ordem=10
    )

    pedido = pedir(cenario)
    assert pedido.fase == f"Aguardando aprovação · {gestor.get_short_name()}"

    apr.decidir(pedido.aprovacao, gestor, "aprovar")
    pedido.refresh_from_db()

    assert pedido.fase == "Aguardando aprovação · Compras"
