"""ATD — "não resolveu": a saída que faltava depois de concluído.

Concluir era ponto final. Só quem atendia podia encerrar o pedido, e quem
pediu não tinha caminho nenhum para discordar: o notebook continuava sem ligar
e a pessoa abria um SEGUNDO pedido.

Três coisas quebravam nessa segunda abertura, e os testes daqui protegem as
três:

1. **O histórico do mesmo problema ficava partido em dois.** Agora é o MESMO
   pedido que volta, com a mesma linha do tempo.
2. **O primeiro pedido entrava nos indicadores como resolvido rápido.**
   `concluido_em` volta a ser nulo, e o pedido SAI da conta do prazo medido
   enquanto estiver reaberto — é o teste que dá nome a esta suíte.
3. **Quem atendeu não ficava sabendo.** O aviso vai para o ATENDENTE, e é o
   único deste módulo que não vai para quem pediu.

E o que a reabertura NÃO faz: refazer a aprovação. O que se contesta é a
entrega, não a autorização.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.models import (
    AcaoSolicitacao,
    GrupoCatalogo,
    ItemCatalogo,
    Notificacao,
    SituacaoServico,
    SolicitacaoServico,
    TipoNotificacao,
)
from workspace.models.catalogo import PRAZO_REABERTURA_DIAS
from workspace.services import atendimento as atd
from workspace.services import catalogo as svc
from workspace.services import historico as hst
from workspace.services.atendimento import AtendimentoError

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    ana, tecnico, outra = (f.pessoa(n) for n in ("ana", "tecnico", "outra"))
    for pessoa in (ana, tecnico, outra):
        f.lotar(pessoa)
    f.atribuir(tecnico, f.papel("ti", ["ti.atender.unidade"], escopo="unidade"))

    chamado = ItemCatalogo.objects.create(
        chave="equipamento-quebrado", nome="Equipamento parado",
        grupo=GrupoCatalogo.EQUIPAMENTO, dominio="ti.chamado",
        prazo_prometido_dias=2, limite_auto_aprovacao=Decimal("0"),
        campos=[{"chave": "o_que", "rotulo": "O que houve", "obrigatorio": True}],
    )
    return {"ana": ana, "tecnico": tecnico, "outra": outra, "chamado": chamado}


def concluido(cenario, quem=None):
    """Um pedido que já foi entregue — é daqui que a reabertura parte."""
    pedido = svc.solicitar(cenario["chamado"], cenario["ana"], {"o_que": "A tela apagou"})
    atd.assumir(pedido, quem or cenario["tecnico"])
    atd.concluir(pedido, quem or cenario["tecnico"])
    return pedido


def envelhecer(pedido, dias):
    """Empurra a conclusão para o passado. `update` porque o teste precisa
    escrever uma data que o fluxo normal nunca escreveria."""
    SolicitacaoServico.objects.filter(pk=pedido.pk).update(
        concluido_em=timezone.now() - timedelta(days=dias)
    )
    pedido.refresh_from_db()
    return pedido


# ── O pedido volta, e é o mesmo pedido ──────────────────────────────


def test_reabrir_devolve_o_pedido_para_quem_atendeu(cenario):
    pedido = concluido(cenario)

    atd.reabrir(pedido, cenario["ana"], "A tela apagou de novo no mesmo dia")

    assert pedido.situacao == SituacaoServico.EM_ATENDIMENTO
    assert pedido.atendente == cenario["tecnico"], "quem disse pronto ouve o não está"


def test_o_pedido_reaparece_na_fila_de_quem_atende(cenario):
    pedido = concluido(cenario)
    assert list(atd.fila_de(cenario["tecnico"])) == [], "concluído sai da fila"

    atd.reabrir(pedido, cenario["ana"], "Voltou a travar")

    assert list(atd.fila_de(cenario["tecnico"])) == [pedido]


def test_sem_atendente_o_pedido_volta_para_a_fila_inteira(cenario):
    """A pessoa saiu da empresa. Melhor a fila toda ver do que ficar preso a um
    nome que não existe mais."""
    pedido = concluido(cenario)
    SolicitacaoServico.objects.filter(pk=pedido.pk).update(atendente=None)
    pedido.refresh_from_db()

    atd.reabrir(pedido, cenario["ana"], "Continua sem funcionar")

    assert pedido.situacao == SituacaoServico.APROVADA


def test_e_o_mesmo_pedido_e_nao_um_novo(cenario):
    """Era o que acontecia antes: o mesmo problema virava dois números."""
    pedido = concluido(cenario)

    atd.reabrir(pedido, cenario["ana"], "Não resolveu")

    assert SolicitacaoServico.objects.count() == 1


# ── O indicador que estava mentindo ─────────────────────────────────


def test_reabrir_tira_o_pedido_da_conta_do_prazo_medido(cenario):
    """O TESTE desta suíte.

    Antes, o pedido fechado sem resolver contava como "resolvido em um dia", e
    a pessoa abria outro — que começava a contar do zero. O catálogo prometia
    um prazo construído em cima de entregas que não entregaram nada.
    """
    item = cenario["chamado"]
    pedidos = [concluido(cenario) for _ in range(svc.MINIMO_PARA_PRAZO_MEDIDO)]

    _, medido = svc.prazo_medido(item)
    assert medido, "com histórico suficiente, o prazo da tela vem da realidade"

    atd.reabrir(pedidos[0], cenario["ana"], "Não resolveu")

    _, medido = svc.prazo_medido(item)
    assert not medido, "o que voltou não é entrega, e sai da conta"


def test_concluido_em_volta_a_ser_nulo(cenario):
    pedido = concluido(cenario)
    assert pedido.concluido_em is not None

    atd.reabrir(pedido, cenario["ana"], "Não resolveu")

    assert pedido.concluido_em is None
    assert pedido.dias_para_concluir is None


def test_a_segunda_conclusao_mede_ate_a_solucao(cenario):
    """O tempo passa a ser do pedido até resolver — não até a primeira
    tentativa."""
    pedido = concluido(cenario)
    primeira = pedido.concluido_em

    atd.reabrir(pedido, cenario["ana"], "Não resolveu")
    atd.concluir(pedido, cenario["tecnico"])

    assert pedido.concluido_em > primeira


def test_o_contador_de_reaberturas_sobe(cenario):
    pedido = concluido(cenario)

    atd.reabrir(pedido, cenario["ana"], "Primeira vez")
    atd.concluir(pedido, cenario["tecnico"])
    atd.reabrir(pedido, cenario["ana"], "Segunda vez")

    assert pedido.reaberturas == 2


def test_a_fila_conta_o_que_voltou(cenario):
    """Fila que só conta o que entra e o que sai parece saudável mesmo quando
    metade do que saiu está voltando."""
    pedido = concluido(cenario)
    atd.reabrir(pedido, cenario["ana"], "Não resolveu")

    assert atd.resumo_da_fila(cenario["tecnico"])["reabertos"] == 1


# ── Quem pode, e sob que condição ───────────────────────────────────


def test_so_quem_pediu_pode_dizer_que_nao_resolveu(cenario):
    """É por serem duas pessoas diferentes que a segunda palavra significa
    alguma coisa."""
    pedido = concluido(cenario)

    with pytest.raises(AtendimentoError, match="Só quem pediu"):
        atd.reabrir(pedido, cenario["tecnico"], "Achei que não ficou bom")


def test_o_motivo_e_obrigatorio(cenario):
    """Sem ele, o pedido volta para a mesma pessoa que já tentou uma vez, sem
    nada de novo para fazer diferente."""
    pedido = concluido(cenario)

    with pytest.raises(AtendimentoError, match="continua sem resolver"):
        atd.reabrir(pedido, cenario["ana"], "   ")


def test_o_que_nao_foi_concluido_nao_se_reabre(cenario):
    """Cancelar é ato de quem pediu — não há entrega para contestar."""
    pedido = concluido(cenario)
    SolicitacaoServico.objects.filter(pk=pedido.pk).update(
        situacao=SituacaoServico.CANCELADA
    )
    pedido.refresh_from_db()

    with pytest.raises(AtendimentoError, match="só o que foi concluído"):
        atd.reabrir(pedido, cenario["ana"], "Não resolveu")


def test_passado_o_prazo_o_caminho_e_outro_pedido(cenario):
    """Reabrir um pedido fechado há meses ressuscita trabalho já morto, e quem
    recebe não tem como reconstruir o que aconteceu."""
    pedido = envelhecer(concluido(cenario), PRAZO_REABERTURA_DIAS + 1)

    with pytest.raises(AtendimentoError, match="Abra um novo pedido"):
        atd.reabrir(pedido, cenario["ana"], "Não resolveu")


def test_dentro_do_prazo_ainda_da(cenario):
    pedido = envelhecer(concluido(cenario), PRAZO_REABERTURA_DIAS - 1)

    atd.reabrir(pedido, cenario["ana"], "Voltou a travar hoje")

    assert pedido.situacao == SituacaoServico.EM_ATENDIMENTO


def test_a_data_limite_aparece_para_quem_pediu(cenario):
    """Sem ela o botão sumiria um dia sem aviso, e a pessoa acharia que o
    sistema quebrou."""
    pedido = concluido(cenario)

    assert pedido.prazo_reabertura is not None
    assert (pedido.prazo_reabertura - pedido.concluido_em).days == PRAZO_REABERTURA_DIAS


def test_pedido_em_aberto_nao_oferece_reabertura(cenario):
    pedido = svc.solicitar(cenario["chamado"], cenario["ana"], {"o_que": "Parou"})

    assert pedido.pode_reabrir is False
    assert pedido.prazo_reabertura is None


# ── O que a reabertura não faz ──────────────────────────────────────


def test_a_aprovacao_nao_e_refeita(cenario):
    """Mandar o gestor aprovar de novo o mesmo notebook que ele já aprovou
    transformaria uma reclamação em burocracia."""
    pedido = concluido(cenario)

    atd.reabrir(pedido, cenario["ana"], "Não resolveu")

    assert pedido.situacao != SituacaoServico.AGUARDANDO_APROVACAO


# ── O aviso, e para quem ele vai ────────────────────────────────────


def test_quem_atendeu_e_avisado(cenario):
    pedido = concluido(cenario)

    atd.reabrir(pedido, cenario["ana"], "A tela apagou de novo")

    aviso = Notificacao.objects.de(cenario["tecnico"]).get(
        tipo=TipoNotificacao.PEDIDO_REABERTO
    )
    assert "A tela apagou de novo" in aviso.corpo, "o motivo viaja junto"
    assert aviso.url == reverse("workspace:fila")


def test_quem_reabriu_nao_e_avisado_do_proprio_ato(cenario):
    pedido = concluido(cenario)

    atd.reabrir(pedido, cenario["ana"], "Não resolveu")

    assert not Notificacao.objects.de(cenario["ana"]).filter(
        tipo=TipoNotificacao.PEDIDO_REABERTO
    ).exists()


# ── O histórico ─────────────────────────────────────────────────────


def test_a_reabertura_entra_na_linha_do_tempo_com_o_motivo(cenario):
    pedido = concluido(cenario)

    atd.reabrir(pedido, cenario["ana"], "A tela apagou de novo no mesmo dia")

    evento = hst.de(pedido).get(acao=AcaoSolicitacao.REABERTA)
    assert evento.quem == cenario["ana"]
    assert "no mesmo dia" in evento.observacao


def test_a_vida_inteira_do_pedido_que_voltou(cenario):
    pedido = concluido(cenario)
    atd.reabrir(pedido, cenario["ana"], "Não resolveu")
    atd.concluir(pedido, cenario["tecnico"])

    assert [e.acao for e in hst.de(pedido)] == [
        AcaoSolicitacao.CRIADA,
        AcaoSolicitacao.AUTO_APROVADA,
        AcaoSolicitacao.ASSUMIDA,
        AcaoSolicitacao.CONCLUIDA,
        AcaoSolicitacao.REABERTA,
        AcaoSolicitacao.CONCLUIDA,
    ]


def test_o_motivo_da_ultima_reabertura_fica_a_mao_da_fila(cenario):
    """Marcar a linha só com "reaberto" faria a pessoa tentar de novo
    exatamente a mesma coisa — que foi o que já não resolveu."""
    pedido = concluido(cenario)
    atd.reabrir(pedido, cenario["ana"], "Primeiro motivo")
    atd.concluir(pedido, cenario["tecnico"])
    atd.reabrir(pedido, cenario["ana"], "Segundo motivo")

    assert pedido.motivo_reabertura == "Segundo motivo"


def test_pedido_que_nunca_voltou_nao_consulta_eventos(cenario, django_assert_num_queries):
    """O atalho que faz a fila não pagar por uma coluna que quase ninguém usa:
    `reaberturas` é zero e a propriedade sai antes de tocar no banco."""
    pedido = concluido(cenario)

    with django_assert_num_queries(0):
        assert pedido.motivo_reabertura == ""


# ── A tela ──────────────────────────────────────────────────────────


def test_a_tela_oferece_a_saida_a_quem_pediu(client, cenario):
    concluido(cenario)

    client.force_login(cenario["ana"])
    corpo = client.get(reverse("workspace:minhas_solicitacoes")).content.decode()

    assert "Não resolveu?" in corpo
    assert "au-reabrir" in corpo


def test_reabrir_pela_tela(client, cenario):
    pedido = concluido(cenario)

    client.force_login(cenario["ana"])
    resposta = client.post(
        reverse("workspace:reabrir_solicitacao", args=[pedido.pk]),
        {"motivo": "A tela apagou de novo"},
    )
    pedido.refresh_from_db()

    assert resposta.status_code == 302
    assert pedido.situacao == SituacaoServico.EM_ATENDIMENTO


def test_a_tela_nao_reabre_pedido_de_outra_pessoa(client, cenario):
    """`svc.minhas()` é a autorização inteira: quem não pediu não enxerga."""
    pedido = concluido(cenario)

    client.force_login(cenario["outra"])
    resposta = client.post(
        reverse("workspace:reabrir_solicitacao", args=[pedido.pk]),
        {"motivo": "Quero mexer no pedido dos outros"},
    )
    pedido.refresh_from_db()

    assert resposta.status_code == 404
    assert pedido.situacao == SituacaoServico.CONCLUIDA


def test_sem_motivo_a_tela_explica_em_vez_de_quebrar(client, cenario):
    pedido = concluido(cenario)

    client.force_login(cenario["ana"])
    resposta = client.post(
        reverse("workspace:reabrir_solicitacao", args=[pedido.pk]),
        {"motivo": ""},
        follow=True,
    )
    pedido.refresh_from_db()

    assert pedido.situacao == SituacaoServico.CONCLUIDA
    assert "continua sem resolver" in resposta.content.decode()


def test_a_fila_mostra_o_que_voltou_e_por_que(client, cenario):
    pedido = concluido(cenario)
    atd.reabrir(pedido, cenario["ana"], "A tela apagou de novo")

    client.force_login(cenario["tecnico"])
    corpo = client.get(reverse("workspace:fila")).content.decode()

    assert "voltou sem resolver" in corpo
    assert "A tela apagou de novo" in corpo
