"""monday.com — projetos, marcos, responsáveis e bloqueios.

## A API, conferida em 01/09/2026

Documentação vigente: <https://developer.monday.com/api-reference/>.

    POST https://api.monday.com/v2
    Authorization: <token>
    API-Version: 2026-07          ← estável hoje; 2026-04 em manutenção,
    Content-Type: application/json   2026-10 é release candidate

Três coisas da documentação que mudam o código:

1. **`items_page` aceita no máximo 500 itens** e devolve `cursor`. As páginas
   seguintes vêm de `next_items_page(cursor:)`, que é um objeto de topo — e não
   de repetir `items_page` dentro de `boards`, que multiplica o custo de
   complexidade da consulta.
2. **Erro de limite traz `retry_in_seconds`.** O transporte honra esse número
   antes do próprio recuo exponencial: o chute pode esperar de menos e queimar
   as tentativas, ou de mais e estourar a janela.
3. **O limite diário é de 1.000 chamadas** nos planos Free/Standard/Basic. Por
   isso `PAGINAS_MAXIMAS` existe: um cursor que não avança viraria laço
   infinito e queimaria a cota do dia inteiro em minutos.

## O parsing de `column_values` é o trabalho de verdade

`column_values` devolve `id`, `type`, `text` e `value` para todo tipo, mais
campos próprios por tipo. As armadilhas, na ordem em que atrapalham:

- **status** — `text` é o rótulo, mas quem muda o rótulo na tela muda o `text` de
  todo o histórico. `index` é estável. Lemos os dois e casamos pelo rótulo,
  caindo no índice quando o rótulo não é conhecido.
- **board_relation** — não tem `text` útil: traz IDs de itens do outro board. É
  por ele que o projeto acha o contrato.
- **mirror** — **às vezes vem vazio na API mesmo aparecendo na tela.** Espelho de
  espelho não é fonte: um valor que existe na tela e não na API produziria um
  campo que zera sozinho na carga seguinte. Por isso mirror é ignorado, e o dado
  que ele espelharia é buscado no board de origem.

## O que este arquivo NÃO pode saber

Os **ids dos boards e das colunas da ADB**. Eles são números daquela conta, e não
existe resposta certa que eu possa escrever sem ver os boards.

Por isso o mapa está em `settings.MONDAY_BOARDS`, e o levantamento sai de
`scripts/inventario_monday.py`. Sem mapa, o conector diz o que falta em vez de
carregar zero item e marcar a carga como sucesso.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from datetime import datetime

from django.conf import settings

from ..transporte import PAGINAS_MAXIMAS, FonteNaoConfigurada, TransporteError, pedir
from .base import ConectorBase, Janela, Registro

logger = logging.getLogger("cargas")

ENDPOINT = "https://api.monday.com/v2"

#: Fixada, e não omitida. Sem o cabeçalho, a conta cai na versão padrão do dia —
#: e o dia em que o monday promover a release candidate, a carga muda de
#: comportamento sozinha, num domingo.
API_VERSION = "2026-07"

#: Teto da API. Pedir mais devolve erro de validação, não uma página maior.
POR_PAGINA = 100

#: Fragmentos por tipo. `text` e `value` vêm de graça pela interface; o resto é
#: o que cada tipo sabe responder além disso.
CAMPOS = """
  id
  name
  updated_at
  group { title }
  column_values {
    id
    type
    text
    value
    ... on StatusValue { index label }
    ... on BoardRelationValue { linked_item_ids }
    ... on DateValue { date }
    ... on PeopleValue { text }
  }
