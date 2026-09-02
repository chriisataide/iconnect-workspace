"""O painel de exceções — a lista de regras, e o que cada uma achou.

## Por que a avaliação acontece no GET

Ela é **cara** e é **fresca**. Cara porque são dezoito regras varrendo tabelas;
fresca porque o número que o painel mostra tem de ser o de agora — um painel de
exceções que mostra o retrato de ontem manda alguém consertar o que já foi
consertado.

A escolha aqui foi pela frescura, e o preço é uma tela lenta que se abre de
propósito. Ela não está na home, não está no trilho de todo mundo, e ninguém
cai nela por acidente.

O GET **não escreve**. Quem grava o retrato é `avaliar_excecoes`, o comando —
e é dele que sai a tendência que a tela mostra ao lado da contagem.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from workspace.models.excecao import RegraExcecao
from workspace.services import excecoes as svc


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


@login_required
def excecoes(request: HttpRequest) -> HttpResponse:
    try:
        panorama = svc.painel(request.user, cache=_cache(request))
    except svc.SemExcecoes as sem:
        # 403 e não lista vazia. Lista vazia para quem nunca vai ter regra é a
        # mesma mentira de um painel de zeros: faz a pessoa achar que está tudo
        # em ordem, quando na verdade ela não está olhando nada.
        raise PermissionDenied(str(sem))

    return render(request, "workspace/excecoes.html", panorama)


@require_POST
@login_required
def notificar_excecao(request: HttpRequest, chave: str) -> HttpResponse:
    """Avisa quem responde pela regra.

    POST porque avisa gente. Um `GET` faria um *prefetch* do navegador mandar
    notificação — e a segunda vez que isso acontecesse, ninguém mais leria as
    notificações do produto.
    """
    regra = RegraExcecao.objects.filter(chave=chave, ativa=True).first()
    if regra is None:
        raise Http404("Regra desconhecida ou desligada.")

    visiveis = {r.chave for r in svc.regras_de(request.user, cache=_cache(request))}
    if regra.chave not in visiveis:
        # Quem não vê a regra não avisa por ela. Sem esta checagem, o painel
        # viraria um jeito de mandar notificação para departamentos alheios.
        raise PermissionDenied("Você não responde por esta regra.")

    avaliacao = svc.avaliar(regra)
    if not avaliacao.avaliada:
        messages.warning(
            request,
            f"{regra.titulo}: {avaliacao.motivo} Ninguém foi avisado.",
        )
        return redirect("workspace:excecoes")

    quantos = svc.notificar(avaliacao, quem=request.user)
    if quantos:
        messages.success(
            request, f"{quantos} pessoa(s) avisada(s) sobre {regra.titulo.lower()}."
        )
    else:
        # "Ninguém tem o papel" é um achado, e não um erro de operação — é a
        # regra 2 aparecendo por outro caminho.
        messages.warning(
            request,
            f"Ninguém ocupa o papel que responde por {regra.titulo.lower()} — "
            "não havia quem avisar.",
        )
    return redirect("workspace:excecoes")
