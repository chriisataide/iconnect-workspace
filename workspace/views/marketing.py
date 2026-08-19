"""MKT — o radar de oportunidades. §23.

Uma tela: a lista com o prazo à frente, o formulário de cadastro e a decisão em
linha. Não há tela de aprovação **de propósito** — decidir ir a uma feira é
gastar dinheiro da empresa, e esse caminho já existe: o item `evento` do
catálogo, que passa por gestor e diretoria conforme a faixa e confere o
orçamento do centro de custo.

    mkt.ler       vê o radar
    mkt.atender   cadastra e decide
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date

from workspace.models.marketing import (
    Oportunidade,
    SituacaoOportunidade,
    TipoOportunidade,
)
from workspace.services import marketing as mkt
from workspace.services.marketing import MarketingError


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


@login_required
def marketing(request: HttpRequest) -> HttpResponse:
    """O radar. Abertas por padrão — é o que precisa de decisão."""
    cache = _cache(request)
    if not mkt.pode_ler(request.user, cache=cache):
        raise PermissionDenied("Esta tela é de quem cuida de marketing.")

    situacao = request.GET.get("situacao", "")
    if situacao not in SituacaoOportunidade.values:
        situacao = ""

    return render(
        request,
        "workspace/marketing.html",
        {
            "oportunidades": list(mkt.radar(situacao)),
            "prazos": mkt.com_prazo_estourando(),
            "resumo": mkt.resumo(),
            "situacao_atual": situacao,
            "situacoes": SituacaoOportunidade.choices,
            "tipos": TipoOportunidade.choices,
            "pessoas": get_user_model()
            .objects.filter(lotacao__isnull=False)
            .order_by("nome", "email"),
            "opera": mkt.pode_operar(request.user, cache=cache),
        },
    )


@login_required
def oportunidade_registrar(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    """Cadastra ou atualiza. Sempre `POST`, sempre de volta para a lista."""
    if request.method != "POST":
        return redirect(reverse("workspace:marketing"))

    oportunidade = get_object_or_404(Oportunidade, pk=pk) if pk else None
    try:
        mkt.registrar(
            request.user,
            titulo=request.POST.get("titulo", ""),
            tipo=request.POST.get("tipo", ""),
            oportunidade=oportunidade,
            organizador=request.POST.get("organizador", ""),
            cidade=request.POST.get("cidade", ""),
            site=request.POST.get("site", ""),
            data_inicio=parse_date(request.POST.get("data_inicio") or ""),
            data_fim=parse_date(request.POST.get("data_fim") or ""),
            prazo_decisao=parse_date(request.POST.get("prazo_decisao") or ""),
            custo_estimado=_decimal(request.POST.get("custo_estimado")),
            publico_estimado=_inteiro(request.POST.get("publico_estimado")),
            retorno_esperado=request.POST.get("retorno_esperado", ""),
            origem=request.POST.get("origem", ""),
            responsavel=_pessoa(request.POST.get("responsavel")),
            cache=_cache(request),
        )
    except MarketingError as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, "Oportunidade registrada.")

    return redirect(reverse("workspace:marketing"))


@login_required
def oportunidade_decidir(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect(reverse("workspace:marketing"))

    oportunidade = get_object_or_404(Oportunidade, pk=pk)
    try:
        mkt.decidir(
            oportunidade,
            request.user,
            request.POST.get("situacao", ""),
            motivo=request.POST.get("motivo", ""),
            cache=_cache(request),
        )
    except MarketingError as erro:
        messages.error(request, str(erro))
    else:
        messages.success(
            request,
            f"{oportunidade.titulo} — {oportunidade.get_situacao_display().lower()}.",
        )

    return redirect(reverse("workspace:marketing"))


def _decimal(bruto):
    try:
        return Decimal(str(bruto).replace(".", "").replace(",", ".")) if bruto else None
    except (InvalidOperation, TypeError, ValueError):
        # Valor mal digitado vira vazio e não erro: o custo é ESTIMADO, e perder
        # o cadastro inteiro por causa dele seria trocar um campo opcional por
        # uma tela.
        return None


def _inteiro(bruto):
    try:
        return int(str(bruto).strip())
    except (TypeError, ValueError):
        return None


def _pessoa(bruto):
    return (
        get_user_model().objects.filter(pk=int(bruto)).first()
        if bruto and str(bruto).isdigit()
        else None
    )
