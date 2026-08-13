"""Home do Workspace — pública, com um único acesso ao iConnect."""

from __future__ import annotations

import re

import pytest
from django.test import Client
from django.urls import resolve, reverse
from django.conf import settings


@pytest.mark.django_db
def test_home_responde_200_para_anonimo():
    """O requisito central: o Workspace NÃO exige login."""
    assert Client().get(reverse("workspace:home")).status_code == 200


@pytest.mark.django_db
def test_home_nao_redireciona_para_login(client):
    resposta = client.get(reverse("workspace:home"))
    assert resposta.status_code != 302, "o Workspace virou página autenticada — não é o desenho"


@pytest.mark.django_db
def test_home_responde_200_para_autenticado(client, user):
    client.force_login(user)
    assert client.get(reverse("workspace:home")).status_code == 200


def test_rota_montada_sob_workspace():
    assert reverse("workspace:home") == "/workspace/"
    assert resolve("/workspace/").view_name == "workspace:home"


# ── Um único acesso ao iConnect ──────────────────────────────────


@pytest.mark.django_db
def test_existe_exatamente_um_link_para_o_login(client):
    """Antes havia três (topbar, tile, faixa). Três caminhos para o mesmo
    destino fazem o usuário parar para decidir se são a mesma coisa."""
    corpo = client.get(reverse("workspace:home")).content.decode()
    links = re.findall(
        r'href="%s"' % re.escape(settings.ICONNECT_URL), corpo
    )
    assert len(links) == 1, f"esperado 1 acesso ao iConnect, achei {len(links)}"


@pytest.mark.django_db
def test_topbar_nao_tem_botao_de_login(client):
    corpo = client.get(reverse("workspace:home")).content.decode()
    assert "Entrar no iConnect" not in corpo


@pytest.mark.django_db
def test_tile_do_iconnect_e_o_acesso(client):
    """O elo do diagrama: Workspace → iConnect → login do sistema principal."""
    resposta = client.get(reverse("workspace:home"))
    iconnect = next(a for a in resposta.context["apps"] if a.chave == "iconnect")

    assert iconnect.disponivel
    # URL ABSOLUTA e de configuração: o tile sai desta aplicação. Era
    # `reverse("login")` enquanto os dois produtos moravam no mesmo projeto.
    assert iconnect.destino == settings.ICONNECT_URL
    assert iconnect.destino.startswith("http"), (
        "o acesso ao iConnect tem de sair do Workspace; caminho relativo cairia "
        "no login do próprio Workspace, que é outro cadastro"
    )


# ── Grade de aplicativos ─────────────────────────────────────────


@pytest.mark.django_db
def test_todo_modulo_registrado_tem_tile(client):
    """DERIVADO de `MODULOS`, não uma lista fixa.

    A versão anterior fixava as dez chaves do diagrama original, e quebrou duas
    vezes: quando Documentação ganhou tela e quando Reservas e Correspondências
    nasceram. Teste que precisa ser editado a cada módulo novo não protege nada —
    ele só ensina a atualizar o número.
    """
    from workspace.modulos import MODULOS

    apps = client.get(reverse("workspace:home")).context["apps"]
    chaves = {a.chave for a in apps}

    assert {m.chave for m in MODULOS} <= chaves, "módulo sem tile na home"
    # Os dois destinos que NÃO são módulo: a Platform e o HelpDesk dela.
    assert {"iconnect", "helpdesk"} <= chaves


@pytest.mark.django_db
def test_sistema_inexistente_aparece_como_em_breve(client):
    """Não esconder o que não existe — o Workspace comunica o roadmap."""
    resposta = client.get(reverse("workspace:home"))
    # `helpdesk` é o único "em breve" permanente, por desenho: chamado abre no
    # iConnect Platform, e uma segunda fila aqui seria duas verdades sobre o
    # mesmo chamado. RH e Documentação já ocuparam este lugar e ganharam página
    # — exemplo que muda a cada onda não serve de exemplo.
    helpdesk = next(a for a in resposta.context["apps"] if a.chave == "helpdesk")

    assert not helpdesk.disponivel
    assert helpdesk.destino == ""
    assert "Em breve" in resposta.content.decode()


@pytest.mark.django_db
def test_tile_de_modulo_pronto_leva_a_pagina(client):
    resposta = client.get(reverse("workspace:home"))
    rh = next(a for a in resposta.context["apps"] if a.chave == "rh")

    assert rh.disponivel
    assert rh.destino == reverse("workspace:modulo", args=("rh",))


# ── Personalização progressiva ───────────────────────────────────


@pytest.mark.django_db
def test_autenticado_e_cumprimentado_pelo_primeiro_nome(client, django_user_model):
    usuario = django_user_model.objects.create_user(
        "cataide@icodev.com.br", password="x", nome="Christopher Ataide"
    )
    client.force_login(usuario)
    resposta = client.get(reverse("workspace:home"))

    assert resposta.context["nome"] == "Christopher"
    assert "Olá, Christopher." in resposta.content.decode()


@pytest.mark.django_db
def test_anonimo_ve_saudacao_neutra(client):
    corpo = client.get(reverse("workspace:home")).content.decode()
    assert "Bem-vindo ao Workspace." in corpo


@pytest.mark.django_db
def test_nome_cai_para_a_parte_local_do_email_sem_nome(client, django_user_model):
    """Sem nome, cumprimenta pela parte local — não pelo e-mail inteiro.

    "Olá, semnome@icodev.com.br." é pior que não cumprimentar. Conta criada pelo
    SSO sempre traz `displayName`; a que cai aqui é conta de serviço ou
    importação incompleta.
    """
    usuario = django_user_model.objects.create_user(
        "semnome@icodev.com.br", password="x"
    )
    client.force_login(usuario)
    assert client.get(reverse("workspace:home")).context["nome"] == "semnome"


# ── Marca ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_pagina_usa_a_marca_icodev(client):
    corpo = client.get(reverse("workspace:home")).content.decode()
    assert "icodev-wordmark.png" in corpo
    assert "favicon.ico" in corpo
    assert "icodev-apple-touch.png" in corpo


@pytest.mark.django_db
def test_shell_nao_herda_material_dashboard(client):
    """Decisão A-02: o shell do Workspace não carrega a casca antiga."""
    corpo = client.get(reverse("workspace:home")).content.decode().lower()
    for marcador in ("material-dashboard", "bootstrap", "argon"):
        assert marcador not in corpo, f"casca antiga vazou para o Workspace: {marcador}"


@pytest.mark.django_db
def test_pagina_carrega_tokens_e_script(client):
    corpo = client.get(reverse("workspace:home")).content.decode()
    assert "workspace/src/tokens.css" in corpo
    assert "workspace/src/workspace.css" in corpo
    assert "workspace/js/workspace.js" in corpo


@pytest.mark.django_db
def test_nenhum_script_inline(client):
    """A CSP de produção não tem `unsafe-inline`. Um `<script>` sem src aqui
    passa em dev e quebra calado em produção."""
    corpo = client.get(reverse("workspace:home")).content.decode()
    inline = re.findall(r"<script(?![^>]*\ssrc=)[^>]*>", corpo)
    assert not inline, f"script inline encontrado: {inline}"
