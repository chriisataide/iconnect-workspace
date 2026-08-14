"""Correspondências — a minha, e a fila de quem opera a recepção.

Uma tela, dois públicos. Quem tem `cor.registrar` vê a fila e o formulário de
registro; todo mundo vê o que chegou para si. Duas telas separadas fariam a
recepção precisar decorar duas URLs, e o resto da empresa tropeçar na fila.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from workspace.acesso import pessoa_da_requisicao
from identidade.services.autorizacao import pode
from workspace.models.correspondencia import Correspondencia, TipoCorrespondencia
from workspace.services import correspondencia as cor


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


def correspondencias(request: HttpRequest) -> HttpResponse:
    cache = _cache(request)
    pessoa = pessoa_da_requisicao(request)
    opera = pode(pessoa, cor.PERMISSAO_REGISTRAR, cache=cache)

    return render(
        request,
        "workspace/correspondencias.html",
        {
            "minhas": cor.minhas(pessoa),
            "aguardando": cor.aguardando_de(pessoa),
            "opera_recepcao": opera,
            "fila": list(cor.fila(pessoa, cache=cache)) if opera else [],
            "nao_identificadas": (
                list(cor.nao_identificadas(pessoa, cache=cache)) if opera else []
            ),
            "tipos": TipoCorrespondencia.choices,
            # Só quem tem lotação: a lista de destinatários é o organograma, não
            # a tabela de usuários — os 1432 do iConnect não trabalham aqui.
            "pessoas": get_user_model().objects.filter(lotacao__isnull=False).order_by(
                "nome", "email"
            ),
        },
    )


def registrar_correspondencia(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect(reverse("workspace:correspondencias"))

    pessoa = pessoa_da_requisicao(request)
    destinatario = None
    if request.POST.get("destinatario"):
        destinatario = get_user_model().objects.filter(pk=request.POST["destinatario"]).first()

    try:
        registro = cor.registrar(
            pessoa,
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


def entregar_correspondencia(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect(reverse("workspace:correspondencias"))

    registro = get_object_or_404(Correspondencia, pk=pk)
    pessoa = pessoa_da_requisicao(request)
    try:
        cor.entregar(registro, pessoa, cache=_cache(request))
    except cor.CorrespondenciaError as falha:
        messages.error(request, str(falha))
    else:
        messages.success(request, "Retirada registrada.")

    return redirect(reverse("workspace:correspondencias"))


def identificar_correspondencia(request: HttpRequest, pk: int) -> HttpResponse:
    """Aponta o destinatário do que chegou sem nome — e avisa na hora.

    É o único momento em que a pessoa pode saber que algo chegou para ela: no
    registro, ninguém sabia quem era.
    """
    if request.method != "POST":
        return redirect(reverse("workspace:correspondencias"))

    registro = get_object_or_404(Correspondencia, pk=pk)
    pessoa = pessoa_da_requisicao(request)
    destinatario = get_user_model().objects.filter(pk=request.POST.get("destinatario")).first()
    if destinatario is None:
        messages.error(request, "Escolha o destinatário.")
        return redirect(reverse("workspace:correspondencias"))

    try:
        cor.identificar(registro, destinatario, pessoa, cache=_cache(request))
    except cor.CorrespondenciaError as falha:
        messages.error(request, str(falha))
    else:
        nome = destinatario.get_short_name() or destinatario.get_username()
        messages.success(request, f"Identificada para {nome}, que foi avisado.")

    return redirect(reverse("workspace:correspondencias"))
