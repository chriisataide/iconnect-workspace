"""HST — o histórico de um pedido, e quem fez o quê.

A pergunta que não se conseguia responder antes deste módulo: **"esse pedido
está parado há duas semanas — o que aconteceu com ele?"**. `EtapaAprovacao`
guardava as decisões de aprovação, e só. Quem assumiu o atendimento e largou,
quem devolveu e por quê, quem cancelou — nada disso deixava rastro.

O que estes testes protegem:

1. **Todo ato que muda o estado do pedido vira linha**, em cada um dos caminhos.
2. **A linha do tempo é do mais antigo para o mais novo** — ela se lê de cima
   para baixo.
3. **Ato sem gente é caso legítimo**: a auto-aprovação não tem autor, e
   inventar um faria o histórico mentir sobre quem assinou.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.models import (
    AcaoSolicitacao,
    EventoSolicitacao,
    GrupoCatalogo,
    ItemCatalogo,
    RegraAprovacao,
    TipoAprovador,
)
from workspace.services import aprovacao as apr
from workspace.services import atendimento as atd
from workspace.services import catalogo as svc
from workspace.services import historico as hst

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    ana, gestor, tecnico = (f.pessoa(n) for n in ("ana", "gestor", "tecnico"))
    f.lotar(gestor)
    f.lotar(ana, gestor=gestor)
    f.lotar(tecnico)
    f.atribuir(gestor, f.papel("gestor", ["apr.aprovar.equipe"], escopo="equipe"))
    f.atribuir(tecnico, f.papel("ti", ["ti.atender.unidade"], escopo="unidade"))

    item = ItemCatalogo.objects.create(
        chave="chamado", nome="Equipamento parado",
        grupo=GrupoCatalogo.EQUIPAMENTO, dominio="ti.chamado",
        campos=[{"chave": "o_que", "rotulo": "O que houve", "obrigatorio": True}],
        limite_auto_aprovacao=None,  # sempre passa pela cadeia
    )
    RegraAprovacao.objects.create(
        dominio="*", tipo=TipoAprovador.GESTOR_DIRETO, ordem=10
    )
    return {"ana": ana, "gestor": gestor, "tecnico": tecnico, "item": item}


def pedir(cenario):
    return svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "A tela apagou"})


def acoes(solicitacao):
    return [e.acao for e in hst.de(solicitacao)]


# ── Cada ato vira linha ─────────────────────────────────────────────


def test_abrir_o_pedido_e_a_primeira_linha(cenario):
    pedido = pedir(cenario)

    evento = hst.de(pedido).get()
    assert evento.acao == AcaoSolicitacao.CRIADA
    assert evento.quem == cenario["ana"]


def test_auto_aprovacao_nao_tem_autor(cenario):
    """Ninguém decidiu — o pedido coube na política. Inventar um autor aqui
    faria o histórico mentir sobre quem assinou."""
    cenario["item"].limite_auto_aprovacao = Decimal("0")
    cenario["item"].save(update_fields=["limite_auto_aprovacao"])

    pedido = pedir(cenario)

    auto = hst.de(pedido).get(acao=AcaoSolicitacao.AUTO_APROVADA)
    assert auto.quem is None
    assert "limite" in auto.observacao


def test_aprovacao_do_gestor_entra_no_historico_do_pedido(cenario):
    """Quem lê a linha do tempo não deveria precisar abrir a bandeja para saber
    quem assinou."""
    pedido = pedir(cenario)
    apr.decidir(pedido.aprovacao, cenario["gestor"], apr.Decisao.APROVAR)

    aprovacao = hst.de(pedido).get(acao=AcaoSolicitacao.APROVADA)
    assert aprovacao.quem == cenario["gestor"]


def test_devolucao_guarda_o_motivo(cenario):
    pedido = pedir(cenario)
    apr.decidir(
        pedido.aprovacao, cenario["gestor"], apr.Decisao.DEVOLVER,
        "Diga o número de patrimônio",
    )

    devolucao = hst.de(pedido).get(acao=AcaoSolicitacao.DEVOLVIDA)
    assert "patrimônio" in devolucao.observacao


def test_cancelar_o_proprio_pedido_vira_linha(cenario):
    pedido = pedir(cenario)
    svc.cancelar(pedido, cenario["ana"])

    assert AcaoSolicitacao.CANCELADA in acoes(pedido)


def test_assumir_e_concluir_viram_linhas(cenario):
    pedido = pedir(cenario)
    apr.decidir(pedido.aprovacao, cenario["gestor"], apr.Decisao.APROVAR)
    pedido.refresh_from_db()

    atd.assumir(pedido, cenario["tecnico"])
    atd.concluir(pedido, cenario["tecnico"])

    registradas = acoes(pedido)
    assert AcaoSolicitacao.ASSUMIDA in registradas
    assert AcaoSolicitacao.CONCLUIDA in registradas
    assert hst.de(pedido).get(acao=AcaoSolicitacao.CONCLUIDA).quem == cenario["tecnico"]


def test_devolver_no_atendimento_guarda_o_motivo(cenario):
    pedido = pedir(cenario)
    apr.decidir(pedido.aprovacao, cenario["gestor"], apr.Decisao.APROVAR)
    pedido.refresh_from_db()

    atd.devolver(pedido, cenario["tecnico"], "Falta o número de série")

    devolucao = hst.de(pedido).filter(acao=AcaoSolicitacao.DEVOLVIDA).last()
    assert "número de série" in devolucao.observacao
    assert devolucao.quem == cenario["tecnico"]


# ── A linha do tempo inteira ────────────────────────────────────────


def test_a_vida_do_pedido_em_ordem(cenario):
    """De cima para baixo, na ordem em que aconteceu — é assim que se lê."""
    pedido = pedir(cenario)
    apr.decidir(pedido.aprovacao, cenario["gestor"], apr.Decisao.APROVAR)
    pedido.refresh_from_db()
    atd.assumir(pedido, cenario["tecnico"])
    atd.concluir(pedido, cenario["tecnico"])

    assert acoes(pedido) == [
        AcaoSolicitacao.CRIADA,
        AcaoSolicitacao.APROVADA,
        AcaoSolicitacao.ASSUMIDA,
        AcaoSolicitacao.CONCLUIDA,
    ]


def test_o_historico_e_de_um_pedido_so(cenario):
    primeiro = pedir(cenario)
    segundo = pedir(cenario)

    assert hst.de(primeiro).count() == 1
    assert hst.de(segundo).count() == 1
    assert EventoSolicitacao.objects.count() == 2


def test_registrar_sem_pedido_nao_explode():
    """O histórico explica o que aconteceu; derrubar a operação que ele
    descreve inverteria a relação."""
    assert hst.registrar(None, AcaoSolicitacao.CRIADA) is None


# ── A tela ──────────────────────────────────────────────────────────


def test_o_resumo_mostra_a_linha_do_tempo(client, cenario):
    """É o que responde "esse pedido está parado há duas semanas — o que
    aconteceu com ele?"."""
    pedido = pedir(cenario)
    apr.decidir(pedido.aprovacao, cenario["gestor"], apr.Decisao.APROVAR)

    client.force_login(cenario["ana"])
    corpo = client.get(reverse("workspace:minhas_solicitacoes")).content.decode()

    assert "O que aconteceu" in corpo
    assert "Pedido aberto" in corpo
    assert "au-timeline" in corpo


