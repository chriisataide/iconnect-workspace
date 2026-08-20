"""O pedido que volta, é corrigido e segue de novo — o fluxo de 20/08/2026.

## O beco que existia

Devolver era o fim da linha. O pedido voltava com o motivo escrito, ficava "em
aberto" para sempre, e a pessoa tinha exatamente uma saída: abrir OUTRO pedido.

O custo disso não é o clique. É que o mesmo assunto vira dois números — o
primeiro fica aberto na conta de quem atende, os anexos e a conversa ficam
presos nele, e quem pega o segundo começa do zero sem saber que já houve uma
tentativa. É o mesmo defeito que `reabrir()` conserta do outro lado da esteira.

## O fluxo inteiro

    colaborador abre no módulo    →  fila do GESTOR dele
    gestor aprova                 →  fila da ÁREA do módulo onde foi aberto
    área conclui                  →  fim
    área devolve com motivo       →  volta para quem pediu, EDITÁVEL
    pessoa corrige e reenvia      →  recomeça do gestor

O último passo é este arquivo. Os anteriores estão em `test_cadeia_aprovacao`,
`test_atendimento` e `test_comentarios`.

## As duas decisões que mais custam se forem invertidas

**A cadeia é refeita.** O gestor aprovou um texto; a pessoa mudou o texto.
Reaproveitar a aprovação seria fazer alguém assinar o que não viu.

**O relógio não volta.** `criado_em` fica onde estava. Se o reenvio zerasse a
contagem, devolver viraria o jeito de limpar o próprio atraso — e o indicador
de prazo passaria a medir a última tentativa em vez da espera real.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.models import Lotacao
from identidade.tests import fabricas as f
from workspace.models import (
    GrupoCatalogo,
    ItemCatalogo,
    RegraAprovacao,
    SituacaoServico,
    SolicitacaoServico,
    TipoAprovador,
)
from workspace.services import aprovacao as apr
from workspace.services import atendimento as atd
from workspace.services import catalogo as svc
from workspace.services.catalogo import SolicitacaoError

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    """Quem pede, quem aprova, quem atende — e um item que passa pelo gestor."""
    ana, gestor, area, estranho = (
        f.pessoa(n) for n in ("ana", "gestor", "area", "estranho")
    )
    f.lotar(gestor)
    f.lotar(ana, gestor=gestor)
    f.lotar(area)
    f.lotar(estranho)
    f.atribuir(area, f.papel("financeiro", ["fin.atender.global"], escopo="global"))

    item = ItemCatalogo.objects.create(
        chave="adiantamento", nome="Adiantamento", grupo=GrupoCatalogo.DINHEIRO,
        dominio="fin.adiantamento", prazo_prometido_dias=3,
        # `None` = nunca auto-aprova. Com um limite numérico e sem valor
        # informado, `pode_auto_aprovar` devolve True e o pedido pula a cadeia
        # inteira — que é justamente o que este arquivo precisa exercitar.
        limite_auto_aprovacao=None,
        campos=[{"chave": "motivo", "rotulo": "Para quê", "obrigatorio": True}],
    )
    RegraAprovacao.objects.create(
        dominio="fin.", tipo=TipoAprovador.GESTOR_DIRETO, ordem=10,
        valor_minimo=Decimal("0"),
    )
    return {
        "ana": ana, "gestor": gestor, "area": area, "estranho": estranho, "item": item,
    }


def devolvido(cenario, motivo="Falta o comprovante."):
    """Um pedido que percorreu o fluxo até ser devolvido pela área."""
    pedido = svc.solicitar(cenario["item"], cenario["ana"], {"motivo": "viagem"})
    apr.decidir(pedido.aprovacao, cenario["gestor"], apr.Decisao.APROVAR)
    pedido.refresh_from_db()
    atd.devolver(pedido, cenario["area"], motivo)
    pedido.refresh_from_db()
    return pedido


# ── O caminho até a devolução ───────────────────────────────────────


def test_depois_do_gestor_o_pedido_vai_para_a_fila_da_area(cenario):
    """E NÃO para uma segunda bandeja de aprovação da mesma área.

    Era o que acontecia até 20/08: a área aprovava e depois atendia, duas telas
    para uma decisão que ela toma uma vez só.
    """
    pedido = svc.solicitar(cenario["item"], cenario["ana"], {"motivo": "viagem"})
    apr.decidir(pedido.aprovacao, cenario["gestor"], apr.Decisao.APROVAR)
    pedido.refresh_from_db()

    assert pedido.situacao == SituacaoServico.APROVADA
    assert pedido.pk in list(atd.fila_de(cenario["area"]).values_list("pk", flat=True))
    assert not apr.pendentes_para(cenario["area"]).exists()


def test_a_fase_diz_para_qual_area_o_pedido_foi(cenario):
    pedido = svc.solicitar(cenario["item"], cenario["ana"], {"motivo": "viagem"})
    apr.decidir(pedido.aprovacao, cenario["gestor"], apr.Decisao.APROVAR)
    pedido.refresh_from_db()

    assert pedido.fase == "Aprovada · aguardando Financeiro"


def test_a_area_conclui_sem_precisar_assumir_antes(cenario):
    """Um clique, não dois: "realizado" é a resposta da área, e obrigá-la a
    assumir antes só produz duas telas para o mesmo fim."""
    pedido = svc.solicitar(cenario["item"], cenario["ana"], {"motivo": "viagem"})
    apr.decidir(pedido.aprovacao, cenario["gestor"], apr.Decisao.APROVAR)
    pedido.refresh_from_db()

    atd.concluir(pedido, cenario["area"])

    pedido.refresh_from_db()
    assert pedido.situacao == SituacaoServico.CONCLUIDA


# ── Devolvido continua vivo ─────────────────────────────────────────


def test_devolvido_continua_em_aberto(cenario):
    """"O chamado continua em aberto" — ele não some da esteira nem da conta."""
    pedido = devolvido(cenario)

    assert pedido.situacao == SituacaoServico.DEVOLVIDA
    assert pedido.em_aberto
    assert pedido.pode_reenviar


def test_devolvido_carrega_o_motivo(cenario):
    """Sem motivo, quem recebe de volta adivinha — e adivinhar gera um segundo
    envio igualmente errado."""
    pedido = devolvido(cenario, "Falta o comprovante da despesa.")

    assert pedido.motivo_devolucao == "Falta o comprovante da despesa."


def test_devolvido_sai_da_fila_da_area(cenario):
    """A bola está com quem pediu. Deixá-lo na fila faria a área olhar todo dia
    um pedido que não depende dela."""
    pedido = devolvido(cenario)

    assert pedido.pk not in list(
        atd.fila_de(cenario["area"]).values_list("pk", flat=True)
    )


# ── O reenvio ───────────────────────────────────────────────────────


def test_reenviar_promove_a_mesma_linha(cenario):
    """O MESMO número. Um pedido novo partiria o histórico do mesmo assunto em
    dois e deixaria o primeiro aberto para sempre."""
    pedido = devolvido(cenario)

    reenviado = svc.solicitar(
        cenario["item"], cenario["ana"], {"motivo": "viagem com comprovante"},
        devolvido=pedido,
    )

    assert reenviado.pk == pedido.pk
    assert SolicitacaoServico.objects.count() == 1


def test_reenviar_guarda_o_que_foi_corrigido(cenario):
    pedido = devolvido(cenario)

    svc.solicitar(
        cenario["item"], cenario["ana"], {"motivo": "agora com nota fiscal"},
        devolvido=pedido,
    )

    pedido.refresh_from_db()
    assert pedido.dados["motivo"] == "agora com nota fiscal"


def test_reenviar_limpa_o_motivo_da_devolucao(cenario):
    """Ele deixou de ser verdade: a pessoa corrigiu. Deixá-lo na tela faria o
    pedido continuar parecendo devolvido depois de reenviado — e é a etiqueta
    que quem atende lê primeiro."""
    pedido = devolvido(cenario)

    svc.solicitar(cenario["item"], cenario["ana"], {"motivo": "ok"}, devolvido=pedido)

    pedido.refresh_from_db()
    assert pedido.motivo_devolucao == ""


def test_reenviar_solta_o_atendente(cenario):
    """Quem devolveu não é mais responsável. Manter o nome faria a fila mostrar
    "em andamento com Fulano" um pedido que ninguém está atendendo."""
    pedido = svc.solicitar(cenario["item"], cenario["ana"], {"motivo": "viagem"})
    apr.decidir(pedido.aprovacao, cenario["gestor"], apr.Decisao.APROVAR)
    pedido.refresh_from_db()
    atd.assumir(pedido, cenario["area"])
    atd.devolver(pedido, cenario["area"], "faltou nota")
    pedido.refresh_from_db()
    assert pedido.atendente == cenario["area"]

    svc.solicitar(cenario["item"], cenario["ana"], {"motivo": "ok"}, devolvido=pedido)

    pedido.refresh_from_db()
    assert pedido.atendente is None


def test_reenviar_refaz_a_cadeia_de_aprovacao(cenario):
    """O gestor aprovou um texto; a pessoa mudou o texto. Reaproveitar a
    aprovação seria fazer alguém assinar o que não viu."""
    pedido = devolvido(cenario)
    aprovacao_antiga = pedido.aprovacao

    reenviado = svc.solicitar(
        cenario["item"], cenario["ana"], {"motivo": "outra coisa"}, devolvido=pedido
    )

    assert reenviado.situacao == SituacaoServico.AGUARDANDO_APROVACAO
    assert reenviado.aprovacao_id != aprovacao_antiga.pk
    assert reenviado.aprovacao.etapa_atual.aprovador == cenario["gestor"]


def test_reenviar_nao_devolve_o_relogio_do_prazo(cenario):
    """Se o reenvio zerasse `criado_em`, devolver viraria o jeito de limpar o
    próprio atraso — e o prazo passaria a medir a última tentativa em vez da
    espera real de quem pediu."""
    pedido = devolvido(cenario)
    SolicitacaoServico.objects.filter(pk=pedido.pk).update(
        criado_em=timezone.now() - timedelta(days=10)
    )
    pedido.refresh_from_db()
    nascimento = pedido.criado_em

    svc.solicitar(cenario["item"], cenario["ana"], {"motivo": "ok"}, devolvido=pedido)

    pedido.refresh_from_db()
    assert pedido.criado_em == nascimento
    assert pedido.prioridade == "atrasado", "o atraso acumulado continua visível"


def test_reenviar_deixa_linha_propria_no_historico(cenario):
    """"Voltou corrigido" não é "nasceu". Sem uma ação própria, o mesmo pedido
    apareceria nascendo duas vezes e a cadeia teria dois começos."""
    pedido = devolvido(cenario)

    svc.solicitar(cenario["item"], cenario["ana"], {"motivo": "ok"}, devolvido=pedido)

    acoes = [e.acao for e in pedido.eventos.order_by("quando")]
    assert acoes == ["criada", "aprovada", "devolvida", "reenviada"]


def test_o_pedido_reenviado_volta_a_percorrer_o_fluxo_inteiro(cenario):
    """"Seguirá novamente o fluxo padrão original" — até a área, de novo."""
    pedido = devolvido(cenario)
    reenviado = svc.solicitar(
        cenario["item"], cenario["ana"], {"motivo": "corrigido"}, devolvido=pedido
    )

    apr.decidir(reenviado.aprovacao, cenario["gestor"], apr.Decisao.APROVAR)
    reenviado.refresh_from_db()
    assert reenviado.pk in list(
        atd.fila_de(cenario["area"]).values_list("pk", flat=True)
    )

    atd.concluir(reenviado, cenario["area"])

    reenviado.refresh_from_db()
    assert reenviado.situacao == SituacaoServico.CONCLUIDA


# ── Quem pode reenviar ──────────────────────────────────────────────


def test_ninguem_reenvia_o_pedido_de_outra_pessoa(cenario):
    """Sem isto, trocar um dígito na URL reenviaria o pedido de um colega em
    nome dele — com o texto que o intruso quisesse."""
    pedido = devolvido(cenario)

    with pytest.raises(SolicitacaoError, match="não é seu"):
        svc.solicitar(
            cenario["item"], cenario["estranho"], {"motivo": "meu agora"},
            devolvido=pedido,
        )


def test_so_pedido_devolvido_pode_ser_reenviado(cenario):
    """Sem isto, o reenvio viraria um jeito de reabrir a cadeia de um pedido já
    aprovado — devolvendo ao gestor uma decisão que ele já tomou, sobre um
    texto que a pessoa acabou de trocar."""
    pedido = svc.solicitar(cenario["item"], cenario["ana"], {"motivo": "viagem"})
    apr.decidir(pedido.aprovacao, cenario["gestor"], apr.Decisao.APROVAR)
    pedido.refresh_from_db()

    with pytest.raises(SolicitacaoError, match="devolvido"):
        svc.solicitar(
            cenario["item"], cenario["ana"], {"motivo": "trocando"}, devolvido=pedido
        )


def test_devolvido_de_nunca_devolve_o_de_outra_pessoa(cenario):
    pedido = devolvido(cenario)

    assert svc.devolvido_de(cenario["ana"], pedido.pk) == pedido
    assert svc.devolvido_de(cenario["estranho"], pedido.pk) is None
    assert svc.devolvido_de(cenario["ana"], "não é número") is None


# ── Pela tela ───────────────────────────────────────────────────────


def test_a_lista_oferece_corrigir_e_reenviar(client, cenario):
    pedido = devolvido(cenario)
    client.force_login(cenario["ana"])

    corpo = client.get(reverse("workspace:minhas_solicitacoes")).content.decode()

    assert "Corrigir e reenviar" in corpo
    assert f"?devolvido={pedido.pk}" in corpo


def test_a_lista_nao_oferece_reenviar_o_que_nao_voltou(client, cenario):
    svc.solicitar(cenario["item"], cenario["ana"], {"motivo": "viagem"})
    client.force_login(cenario["ana"])

    corpo = client.get(reverse("workspace:minhas_solicitacoes")).content.decode()

    assert "Corrigir e reenviar" not in corpo


def test_o_formulario_volta_preenchido_e_com_o_motivo_a_vista(client, cenario):
    """Corrigir de memória é como se produz o segundo envio igualmente errado."""
    pedido = devolvido(cenario, "Falta o comprovante da despesa.")
    client.force_login(cenario["ana"])

    corpo = client.get(
        reverse("workspace:pedir", args=[cenario["item"].chave]),
        {"devolvido": pedido.pk},
    ).content.decode()

    assert "Falta o comprovante da despesa." in corpo
    assert "viagem" in corpo, "o que a pessoa tinha escrito volta"
    assert "Enviar solicitação" in corpo


def test_o_formulario_nao_abre_o_pedido_devolvido_de_outra_pessoa(client, cenario):
    pedido = devolvido(cenario)
    client.force_login(cenario["estranho"])

    corpo = client.get(
        reverse("workspace:pedir", args=[cenario["item"].chave]),
        {"devolvido": pedido.pk},
    ).content.decode()

    assert "Este pedido voltou para você" not in corpo
    assert "viagem" not in corpo


def test_enviar_pela_tela_promove_a_mesma_linha(client, cenario):
    pedido = devolvido(cenario)
    client.force_login(cenario["ana"])

    client.post(
        reverse("workspace:pedir", args=[cenario["item"].chave]),
        {"motivo": "agora com nota", "devolvido": pedido.pk, "acao": "enviar"},
    )

    pedido.refresh_from_db()
    assert SolicitacaoServico.objects.count() == 1
    assert pedido.situacao == SituacaoServico.AGUARDANDO_APROVACAO
    assert pedido.dados["motivo"] == "agora com nota"


# ── Os sete módulos ─────────────────────────────────────────────────
#
# O fluxo foi descrito com o Financeiro como exemplo e vale para os sete. O que
# faz um módulo participar dele NÃO é uma lista escrita em lugar nenhum: é
# `<raiz>.atender` existir em algum papel. Um módulo sem isso aprova o pedido e
# o deixa numa fila que ninguém pode abrir — e a fase passa a dizer
# "Aprovada · sem área responsável", que é o diagnóstico.
#
# Este teste é o que percebe se um módulo perder a área na próxima onda.

MODULOS = [
    ("Financeiro", "fin.", "financeiro"),
    ("R.H.", "rh.", "rh"),
    ("Operação", "ops.", "operacao"),
    ("Suprimentos", "log.", "logistica"),
    ("Redes / T.I.", "ti.", "ti"),
    ("Vendas", "ven.", "vendas"),
    ("Universidade", "hab.", "sesmt"),
]


@pytest.mark.parametrize("nome,prefixo,papel", MODULOS)
def test_cada_modulo_tem_area_que_recebe_a_fila(nome, prefixo, papel):
    """O papel que atende cada raiz de domínio existe e tem a permissão."""
    from identidade.papeis import PAPEIS_V1
    from workspace.services.atendimento import permissao_de

    spec = next((p for p in PAPEIS_V1 if p["chave"] == papel), None)
    assert spec is not None, f"{nome}: o papel {papel} sumiu de PAPEIS_V1"

    esperada = permissao_de(prefixo)
    tem = any(p.split(".")[:2] == esperada.split(".") for p in spec["permissoes"])
    assert tem, f"{nome}: {papel} não declara {esperada} — a fila dele não abre"


@pytest.mark.parametrize("nome,prefixo,papel", MODULOS)
def test_nenhum_modulo_tem_degrau_de_aprovacao_da_propria_area(
    nome, prefixo, papel, cenario
):
    """A área revisa na FILA, não numa segunda bandeja.

    Enquanto o degrau existia, a área tocava o mesmo pedido duas vezes — e quem
    pediu via "aguardando aprovação" depois de o gestor já ter aprovado.
    """
    from io import StringIO

    from django.core.management import call_command

    call_command("semear_papeis", "--aplicar", stdout=StringIO())
    call_command("semear_regras_aprovacao", "--aplicar", stdout=StringIO())

    assert not RegraAprovacao.objects.filter(
        ativa=True, dominio=prefixo, tipo=TipoAprovador.PAPEL, ordem=15
    ).exists(), f"{nome} voltou a ter revisão de área na cadeia"
