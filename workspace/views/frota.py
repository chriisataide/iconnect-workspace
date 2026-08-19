"""FRT — a tela da frota. §18 e §19.

Uma tela só, e não uma por assunto: a pergunta de quem abre é sempre sobre um
carro — o que ele custou, quanto ele faz por litro, e se o documento está em
dia. Separar "veículos", "abastecimentos" e "documentos" em três telas obrigaria
a pessoa a atravessar as três para responder uma pergunta.

    log.frota.ler       vê a frota, os prazos e o consumo
    log.frota.operar    cadastra veículo e lança despesa

**Não há tela de reserva aqui.** O carro de uso comum é reservado na grade de
Reservas, que já garante que duas pessoas não peguem a van no mesmo horário.
Uma segunda porta para a mesma coisa é como o produto passou a ter dois modos
de marcar o mesmo veículo — ver `models/frota.py`.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date

from identidade.models import Unidade
from workspace.models.frota import (
    SituacaoVeiculo,
    TipoDespesaVeiculo,
    TipoVeiculo,
    Veiculo,
)
from workspace.models.reserva import Recurso, TipoRecurso
from workspace.services import frota as frt
from workspace.services.frota import FrotaError


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


@login_required
def frota(request: HttpRequest) -> HttpResponse:
    """A frota, os prazos estourando e — quando escolhido — um veículo inteiro."""
    cache = _cache(request)
    if not frt.pode_ler(request.user, cache=cache):
        raise PermissionDenied("Você não tem acesso à frota.")

    veiculos = list(frt.frota())

    # Um veículo por vez no detalhe. O consumo da frota inteira numa tela só
    # seria uma tabela que ninguém lê: a pergunta é sempre sobre UM carro.
    placa = request.GET.get("placa", "")
    veiculo = next((v for v in veiculos if v.placa == placa.upper()), None)

    return render(
        request,
        "workspace/frota.html",
        {
            "veiculos": veiculos,
            "prazos": frt.com_prazo_estourando(),
            "veiculo": veiculo,
            "resumo": frt.resumo_de(veiculo) if veiculo else None,
            "consumo": frt.consumo_de(veiculo) if veiculo else (),
            "despesas": frt.despesas_de(veiculo, limite=40) if veiculo else (),
            "tipos_despesa": TipoDespesaVeiculo.choices,
            "tipos_veiculo": TipoVeiculo.choices,
            "situacoes": SituacaoVeiculo.choices,
            "unidades": Unidade.objects.order_by("nome"),
            # Quem pode ter dirigido: o organograma, e não a tabela de contas.
            "pessoas": get_user_model()
            .objects.filter(lotacao__isnull=False)
            .order_by("nome", "email"),
            # Só recurso de veículo, e só o que ainda não tem carro amarrado:
            # oferecer um recurso já ligado a outra placa produziria justamente
            # a dupla ficha que o `OneToOne` existe para impedir.
            "recursos": Recurso.objects.filter(
                tipo=TipoRecurso.VEICULO, ativo=True, veiculo__isnull=True
            ).order_by("nome"),
            "opera": frt.pode_operar(request.user, cache=cache),
        },
    )


def _de_volta(placa: str = "") -> HttpResponse:
    destino = reverse("workspace:frota")
    return redirect(f"{destino}?placa={placa}" if placa else destino)


@login_required
def cadastrar_veiculo(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return _de_volta()

    if not frt.pode_operar(request.user, cache=_cache(request)):
        raise PermissionDenied("Você não pode cadastrar veículo.")

    placa = (request.POST.get("placa") or "").strip().upper()
    modelo = (request.POST.get("modelo") or "").strip()
    if not placa or not modelo:
        messages.error(request, "Placa e modelo são obrigatórios.")
        return _de_volta()
    if Veiculo.objects.filter(placa=placa).exists():
        # Recusar com a placa no recado, e não com "já existe": duas fichas para
        # a mesma placa é como a frota passa a ter dois históricos de manutenção.
        messages.error(request, f"Já existe um veículo com a placa {placa}.")
        return _de_volta(placa)

    Veiculo.objects.create(
        placa=placa,
        modelo=modelo[:60],
        marca=(request.POST.get("marca") or "").strip()[:40],
        tipo=request.POST.get("tipo") or TipoVeiculo.CARRO,
        ano=_inteiro(request.POST.get("ano")),
        renavam=(request.POST.get("renavam") or "").strip()[:20],
        km_atual=_inteiro(request.POST.get("km_atual")) or 0,
        unidade=_unidade(request.POST.get("unidade")),
        recurso=_recurso(request.POST.get("recurso")),
        licenciamento_ate=parse_date(request.POST.get("licenciamento_ate") or ""),
        seguro_ate=parse_date(request.POST.get("seguro_ate") or ""),
        ipva_ate=parse_date(request.POST.get("ipva_ate") or ""),
        revisao_em=parse_date(request.POST.get("revisao_em") or ""),
    )
    messages.success(request, f"{placa} cadastrado.")
    return _de_volta(placa)


@login_required
def atualizar_veiculo(request: HttpRequest, pk: int) -> HttpResponse:
    """Prazos, situação e o recurso reservável. Não a placa.

    Placa não se corrige: se ela está errada, o veículo é outro — e trocá-la
    levaria junto o histórico de multa e manutenção do carro anterior.
    """
    if request.method != "POST":
        return _de_volta()

    if not frt.pode_operar(request.user, cache=_cache(request)):
        raise PermissionDenied("Você não pode editar veículo.")

    veiculo = get_object_or_404(Veiculo, pk=pk)
    veiculo.situacao = request.POST.get("situacao") or veiculo.situacao
    for campo in ("licenciamento_ate", "seguro_ate", "ipva_ate", "revisao_em"):
        if campo in request.POST:
            setattr(veiculo, campo, parse_date(request.POST[campo] or ""))
    if "recurso" in request.POST:
        veiculo.recurso = _recurso(request.POST.get("recurso"))
    veiculo.save()

    messages.success(request, f"{veiculo.placa} atualizado.")
    return _de_volta(veiculo.placa)


@login_required
def lancar_despesa(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return _de_volta()

    veiculo = get_object_or_404(Veiculo, pk=pk)
    try:
        frt.lancar_despesa(
            veiculo,
            request.POST.get("tipo", ""),
            request.POST.get("valor") or "0",
            quem=request.user,
            data=parse_date(request.POST.get("data") or "") or None,
            km=_inteiro(request.POST.get("km")),
            litros=request.POST.get("litros") or None,
            tanque_cheio=bool(request.POST.get("tanque_cheio")),
            fornecedor=request.POST.get("fornecedor", ""),
            observacao=request.POST.get("observacao", ""),
            motorista=_pessoa(request.POST.get("motorista")),
            destino=request.POST.get("destino", ""),
            finalidade=request.POST.get("finalidade", ""),
            cache=_cache(request),
        )
    except (FrotaError, ArithmeticError, ValueError) as erro:
        # `ValueError` e `ArithmeticError` cobrem o valor digitado que não é
        # número: `Decimal("abacaxi")` levanta `InvalidOperation`, que é um
        # `ArithmeticError` — e um 500 por causa de um campo de texto seria a
        # forma mais cara possível de dizer "digite um número".
        messages.error(request, str(erro) or "Valor inválido.")
    else:
        messages.success(request, "Despesa lançada.")

    return _de_volta(veiculo.placa)


def _inteiro(bruto) -> int | None:
    try:
        return int(str(bruto).strip())
    except (TypeError, ValueError):
        return None


def _pessoa(bruto):
    from django.contrib.auth import get_user_model

    return (
        get_user_model().objects.filter(pk=int(bruto)).first()
        if bruto and str(bruto).isdigit()
        else None
    )


def _unidade(bruto):
    return (
        Unidade.objects.filter(pk=int(bruto)).first()
        if bruto and str(bruto).isdigit()
        else None
    )


def _recurso(bruto):
    return (
        Recurso.objects.filter(pk=int(bruto), tipo=TipoRecurso.VEICULO).first()
        if bruto and str(bruto).isdigit()
        else None
    )
