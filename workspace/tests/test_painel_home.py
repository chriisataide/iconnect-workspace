"""§50 e §51 — os cards contextuais da home, e o "perfil" que não é preferência.

## O que a auditoria encontrou

A home era a **única tela do produto sem o trilho**. Todos os contadores que o
Workspace já sabia calcular — pedidos esperando decisão, fila da área,
equipamento a confirmar, habilitação vencendo, documento de veículo estourado —
moravam no trilho, e o trilho não aparece na home.

A tela em que a pessoa cai ao entrar era a que menos sabia sobre ela: um card
condicional e o resto igual para o estagiário e para o diretor.

## O que estes testes guardam

1. **Nenhum card com número nasce vazio** (ADR-012). Card sempre visível e
   sempre zerado ensina a pessoa a ignorar a faixa inteira.
2. **A ordem é a mensagem.** Primeiro o que trava outra pessoa. "3 avisos não
   lidos" acima de "7 esperando sua decisão" é a inversão exata do que importa.
3. **Os cards não custam consulta.** A view pede os contadores, o processador de
   contexto reaproveita — e `cards()` é função pura sobre o resultado.
4. **§51: perfil é papel, não preferência.** Não há tela de configuração; a home
   se corrige sozinha quando o R.H. concede ou revoga.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.services import painel

pytestmark = pytest.mark.django_db


def chaves(cards) -> list[str]:
    return [c.chave for c in cards]


# ── A função pura ───────────────────────────────────────────────────


def test_cards_nao_toca_no_banco(django_assert_num_queries):
    """É o que permite a home mostrar sete cards sem custar uma consulta a mais
    do que a home que mostrava três."""
    with django_assert_num_queries(0):
        painel.cards({"pendentes_aprovacao": 3, "na_fila": 2, "abertas": 1}, 19)


def test_nenhum_card_com_numero_nasce_vazio():
    """Card sempre visível e sempre zerado ensina a pessoa a ignorar a faixa —
    e depois a ignorar o card que finalmente tem algo."""
    cards = painel.cards(dict(painel.SEM_SESSAO))

    assert chaves(cards) == ["meu_dia", "minhas", "servicos"]
    assert all(c.fixo for c in cards)


def test_o_que_trava_outra_pessoa_vem_primeiro():
    """"3 avisos não lidos" acima de "7 esperando sua decisão" é a inversão
    exata do que importa."""
    cards = painel.cards({"nao_lidas": 30, "pendentes_aprovacao": 1})

    assert chaves(cards)[0] == "aprovacoes"


def test_entre_urgentes_ganha_o_maior_numero():
    cards = painel.cards({"pendentes_aprovacao": 2, "na_fila": 9})

    assert chaves(cards)[:2] == ["fila", "aprovacoes"]


def test_empate_mantem_a_ordem_pensada():
    """A ordenação é estável, então o empate cai na ordem da tabela — que é a
    ordem pensada, e não a ordem do acaso."""
    cards = painel.cards({"pendentes_aprovacao": 3, "na_fila": 3})

    assert chaves(cards)[:2] == ["aprovacoes", "fila"]


def test_urgente_vence_numero_maior_nao_urgente():
    cards = painel.cards({"pendentes_aprovacao": 1, "nao_lidas": 40})

    ordem = chaves(cards)
    assert ordem.index("aprovacoes") < ordem.index("notificacoes")


def test_a_navegacao_fica_por_ultimo():
    cards = painel.cards({"pendentes_aprovacao": 1})

    assert chaves(cards)[-3:] == ["meu_dia", "minhas", "servicos"]


def test_o_card_de_rascunho_abre_a_aba_de_rascunhos():
    """Mandar para "Minhas solicitações" faria a pessoa procurar, numa lista de
    tudo, o que o card acabou de dizer que existe."""
    card = next(c for c in painel.cards({"rascunhos": 2}) if c.chave == "rascunhos")

    assert card.destino.endswith("?situacao=rascunho")


def test_o_total_do_catalogo_entra_na_descricao():
    """"19 serviços" convence a clicar; "peça o que precisa" não."""
    card = next(c for c in painel.cards({}, 19) if c.chave == "servicos")

    assert "19 serviços" in card.descricao


def test_sem_catalogo_a_descricao_nao_mente():
    card = next(c for c in painel.cards({}, 0) if c.chave == "servicos")

    assert "0" not in card.descricao


# ── §51 — perfil é papel ────────────────────────────────────────────


def test_estoque_e_frota_aparecem_pelo_papel_e_sem_numero():
    """Não são pendência: são a área de trabalho de quem tem o papel. Um
    contador de "quantos materiais existem" não pede ação nenhuma, e virar selo
    vermelho seria alarme falso."""
    cards = painel.cards({"ve_estoque": True, "ve_frota": True})

    estoque = next(c for c in cards if c.chave == "estoque")
    assert estoque.fixo
    assert estoque.contagem == 0
    assert "frota" in chaves(cards)


def test_com_prazo_estourando_a_frota_aparece_uma_vez_so():
    """Dois cards para a mesma tela na mesma faixa fazem a pessoa duvidar se são
    a mesma coisa."""
    cards = painel.cards({"ve_frota": True, "prazos_de_veiculo": 2})

    assert chaves(cards).count("frota") == 1
    assert next(c for c in cards if c.chave == "frota").urgente


def test_quem_nao_tem_papel_nao_ve_a_porta():
    cards = painel.cards({"ve_estoque": False, "ve_frota": False, "ve_indicadores": False})

    assert "estoque" not in chaves(cards)
    assert "frota" not in chaves(cards)
    assert "indicadores" not in chaves(cards)


# ── Os contadores ───────────────────────────────────────────────────


def test_anonimo_nao_recebe_contador_de_ninguem(rf):
    """O hub é aberto e devolve uma pessoa de REFERÊNCIA para calcular alcance —
    usá-la para contar mostraria os números dela a quem nunca entrou."""
    from django.contrib.auth.models import AnonymousUser

    requisicao = rf.get("/workspace/")
    requisicao.user = AnonymousUser()

    assert painel.contadores(requisicao) == painel.SEM_SESSAO


def test_anonimo_nao_toca_no_banco(rf, django_assert_num_queries):
    from django.contrib.auth.models import AnonymousUser

    requisicao = rf.get("/workspace/")
    requisicao.user = AnonymousUser()

    with django_assert_num_queries(0):
        painel.contadores(requisicao)


def test_o_calculo_acontece_uma_vez_por_requisicao(rf, django_assert_num_queries):
    """A view da home pede primeiro; o processador de contexto encontra o
    resultado memoizado. Sem isso, dar contexto à home custaria oito consultas a
    mais na tela mais visitada do produto."""
    ana = f.pessoa("ana")
    f.lotar(ana)
    requisicao = rf.get("/workspace/")
    requisicao.user = ana

    painel.contadores(requisicao)
    with django_assert_num_queries(0):
        painel.contadores(requisicao)


def test_o_rail_reaproveita_o_que_a_view_calculou(rf, django_assert_num_queries):
    from workspace.context import rail

    ana = f.pessoa("ana")
    f.lotar(ana)
    requisicao = rf.get("/workspace/")
    requisicao.user = ana

    painel.contadores(requisicao)
    with django_assert_num_queries(0):
        rail(requisicao)


def test_o_rail_fora_do_workspace_nao_faz_nada(rf):
    """ADR-009 — curto-circuito fora do Workspace."""
    from workspace.context import rail

    requisicao = rf.get("/admin/")
    requisicao.user = f.pessoa("ana")

    assert rail(requisicao) == {}


# ── A home de verdade ───────────────────────────────────────────────


@pytest.fixture
def cenario():
    unidade = f.unidade()
    ana, almox = f.pessoa("ana"), f.pessoa("almoxarife")
    f.lotar(ana, uni=unidade)
    f.lotar(almox, uni=unidade)
    f.atribuir(
        almox,
        f.papel(
            "sup",
            ["log.frota.ler.global", "log.frota.operar.global", "log.movimentar.global"],
            escopo="global",
        ),
    )
    return {"unidade": unidade, "ana": ana, "almox": almox}


def test_a_home_do_colaborador_comum_e_so_navegacao(cenario, client):
    client.force_login(cenario["ana"])

    cards = client.get(reverse("workspace:home")).context["cards"]

    assert chaves(cards) == ["meu_dia", "minhas", "servicos"]


def test_a_home_de_quem_tem_papel_ganha_as_portas_do_papel(cenario, client):
    """§51 inteiro: a personalização vem do papel, e não de uma tela de
    preferências que quase ninguém abre."""
    client.force_login(cenario["almox"])

    cards = chaves(client.get(reverse("workspace:home")).context["cards"])

    assert "estoque" in cards
    assert "frota" in cards


def test_a_home_do_anonimo_nao_mostra_card_pessoal(client):
    cards = client.get(reverse("workspace:home")).context["cards"]

    assert chaves(cards) == ["meu_dia", "minhas", "servicos"]


def test_documento_de_veiculo_vencido_vira_card_urgente(cenario, client):
    from workspace.models.frota import Veiculo

    Veiculo.objects.create(
        placa="RTA1B23",
        modelo="Ducato",
        unidade=cenario["unidade"],
        licenciamento_ate=timezone.localdate() - timedelta(days=2),
    )
    client.force_login(cenario["almox"])

    cards = client.get(reverse("workspace:home")).context["cards"]
    frota = next(c for c in cards if c.chave == "frota")

    assert frota.urgente
    assert frota.contagem == 1
    assert chaves(cards)[0] == "frota"


def test_equipamento_a_confirmar_vira_card(cenario, client):
    from workspace.models.estoque import Material, TipoMovimento
    from workspace.services import custodia as cst
    from workspace.services import estoque as est

    f.atribuir(
        cenario["almox"],
        f.papel("cust", ["log.custodia.atribuir.global"], escopo="global"),
    )
    material = Material.objects.create(codigo="notebook", nome="Notebook")
    est.movimentar(material, cenario["unidade"], TipoMovimento.ENTRADA, 3)
    cst.entregar(material, cenario["ana"], cenario["almox"])

    client.force_login(cenario["ana"])
    cards = client.get(reverse("workspace:home")).context["cards"]

    assert "custodia" in chaves(cards)


def test_a_home_desenha_o_card_com_o_numero(cenario, client):
    from workspace.models.frota import Veiculo

    Veiculo.objects.create(
        placa="RTA1B23",
        modelo="Ducato",
        licenciamento_ate=timezone.localdate() - timedelta(days=2),
    )
    client.force_login(cenario["almox"])

    corpo = client.get(reverse("workspace:home")).content.decode()

    assert "Documento de veículo" in corpo
    assert reverse("workspace:frota") in corpo
