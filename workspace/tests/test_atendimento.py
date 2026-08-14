"""ATD — a fila de quem atende, depois da aprovação.

O buraco que estes testes fecham era estrutural: `EM_ATENDIMENTO` e `CONCLUIDA`
existiam como estados, `concluir()` existia no modelo, e **nada no produto os
usava**. O pedido era aprovado e parava ali para sempre.

O que se protege aqui:

1. **A fila é de quem pode atender aquele domínio** — e quem não atende nada
   não vê tela nenhuma.
2. **Concluir alimenta o prazo REAL do catálogo.** Sem isto, `prazo_medido()`
   nunca sairia do prometido, e o número da tela seria sempre um chute.
3. **Devolver daqui não é reprovar**: a aprovação continua valendo, o motivo é
   obrigatório e o pedido volta para quem pediu.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.models import (
    GrupoCatalogo,
    ItemCatalogo,
    Notificacao,
    SituacaoServico,
    SolicitacaoServico,
    TipoNotificacao,
)
from workspace.services import atendimento as atd
from workspace.services import catalogo as svc
from workspace.services.atendimento import AtendimentoError

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    ana, ti, rh = (f.pessoa(n) for n in ("ana", "tecnico", "rh"))
    for pessoa in (ana, ti, rh):
        f.lotar(pessoa)

    f.atribuir(ti, f.papel("ti", ["ti.atender.unidade"], escopo="unidade"))
    f.atribuir(rh, f.papel("rh", ["rh.atender.global"], escopo="global"))

    chamado = ItemCatalogo.objects.create(
        chave="equipamento-quebrado", nome="Equipamento parado",
        grupo=GrupoCatalogo.EQUIPAMENTO, dominio="ti.chamado",
        prazo_prometido_dias=2, limite_auto_aprovacao=Decimal("0"),
        campos=[{"chave": "o_que", "rotulo": "O que houve", "obrigatorio": True}],
    )
    ferias = ItemCatalogo.objects.create(
        chave="ferias", nome="Férias", grupo=GrupoCatalogo.TRABALHO,
        dominio="rh.ferias", prazo_prometido_dias=2,
        limite_auto_aprovacao=Decimal("0"),
        campos=[{"chave": "dias", "rotulo": "Dias", "obrigatorio": True}],
    )
    return {"ana": ana, "ti": ti, "rh": rh, "chamado": chamado, "ferias": ferias}


def pedir(cenario, item="chamado", campo="o_que", valor="A tela apagou"):
    """Um pedido já aprovado — é onde a fila começa."""
    return svc.solicitar(cenario[item], cenario["ana"], {campo: valor})


# ── Quem vê qual fila ───────────────────────────────────────────────


def test_a_fila_e_do_dominio_que_a_pessoa_atende(cenario):
    chamado = pedir(cenario)
    ferias = pedir(cenario, item="ferias", campo="dias", valor="10")

    assert list(atd.fila_de(cenario["ti"])) == [chamado]
    assert list(atd.fila_de(cenario["rh"])) == [ferias]


def test_quem_nao_atende_nada_nao_tem_fila(cenario):
    pedir(cenario)
    assert not atd.fila_de(cenario["ana"]).exists()
    assert atd.atende_alguma_coisa(cenario["ana"]) is False


def test_a_tela_recusa_quem_nao_atende_nada(client, cenario):
    """403 e não uma tela vazia: "sua fila está vazia" para quem não atende
    nada é mentira, e faz a pessoa esperar por trabalho que nunca vem."""
    client.force_login(cenario["ana"])
    assert client.get(reverse("workspace:fila")).status_code == 403


def test_pedido_esperando_aprovacao_nao_entra_na_fila(cenario):
    """Não há o que atender enquanto ninguém decidiu."""
    item = cenario["chamado"]
    item.limite_auto_aprovacao = None  # sempre passa pela cadeia
    item.save(update_fields=["limite_auto_aprovacao"])

    pedir(cenario)
    assert not atd.fila_de(cenario["ti"]).exists()


def test_a_fila_e_do_mais_antigo_para_o_mais_novo(cenario):
    """Fila que se reordena sozinha é fila em que o pedido pequeno de janeiro
    nunca é atendido."""
    primeiro = pedir(cenario)
    segundo = pedir(cenario, valor="O teclado quebrou")

    assert list(atd.fila_de(cenario["ti"])) == [primeiro, segundo]


# ── Assumir ─────────────────────────────────────────────────────────


def test_assumir_poe_um_nome_no_pedido(cenario):
    """Sem dono, o pedido fica esperando "o setor" — e setor nenhum atende."""
    chamado = atd.assumir(pedir(cenario), cenario["ti"])

    assert chamado.atendente == cenario["ti"]
    assert chamado.situacao == SituacaoServico.EM_ATENDIMENTO


def test_o_que_foi_assumido_continua_na_fila(cenario):
    """Some-lo faria a pessoa perder de vista o próprio trabalho em curso."""
    chamado = atd.assumir(pedir(cenario), cenario["ti"])
    assert list(atd.fila_de(cenario["ti"])) == [chamado]


def test_nao_se_toma_o_pedido_de_outra_pessoa(cenario):
    outro = f.pessoa("bruno")
    f.lotar(outro)
    f.atribuir(outro, f.papel("ti2", ["ti.atender.unidade"], escopo="unidade"))

    chamado = atd.assumir(pedir(cenario), cenario["ti"])
    with pytest.raises(AtendimentoError, match="já assumiu"):
        atd.assumir(chamado, outro)


def test_assumir_da_fila_alheia_e_recusado(cenario):
    with pytest.raises(AtendimentoError, match="não é da sua fila"):
        atd.assumir(pedir(cenario), cenario["rh"])


def test_assumir_avisa_quem_pediu(cenario):
    atd.assumir(pedir(cenario), cenario["ti"])

    aviso = Notificacao.objects.de(cenario["ana"]).get()
    assert aviso.tipo == TipoNotificacao.PEDIDO_EM_ATENDIMENTO


# ── Concluir, e o prazo real ────────────────────────────────────────


def test_concluir_fecha_e_avisa(cenario):
    chamado = atd.concluir(pedir(cenario), cenario["ti"])

    assert chamado.situacao == SituacaoServico.CONCLUIDA
    assert chamado.concluido_em is not None
    assert (
        Notificacao.objects.de(cenario["ana"]).get().tipo
        == TipoNotificacao.PEDIDO_CONCLUIDO
    )


def test_concluir_sem_assumir_registra_quem_atendeu(cenario):
    """Para o pedido de dois minutos, exigir "assumir" antes seria dois cliques
    para o mesmo fim. Mas o nome fica."""
    chamado = atd.concluir(pedir(cenario), cenario["ti"])
    assert chamado.atendente == cenario["ti"]


def test_concluido_sai_da_fila(cenario):
    atd.concluir(pedir(cenario), cenario["ti"])
    assert not atd.fila_de(cenario["ti"]).exists()


def test_nao_se_conclui_duas_vezes(cenario):
    chamado = atd.concluir(pedir(cenario), cenario["ti"])
    with pytest.raises(AtendimentoError, match="não há o que atender"):
        atd.concluir(chamado, cenario["ti"])


def test_concluir_e_o_que_faz_o_prazo_do_catalogo_ser_medido(cenario):
    """A razão de este módulo existir.

    `prazo_medido()` só troca o prometido pelo medido depois de 5 conclusões —
    e antes desta fila NADA no produto concluía nada. O card do catálogo diria
    "estimado" para sempre.
    """
    item = cenario["chamado"]
    assert svc.prazo_medido(item) == (2, False), "sem histórico, é o prometido"

    for _ in range(5):
        atd.concluir(pedir(cenario), cenario["ti"])

    dias, medido = svc.prazo_medido(item)
    assert medido is True, "cinco conclusões: o prazo passa a ser o real"
    assert dias == 0


# ── Devolver ────────────────────────────────────────────────────────


def test_devolver_exige_motivo(cenario):
    """Sem motivo, quem recebe de volta adivinha — e adivinhar gera um segundo
    envio igualmente errado."""
    with pytest.raises(AtendimentoError, match="Diga o que falta"):
        atd.devolver(pedir(cenario), cenario["ti"], "   ")


def test_devolver_volta_para_quem_pediu_com_o_motivo(cenario):
    chamado = atd.devolver(
        pedir(cenario), cenario["ti"], "Diga o número de patrimônio do aparelho"
    )

    assert chamado.situacao == SituacaoServico.DEVOLVIDA
    assert "patrimônio" in chamado.motivo_devolucao
    assert (
        Notificacao.objects.de(cenario["ana"]).get().tipo
        == TipoNotificacao.PEDIDO_DEVOLVIDO
    )


# ── A tela ──────────────────────────────────────────────────────────


def test_a_tela_lista_e_conta(client, cenario):
    pedir(cenario)
    client.force_login(cenario["ti"])

    corpo = client.get(reverse("workspace:fila")).content.decode()

    assert "Equipamento parado" in corpo
    assert "Assumir" in corpo and "Concluir" in corpo
    assert "ana" in corpo.lower()


def test_concluir_pela_tela(client, cenario):
    chamado = pedir(cenario)
    client.force_login(cenario["ti"])

    resposta = client.post(
        reverse("workspace:atender", args=[chamado.pk]), {"acao": "concluir"}
    )

    assert resposta.status_code == 302
    chamado.refresh_from_db()
    assert chamado.situacao == SituacaoServico.CONCLUIDA


def test_devolver_sem_motivo_pela_tela_explica(client, cenario):
    chamado = pedir(cenario)
    client.force_login(cenario["ti"])

    client.post(
        reverse("workspace:atender", args=[chamado.pk]),
        {"acao": "devolver", "motivo": ""},
        follow=True,
    )

    chamado.refresh_from_db()
    assert chamado.situacao == SituacaoServico.APROVADA, "não devolveu"


def test_atender_pedido_de_outra_fila_pela_tela(client, cenario):
    """A permissão é conferida no serviço, e a tela não é a fonte de verdade:
    este POST existe mesmo sem botão na tela de ninguém."""
    ferias = pedir(cenario, item="ferias", campo="dias", valor="10")
    client.force_login(cenario["ti"])

    client.post(reverse("workspace:atender", args=[ferias.pk]), {"acao": "concluir"})

    ferias.refresh_from_db()
    assert ferias.situacao == SituacaoServico.APROVADA


def test_a_fila_exige_identidade(client, cenario):
    resposta = client.get(reverse("workspace:fila"))
    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/entrar/")


def test_o_trilho_conta_a_fila(client, cenario):
    pedir(cenario)
    client.force_login(cenario["ti"])

    corpo = client.get(reverse("workspace:servicos")).content.decode()
    assert "Atender" in corpo


def test_quem_nao_atende_nao_ve_o_item_no_trilho(client, cenario):
    pedir(cenario)
    client.force_login(cenario["ana"])

    corpo = client.get(reverse("workspace:servicos")).content.decode()
    assert "workspace/fila" not in corpo
