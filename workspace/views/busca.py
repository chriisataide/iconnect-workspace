"""Endpoint da busca — devolve fragmento HTML, não JSON.

Etapa 3 §3.1.2: só existe endpoint JSON quando há consumidor externo
declarado. Aqui o consumidor é o próprio navegador, então o servidor devolve
HTML pronto e o cliente injeta. Sem serialização, sem template no JS, sem risco
de XSS por montagem de string.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from workspace.services.busca import MIN_CARACTERES, buscar


def buscar_view(request: HttpRequest) -> HttpResponse:
    """Quem busca é `request.user`, e nunca a pessoa de referência do hub.

    `pessoa_da_requisicao()` devolve uma conta REAL do organograma para o
    visitante anônimo, porque as telas abertas precisam de alguém para calcular
    ALCANCE — quais tiles aparecem, quais itens do catálogo. Alcance é uma
    coisa; "o que é meu" é outra, e a busca responde as duas.

    Estava usando a pessoa de referência, e o §57 transformou isso num
    vazamento direto: com solicitação e correspondência no índice, o visitante
    anônimo passava a procurar COMO aquela pessoa — e via, com nome e número, os
    pedidos dela. Antes do §57 o mesmo caminho já entregava documento dirigido
    ao departamento dela, o que era menos visível e igualmente errado.

    `subjects_de(AnonymousUser)` devolve `["*"]`: o visitante vê o que é
    institucional, e nada mais. É o recorte certo para um hub aberto.
    """
    consulta = (request.GET.get("q") or "").strip()
    grupos = buscar(consulta, request.user)

    return render(
        request,
        "workspace/_resultados_busca.html",
        {
            "consulta": consulta,
            "grupos": grupos,
            "curta": 0 < len(consulta) < MIN_CARACTERES,
            "total": sum(len(itens) for itens in grupos.values()),
        },
    )
