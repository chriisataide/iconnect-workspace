"""Toda classe `au-*` escrita num template existe no CSS.

Escrito depois de encontrar a tela de identificação renderizando com as caixas
cruas do navegador, no meio de um produto inteiro estilizado. Ela usava
`au-form-entrar`, `au-campo-entrada` e `au-botao` — o vocabulário do projeto
anterior, que nunca existiu neste CSS. Nada quebrava: HTML aceita qualquer
classe, o Django renderiza feliz, e a suíte passava verde.

É a mesma família de defeito do teste de contraste ao lado: **estilo regride em
silêncio**. Não levanta exceção, não vira 500 — só fica feio numa tela que
ninguém abre com frequência. E `/entrar/` é exatamente uma tela dessas: ninguém
chega nela navegando, só ao tentar um ato que exige identidade.

O teste é bobo de propósito. Ele não sabe se o estilo está bonito; sabe se
alguém escreveu um nome de classe que o CSS nunca ouviu falar.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
ESTILOS = RAIZ / "workspace" / "static" / "workspace" / "src"


def _css() -> str:
    return "\n".join(
        arquivo.read_text(encoding="utf-8") for arquivo in ESTILOS.glob("*.css")
    )


def _classes_por_template() -> dict[str, set[str]]:
    """As classes literais de cada template.

    Valor com `{` fica de fora: `au-etiqueta--{{ s.situacao }}` é montado em
    tempo de render, e conferir isso exigiria enumerar os valores possíveis do
    enum — o teste passaria a falhar por um `TextChoices` novo, e não por uma
    classe sem estilo.
    """
    achadas: dict[str, set[str]] = {}
    for template in RAIZ.glob("**/templates/**/*.html"):
        if ".venv" in template.parts:
            continue
        for atributo in re.findall(r'class="([^"]*)"', template.read_text(encoding="utf-8")):
            if "{" in atributo:
                continue
            for classe in atributo.split():
                if classe.startswith("au-"):
                    achadas.setdefault(str(template.relative_to(RAIZ)), set()).add(classe)
    return achadas


def test_nenhuma_classe_de_template_ficou_sem_css():
    css = _css()
    orfas = {
        template: sorted(c for c in classes if f".{c}" not in css)
        for template, classes in _classes_por_template().items()
    }
    orfas = {t: c for t, c in orfas.items() if c}

    assert not orfas, "classes sem nenhuma regra no CSS:\n" + "\n".join(
        f"  {template}: {', '.join(classes)}" for template, classes in sorted(orfas.items())
    )


def test_o_teste_enxerga_os_templates_de_todos_os_apps():
    """Guarda contra o pior defeito possível aqui: um teste que não olha nada
    e passa verde para sempre. `contas/` tem a tela de identificação; se o
    varredor deixar de vê-la, é ela que volta a ficar sem estilo."""
    templates = _classes_por_template()

    assert any(t.startswith("workspace/templates/") for t in templates)
    assert any(t.startswith("contas/templates/") for t in templates)
    assert sum(len(c) for c in templates.values()) > 100


def test_nenhum_comentario_curto_vazou_para_a_pagina():
    """`{# … #}` só é comentário em UMA linha.

    Escrito em duas, o Django não o reconhece e imprime o texto na página. Foi
    o que aconteceu com a explicação do `type="time"`: a frase sobre os
    dois-pontos apareceu dentro do formulário de atestado, entre dois campos,
    e só foi notada porque um teste de fumaça contou os campos de hora e achou
    quatro onde deviam existir dois.

    Comentário de mais de uma linha usa `{% comment %}`.
    """
    vazados: list[str] = []
    for template in RAIZ.glob("**/templates/**/*.html"):
        if ".venv" in template.parts:
            continue
        linhas = template.read_text(encoding="utf-8").splitlines()
        for numero, linha in enumerate(linhas, start=1):
            if "{#" in linha and "#}" not in linha:
                vazados.append(f"{template.relative_to(RAIZ)}:{numero}")

    assert not vazados, (
        "comentário `{# #}` aberto numa linha e fechado em outra — o Django "
        "imprime isso na tela:\n  " + "\n  ".join(vazados)
    )
