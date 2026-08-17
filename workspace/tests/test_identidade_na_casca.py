"""WKS — quem está logado, e a porta de saída.

Dois buracos que conviviam:

1. **Não dava para sair.** A rota `/sair/` existia desde o começo e nenhuma tela
   apontava para ela. Num produto que muda de comportamento conforme quem está
   dentro — a fila é de quem atende, a bandeja é de quem aprova —, sair é
   operação normal, não caso de exceção.
2. **Não dava para saber quem se é.** O login cai em `/meu-dia/`, que abria com
   "Meu dia" e uma contagem, sem dizer para quem. Trocar de perfil e não
   perceber é o caminho para assinar um pedido achando que se é outra pessoa.

E a armadilha que estes testes guardam de verdade: o hub é **aberto**, e
`pessoa_da_requisicao()` devolve uma pessoa de referência para o visitante
anônimo. Usar aquela função no canto da tela escreveria o nome de um colega para
quem nunca entrou.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f

pytestmark = pytest.mark.django_db


@pytest.fixture
def ana():
    pessoa = f.pessoa("ana")
    f.lotar(
        pessoa,
        cargo="Analista de Suporte",
        dep=f.departamento("OPS", "Operações"),
        uni=f.unidade("MTZ", "Matriz"),
    )
    return pessoa


def corpo(client, rota="workspace:home"):
    return client.get(reverse(rota)).content.decode()


# ── A porta de saída ────────────────────────────────────────────────


def test_quem_entrou_tem_por_onde_sair(client, ana):
    client.force_login(ana)

    assert reverse("sair") in corpo(client)


def test_o_botao_de_sair_esta_em_toda_tela(client, ana):
    """Ele mora na casca. Depender de cada template lembrar de incluí-lo é como
    o sino já sumiu de uma tela nova uma vez."""
    client.force_login(ana)

    for rota in ("workspace:home", "workspace:servicos", "workspace:meu_dia"):
        assert reverse("sair") in corpo(client, rota), f"faltou em {rota}"


def test_sair_de_verdade_encerra_a_sessao(client, ana):
    client.force_login(ana)

    client.post(reverse("sair"))

    assert "_auth_user_id" not in client.session


def test_sair_e_POST_e_nao_link(client, ana):
    """`LogoutView` recusa GET desde o Django 4.1, e está certo em recusar: link
    que desloga permite a um site de fora tirar você daqui com uma imagem
    escondida."""
    client.force_login(ana)

    client.get(reverse("sair"))

    assert "_auth_user_id" in client.session, "GET não pode deslogar"


def test_quem_nao_entrou_ve_ENTRAR_e_nao_SAIR(client):
    """"Sair" para quem nunca entrou é um botão que não faz nada."""
    pagina = corpo(client)

    assert reverse("entrar") in pagina
    assert reverse("sair") not in pagina


# ── Quem eu sou ─────────────────────────────────────────────────────


def test_o_nome_aparece_na_topbar(client, ana):
    client.force_login(ana)

    assert ana.get_short_name() in corpo(client)


def test_a_area_aparece_junto_do_nome(client, ana):
    """É o que responde "entrei como quem?" sem abrir outra tela."""
    client.force_login(ana)
    lotacao = ana.lotacao

    assert lotacao.departamento.nome in corpo(client)


def test_o_visitante_anonimo_nao_ve_o_nome_de_ninguem(client, ana):
    """A ARMADILHA desta suíte.

    O hub é aberto, e `pessoa_da_requisicao()` devolve uma pessoa de referência
    para o anônimo — as telas precisam de alguém para calcular alcance. Usar
    aquela função aqui escreveria o nome de um colega no canto da tela de quem
    nunca entrou.
    """
    pagina = corpo(client)

    assert ana.get_short_name() not in pagina


def test_a_saudacao_esta_onde_o_login_cai(client, ana, settings):
    """`LOGIN_REDIRECT_URL` aponta para o Meu dia, e era lá que não se sabia
    quem tinha entrado."""
    assert settings.LOGIN_REDIRECT_URL == reverse("workspace:meu_dia")

    client.force_login(ana)
    pagina = corpo(client, "workspace:meu_dia")

    assert "Bem-vindo" in pagina
    assert ana.get_short_name() in pagina


def test_a_home_cumprimenta_pelo_nome(client, ana):
    client.force_login(ana)

    assert "Bem-vindo" in corpo(client)


def test_o_meu_dia_de_quem_nao_entrou_nao_cumprimenta_ninguem(client):
    """`/meu-dia/` exige login, então o anônimo é mandado para a porta — e não
    para uma tela que diz "bem-vindo" a ninguém."""
    resposta = client.get(reverse("workspace:meu_dia"))

    assert resposta.status_code == 302
    assert reverse("entrar") in resposta.url


def test_sem_lotacao_a_tela_nao_mostra_cracha_vazio(client):
    """Traço solto parece defeito."""
    sem_lotacao = f.pessoa("avulsa")
    client.force_login(sem_lotacao)

    pagina = corpo(client)

    assert "au-hero-cracha" not in pagina
    assert sem_lotacao.get_short_name() in pagina, "o nome continua"
