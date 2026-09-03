"""Cabeçalhos de segurança do Workspace, com a CSP estrita.

## Por que é nosso, e não uma biblioteca

São quarenta linhas cuja razão de existir é ser **explícita e testada**. Uma
biblioteca de CSP resolve o caso geral — nonce, hash, report-only, por-view —, e
o caso geral é o que produz política com exceção: alguém precisa de um
`unsafe-inline` numa tela, a exceção entra "temporariamente", e nunca sai.

Aqui não há exceção a manter, porque não há inline nenhum a permitir.

## O que mudou na Onda 9.5

`style-src` passou a ter `unsafe-inline`. A decisão está no ADR-040
(docs/EXEC_25_GRAFICOS.md): a biblioteca de gráficos escreve `style=` no DOM, e
não há biblioteca de mercado que não escreva.

`script-src` **não** mudou quanto a inline: continua `'self'`, agora com nonce.
Nonce ali não enfraquece nada — ele só anularia um `unsafe-inline` que não
existe — e permite, sem ambiguidade, o bloco de dados
`<script type="application/json" nonce="…">` que leva os números até o gráfico.

## O detalhe que decide onde o nonce vai

Navegador moderno **ignora `unsafe-inline` quando há nonce na mesma diretiva**.
Manter os dois não é meio-termo: é manter o comportamento antigo achando que
abriu, e o sintoma é gráfico saindo errado em silêncio.

Por isso o nonce está em `script-src` e **não** em `style-src`. Há teste que
afirma exatamente isso — é o tipo de coisa que alguém "arruma" numa faxina.

## A disciplina que a CSP não cobra mais

`style=` em template NOSSO continua proibido, agora por lint e não pelo
navegador. O que a biblioteca injeta é aceito; o que nós escrevemos, não — e é
isso que mantém aberta a porta de voltar atrás.

A barra tripla da bandeja continua em SVG, onde `width` é atributo. Não porque
precise mais, mas porque desenhar com atributo é melhor de qualquer forma: ele
sobrevive a `style-src` fechada, e a decisão de fechar de novo não deveria custar
uma reescrita.
"""

from __future__ import annotations

import secrets

from django.conf import settings


def gerar_nonce() -> str:
    """Um nonce por requisição.

    `token_urlsafe(16)` são 128 bits. O mínimo que a especificação recomenda é
    128 — e nonce previsível é nonce que não serve para nada: quem consegue
    adivinhá-lo escreve o `<script>` que quiser.
    """
    return secrets.token_urlsafe(16)


class CabecalhosDeSeguranca:
    """Aplica CSP e as demais políticas em toda resposta."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # ANTES da view: o template precisa do nonce para escrever
        # `<script type="application/json" nonce="…">`, e `request` já está no
        # contexto de todo template por `context_processors.request`.
        #
        # Um atributo na requisição e não um `threading.local`: o segundo
        # sobrevive à requisição num servidor com pool de threads, e um nonce
        # que vaza de uma requisição para outra é um nonce reutilizável.
        request.csp_nonce = gerar_nonce()

        resposta = self.get_response(request)

        # `setdefault` e não atribuição: se uma view precisar de política
        # própria, ela decide — e o middleware não desfaz a decisão dela.
        resposta.setdefault(
            "Content-Security-Policy",
            settings.SEGURANCA_CSP_MOLDE.format(nonce=request.csp_nonce),
        )
        resposta.setdefault("X-Content-Type-Options", "nosniff")
        resposta.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resposta.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
        )
        # Isola o contexto de navegação: impede que outra origem consulte a
        # nossa via `window.open`.
        resposta.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        # E impede que outra origem EMBUTA o que servimos — `<img>`, `<script>`,
        # `<iframe>` de fora deixam de conseguir ler a resposta. `frame-ancestors`
        # e `X-Frame-Options` já cobrem o enquadramento da PÁGINA; este cobre os
        # recursos, e é o que barra o download de um anexo puxado por uma página
        # de outra origem no navegador de quem está com a sessão aberta.
        #
        # `same-origin` e não `same-site`: os dois produtos são domínios
        # diferentes de propósito, e não há recurso nosso que o iConnect embuta.
        resposta.setdefault("Cross-Origin-Resource-Policy", "same-origin")

        return resposta
