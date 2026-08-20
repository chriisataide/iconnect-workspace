"""§45 — a conversa dentro do pedido, e a auditoria da tabbar (§44).

## O que faltava no workflow

A auditoria do §45 encontrou nove dos dez itens já implementados: etapas,
responsáveis, aprovação, execução, conclusão, SLA, histórico, anexos e
notificações. Faltava **comentários**, e a consequência é concreta.

Um atendente precisa perguntar "qual o número de série?". Antes disto, duas
saídas, as duas ruins:

* **Devolver** — bounce do pedido inteiro. Ele sai da fila, perde a posição e
  volta como se estivesse errado. Devolver quer dizer "corrija e reenvie", e
  não é isso que a pergunta quer dizer.
* **Mensagem por fora** — funciona e some. Três meses depois ninguém sabe por
  que aquele pedido demorou onze dias: a explicação está no WhatsApp de duas
  pessoas.

## Interno e visível

Nem tudo que a área escreve é para quem pediu. Com um tipo só, o produto obriga
a escolher entre nota interna vazando ou pergunta não chegando.

**O padrão é VISÍVEL**, e é deliberado: nota interna que vaza é constrangimento;
pergunta que não chega é o pedido parado. O segundo acontece toda semana, o
primeiro quase nunca — o padrão protege contra o erro frequente.

## §44 — a tabbar

Todo estado tinha aba, mas `APROVADA` e `EM_ATENDIMENTO` só apareciam dentro de
"Em aberto". É o que produziu a queixa do §43: o pedido diz "Aprovada", não está
em "Concluídas", continua em "Em aberto", e não há onde vê-lo isolado — a
leitura óbvia é a de que a máquina de estados está errada. Ela não estava; a
tela é que não dizia a FASE.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.models import Notificacao, TipoNotificacao
from workspace.models.catalogo import (
    GrupoCatalogo,
    ItemCatalogo,
    SituacaoServico,
)
from workspace.models.comentario import ComentarioSolicitacao
from workspace.services import atendimento as atd
from workspace.services import catalogo as svc
from workspace.services import comentario as cmt
from workspace.services import listagem as lst
from workspace.services.comentario import ComentarioError

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    ana, tecnico, outro = (f.pessoa(n) for n in ("ana", "tecnico", "outro"))
    for pessoa in (ana, tecnico, outro):
        f.lotar(pessoa)
    f.atribuir(tecnico, f.papel("ti", ["ti.atender.global"], escopo="global"))

    item = ItemCatalogo.objects.create(
        chave="acesso", nome="Acesso a um sistema", grupo=GrupoCatalogo.EQUIPAMENTO,
        dominio="ti.acesso", prazo_prometido_dias=2,
        limite_auto_aprovacao=Decimal("0"),
        campos=[{"chave": "o_que", "rotulo": "O quê", "obrigatorio": True}],
    )
    pedido = svc.solicitar(item, ana, {"o_que": "VPN"})
    return {"ana": ana, "tecnico": tecnico, "outro": outro, "pedido": pedido}


# ── Quem pode falar ─────────────────────────────────────────────────


def test_quem_pediu_comenta(cenario):
    comentario = cmt.comentar(cenario["pedido"], cenario["ana"], "Já preciso disso.")

    assert comentario.pk is not None
    assert not comentario.interno


def test_quem_atende_comenta(cenario):
    comentario = cmt.comentar(
        cenario["pedido"], cenario["tecnico"], "Qual o número de série?"
    )

    assert comentario.autor == cenario["tecnico"]


def test_quem_nao_pediu_nem_atende_nao_comenta(cenario):
    """Comentário é parte do pedido, e o pedido é de duas partes."""
    with pytest.raises(ComentarioError, match="não é seu nem da sua fila"):
        cmt.comentar(cenario["pedido"], cenario["outro"], "opinião")


def test_texto_vazio_e_recusado(cenario):
    with pytest.raises(ComentarioError, match="Escreva alguma coisa"):
        cmt.comentar(cenario["pedido"], cenario["ana"], "   ")


def test_texto_gigante_e_recusado(cenario):
    """Um comentário não é um documento. O campo longo convida a colar log
    inteiro dentro da conversa."""
    with pytest.raises(ComentarioError, match="anexo"):
        cmt.comentar(cenario["pedido"], cenario["ana"], "x" * (cmt.MAXIMO + 1))


# ── Interno e visível ───────────────────────────────────────────────


def test_o_padrao_e_visivel(cenario):
    """Nota interna que vaza é constrangimento; pergunta que não chega é o
    pedido parado. O segundo acontece toda semana."""
    comentario = cmt.comentar(cenario["pedido"], cenario["tecnico"], "Pergunta")

    assert not comentario.interno


def test_quem_atende_pode_marcar_interno(cenario):
    comentario = cmt.comentar(
        cenario["pedido"], cenario["tecnico"], "Conferir o contrato", interno=True
    )

    assert comentario.interno


def test_quem_pediu_nao_consegue_marcar_interno(cenario):
    """Marcado por quem pediu, `interno` esconderia a fala da própria pessoa
    dela mesma."""
    comentario = cmt.comentar(
        cenario["pedido"], cenario["ana"], "Minha nota", interno=True
    )

    assert not comentario.interno


def test_quem_pediu_nao_ve_o_interno(cenario):
    cmt.comentar(cenario["pedido"], cenario["tecnico"], "Visível")
    cmt.comentar(cenario["pedido"], cenario["tecnico"], "Interno", interno=True)

    textos = [c.texto for c in cmt.de(cenario["pedido"], cenario["ana"])]

    assert textos == ["Visível"]


def test_quem_atende_ve_tudo(cenario):
    cmt.comentar(cenario["pedido"], cenario["tecnico"], "Visível")
    cmt.comentar(cenario["pedido"], cenario["tecnico"], "Interno", interno=True)

    assert cmt.de(cenario["pedido"], cenario["tecnico"]).count() == 2


# ── O aviso vai para o OUTRO lado ───────────────────────────────────


def test_quem_atende_comenta_e_quem_pediu_e_avisado(cenario):
    """É o caso que conserta o §45: a pergunta chega sem o pedido precisar ser
    devolvido."""
    cmt.comentar(cenario["pedido"], cenario["tecnico"], "Qual o número de série?")

    aviso = Notificacao.objects.get(
        destinatario=cenario["ana"], tipo=TipoNotificacao.COMENTARIO_NO_PEDIDO
    )
    assert "Qual o número de série?" in aviso.corpo


def test_o_autor_nao_recebe_o_proprio_comentario(cenario):
    cmt.comentar(cenario["pedido"], cenario["tecnico"], "Pergunta")

    assert not Notificacao.objects.filter(
        destinatario=cenario["tecnico"], tipo=TipoNotificacao.COMENTARIO_NO_PEDIDO
    ).exists()


def test_quem_pediu_comenta_e_quem_assumiu_e_avisado(cenario):
    atd.assumir(cenario["pedido"], cenario["tecnico"])
    Notificacao.objects.all().delete()

    cmt.comentar(cenario["pedido"], cenario["ana"], "É o número 4471.")

    assert Notificacao.objects.filter(
        destinatario=cenario["tecnico"], tipo=TipoNotificacao.COMENTARIO_NO_PEDIDO
    ).exists()


def test_sem_atendente_o_comentario_de_quem_pediu_nao_avisa_ninguem(cenario):
    """O pedido está na fila e o comentário será lido quando alguém pegar.
    Avisar a área inteira por um comentário seria ruído por definição."""
    cmt.comentar(cenario["pedido"], cenario["ana"], "Urgente")

    assert not Notificacao.objects.filter(
        tipo=TipoNotificacao.COMENTARIO_NO_PEDIDO
    ).exists()


def test_o_interno_nao_avisa_quem_pediu(cenario):
    atd.assumir(cenario["pedido"], cenario["tecnico"])
    Notificacao.objects.all().delete()

    cmt.comentar(cenario["pedido"], cenario["tecnico"], "Nota", interno=True)

    assert not Notificacao.objects.filter(destinatario=cenario["ana"]).exists()


def test_o_interno_avisa_quem_assumiu(cenario):
    """Nota entre atendentes chega a quem está com o pedido — e a mais ninguém:
    a fila inteira receber nota interna de um pedido que não é dela transforma o
    sino em ruído."""
    outro_tecnico = f.pessoa("tecnico2")
    f.lotar(outro_tecnico)
    f.atribuir(outro_tecnico, f.papel("ti2", ["ti.atender.global"], escopo="global"))
    atd.assumir(cenario["pedido"], cenario["tecnico"])
    Notificacao.objects.all().delete()

    cmt.comentar(cenario["pedido"], outro_tecnico, "Olha isto", interno=True)

    assert Notificacao.objects.filter(destinatario=cenario["tecnico"]).exists()
    assert not Notificacao.objects.filter(destinatario=outro_tecnico).exists()


# ── O comentário não substitui devolver ─────────────────────────────


def test_comentar_nao_tira_o_pedido_da_fila(cenario):
    """O ponto do §45. Devolver tiraria."""
    cmt.comentar(cenario["pedido"], cenario["tecnico"], "Qual o número de série?")

    cenario["pedido"].refresh_from_db()
    assert cenario["pedido"].situacao == SituacaoServico.APROVADA
    assert cenario["pedido"] in atd.fila_de(cenario["tecnico"])


def test_comentario_nao_e_editavel_nem_apagavel_pelo_produto(cenario):
    """Histórico que muda depois não serve para explicar o que aconteceu.
    Correção é um comentário novo."""
    assert not hasattr(cmt, "editar")
    assert not hasattr(cmt, "apagar")


# ── As telas ────────────────────────────────────────────────────────


def test_a_fila_mostra_a_conversa(client, cenario):
    cmt.comentar(cenario["pedido"], cenario["tecnico"], "Qual o número de série?")
    client.force_login(cenario["tecnico"])

    corpo = client.get(reverse("workspace:fila")).content.decode()

    assert "Qual o número de série?" in corpo
    assert "Pergunte sem devolver" in corpo


def test_comentar_pela_fila(client, cenario):
    client.force_login(cenario["tecnico"])

    client.post(
        reverse("workspace:atender", args=[cenario["pedido"].pk]),
        {"acao": "comentar", "texto": "Qual o número de série?"},
    )

    assert ComentarioSolicitacao.objects.count() == 1


def test_comentar_pedido_de_outra_fila_vira_mensagem_e_nao_erro(client, cenario):
    """Erro de permissão numa ação de tela é MENSAGEM, não 500.

    Quem atende OUTRO domínio: ele passa pela porta da tela de atendimento
    (atende alguma fila) e é barrado no pedido específico — que é onde a
    checagem tem de estar.
    """
    do_rh = f.pessoa("rh")
    f.lotar(do_rh)
    f.atribuir(do_rh, f.papel("rh", ["rh.atender.global"], escopo="global"))
    # Um item de R.H. precisa EXISTIR para que ele atenda alguma fila: os
    # prefixos que uma pessoa atende saem dos domínios que o catálogo tem. Sem
    # isto ele leva 403 na porta da tela, e o teste mediria a porta em vez da
    # checagem do pedido.
    ItemCatalogo.objects.create(
        chave="vaga", nome="Vaga", grupo=GrupoCatalogo.TRABALHO,
        dominio="rh.vaga", prazo_prometido_dias=2,
        limite_auto_aprovacao=Decimal("0"), campos=[],
    )
    client.force_login(do_rh)

    resposta = client.post(
        reverse("workspace:atender", args=[cenario["pedido"].pk]),
        {"acao": "comentar", "texto": "x"},
        follow=True,
    )

    assert resposta.status_code == 200
    assert "não é seu nem da sua fila" in resposta.content.decode()
    assert not ComentarioSolicitacao.objects.exists()


def test_minhas_solicitacoes_mostra_a_conversa(client, cenario):
    cmt.comentar(cenario["pedido"], cenario["tecnico"], "Qual o número de série?")
    client.force_login(cenario["ana"])

    corpo = client.get(reverse("workspace:minhas_solicitacoes")).content.decode()

    assert "Qual o número de série?" in corpo
    assert "Conversa" in corpo


def test_minhas_solicitacoes_esconde_o_interno(client, cenario):
    cmt.comentar(cenario["pedido"], cenario["tecnico"], "Nota da área", interno=True)
    client.force_login(cenario["ana"])

    corpo = client.get(reverse("workspace:minhas_solicitacoes")).content.decode()

    assert "Nota da área" not in corpo


def test_comentar_pela_tela_de_quem_pediu(client, cenario):
    client.force_login(cenario["ana"])

    client.post(
        reverse("workspace:comentar_solicitacao", args=[cenario["pedido"].pk]),
        {"texto": "É o número 4471."},
    )

    assert ComentarioSolicitacao.objects.get().texto == "É o número 4471."


def test_comentar_pedido_de_outro_e_recusado(client, cenario):
    client.force_login(cenario["outro"])

    client.post(
        reverse("workspace:comentar_solicitacao", args=[cenario["pedido"].pk]),
        {"texto": "opinião"},
    )

    assert not ComentarioSolicitacao.objects.exists()


def test_comentar_exige_sessao(client, cenario):
    resposta = client.post(
        reverse("workspace:comentar_solicitacao", args=[cenario["pedido"].pk]),
        {"texto": "x"},
    )

    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/entrar/")


def test_a_fila_nao_faz_uma_consulta_por_comentario(client, cenario):
    """`comentarios__autor` no prefetch: sem ele seriam duas consultas por
    linha — uma para os comentários e outra para o nome de quem escreveu."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    def custo(quantos):
        ComentarioSolicitacao.objects.all().delete()
        for i in range(quantos):
            cmt.comentar(cenario["pedido"], cenario["tecnico"], f"nota {i}")
        client.force_login(cenario["tecnico"])
        with CaptureQueriesContext(connection) as ctx:
            assert client.get(reverse("workspace:fila")).status_code == 200
        return len(ctx.captured_queries)

    assert custo(6) <= custo(1) + 1


