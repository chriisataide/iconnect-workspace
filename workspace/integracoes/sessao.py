"""A identidade do lado de lá — a ponte SSO → JWT. §21 e §52.

## O problema que a ponte resolve

O Workspace e o iConnect compartilham o login SSO, e nada mais: deploys
separados, bancos separados, sessões separadas. Para o Workspace **ler** a API
do iConnect em nome da pessoa, ele precisa de um JWT dela — e não pode obtê-lo
por usuário+senha, porque conta provisionada por SSO recebe
`set_unusable_password()` do outro lado.

O fluxo, conforme o §2 do `API.md` deles:

1. o SSO é iniciado com `?next=` apontando para o Workspace;
2. o iConnect valida a origem, cria um código de uso único (60s) e redireciona
   para `{workspace}?sso_exchange=<code>`;
3. **este módulo** troca o código por `{access, refresh}` em
   `POST /api/v1/auth/sso-exchange/`.

## Onde o token fica, e por que não no banco

Na **sessão** da pessoa. Guardar JWT de terceiro numa tabela criaria um cofre
de credenciais para proteger, rotacionar e explicar numa auditoria — e o token
do iConnect vale 1 hora. A sessão já é o lugar onde a identidade da pessoa mora
neste produto, expira com ela, e some quando ela sai.

Consequência aceita e explícita: **um comando de linha não fala pela pessoa.**
Trabalho de fundo que precise da API do iConnect vai precisar de uma conta de
serviço com API Key — que é justamente o que o §2 do `API.md` recomenda, e é
outra decisão.

## O código de uso único não pode ficar na URL

O `API.md` pede em letras maiúsculas: a página que recebe `?sso_exchange=` tem
de limpar o parâmetro **antes** de qualquer script de terceiro rodar. Aqui isso
é resolvido no servidor — o middleware troca o código e **redireciona** para a
mesma URL sem ele. Redirecionar é mais forte que `history.replaceState`: o
código nunca chega a existir numa URL que o navegador guarda no histórico, e
nunca entra no `Referer` de uma requisição seguinte.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request

from django.conf import settings

from workspace.integracoes import cliente

logger = logging.getLogger(__name__)

#: Chaves na sessão. Prefixo próprio para não colidir com nada do Django.
CHAVE_ACCESS = "iconnect_access"
CHAVE_REFRESH = "iconnect_refresh"

#: O parâmetro que o iConnect devolve no redirecionamento do SSO.
PARAMETRO = "sso_exchange"


def trocar_codigo(request, codigo: str) -> bool:
    """Troca o código de uso único por um JWT e guarda na sessão.

    Devolve `False` em qualquer falha, sem levantar: o código pode ter expirado
    (60s), sido usado, ou não existir — e o iConnect responde a mesma coisa para
    os três, de propósito, para não virar oráculo. A pessoa continua entrando no
    Workspace; o que ela perde é a leitura do iConnect, e a tela diz isso.
    """
    if not codigo or not cliente.disponivel():
        return False

    cabecalho = {}
    if settings.WORKSPACE_SHARED_SECRET:
        cabecalho["X-Workspace-Secret"] = settings.WORKSPACE_SHARED_SECRET

    try:
        resposta = _post_sem_token(
            "/api/v1/auth/sso-exchange/", {"code": codigo}, cabecalho
        )
    except cliente.IntegracaoError as erro:
        # `info` e não `warning`: código expirado é rotina — a pessoa deixou a
        # aba aberta um minuto a mais. Barulho aqui treina a ignorar o log.
        logger.info("sso-exchange recusado: %s", erro)
        return False

    acesso = resposta.get("access")
    if not acesso:
        logger.warning("sso-exchange respondeu sem `access`")
        return False

    request.session[CHAVE_ACCESS] = acesso
    if resposta.get("refresh"):
        request.session[CHAVE_REFRESH] = resposta["refresh"]
    return True


def _post_sem_token(caminho: str, corpo: dict, cabecalhos: dict) -> dict:
    """`POST` com header extra. Existe porque `cliente.chamar` não expõe
    cabeçalho arbitrário de propósito — o único caso é este, e abrir a porta
    faria cada chamador inventar o seu."""
    url = f"{settings.ICONNECT_API_URL}/{caminho.lstrip('/')}"
    dados = json.dumps(corpo).encode()
    todos = {"Content-Type": "application/json", "Accept": "application/json"}
    todos.update(cabecalhos)

    requisicao = urllib.request.Request(url, data=dados, headers=todos, method="POST")
    try:
        with urllib.request.urlopen(
            requisicao, timeout=settings.ICONNECT_TIMEOUT
        ) as resposta:
            return json.loads(resposta.read() or b"{}")
    except urllib.error.HTTPError as erro:
        raise cliente.IntegracaoError(cliente._motivo_http(erro)) from erro
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as erro:
        raise cliente.IntegracaoError("O iConnect não respondeu a tempo.") from erro


def token_de(request) -> str:
    """O JWT desta pessoa, ou `""`.

    Vazio é resposta normal e não erro: quem entrou por senha no Workspace, sem
    passar pelo SSO, simplesmente não tem token do iConnect — e a tela diz isso
    em vez de fingir que o outro lado está fora do ar.
    """
    sessao = getattr(request, "session", None)
    return sessao.get(CHAVE_ACCESS, "") if sessao is not None else ""


def renovar(request) -> bool:
    """Usa o refresh para obter um access novo. `False` quando não dá.

    O access do iConnect vale 1 hora e o refresh 7 dias — então numa jornada
    normal a renovação acontece. Sem ela, a tela de chamados quebraria depois do
    almoço para quem entrou de manhã.
    """
    sessao = getattr(request, "session", None)
    refresh = sessao.get(CHAVE_REFRESH, "") if sessao is not None else ""
    if not refresh:
        return False

    try:
        resposta = cliente.chamar(
            "/api/v1/auth/jwt/refresh/", metodo="POST", corpo={"refresh": refresh}
        )
    except (cliente.IntegracaoError, cliente.IntegracaoIndisponivel):
        esquecer(request)
        return False

    if not resposta.get("access"):
        esquecer(request)
        return False

    sessao[CHAVE_ACCESS] = resposta["access"]
    return True


def esquecer(request) -> None:
    """Apaga o token da sessão. Chamado quando o iConnect diz que expirou."""
    sessao = getattr(request, "session", None)
    if sessao is None:
        return
    sessao.pop(CHAVE_ACCESS, None)
    sessao.pop(CHAVE_REFRESH, None)


def conectado(request) -> bool:
    """Esta pessoa tem leitura do iConnect agora?"""
    return cliente.disponivel() and bool(token_de(request))
