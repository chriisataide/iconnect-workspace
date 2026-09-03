"""Orçamento anual e revisão (15).

## A decisão que veio antes da tela

Já existiam dois orçados no produto: o **teto de operação**, daqui, que responde
"isto cabe?" na bandeja de aprovação; e o **orçado contábil**, espelhado do
Sankhya, que responde "o mês fechou onde deveria?" nos Resultados.

Eles não se fundem. Esta tela mostra o nosso, e mostra o confronto com o do
espelho **lado a lado, sem desempate**. Ver ADR-036.

## O teto vigente muda por REVISÃO

Não há formulário de edição de orçamento vigente. Há um formulário de revisão,
com motivo obrigatório — e a revisão fica no histórico, com autor e delta por
mês. Antes desta onda, alguém com `is_staff` editava um campo e ninguém ficava
sabendo.

## 403, nunca grade de zeros

Quem não responde por centro de custo nenhum recebe 403. Uma grade zerada para
quem nunca vai ter dado faz a pessoa achar que a empresa não gastou nada.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from workspace.services import orcamento as svc


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


def _ano(request: HttpRequest) -> int:
    bruto = request.GET.get("ano") or request.POST.get("ano") or ""
    if not bruto:
        return timezone.localdate().year
    try:
        ano = int(bruto)
    except ValueError:
        raise Http404("Ano inválido.")
    if not 2000 <= ano <= 2100:
        raise Http404("Ano fora do calendário.")
    return ano


def _centros(request: HttpRequest):
    try:
        return svc.centros_visiveis(request.user, cache=_cache(request))
    except svc.SemOrcamento as sem:
        raise PermissionDenied(str(sem))


@login_required
def orcamento(request: HttpRequest) -> HttpResponse:
    """A lista de centros de custo com o total do ano."""
    centros = _centros(request)
    ano = _ano(request)

    linhas = []
    for centro in centros:
        grade = svc.grade_anual(centro.codigo, ano)
        orcado = [linha.orcado for linha in grade if linha.orcado is not None]
        linhas.append(
            {
                "centro": centro,
                # `None` e não zero quando NENHUM mês tem teto: o total de um
                # orçamento inexistente não é zero, e a tela escreve "—".
                "orcado": sum(orcado, Decimal("0")) if orcado else None,
                "consumido": sum((linha.consumido for linha in grade), Decimal("0")),
                "estourados": [linha.mes for linha in grade if linha.estourado],
            }
        )

    return render(
        request,
        "workspace/orcamento.html",
        {
            "linhas": linhas,
            "ano": ano,
            "anos": range(timezone.localdate().year - 2, timezone.localdate().year + 2),
            "pode_revisar": svc.pode_revisar(request.user, cache=_cache(request)),
        },
    )


@login_required
def orcamento_centro(request: HttpRequest, codigo: str, ano: int) -> HttpResponse:
    """Os doze meses, com as seis colunas."""
    centros = _centros(request)
    centro = next((c for c in centros if c.codigo == codigo), None)
    if centro is None:
        # 403 e não 404: dizer "não existe" a quem apenas não alcança o centro
        # de custo transformaria a tela num verificador de códigos.
        raise PermissionDenied("Este centro de custo não é seu.")
    if not 2000 <= ano <= 2100:
        raise Http404("Ano fora do calendário.")

    grade = svc.grade_anual(codigo, ano)
    return render(
        request,
        "workspace/orcamento_centro.html",
        {
            "centro": centro,
            "ano": ano,
            "grade": grade,
            "revisoes": svc.revisoes(codigo, ano),
            "confronto": svc.confronto_com_o_espelho(codigo, ano),
            "total_orcado": sum(
                (linha.orcado for linha in grade if linha.orcado is not None),
                Decimal("0"),
            ),
            "total_consumido": sum((linha.consumido for linha in grade), Decimal("0")),
            "pode_revisar": svc.pode_revisar(request.user, cache=_cache(request)),
        },
    )


def _deltas(request: HttpRequest) -> dict:
    """Os doze campos do formulário, só os preenchidos e diferentes de zero.

    Campo em branco é "não mexi neste mês", e não "zerei este mês". Tratar os
    dois igual faria uma revisão de julho zerar os outros onze.
    """
    deltas = {}
    for mes in range(1, 13):
        bruto = (request.POST.get(f"delta_{mes}") or "").strip().replace(",", ".")
        if not bruto:
            continue
        try:
            valor = Decimal(bruto)
        except InvalidOperation:
            messages.warning(request, f"Valor inválido em {svc.MESES[mes - 1]} — ignorado.")
            continue
        if valor:
            deltas[mes] = valor
    return deltas


@require_POST
@login_required
def revisar_orcamento(request: HttpRequest, codigo: str, ano: int) -> HttpResponse:
    """A revisão. Motivo obrigatório, e o delta por mês."""
    centros = _centros(request)
    if not any(c.codigo == codigo for c in centros):
        raise PermissionDenied("Este centro de custo não é seu.")
    if not svc.pode_revisar(request.user, cache=_cache(request)):
        raise PermissionDenied("Revisar o orçamento é de quem responde pelo dinheiro.")

    destino = redirect("workspace:orcamento_centro", codigo=codigo, ano=ano)
    try:
        revisao = svc.revisar(
            codigo, ano, _deltas(request), request.POST.get("motivo", ""),
            request.user, cache=_cache(request),
        )
    except svc.OrcamentoError as erro:
        messages.error(request, str(erro))
        return destino

    if revisao is None:
        # Duas causas, uma mensagem só não serviria: sem orçamento vigente não
        # há o que revisar; sem delta, não houve mudança. As duas pedem coisas
        # diferentes de quem está na tela.
        messages.warning(
            request,
            "Nada foi revisado: ou este ano não tem orçamento vigente, ou "
            "nenhum mês recebeu valor.",
        )
    else:
        messages.success(
            request,
            f"Revisão {revisao.numero} aplicada: {revisao.total} no ano.",
        )
    return destino


@require_POST
@login_required
def vigorar_orcamento(request: HttpRequest, codigo: str, ano: int) -> HttpResponse:
    """Rascunho → vigente. Daqui em diante, só por revisão."""
    centros = _centros(request)
    if not any(c.codigo == codigo for c in centros):
        raise PermissionDenied("Este centro de custo não é seu.")

    try:
        aplicou = svc.vigorar(codigo, ano, request.user, cache=_cache(request))
    except svc.OrcamentoError as erro:
        messages.error(request, str(erro))
    else:
        if aplicou:
            messages.success(
                request,
                "Orçamento em vigor. A partir de agora ele muda por revisão, "
                "com motivo e autor.",
            )
        else:
            messages.warning(
                request,
                "Não havia rascunho com linhas para pôr em vigor neste ano.",
            )
    return redirect("workspace:orcamento_centro", codigo=codigo, ano=ano)
