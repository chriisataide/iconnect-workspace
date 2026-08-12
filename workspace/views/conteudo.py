"""Documentação — o acervo, e a leitura de um documento.

**Públicas**, como o resto do hub: quem está na rede da empresa vê a política de
viagens sem senha. O login entra quando a pessoa vai *confirmar* leitura — porque
confirmação sem identidade não é trilha de auditoria, é linha em branco.

Documento de departamento não aparece para anônimo: `subjects_de()` de quem não
está logado devolve só `["*"]`.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from workspace.models.conteudo import Documento
from workspace.services import conteudo as cnt


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


def documentacao(request: HttpRequest) -> HttpResponse:
    """A vitrine, agrupada por tipo."""
    cache = _cache(request)
    pessoa = request.user if request.user.is_authenticated else None

    grupos = [
        {"rotulo": rotulo, "documentos": documentos}
        for rotulo, documentos in cnt.agrupado_para(pessoa, cache=cache).items()
    ]
    return render(
        request,
        "workspace/documentacao.html",
        {
            "grupos": grupos,
            "autenticado": request.user.is_authenticated,
            "pendentes": len(cnt.pendentes_de_leitura(pessoa, cache=cache)),
            "total": sum(len(g["documentos"]) for g in grupos),
        },
    )


def documento(request: HttpRequest, slug: str) -> HttpResponse:
    """A leitura. Vencido e revogado abrem, com aviso — ver `cnt.pode_ver`."""
    doc = get_object_or_404(Documento.objects.select_related("dono", "revoga"), slug=slug)
    cache = _cache(request)
    pessoa = request.user if request.user.is_authenticated else None

    if not cnt.pode_ver(doc, pessoa, cache=cache):
        raise PermissionDenied("Você não tem acesso a este documento.")

    substituto = doc.revogado_por.filter(situacao="vigente").first()
    return render(
        request,
        "workspace/documento.html",
        {
            "documento": doc,
            "autenticado": request.user.is_authenticated,
            "ja_confirmou": cnt.ja_confirmou(doc, pessoa),
            "cobertura": cnt.cobertura_de_leitura(doc),
            "e_dono": getattr(pessoa, "pk", None) == doc.dono_id,
            # Documento revogado sem para onde ir é um beco: a pessoa descobre
            # que o texto não vale e não sabe qual vale.
            "substituto": substituto,
        },
    )


@login_required
def confirmar_leitura(request: HttpRequest, slug: str) -> HttpResponse:
    """POST apenas: confirmação é escrita, e GET não muda estado.

    Sem isso, o pré-carregamento de link do navegador registraria conformidade
    que a pessoa nunca declarou — e é exatamente esse registro que se leva para
    uma audiência.
    """
    doc = get_object_or_404(Documento, slug=slug)
    if request.method != "POST":
        return redirect(reverse("workspace:documento", args=(slug,)))

    if not cnt.pode_ver(doc, request.user, cache=_cache(request)):
        raise PermissionDenied("Você não tem acesso a este documento.")

    try:
        cnt.confirmar(doc, request.user)
    except cnt.ConteudoError as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, f"Leitura de {doc.titulo} confirmada.")

    return redirect(reverse("workspace:documento", args=(slug,)))
