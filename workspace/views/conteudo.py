"""Documentação — o acervo, e a leitura de um documento."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from workspace.acesso import pessoa_da_requisicao
from workspace.models.conteudo import Documento
from workspace.services import conteudo as cnt


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


def documentacao(request: HttpRequest) -> HttpResponse:
    """A vitrine, agrupada por tipo.

    Duas pessoas nesta view, de propósito:

    - `pessoa` decide o ALCANCE — quais documentos o acervo mostra. É onde a
      pessoa de referência do hub aberto continua valendo, porque saber que um
      POP existe é informação institucional.
    - `quem` decide o que é PESSOAL — quantas leituras faltam confirmar. Isso é
      de uma pessoa, e o visitante anônimo estava vendo o número de outra: o
      contador dizia "3 pendentes" para quem nunca entrou, contando os
      documentos que uma conta específica ainda não tinha lido.
    """
    cache = _cache(request)
    pessoa = pessoa_da_requisicao(request)
    quem = request.user if request.user.is_authenticated else None

    grupos = [
        {"rotulo": rotulo, "documentos": documentos}
        for rotulo, documentos in cnt.agrupado_para(pessoa, cache=cache).items()
    ]
    return render(
        request,
        "workspace/documentacao.html",
        {
            "grupos": grupos,
            "autenticado": quem is not None,
            "pendentes": (
                len(cnt.pendentes_de_leitura(quem, cache=cache)) if quem else 0
            ),
            "total": sum(len(g["documentos"]) for g in grupos),
        },
    )


def documento(request: HttpRequest, slug: str) -> HttpResponse:
    """A leitura. Vencido e revogado abrem, com aviso — ver `cnt.pode_ver`."""
    doc = get_object_or_404(Documento.objects.select_related("dono", "revoga"), slug=slug)
    cache = _cache(request)
    pessoa = pessoa_da_requisicao(request)

    if not cnt.pode_ver(doc, pessoa, cache=cache):
        raise PermissionDenied("Você não tem acesso a este documento.")

    substituto = doc.revogado_por.filter(situacao="vigente").first()
    return render(
        request,
        "workspace/documento.html",
        {
            "documento": doc,
            "autenticado": True,
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

    Pelo mesmo motivo, `@login_required`: é a declaração de que uma pessoa
    NOMEADA leu um normativo. Ler o documento continua aberto; assinar que leu,
    não — a confirmação anônima entraria com o nome de outra pessoa, e é essa
    linha que a empresa apresenta quando precisa provar conformidade.
    """
    doc = get_object_or_404(Documento, slug=slug)
    pessoa = request.user
    if request.method != "POST":
        return redirect(reverse("workspace:documento", args=(slug,)))

    if not cnt.pode_ver(doc, pessoa, cache=_cache(request)):
        raise PermissionDenied("Você não tem acesso a este documento.")

    try:
        cnt.confirmar(doc, pessoa)
    except cnt.ConteudoError as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, f"Leitura de {doc.titulo} confirmada.")

    return redirect(reverse("workspace:documento", args=(slug,)))
