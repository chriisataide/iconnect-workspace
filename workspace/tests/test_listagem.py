"""LST — filtrar e paginar, e o custo de não fazer nem uma coisa nem outra.

Três defeitos medidos no produto rodando, todos invisíveis com dezenove pedidos
no banco e todos garantidos com vinte mil:

1. **O catálogo fazia 42 consultas**, 28 delas de `prazo_medido()` — uma por
   item, e cada uma lendo todo o histórico de conclusões daquele item.
2. **Nenhuma lista paginava.** Quatorze pedidos já geravam 65 KB de HTML e
   quinze `<dialog>` montados no servidor, um por linha. Crescimento linear,
   sem teto.
3. **Nenhuma lista filtrava.** Achar "aquele reembolso de março" era rolar a
   tela, e numa lista que só cresce isso deixa de ser incômodo.

O que estes testes protegem é principalmente o **número de consultas** — a
única das três que regride sem ninguém ver.
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
from workspace.services import listagem as lst

pytestmark = pytest.mark.django_db


@pytest.fixture
def ana():
    pessoa = f.pessoa("ana")
    f.lotar(pessoa)
    return pessoa


@pytest.fixture
def item():
    return ItemCatalogo.objects.create(
        chave="cadeira", nome="Cadeira nova", grupo=GrupoCatalogo.EQUIPAMENTO,
        dominio="com.requisicao", prazo_prometido_dias=9,
        limite_auto_aprovacao=Decimal("0"),
        campos=[{"chave": "o_que", "rotulo": "O quê", "obrigatorio": True}],
    )


def pedir(item, pessoa, n=1):
    return [
        svc.solicitar(item, pessoa, {"o_que": f"pedido {i}"}) for i in range(n)
    ]


def concluir(pedido, dias_atras=1, levou=2):
    """Conclui no passado, para alimentar o prazo medido."""
    fim = timezone.now() - timedelta(days=dias_atras)
    SolicitacaoServico.objects.filter(pk=pedido.pk).update(
        situacao=SituacaoServico.CONCLUIDA,
        criado_em=fim - timedelta(days=levou),
        concluido_em=fim,
    )


# ── 1. O prazo medido, em uma consulta ──────────────────────────────


def test_o_prazo_de_muitos_itens_custa_uma_consulta(ana, django_assert_num_queries):
    """O defeito: uma consulta por item, cada uma lendo o histórico inteiro."""
    itens = [
        ItemCatalogo.objects.create(
            chave=f"item-{i}", nome=f"Item {i}", grupo=GrupoCatalogo.EQUIPAMENTO,
            dominio="com.x", prazo_prometido_dias=3,
        )
        for i in range(10)
    ]

    with django_assert_num_queries(1):
        svc.prazos_medidos(itens)


def test_o_catalogo_nao_cresce_em_consultas_com_o_catalogo(client, ana, django_assert_num_queries):
    """A tela mais visitada do produto não pode custar mais a cada item novo."""
    for i in range(12):
        ItemCatalogo.objects.create(
            chave=f"extra-{i}", nome=f"Extra {i}", grupo=GrupoCatalogo.EQUIPAMENTO,
            dominio="com.x", prazo_prometido_dias=3,
        )
    client.force_login(ana)
    antes = len(_consultas(client, reverse("workspace:servicos")))

    for i in range(12):
        ItemCatalogo.objects.create(
            chave=f"mais-{i}", nome=f"Mais {i}", grupo=GrupoCatalogo.EQUIPAMENTO,
            dominio="com.x", prazo_prometido_dias=3,
        )
    depois = len(_consultas(client, reverse("workspace:servicos")))

    assert depois == antes, "dobrar o catálogo não pode dobrar as consultas"


def _consultas(client, url):
    from django.db import connection, reset_queries
    from django.test.utils import override_settings

    with override_settings(DEBUG=True):
        client.get(url)  # aquece
        reset_queries()
        client.get(url)
        return list(connection.queries)


def test_sem_historico_bastante_o_prazo_e_o_prometido(item, ana):
    pedir(item, ana, 3)

    dias, medido = svc.prazo_medido(item)

    assert (dias, medido) == (9, False)


def test_com_historico_o_prazo_vem_da_realidade(item, ana):
    for pedido in pedir(item, ana, svc.MINIMO_PARA_PRAZO_MEDIDO):
        concluir(pedido, levou=4)

    dias, medido = svc.prazo_medido(item)

    assert (dias, medido) == (4, True)


def test_conclusao_velha_nao_conta_mais(item, ana):
    """O prazo é uma promessa sobre o que a empresa faz HOJE. Média de todo o
    histórico envelhece junto com a empresa e nunca melhora."""
    for pedido in pedir(item, ana, svc.MINIMO_PARA_PRAZO_MEDIDO):
        concluir(pedido, dias_atras=svc.JANELA_PRAZO_DIAS + 30, levou=1)

    dias, medido = svc.prazo_medido(item)

    assert medido is False, "fora da janela, volta a valer o prometido"
    assert dias == 9


def test_o_lote_e_o_individual_concordam(item, ana):
    for pedido in pedir(item, ana, svc.MINIMO_PARA_PRAZO_MEDIDO):
        concluir(pedido, levou=6)

    assert svc.prazos_medidos([item])[item.pk] == svc.prazo_medido(item)


def test_item_sem_pedido_nenhum_nao_some_do_lote(item):
    assert svc.prazos_medidos([item]) == {item.pk: (9, False)}


# ── 2. Paginação ────────────────────────────────────────────────────


def test_a_lista_pagina(client, item, ana):
    pedir(item, ana, lst.POR_PAGINA + 5)
    client.force_login(ana)

    contexto = client.get(reverse("workspace:minhas_solicitacoes")).context

    assert len(contexto["solicitacoes"]) == lst.POR_PAGINA
    assert contexto["pagina"].paginator.num_pages == 2


def test_a_pagina_dois_traz_o_resto(client, item, ana):
    pedir(item, ana, lst.POR_PAGINA + 5)
    client.force_login(ana)

    contexto = client.get(
        reverse("workspace:minhas_solicitacoes"), {"p": 2}
    ).context

    assert len(contexto["solicitacoes"]) == 5


def test_pagina_absurda_cai_na_ultima_em_vez_de_404(client, item, ana):
    """Quem chega com `?p=99` veio de um link velho. Devolver 404 é castigar a
    pessoa por uma URL que o próprio produto deu."""
    pedir(item, ana, 3)
    client.force_login(ana)

    resposta = client.get(reverse("workspace:minhas_solicitacoes"), {"p": 99})

    assert resposta.status_code == 200


def test_pagina_que_nao_e_numero_cai_na_primeira(client, item, ana):
    pedir(item, ana, 3)
    client.force_login(ana)

    resposta = client.get(reverse("workspace:minhas_solicitacoes"), {"p": "abc"})

    assert resposta.status_code == 200
    assert resposta.context["pagina"].number == 1


def test_a_pagina_so_carrega_os_modais_dela(client, item, ana):
    """O resumo em modal é montado no servidor, um por linha. Sem paginar, a
    página cresce para sempre."""
    pedir(item, ana, lst.POR_PAGINA + 5)
    client.force_login(ana)

    corpo = client.get(reverse("workspace:minhas_solicitacoes")).content.decode()

    assert corpo.count("<dialog") == lst.POR_PAGINA + 1, "os da página + a paleta"


def test_lista_curta_nao_mostra_paginacao(client, item, ana):
    """Controle que diz "página 1 de 1" ensina a pessoa a ignorá-lo."""
    pedir(item, ana, 3)
    client.force_login(ana)

    assert "au-paginacao" not in client.get(
        reverse("workspace:minhas_solicitacoes")
    ).content.decode()


# ── 3. Filtro e busca ───────────────────────────────────────────────


def test_filtrar_por_situacao(client, item, ana):
    pedidos = pedir(item, ana, 4)
    svc.cancelar(pedidos[0], ana)
    client.force_login(ana)

    contexto = client.get(
        reverse("workspace:minhas_solicitacoes"), {"situacao": "cancelada"}
    ).context

    assert [s.pk for s in contexto["solicitacoes"]] == [pedidos[0].pk]


def test_buscar_pelo_nome_do_servico(client, item, ana):
    outro = ItemCatalogo.objects.create(
        chave="ferias", nome="Férias", grupo=GrupoCatalogo.TRABALHO,
        dominio="rh.ferias", limite_auto_aprovacao=Decimal("0"),
        campos=[{"chave": "o_que", "rotulo": "O quê", "obrigatorio": True}],
    )
    pedir(item, ana, 2)
    pedir(outro, ana, 1)
    client.force_login(ana)

    contexto = client.get(
        reverse("workspace:minhas_solicitacoes"), {"q": "Férias"}
    ).context

    assert contexto["encontradas"] == 1


def test_a_busca_nao_varre_o_conteudo_do_formulario(client, item, ana):
    """Ali moram atestado, dados bancários e motivo de afastamento. Uma busca
    que varre isso vira um vazador de dado sensível para quem espia a tela."""
    pedir(item, ana, 1)
    client.force_login(ana)

    contexto = client.get(
        reverse("workspace:minhas_solicitacoes"), {"q": "pedido 0"}
    ).context

    assert contexto["encontradas"] == 0


def test_o_filtro_sobrevive_a_troca_de_pagina(client, item, ana):
    """Clicar em "próxima" dentro de um filtro não pode voltar para a lista
    inteira — a pessoa perderia o recorte sem entender por quê."""
    pedidos = pedir(item, ana, lst.POR_PAGINA + 5)
    for pedido in pedidos:
        svc.cancelar(pedido, ana)
    client.force_login(ana)

    corpo = client.get(
        reverse("workspace:minhas_solicitacoes"), {"situacao": "cancelada"}
    ).content.decode()

    assert "situacao=cancelada&amp;p=2" in corpo


def test_filtro_sem_resultado_nao_diz_que_voce_nunca_pediu_nada(client, item, ana):
    """A mesma frase para quem filtrou e não achou é mentira, e faz a pessoa
    achar que perdeu os pedidos."""
    pedir(item, ana, 3)
    client.force_login(ana)

    corpo = client.get(
        reverse("workspace:minhas_solicitacoes"), {"situacao": "cancelada"}
    ).content.decode()

    assert "Nada com esse recorte" in corpo
    assert "ainda não pediu nada" not in corpo


# ── A fila ──────────────────────────────────────────────────────────


@pytest.fixture
def fila(item, ana):
    tecnico = f.pessoa("tecnico")
    f.lotar(tecnico)
    f.atribuir(tecnico, f.papel("com", ["com.atender.global"], escopo="global"))
    pedidos = pedir(item, ana, 3)
    atd.assumir(pedidos[0], tecnico)
    return {"tecnico": tecnico, "pedidos": pedidos}


def test_a_fila_filtra_o_que_e_meu(client, fila):
    client.force_login(fila["tecnico"])

    contexto = client.get(reverse("workspace:fila"), {"filtro": "meus"}).context

    assert [s.pk for s in contexto["solicitacoes"]] == [fila["pedidos"][0].pk]


def test_a_fila_filtra_o_que_nao_tem_dono(client, fila):
    """É onde a fila trava quando todo mundo acha que é do outro."""
    client.force_login(fila["tecnico"])

    contexto = client.get(reverse("workspace:fila"), {"filtro": "livres"}).context

    assert contexto["encontradas"] == 2


def test_os_kpis_nao_acompanham_o_filtro(client, fila):
    """"3 atrasados" não pode virar "0 atrasados" porque a pessoa clicou numa
    aba — a tela passaria a esconder o que ela existe para mostrar."""
    client.force_login(fila["tecnico"])

    contexto = client.get(reverse("workspace:fila"), {"filtro": "meus"}).context

    assert contexto["resumo"]["total"] == 3
    assert len(contexto["solicitacoes"]) == 1


def test_filtro_vazio_nao_diz_que_a_fila_esta_vazia(client, fila):
    client.force_login(fila["tecnico"])
    atd.concluir(fila["pedidos"][0], fila["tecnico"])

    corpo = client.get(reverse("workspace:fila"), {"filtro": "meus"}).content.decode()

    assert "Nada com esse recorte" in corpo
    assert "Nada esperando você" not in corpo
