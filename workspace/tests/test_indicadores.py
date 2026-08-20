"""IND — o painel que faz o portal se defender.

O índice `wks_evento_quem_idx` foi criado com um comentário dizendo para que
servia — *"quantos o Fulano concluiu em julho"* — e nada consultava. O produto
media tudo e não mostrava nada.

O que estes testes protegem:

1. **Quem vê o quê.** Diretoria, Sócios e R.H. veem a empresa; quem atende uma
   fila vê a própria área; quem não é nem um nem outro recebe 403.
2. **As contas.** Mediana e não média, aprovar e atender separados, e o
   denominador da taxa de reabertura — que na primeira medição deu **200%**.
3. **O custo.** O painel é a tela que mais tenta virar N+1, porque a cabeça
   pensa "para cada área, calcule...".
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.models import (
    GrupoCatalogo,
    ItemCatalogo,
    SituacaoServico,
    SolicitacaoServico,
)
from workspace.services import atendimento as atd
from workspace.services import catalogo as svc
from workspace.services import indicadores as ind

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    ana, chefia, comprador = (f.pessoa(n) for n in ("ana", "chefia", "comprador"))
    for pessoa in (ana, chefia, comprador):
        f.lotar(pessoa)
    f.atribuir(chefia, f.papel("diretoria", ["ind.ler.global"], escopo="global"))
    f.atribuir(comprador, f.papel("compras", ["com.atender.global"], escopo="global"))

    compra = ItemCatalogo.objects.create(
        chave="cadeira", nome="Cadeira", grupo=GrupoCatalogo.EQUIPAMENTO,
        dominio="com.requisicao", prazo_prometido_dias=3,
        limite_auto_aprovacao=Decimal("0"),
        campos=[{"chave": "o_que", "rotulo": "O quê", "obrigatorio": True}],
    )
    ferias = ItemCatalogo.objects.create(
        chave="ferias", nome="Férias", grupo=GrupoCatalogo.TRABALHO,
        dominio="rh.ferias", prazo_prometido_dias=5,
        limite_auto_aprovacao=Decimal("0"),
        campos=[{"chave": "o_que", "rotulo": "O quê", "obrigatorio": True}],
    )
    return {
        "ana": ana, "chefia": chefia, "comprador": comprador,
        "compra": compra, "ferias": ferias,
    }


def pedir(item, pessoa, n=1):
    return [svc.solicitar(item, pessoa, {"o_que": f"p{i}"}) for i in range(n)]


def concluir_em(pedido, levou_dias):
    fim = timezone.now()
    SolicitacaoServico.objects.filter(pk=pedido.pk).update(
        situacao=SituacaoServico.CONCLUIDA,
        criado_em=fim - timedelta(days=levou_dias),
        concluido_em=fim,
    )


def area(panorama, dominio):
    return next(a for a in panorama["areas"] if a["dominio"] == dominio)


# ── Quem vê o quê ───────────────────────────────────────────────────


def test_a_diretoria_ve_a_empresa_inteira(cenario):
    pedir(cenario["compra"], cenario["ana"])
    pedir(cenario["ferias"], cenario["ana"])

    panorama = ind.panorama(cenario["chefia"])

    assert {a["dominio"] for a in panorama["areas"]} == {"com", "rh"}
    assert panorama["tudo"] is True


def test_quem_atende_ve_so_a_propria_area(cenario):
    """O gerente de Compras tem direito aos números de Compras sem precisar dos
    do R.H. — e negar isso obrigaria a pedir relatório toda semana."""
    pedir(cenario["compra"], cenario["ana"])
    pedir(cenario["ferias"], cenario["ana"])

    panorama = ind.panorama(cenario["comprador"])

    assert [a["dominio"] for a in panorama["areas"]] == ["com"]
    assert panorama["tudo"] is False


def test_quem_nao_atende_nem_administra_nao_tem_painel(cenario):
    with pytest.raises(ind.SemPainel):
        ind.panorama(cenario["ana"])


def test_a_tela_recusa_em_vez_de_mostrar_tudo_zerado(client, cenario):
    """Números todos em zero para quem nunca vai ter dado faz a pessoa achar
    que a empresa parou."""
    client.force_login(cenario["ana"])

    assert client.get(reverse("workspace:indicadores")).status_code == 403


def test_a_tela_abre_para_a_diretoria(client, cenario):
    client.force_login(cenario["chefia"])

    assert client.get(reverse("workspace:indicadores")).status_code == 200


def test_o_trilho_mostra_o_item_para_quem_tem_painel(client, cenario):
    client.force_login(cenario["comprador"])

    corpo = client.get(reverse("workspace:servicos")).content.decode()

    assert reverse("workspace:indicadores") in corpo


def test_o_trilho_esconde_o_item_de_quem_nao_tem(client, cenario):
    client.force_login(cenario["ana"])

    corpo = client.get(reverse("workspace:servicos")).content.decode()

    assert reverse("workspace:indicadores") not in corpo


# ── As contas ───────────────────────────────────────────────────────


def test_o_tempo_ate_resolver_e_a_mediana(cenario):
    """Um pedido esquecido oitenta dias puxaria a média da área inteira e faria
    o setor parecer lento."""
    pedidos = pedir(cenario["compra"], cenario["ana"], 3)
    concluir_em(pedidos[0], 1)
    concluir_em(pedidos[1], 2)
    concluir_em(pedidos[2], 80)

    assert area(ind.panorama(cenario["chefia"]), "com")["ate_concluir"] == 2


def test_sem_amostra_o_tempo_e_None_e_nao_zero(cenario):
    """Zero diria "resolve no mesmo dia", que é o oposto de "ainda não sei"."""
    pedir(cenario["compra"], cenario["ana"])

    assert area(ind.panorama(cenario["chefia"]), "com")["ate_concluir"] is None


def test_atraso_conta_so_o_que_ainda_esta_aberto(cenario):
    """O que já foi entregue tem o tempo real medido na coluna do lado; contar
    as duas coisas somaria o mesmo pedido duas vezes."""
    velho, entregue = pedir(cenario["compra"], cenario["ana"], 2)
    SolicitacaoServico.objects.filter(pk=velho.pk).update(
        criado_em=timezone.now() - timedelta(days=30)
    )
    concluir_em(entregue, 30)

    assert area(ind.panorama(cenario["chefia"]), "com")["atrasados"] == 1


def test_a_taxa_de_reabertura_nao_passa_de_cem(cenario):
    """O DEFEITO da primeira medição: deu 200%.

    Um pedido reaberto deixa de estar "concluído", então saía do denominador e
    continuava no numerador. O denominador honesto é quantos já foram entregues
    ALGUMA VEZ.
    """
    pedidos = pedir(cenario["compra"], cenario["ana"], 2)
    for pedido in pedidos:
        atd.assumir(pedido, cenario["comprador"])
        atd.concluir(pedido, cenario["comprador"])
        atd.reabrir(pedido, cenario["ana"], "não resolveu")

    taxa = ind.panorama(cenario["chefia"])["taxa_reabertura"]

    assert taxa == 100, "dois entregues, dois voltaram"


def test_area_sem_movimento_nao_vira_linha(cenario):
    """Zero em todas as colunas não é informação; é ruído que empurra para
    baixo as áreas que têm o que mostrar."""
    pedir(cenario["compra"], cenario["ana"])

    assert [a["dominio"] for a in ind.panorama(cenario["chefia"])["areas"]] == ["com"]


def test_fora_da_janela_o_pedido_nao_conta(cenario):
    """Indicador acumulado desde a fundação nunca melhora, por melhor que a
    equipe fique."""
    antigo = pedir(cenario["compra"], cenario["ana"])[0]
    SolicitacaoServico.objects.filter(pk=antigo.pk).update(
        criado_em=timezone.now() - timedelta(days=400)
    )

    assert ind.panorama(cenario["chefia"], dias=90)["total"] == 0
    assert ind.panorama(cenario["chefia"], dias=365)["total"] == 0


def test_quem_entregou_sai_do_historico(cenario):
    """A consulta que o índice `wks_evento_quem_idx` esperava desde que o
    histórico foi criado."""
    pedido = pedir(cenario["compra"], cenario["ana"])[0]
    atd.assumir(pedido, cenario["comprador"])
    atd.concluir(pedido, cenario["comprador"])

    entregou = ind.panorama(cenario["chefia"])["quem_entregou"]

    assert entregou[0]["total"] == 1


def test_mais_pedidos_ordena_pelo_volume(cenario):
    pedir(cenario["compra"], cenario["ana"], 3)
    pedir(cenario["ferias"], cenario["ana"], 1)

    mais = ind.panorama(cenario["chefia"])["mais_pedidos"]

    assert mais[0] == {"nome": "Cadeira", "total": 3}


def test_o_recorte_de_area_nao_vaza_o_de_outra(cenario):
    """Quem entregou é filtrado pelas áreas visíveis, como o resto."""
    pedido = pedir(cenario["ferias"], cenario["ana"])[0]
    SolicitacaoServico.objects.filter(pk=pedido.pk).update(
        situacao=SituacaoServico.CONCLUIDA, concluido_em=timezone.now()
    )

    panorama = ind.panorama(cenario["comprador"])

    assert all(a["dominio"] == "com" for a in panorama["areas"])


# ── O custo ─────────────────────────────────────────────────────────


def test_o_painel_nao_cresce_em_consultas_com_as_areas(cenario, django_assert_max_num_queries):
    """A tela que mais tenta virar N+1: a cabeça pensa "para cada área,
    calcule..."."""
    for i in range(6):
        item = ItemCatalogo.objects.create(
            chave=f"x{i}", nome=f"X{i}", grupo=GrupoCatalogo.EQUIPAMENTO,
            dominio=f"d{i}.coisa", prazo_prometido_dias=3,
            limite_auto_aprovacao=Decimal("0"),
            campos=[{"chave": "o_que", "rotulo": "O quê", "obrigatorio": True}],
        )
        pedir(item, cenario["ana"], 2)

    with django_assert_max_num_queries(5):
        ind.panorama(cenario["chefia"])


