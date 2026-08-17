"""Pessoas e papéis — a tela de quem aprova o quê.

Área de administração, e não de autoatendimento: exige identidade e a permissão
`rh.admin`. Ela responde duas perguntas que hoje só o `/admin/` responde, e mal:

1. quem aprova cada área — e **qual área está sem ninguém**;
2. que papéis uma pessoa tem, com escopo e prazo.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from identidade.models import AtribuicaoPapel, ESCOPO_CHOICES, Papel
from identidade.services import administracao as adm
from identidade.services.administracao import AdministracaoError
from workspace.services import mapa_aprovacao as mapa


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


def _garantir_acesso(request: HttpRequest) -> None:
    if not adm.pode_administrar(request.user, cache=_cache(request)):
        raise PermissionDenied("Esta tela é de quem administra papéis.")


@login_required
def pessoas(request: HttpRequest) -> HttpResponse:
    """A lista, com o mapa de aprovação por área em cima.

    O mapa vem primeiro de propósito: a pergunta que traz alguém a esta tela é
    quase sempre "por que o pedido de férias não chegou em ninguém?", e a
    resposta costuma ser uma área sem aprovador.
    """
    _garantir_acesso(request)

    lotacoes = list(adm.pessoas_administraveis())
    por_pessoa = []
    for lotacao in lotacoes:
        por_pessoa.append(
            {
                "lotacao": lotacao,
                "pessoa": lotacao.user,
                "atribuicoes": list(adm.atribuicoes_de(lotacao.user)),
            }
        )

    return render(
        request,
        "workspace/pessoas.html",
        {
            "pessoas": por_pessoa,
            "mapa": mapa.resumo_de_aprovacao(),
            "papeis": adm.papeis_concedíveis(),
            "escopos": ESCOPO_CHOICES,
        },
    )


@login_required
def conceder_papel(request: HttpRequest) -> HttpResponse:
    _garantir_acesso(request)
    if request.method != "POST":
        return redirect(reverse("workspace:pessoas"))

    from contas.models import Pessoa

    try:
        alvo = get_object_or_404(Pessoa, pk=request.POST.get("pessoa"))
        papel = get_object_or_404(Papel, pk=request.POST.get("papel"))
        adm.conceder(
            pessoa=alvo,
            papel=papel,
            escopo=request.POST.get("escopo", ""),
            quem=request.user,
            justificativa=request.POST.get("justificativa", ""),
            vigencia_fim=request.POST.get("vigencia_fim") or None,
        )
    except AdministracaoError as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, f"{papel} concedido a {alvo}.")

    return redirect(reverse("workspace:pessoas"))


@login_required
def revogar_papel(request: HttpRequest, pk: int) -> HttpResponse:
    _garantir_acesso(request)
    if request.method != "POST":
        return redirect(reverse("workspace:pessoas"))

    atribuicao = get_object_or_404(AtribuicaoPapel, pk=pk)
    try:
        adm.revogar(atribuicao, request.user, motivo=request.POST.get("motivo", ""))
    except AdministracaoError as erro:
        messages.error(request, str(erro))
    else:
        messages.success(
            request, f"{atribuicao.papel} encerrado para {atribuicao.user}."
        )

    return redirect(reverse("workspace:pessoas"))
