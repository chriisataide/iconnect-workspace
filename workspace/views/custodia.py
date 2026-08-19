"""EST — o que está com você, e o que está com os outros. §17.

Uma tela, dois públicos, como a de correspondências e pela mesma razão: quem
controla o patrimônio também recebe equipamento, e duas URLs fariam essa pessoa
decorar as duas.

    todo mundo              vê o que está no próprio nome e confirma o recebimento
    log.custodia.ler        vê quem está com o quê
    log.custodia.atribuir   entrega e dá baixa na devolução
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from workspace.models.custodia import Custodia
from workspace.models.estoque import CondicaoMaterial, Material
from workspace.services import custodia as cst
from workspace.services import estoque as est
from workspace.services.custodia import CustodiaError


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


@login_required
def custodia(request: HttpRequest) -> HttpResponse:
    """Autenticada, sem exceção — a lista diz o que cada pessoa levou embora."""
    cache = _cache(request)
    pessoa = request.user
    controla = cst.pode_ler(pessoa, cache=cache)

    minhas = list(cst.minhas(pessoa))
    return render(
        request,
        "workspace/custodia.html",
        {
            "minhas": minhas,
            # Em cima da lista porque é a única coisa nesta tela em que a pessoa
            # PRECISA agir; o resto ela só lê.
            "a_aceitar": [c for c in minhas if c.espera_aceite],
            "em_uso_por_mim": [c for c in minhas if c.em_uso],
            "controla": controla,
            "atribui": cst.pode_atribuir(pessoa, cache=cache),
            "de_terceiros": (
                list(cst.em_poder_de_terceiros(pessoa, cache=cache)) if controla else []
            ),
            "materiais": Material.objects.filter(ativo=True).order_by("nome"),
            "condicoes": CondicaoMaterial.choices,
            # Só quem tem lotação: a lista é o organograma, não a tabela de
            # usuários — e sem lotação não há unidade de onde baixar.
            "pessoas": get_user_model()
            .objects.filter(lotacao__isnull=False)
            .exclude(pk=pessoa.pk)
            .order_by("nome", "email"),
        },
    )


@login_required
def aceitar_custodia(request: HttpRequest, pk: int) -> HttpResponse:
    """A pessoa confirma que recebeu — o §6 da correspondência aplicado aqui."""
    if request.method != "POST":
        return redirect(reverse("workspace:custodia"))

    registro = get_object_or_404(Custodia.objects.select_related("material"), pk=pk)
    try:
        cst.aceitar(registro, request.user)
    except CustodiaError as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, f"Recebimento de {registro.material.nome} confirmado.")

    return redirect(reverse("workspace:custodia"))


@login_required
def entregar_custodia(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect(reverse("workspace:custodia"))

    material = Material.objects.filter(codigo=request.POST.get("material", "")).first()
    destino = (
        get_user_model().objects.filter(pk=request.POST.get("pessoa")).first()
        if (request.POST.get("pessoa") or "").isdigit()
        else None
    )

    try:
        quantidade = int(request.POST.get("quantidade") or 1)
    except (TypeError, ValueError):
        messages.error(request, "A quantidade tem de ser um número.")
        return redirect(reverse("workspace:custodia"))

    if material is None:
        messages.error(request, "Escolha o material.")
        return redirect(reverse("workspace:custodia"))

    try:
        registro = cst.entregar(
            material,
            destino,
            request.user,
            quantidade=quantidade,
            patrimonio=request.POST.get("patrimonio", ""),
            numero_serie=request.POST.get("numero_serie", ""),
            observacao=request.POST.get("observacao", ""),
            cache=_cache(request),
        )
    except (CustodiaError, est.EstoqueError) as erro:
        messages.error(request, str(erro))
    else:
        nome = registro.pessoa.get_short_name() or registro.pessoa.get_full_name()
        messages.success(
            request, f"{material.nome} registrado com {nome}, que foi avisado."
        )

    return redirect(reverse("workspace:custodia"))


@login_required
def devolver_custodia(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect(reverse("workspace:custodia"))

    registro = get_object_or_404(
        Custodia.objects.select_related("material", "pessoa", "unidade"), pk=pk
    )
    try:
        cst.devolver(
            registro,
            request.user,
            request.POST.get("condicao", ""),
            observacao=request.POST.get("observacao", ""),
            cache=_cache(request),
        )
    except (CustodiaError, est.EstoqueError) as erro:
        messages.error(request, str(erro))
    else:
        messages.success(
            request,
            f"{registro.material.nome} devolvido — "
            f"{registro.get_condicao_devolucao_display().lower()}.",
        )

    return redirect(reverse("workspace:custodia"))
