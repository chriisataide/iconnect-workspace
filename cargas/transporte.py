"""O transporte dos conectores — HTTP para quem roda fora de uma requisição.

## Por que não é o `workspace/integracoes/cliente.py`

Porque os dois têm requisitos opostos, e um módulo com seis parâmetros para
servir aos dois não serviria bem a nenhum:

| | `workspace/integracoes/cliente.py` | aqui |
|---|---|---|
| roda | dentro de uma requisição do usuário | em comando agendado |
| timeout | 4 s — a tela não pode esperar | 60 s — a carga pode |
| retry | linear, 3× | recuo exponencial |
| `POST` | **nunca** repete | é o método de LEITURA do monday |
| paginação | não tem | limite de páginas por execução |
| falha | degrada o widget | marca a carga "parcial" |

A linha do `POST` decide sozinha. A API do monday é GraphQL: toda leitura é um
`POST`, e o cliente do iConnect recusa repetir `POST` — por um motivo correto lá,
que é não duplicar um consumo de código de uso único.

Além disso, aquele módulo é *o cliente do iConnect*, não um cliente HTTP: ele lê
`settings.ICONNECT_API_URL`, e a exceção dele diz "a integração com o iConnect
não está configurada".

O que os dois COMPARTILHAM é a disciplina, e ela é amarrada por teste e não por
herança: `test_nenhum_transporte_registra_credencial` exercita os dois e afirma
que nenhum valor de cabeçalho chega ao log.

## O que nunca sai daqui

Token, senha, `client_secret`, `X-Token`, cookie. O log registra método, host,
caminho e o motivo — nunca cabeçalho, nunca corpo de requisição. A tela de
fontes é visível à diretoria, e `erro_resumo` sai deste módulo.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

logger = logging.getLogger("cargas")

#: Tempo de uma chamada de carga. Generoso de propósito: o carregador roda em
#: comando agendado, e uma consulta de competência inteira no ERP demora.
TIMEOUT = 60.0

#: Tentativas por chamada. Três, e não mais: o carregador roda de novo amanhã, e
#: insistir dez vezes numa fonte fora do ar só atrasa a janela de carga inteira.
TENTATIVAS = 3

#: Recuo EXPONENCIAL: 1 s, 2 s, 4 s. Linear bate de novo enquanto o outro lado
#: ainda está subindo — e três batidas seguidas num serviço em recuperação é
#: como um `429` vira um bloqueio.
RECUO_INICIAL = 1.0

#: Teto do recuo. Sem ele, uma sequência longa esperaria minutos entre
#: tentativas e a carga estouraria a janela sem nunca falhar de vez.
RECUO_MAXIMO = 30.0

#: Códigos que valem repetir. `429` é explicitamente temporário; `4xx` de
#: permissão ou payload, não — insistir só demora mais para dar o mesmo erro.
REPETIVEIS = frozenset({429, 500, 502, 503, 504})

#: Páginas por execução, por fonte. É o freio do §"um conector que trava segura
#: a janela de carga inteira": sem teto, um cursor que não avança vira laço
#: infinito, e a carga das outras fontes nunca começa.
PAGINAS_MAXIMAS = 200


class TransporteError(Exception):
    """Tentou falar com a fonte e não deu. A mensagem vai para `erro_resumo`."""


class FonteNaoConfigurada(TransporteError):
    """Falta credencial ou endereço. Estado normal em desenvolvimento.

    Separada de `TransporteError` porque a resposta é outra: fonte não
    configurada não é uma fonte quebrada, e a tela precisa dizer coisas
    diferentes. É a mesma distinção que `IntegracaoIndisponivel` faz do outro
    lado.
    """


def pedir(
    url: str,
    *,
    metodo: str = "GET",
    cabecalhos: dict | None = None,
    corpo: dict | None = None,
    forma: str = "json",
    timeout: float = TIMEOUT,
    tentativas: int = TENTATIVAS,
    dormir=time.sleep,
) -> dict:
    """Uma chamada. Devolve o JSON decodificado ou levanta `TransporteError`.

    `forma="json"` envia `application/json`; `forma="form"` envia
    `application/x-www-form-urlencoded`, que é o que o `/authenticate` do
    Sankhya exige.

    `dormir` é injetável para o teste não esperar sete segundos de recuo. Não é
    ponto de extensão — é a única forma de testar recuo exponencial sem tornar a
    suíte lenta ou o recuo falso.
    """
    dados, cabecalhos = _preparar(corpo, forma, cabecalhos)
    host = urllib.parse.urlsplit(url).netloc
    caminho = urllib.parse.urlsplit(url).path

    ultima = ""
    for tentativa in range(1, tentativas + 1):
        requisicao = urllib.request.Request(
            url, data=dados, headers=cabecalhos, method=metodo
        )
        try:
            with urllib.request.urlopen(requisicao, timeout=timeout) as resposta:
                return _decodificar(resposta.read(), host, caminho)
        except urllib.error.HTTPError as erro:
            ultima = f"HTTP {erro.code} em {host}{caminho}"
            if erro.code not in REPETIVEIS or tentativa == tentativas:
                # Método, host e caminho. NUNCA cabeçalho, nunca corpo.
                logger.warning("carga %s %s%s → HTTP %s", metodo, host, caminho, erro.code)
                raise TransporteError(ultima) from erro
            # Só agora, porque `_espera_pedida` consome o corpo do erro — e num
            # erro que não se repete esse corpo não serve para nada.
            espera = _espera_pedida(erro) or _recuo(tentativa)
        except (urllib.error.URLError, TimeoutError, OSError) as erro:
            ultima = f"{host} não respondeu"
            if tentativa == tentativas:
                logger.warning("carga %s %s%s → %s", metodo, host, caminho, type(erro).__name__)
                raise TransporteError(ultima) from erro
            espera = _recuo(tentativa)
        dormir(espera)

    raise TransporteError(ultima or f"{host} não respondeu.")


def _preparar(corpo, forma: str, cabecalhos: dict | None):
    cabecalhos = dict(cabecalhos or {})
    cabecalhos.setdefault("Accept", "application/json")
    if corpo is None:
        return None, cabecalhos
    if forma == "form":
        cabecalhos["Content-Type"] = "application/x-www-form-urlencoded"
        return urllib.parse.urlencode(corpo).encode(), cabecalhos
    cabecalhos["Content-Type"] = "application/json"
    return json.dumps(corpo).encode(), cabecalhos


def _recuo(tentativa: int) -> float:
    """1 s, 2 s, 4 s… com teto."""
    return min(RECUO_INICIAL * (2 ** (tentativa - 1)), RECUO_MAXIMO)


def _espera_pedida(erro) -> float | None:
    """A espera que a PRÓPRIA fonte pediu, quando ela pede.

    O monday devolve `retry_in_seconds` no corpo do erro de limite, e o padrão
    HTTP tem `Retry-After`. Honrar o número da fonte é melhor que o nosso chute:
    o recuo exponencial pode esperar de menos e queimar as tentativas, ou de
    mais e estourar a janela.
    """
    cabecalho = None
    try:
        cabecalho = erro.headers.get("Retry-After")
    except Exception:  # pragma: no cover - headers ausentes em erro sintético
        cabecalho = None
    if cabecalho:
        try:
            return min(float(cabecalho), RECUO_MAXIMO)
        except ValueError:
            pass

    try:
        corpo = json.loads(erro.read().decode("utf-8"))
    except Exception:
        return None
    pedido = corpo.get("retry_in_seconds") if isinstance(corpo, dict) else None
    if isinstance(pedido, (int, float)):
        return min(float(pedido), RECUO_MAXIMO)
    return None


def _decodificar(bruto: bytes, host: str, caminho: str) -> dict:
    try:
        corpo = json.loads(bruto.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as erro:
        logger.warning("carga %s%s → resposta não é JSON", host, caminho)
        raise TransporteError(f"{host} respondeu algo que não é JSON.") from erro
    if not isinstance(corpo, dict):
        # Lista na raiz acontece, e quem chama espera um dicionário. Embrulhar é
        # melhor que levantar: o conector sabe o que fazer com `{"lista": [...]}`.
        return {"lista": corpo}
    return corpo
