"""O painel de indicadores — a tela que faltava para o portal se defender.

`@login_required` e `request.user`: o painel agrega o trabalho da empresa
inteira, por área e por pessoa. Não é informação institucional como o catálogo
— é o desempenho de setores e de gente com nome, e a pessoa de referência do
hub aberto não pode servir de crachá para isso.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from workspace.services import indicadores as ind


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


def _periodo(request: HttpRequest) -> int:
    """O período pedido, ou o padrão. Valor fora da lista cai no padrão em vez
    de erro: `?dias=99999` faria uma consulta enorme por uma URL digitada."""
    permitidos = {dias for dias, _ in ind.PERIODOS}
    try:
        pedido = int(request.GET.get("dias", ""))
    except (TypeError, ValueError):
        return ind.PERIODO_PADRAO
    return pedido if pedido in permitidos else ind.PERIODO_PADRAO


@login_required
def indicadores(request: HttpRequest) -> HttpResponse:
    try:
        panorama = ind.panorama(
            request.user, dias=_periodo(request), cache=_cache(request)
        )
    except ind.SemPainel as sem:
        # 403 e não tela zerada, pela mesma razão da fila de atendimento: uma
        # tela de números todos em zero para quem nunca vai ter dado faz a
        # pessoa achar que a empresa parou.
        raise PermissionDenied(str(sem))

    return render(request, "workspace/indicadores.html", panorama)
