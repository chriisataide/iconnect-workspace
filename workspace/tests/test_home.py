"""Home do Workspace — pública, com um único acesso ao iConnect."""

from __future__ import annotations

import re

import pytest
from django.test import Client
from django.urls import resolve, reverse


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
    links = re.findall(r'href="%s"' % re.escape(reverse("login")), corpo)
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
    assert iconnect.destino == reverse("login")


# ── Grade de aplicativos ─────────────────────────────────────────


@pytest.mark.django_db
def test_os_dez_destinos_do_diagrama_aparecem(client):
    esperados = {
        "iconnect", "helpdesk", "rh", "financeiro", "operacoes",
        "logistica", "redes", "compras", "universidade", "documentacao",
    }
    apps = client.get(reverse("workspace:home")).context["apps"]
    assert {a.chave for a in apps} == esperados


@pytest.mark.django_db
def test_sistema_inexistente_aparece_como_em_breve(client):
    """Não esconder o que não existe — o Workspace comunica o roadmap."""
    resposta = client.get(reverse("workspace:home"))
    # `documentacao` e não `rh`: o RH passou a ter página quando os tiles
    # viraram destinos reais. Documentação segue sem nada a mostrar — não se
    # "pede" um POP —, e é o caso honesto de roadmap visível.
    doc = next(a for a in resposta.context["apps"] if a.chave == "documentacao")

    assert not doc.disponivel
    assert doc.destino == ""
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
        username="cataide", password="x", first_name="Christopher", last_name="Ataide"
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
def test_nome_cai_para_username_sem_nome_completo(client, django_user_model):
    usuario = django_user_model.objects.create_user(username="semnome", password="x")
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
