"""Endpoint da busca — devolve fragmento HTML, não JSON.

Etapa 3 §3.1.2: só existe endpoint JSON quando há consumidor externo
declarado. Aqui o consumidor é o próprio navegador, então o servidor devolve
HTML pronto e o cliente injeta. Sem serialização, sem template no JS, sem risco
de XSS por montagem de string.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from workspace.acesso import pessoa_da_requisicao
from workspace.services.busca import MIN_CARACTERES, buscar


def buscar_view(request: HttpRequest) -> HttpResponse:
    consulta = (request.GET.get("q") or "").strip()
    pessoa = pessoa_da_requisicao(request)
    grupos = buscar(consulta, pessoa)

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