"""

Q_PAGINA = """
query ($board: ID!, $limit: Int!) {
  boards (ids: [$board]) {
    id
    name
    items_page (limit: $limit) {
      cursor
      items { %s }
    }
  }
}
""" % CAMPOS

Q_PROXIMA = """
query ($cursor: String!, $limit: Int!) {
  next_items_page (cursor: $cursor, limit: $limit) {
    cursor
    items { %s }
  }
}
""" % CAMPOS

#: Rótulos de status → situação do espelho. Casado por rótulo NORMALIZADO, para
#: "Em Andamento", "em andamento" e "EM ANDAMENTO" serem a mesma coisa.
SITUACOES = {
    "nao iniciado": "nao_iniciado",
    "a fazer": "nao_iniciado",
    "em andamento": "em_andamento",
    "trabalhando nisso": "em_andamento",
    "concluido": "concluido",
    "feito": "concluido",
    "pronto": "concluido",
    "cancelado": "cancelado",
    "parado": "cancelado",
}

BLOQUEADOS = frozenset({"bloqueado", "travado", "impedido", "em risco"})


class ConectorMonday(ConectorBase):
    chave = "monday"

    @property
    def token(self) -> str:
        return getattr(settings, "MONDAY_TOKEN", "") or ""

    def boards(self) -> dict:
        """`{"projeto": {"board": 123, "colunas": {...}}, "marco": {...}}`.

        Vem do settings porque são ids da conta da ADB. O levantamento sai de
        `scripts/inventario_monday.py`.
        """
        return getattr(settings, "MONDAY_BOARDS", None) or {}

    def disponivel(self) -> bool:
        return bool(self.token and self.boards())

    # ── Coleta ──────────────────────────────────────────────────────

    def coletar(self, janela: Janela) -> Iterable[dict]:
        if not self.token:
            raise FonteNaoConfigurada("Falta MONDAY_TOKEN.")
        if not self.boards():
            raise FonteNaoConfigurada(
                "Falta MONDAY_BOARDS. Rode scripts/inventario_monday.py para "
                "levantar os ids de board e de coluna."
            )

        for entidade, config in self.boards().items():
            board = config.get("board")
            if not board:
                raise TransporteError(f"{entidade}: board não declarado em MONDAY_BOARDS.")
            for item in self._itens(board):
                yield {"_entidade": entidade, "_config": config, **item}

    def _itens(self, board) -> Iterable[dict]:
        resposta = self._consultar(Q_PAGINA, {"board": str(board), "limit": POR_PAGINA})
        boards = (resposta.get("data") or {}).get("boards") or []
        if not boards:
            # Board inexistente ou sem acesso. Silêncio aqui produziria carga
            # "sucesso" com zero projetos, que é indistinguível de "a empresa
            # não tem projeto nenhum".
            raise TransporteError(f"board {board} não existe ou não é visível pelo token.")

        pagina = boards[0].get("items_page") or {}
        yield from pagina.get("items") or []
        cursor = pagina.get("cursor")

        lidas = 1
        while cursor:
            if lidas >= PAGINAS_MAXIMAS:
                raise TransporteError(
                    f"board {board}: passou de {PAGINAS_MAXIMAS} páginas. "
                    "Cursor que não termina queima a cota diária da conta."
                )
            resposta = self._consultar(
                Q_PROXIMA, {"cursor": cursor, "limit": POR_PAGINA}
            )
            proxima = (resposta.get("data") or {}).get("next_items_page") or {}
            yield from proxima.get("items") or []
            cursor = proxima.get("cursor")
            lidas += 1

    def _consultar(self, query: str, variaveis: dict) -> dict:
        resposta = pedir(
            ENDPOINT,
            metodo="POST",
            cabecalhos={
                "Authorization": self.token,
                "API-Version": API_VERSION,
            },
            corpo={"query": query, "variables": variaveis},
        )
        erros = resposta.get("errors") or resposta.get("error_message")
        if erros:
            # A mensagem do GraphQL vai para `erro_resumo`, que aparece na tela
            # de fontes — por isso truncada e sem o corpo inteiro, que às vezes
            # traz de volta a query com as variáveis.
            texto = json.dumps(erros, ensure_ascii=False)[:200]
            raise TransporteError(f"monday recusou a consulta: {texto}")
        return resposta

    # ── Normalização ────────────────────────────────────────────────

    def normalizar(self, bruto: Iterable[dict]) -> Iterable[Registro]:
        for item in bruto:
            registro = self._converter(item)
            if registro is not None:
                yield registro

    def _converter(self, item: dict) -> Registro | None:
        entidade = item.get("_entidade", "")
        config = item.get("_config") or {}
        colunas = config.get("colunas") or {}
        if not entidade:
            return None

        valores = _por_id(item.get("column_values") or [])
        dados: dict = {"nome" if entidade == "projeto" else "titulo": item.get("name") or ""}

        for campo, coluna_id in colunas.items():
            valor = valores.get(coluna_id)
            if valor is None:
                continue
            convertido = _converter_coluna(campo, valor)
            if convertido is not None:
                dados[campo] = convertido

        if entidade == "projeto":
            dados.setdefault("codigo", f"MON-{item.get('id')}")
            dados["movimentado_em"] = _instante(item.get("updated_at"))
            # Bloqueio sai do status, e não de uma coluna de checkbox: no monday
            # o "travado" quase sempre é um rótulo de status, e uma coluna
            # separada ficaria desatualizada em relação a ele.
            rotulo = _rotulo(valores.get(colunas.get("situacao", "")))
            dados["bloqueado"] = _normalizar(rotulo) in BLOQUEADOS
            if "situacao" in dados:
                dados["situacao"] = SITUACOES.get(_normalizar(dados["situacao"]), "em_andamento")

        return Registro(
            entidade=entidade,
            chave_externa=str(item.get("id") or ""),
            dados=dados,
        )


def _por_id(valores: list) -> dict:
    return {v.get("id"): v for v in valores if v.get("id")}


def _rotulo(valor) -> str:
    if not isinstance(valor, dict):
        return ""
    return valor.get("label") or valor.get("text") or ""


def _converter_coluna(campo: str, valor: dict):
    """Um valor de coluna do monday no vocabulário do espelho.

    A ordem dos testes é a ordem da confiabilidade: campo tipado primeiro,
    `text` depois. `text` é o que a tela mostra e muda quando alguém renomeia um
    rótulo; o campo tipado é o que o monday guarda.
    """
    tipo = valor.get("type") or ""

    if tipo == "mirror":
        # Ver o cabeçalho: mirror às vezes vem vazio na API mesmo aparecendo na
        # tela, e um campo que zera sozinho é pior que um campo ausente.
        return None
    if tipo == "status":
        return valor.get("label") or valor.get("text") or None
    if tipo == "date":
        return _dia(valor.get("date") or valor.get("text"))
    if tipo == "board_relation":
        ids = valor.get("linked_item_ids") or []
        return str(ids[0]) if ids else None
    if tipo == "numbers":
        texto = valor.get("text") or ""
        try:
            return int(float(texto)) if campo == "percentual_concluido" else texto
        except (TypeError, ValueError):
            return None
    return (valor.get("text") or "").strip() or None


def _dia(texto):
    if not texto:
        return None
    try:
        return datetime.strptime(str(texto)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _instante(texto):
    if not texto:
        return None
    try:
        return datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    except ValueError:
        return None


def _normalizar(texto: str) -> str:
    import unicodedata

    sem_acento = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).casefold().strip()
