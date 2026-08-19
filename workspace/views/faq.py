"""A manutenção da base de conhecimento — §3.

A tela de quem RESPONDE. Ela mostra também as perguntas desativadas, que é o
oposto do que o assistente mostra: desativar é o jeito de tirar uma resposta do
ar sem perder o texto enquanto alguém reescreve.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from workspace.models.faq import AreaFAQ, PerguntaFrequente
from workspace.services import assistente as asst


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


def _garantir(request: HttpRequest) -> None:
    if not asst.pode_manter(request.user, cache=_cache(request)):
        raise PermissionDenied("Esta tela é de quem mantém a base de conhecimento.")


@login_required
def faq(request: HttpRequest) -> HttpResponse:
    _garantir(request)
    return render(
        request,
        "workspace/faq/lista.html",
        {
            "perguntas": list(asst.todas_para_manutencao(request.user, cache=_cache(request))),
            "areas": AreaFAQ.choices,
        },
    )


@login_required
def faq_editar(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    """Cria e edita na mesma tela — ver `publicacao_editar` para o porquê."""
    _garantir(request)
    pergunta = get_object_or_404(PerguntaFrequente, pk=pk) if pk else None

    if request.method == "POST":
        try:
            asst.salvar_pergunta(
                request.user,
                pergunta,
                area=request.POST.get("area", ""),
                titulo=request.POST.get("pergunta", ""),
                resposta=request.POST.get("resposta", ""),
                # Uma por linha, e não separadas por vírgula: sinônimo com
                # vírgula dentro existe ("nota fiscal, NF"), e o separador que
                # aparece no conteúdo é o separador que corrompe o dado.
                palavras_chave=(request.POST.get("palavras_chave") or "").splitlines(),
                url_acao=request.POST.get("url_acao", ""),
                rotulo_acao=request.POST.get("rotulo_acao", ""),
                prioridade=request.POST.get("prioridade") or 0,
                ativo=bool(request.POST.get("ativo")),
                cache=_cache(request),
            )
        except asst.FAQError as falha:
            messages.error(request, str(falha))
        else:
            messages.success(request, "Pergunta salva.")
            return redirect(reverse("workspace:faq"))

    return render(
        request,
        "workspace/faq/editar.html",
        {
            "pergunta": pergunta,
            "areas": AreaFAQ.choices,
            "palavras_texto": "\\n".join(pergunta.palavras_chave) if pergunta else "",
        },
    )


@login_required
def faq_excluir(request: HttpRequest, pk: int) -> HttpResponse:
    _garantir(request)
    if request.method != "POST":
        return redirect(reverse("workspace:faq"))

    pergunta = get_object_or_404(PerguntaFrequente, pk=pk)
    titulo = pergunta.pergunta
    asst.excluir_pergunta(pergunta, request.user, cache=_cache(request))
    messages.success(request, f"“{titulo}” foi removida da base.")
    return redirect(reverse("workspace:faq"))
