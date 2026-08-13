#!/usr/bin/env python3
"""Verifica os ratchets de qualidade da suíte: cobertura por app e nº de testes.

Dois gates, porque são duas falhas diferentes:

1. **Cobertura por app** — pega *código novo sem teste*.
   O pytest-cov só aceita um ``--cov-fail-under`` global, e um piso global
   permite que um app regrida enquanto outro sobe: a média esconde. No projeto
   anterior foi assim que ``fsm`` (núcleo do field service) e ``km_audit``
   ficaram sem proteção nenhuma enquanto ``dashboard`` subia — os dois eram
   apps grandes, e a média global nunca acusou.

2. **Contagem de testes** — pega *teste que sumiu*.
   Cobertura NÃO detecta remoção de teste. Medido em 2026-08-07, ainda no
   projeto anterior: apagar um arquivo inteiro com 16 testes derrubou a
   cobertura em 0,15 ponto — menos que o ruído de medição. Os testes se
   sobrepõem demais para a cobertura sozinha servir de gate contra remoção.

Uso:
    pytest                                   # gera coverage.json e junit.xml
    python scripts/check_coverage_ratchet.py # verifica os dois ratchets

Saída: 0 se ambos passam; 1 se algum regrediu.
"""

from __future__ import annotations

import json
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PYPROJECT = RAIZ / "pyproject.toml"
COVERAGE_JSON = RAIZ / "coverage.json"
JUNIT_XML = RAIZ / "junit.xml"

# Margem de tolerância para ruído de medição (ordem de teste, versão de lib).
# Deliberadamente pequena: o ponto do ratchet é ser apertado.
TOLERANCIA = 0.05


def carregar_pisos() -> dict[str, float]:
    """Lê os pisos por app de [tool.coverage_ratchet]."""
    if not PYPROJECT.exists():
        sair_com_erro(f"pyproject.toml não encontrado em {PYPROJECT}")
    dados = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    pisos = dados.get("tool", {}).get("coverage_ratchet", {})
    if not pisos:
        sair_com_erro("Seção [tool.coverage_ratchet] ausente ou vazia no pyproject.toml")
    return {app: float(valor) for app, valor in pisos.items()}


def carregar_cobertura(caminho: Path) -> dict:
    """Lê o relatório JSON do pytest-cov."""
    if not caminho.exists():
        sair_com_erro(
            f"{caminho.name} não encontrado.\n"
            "Rode `pytest` antes — o relatório JSON é gerado pelo addopts do pyproject."
        )
    return json.loads(caminho.read_text(encoding="utf-8"))


def agregar_por_app(cobertura: dict, apps: list[str]) -> dict[str, tuple[int, int]]:
    """Soma linhas cobertas e totais de cada app.

    O ``omit`` do coverage já removeu migrações, testes e conftest — aqui só
    somamos o que sobrou, atribuindo cada arquivo ao app pelo prefixo do caminho.
    """
    agregado: dict[str, list[int]] = {app: [0, 0] for app in apps}
    for caminho, arquivo in cobertura.get("files", {}).items():
        normalizado = caminho.replace("\\", "/")
        for app in apps:
            if normalizado.startswith(f"{app}/"):
                resumo = arquivo["summary"]
                agregado[app][0] += resumo["covered_lines"]
                agregado[app][1] += resumo["num_statements"]
                break
    return {app: (c, t) for app, (c, t) in agregado.items()}


def verificar_contagem_testes() -> str | None:
    """Confere o piso de testes coletados. Devolve a mensagem de falha, ou None.

    Conta ``<testcase>`` do JUnit XML — inclui aprovados, falhos e pulados, ou
    seja, é a contagem de COLETA. Independe de o ambiente ser SQLite ou
    PostgreSQL, então serve como piso estável nos dois.
    """
    dados = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    minimo = dados.get("tool", {}).get("test_count_ratchet", {}).get("minimo")
    if minimo is None:
        return None  # ratchet de contagem não configurado — silencioso

    if not JUNIT_XML.exists():
        return (
            f"{JUNIT_XML.name} não encontrado — o addopts do pyproject deveria "
            "gerá-lo (--junitxml=junit.xml)"
        )

    raiz = ET.parse(JUNIT_XML).getroot()
    coletados = sum(1 for _ in raiz.iter("testcase"))

    print("\n\033[1mRatchet de quantidade de testes\033[0m")
    print(f"  coletados: {coletados}   piso: {minimo}   margem: {coletados - minimo:+d}")

    if coletados < minimo:
        return (
            f"{coletados} testes coletados, abaixo do piso de {minimo}.\n"
            f"      Se testes foram consolidados de propósito, ajuste "
            f"[tool.test_count_ratchet] COM justificativa no PR."
        )
    return None


def sair_com_erro(mensagem: str) -> None:
    print(f"\n\033[31m✗ {mensagem}\033[0m\n", file=sys.stderr)
    sys.exit(2)


def main() -> int:
    pisos = carregar_pisos()
    cobertura = carregar_cobertura(COVERAGE_JSON)
    agregado = agregar_por_app(cobertura, list(pisos))

    print("\n\033[1mRatchet de cobertura por app\033[0m")
    print(f"{'app':<14}{'atual':>9}{'piso':>9}{'margem':>10}   ")
    print("─" * 52)

    falhas: list[str] = []
    for app, piso in sorted(pisos.items()):
        cobertas, total = agregado.get(app, (0, 0))
        if total == 0:
            falhas.append(f"{app}: nenhum arquivo medido — o app está em --cov?")
            print(f"{app:<14}{'—':>9}{piso:>8.1f}%{'—':>10}   \033[31mSEM DADOS\033[0m")
            continue

        atual = 100.0 * cobertas / total
        margem = atual - piso
        if margem < -TOLERANCIA:
            falhas.append(f"{app}: {atual:.2f}% está abaixo do piso de {piso:.1f}%")
            marca, cor = "REGREDIU", "\033[31m"
        elif margem >= 1.0:
            marca, cor = "SUBIU", "\033[32m"
        else:
            marca, cor = "ok", "\033[32m"
        print(f"{app:<14}{atual:>8.2f}%{piso:>8.1f}%{margem:>+9.2f}   {cor}{marca}\033[0m")

    print("─" * 52)

    # Os dois ratchets rodam sempre — reportar só o primeiro esconde o segundo.
    falha_contagem = verificar_contagem_testes()
    if falha_contagem:
        falhas.append(falha_contagem)

    if falhas:
        print("\n\033[31m✗ Ratchet violado:\033[0m")
        for falha in falhas:
            print(f"    • {falha}")
        print(
            "\nOs pisos só sobem, nunca descem. Se a queda for intencional,\n"
            "ajuste o pyproject.toml COM justificativa no PR.\n"
        )
        return 1

    subiu = [
        app
        for app, piso in pisos.items()
        if agregado.get(app, (0, 0))[1]
        and 100.0 * agregado[app][0] / agregado[app][1] - piso >= 1.0
    ]
    print("\n\033[32m✓ Cobertura e quantidade de testes no piso ou acima.\033[0m")
    if subiu:
        print(
            f"  Sugestão: {', '.join(sorted(subiu))} subiu ≥1 ponto — "
            "vale elevar o piso em [tool.coverage_ratchet].\n"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
