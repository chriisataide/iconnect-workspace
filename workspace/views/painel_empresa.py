"""O painel da empresa — §I1.

403 e não tela zerada, como a tela 10: números todos em zero para quem nunca vai
ter dado faz a pessoa achar que a empresa parou.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from workspace.services import painel_empresa as svc


@login_required
def painel(request: HttpRequest) -> HttpResponse:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    try:
        montado = svc.montar(request.user, cache=request.perm_cache)
    except svc.SemResultados as sem:
        raise PermissionDenied(str(sem))

    return render(
        request,
        "workspace/painel.html",
        {
            "painel": montado,
            # Modo apresentação também aqui — §I2. Query string e não tela
            # separada, pela mesma razão da 10: a segunda tela divergiria da
            # primeira na terceira semana.
            "apresentacao": request.GET.get("apresentacao") == "1",
        },
    )
