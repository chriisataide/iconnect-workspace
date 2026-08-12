"""Catálogo de serviços — as telas de pedir e acompanhar.

Área pessoal: pedir exige saber quem pede. A home do Portal continua pública; é
aqui que o login passa a ser necessário, e `@login_required` só aparece neste
arquivo e no de aprovações.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from workspace.models.catalogo import ItemCatalogo
from workspace.services import catalogo as svc
from workspace.services.catalogo import SolicitacaoError


def _cache(request: HttpRequest) -> dict:
    """Cache de permissão por requisição. O middleware do ST-0xx cria isto;
    até lá, cada view garante o seu."""
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


@login_required
def catalogo(request: HttpRequest) -> HttpResponse:
    """O catálogo agrupado por intenção, com prazo real medido."""
    cache = _cache(request)
    grupos = []
    for rotulo, itens in svc.agrupado_para(request.user, cache=cache).items():
        grupos.append(
            {
                "rotulo": rotulo,
                "itens": [
                    {"item": item, "prazo": svc.prazo_medido(item)} for item in itens
                ],
            }
        )

    minhas = svc.minhas(request.user)
    return render(
        request,
        "workspace/servicos/catalogo.html",
        {
            "grupos": grupos,
            "abertas": minhas.filter(situacao__in=_ABERTAS).count(),
            "devolvidas": minhas.filter(situacao="devolvida").count(),
        },
    )


_ABERTAS = ["aguardando_aprovacao", "aprovada", "em_atendimento", "devolvida"]


@login_required
def pedir(request: HttpRequest, chave: str) -> HttpResponse:
    """Formulário de um item. Valida antes de enviar e bloqueia com o motivo."""
    item = get_object_or_404(ItemCatalogo, chave=chave, ativo=True)
    cache = _cache(request)

    dados = {}
    valor = None
    impedimentos = []

    if request.method == "POST":
        dados = {
            campo["chave"]: (request.POST.get(campo["chave"]) or "").strip()
            for campo in item.campos
        }
        valor = _valor_de(request.POST.get("valor"))

        try:
            solicitacao = svc.solicitar(item, request.user, dados, valor, cache=cache)
        except SolicitacaoError:
            # Revalida para devolver a lista completa por campo, e não só a
            # primeira mensagem: corrigir um erro por vez é o que faz o usuário
            # desistir no terceiro envio.
            impedimentos = svc.verificar(item, request.user, dados, valor, cache=cache)
        else:
            if solicitacao.auto_aprovada:
                messages.success(
                    request,
                    f"{item.nome} aprovado automaticamente — está dentro da política.",
                )
            else:
                messages.success(request, f"{item.nome} enviado para aprovação.")
            return redirect(reverse("workspace:minhas_solicitacoes"))

    # Campos já montados com valor e erro. O template não faz busca por chave
    # dinâmica — é a regra do design system: a view agrega, o template desenha.
    por_campo = {i.campo: i.motivo for i in impedimentos}
    campos = [
        {**campo, "valor": dados.get(campo["chave"], ""), "erro": por_campo.get(campo["chave"])}
        for campo in item.campos
    ]

    return render(
        request,
        "workspace/servicos/pedir.html",
        {
            "item": item,
            "prazo": svc.prazo_medido(item),
            "campos": campos,
            "valor": valor,
            "erro_valor": por_campo.get("valor"),
            "impedimentos": impedimentos,
            "centro_custo": svc._centro_custo_de(request.user),
        },
    )


def _valor_de(bruto: str | None) -> Decimal | None:
    """Aceita `1.234,56` e `1234.56` — o usuário digita como aprendeu."""
    if not bruto:
        return None
    texto = bruto.strip().replace(".", "").replace(",", ".")
    try:
        return Decimal(texto)
    except (InvalidOperation, ValueError):
        return None


@login_required
def minhas_solicitacoes(request: HttpRequest) -> HttpResponse:
    solicitacoes = svc.minhas(request.user)
    return render(
        request,
        "workspace/servicos/minhas.html",
        {
            "solicitacoes": solicitacoes,
            "abertas": solicitacoes.filter(situacao__in=_ABERTAS).count(),
        },
    )


@login_required
def cancelar(request: HttpRequest, pk: int) -> HttpResponse:
    solicitacao = get_object_or_404(svc.minhas(request.user), pk=pk)
    if request.method == "POST":
        try:
            svc.cancelar(solicitacao, request.user)
            messages.success(request, "Solicitação cancelada.")
        except SolicitacaoError as erro:
            messages.error(request, str(erro))
    return redirect(reverse("workspace:minhas_solicitacoes"))
