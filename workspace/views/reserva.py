"""Reservas — a agenda antes do formulário.

A tela mostra o que JÁ está ocupado hoje em cada recurso, e só então o campo de
horário. Formulário que aceita qualquer hora e responde "conflito" depois do
envio faz a pessoa tentar por adivinhação.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from workspace.models.reserva import Recurso, Reserva
from workspace.services import reserva as res

# Horário comercial, para os atalhos da tela. Não é regra de negócio: a reserva
# aceita qualquer hora, e a maioria das reservas cai aqui.
HORARIOS = ("08:00", "09:00", "10:00", "11:00", "13:00", "14:00", "15:00", "16:00", "17:00")


def _dia_pedido(request: HttpRequest):
    """O dia da agenda. Hoje quando não vem, ou quando vem inválido.

    Data inválida na URL não pode virar erro 500: o parâmetro é editável na barra
    de endereço, e a resposta certa a `?dia=abacaxi` é mostrar hoje.
    """
    bruto = request.GET.get("dia", "")
    if bruto:
        try:
            return datetime.strptime(bruto, "%Y-%m-%d").date()
        except ValueError:
            pass
    return timezone.localdate()


def reservas(request: HttpRequest) -> HttpResponse:
    """Vitrine dos recursos, com a agenda do dia em cada um."""
    dia = _dia_pedido(request)
    pessoa = request.user if request.user.is_authenticated else None

    grupos = []
    for rotulo, recursos in res.agrupados_para(pessoa).items():
        grupos.append(
            {
                "rotulo": rotulo,
                "recursos": [
                    {"recurso": r, "agenda": list(res.agenda_do_dia(r, dia))}
                    for r in recursos
                ],
            }
        )

    return render(
        request,
        "workspace/reservas.html",
        {
            "grupos": grupos,
            "dia": dia,
            "ontem": dia - timedelta(days=1),
            "amanha": dia + timedelta(days=1),
            "e_hoje": dia == timezone.localdate(),
            "autenticado": request.user.is_authenticated,
            "total": sum(len(g["recursos"]) for g in grupos),
            "minhas_futuras": (
                res.minhas(pessoa).confirmadas().futuras().count() if pessoa else 0
            ),
        },
    )


@login_required
def reservar(request: HttpRequest, codigo: str) -> HttpResponse:
    """Formulário de um recurso, com a agenda do dia ao lado."""
    recurso = get_object_or_404(Recurso, codigo=codigo, ativo=True)
    dia = _dia_pedido(request)
    erro = ""

    if request.method == "POST":
        inicio, fim, erro = _janela_do_post(request)
        if not erro:
            try:
                res.reservar(
                    recurso,
                    request.user,
                    inicio,
                    fim,
                    motivo=(request.POST.get("motivo") or "").strip(),
                )
            except res.ReservaError as falha:
                erro = str(falha)
            else:
                messages.success(
                    request,
                    f"{recurso.nome} reservado para "
                    f"{timezone.localtime(inicio):%d/%m às %H:%M}.",
                )
                return redirect(reverse("workspace:minhas_reservas"))

    return render(
        request,
        "workspace/reservar.html",
        {
            "recurso": recurso,
            "agenda": list(res.agenda_do_dia(recurso, dia)),
            "dia": dia,
            "horarios": HORARIOS,
            "erro": erro,
            "valores": request.POST if request.method == "POST" else {},
        },
    )


def _janela_do_post(request: HttpRequest):
    """`(inicio, fim, erro)` a partir do formulário.

    Data e horas separadas, e não dois `datetime-local`: a pessoa reserva "dia 12,
    das 14 às 16", e dois campos de data-hora fazem ela digitar o dia duas vezes —
    e errar um dos dois.
    """
    dia = (request.POST.get("dia") or "").strip()
    de = (request.POST.get("de") or "").strip()
    ate = (request.POST.get("ate") or "").strip()

    if not (dia and de and ate):
        return None, None, "Informe o dia, a hora de início e a de fim."

    try:
        inicio = timezone.make_aware(datetime.strptime(f"{dia} {de}", "%Y-%m-%d %H:%M"))
        fim = timezone.make_aware(datetime.strptime(f"{dia} {ate}", "%Y-%m-%d %H:%M"))
    except ValueError:
        return None, None, "Data ou hora inválida."

    return inicio, fim, ""


@login_required
def minhas_reservas(request: HttpRequest) -> HttpResponse:
    consulta = res.minhas(request.user)
    return render(
        request,
        "workspace/minhas_reservas.html",
        {
            "reservas": consulta,
            "futuras": consulta.confirmadas().futuras().count(),
        },
    )


@login_required
def cancelar_reserva(request: HttpRequest, pk: int) -> HttpResponse:
    reserva = get_object_or_404(Reserva, pk=pk)
    if request.method == "POST":
        try:
            res.cancelar(reserva, request.user)
            messages.success(request, f"Reserva de {reserva.recurso} cancelada.")
        except res.ReservaError as falha:
            messages.error(request, str(falha))
    return redirect(reverse("workspace:minhas_reservas"))
