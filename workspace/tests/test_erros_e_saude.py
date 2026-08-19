"""§53 — as quatro telas de erro, e a sonda do balanceador.

Nada disto existia. Em desenvolvimento o produto entregava a tela de depuração
do Django; em produção, a página cinza padrão — sem marca, sem saída e, no caso
do 403, sem dizer por que o acesso foi negado, que é justamente a informação de
que a pessoa precisa para resolver.

O 403 é o que mais importa, e não é hipótese: a fila de atendimento, a bandeja
de aprovação e o estoque levantam `PermissionDenied` de propósito, em vez de
mostrarem uma lista vazia. "Sua fila está vazia" para quem não atende nada é
mentira, e mentira que faz a pessoa esperar por trabalho que nunca vem.

O que estes testes guardam:

1. **O 500 se desenha sem request e sem banco.** É a propriedade inteira dessa
   tela: a casca lê o banco em cada carregamento, e uma página de erro que
   consulta o banco falha exatamente quando o banco é o problema.
2. **O 404 não imprime o endereço tentado.** Texto de terceiro numa página que
   qualquer um faz o navegador de alguém abrir é o começo do XSS refletido.
3. **A sonda devolve 503 quando o banco não responde** — e não 200 com um JSON
   dizendo "erro", que nenhum balanceador lê.
"""

from __future__ import annotations

import json
from unittest import mock

import pytest
from django.db import DatabaseError
from django.template.loader import get_template
from django.urls import reverse

from identidade.tests import fabricas as f

pytestmark = pytest.mark.django_db


# ── As telas de erro ────────────────────────────────────────────────


def test_404_usa_a_tela_do_produto(client, settings):
    settings.DEBUG = False

    resposta = client.get("/workspace/rota-que-nunca-existiu/")

    assert resposta.status_code == 404
    corpo = resposta.content.decode()
    assert "Esta página não existe." in corpo
    assert "au-tela-erro" in corpo


def test_404_nao_imprime_o_endereco_tentado(client, settings):
    """`request_path` vem do que alguém digitou. O Django escapa — e ainda assim
    o texto de outra pessoa não tem nada que fazer nesta tela."""
    settings.DEBUG = False

    corpo = client.get("/workspace/marca-do-atacante/").content.decode()

    assert "marca-do-atacante" not in corpo


def test_404_oferece_saidas_de_verdade(client, settings):
    """Tela de erro sem saída obriga a pessoa a usar o botão do navegador — e o
    histórico dela, depois de um redirecionamento, não leva onde ela espera."""
    settings.DEBUG = False

    corpo = client.get("/workspace/nao-existe/").content.decode()

    assert reverse("workspace:home") in corpo
    assert reverse("workspace:servicos") in corpo


def test_403_explica_o_caminho_em_vez_de_so_negar(client, settings):
    """A tela que o produto usa de verdade: a fila levanta `PermissionDenied`
    para quem não atende nada."""
    settings.DEBUG = False
    ana = f.pessoa("ana")
    f.lotar(ana)
    client.force_login(ana)

    resposta = client.get(reverse("workspace:fila"))

    assert resposta.status_code == 403
    corpo = resposta.content.decode()
    assert "Isto não é seu." in corpo
    # O que resolve, e não só o que aconteceu: quem concede, e que o papel vale
    # a partir da requisição seguinte.
    assert "R.H." in corpo


def test_403_do_estoque_tambem_e_a_tela_do_produto(client, settings):
    settings.DEBUG = False
    ana = f.pessoa("ana")
    f.lotar(ana)
    client.force_login(ana)

    resposta = client.get(reverse("workspace:estoque"))

    assert resposta.status_code == 403
    assert "au-tela-erro" in resposta.content.decode()


def test_as_telas_de_erro_mantem_a_navegacao(client, settings):
    """400, 403 e 404 acontecem com o sistema saudável, e a coisa mais útil que
    se oferece a quem bateu numa delas é a navegação inteira."""
    settings.DEBUG = False
    ana = f.pessoa("ana")
    f.lotar(ana)
    client.force_login(ana)

    corpo = client.get(reverse("workspace:fila")).content.decode()

    assert "au-topbar" in corpo
    assert "au-rodape" in corpo


def test_400_aparece_quando_o_host_e_recusado(client, settings):
    """A causa real de um 400 aqui: `ALLOWED_HOSTS`. E o handler do Django
    renderiza esta tela SEM request — igual ao 500 —, então ela também tem de se
    desenhar sozinha."""
    settings.DEBUG = False

    resposta = client.get("/workspace/", headers={"host": "atacante.example"})

    assert resposta.status_code == 400
    assert "au-tela-erro" in resposta.content.decode()


