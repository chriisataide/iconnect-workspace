"""Isolamento arquitetural — ST-002 aceite ④.

A Etapa 5 §5.3 põe WKS como **folha**: o Workspace depende de todos os domínios
(via provider), e nenhum domínio depende dele. Mas a mesma etapa (§5.9) mostra
`fsm/apps.py` fazendo `from workspace.launcher import registrar_app`, e a
Etapa 3 §3.1.1 regra 4 diz que o registro acontece no `apps.py` do domínio.

As duas coisas só se reconciliam de um jeito, que é o que este teste fixa:

    o domínio pode depender do CONTRATO (`workspace.providers`),
    nunca da SUPERFÍCIE (`workspace.views`, `.models`, `.services`, `.urls`…).

O contrato é PLT, que a matriz de dependência da §5.3 marca como "consumido por
todos". A superfície é WKS, que é folha. Hoje `dashboard` e `fsm` não importam
nada de `workspace` — este teste é o que impede a primeira violação de entrar
sem ninguém perceber.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent.parent

# Apps de domínio que não podem depender da superfície do Workspace.
DOMINIOS = ("dashboard", "fsm", "km_audit", "calculo_vigilante")

# O único subpacote de `workspace` que um domínio pode importar.
CONTRATO_PERMITIDO = "workspace.providers"


def _arquivos_python(app: str) -> list[Path]:
    diretorio = RAIZ / app
    if not diretorio.is_dir():
        return []
    return [
        caminho
        for caminho in diretorio.rglob("*.py")
        if "migrations" not in caminho.parts and "__pycache__" not in caminho.parts
    ]


def _modulos_workspace_importados(caminho: Path) -> list[str]:
    """Nomes de módulo de `workspace` importados por este arquivo."""
    try:
        arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    except SyntaxError:  # pragma: no cover - arquivo inválido é problema de outro gate
        return []

    encontrados: list[str] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            encontrados += [
                alias.name
                for alias in no.names
                if alias.name == "workspace" or alias.name.startswith("workspace.")
            ]
        elif isinstance(no, ast.ImportFrom):
            # `level > 0` é import relativo: nunca alcança outro app.
            if no.level == 0 and no.module and (
                no.module == "workspace" or no.module.startswith("workspace.")
            ):
                encontrados.append(no.module)
    return encontrados


@pytest.mark.parametrize("app", DOMINIOS)
def test_dominio_nao_importa_superficie_do_workspace(app):
    violacoes = []
    for caminho in _arquivos_python(app):
        for modulo in _modulos_workspace_importados(caminho):
            permitido = modulo == CONTRATO_PERMITIDO or modulo.startswith(
                CONTRATO_PERMITIDO + "."
            )
            if not permitido:
                violacoes.append(f"{caminho.relative_to(RAIZ)}: importa {modulo}")

    assert not violacoes, (
        "Domínio importando a superfície do Workspace (WKS é folha — Etapa 5 §5.3).\n"
        f"Permitido apenas `{CONTRATO_PERMITIDO}`.\n  " + "\n  ".join(violacoes)
    )


@pytest.mark.parametrize("app", DOMINIOS)
def test_st002_nao_acoplou_nenhum_dominio(app):
    """Aceite ④ no estado em que o ST-002 entrega: acoplamento zero.

    Diferente do teste acima, que permite o contrato. Este fixa o *ponto de
    partida*: nenhum domínio foi tocado. Quando o primeiro provider real for
    escrito (Onda 2+), este teste sai e o de cima continua.
    """
    importadores = [
        str(caminho.relative_to(RAIZ))
        for caminho in _arquivos_python(app)
        if _modulos_workspace_importados(caminho)
    ]
    assert not importadores, (
        f"O ST-002 não deveria tocar `{app}`. Arquivos que importam workspace: {importadores}"
    )


def test_workspace_nao_importa_model_de_dominio():
    """O caminho inverso: a superfície não consulta model de outro domínio.

    Etapa 3 §3.1.1 regra 4. `dashboard.PerfilUsuario` é a exceção conhecida —
    é identidade, não domínio, e a Etapa 3 decidiu evoluí-la em vez de duplicar.
    """
    proibidos = ("fsm", "km_audit", "calculo_vigilante")
    violacoes = []

    for caminho in _arquivos_python("workspace"):
        if "tests" in caminho.parts:
            continue
        try:
            arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
        except SyntaxError:  # pragma: no cover
            continue
        for no in ast.walk(arvore):
            alvos = []
            if isinstance(no, ast.Import):
                alvos = [alias.name for alias in no.names]
            elif isinstance(no, ast.ImportFrom) and no.level == 0 and no.module:
                alvos = [no.module]
            for alvo in alvos:
                raiz = alvo.split(".")[0]
                if raiz in proibidos:
                    violacoes.append(f"{caminho.relative_to(RAIZ)}: importa {alvo}")

    assert not violacoes, (
        "Workspace importando app de domínio diretamente — use um WorkspaceProvider.\n  "
        + "\n  ".join(violacoes)
    )
