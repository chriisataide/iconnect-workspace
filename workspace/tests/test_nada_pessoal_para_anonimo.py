"""WKS — o visitante anônimo não vê o que é de uma pessoa.

O Workspace é ABERTO, e `pessoa_da_requisicao()` devolve uma conta real do
organograma para quem não entrou: as telas do hub precisam de alguém para
calcular ALCANCE — quais tiles aparecem, quais itens do catálogo, quais
documentos o acervo mostra.

Alcance é uma coisa. **Contador pessoal é outra**, e o produto misturava as
duas. Quem abrisse `/workspace/` sem entrar via, no trilho, os números da
primeira conta do organograma — no banco de demonstração, os do superusuário:
quantas notificações ele tinha para ler, quantas aprovações esperavam por ele,
e até o item "Pessoas e papéis", que só aparece para quem administra.

Não era exploração de falha: era a tela contando, a quem passasse pelo
endereço, quantas notificações uma pessoa específica tinha.

O que estes testes protegem:

1. **Nenhum contador pessoal** para quem não entrou — nem no trilho, nem na
   documentação.
2. **Nenhum item pessoal** no trilho: "Atender" e "Pessoas e papéis" são
   trabalho de gente com nome.
3. **Alcance continua funcionando** — o hub aberto não pode virar um hub vazio.
4. Depois do login, os números são **de quem entrou**, e de mais ninguém.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.context import rail
from workspace.models import (
    GrupoCatalogo,
    ItemCatalogo,
    TipoNotificacao,
)
from workspace.services import catalogo as svc
from workspace.services import notificacoes as nt

pytestmark = pytest.mark.django_db


@pytest.fixture
def gente_com_coisas():
    """Alguém com notificação, pedido aberto e poder de administrar papéis —
    exatamente o perfil cujos números vazavam."""
    dono = f.pessoa("dono")
    f.lotar(dono)
    f.atribuir(dono, f.papel("rh", ["rh.admin.global", "rh.atender.global"], escopo="global"))

    item = ItemCatalogo.objects.create(
        chave="cadeira", nome="Cadeira", grupo=GrupoCatalogo.EQUIPAMENTO,
        dominio="rh.pedido", limite_auto_aprovacao=Decimal("0"),
        campos=[{"chave": "o_que", "rotulo": "O quê", "obrigatorio": True}],
    )
    svc.solicitar(item, dono, {"o_que": "uma"})
    nt.criar(dono, tipo=TipoNotificacao.PEDIDO_APROVADO, titulo="Seu pedido saiu")
    return dono


def corpo(client, rota="workspace:servicos"):
    return client.get(reverse(rota)).content.decode()


# ── O trilho de quem não entrou ─────────────────────────────────────


def test_o_trilho_do_anonimo_e_todo_zero(client, gente_com_coisas):
    """O defeito, na forma mais direta: o anônimo via os números de outra
    pessoa porque a função que calcula alcance foi usada para contar."""

    class Req:
        path = "/workspace/"
        user = client.get(reverse("workspace:home")).wsgi_request.user

    assert rail(Req()) == {
        "eu": None,
        "abertas": 0,
        # §43 — rascunho tem contador próprio, e o do anônimo também é zero.
        "rascunhos": 0,
        "pendentes_aprovacao": 0,
        "nao_lidas": 0,
        "notificacoes_recentes": (),
        "na_fila": 0,
        "administra_papeis": False,
        # O painel de indicadores segue a mesma regra: sem sessão, sem item.
        "ve_aprovacoes": False,
        "habilitacoes_pendentes": 0,
        "ve_faq": False,
        "ve_publicacoes": False,
        "ve_indicadores": False,
        # §Onda 3 — a tela de resultados e a de fontes. `False` para
        # anônimo pela razão mais simples possível: resultado
        # financeiro não é informação institucional, e a tela de
        # fontes conta quais sistemas a empresa usa.
        "ve_resultados": False,
        # §Onda 4 — o painel de exceções. `False` para anônimo pela
        # mesma razão dos outros dois: a lista de regras conta o que a
        # empresa vigia, e a grade nomeia gente.
        "ve_excecoes": False,
        "ve_fontes": False,
        # Estoque e custódia entram na mesma regra: a porta do estoque não é
        # oferecida a quem não pode abri-la, e "0 equipamentos para confirmar"
        # de outra pessoa é exatamente o número que o anônimo não pode ver.
        "ve_estoque": False,
        "custodias_a_aceitar": 0,
        "ve_frota": False,
        "prazos_de_veiculo": 0,
        # §37 — leitura obrigatória e vigência de documento seguem a mesma
        # regra: são de UMA pessoa, e o anônimo não é ninguém.
        "leituras_pendentes": 0,
        "ve_documentos": False,
        "documentos_a_vencer": 0,
        "ve_marketing": False,
        "prazos_de_marketing": 0,
        "ve_candidaturas": False,
        "chamados_abertos": 0,
    }


def test_o_anonimo_nao_ve_contador_de_notificacao_na_tela(client, gente_com_coisas):
    assert nt.quantas_nao_lidas(gente_com_coisas) == 1, "a pessoa TEM o que ler"

    assert "au-rail-contagem" not in corpo(client)


def test_o_anonimo_nao_ve_o_item_de_atender(client, gente_com_coisas):
    """Fila é trabalho de gente com nome."""
    assert "workspace:fila" not in corpo(client)
    assert reverse("workspace:fila") not in corpo(client)


def test_o_anonimo_nao_ve_o_item_de_papeis(client, gente_com_coisas):
    """Esse item só aparece para quem administra — e ninguém administra sem
    estar logado."""
    assert reverse("workspace:pessoas") not in corpo(client)


def test_o_trilho_do_anonimo_nao_consulta_o_banco(client, django_assert_num_queries):
    """Não vazar é o principal; não custar cinco consultas no caminho mais
    comum do hub aberto é o troco."""

    class Req:
        path = "/workspace/"
        user = None

    with django_assert_num_queries(0):
        rail(Req())


# ── A documentação ──────────────────────────────────────────────────


def test_o_anonimo_nao_ve_leitura_pendente_de_ninguem(client, gente_com_coisas):
    """O contador dizia "3 pendentes" para quem nunca entrou, contando os
    documentos que uma conta específica ainda não tinha lido."""
    contexto = client.get(reverse("workspace:documentacao")).context

    assert contexto["pendentes"] == 0
    assert contexto["autenticado"] is False


# ── O alcance continua ──────────────────────────────────────────────


def test_o_hub_aberto_continua_aberto(client, gente_com_coisas):
    """A correção não pode transformar o hub aberto num hub vazio: o catálogo,
    o acervo e a home seguem mostrando o que existe."""
    for rota in ("workspace:home", "workspace:servicos", "workspace:documentacao"):
        resposta = client.get(reverse(rota))
        assert resposta.status_code == 200, rota

    assert "Cadeira" in corpo(client), "o item do catálogo continua à vista"


# ── Depois do login ─────────────────────────────────────────────────


def test_quem_entrou_ve_os_proprios_numeros(client, gente_com_coisas):
    client.force_login(gente_com_coisas)

    contexto = client.get(reverse("workspace:servicos")).context

    assert contexto["nao_lidas"] == 1
    assert contexto["abertas"] == 1
    assert contexto["administra_papeis"] is True


def test_cada_um_ve_so_o_que_e_seu(client, gente_com_coisas):
    """O contador não é do sistema — é de quem está lendo a tela."""
    outra = f.pessoa("outra")
    f.lotar(outra)
    client.force_login(outra)

    contexto = client.get(reverse("workspace:servicos")).context

    assert contexto["nao_lidas"] == 0
    assert contexto["abertas"] == 0
    assert contexto["administra_papeis"] is False


def test_a_home_cumprimenta_quem_entrou_pelo_nome(client, gente_com_coisas):
    """`autenticado` estava fixo em `False` na view, então a home dizia
    "Bem-vindo ao Workspace" para todo mundo — a saudação por nome existia no
    template e nunca acontecia."""
    client.force_login(gente_com_coisas)

    pagina = corpo(client, "workspace:home")

    assert gente_com_coisas.get_short_name() in pagina


def test_a_home_do_anonimo_nao_traz_nome_nenhum(client, gente_com_coisas):
    pagina = corpo(client, "workspace:home")

    assert gente_com_coisas.get_short_name() not in pagina
    assert "Bem-vindo ao Workspace" in pagina
