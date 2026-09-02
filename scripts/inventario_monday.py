#!/usr/bin/env python3
"""
Inventário dos boards do monday.com — insumo para o conector_monday do
iConnect Workspace.

Não altera nada no monday. Faz apenas leitura, e grava dois arquivos:

  monday_inventario.json  — estrutura completa, para o Claude Code ler
  monday_inventario.md    — resumo legível, para você conferir

USO
    export MONDAY_TOKEN="seu_token_de_api"
    python inventario_monday.py                     # tudo
    python inventario_monday.py --workspace 12345   # só um workspace
    python inventario_monday.py --com-amostra       # inclui 1 item por board

O token sai de: monday → avatar → Developers → My Access Tokens.
Use um token de usuário de SERVIÇO com acesso somente leitura, nunca o seu.

NOTA SOBRE A API
O endpoint e o cabeçalho de versão abaixo refletem a API v2 do monday. Se a
chamada falhar com erro de versão, confira o valor corrente em
https://developer.monday.com/api-reference/ e ajuste API_VERSION.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter

import requests

ENDPOINT = "https://api.monday.com/v2"
API_VERSION = "2024-10"
PAGINA = 25          # boards por página; monday cobra complexidade por chamada
PAUSA = 0.6          # segundo entre chamadas, para não bater no rate limit


# ─────────────────────────────────────────────────────────── consultas ──

Q_BOARDS = """
query ($limit: Int!, $page: Int!, $ids: [ID!]) {
  boards (limit: $limit, page: $page, workspace_ids: $ids,
          board_kind: public, state: active, order_by: used_at) {
    id
    name
    description
    board_kind
    state
    items_count
    updated_at
    workspace { id name }
    groups { id title }
    columns { id title type description settings_str }
  }
}
"""

Q_AMOSTRA = """
query ($board: ID!) {
  boards (ids: [$board]) {
    items_page (limit: 1) {
      items {
        id
        name
        group { title }
        column_values { id type text value }
      }
    }
  }
}
"""


def consultar(token: str, query: str, variables: dict) -> dict:
    resposta = requests.post(
        ENDPOINT,
        json={"query": query, "variables": variables},
        headers={
            "Authorization": token,
            "API-Version": API_VERSION,
            "Content-Type": "application/json",
        },
        timeout=60,
    )
    resposta.raise_for_status()
    corpo = resposta.json()
    if "errors" in corpo:
        raise RuntimeError(json.dumps(corpo["errors"], ensure_ascii=False, indent=2))
    return corpo["data"]


def coletar_boards(token: str, workspace_ids: list[str] | None) -> list[dict]:
    boards, pagina = [], 1
    while True:
        dados = consultar(
            token,
            Q_BOARDS,
            {"limit": PAGINA, "page": pagina, "ids": workspace_ids},
        )
        lote = dados.get("boards") or []
        boards.extend(lote)
        print(f"  página {pagina}: {len(lote)} boards", file=sys.stderr)
        if len(lote) < PAGINA:
            break
        pagina += 1
        time.sleep(PAUSA)
    return boards


def coletar_amostra(token: str, board_id: str) -> dict | None:
    try:
        dados = consultar(token, Q_AMOSTRA, {"board": board_id})
        itens = dados["boards"][0]["items_page"]["items"]
        return itens[0] if itens else None
    except Exception as erro:                    # board sem acesso, board vazio
        return {"_erro": str(erro)[:200]}


# ──────────────────────────────────────────────────────────── relatório ──

def escrever_markdown(boards: list[dict], caminho: str) -> None:
    tipos = Counter(c["type"] for b in boards for c in b["columns"])
    workspaces: dict[str, list[dict]] = {}
    for b in boards:
        ws = (b.get("workspace") or {}).get("name") or "— sem workspace —"
        workspaces.setdefault(ws, []).append(b)

    linhas = [
        "# Inventário monday.com — ADB",
        "",
        f"{len(boards)} boards em {len(workspaces)} workspaces.",
        "",
        "## Tipos de coluna em uso",
        "",
        "| Tipo | Ocorrências |",
        "|---|---|",
    ]
    for tipo, n in tipos.most_common():
        linhas.append(f"| `{tipo}` | {n} |")

    linhas += ["", "## Boards por workspace", ""]
    for ws, lista in sorted(workspaces.items()):
        linhas.append(f"### {ws}")
        linhas.append("")
        for b in sorted(lista, key=lambda x: x["name"]):
            linhas.append(
                f"**{b['name']}** — id `{b['id']}` · "
                f"{b.get('items_count', '?')} itens · "
                f"atualizado em {b.get('updated_at', '?')[:10]}"
            )
            if b.get("description"):
                linhas.append(f"> {b['description']}")
            linhas.append("")
            linhas.append("| Coluna | id | tipo |")
            linhas.append("|---|---|---|")
            for c in b["columns"]:
                linhas.append(f"| {c['title']} | `{c['id']}` | `{c['type']}` |")
            grupos = ", ".join(g["title"] for g in b.get("groups", []))
            linhas.append("")
            linhas.append(f"Grupos: {grupos or '—'}")
            linhas.append("")

    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write("\n".join(linhas))


# ───────────────────────────────────────────────────────────────── main ──

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", action="append", dest="workspaces",
                        help="ID de workspace; pode repetir. Padrão: todos.")
    parser.add_argument("--com-amostra", action="store_true",
                        help="Inclui um item de exemplo por board.")
    parser.add_argument("--saida", default="monday_inventario",
                        help="Prefixo dos arquivos de saída.")
    args = parser.parse_args()

    token = os.environ.get("MONDAY_TOKEN")
    if not token:
        print("Defina MONDAY_TOKEN antes de rodar.", file=sys.stderr)
        return 1

    print("Coletando boards…", file=sys.stderr)
    boards = coletar_boards(token, args.workspaces)

    if args.com_amostra:
        print("Coletando amostras…", file=sys.stderr)
        for i, b in enumerate(boards, 1):
            b["_amostra"] = coletar_amostra(token, b["id"])
            print(f"  {i}/{len(boards)} {b['name']}", file=sys.stderr)
            time.sleep(PAUSA)

    with open(f"{args.saida}.json", "w", encoding="utf-8") as arquivo:
        json.dump(boards, arquivo, ensure_ascii=False, indent=2)
    escrever_markdown(boards, f"{args.saida}.md")

    print(
        f"\nPronto: {len(boards)} boards.\n"
        f"  {args.saida}.json  → para o Claude Code\n"
        f"  {args.saida}.md    → para você conferir\n\n"
        "ANTES DE COMPARTILHAR: o .json pode conter nome de cliente e de\n"
        "colaborador. Se for anexar em algum lugar, revise.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
