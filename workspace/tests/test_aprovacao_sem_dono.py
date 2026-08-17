"""APR — o pedido que para num papel que ninguém ocupa.

Era o jeito mais silencioso de o produto perder um pedido. A cadeia manda para
"Compras", ninguém tem o papel de Compras, e a etapa **não aparece na bandeja
de pessoa nenhuma** — etapa por papel não gera notificação, de propósito, e o
contador da bandeja de todo mundo continua zerado.

Do lado de quem pediu: "aguardando aprovação", para sempre. Do outro lado não
havia lado.

O que estes testes protegem:

1. **Quem pode conceder o papel é avisado.** É a única pessoa capaz de tirar o
   pedido dali, e o aviso leva à tela de papéis — não à bandeja, porque quem
   recebe não tem o que decidir.
2. **Papel COM titular continua em silêncio.** O aviso é para o defeito, não
   para o funcionamento normal.
3. **Quem pediu vê o motivo da parada.** Não pode consertar, mas silêncio é o
   que faz a pessoa mandar e-mail perguntando.
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
