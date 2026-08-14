"""A fila de quem atende — a tela que faltava depois da aprovação.

Área de trabalho, e não vitrine: exige identidade como a bandeja de aprovação,
e pela mesma razão. Assumir, concluir e devolver assinam com um nome, e a fila
em si é o trabalho de um setor — não é informação institucional.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from workspace.models.catalogo import SolicitacaoServico
from workspace.services import atendimento as atd
from workspace.services.atendimento import AtendimentoError


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


@login_required
def fila(request: HttpRequest) -> HttpResponse:
    """O que espera trabalho seu, mais antigo primeiro."""
    cache = _cache(request)
    if not atd.atende_alguma_coisa(request.user, cache=cache):
        # 403 e não uma tela vazia: "sua fila está vazia" para quem não atende
        # nada é mentira, e faz a pessoa esperar por trabalho que nunca vem.
        raise PermissionDenied("Você não atende nenhuma fila de serviço.")

    resumo = atd.resumo_da_fila(request.user, cache=cache)
    return render(
        request,
        "workspace/servicos/fila.html",
        {
            "resumo": resumo,
            "solicitacoes": resumo["solicitacoes"],
            "eu": request.user,
        },
    )


@login_required
def atender(request: HttpRequest, pk: int) -> HttpResponse:
    """Assumir, concluir ou devolver. Uma rota só, porque é uma tela só.

    O que decide é o `name` do botão apertado — três rotas para três verbos do
    mesmo objeto multiplicariam a mesma checagem de permissão por três.
    """
    if request.method != "POST":
        return redirect(reverse("workspace:fila"))

    solicitacao = get_object_or_404(
        SolicitacaoServico.objects.select_related("item", "solicitante"), pk=pk
    )
    acao = request.POST.get("acao", "")
    cache = _cache(request)

    try:
        if acao == "assumir":
            atd.assumir(solicitacao, request.user, cache=cache)
            messages.success(request, f"Você assumiu {solicitacao.item.nome}.")
        elif acao == "concluir":
            atd.concluir(solicitacao, request.user, cache=cache)
            messages.success(
                request,
                f"{solicitacao.item.nome} concluído — o solicitante foi avisado.",
            )
        elif acao == "devolver":
            atd.devolver(
                solicitacao, request.user, request.POST.get("motivo", ""), cache=cache
            )
            messages.success(request, f"{solicitacao.item.nome} devolveu para quem pediu.")
        else:
            messages.error(request, "Ação desconhecida.")
    except AtendimentoError as erro:
        messages.error(request, str(erro))

    return redirect(reverse("workspace:fila"))
