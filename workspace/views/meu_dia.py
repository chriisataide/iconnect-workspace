"""Meu dia e a Central de Notificações.

Duas telas com papéis distintos, e a distinção é o desenho:

- **Meu dia** responde *o que exige você*. Só o acionável.
- **Notificações** responde *o que aconteceu*. Histórico, incluindo o que já foi
  resolvido.

Juntar as duas produz uma lista onde o que precisa de ação some no meio do que é
só informação — e é assim que a pessoa para de olhar as duas.
"""

from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from workspace.acesso import pessoa_da_requisicao
from workspace.services import meu_dia as md
from workspace.services import notificacoes as nt

LIMITE_HISTORICO = 60


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


def meu_dia(request: HttpRequest) -> HttpResponse:
    contexto = md.para(pessoa_da_requisicao(request), cache=_cache(request))
    return render(request, "workspace/meu_dia.html", contexto)


def notificacoes(request: HttpRequest) -> HttpResponse:
    """O histórico. Abrir a tela NÃO marca tudo como lido.

    Marcar em massa ao abrir é o padrão que faz a pessoa perder o aviso que ela
    ainda não leu — ela entrou para ver um item e apagou o rastro dos outros.
    Aqui a marcação é uma ação explícita.
    """
    itens = list(nt.para(pessoa_da_requisicao(request), limite=LIMITE_HISTORICO))
    return render(
        request,
        "workspace/notificacoes.html",
        {
            "notificacoes": itens,
            "nao_lidas": sum(1 for n in itens if not n.lida),
            "truncado": len(itens) >= LIMITE_HISTORICO,
        },
    )


def marcar_lidas(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect(reverse("workspace:notificacoes"))

    ids = request.POST.getlist("ids") or None
    quantas = nt.marcar_lidas(pessoa_da_requisicao(request), ids=ids)
    if quantas:
        messages.success(request, f"{quantas} notificação(ões) marcada(s) como lida(s).")

    # Volta para onde a pessoa estava: o sino é clicável de qualquer tela, e
    # devolver todo mundo para a Central quebraria o fluxo de quem só quis
    # limpar o contador.
    destino = request.POST.get("voltar") or reverse("workspace:notificacoes")
    return redirect(destino if destino.startswith("/workspace/") else reverse("workspace:notificacoes"))