# ── §44 — a tabbar ──────────────────────────────────────────────────


def test_toda_situacao_tem_uma_aba():
    """A auditoria que o §44 pede, em código: nenhum estado fica sem lugar."""
    cobertos = set()
    for _, _, situacoes in lst.FILTROS_MINHAS:
        if situacoes:
            cobertos |= set(situacoes)

    assert cobertos == set(SituacaoServico)


def test_aprovada_e_em_andamento_tem_aba_propria():
    """Os dois existiam e só apareciam dentro de "Em aberto" — que é o que
    produziu a queixa do §43."""
    chaves = {chave for chave, _, _ in lst.FILTROS_MINHAS}

    assert "aprovada" in chaves
    assert "em_atendimento" in chaves


def test_a_aba_filtra_pelo_estado_real(cenario):
    """§44: "não utilizar apenas status visual". A aba consulta o banco."""
    from workspace.models.catalogo import SolicitacaoServico

    atd.assumir(cenario["pedido"], cenario["tecnico"])

    consulta = SolicitacaoServico.objects.de(cenario["ana"])
    assert list(lst.filtrar_minhas(consulta, "em_atendimento")) == [cenario["pedido"]]
    assert list(lst.filtrar_minhas(consulta, "aprovada")) == []


def test_a_fase_diz_o_que_aprovada_significa(cenario):
    """"Aprovada" é tecnicamente certo e produziu a queixa. A fase diz que é
    meio do caminho — e desde a rodada de testes de agosto diz TAMBÉM de quem
    é o meio do caminho.

    "aguardando a área" mandou quem pediu um adiantamento procurar no
    Financeiro sem saber se era ali. O nome sai do papel que declara
    `<raiz>.atender`, que é a mesma fonte do roteamento da fila: a frase não
    pode discordar de para onde o pedido de fato foi.
    """
    assert cenario["pedido"].fase == "Aprovada · aguardando Ti"


