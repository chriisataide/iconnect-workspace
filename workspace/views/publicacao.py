"""Leitura de um comunicado ou notícia."""

from __future__ import annotations

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from workspace.models import Publicacao


def detalhe(request: HttpRequest, pk: int) -> HttpResponse:
    """Uma publicação. 404 se não estiver no ar.

    Usa o mesmo `publicadas()` da home: rascunho e agendado não vazam por URL
    adivinhada. Fosse `get_object_or_404(Publicacao, pk=pk)`, qualquer pessoa
    leria o comunicado de amanhã hoje.
    """
    publicacao = Publicacao.objects.publicadas().filter(pk=pk).first()
    if publicacao is None:
        raise Http404("Publicação não encontrada ou fora do ar.")

    return render(request, "workspace/publicacao.html", {"publicacao": publicacao})
