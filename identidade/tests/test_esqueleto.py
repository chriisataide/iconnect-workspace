"""Carga do app IDN.

Parece trivial, mas app registrado no INSTALLED_APPS sem
`migrations/__init__.py` quebra o `makemigrations` só quando alguém adiciona o
primeiro modelo — semanas depois, longe da causa.
"""

from __future__ import annotations

from pathlib import Path

from django.apps import apps


def test_app_registrado():
    config = apps.get_app_config("identidade")
    assert config.name == "identidade"
    assert config.verbose_name == "Identidade & Organização"


def test_pacote_de_migracoes_existe():
    raiz = Path(__file__).resolve().parent.parent
    assert (raiz / "migrations" / "__init__.py").exists()
    assert (raiz / "migrations" / "0001_initial.py").exists()


def test_os_seis_modelos_de_idn_existem():
    """A fundação: estrutura (2) + posição (1) + autorização (3)."""
    nomes = {m.__name__ for m in apps.get_app_config("identidade").get_models()}
    assert nomes == {
        "Unidade",
        "Departamento",
        "Lotacao",
        "Papel",
        "AtribuicaoPapel",
        "Delegacao",
    }


def test_idn_nao_importa_app_de_dominio():
    """A Etapa 5 §5.3 põe IDN como raiz: ninguém depende de nada para chegar aqui.

    A única exceção é o comando `semear_papeis`, que precisa ler o `UserRole`
    legado de `dashboard/utils/rbac.py` para migrar sem ninguém perder acesso.
    Ela é deliberada, está isolada num import tardio dentro do comando, e é o
    único ponto do app que conhece o legado.
    """
    import ast

    raiz = Path(__file__).resolve().parent.parent
    proibidos = {"dashboard", "fsm", "km_audit", "calculo_vigilante", "workspace"}
    excecao = raiz / "management" / "commands" / "semear_papeis.py"
    violacoes = []

    for caminho in raiz.rglob("*.py"):
        if "migrations" in caminho.parts or "__pycache__" in caminho.parts:
            continue
        if caminho == excecao or "tests" in caminho.parts:
            continue
        arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
        for no in ast.walk(arvore):
            alvos = []
            if isinstance(no, ast.Import):
                alvos = [a.name for a in no.names]
            elif isinstance(no, ast.ImportFrom) and no.level == 0 and no.module:
                alvos = [no.module]
            for alvo in alvos:
                if alvo.split(".")[0] in proibidos:
                    violacoes.append(f"{caminho.relative_to(raiz)}: importa {alvo}")

    assert not violacoes, (
        "IDN é a raiz da dependência e não pode importar app de domínio.\n  "
        + "\n  ".join(violacoes)
    )