def test_a_fase_denuncia_o_dominio_que_ninguem_atende(cenario):
    """Sem papel de atendimento, o pedido é aprovado e cai numa fila que
    ninguém pode abrir. Dizer "aguardando a área" ali é apontar para o vazio."""
    from identidade.models import Papel

    from workspace.services.atendimento import esquecer_areas

    Papel.objects.filter(chave="ti").update(ativo=False)
    esquecer_areas()

    assert cenario["pedido"].fase == "Aprovada · sem área responsável"


def test_a_fase_de_em_andamento_diz_quem_esta_com_ele(cenario):
    atd.assumir(cenario["pedido"], cenario["tecnico"])

    assert cenario["pedido"].fase.startswith("Em andamento · ")


def test_a_fase_de_devolvida_diz_o_que_fazer(cenario):
    atd.devolver(cenario["pedido"], cenario["tecnico"], "Faltou o motivo.")

    assert cenario["pedido"].fase == "Devolvida · esperando você corrigir"


def test_a_fase_dos_terminais_e_o_proprio_nome(cenario):
    atd.concluir(cenario["pedido"], cenario["tecnico"])

    assert cenario["pedido"].fase == "Concluída"


def test_a_tela_mostra_a_fase_e_nao_o_estado_cru(client, cenario):
    client.force_login(cenario["ana"])

    corpo = client.get(reverse("workspace:minhas_solicitacoes")).content.decode()

    assert "Aprovada · aguardando Ti" in corpo