def test_400_se_desenha_sem_request_e_sem_banco(django_assert_num_queries):
    """`django.views.defaults.bad_request` também renderiza sem contexto. A
    casca aguenta porque tudo o que ela mostra de pessoal está atrás de
    `{% if eu %}` — o sino e o nome simplesmente não aparecem."""
    with django_assert_num_queries(0):
        corpo = get_template("400.html").render()

    assert "au-topbar" in corpo
    assert "au-sino" not in corpo


def test_400_diz_o_que_fazer_e_nao_so_o_que_houve(client, settings):
    settings.DEBUG = False

    corpo = get_template("400.html").render()

    assert "Recarregue a página" in corpo


# ── O 500, que é outra coisa ────────────────────────────────────────


def test_o_500_se_desenha_sem_request_e_sem_contexto():
    """A propriedade inteira dessa tela.

    `django.views.defaults.server_error` renderiza sem request: os context
    processors não rodam. Se o template dependesse de `eu`, `nao_lidas` ou de
    qualquer coisa que a casca calcula, ele apareceria quebrado — ou não
    apareceria, e o visitante receberia o "A server error occurred." cru.
    """
    corpo = get_template("500.html").render()

    assert "Alguma coisa quebrou do nosso lado" in corpo
    assert "au-tela-erro" in corpo


def test_o_500_nao_toca_no_banco(django_assert_num_queries):
    """Uma página de erro que consulta o banco falha exatamente quando o banco é
    o problema."""
    with django_assert_num_queries(0):
        get_template("500.html").render()


def test_o_500_nao_estende_a_casca():
    """Guarda a decisão contra o refactor bem-intencionado.

    "As telas de erro deviam todas estender a casca" é a mudança óbvia, e ela
    reintroduz o defeito inteiro — a casca lê o banco.
    """
    fonte = (
        __import__("pathlib")
        .Path("workspace/templates/500.html")
        .read_text(encoding="utf-8")
    )

    assert "extends" not in fonte


def test_o_500_nao_resolve_nome_de_rota():
    """Resolver nome de rota carrega o URLconf inteiro, e erro de importação em
    um módulo de views é uma das causas plausíveis de um 500 — derrubaria também
    a página que existe para contar sobre ele."""
    fonte = (
        __import__("pathlib")
        .Path("workspace/templates/500.html")
        .read_text(encoding="utf-8")
    )

    assert "{% url" not in fonte


def test_o_500_avisa_que_nada_ficou_pela_metade():
    """Sem isso a pessoa reenvia o formulário por medo — e o reenvio é o que de
    fato produz o pedido duplicado."""
    corpo = get_template("500.html").render()

    assert "pela metade" in corpo


# ── A sonda ─────────────────────────────────────────────────────────


def test_a_sonda_responde_ok_com_o_banco_de_pe(client):
    resposta = client.get(reverse("saude"))

    assert resposta.status_code == 200
    assert json.loads(resposta.content) == {"status": "ok", "banco": "ok"}


def test_a_sonda_devolve_503_quando_o_banco_cai(client):
    """503 e não 200 com um JSON dizendo "erro": o balanceador lê o código."""
    with mock.patch(
        "iconnect_workspace.saude._banco_responde", return_value=False
    ):
        resposta = client.get(reverse("saude"))

    assert resposta.status_code == 503
    assert json.loads(resposta.content)["status"] == "indisponivel"


def test_o_erro_de_banco_vira_503_e_nao_500(client):
    """A sonda não pode ser mais uma coisa que quebra quando o banco quebra."""
    from django.db import connections

    with mock.patch.object(
        connections["default"], "cursor", side_effect=DatabaseError("caiu")
    ):
        resposta = client.get(reverse("saude"))

    assert resposta.status_code == 503


def test_a_sonda_nunca_e_guardada_em_cache(client):
    """Health check cacheado responde "ok" durante toda a indisponibilidade, que
    é o único momento em que ele importa."""
    resposta = client.get(reverse("saude"))

    assert resposta["Cache-Control"] == "no-store"


def test_a_sonda_e_anonima(client):
    """Sonda de balanceador não faz login. Por isso ela também não imprime
    versão, host nem nome de banco — tudo o que ela diz é público."""
    corpo = json.loads(client.get(reverse("saude")).content)

    assert set(corpo) == {"status", "banco"}
