"""Sprite de ícones.

Existe por causa de um bug real: os símbolos nasceram como `<g>` sem `viewBox`.
`<use>` então desenhava os paths de 24×24 em 1:1 dentro de um viewport de 18px,
e todo ícone da grade aparecia cortado — sem erro de console, sem teste
falhando, só feio. É invisível para qualquer verificação que não olhe o SVG.
"""

from __future__ import annotations

import re
from pathlib import Path
from xml.etree import ElementTree

import pytest
from django.urls import reverse

from workspace.launcher import catalogo_semente

SPRITE = Path(__file__).resolve().parent.parent / "templates" / "workspace" / "_icones.html"
SVG_NS = "{http://www.w3.org/2000/svg}"


def _sprite_xml() -> ElementTree.Element:
    bruto = SPRITE.read_text(encoding="utf-8")
    # Recorta só o <svg>…</svg>: o resto do arquivo é template Django, e o
    # bloco {% comment %} não é XML válido.
    trecho = re.search(r"<svg\b.*</svg>", bruto, flags=re.S)
    assert trecho, "não achei o bloco <svg> no sprite"
    return ElementTree.fromstring(trecho.group(0))


def _simbolos() -> list[ElementTree.Element]:
    return _sprite_xml().findall(f"{SVG_NS}symbol")


def test_sprite_e_xml_valido():
    assert _simbolos(), "nenhum <symbol> encontrado no sprite"


@pytest.mark.parametrize("simbolo", _simbolos(), ids=lambda s: s.get("id"))
def test_todo_simbolo_tem_viewbox(simbolo):
    """Sem viewBox, `<use>` não escala e o ícone sai cortado."""
    assert simbolo.get("viewBox"), f"{simbolo.get('id')} sem viewBox"


@pytest.mark.parametrize("simbolo", _simbolos(), ids=lambda s: s.get("id"))
def test_todo_simbolo_herda_a_cor_do_texto(simbolo):
    assert simbolo.get("stroke") == "currentColor", (
        f"{simbolo.get('id')} não herda currentColor — não acompanha o tema"
    )


def test_ids_sao_unicos():
    ids = [s.get("id") for s in _simbolos()]
    assert len(ids) == len(set(ids)), f"ids repetidos: {ids}"


def test_todo_icone_do_catalogo_existe_no_sprite():
    """AppSpec com `icone` inexistente renderiza um tile de ícone vazio."""
    disponiveis = {s.get("id") for s in _simbolos()}
    faltando = {
        spec.icone for spec in catalogo_semente() if f"i-{spec.icone}" not in disponiveis
    }
    assert not faltando, f"ícones referenciados que não existem no sprite: {faltando}"


@pytest.mark.django_db
def test_pagina_nao_referencia_icone_inexistente(client):
    corpo = client.get(reverse("workspace:home")).content.decode()
    usados = set(re.findall(r'<use href="#(i-[\w-]+)"', corpo))
    definidos = {s.get("id") for s in _simbolos()}

    assert usados, "a página não referenciou ícone nenhum"
    assert usados <= definidos, f"referências quebradas: {usados - definidos}"
