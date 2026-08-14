"""Bandeja de aprovação — a tela que justifica o módulo.

Aprovação sem contexto financeiro é carimbo. Com a barra tripla — realizado,
comprometido, este pedido — é decisão.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from workspace.acesso import pessoa_da_requisicao
from workspace.models.aprovacao import SolicitacaoAprovacao
from workspace.services import aprovacao as apr
from workspace.services import orcamento as orc


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


LARGURA_BARRA = 100  # unidades do viewBox do SVG


def _faixas(resumo, valor) -> list[dict] | None:
    """As três faixas da barra, em largura de viewBox SVG.

    SVG e não CSS: a CSP de produção traz nonce em `style-src`, e navegador
    moderno ignora `unsafe-inline` quando há nonce — o que bloqueia atributo
    `style="width: …"`. Em SVG, `width` é atributo, não estilo.
    """
    if resumo is None or not resumo.tem_orcamento:
        return None

    orcamento = resumo.orcamento
    partes = [
        ("realizado", resumo.realizado),
        ("comprometido", resumo.comprometido),
        ("pedido", valor or 0),
    ]

    faixas = []
    x = 0.0
    for nome, montante in partes:
        largura = float(montante) / float(orcamento) * LARGURA_BARRA
        # Trunca no fim da barra: pedido que estoura não deve desenhar fora do
        # gráfico — o alerta textual é que comunica o estouro.
        largura = max(0.0, min(largura, LARGURA_BARRA - x))
        if largura > 0:
            # STRING com ponto decimal, não float.
            #
            # O Django localiza número no template (pt-BR → `8,42`), e vírgula
            # é inválida em atributo SVG — o navegador descarta o `<rect>` e a
            # barra não desenha. É um bug que só aparece no console do browser,
            # não em teste de servidor.
            faixas.append(
                {
                    "nome": nome,
                    "x": f"{x:.2f}",
                    "largura": f"{largura:.2f}",
                    # Números para o teste conferir sem reparsear string.
                    "x_num": round(x, 2),
                    "largura_num": round(largura, 2),
                }
            )
        x += largura
        if x >= LARGURA_BARRA:
            break
    return faixas


def _servico_de(solicitacao: SolicitacaoAprovacao):
    """O pedido de catálogo ligado a esta aprovação, ou `None`.

    `try` e não `getattr(..., None)`: acessor reverso de OneToOne levanta
    `DoesNotExist`, que não é `AttributeError` — o default do `getattr` não
    captura, e a bandeja quebraria em toda aprovação que não vem do catálogo
    (férias lançadas direto pelo RH, por exemplo).
    """
    try:
        return solicitacao.servico
    except ObjectDoesNotExist:
        return None


def _despesas_de(solicitacao: SolicitacaoAprovacao) -> list:
    """As compras, uma a uma, quando o pedido foi item a item.

    É o que transforma "R$ 340,00 e cinco imagens" em uma lista conferível. Sem
    isto, itemizar teria melhorado só o lado de quem pede — e quem aprova
    continuaria refazendo a soma à mão para saber se o total bate.
    """
    servico = _servico_de(solicitacao)
    if servico is None:
        return []
    return list(servico.despesas.select_related("anexo"))


def _anexos_de(solicitacao: SolicitacaoAprovacao) -> list:
    """Anexos do pedido de serviço ligado a esta aprovação.

    A aprovação não conhece o catálogo — é a direção que mantém APR reusável
    por férias, reembolso e compra. Então a busca vem do outro lado.
    """
    servico = _servico_de(solicitacao)
    if servico is None:
        return []
    return list(servico.anexos.all())


def _dossie(solicitacao: SolicitacaoAprovacao) -> dict:
    """O contexto que transforma carimbo em decisão."""
    resumo = None
    if solicitacao.centro_custo_codigo:
        resumo = orc.resumo(solicitacao.centro_custo_codigo)

    return {
        "solicitacao": solicitacao,
        # Aprovar reembolso sem poder abrir o comprovante é exatamente o
        # carimbo que esta tela existe para evitar.
        "anexos": _anexos_de(solicitacao),
        "despesas": _despesas_de(solicitacao),
        "resumo": resumo,
        "faixas": _faixas(resumo, solicitacao.valor),
        "pct_atual": resumo.percentual() if resumo else None,
        "pct_apos": resumo.percentual(solicitacao.valor) if resumo else None,
        "cabe": resumo.cabe(solicitacao.valor) if resumo and solicitacao.valor else True,
        "etapas": list(apr.historico(solicitacao)),
        "etapa_atual": solicitacao.etapa_atual,
    }


def bandeja(request: HttpRequest) -> HttpResponse:
    cache = _cache(request)
    resumo = apr.resumo_da_bandeja(pessoa_da_requisicao(request), cache=cache)
    return render(
        request,
        "workspace/aprovacoes/bandeja.html",
        {
            "resumo": resumo,
            "itens": [_dossie(s) for s in resumo["solicitacoes"]],
        },
    )


@login_required
def decidir(request: HttpRequest, pk: int) -> HttpResponse:
    """Registra a decisão. Toda regra está no serviço, não aqui.

    `@login_required` e `request.user`, não `pessoa_da_requisicao()`: a bandeja
    é aberta como o resto do Workspace, mas DECIDIR assina. Sem identidade, o
    fallback anônimo aprovaria pedidos com o nome da primeira pessoa do
    organograma — e o histórico registraria que foi ela.
    """
    if request.method != "POST":
        return redirect(reverse("workspace:aprovacoes"))

    solicitacao = get_object_or_404(SolicitacaoAprovacao, pk=pk)
    pessoa = request.user
    decisao = request.POST.get("decisao", "")
    justificativa = (request.POST.get("justificativa") or "").strip()

    try:
        apr.decidir(
            solicitacao, pessoa, decisao, justificativa, cache=_cache(request)
        )
    except apr.AprovacaoError as erro:
        messages.error(request, str(erro))
    else:
        rotulo = {
            apr.Decisao.APROVAR: "aprovada",
            apr.Decisao.DEVOLVER: "devolvida",
            apr.Decisao.CANCELAR: "cancelada",
        }.get(decisao, "decidida")
        messages.success(request, f"{solicitacao.titulo} · {rotulo}.")

    return redirect(reverse("workspace:aprovacoes"))


@login_required
def decidir_em_lote(request: HttpRequest) -> HttpResponse:
    """Aprova as selecionadas. Não aborta tudo quando uma falha.

    Assina como `decidir()`, e em lote — o que torna a falta de identidade aqui
    mais cara, não menos.
    """
    if request.method != "POST":
        return redirect(reverse("workspace:aprovacoes"))

    ids = request.POST.getlist("selecionadas")
    if not ids:
        messages.info(request, "Selecione ao menos uma solicitação para aprovar em lote.")
        return redirect(reverse("workspace:aprovacoes"))

    solicitacoes = list(SolicitacaoAprovacao.objects.filter(pk__in=ids))
    pessoa = request.user
    decididas, falhas = apr.decidir_em_lote(
        solicitacoes, pessoa, apr.Decisao.APROVAR, cache=_cache(request)
    )

    if decididas:
        messages.success(request, f"{len(decididas)} aprovada(s).")
    for _pk, motivo in falhas:
        messages.error(request, motivo)

    return redirect(reverse("workspace:aprovacoes"))
