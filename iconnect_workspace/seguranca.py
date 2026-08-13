"""Cabeçalhos de segurança do Workspace, com a CSP estrita.

## Por que é nosso, e não uma biblioteca

São quarenta linhas cuja razão de existir é ser **explícita e testada**. Uma
biblioteca de CSP resolve o caso geral — nonce, hash, report-only, por-view —, e
o caso geral é o que produz política com exceção: alguém precisa de um
`unsafe-inline` numa tela, a exceção entra "temporariamente", e nunca sai.

Aqui não há exceção a manter, porque não há inline nenhum a permitir.

## Por que a política pode ser estrita

O Workspace não tem um único `style=` nem `onclick=`. Isso não é aspiração: há
teste que varre os templates e falha se aparecer um. O CSS mora em
`workspace/static/workspace/src/`, o JS em `workspace.js`, e ambos são carregados
por `<link>` e `<script src>`.

O projeto anterior não tinha essa opção. Ele servia o Workspace no mesmo processo
do iConnect Platform, que usa `style=` em larga escala e por isso precisa de
`unsafe-inline` em `style-src`. Um header, dois inquilinos, e o denominador comum
é sempre o mais permissivo — o Workspace pagava a dívida sem colher o benefício.

## O detalhe que motivou tudo isso

Navegador moderno **ignora `unsafe-inline` quando há nonce** na mesma diretiva. E
nonce não se aplica a atributo `style=""`, só a `<style>`. Ou seja: numa CSP com
nonce, todo `style="width: 42%"` é descartado em silêncio — o elemento
simplesmente não recebe o estilo, e nada aparece no log do servidor. É por isso
que a barra tripla da bandeja de aprovação é desenhada em SVG, onde `width` é
atributo e não estilo.
"""

from __future__ import annotations

from django.conf import settings


class CabecalhosDeSeguranca:
    """Aplica CSP e as demais políticas em toda resposta."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        resposta = self.get_response(request)

        # `setdefault` e não atribuição: se uma view precisar de política
        # própria, ela decide — e o middleware não desfaz a decisão dela.
        resposta.setdefault("Content-Security-Policy", settings.SEGURANCA_CSP)
        resposta.setdefault("X-Content-Type-Options", "nosniff")
        resposta.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resposta.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
        )
        # Isola o contexto de navegação: impede que outra origem consulte a
        # nossa via `window.open`.
        resposta.setdefault("Cross-Origin-Opener-Policy", "same-origin")

        return resposta
