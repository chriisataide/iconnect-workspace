"""A Apresentação de Resultados (10) e a tela de fontes (99).

## 403, nunca tela zerada

Resultado financeiro **não é informação institucional**. O Workspace é aberto
para o hub, o catálogo, a documentação e a agenda das salas; isto aqui é o
desempenho da empresa com nome de cliente ao lado, e o anônimo recebe 403 no
GET — não no POST.

Quem está logado e não tem escopo também recebe 403, e não um painel de zeros.
Números todos em zero para quem nunca vai ter dado faz a pessoa achar que a
empresa parou — mesma regra de `/workspace/indicadores/`.

## Nenhuma chamada de rede acontece aqui

Se um número vem de fora, ele já está no espelho quando a tela abre. A view
pergunta ao contrato, o contrato consulta o espelho, e o espelho é banco local.
Uma tela executiva que depende de uma API de terceiro no meio de uma reunião é
uma tela que cai no meio de uma reunião.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from workspace.providers import frescor as contrato_frescor
from workspace.services import resultados as svc


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


@login_required
def resultados(request: HttpRequest) -> HttpResponse:
    try:
        panorama = svc.painel(request.user, request.GET, cache=_cache(request))
    except svc.SemResultados as sem:
        raise PermissionDenied(str(sem))

    # Modo apresentação: esconde trilho e filtros e aumenta a tipografia. É o
    # que faz a tela servir para a reunião em vez de servir só para consulta —
    # e é uma query string, não uma tela separada, porque a segunda tela
    # divergiria da primeira na terceira semana.
    apresentacao = request.GET.get("apresentacao") == "1"

    return render(
        request,
        "workspace/resultados.html",
        {
            **panorama,
            "apresentacao": apresentacao,
            "pode_ver_fontes": svc.pode_ver_fontes(request.user, cache=_cache(request)),
        },
    )


@login_required
def quadro(request: HttpRequest) -> HttpResponse:
    """Quadro e jornada (16) — a antiga faixa 6 da tela 10.

    Tela própria porque a PERGUNTA é de outra gente. Enquanto ela morava dentro
    da Apresentação de Resultados, dar o turnover de um centro de custo a quem
    responde por gente significava dar junto a margem de todo contrato da
    empresa — e por isso ninguém dava.

    Sem dado pessoal, aqui como lá: o quadro é agregado por centro de custo, e
    nome de colaborador não entra em grade nem em exportação.
    """
    try:
        panorama = svc.painel_de_pessoas(request.user, request.GET, cache=_cache(request))
    except svc.SemResultados as sem:
        raise PermissionDenied(str(sem))

    return render(
        request,
        "workspace/quadro.html",
        {**panorama, "apresentacao": request.GET.get("apresentacao") == "1"},
    )


@login_required
def satisfacao(request: HttpRequest) -> HttpResponse:
    """Satisfação do cliente (17) — a antiga faixa 7 da tela 10.

    Mesma razão da 16, outro público: o NPS é do comercial. E o detrator SEM
    tratativa é o motivo de a tela existir — ele não é linha de tabela, é uma
    pessoa esperando.
    """
    try:
        panorama = svc.painel_de_satisfacao(
            request.user, request.GET, cache=_cache(request)
        )
    except svc.SemResultados as sem:
        raise PermissionDenied(str(sem))

    return render(
        request,
        "workspace/satisfacao.html",
        {**panorama, "apresentacao": request.GET.get("apresentacao") == "1"},
    )


@login_required
def resultados_detalhe(request: HttpRequest) -> HttpResponse:
    """As linhas por trás do agregado — o mecanismo 4.

    Tela própria e não gaveta: a gaveta exigiria carregar a tabela por
    JavaScript, e uma tela tem URL — que é o que permite mandar o detalhe numa
    mensagem, do mesmo jeito que o agregado.

    Link explícito, e nunca clique acidental no gráfico: descer para as linhas é
    outra pergunta, e não uma variação da mesma.
    """
    try:
        contexto = svc.detalhe(request.user, request.GET, cache=_cache(request))
    except svc.SemResultados as sem:
        raise PermissionDenied(str(sem))
    return render(request, "workspace/resultados/detalhe.html", contexto)


@login_required
def resultados_dados(request: HttpRequest) -> JsonResponse:
    """O agregado em JSON, com o MESMO escopo da tela.

    É o erro clássico que o prompt nomeia: a tela filtra por regional e a API
    devolve tudo. Aqui as duas chamam `escopo_de` e `ler_filtros` — não há como
    divergir sem que alguém escreva um segundo caminho de propósito.

    `@login_required` faz o anônimo cair no login; quem entra e não tem escopo
    recebe 403, exatamente como na tela.
    """
    try:
        corpo = svc.dados(request.user, request.GET, cache=_cache(request))
    except svc.SemResultados as sem:
        raise PermissionDenied(str(sem))
    # `json_dumps_params` com `default=str`: `Decimal` e `date` não são JSON, e
    # um `TypeError` aqui viraria 500 numa rota que o JS consome.
    return JsonResponse(corpo, json_dumps_params={"default": str})


@login_required
def fontes(request: HttpRequest) -> HttpResponse:
    """De onde vem esse número — a tela 99 do benchmark.

    Permissão SEPARADA da tela de resultados: ver a procedência não dá acesso
    aos números. O T.I. conserta a carga sem enxergar o resultado financeiro.
    """
    if not svc.pode_ver_fontes(request.user, cache=_cache(request)):
        raise PermissionDenied("Esta tela é de quem opera as cargas.")

    return render(
        request,
        "workspace/fontes.html",
        {
            **svc.panorama_das_fontes(),
            "pode_recarregar": svc.pode_recarregar(
                request.user, cache=_cache(request)
            ),
        },
    )


@require_POST
@login_required
def recarregar_fonte(request: HttpRequest, chave: str) -> HttpResponse:
    """Recarregar é ação, e ação é POST.

    `GET` aqui faria um *prefetch* do navegador disparar uma carga — e o
    histórico de execuções encheria de linhas que ninguém pediu.
    """
    if not svc.pode_recarregar(request.user, cache=_cache(request)):
        raise PermissionDenied("Recarregar uma fonte é de quem opera.")

    provedor = contrato_frescor.obter()
    if provedor is None:
        messages.error(request, "Nenhuma fonte está registrada neste ambiente.")
    elif provedor.recarregar(chave, quem=request.user):
        messages.success(request, f"Carga de {chave} concluída.")
    else:
        # A carga já registrou a execução com o motivo. Inventar uma segunda
        # mensagem aqui produziria duas versões do mesmo erro.
        messages.warning(
            request,
            f"A carga de {chave} não foi concluída. O motivo está no histórico "
            "abaixo.",
        )
    return redirect("workspace:fontes")


@login_required
def resultados_pdf(request: HttpRequest) -> HttpResponse:
    """O PDF da competência, gerado no servidor.

    Mesma permissão e mesmo escopo da tela: o PDF não pode mostrar o que a tela
    esconde. Se pudesse, exportar viraria a forma de contornar o recorte — e a
    exportação é justamente o caminho por onde o dado sai do prédio.
    """
    try:
        panorama = svc.painel(request.user, request.GET, cache=_cache(request))
    except svc.SemResultados as sem:
        raise PermissionDenied(str(sem))

    from workspace.services import pdf_resultados

    conteudo = pdf_resultados.gerar(panorama)
    nome = pdf_resultados.nome_do_arquivo(panorama["filtros"].competencia)

    resposta = HttpResponse(conteudo, content_type="application/pdf")
    # `inline` e não `attachment`: quem clica quer CONFERIR antes da reunião, e
    # o download direto obriga a abrir a pasta para ver se saiu certo.
    resposta["Content-Disposition"] = f'inline; filename="{nome}"'
    return resposta
