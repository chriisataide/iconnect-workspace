"""O posicionamento, verificado onde ele é visível.

Decidido em 12/08/2026: **são dois produtos.** O iConnect Workspace organiza a
vida corporativa da empresa; o iConnect Platform organiza a operação de
atendimento aos clientes.

Posicionamento não é slide — ou está na ordem das faixas e no tratamento visual
dos tiles, ou não existe. Antes desta data a home abria por "Aplicativos" com o
iConnect como tile herói: a primeira coisa que o colaborador via era a lista de
sistemas, e o próprio trabalho vinha depois. Isso é um app launcher.

Estes testes existem porque a regressão é silenciosa: alguém acrescenta uma
faixa, ela cai no lugar errado, e o produto volta a ser launcher sem que nenhuma
tela quebre.
"""

from __future__ import annotations

import re

import pytest
from django.urls import reverse

from workspace.launcher import catalogo_semente

pytestmark = pytest.mark.django_db


# ── A ordem das faixas ──────────────────────────────────────────────


def _posicoes(corpo: str) -> dict[str, int]:
    """Onde cada faixa começa no HTML."""
    faixas = ("Meu dia", "Minha empresa", "Aplicativos")
    return {
        faixa: corpo.index(f'class="au-secao-titulo">{faixa}')
        for faixa in faixas
        if f'class="au-secao-titulo">{faixa}' in corpo
    }


def test_meu_dia_vem_antes_dos_aplicativos(client):
    """Primeiro o usuário, depois os sistemas."""
    corpo = client.get(reverse("workspace:home")).content.decode()
    pos = _posicoes(corpo)

    assert set(pos) == {"Meu dia", "Minha empresa", "Aplicativos"}, (
        f"faixa faltando ou renomeada: {sorted(pos)}"
    )
    assert pos["Meu dia"] < pos["Minha empresa"] < pos["Aplicativos"], (
        "a home voltou a abrir por sistemas — é o desenho de app launcher"
    )


def test_aplicativos_e_a_ultima_faixa(client):
    """Abrir outro sistema é o que a pessoa faz quando o Workspace não
    resolveu, não o objetivo dela ao entrar."""
    corpo = client.get(reverse("workspace:home")).content.decode()
    titulos = re.findall(r'class="au-secao-titulo">([^<]+)', corpo)

    assert titulos[-1] == "Aplicativos"


# ── O iConnect é um tile entre outros ───────────────────────────────


def test_iconnect_nao_tem_destaque():
    """Sem borda de marca, sem primeira posição.

    `destaque` pinta o tile com a cor da marca e o põe em evidência. Usá-lo no
    iConnect dizia que o Workspace existe para levar até lá.
    """
    iconnect = next(s for s in catalogo_semente() if s.chave == "iconnect")

    assert not iconnect.destaque, "o iConnect voltou a ser o tile herói da home"


def test_iconnect_se_chama_platform():
    iconnect = next(s for s in catalogo_semente() if s.chave == "iconnect")

    assert iconnect.nome == "iConnect Platform"
    assert "principal" not in iconnect.descricao.lower(), (
        "'sistema principal' descreve a relação antiga — são dois produtos"
    )


def test_nenhum_tile_de_aplicativo_tem_destaque():
    """A faixa inteira é plana. Um tile em destaque entre dez cria hierarquia
    que a nova posição não sustenta."""
    com_destaque = [s.chave for s in catalogo_semente() if s.destaque]

    assert not com_destaque, f"tiles em destaque: {com_destaque}"


def test_ordem_coloca_a_platform_no_fim():
    """A Platform é um destino entre outros, e fica no fim da faixa.

    Eram duas entradas — `iconnect` e `helpdesk`. O tile do HelpDesk saiu no
    §38: ele levava para fora e não fazia mais nada, enquanto
    `/workspace/chamados/` direciona, integra e mostra status e histórico.
    """
    ordens = {s.chave: s.ordem for s in catalogo_semente()}
    maior_modulo = max(v for k, v in ordens.items() if k != "iconnect")

    assert ordens["iconnect"] > maior_modulo


# ── O nome do produto ───────────────────────────────────────────────


def test_a_casca_diz_workspace(client):
    corpo = client.get(reverse("workspace:home")).content.decode()

    assert "iConnect Workspace" in corpo
    assert 'class="au-brand-produto">Workspace<' in corpo


def test_nenhuma_tela_ainda_diz_portal(client):
    """"Portal" é conceito morto. Sobra dele numa tela é dívida visível ao
    usuário — e num produto que acabou de ser renomeado, é o tipo de detalhe
    que faz a mudança parecer inacabada."""
    rotas = [
        reverse("workspace:home"),
        reverse("workspace:modulo", args=("rh",)),
    ]
    for rota in rotas:
        corpo = client.get(rota).content.decode()
        assert "Portal" not in corpo, f"{rota} ainda diz Portal"


def test_titulo_da_aba_tem_o_produto_como_sufixo(client):
    corpo = client.get(reverse("workspace:home")).content.decode()

    assert "<title>Início · iConnect Workspace</title>" in corpo
