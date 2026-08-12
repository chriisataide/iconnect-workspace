"""Contraste dos tokens — WCAG 2.1 AA, nos dois temas.

Antecipa o ST-019. Entrou junto com a criação dos tokens porque a primeira
decisão de cor já teve um defeito: a ação primária usava `--au-brand-700`
(#334155) nos dois temas, o que dá 10:1 no claro e some no escuro. Token de cor
regride em silêncio — não quebra teste, não gera erro, só fica ruim.

A Etapa 6 §6.0 registra o mesmo defeito já encontrado antes no CSS legado:
`a { color: #06b6d4 }` sobre branco, contraste 2,43:1.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

TOKENS = Path(__file__).resolve().parent.parent / "static" / "workspace" / "src" / "tokens.css"

# (frente, fundo, mínimo). 4.5 = texto normal AA · 3.0 = texto grande e UI.
PARES = [
    ("--au-text", "--au-bg", 4.5),
    ("--au-text", "--au-surface", 4.5),
    ("--au-text-muted", "--au-surface", 4.5),
    ("--au-text-muted", "--au-bg", 4.5),
    ("--au-accent-text", "--au-surface", 4.5),
    ("--au-btn-fg", "--au-btn-bg", 4.5),
    # `subtle` também exige 4,5: veste rótulo de seção (11px) e selo — é texto
    # pequeno, não elemento gráfico. A regra de 3:1 só valeria para 18pt+.
    ("--au-text-subtle", "--au-surface", 4.5),
    ("--au-text-subtle", "--au-bg", 4.5),
]


def _bloco(css: str, tema: str) -> dict[str, str]:
    """Tokens do tema. `escuro` = :root + overrides de [data-theme="dark"]."""
    raiz = re.search(r":root\s*\{(.*?)\n\}", css, flags=re.S)
    assert raiz, "bloco :root não encontrado"
    tokens = dict(re.findall(r"(--au-[\w-]+)\s*:\s*([^;]+);", raiz.group(1)))

    if tema == "escuro":
        dark = re.search(r':root\[data-theme="dark"\]\s*\{(.*?)\n\}', css, flags=re.S)
        assert dark, "bloco [data-theme=dark] não encontrado"
        tokens.update(re.findall(r"(--au-[\w-]+)\s*:\s*([^;]+);", dark.group(1)))

    return {k: v.strip() for k, v in tokens.items()}


def _resolver(nome: str, tokens: dict[str, str], profundidade: int = 0) -> str:
    """Segue cadeias `var(--x)` até chegar num literal de cor."""
    assert profundidade < 10, f"referência circular em {nome}"
    valor = tokens[nome]
    ref = re.fullmatch(r"var\((--au-[\w-]+)\)", valor)
    return _resolver(ref.group(1), tokens, profundidade + 1) if ref else valor


def _rgb(cor: str) -> tuple[int, int, int]:
    cor = cor.strip()
    if cor.startswith("#"):
        h = cor[1:]
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
    nums = re.findall(r"[\d.]+", cor)
    assert len(nums) >= 3, f"cor não suportada: {cor}"
    return tuple(int(float(n)) for n in nums[:3])


def _luminancia(rgb: tuple[int, int, int]) -> float:
    def canal(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (canal(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _razao(frente: str, fundo: str) -> float:
    a, b = _luminancia(_rgb(frente)), _luminancia(_rgb(fundo))
    claro, escuro = max(a, b), min(a, b)
    return (claro + 0.05) / (escuro + 0.05)


@pytest.mark.parametrize("tema", ["claro", "escuro"])
@pytest.mark.parametrize(("frente", "fundo", "minimo"), PARES)
def test_par_de_cor_passa_em_aa(tema, frente, fundo, minimo):
    tokens = _bloco(TOKENS.read_text(encoding="utf-8"), tema)
    razao = _razao(_resolver(frente, tokens), _resolver(fundo, tokens))

    assert razao >= minimo, (
        f"[{tema}] {frente} sobre {fundo} = {razao:.2f}:1, exigido {minimo}:1"
    )


def test_razao_de_contraste_esta_correta():
    """Sanidade do próprio cálculo: preto sobre branco é 21:1."""
    assert round(_razao("#000000", "#ffffff"), 1) == 21.0
    assert round(_razao("#ffffff", "#ffffff"), 1) == 1.0


def test_au_tabela_tem_estilo():
    """`.au-tabela` é usada em quatro telas e ficou sem CSS por várias ondas.

    Tabela vazia parece igual estilizada ou não, então o defeito atravessou
    revisão e screenshot — só apareceu quando a fila da recepção encheu.

    Este teste guarda o caso geral: classe usada em template PRECISA existir na
    folha de estilo. Sem isso, o próximo `.au-algo` novo repete o erro.
    """
    app = TOKENS.parents[3]  # .../workspace
    folha = (TOKENS.with_name("workspace.css")).read_text(encoding="utf-8")
    folha += TOKENS.read_text(encoding="utf-8")

    usadas = set()
    for template in (app / "templates").rglob("*.html"):
        for atributo in re.findall(r'class="([^"]*)"', template.read_text(encoding="utf-8")):
            for classe in atributo.split():
                # Ignora o que o Django interpola: `au-etiqueta--{{ ... }}`.
                if classe.startswith("au-") and "{" not in classe:
                    usadas.add(classe)

    sem_estilo = sorted(c for c in usadas if f".{c}" not in folha)
    assert not sem_estilo, f"classes usadas sem CSS: {sem_estilo}"
