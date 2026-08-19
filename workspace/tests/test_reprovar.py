"""APR — o "não" definitivo, que o produto não sabia dizer.

## O buraco

As decisões eram três: aprovar, devolver, cancelar. Faltava reprovar, e a falta
não aparecia como erro — aparecia como um pedido que não morre.

Devolver e reprovar pareciam a mesma coisa e não são. **Devolver diz "corrija e
reenvie"**: o pedido continua vivo, esperando ação de quem pediu. **Reprovar diz
"não vai acontecer"**. Enquanto só existia o primeiro, o gestor que queria negar
devolvia, quem pediu corrigia o que não era o problema, e o pedido voltava — até
alguém desistir por cansaço. Do lado dos indicadores, esse pedido ficava para
sempre em "aberto".

Cancelar não resolvia: cancelar é do SOLICITANTE, é ele desistindo. Reprovar é
do aprovador, tem autor e tem motivo.

## O que estes testes guardam

1. **Reprovar exige motivo.** Um "não" sem razão faz a pessoa tentar a sorte com
   outro aprovador, num segundo formulário.
2. **A cadeia inteira para.** As etapas seguintes viram `PULADA` — um "não" que
   não desce a cadeia deixaria o pedido na bandeja de quem viria depois.
3. **É terminal.** Reprovada não é "em aberto", não entra em fila nenhuma, e
   ninguém da área que executaria fica sabendo — não há o que executar.
4. **Quem pediu descobre POR QUÊ**, no corpo do aviso e não só na tela.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from identidade.models import Lotacao
from identidade.tests import fabricas as f
from workspace.models import (
    GrupoCatalogo,
    ItemCatalogo,
    Notificacao,
    RegraAprovacao,
    SituacaoServico,
    TipoAprovador,
    TipoNotificacao,
)
from workspace.models.aprovacao import SituacaoEtapa, SituacaoSolicitacao
from workspace.services import aprovacao as apr
from workspace.services import atendimento as atd
from workspace.services import catalogo as svc
from workspace.services import historico as hst
from workspace.services import listagem as lst

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    ana, gestor, diretor, tecnico = (
        f.pessoa(n) for n in ("ana", "gestor", "diretor", "tecnico")
    )
    f.lotar(diretor)
    f.lotar(gestor, gestor=diretor)
    f.lotar(ana, gestor=gestor)
    f.lotar(tecnico)
    f.atribuir(tecnico, f.papel("ti", ["ti.atender.global"], escopo="global"))

    RegraAprovacao.objects.create(dominio="*", tipo=TipoAprovador.GESTOR_DIRETO, ordem=10)
    item = ItemCatalogo.objects.create(
        chave="acesso", nome="Acesso a um sistema", grupo=GrupoCatalogo.EQUIPAMENTO,
        dominio="ti.acesso", prazo_prometido_dias=2, limite_auto_aprovacao=None,
        campos=[{"chave": "o_que", "rotulo": "O quê", "obrigatorio": True}],
    )
    pedido = svc.solicitar(item, ana, {"o_que": "VPN"})
    return {
        "ana": ana, "gestor": gestor, "diretor": diretor, "tecnico": tecnico,
        "item": item, "pedido": pedido,
    }


def reprovar(cenario, motivo="Fora do orçamento deste ano."):
    return apr.decidir(
        cenario["pedido"].aprovacao, cenario["gestor"], apr.Decisao.REJEITAR, motivo
    )


# ── O motivo é obrigatório ──────────────────────────────────────────


def test_reprovar_sem_motivo_e_recusado(cenario):
    with pytest.raises(apr.AprovacaoError, match="justificativa"):
        reprovar(cenario, "")


def test_reprovar_so_com_espacos_tambem_e_recusado(cenario):
    with pytest.raises(apr.AprovacaoError, match="justificativa"):
        reprovar(cenario, "    ")


# ── O desfecho ──────────────────────────────────────────────────────


def test_reprovar_encerra_a_aprovacao_e_o_pedido(cenario):
    aprovacao = reprovar(cenario)

    assert aprovacao.situacao == SituacaoSolicitacao.REJEITADA
    cenario["pedido"].refresh_from_db()
    assert cenario["pedido"].situacao == SituacaoServico.REJEITADA


def test_a_etapa_guarda_quem_disse_nao_e_por_que(cenario):
    """Reprovar tem autor. É o que separa isto de cancelar."""
    aprovacao = reprovar(cenario, "Fora do orçamento.")
    etapa = aprovacao.etapas.order_by("ordem").first()

    assert etapa.situacao == SituacaoEtapa.REJEITADA
    assert etapa.decidido_por == cenario["gestor"]
    assert etapa.justificativa == "Fora do orçamento."


def test_a_cadeia_seguinte_e_pulada(cenario):
    """Um "não" que não desce a cadeia deixaria o pedido esperando na bandeja
    de quem viria depois — e ele apareceria lá para sempre."""
    RegraAprovacao.objects.create(
        dominio="*", tipo=TipoAprovador.GESTOR_DIRETO, ordem=20
    )
    Lotacao.objects.filter(user=cenario["gestor"]).update(gestor=cenario["diretor"])
    pedido = svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "Outro"})
    assert pedido.aprovacao.etapas.count() >= 2

    apr.decidir(pedido.aprovacao, cenario["gestor"], apr.Decisao.REJEITAR, "Não.")

    assert not pedido.aprovacao.etapas.filter(situacao=SituacaoEtapa.PENDENTE).exists()
    assert not apr.pendentes_para(cenario["diretor"]).filter(pk=pedido.aprovacao.pk)


def test_reprovado_nao_vira_trabalho_de_ninguem(cenario):
    """Não há o que executar. A área que atenderia não recebe nem o pedido nem
    o aviso — foi exatamente o inverso disto que quebrou na aprovação."""
    reprovar(cenario)

    assert not atd.fila_de(cenario["tecnico"]).exists()
    assert not Notificacao.objects.filter(
        destinatario=cenario["tecnico"], tipo=TipoNotificacao.PEDIDO_NA_FILA
    ).exists()


def test_reprovado_nao_pode_ser_decidido_de_novo(cenario):
    reprovar(cenario)

    with pytest.raises(apr.AprovacaoError, match="já está"):
        apr.decidir(
            cenario["pedido"].aprovacao, cenario["gestor"], apr.Decisao.APROVAR
        )


# ── Quem pediu descobre, e descobre por quê ─────────────────────────


def test_quem_pediu_e_avisado_com_o_motivo(cenario):
    reprovar(cenario, "Fora do orçamento deste ano.")

    aviso = Notificacao.objects.filter(
        destinatario=cenario["ana"], tipo=TipoNotificacao.PEDIDO_REJEITADO
    ).get()
    assert "reprovado" in aviso.titulo
    assert aviso.corpo == "Fora do orçamento deste ano."


def test_o_motivo_fica_no_pedido_e_na_linha_do_tempo(cenario):
    reprovar(cenario, "Fora do orçamento deste ano.")

    pedido = cenario["pedido"]
    pedido.refresh_from_db()
    assert pedido.motivo_devolucao == "Fora do orçamento deste ano."

    evento = pedido.eventos.filter(acao=hst.Acao.REJEITADA).get()
    assert evento.quem == cenario["gestor"]
    assert evento.observacao == "Fora do orçamento deste ano."


# ── Terminal: sai de "em aberto" ────────────────────────────────────


def test_reprovado_sai_de_em_aberto(cenario):
    """O sintoma que o §43 do pedido descreve: reprovar sem estado terminal
    deixaria o pedido contado como aberto para sempre."""
    from workspace.models import SolicitacaoServico

    assert SolicitacaoServico.objects.abertas().filter(pk=cenario["pedido"].pk).exists()

    reprovar(cenario)

    assert not SolicitacaoServico.objects.abertas().filter(
        pk=cenario["pedido"].pk
    ).exists()
    cenario["pedido"].refresh_from_db()
    assert cenario["pedido"].situacao not in lst.ABERTAS


def test_o_filtro_de_reprovadas_existe_e_so_pega_reprovadas(cenario):
    from workspace.models import SolicitacaoServico

    outro = svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "Outro"})
    reprovar(cenario)

    encontradas = lst.filtrar_minhas(
        SolicitacaoServico.objects.de(cenario["ana"]), "rejeitada"
    )
    assert list(encontradas) == [cenario["pedido"]]
    assert outro not in encontradas


def test_abertas_deriva_dos_terminais_e_nao_de_lista_escrita_a_mao(cenario):
    """A lista literal vivia em quatro arquivos. Quando `REJEITADA` nasceu, só
    um deles soube — e este teste é o que impede a quinta cópia.

    A partição virou de três com o §43: um pedido está na esteira, já acabou, ou
    ainda não foi enviado. Rascunho não é aberto nem terminal — é antes do
    começo —, e o teste continua exigindo que os três conjuntos cubram todos os
    estados sem se sobrepor. Foi ele que pegou o `RASCUNHO` caindo dentro de
    "em aberto" por herança da fórmula antiga.
    """
    from workspace.models.catalogo import (
        SITUACOES_NAO_ENVIADAS,
        SITUACOES_TERMINAIS,
    )

    abertas = set(lst.ABERTAS)
    terminais = set(SITUACOES_TERMINAIS)
    nao_enviadas = set(SITUACOES_NAO_ENVIADAS)

    assert abertas & terminais == set()
    assert abertas & nao_enviadas == set()
    assert terminais & nao_enviadas == set()
    assert abertas | terminais | nao_enviadas == set(SituacaoServico)


# ── Continua sendo diferente de devolver ────────────────────────────


def test_devolver_continua_deixando_o_pedido_vivo(cenario):
    """A distinção inteira em um teste: devolvido espera correção e continua
    aberto; reprovado não espera nada."""
    apr.decidir(
        cenario["pedido"].aprovacao, cenario["gestor"], apr.Decisao.DEVOLVER, "Faltou a NF."
    )

    cenario["pedido"].refresh_from_db()
    assert cenario["pedido"].situacao == SituacaoServico.DEVOLVIDA
    assert cenario["pedido"].situacao in lst.ABERTAS


def test_ninguem_reprova_o_proprio_pedido(cenario):
    """Vale a mesma regra de aprovar. Sem isto, quem tem papel de aprovador
    poderia encerrar o próprio pedido para tirá-lo da fila de alguém."""
    with pytest.raises(apr.AprovacaoError, match="próprio pedido"):
        apr.decidir(
            cenario["pedido"].aprovacao, cenario["ana"], apr.Decisao.REJEITAR, "Não."
        )


# ── A bandeja mostra o pedido inteiro, sem N+1 ──────────────────────


def test_a_bandeja_mostra_o_que_foi_pedido_e_a_linha_do_tempo(client, cenario):
    """§39: decidir sem ver o pedido é carimbar.

    A bandeja mostrava a barra de orçamento e os comprovantes, e não mostrava o
    formulário nem o histórico. Para saber o que a pessoa tinha pedido, o
    aprovador teria de abrir "Minhas solicitações" de outro alguém — que ninguém
    pode — ou perguntar por mensagem.
    """
    from django.urls import reverse

    client.force_login(cenario["gestor"])
    corpo = client.get(reverse("workspace:aprovacoes")).content.decode()

    assert "Ver o pedido" in corpo
    assert f'id="resumo-{cenario["pedido"].pk}"' in corpo, "o modal de detalhe não veio"
    assert "VPN" in corpo, "o que foi preenchido no formulário não aparece"
    assert "O que aconteceu" in corpo, "a linha do tempo não aparece"


def _consultas_da_bandeja(client, cenario, quantos):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext
    from django.urls import reverse

    for i in range(quantos - 1):
        svc.solicitar(cenario["item"], cenario["ana"], {"o_que": f"Sistema {i}"})

    client.force_login(cenario["gestor"])
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(reverse("workspace:aprovacoes")).status_code == 200
    return len(ctx.captured_queries)


def test_a_bandeja_custa_o_mesmo_com_um_e_com_cinco_pedidos(client, cenario):
    """O dossiê completo é exatamente onde um N+1 nasce: formulário, anexos,
    despesas, etapas e eventos, uma vez por linha da bandeja.

    O teste compara a INCLINAÇÃO e não um teto, porque teto folgado esconde
    justamente o defeito que interessa: com um número absoluto generoso, cinco
    consultas por linha passam e só doem em produção. Medido antes do conserto:
    30 consultas com um pedido e 58 com cinco — e o grosso era `etapa_atual`,
    que refaz a consulta a cada chamada e é chamada seis vezes por linha.
    """
    um = _consultas_da_bandeja(client, cenario, 1)
    cinco = _consultas_da_bandeja(client, cenario, 5)

    assert cinco == um, f"a bandeja cresce com o número de linhas: {um} → {cinco}"
    assert um < 30, f"a bandeja ficou cara mesmo com uma linha: {um}"
