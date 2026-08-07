"""Teste de fumaça da rota — ST-002 T5.

Aceite ②: `/workspace/` acessível para usuário autenticado.
"""

from __future__ import annotations

import pytest
from django.urls import resolve, reverse


@pytest.mark.django_db
def test_home_responde_200_para_autenticado(client, user):
    client.force_login(user)
    resposta = client.get(reverse("workspace:home"))
    assert resposta.status_code == 200


@pytest.mark.django_db
def test_home_redireciona_anonimo_para_login(client):
    resposta = client.get(reverse("workspace:home"))
    assert resposta.status_code == 302
    assert "/login" in resposta["Location"]


def test_rota_montada_sob_workspace():
    assert reverse("workspace:home") == "/workspace/"
    assert resolve("/workspace/").view_name == "workspace:home"


@pytest.mark.django_db
def test_shell_nao_herda_material_dashboard(client, user):
    """Decisão A-02: o shell do Workspace não carrega a casca antiga.

    Se alguém trocar `_shell.html` por `{% extends "base.html" %}`, o Bootstrap
    e o Material Dashboard voltam junto — e a decisão de casca isolada morre em
    silêncio, sem ninguém notar até o produto parecer o de sempre.
    """
    client.force_login(user)
    corpo = client.get(reverse("workspace:home")).content.decode()

    for marcador in ("material-dashboard", "bootstrap", "argon"):
        assert marcador not in corpo.lower(), f"casca antiga vazou para o Workspace: {marcador}"


@pytest.mark.django_db
def test_home_usa_o_registro_e_nao_lista_fixa(client, user):
    """Com o registro vazio, a home não inventa aplicação nenhuma."""
    client.force_login(user)
    resposta = client.get(reverse("workspace:home"))
    assert list(resposta.context["providers"]) == []
