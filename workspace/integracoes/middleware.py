"""Recebe o código do SSO e o tira da URL. §21.

O iConnect redireciona para `{workspace}?sso_exchange=<code>`. O `API.md` pede
que o parâmetro saia da URL **imediatamente**, antes de qualquer script de
terceiro rodar — o código é de uso único e dura 60s, mas não deve ficar em log
de CDN nem no histórico do navegador.

Resolvido no servidor, e não com `history.replaceState`: o middleware troca o
código e **redireciona** para a mesma URL sem ele. É mais forte que a versão em
JavaScript — o código nunca chega a existir numa URL que o navegador guarda, e
nunca entra no `Referer` da requisição seguinte.

Middleware e não view: o iConnect pode mandar a pessoa para qualquer tela do
Workspace (`?next=`), e uma view só funcionaria se o destino fosse sempre a
home.
"""

from __future__ import annotations

from django.http import HttpResponseRedirect

from workspace.integracoes import sessao


class PonteSSO:
    """Troca `?sso_exchange=` por um JWT na sessão e limpa a URL."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        codigo = request.GET.get(sessao.PARAMETRO)
        if not codigo:
            return self.get_response(request)

        sessao.trocar_codigo(request, codigo)

        # Redireciona SEMPRE, mesmo quando a troca falhou: o código já foi
        # consumido (ou já era inválido), e deixá-lo na URL só o expõe. A pessoa
        # segue para a tela que pediu; o que ela perde é a leitura do iConnect,
        # e a tela diz isso.
        restante = request.GET.copy()
        restante.pop(sessao.PARAMETRO, None)
        destino = request.path
        if restante:
            destino = f"{destino}?{restante.urlencode()}"
        return HttpResponseRedirect(destino)
