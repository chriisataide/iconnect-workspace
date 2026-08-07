"""Home do Portal — pública.

O Portal é a porta de entrada da empresa e **não exige login**: quem chega vê
o hub e escolhe o sistema. O tile do iConnect é que leva ao login do sistema
principal.

A personalização do briefing original ("Olá Christopher", pendências,
aprovações, favoritos) exige identidade. Resolvido de forma progressiva: a
página funciona anônima e, se houver sessão, cumprimenta pelo nome e passa a
`pessoa` para o launcher filtrar. Nada aqui redireciona para o login.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from workspace.launcher import apps_disponiveis


def home(request: HttpRequest) -> HttpResponse:
    """Renderiza o hub do Portal."""
    autenticado = request.user.is_authenticated
    pessoa = request.user if autenticado else None

    return render(
        request,
        "workspace/home.html",
        {
            "autenticado": autenticado,
            "nome": _primeiro_nome(request) if autenticado else "",
            "apps": apps_disponiveis(pessoa),
        },
    )


def _primeiro_nome(request: HttpRequest) -> str:
    """Só o primeiro nome — 'Olá Christopher', não 'Olá Christopher Ataide'."""
    completo = (request.user.get_full_name() or request.user.get_username()).strip()
    return completo.split()[0] if completo else ""
