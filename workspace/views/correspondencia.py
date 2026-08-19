"""Correspondências — a minha, e a fila de quem opera a recepção.

Uma tela, dois públicos. Quem tem `cor.registrar` vê a fila e o formulário de
registro; todo mundo vê o que chegou para si. Duas telas separadas fariam a
recepção precisar decorar duas URLs, e o resto da empresa tropeçar na fila.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from identidade.services.autorizacao import pode
from workspace.models.correspondencia import Correspondencia, TipoCorrespondencia
from workspace.services import correspondencia as cor


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


@login_required
def correspondencias(request: HttpRequest) -> HttpResponse:
    """A exceção à regra "ver é aberto", e a razão está no conteúdo da tela.

    Aqui não há tela institucional nenhuma: o que se lê é *quem recebeu
    intimação, de quem, e quando*. Aberta, ela responde isso a respeito da
    primeira pessoa do organograma — e, se essa pessoa operar a recepção, a
    respeito da empresa inteira.

    O guia de QA já dizia "tudo autenticado, é dado de pessoa", e a fila não é
    pública nem para gestores. Manter aberto seria contradizer a única regra
    que esta tela tem.
    """
    cache = _cache(request)
    pessoa = request.user
    opera = pode(pessoa, cor.PERMISSAO_REGISTRAR, cache=cache)

    return render(
        request,
        "workspace/correspondencias.html",
        {
            "minhas": cor.minhas(pessoa),
            # O que a recepção já entregou e ainda espera a palavra de quem
            # recebeu. Em cima da lista porque é a única coisa nesta tela em que
            # a pessoa PRECISA agir.
            "a_confirmar": [c for c in cor.minhas(pessoa) if c.espera_confirmacao],
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


def _chegada(bruta: str | None):
    """A data digitada, ou `None` para "agora".

    Data inválida vira `None` em vez de erro: o registro é o que importa, e
    recusar a correspondência inteira porque alguém digitou `31/02` deixaria a
    intimação sem entrar em lugar nenhum.
    """
    from django.utils.dateparse import parse_date

    if not bruta:
        return None
    dia = parse_date(bruta.strip())
    if dia is None:
        return None
    # Meio-dia e não meia-noite: a data vem sem hora, e `00:00` no fuso local
    # cai no dia anterior em UTC — o prazo da intimação passaria a contar um dia
    # antes do que a recepção escreveu.
    from datetime import datetime, time

    return timezone.make_aware(datetime.combine(dia, time(12, 0)))


@login_required
def confirmar_correspondencia(request: HttpRequest, pk: int) -> HttpResponse:
    """O destinatário diz que recebeu — §6."""
    if request.method != "POST":
        return redirect(reverse("workspace:correspondencias"))

    correspondencia = get_object_or_404(Correspondencia, pk=pk)
    try:
        cor.confirmar(correspondencia, request.user)
    except cor.CorrespondenciaError as falha:
        messages.error(request, str(falha))
    else:
        messages.success(request, "Recebimento confirmado.")

    return redirect(reverse("workspace:correspondencias"))


@login_required
def registrar_correspondencia(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return redirect(reverse("workspace:correspondencias"))

    pessoa = request.user
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
            empresa=(request.POST.get("empresa") or "").strip(),
            numero_rastreio=(request.POST.get("numero_rastreio") or "").strip(),
            observacao=(request.POST.get("observacao") or "").strip(),
            recebido_em=_chegada(request.POST.get("recebido_em")),
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
    pessoa = request.user
    try:
        cor.entregar(registro, pessoa, cache=_cache(request))
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
    pessoa = request.user
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
