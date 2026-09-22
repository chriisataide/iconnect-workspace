"""O ciclo de planejamento (12) — a pauta, a reunião e a ATA.

## A fronteira passa entre o GET e o POST

O GET da pauta é consulta: quem participa do ciclo lê a ordem de olhar, os
carimbos de cada destino e o que já foi anotado. Todo POST — abrir, anotar,
fechar — assina em nome da reunião, e exige `cic.conduzir`.

É a restrição 7 do produto, e ela vale aqui mais do que em qualquer outra tela:
a ATA é o documento que uma auditoria vai citar.

## 403, nunca pauta vazia

Quem não participa de ciclo nenhum recebe 403. Uma lista vazia diria "a empresa
não tem ciclo de planejamento" para quem apenas não está na sala — e essa é uma
frase que alguém repete numa reunião.

## Modo apresentação é query string (ADR-025)

`?etapa=CP05` mostra uma etapa por vez; `?apresentacao=1` tira o trilho do HTML.
São dois parâmetros ortogonais na MESMA view, e não uma segunda tela: a tela que
a diretoria vê na reunião é justamente a que não pode divergir da que ela
consulta na terça.
"""

from __future__ import annotations

from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from workspace.models.ciclo import CicloPlanejamento, EtapaCiclo
from workspace.services import ciclos as svc


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


def _ciclo_visivel(request: HttpRequest, chave: str) -> CicloPlanejamento:
    ciclo = get_object_or_404(CicloPlanejamento, chave=chave, ativo=True)
    if not svc.pode_ler(ciclo, request.user, cache=_cache(request)):
        raise PermissionDenied("Você não participa deste ciclo.")
    return ciclo


@login_required
def ciclos(request: HttpRequest) -> HttpResponse:
    try:
        panorama = svc.painel(request.user, cache=_cache(request))
    except svc.SemCiclos as sem:
        raise PermissionDenied(str(sem))
    return render(request, "workspace/ciclos/ciclos.html", panorama)


@login_required
def ciclo(request: HttpRequest, chave: str, ano: int = 0, mes: int = 0) -> HttpResponse:
    """A pauta de um ciclo — com a reunião da competência, se houver."""
    alvo = _ciclo_visivel(request, chave)

    contexto = svc.tela_do_ciclo(
        alvo,
        request.user,
        ano=ano or None,
        mes=mes or None,
        codigo_da_etapa=request.GET.get("etapa", "").strip().upper(),
        cache=_cache(request),
    )
    contexto["apresentacao"] = request.GET.get("apresentacao") == "1"
    return render(request, "workspace/ciclos/ciclo.html", contexto)


def _competencia(ano: int, mes: int) -> tuple[int, int]:
    if not 1 <= mes <= 12 or not 2000 <= ano <= 2100:
        raise Http404("Competência fora do calendário.")
    return ano, mes


@require_POST
@login_required
def abrir_ciclo(request: HttpRequest, chave: str, ano: int, mes: int) -> HttpResponse:
    """Abre a reunião da competência.

    POST porque cria registro em nome da empresa. Um GET aqui faria um
    *prefetch* do navegador abrir a reunião de setembro em agosto.
    """
    alvo = _ciclo_visivel(request, chave)
    ano, mes = _competencia(ano, mes)
    if not svc.pode_conduzir(alvo, request.user, cache=_cache(request)):
        raise PermissionDenied("Abrir a reunião é de quem conduz o ciclo.")

    confirmado = request.POST.get("confirmar") == "1"
    try:
        svc.abrir(alvo, request.user, ano, mes, confirmado=confirmado,
                  cache=_cache(request))
    except svc.CicloError as erro:
        # A fonte atrasada NÃO impede a reunião: o aviso é o primeiro POST, e o
        # segundo abre. Travar transformaria um problema de carga em um problema
        # de governança.
        for imp in getattr(erro, "impedimentos", []):
            messages.warning(
                request, f"{imp['etapa']} · {imp['titulo']}: {imp['carimbo']}"
            )
        messages.error(request, str(erro))
        return redirect("workspace:ciclo_competencia", chave=chave, ano=ano, mes=mes)

    messages.success(request, f"Reunião de {mes:02d}/{ano} aberta.")
    return redirect("workspace:ciclo_competencia", chave=chave, ano=ano, mes=mes)


@require_POST
@login_required
def anotar_etapa(request: HttpRequest, chave: str, ano: int, mes: int) -> HttpResponse:
    alvo = _ciclo_visivel(request, chave)
    ano, mes = _competencia(ano, mes)
    # A permissão ANTES da existência da reunião, e é deliberado: se o 404 viesse
    # primeiro, quem não conduz distinguiria "reunião aberta" de "reunião não
    # aberta" pelo código de resposta. É pouco, e é informação que só quem
    # conduz tem motivo de ter.
    if not svc.pode_conduzir(alvo, request.user, cache=_cache(request)):
        raise PermissionDenied("Anotar em nome da reunião exige conduzi-la.")

    ocorrencia = svc.ocorrencia_de(alvo, ano, mes)
    if ocorrencia is None:
        raise Http404("Esta reunião ainda não foi aberta.")

    etapa = EtapaCiclo.objects.filter(
        pk=request.POST.get("etapa") or 0, ciclo=alvo
    ).first()
    if etapa is None:
        # Filtrado POR CICLO na consulta, e não conferido depois: um `pk` de
        # etapa de outro ciclo escreveria numa pauta alheia — o IDOR pela porta
        # do formulário.
        raise Http404("Etapa desconhecida neste ciclo.")

    prazo = None
    if request.POST.get("prazo"):
        try:
            prazo = datetime.strptime(request.POST["prazo"], "%Y-%m-%d").date()
        except ValueError:
            messages.warning(request, "Data de prazo inválida — anotada sem prazo.")

    try:
        svc.anotar(
            ocorrencia,
            etapa,
            request.user,
            texto=request.POST.get("texto", ""),
            encaminhamento=request.POST.get("encaminhamento", ""),
            prazo=prazo,
            cache=_cache(request),
        )
    except svc.CicloError as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, f"Anotado em {etapa.codigo}.")

    destino = redirect("workspace:ciclo_competencia", chave=chave, ano=ano, mes=mes)
    # Volta para a MESMA etapa, e em apresentação se era daí que veio. Devolver
    # a pauta inteira no meio da reunião faria quem conduz procurar o lugar de
    # novo, com a sala esperando.
    destino["Location"] += f"?etapa={etapa.codigo}"
    if request.POST.get("apresentacao") == "1":
        destino["Location"] += "&apresentacao=1"
    return destino


@require_POST
@login_required
def fechar_ciclo(request: HttpRequest, chave: str, ano: int, mes: int) -> HttpResponse:
    """Fecha a reunião e gera a ATA no acervo."""
    alvo = _ciclo_visivel(request, chave)
    ano, mes = _competencia(ano, mes)
    if not svc.pode_conduzir(alvo, request.user, cache=_cache(request)):
        raise PermissionDenied("Fechar a reunião é de quem conduz o ciclo.")

    ocorrencia = svc.ocorrencia_de(alvo, ano, mes)
    if ocorrencia is None:
        raise Http404("Esta reunião ainda não foi aberta.")

    try:
        documento = svc.fechar(ocorrencia, request.user, cache=_cache(request))
    except svc.CicloError as erro:
        messages.error(request, str(erro))
        return redirect("workspace:ciclo_competencia", chave=chave, ano=ano, mes=mes)

    messages.success(request, "ATA gerada no acervo.")
    return redirect("workspace:documento", slug=documento.slug)
