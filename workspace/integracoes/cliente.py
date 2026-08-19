"""O transporte — §52 e §53.

Uma função que fala HTTP e traduz tudo o que dá errado em uma exceção com
mensagem em português. É o único lugar do produto que conhece `urllib`.

## Os cinco requisitos do §53, e onde cada um mora

| exigência | aqui |
|---|---|
| **timeout** | `settings.ICONNECT_TIMEOUT`, curto (4s) — a chamada acontece DENTRO de uma requisição do Workspace, e um iConnect lento não pode virar um Workspace lento |
| **retry** | só em `GET` e só em erro de REDE ou `5xx`. Repetir um `POST` é reenviar; repetir um `4xx` é insistir no mesmo erro mais devagar |
| **logging** | tudo, com o endpoint e o motivo. Nunca o token, nunca o corpo |
| **fallback** | quem chama recebe exceção tipada e decide — a lista fica vazia, a tela diz o que houve |
| **mensagem amigável** | `IntegracaoError.__str__` é o texto que vai para a tela. "HTTPError 502" não é resposta para ninguém |

## Duas exceções, e a diferença importa

`IntegracaoIndisponivel` significa **não configurado** — o Workspace roda sem o
iConnect, e isso é estado normal, não falha. A tela diz "não está conectado".

`IntegracaoError` significa **tentou e não deu**. A tela diz "o iConnect não
respondeu" e mostra o que já sabe.

Misturar as duas faria a instalação sem integração parecer um sistema quebrado.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings

logger = logging.getLogger(__name__)

#: Quantas vezes repetir um `GET` que falhou por rede ou 5xx. Duas tentativas
#: extras cobrem o reinício de um processo do outro lado; a terceira só
#: transformaria uma indisponibilidade em espera longa para o usuário.
TENTATIVAS = 3

#: Espera entre tentativas, em segundos. Cresce para não bater de novo no
#: mesmo instante em que o outro lado ainda está subindo.
ESPERA_INICIAL = 0.2

#: Códigos que valem repetir. `429` entra porque é explicitamente temporário;
#: `4xx` de permissão ou payload, não — insistir só demora mais para dar o
#: mesmo erro.
REPETIVEIS = frozenset({429, 500, 502, 503, 504})


class IntegracaoIndisponivel(Exception):
    """O iConnect não está configurado neste ambiente. Estado normal."""

    def __str__(self) -> str:
        return "A integração com o iConnect não está configurada neste ambiente."


class IntegracaoError(Exception):
    """Tentou falar com o iConnect e não deu. A mensagem vai para a tela."""


def disponivel() -> bool:
    return bool(getattr(settings, "ICONNECT_API_URL", ""))


def _url(caminho: str, parametros: dict | None = None) -> str:
    base = settings.ICONNECT_API_URL
    url = f"{base}/{caminho.lstrip('/')}"
    if parametros:
        # Só o que tem valor: `?status=None` viraria um filtro literal pela
        # string "None" do outro lado.
        limpos = {k: v for k, v in parametros.items() if v not in (None, "")}
        if limpos:
            url = f"{url}?{urllib.parse.urlencode(limpos)}"
    return url


def chamar(
    caminho: str,
    *,
    token: str = "",
    metodo: str = "GET",
    parametros: dict | None = None,
    corpo: dict | None = None,
    timeout: float | None = None,
) -> dict:
    """Uma chamada ao iConnect. Devolve o JSON ou levanta.

    `token` é o JWT da pessoa — ver `sessao.py`. Sem ele, a chamada vai anônima,
    o que só serve para o *health check*.
    """
    if not disponivel():
        raise IntegracaoIndisponivel()

    dados = json.dumps(corpo).encode() if corpo is not None else None
    cabecalhos = {"Accept": "application/json"}
    if dados is not None:
        cabecalhos["Content-Type"] = "application/json"
    if token:
        cabecalhos["Authorization"] = f"Bearer {token}"

    url = _url(caminho, parametros)
    limite = timeout or settings.ICONNECT_TIMEOUT
    # Repetir só o que é seguro repetir. `POST` que chegou e cuja resposta se
    # perdeu produziria um segundo registro do outro lado — e o único `POST`
    # que fazemos consome um código de uso único.
    tentativas = TENTATIVAS if metodo == "GET" else 1

    ultima = ""
    for tentativa in range(1, tentativas + 1):
        requisicao = urllib.request.Request(
            url, data=dados, headers=cabecalhos, method=metodo
        )
        try:
            with urllib.request.urlopen(requisicao, timeout=limite) as resposta:
                return _decodificar(resposta.read(), caminho)
        except urllib.error.HTTPError as erro:
            ultima = _motivo_http(erro)
            if erro.code not in REPETIVEIS or tentativa == tentativas:
                logger.warning(
                    "iConnect %s %s → HTTP %s", metodo, caminho, erro.code
                )
                raise IntegracaoError(ultima) from erro
        except (urllib.error.URLError, TimeoutError, OSError) as erro:
            ultima = "O iConnect não respondeu a tempo."
            if tentativa == tentativas:
                logger.warning("iConnect %s %s → %s", metodo, caminho, erro)
                raise IntegracaoError(ultima) from erro
        # Espera crescente: 0,2s, 0,4s. O outro lado pode estar subindo.
        time.sleep(ESPERA_INICIAL * tentativa)

    raise IntegracaoError(ultima or "O iConnect não respondeu.")


def _decodificar(bruto: bytes, caminho: str) -> dict:
    """JSON, ou erro com mensagem que alguém entende.

    Corpo vazio vira `{}` e não erro: `204` é resposta legítima, e tratá-lo como
    falha faria uma operação bem-sucedida aparecer como problema.
    """
    if not bruto:
        return {}
    try:
        conteudo = json.loads(bruto)
    except (ValueError, UnicodeDecodeError) as erro:
        logger.warning("iConnect %s devolveu algo que não é JSON", caminho)
        raise IntegracaoError("O iConnect respondeu num formato inesperado.") from erro

    # §10 do `API.md`: vários endpoints devolvem `{"success": false}` com HTTP
    # 200. Confiar só no status code faria a falha passar por sucesso — e o
    # aviso está na documentação deles justamente porque acontece.
    if isinstance(conteudo, dict) and conteudo.get("success") is False:
        raise IntegracaoError(
            conteudo.get("error") or conteudo.get("detail") or "O iConnect recusou."
        )
    return conteudo if isinstance(conteudo, dict) else {"results": conteudo}


def _motivo_http(erro: urllib.error.HTTPError) -> str:
    """A mensagem que vai para a tela. Nunca o corpo bruto do outro lado.

    §10 do `API.md` avisa que o 403 do iConnect às vezes vem como **página
    HTML** (o `role_required` deles) e às vezes como JSON. Mostrar o corpo cru
    despejaria HTML na tela; por isso a mensagem é nossa, por faixa de código.
    """
    if erro.code in (401, 403):
        return "Sua sessão no iConnect expirou ou não tem acesso a isto."
    if erro.code == 404:
        return "O iConnect não encontrou o que foi pedido."
    if erro.code == 429:
        return "O iConnect está recebendo pedidos demais. Tente em instantes."
    if 500 <= erro.code < 600:
        return "O iConnect está com problema. Tente de novo em instantes."
    return "O iConnect recusou o pedido."
