"""Navegação do Workspace — todo destino tem porta, toda porta tem destino.

Estes testes existem por causa de um bug de arquitetura de informação que
nenhuma suíte pegava: a home tinha dez tiles e nove não levavam a lugar nenhum,
enquanto o catálogo — a única área real — não tinha porta na home. Cada tela
passava no seu teste isoladamente; o que ninguém verificava era o grafo.
"""

from __future__ import annotations

import re

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.conf import settings

from workspace.launcher import catalogo_semente
from workspace.modulos import MODULOS
from workspace.models.catalogo import GrupoCatalogo, ItemCatalogo

pytestmark = pytest.mark.django_db


@pytest.fixture
def pessoa(db):
    return get_user_model().objects.create_user("ana@icodev.com.br", password="x")


def _href(html: str) -> set[str]:
    return set(re.findall(r'href="([^"]+)"', html))


# ── O grafo ─────────────────────────────────────────────────────────


def test_home_leva_a_area_pessoal():
    """A porta que faltava: catálogo e solicitações alcançáveis pela home."""
    from django.test import Client

    corpo = Client().get(reverse("workspace:home")).content.decode()
    links = _href(corpo)

    assert reverse("workspace:servicos") in links
    assert reverse("workspace:minhas_solicitacoes") in links


def test_todo_tile_disponivel_leva_a_pagina_que_responde(client):
    """Tile clicável tem de abrir algo. Tile 'em breve' não é clicável."""
    corpo = client.get(reverse("workspace:home")).content.decode()

    for spec in catalogo_semente():
        if not spec.disponivel:
            continue
        if spec.url_direta:  # iConnect sai do Workspace — não é nossa rota
            continue
        destino = reverse(spec.url_name, args=spec.url_args)
        assert destino in _href(corpo), f"tile {spec.chave} não está na home"
        # 200 (público) ou 302 para o login (área pessoal). O que o tile NÃO
        # pode devolver é 404: Correspondências exige login porque é dado
        # pessoal, e exigir 200 aqui obrigaria a tornar a fila da recepção
        # pública para o teste passar.
        resposta = client.get(destino)
        assert resposta.status_code in (200, 302), f"{destino} não responde"
        if resposta.status_code == 302:
            assert settings.LOGIN_URL in resposta["Location"], (
                f"{destino} redireciona para fora do login"
            )


def test_modulo_disponivel_tem_tile_e_destino():
    """Registro de módulos e launcher não podem divergir.

    `disponivel` e não `tem_catalogo`: desde a onda C um módulo pode ter tela
    PRÓPRIA em vez da vista de catálogo — Documentação é o primeiro caso, porque
    acervo normativo não é fila de pedidos.
    """
    tiles = {s.chave: s for s in catalogo_semente()}

    for modulo in MODULOS:
        spec = tiles.get(modulo.chave)
        assert spec is not None, f"módulo {modulo.chave} sem tile na home"
        assert spec.disponivel is modulo.disponivel


def test_modulo_com_rota_propria_nao_abre_a_pagina_de_catalogo(client):
    """A vista de catálogo é só para quem atende domínio de catálogo."""
    com_rota = [m for m in MODULOS if m.rota]
    assert com_rota, "o teste perde o sentido se nenhum módulo tiver rota própria"

    for modulo in com_rota:
        resposta = client.get(reverse("workspace:modulo", args=(modulo.chave,)))
        assert resposta.status_code == 404, f"{modulo.chave} abriu a vista de catálogo"


def test_modulo_sem_destino_nenhum_nao_abre_pagina(client):
    """Sem catálogo e sem rota própria = "em breve", e 404 na URL."""
    sem_destino = [m for m in MODULOS if not m.disponivel]
    for modulo in sem_destino:
        resposta = client.get(reverse("workspace:modulo", args=(modulo.chave,)))
        assert resposta.status_code == 404


def test_modulo_inexistente_da_404(client):
    assert client.get("/workspace/m/inventado/").status_code == 404


# ── A página de módulo ──────────────────────────────────────────────


@pytest.fixture
def item_rh(db):
    return ItemCatalogo.objects.create(
        chave="ferias",
        nome="Férias",
        descricao_curta="Programe suas férias",
        grupo=GrupoCatalogo.TRABALHO,
        dominio="rh.ferias",
        prazo_prometido_dias=10,
    )


def test_modulo_e_publico(client, item_rh):
    """O Workspace é aberto a quem está na rede — a vitrine não pede senha."""
    resposta = client.get(reverse("workspace:modulo", args=("rh",)))

    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert "Férias" in corpo
    assert settings.LOGIN_URL not in resposta.get("Location", "")


