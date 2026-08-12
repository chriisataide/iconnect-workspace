"""Correspondências — a minha, e a fila de quem opera a recepção.

Uma tela, dois públicos. Quem tem `cor.registrar` vê a fila e o formulário de
registro; todo mundo vê o que chegou para si. Duas telas separadas fariam a
recepção precisar decorar duas URLs, e o resto da empresa tropeçar na fila.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from identidade.services.autorizacao import pode
from workspace.models.correspondencia import Correspondencia, TipoCorrespondencia
from workspace.services import correspondencia as cor


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


@login_required
def correspondencias(request: HttpRequest) -> HttpResponse:
    cache = _cache(request)
    opera = pode(request.user, cor.PERMISSAO_REGISTRAR, cache=cache)

    return render(
        request,
        "workspace/correspondencias.html",
        {
            "minhas": cor.minhas(request.user),
            "aguardando": cor.aguardando_de(request.user),
            "opera_recepcao": opera,
            "fila": list(cor.fila(request.user, cache=cache)) if opera else [],
            "nao_identificadas": (
                list(cor.nao_identificadas(request.user, cache=cache)) if opera else []
            ),
            "tipos": TipoCorrespondencia.choices,
            # Só quem tem lotação: a lista de destinatários é o organograma, não
            # a tabela de usuários — os 1432 do iConnect não trabalham aqui.
            "pessoas": User.objects.filter(lotacao__isnull=False).order_by(
                "first_name", "username"
            ),
        },
    )


@login_required
def registrar_correspondencia(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect(reverse("workspace:correspondencias"))

    destinatario = None
    if request.POST.get("destinatario"):
        destinatario = User.objects.filter(pk=request.POST["destinatario"]).first()

    try:
        registro = cor.registrar(
            request.user,
            tipo=request.POST.get("tipo", ""),
            remetente=(request.POST.get("remetente") or "").strip(),
            descricao=(request.POST.get("descricao") or "").strip(),
            destinatario=destinatario,
            nome_no_envelope=(request.POST.get("nome_no_envelope") or "").strip(),
            cache=_cache(request),
        )
    except cor.CorrespondenciaError as falha:
        messages.error(request, str(falha))
    else:
        avisado = " O destinatário foi avisado." if registro.destinatario_id else ""
        messages.success(request, f"{registro.get_tipo_display()} registrada.{avisado}")

    return redirect(reverse("workspace:correspondencias"))


@login_required
def entregar_correspondencia(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect(reverse("workspace:correspondencias"))

    registro = get_object_or_404(Correspondencia, pk=pk)
    try:
        cor.entregar(registro, request.user, cache=_cache(request))
    except cor.CorrespondenciaError as falha:
        messages.error(request, str(falha))
    else:
        messages.success(request, "Retirada registrada.")

    return redirect(reverse("workspace:correspondencias"))


@login_required
def identificar_correspondencia(request: HttpRequest, pk: int) -> HttpResponse:
    """Aponta o destinatário do que chegou sem nome — e avisa na hora.

    É o único momento em que a pessoa pode saber que algo chegou para ela: no
    registro, ninguém sabia quem era.
    """
    if request.method != "POST":
        return redirect(reverse("workspace:correspondencias"))

    registro = get_object_or_404(Correspondencia, pk=pk)
    destinatario = User.objects.filter(pk=request.POST.get("destinatario")).first()
    if destinatario is None:
        messages.error(request, "Escolha o destinatário.")
        return redirect(reverse("workspace:correspondencias"))

    try:
        cor.identificar(registro, destinatario, request.user, cache=_cache(request))
    except cor.CorrespondenciaError as falha:
        messages.error(request, str(falha))
    else:
        nome = destinatario.get_short_name() or destinatario.get_username()
        messages.success(request, f"Identificada para {nome}, que foi avisado.")

    return redirect(reverse("workspace:correspondencias"))
