"""Página de módulo — o destino dos tiles da home.

**Pública**, como o resto do hub: quem está na rede da empresa vê o que cada
departamento atende sem senha. O login só aparece quando a pessoa vai *agir* —
o botão "Pedir" leva para a área pessoal, que é `@login_required`.

Uma página só, parametrizada pela chave do módulo. Oito views quase idênticas
divergiriam na terceira semana; o que muda entre RH e Compras é a fatia do
catálogo, não a estrutura da tela.
"""

from __future__ import annotations

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from workspace.modulos import modulo_por_chave
from workspace.services import catalogo as svc

_ABERTAS = ["aguardando_aprovacao", "aprovada", "em_atendimento", "devolvida"]
LIMITE_MEUS = 5


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


def modulo(request: HttpRequest, chave: str) -> HttpResponse:
    mod = modulo_por_chave(chave)
    if mod is None or not mod.tem_catalogo:
        # Módulo sem fatia de catálogo não tem página. O tile dele já aparece
        # "em breve" na home; 404 aqui evita URL adivinhada abrir tela vazia.
        raise Http404("Módulo sem página no Workspace.")

    autenticado = request.user.is_authenticated
    pessoa = request.user if autenticado else None
    cache = _cache(request)

    # Quem pode pedir o quê. Um `set` de chaves e não uma segunda consulta por
    # item: a tela marca o que está fora do alcance, então precisa das duas
    # listas — a completa (vitrine) e a permitida.
    permitidas = {i.chave for i in svc.catalogo_para(pessoa, cache=cache)}

    itens = [
        {
            "item": item,
            "prazo": svc.prazo_medido(item),
            "pode_pedir": item.chave in permitidas,
        }
        for item in svc.do_modulo(mod.dominios)
    ]

    meus = []
    abertos = 0
    if autenticado:
        pedidos = svc.minhas_do_modulo(pessoa, mod.dominios)
        # Recorte curto: a página do módulo mostra o estado, e o histórico
        # completo mora em "Minhas solicitações". Lista longa aqui empurra a
        # vitrine para fora da tela, que é a razão de a pessoa ter entrado.
        meus = list(pedidos[:LIMITE_MEUS])
        abertos = pedidos.filter(situacao__in=_ABERTAS).count()

    return render(
        request,
        "workspace/modulo.html",
        {
            "modulo": mod,
            "itens": itens,
            "meus": meus,
            "meus_abertos": abertos,
            "autenticado": autenticado,
        },
    )
