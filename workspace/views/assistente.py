"""O assistente do portal — o painel e a resposta.

Aberto como o resto do hub: a base de conhecimento é institucional, e uma parede
de login na frente de "como peço férias" contradiz o produto inteiro. O que o
assistente NÃO faz é agir — ele devolve o link, e o link é que exige sessão
quando for o caso.
"""

from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from workspace.services import assistente as asst


def perguntar(request: HttpRequest) -> JsonResponse:
    """A resposta, em JSON, para o painel flutuante.

    `GET` porque perguntar não muda nada — e porque assim a mesma URL serve de
    página de resultado para quem está sem JS.
    """
    resposta = asst.responder(
        request.GET.get("q", ""), area=request.GET.get("area", "")
    )
    return JsonResponse(
        {
            "texto": resposta.texto,
            "acoes": resposta.acoes,
            "area": resposta.area,
            "sem_resposta": resposta.sem_resposta,
            # §56 — quem respondeu. A tela marca a resposta gerada: texto
            # escrito e conferido por alguém da empresa tem outro peso que texto
            # gerado por aproximação, e apagar a diferença é o que faz alguém
            # citar o portal numa reunião com informação que ninguém revisou.
            "de_ia": resposta.de_ia,
            "pergunta": resposta.faq.pergunta if resposta.faq else "",
        }
    )


def ajuda(request: HttpRequest) -> HttpResponse:
    """A base inteira, numa página.

    Existe por três razões, e nenhuma é redundância com o painel: é o que
    funciona sem JS, é o que o buscador do navegador encontra com ⌘F, e é para
    onde o painel manda quem quer ler tudo em vez de perguntar.
    """
    return render(
        request,
        "workspace/ajuda.html",
        {"grupos": asst.por_area(), "busca": request.GET.get("q", "")},
    )
