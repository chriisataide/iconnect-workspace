"""Universidade Corporativa — o que eu preciso ter em dia, e quem está fora.

Duas telas com públicos diferentes: `universidade` é a da pessoa (as MINHAS
habilitações); `universidade_painel` é a de quem responde pela conformidade —
R.H., SESMT e diretoria.

Fechadas as duas: habilitação vencida é informação sobre uma pessoa com nome, e
a lista de quem está irregular é exatamente o tipo de dado que não pode ficar
aberto no hub.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from identidade.services.autorizacao import pode
from workspace.services import habilitacao as hab


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


@login_required
def universidade(request: HttpRequest) -> HttpResponse:
    """As minhas habilitações. Aberta a qualquer pessoa autenticada."""
    minhas = list(hab.minhas(request.user))
    return render(
        request,
        "workspace/universidade/minhas.html",
        {
            "matriculas": minhas,
            "pendencias": hab.pendencias_de(request.user),
            "ve_painel": pode(request.user, hab.PERMISSAO_GERIR, cache=_cache(request)),
        },
    )


@login_required
def universidade_painel(request: HttpRequest) -> HttpResponse:
    """O painel do §30. Só para quem responde pela conformidade."""
    if not pode(request.user, hab.PERMISSAO_GERIR, cache=_cache(request)):
        # 403 e não painel zerado, pela mesma razão dos indicadores: uma tela de
        # conformidade toda em zero para quem nunca vai ter dado faz a pessoa
        # achar que a empresa está em dia.
        raise PermissionDenied("Esta tela é de quem responde pela conformidade.")

    return render(
        request,
        "workspace/universidade/painel.html",
        {**hab.panorama(), "por_pessoa": hab.por_pessoa()},
    )