# ── O período ───────────────────────────────────────────────────────


def test_periodo_invalido_cai_no_padrao(client, cenario):
    """`?dias=99999` faria uma consulta enorme por uma URL digitada."""
    client.force_login(cenario["chefia"])

    contexto = client.get(reverse("workspace:indicadores"), {"dias": 99999}).context

    assert contexto["dias"] == ind.PERIODO_PADRAO


def test_periodo_da_lista_e_respeitado(client, cenario):
    client.force_login(cenario["chefia"])

    contexto = client.get(reverse("workspace:indicadores"), {"dias": 30}).context

    assert contexto["dias"] == 30


# ── "Abertos" eram duas filas somadas ───────────────────────────────


def test_o_painel_separa_o_que_espera_decisao_do_que_espera_a_area(cenario):
    """A coluna "Abertos" somava o que espera DECISÃO de um gestor com o que
    espera TRABALHO da área.

    O efeito foi relatado assim: o painel dizia que o T.I. tinha um chamado
    pendente, e no perfil do T.I. não havia nada a fazer — porque o pedido
    estava parado na mesa de um gestor, e o T.I. não aprova nada. Quem lia
    concluía que o produto estava mentindo; ele estava misturando duas filas.
    """
    pedidos = pedir(cenario["compra"], cenario["ana"], n=3)
    # Sem cadeia montada o pedido nasce liberado. Aqui interessa o CONTRÁRIO:
    # dois parados esperando decisão de alguém, um já liberado esperando a área.
    SolicitacaoServico.objects.filter(
        pk__in=[p.pk for p in pedidos[1:]]
    ).update(situacao=SituacaoServico.AGUARDANDO_APROVACAO)
    SolicitacaoServico.objects.filter(pk=pedidos[0].pk).update(
        situacao=SituacaoServico.APROVADA
    )

    compras = area(ind.panorama(cenario["chefia"]), "com")

    assert compras["abertos"] == 3
    assert compras["aguardando"] == 2
    assert compras["com_a_area"] == 1


def test_o_que_ja_esta_em_andamento_conta_como_da_area(cenario):
    pedido = pedir(cenario["compra"], cenario["ana"])[0]
    SolicitacaoServico.objects.filter(pk=pedido.pk).update(
        situacao=SituacaoServico.EM_ATENDIMENTO
    )

    compras = area(ind.panorama(cenario["chefia"]), "com")

    assert compras["aguardando"] == 0
    assert compras["com_a_area"] == 1


def test_a_tela_mostra_as_duas_colunas(client, cenario):
    pedir(cenario["compra"], cenario["ana"])
    client.force_login(cenario["chefia"])

    corpo = client.get(reverse("workspace:indicadores")).content.decode()

    assert "Com a área" in corpo
    assert "Aguardando aprovação" in corpo
