"""RH — a tela de candidaturas. §10.

Não há model novo por trás: a inscrição em vaga interna já é um pedido do
catálogo, com currículo anexado e cadeia de aprovação. O que faltava era a
pergunta invertida — *quem se candidatou a esta vaga* e *a que vagas esta pessoa
já se candidatou* —, e é isso que esta tela responde.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from workspace.services import recrutamento as rec
from workspace.services.recrutamento import RecrutamentoError


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


@login_required
def candidaturas(request: HttpRequest) -> HttpResponse:
    """As candidaturas, filtráveis por vaga e por pessoa.

    A busca NEGATIVA fica na mesma tela e atrás de um `<details>`: ela responde
    uma pergunta legítima — quem nunca se moveu — e não é o que se procura ao
    abrir a tela. Numa aba própria, ninguém a encontraria; aberta por padrão,
    empurraria a lista que importa para baixo.
    """
    cache = _cache(request)
    pessoa_id = request.GET.get("pessoa", "")
    pessoa = (
        get_user_model().objects.filter(pk=pessoa_id).first()
        if pessoa_id.isdigit()
        else None
    )

    try:
        linhas = rec.candidaturas(
            request.user, vaga=request.GET.get("vaga", ""), pessoa=pessoa, cache=cache
        )
        resumo = rec.resumo(request.user, cache=cache)
        nunca = list(rec.nunca_se_candidataram(request.user, cache=cache))
    except RecrutamentoError as erro:
        # 403 e não lista vazia: uma tela de recrutamento zerada para quem nunca
        # vai ter dado faz a pessoa achar que ninguém se candidatou a nada.
        raise PermissionDenied(str(erro)) from erro

    return render(
        request,
        "workspace/candidaturas.html",
        {
            "linhas": linhas,
            "resumo": resumo,
            "nunca": nunca,
            "vaga": request.GET.get("vaga", ""),
            "pessoa_atual": pessoa,
            "pessoas": get_user_model()
            .objects.filter(lotacao__isnull=False)
            .order_by("nome", "email"),
        },
    )
