"""ATD — o degrau que faltava: avisar a ÁREA que o pedido caiu na fila dela.

## O que estava quebrado

Todo aviso do módulo de atendimento ia para quem PEDIU. `assumir`, `concluir`,
`devolver` — todos falam com o solicitante. Do outro lado não havia lado: a
área que executa só descobria trabalho novo abrindo a tela da fila.

O efeito disso é o bug que parecia ser de workflow. Rastreado no banco de
desenvolvimento, o motor sempre esteve certo — gestor aprova, o pedido vira
`APROVADA`, `APROVADA` está em `NA_FILA`, e ele aparece na fila do TI. O que
não acontecia era alguém contar isso ao TI. De onde o solicitante estava, o
pedido dizia "Aprovada" e parava, e a leitura óbvia era a de que aprovar
devolve o pedido a quem pediu.

## Os dois caminhos, e por que os dois

Um pedido entra na fila por duas portas: aprovado pela cadeia, ou auto-aprovado
na criação. A segunda é a mais comum e era a mais silenciosa — nem passava por
uma bandeja onde alguém veria.

## Quem NÃO recebe

Quem pediu, mesmo que atenda a própria área: ele acabou de clicar. Quem atende
outro domínio. E o superusuário, que receberia cópia de cada pedido de cada
área da empresa.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from identidade.tests import fabricas as f
from workspace.models import (
    GrupoCatalogo,
    ItemCatalogo,
    Notificacao,
    SituacaoServico,
    TipoNotificacao,
)
from identidade.models import AtribuicaoPapel, Lotacao
from workspace.models import RegraAprovacao, TipoAprovador
from workspace.services import aprovacao as apr
from workspace.services import atendimento as atd
from workspace.services import catalogo as svc

pytestmark = pytest.mark.django_db


def _item(chave="acesso", dominio="ti.acesso", auto=True):
    return ItemCatalogo.objects.create(
        chave=chave,
        nome="Acesso a um sistema",
        grupo=GrupoCatalogo.EQUIPAMENTO,
        dominio=dominio,
        prazo_prometido_dias=2,
        # `None` = nunca auto-aprova, e é o que força a cadeia humana.
        limite_auto_aprovacao=Decimal("0") if auto else None,
        campos=[{"chave": "o_que", "rotulo": "O quê", "obrigatorio": True}],
    )


@pytest.fixture
def cenario():
    ana, tecnico, rh = (f.pessoa(n) for n in ("ana", "tecnico", "rh"))
    for pessoa in (ana, tecnico, rh):
        f.lotar(pessoa)
    f.atribuir(tecnico, f.papel("ti", ["ti.atender.global"], escopo="global"))
    f.atribuir(rh, f.papel("rh", ["rh.atender.global"], escopo="global"))
    return {"ana": ana, "tecnico": tecnico, "rh": rh, "item": _item()}


def _com_gestor(cenario):
    """Põe um gestor sobre a ana e liga a regra de gestor direto.

    A cadeia de aprovação sai do ORGANOGRAMA: `GESTOR_DIRETO` lê `Lotacao.gestor`.
    Sem a regra, `apr.criar()` monta um pedido sem degrau nenhum.
    """
    gestor = f.pessoa("gestor")
    f.lotar(gestor)
    Lotacao.objects.filter(user=cenario["ana"]).update(gestor=gestor)
    RegraAprovacao.objects.create(
        dominio="*", tipo=TipoAprovador.GESTOR_DIRETO, ordem=10
    )
    return gestor


def _avisos_de_fila(pessoa):
    return Notificacao.objects.filter(
        destinatario=pessoa, tipo=TipoNotificacao.PEDIDO_NA_FILA
    )


# ── quem_atende: a pergunta inversa que o produto não sabia fazer ───


def test_quem_atende_devolve_quem_tem_a_permissao_do_dominio(cenario):
    assert atd.quem_atende("ti.acesso") == [cenario["tecnico"]]
    assert atd.quem_atende("rh.ferias") == [cenario["rh"]]


def test_quem_atende_dominio_sem_ninguem_e_lista_vazia(cenario):
    assert atd.quem_atende("jur.parecer") == []


def test_quem_atende_ignora_o_superusuario(cenario):
    """Conta técnica não é atendente. Incluí-la faria o superusuário receber
    cópia de cada pedido de cada área — que é como um sino deixa de ser lido."""
    raiz = f.pessoa("raiz")
    raiz.is_superuser = True
    raiz.save(update_fields=["is_superuser"])

    assert raiz not in atd.quem_atende("ti.acesso")


def test_quem_atende_ignora_quem_perdeu_o_papel(cenario):
    """Atribuição vencida não atende mais. `vigentes()` é quem decide isso."""
    from datetime import timedelta

    from django.utils import timezone

    AtribuicaoPapel.objects.filter(user=cenario["tecnico"]).update(
        # `localdate()` e não `now().date()`: depois das 21h no fuso local, o
        # UTC já virou o dia, e "ontem em UTC" ainda é hoje aqui — o papel
        # continuaria vigente e o teste reprovaria por causa do relógio.
        vigencia_fim=timezone.localdate() - timedelta(days=1)
    )
    assert atd.quem_atende("ti.acesso") == []


# ── Auto-aprovado: a porta silenciosa ───────────────────────────────


def test_auto_aprovado_avisa_a_area(cenario):
    pedido = svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "VPN"})

    assert pedido.situacao == SituacaoServico.APROVADA
    aviso = _avisos_de_fila(cenario["tecnico"]).get()
    assert aviso.titulo == "Acesso a um sistema entrou na sua fila"
    assert cenario["ana"].get_full_name() in aviso.corpo


def test_o_aviso_leva_a_fila_e_nao_as_minhas_solicitacoes(cenario):
    """O destinatário é quem ATENDE. Mandá-lo para "Minhas solicitações" o
    levaria à lista dos pedidos dele mesmo, onde este pedido não está."""
    from django.urls import reverse

    svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "VPN"})

    assert _avisos_de_fila(cenario["tecnico"]).get().url == reverse("workspace:fila")


def test_quem_atende_outro_dominio_nao_recebe(cenario):
    svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "VPN"})

    assert not _avisos_de_fila(cenario["rh"]).exists()


def test_quem_pediu_nao_recebe_copia_mesmo_atendendo_a_propria_area(cenario):
    """O técnico pedindo acesso para si: ele acabou de clicar, e o aviso de
    aprovação já é dele. Um segundo aviso dizendo que o próprio pedido chegou
    na própria fila é a definição de ruído."""
    svc.solicitar(cenario["item"], cenario["tecnico"], {"o_que": "VPN"})

    assert not _avisos_de_fila(cenario["tecnico"]).exists()


# ── Aprovado pela cadeia: o caso que virou o relato de bug ──────────


def test_aprovado_pela_cadeia_avisa_a_area(cenario):
    gestor = _com_gestor(cenario)

    pedido = svc.solicitar(_item("vpn", auto=False), cenario["ana"], {"o_que": "VPN"})
    assert pedido.situacao == SituacaoServico.AGUARDANDO_APROVACAO
    assert not _avisos_de_fila(cenario["tecnico"]).exists()

    apr.decidir(pedido.aprovacao, gestor, apr.Decisao.APROVAR)

    pedido.refresh_from_db()
    assert pedido.situacao == SituacaoServico.APROVADA
    assert list(atd.fila_de(cenario["tecnico"])) == [pedido]
    assert _avisos_de_fila(cenario["tecnico"]).count() == 1


def test_devolver_na_aprovacao_nao_avisa_a_fila(cenario):
    """Devolvido não entrou em fila nenhuma — ele voltou para quem pediu."""
    gestor = _com_gestor(cenario)

    pedido = svc.solicitar(_item("vpn", auto=False), cenario["ana"], {"o_que": "VPN"})
    apr.decidir(pedido.aprovacao, gestor, apr.Decisao.DEVOLVER, "Faltou o motivo.")

    assert not _avisos_de_fila(cenario["tecnico"]).exists()


# ── A guarda do próprio serviço ─────────────────────────────────────


def test_avisar_a_fila_recusa_pedido_que_nao_esta_na_fila(cenario):
    """A função é chamada de dois lugares e um terceiro vai aparecer. A guarda
    é o que impede que ela avise a área sobre um pedido cancelado."""
    pedido = svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "VPN"})
    _avisos_de_fila(cenario["tecnico"]).delete()
    pedido.situacao = SituacaoServico.CANCELADA
    pedido.save(update_fields=["situacao"])

    assert atd.avisar_a_fila(pedido) == 0
    assert not _avisos_de_fila(cenario["tecnico"]).exists()