def test_modulo_mostra_so_a_propria_fatia(client, item_rh):
    ItemCatalogo.objects.create(
        chave="reembolso",
        nome="Reembolso",
        grupo=GrupoCatalogo.DINHEIRO,
        dominio="fin.reembolso",
    )

    corpo = client.get(reverse("workspace:modulo", args=("rh",))).content.decode()

    assert "Férias" in corpo
    assert "Reembolso" not in corpo


def test_anonimo_ve_o_item_mas_nao_o_link_de_pedir(client, item_rh):
    """Ver que o serviço existe é o que faz a pessoa parar de mandar e-mail."""
    corpo = client.get(reverse("workspace:modulo", args=("rh",))).content.decode()

    assert "Férias" in corpo
    assert reverse("workspace:pedir", args=("ferias",)) not in _href(corpo)


def test_autenticado_pode_pedir_direto_do_modulo(client, pessoa, item_rh):
    client.force_login(pessoa)

    corpo = client.get(reverse("workspace:modulo", args=("rh",))).content.decode()

    assert reverse("workspace:pedir", args=("ferias",)) in _href(corpo)


def test_modulo_lista_os_pedidos_da_pessoa_naquela_fatia(client, pessoa, item_rh):
    from workspace.models.catalogo import SolicitacaoServico

    outro = ItemCatalogo.objects.create(
        chave="reembolso", nome="Reembolso", grupo=GrupoCatalogo.DINHEIRO,
        dominio="fin.reembolso",
    )
    SolicitacaoServico.objects.create(item=item_rh, solicitante=pessoa)
    SolicitacaoServico.objects.create(item=outro, solicitante=pessoa)

    client.force_login(pessoa)
    corpo = client.get(reverse("workspace:modulo", args=("rh",))).content.decode()

    assert "Seus pedidos neste módulo" in corpo
    assert corpo.count("Reembolso") == 0


def test_pedido_de_outra_pessoa_nao_aparece(client, pessoa, item_rh):
    from workspace.models.catalogo import SolicitacaoServico

    alheio = get_user_model().objects.create_user("bruno@icodev.com.br", password="x")
    SolicitacaoServico.objects.create(item=item_rh, solicitante=alheio)

    client.force_login(pessoa)
    corpo = client.get(reverse("workspace:modulo", args=("rh",))).content.decode()

    assert "Você ainda não pediu nada aqui." in corpo


# ── Módulo sem domínio ──────────────────────────────────────────────
#
# `Q()` vazio NÃO filtra nada: `filter(Q())` devolve a tabela inteira. Sem a
# guarda de `prefixos` vazio, um módulo que ainda não declarou domínio nenhum
# — Documentação, hoje — passaria a exibir o catálogo completo, e cada item
# apareceria em dois lugares dizendo coisas diferentes sobre quem o atende.


def test_vitrine_de_modulo_sem_dominio_e_vazia(item_rh):
    from workspace.services import catalogo as svc

    assert svc.do_modulo([]) == []
    assert svc.do_modulo(["rh."]) == [item_rh], "com prefixo, filtra de verdade"


def test_meus_pedidos_de_modulo_sem_dominio_e_vazio(pessoa, item_rh):
    from workspace.models.catalogo import SolicitacaoServico
    from workspace.services import catalogo as svc

    SolicitacaoServico.objects.create(item=item_rh, solicitante=pessoa)

    assert not svc.minhas_do_modulo(pessoa, []).exists()
    assert svc.minhas_do_modulo(pessoa, ["rh."]).count() == 1


# ── Regressões de renderização ──────────────────────────────────────


def test_modulo_sem_estilo_inline(client, item_rh):
    """A CSP de produção traz nonce em `style-src`, o que faz o navegador
    ignorar `unsafe-inline` — e nonce não se aplica a atributo `style`."""
    corpo = client.get(reverse("workspace:modulo", args=("rh",))).content.decode()

    assert "style=" not in corpo


def test_icone_do_modulo_existe_no_sprite(client, item_rh):
    """`<use href="#i-x">` para um símbolo inexistente não desenha nada e não
    dá erro — some em silêncio, que é o pior modo de falhar."""
    from pathlib import Path

    from django.conf import settings

    sprite = Path(settings.BASE_DIR) / "workspace/templates/workspace/_icones.html"
    disponiveis = set(re.findall(r'id="i-([a-z-]+)"', sprite.read_text()))

    for modulo in MODULOS:
        assert modulo.icone in disponiveis, f"{modulo.chave} usa ícone inexistente"