def test_o_acerto_do_adiantamento_tambem_vira_linha(client):
    from workspace.models import SituacaoServico, SolicitacaoServico, TipoCampo
    from workspace.services import reembolso as rmb

    pessoa = f.pessoa("bruno")
    f.lotar(pessoa)

    adiantamento_item = ItemCatalogo.objects.create(
        chave="adiantamento", nome="Adiantamento", grupo=GrupoCatalogo.DINHEIRO,
        dominio="fin.adiantamento", exige_valor=True,
        campos=[{"chave": "motivo", "rotulo": "Motivo", "obrigatorio": True}],
        limite_auto_aprovacao=Decimal("100000"),
    )
    reembolso_item = ItemCatalogo.objects.create(
        chave="prestacao", nome="Prestação de contas", grupo=GrupoCatalogo.DINHEIRO,
        dominio="fin.reembolso", exige_valor=True,
        campos=[
            {"chave": "despesas", "tipo": TipoCampo.DESPESAS, "obrigatorio": True},
            {"chave": "adiantamento", "tipo": TipoCampo.ADIANTAMENTO},
        ],
        limite_auto_aprovacao=Decimal("100000"),
    )
    adiantado = SolicitacaoServico.objects.create(
        item=adiantamento_item, solicitante=pessoa, valor=Decimal("100"),
        situacao=SituacaoServico.APROVADA, dados={"motivo": "Viagem"},
    )

    from django.core.files.uploadedfile import SimpleUploadedFile

    prestacao = svc.solicitar(
        reembolso_item, pessoa,
        linhas=[rmb.Linha(
            valor=Decimal("40"), motivo="Táxi",
            arquivo=SimpleUploadedFile(
                "c.jpg", b"\xff\xd8\xff\xe0" + b"0" * 32, content_type="image/jpeg"
            ),
        )],
        adiantamento=adiantado,
    )
    rmb.confirmar_acerto(
        prestacao, pessoa,
        comprovante=SimpleUploadedFile(
            "d.jpg", b"\xff\xd8\xff\xe0" + b"0" * 32, content_type="image/jpeg"
        ),
    )

    acerto = hst.de(prestacao).get(acao=AcaoSolicitacao.ACERTO)
    assert "60" in acerto.observacao, "a diferença fica registrada"
