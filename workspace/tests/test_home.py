"""Home do Portal — pública.

O Portal é a porta de entrada da empresa: acessível sem login. O tile do
iConnect é que leva ao login do sistema principal.
"""

from __future__ import annotations

import pytest
from django.urls import resolve, reverse


@pytest.mark.django_db
def test_home_responde_200_para_anonimo():
    """O requisito central: o Portal NÃO exige login."""
    from django.test import Client

    resposta = Client().get(reverse("workspace:home"))
    assert resposta.status_code == 200


@pytest.mark.django_db
def test_home_nao_redireciona_para_login(client):
    resposta = client.get(reverse("workspace:home"))
    assert resposta.status_code != 302, "o Portal virou página autenticada — não é o desenho"


@pytest.mark.django_db
def test_home_responde_200_para_autenticado(client, user):
    client.force_login(user)
    assert client.get(reverse("workspace:home")).status_code == 200


def test_rota_montada_sob_workspace():
    assert reverse("workspace:home") == "/workspace/"
    assert resolve("/workspace/").view_name == "workspace:home"


@pytest.mark.django_db
def test_anonimo_ve_convite_para_entrar(client):
    corpo = client.get(reverse("workspace:home")).content.decode()
    assert "Entrar no iConnect" in corpo


@pytest.mark.django_db
def test_autenticado_e_cumprimentado_pelo_primeiro_nome(client, django_user_model):
    usuario = django_user_model.objects.create_user(
        username="cataide", password="x", first_name="Christopher", last_name="Ataide"
    )
    client.force_login(usuario)
    resposta = client.get(reverse("workspace:home"))

    assert resposta.context["nome"] == "Christopher"
    corpo = resposta.content.decode()
    assert "Olá, Christopher." in corpo
    assert "Entrar no iConnect" not in corpo, "usuário logado não deve ver convite de login"


@pytest.mark.django_db
def test_nome_cai_para_username_sem_nome_completo(client, django_user_model):
    usuario = django_user_model.objects.create_user(username="semnome", password="x")
    client.force_login(usuario)
    assert client.get(reverse("workspace:home")).context["nome"] == "semnome"


@pytest.mark.django_db
def test_tile_do_iconnect_aponta_para_o_login(client):
    """O elo do diagrama: Portal → iConnect → login do sistema principal."""
    resposta = client.get(reverse("workspace:home"))
    iconnect = next(a for a in resposta.context["apps"] if a.chave == "iconnect")

    assert iconnect.disponivel
    assert iconnect.url_direta == reverse("login")
    assert f'href="{reverse("login")}"' in resposta.content.decode()


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
    """Não esconder o que não existe — o Portal comunica o roadmap."""
    resposta = client.get(reverse("workspace:home"))
    rh = next(a for a in resposta.context["apps"] if a.chave == "rh")

    assert not rh.disponivel
    assert "Em breve" in resposta.content.decode()


@pytest.mark.django_db
def test_shell_nao_herda_material_dashboard(client):
    """Decisão A-02: o shell do Portal não carrega a casca antiga."""
    corpo = client.get(reverse("workspace:home")).content.decode().lower()
    for marcador in ("material-dashboard", "bootstrap", "argon"):
        assert marcador not in corpo, f"casca antiga vazou para o Portal: {marcador}"


@pytest.mark.django_db
def test_pagina_carrega_os_tokens_do_aurora(client):
    corpo = client.get(reverse("workspace:home")).content.decode()
    assert "workspace/src/tokens.css" in corpo
    assert "workspace/src/portal.css" in corpo
