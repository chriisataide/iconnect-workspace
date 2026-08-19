"""Leitura de um comunicado ou notícia."""

from __future__ import annotations

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from workspace.models import Publicacao


def detalhe(request: HttpRequest, pk: int) -> HttpResponse:
    """Uma publicação. 404 quando não está no ar OU não é para esta pessoa.

    `publicadas()` não basta, e a diferença é o §48. Ela responde "está no ar?"
    e ignora o público-alvo, que nasceu no §9 — então o comunicado endereçado ao
    Financeiro era lido por qualquer pessoa que tivesse o número na URL, e o
    número saía da própria busca.

    `para(request.user)` é o mesmo filtro da home, e é de propósito que seja o
    MESMO: duas definições de "quem vê isto" divergem, e a que diverge é sempre
    a que esquece um caso.

    `request.user` e não `pessoa_da_requisicao()`: aquela devolve uma pessoa de
    REFERÊNCIA para o visitante anônimo, e usá-la aqui entregaria a ele o
    comunicado do departamento dela. Anônimo cai no ramo sem lotação e recebe só
    o que é geral.

    404 e não 403: dizer "existe, mas não é para você" já conta que existe um
    comunicado dirigido a outra área — e o título costuma ser a informação.
    """
    publicacao = Publicacao.objects.para(request.user).filter(pk=pk).first()
    if publicacao is None:
        raise Http404("Publicação não encontrada ou fora do seu alcance.")

    return render(request, "workspace/publicacao.html", {"publicacao": publicacao})
