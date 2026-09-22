"""Planos de ação (13) — o que a exceção cobra, e o que foi respondido.

## Limiar gera obrigação

`/workspace/planos/` mostra os quatro estados do benchmark — em andamento no
prazo, fora do prazo, resolvido, não resolvido — mais a **dívida**: ocorrências
de regras com limiar que ainda não têm plano.

## A fronteira

GET é consulta, para quem vê a regra. POST — abrir e fechar — exige
`pla.responder` **e** o papel que atende a regra. Assinar o que a empresa vai
fazer sobre um contrato deficitário é ato de quem responde por ele.

## Fechar não é declarar

O botão de fechar manda a regra rodar de novo. Quem fecha escreve o que
aconteceu; quem decide se resolveu é a regra. Ver `services/planos.py`.
"""

from __future__ import annotations

from datetime import datetime

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from workspace.models.plano import PlanoAcao
from workspace.services import planos as svc


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


@login_required
def planos(request: HttpRequest) -> HttpResponse:
    try:
        panorama = svc.painel(request.user, cache=_cache(request))
    except svc.SemPlanos as sem:
        raise PermissionDenied(str(sem))
    return render(request, "workspace/planos/planos.html", panorama)


@login_required
def plano_novo(request: HttpRequest) -> HttpResponse:
    """O formulário de resposta a uma ocorrência.

    A ocorrência chega por query string — `?regra=…&ocorrencia=…` —, vinda do
    botão do painel de exceções. O formulário **não** pré-preenche justificativa
    nem ação: pedido com dado adivinhado é pior que pedido vazio, e é a mesma
    regra do `?origem=` do catálogo.
    """
    chave = request.GET.get("regra", "") or request.POST.get("regra", "")
    regra = svc.regra_visivel(chave, request.user, cache=_cache(request))
    if regra is None:
        raise Http404("Regra desconhecida, desligada ou fora do seu escopo.")
    if not svc.pode_responder(regra, request.user, cache=_cache(request)):
        raise PermissionDenied("Responder por esta regra exige o papel que a atende.")

    ocorrencia_chave = (
        request.GET.get("ocorrencia", "") or request.POST.get("ocorrencia", "")
    ).strip()
    ocorrencia = svc.ocorrencia_de(regra, ocorrencia_chave)

    if request.method == "POST":
        prazo = None
        if request.POST.get("prazo"):
            try:
                prazo = datetime.strptime(request.POST["prazo"], "%Y-%m-%d").date()
            except ValueError:
                messages.warning(request, "Data de prazo inválida — usei o padrão.")

        responsavel = get_user_model().objects.filter(
            pk=request.POST.get("responsavel") or 0, is_active=True
        ).first()

        try:
            plano = svc.abrir(
                regra,
                ocorrencia_chave,
                request.user,
                justificativa=request.POST.get("justificativa", ""),
                acao=request.POST.get("acao", ""),
                responsavel=responsavel or request.user,
                prazo=prazo,
                cache=_cache(request),
            )
        except svc.PlanoError as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, f"Plano registrado para {plano.titulo}.")
            return redirect("workspace:plano", pk=plano.pk)

    return render(
        request,
        "workspace/planos/plano_editar.html",
        {
            "regra": regra,
            "ocorrencia": ocorrencia,
            "ocorrencia_chave": ocorrencia_chave,
            "prazo_sugerido": svc.prazo_de(regra),
            # Os titulares do papel da regra. É a lista curta e certa: o
            # responsável por um plano de margem é quem responde por margem, e
            # oferecer a empresa inteira num `select` faria a escolha cair em
            # quem estivesse mais perto no alfabeto.
            "candidatos": svc.titulares_da_regra(regra),
        },
    )


@login_required
def plano(request: HttpRequest, pk: int) -> HttpResponse:
    alvo = get_object_or_404(PlanoAcao, pk=pk)
    regra = svc.regra_visivel(alvo.regra_chave, request.user, cache=_cache(request))
    if regra is None:
        raise PermissionDenied("Este plano é de uma regra que você não acompanha.")

    return render(
        request,
        "workspace/planos/plano.html",
        {
            "plano": alvo,
            "regra": regra,
            "verificacoes": list(alvo.verificacoes.all()),
            "pode_responder": svc.pode_responder(
                regra, request.user, cache=_cache(request)
            ),
        },
    )


@require_POST
@login_required
def fechar_plano(request: HttpRequest, pk: int) -> HttpResponse:
    """Fecha o plano — e o desfecho sai da regra, não do formulário."""
    alvo = get_object_or_404(PlanoAcao, pk=pk)
    regra = svc.regra_visivel(alvo.regra_chave, request.user, cache=_cache(request))
    if regra is None:
        raise PermissionDenied("Este plano é de uma regra que você não acompanha.")
    if not svc.pode_responder(regra, request.user, cache=_cache(request)):
        raise PermissionDenied("Fechar este plano exige o papel que atende a regra.")

    try:
        fechado = svc.fechar(
            alvo,
            request.user,
            desfecho=request.POST.get("desfecho", ""),
            cache=_cache(request),
        )
    except svc.PlanoError as erro:
        messages.error(request, str(erro))
    else:
        if fechado.situacao == "resolvido":
            messages.success(request, "A regra não encontra mais a ocorrência.")
        else:
            # A mensagem diz o que a regra respondeu, e não o que quem fechou
            # escreveu. É onde a diferença entre esforço e resultado aparece
            # para a pessoa que acabou de clicar.
            messages.warning(
                request,
                "Fechado como NÃO resolvido: a regra ainda encontra esta "
                "ocorrência.",
            )
    return redirect("workspace:plano", pk=pk)
