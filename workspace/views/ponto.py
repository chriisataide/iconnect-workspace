"""RH — a tela operacional das pendências de ponto.

Uma tela só, com as cinco etapas em sequência: importar, validar, revisar,
testar, enviar. O R.H. não abre n8n, Docker nem terminal; a complexidade fica
do outro lado do webhook.

Toda decisão de permissão é conferida AQUI, no servidor. Esconder botão é
cortesia com quem olha a tela, não autorização — o §32 pede as duas coisas e a
que vale é esta.
"""

from __future__ import annotations

from django.contrib import messages
from django.db.models import Count, Q
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from workspace.models.ponto import (
    AcaoPonto,
    ColaboradorPonto,
    LotePonto,
    ModoEnvio,
    SituacaoEnvio,
    SituacaoLote,
)
from workspace.services import ponto as motor
from workspace.services import ponto_lote as lot
from workspace.services import ponto_whatsapp as zap

LIMITE_HISTORICO = 50


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


def _contexto(request: HttpRequest, lote: LotePonto | None) -> dict:
    cache = _cache(request)
    contexto = {
        "lote": lote,
        "pode_importar": lot.pode_importar(request.user, cache=cache),
        "pode_testar": lot.pode_testar(request.user, cache=cache),
        "pode_enviar": lot.pode_enviar_producao(request.user, cache=cache),
        "MODO_TESTE": ModoEnvio.TESTE,
        "MODO_PRODUCAO": ModoEnvio.PRODUCAO,
    }
    if lote is not None:
        colaboradores = list(lote.colaboradores.all())
        contexto |= {
            "resumo": lot.resumo(lote),
            "colaboradores": colaboradores,
            "progresso": zap.progresso(lote),
            "etapa": _etapa_de(lote),
        }
    return contexto


def _etapa_de(lote: LotePonto) -> int:
    """Qual das cinco bolinhas está acesa. Derivada do estado, nunca guardada.

    Uma coluna `etapa` no banco seria mais simples de ler e passaria a mentir
    no primeiro caminho que mudasse a situação sem lembrar de atualizá-la.
    """
    if lote.situacao in (SituacaoLote.CONCLUIDO, SituacaoLote.CONCLUIDO_COM_ERROS):
        return 5
    if lote.situacao == SituacaoLote.PROCESSANDO:
        return 5
    if lote.envios.exists():
        return 4
    if lote.situacao == SituacaoLote.VALIDADO:
        return 3
    return 2 if lote.colaboradores.exists() else 1


@login_required
def pendencias_ponto(request: HttpRequest) -> HttpResponse:
    """A tela. Sem lote, mostra o estado vazio com a área de upload."""
    lot.exigir(lot.pode_ler(request.user, cache=_cache(request)))

    lote = None
    if (pedido := request.GET.get("lote", "")).isdigit():
        lote = get_object_or_404(LotePonto, pk=pedido)
    else:
        lote = (
            LotePonto.objects.filter(quem_importou=request.user)
            .exclude(situacao=SituacaoLote.CANCELADO)
            .first()
        )

    return render(request, "workspace/ponto/pendencias.html", _contexto(request, lote))


@login_required
@require_POST
def ponto_importar(request: HttpRequest) -> HttpResponse:
    """Etapa 1 e 2 — a planilha entra e é validada. Nada é enviado aqui."""
    lot.exigir(lot.pode_importar(request.user, cache=_cache(request)))

    arquivo = request.FILES.get("planilha")
    if arquivo is None:
        messages.error(request, "Escolha uma planilha para importar.")
        return redirect("workspace:pendencias_ponto")

    try:
        lote = lot.importar(arquivo, request)
    except lot.UploadInvalido as erro:
        if erro.colunas_ausentes:
            faltam = ", ".join(erro.colunas_ausentes)
            messages.error(
                request,
                f"{erro.mensagem} Colunas obrigatórias ausentes: {faltam}.",
            )
        else:
            messages.error(request, erro.mensagem)
        return redirect("workspace:pendencias_ponto")

    resumo = lot.resumo(lote)
    messages.success(
        request,
        f"Validação concluída: {resumo['colaboradores']} colaboradores, "
        f"{resumo['pendencias']} pendências, {resumo['prontos']} prontos para envio.",
    )
    return redirect(f"{reverse('workspace:pendencias_ponto')}?lote={lote.pk}")


@login_required
@require_POST
def ponto_corrigir(request: HttpRequest, pk: int) -> HttpResponse:
    """§14 — corrige o telefone só neste lote, com rastro de quem mudou."""
    lot.exigir(lot.pode_importar(request.user, cache=_cache(request)))

    colaborador = get_object_or_404(ColaboradorPonto, pk=pk)
    try:
        lot.corrigir_telefone(colaborador, request.POST.get("telefone", ""), request)
        messages.success(request, f"Telefone de {colaborador.nome} atualizado neste lote.")
    except lot.UploadInvalido as erro:
        messages.error(request, erro.mensagem)

    return redirect(f"{reverse('workspace:pendencias_ponto')}?lote={colaborador.lote_id}")


@login_required
@require_POST
def ponto_selecionar(request: HttpRequest, pk: int) -> HttpResponse:
    """§15 — quem entra no disparo. Inválido nunca é marcado, nem à força."""
    lot.exigir(lot.pode_importar(request.user, cache=_cache(request)))
    lote = get_object_or_404(LotePonto, pk=pk)

    escolhidos = {int(v) for v in request.POST.getlist("colaborador") if v.isdigit()}
    for colaborador in lote.colaboradores.all():
        marcado = colaborador.pk in escolhidos and colaborador.pode_produzir
        if marcado != colaborador.selecionado:
            colaborador.selecionado = marcado
            colaborador.save(update_fields=["selecionado"])

    return redirect(f"{reverse('workspace:pendencias_ponto')}?lote={lote.pk}")


@login_required
def ponto_mensagem(request: HttpRequest, pk: int) -> HttpResponse:
    """§17 — a prévia. Só mostra; não existe envio a partir daqui."""
    lot.exigir(lot.pode_ler(request.user, cache=_cache(request)))
    colaborador = get_object_or_404(ColaboradorPonto, pk=pk)

    espelho = motor.Colaborador(
        nome=colaborador.nome,
        pendencias=[
            motor.Pendencia(data=p.get("data", ""), motivo=p.get("motivo", ""))
            for p in colaborador.pendencias
        ],
    )
    return render(
        request,
        "workspace/ponto/_mensagem.html",
        {"colaborador": colaborador, "mensagem": espelho.mensagem()},
    )


@login_required
@require_POST
def ponto_enviar(request: HttpRequest, pk: int) -> HttpResponse:
    """Etapas 4 e 5 — o disparo, em teste ou em produção.

    As duas vivem na mesma view porque a diferença entre elas não é o caminho e
    sim a PERMISSÃO e a confirmação: separar em duas rotas duplicaria a
    montagem do lote e criaria um segundo lugar onde a barreira precisa existir.
    """
    lote = get_object_or_404(LotePonto, pk=pk)
    cache = _cache(request)
    producao = request.POST.get("modo") == ModoEnvio.PRODUCAO

    if producao:
        # A permissão do §32 que nunca é derivada de outra.
        lot.exigir(lot.pode_enviar_producao(request.user, cache=cache))
        # §21: a palavra digitada. Confere no servidor — o `disabled` do botão
        # é conveniência da tela e some com um F12.
        if request.POST.get("confirmacao", "").strip().upper() != "ENVIAR":
            messages.error(request, 'Digite ENVIAR para confirmar o disparo real.')
            return redirect(f"{reverse('workspace:pendencias_ponto')}?lote={lote.pk}")
        lote.modo = ModoEnvio.PRODUCAO
        lote.save(update_fields=["modo", "atualizado_em"])
        lot.registrar(lote, AcaoPonto.PRODUCAO_CONFIRMADA, request)
    else:
        lot.exigir(lot.pode_testar(request.user, cache=cache))
        lote.modo = ModoEnvio.TESTE
        lote.telefone_teste = request.POST.get("telefone_teste", "").strip()[:20]
        lote.save(update_fields=["modo", "telefone_teste", "atualizado_em"])
        lot.registrar(lote, AcaoPonto.TESTE_SOLICITADO, request)

    selecionados = lote.colaboradores.filter(selecionado=True)
    if not selecionados.exists():
        messages.error(request, "Selecione ao menos um colaborador.")
        return redirect(f"{reverse('workspace:pendencias_ponto')}?lote={lote.pk}")

    try:
        envios = zap.preparar_envios(lote, selecionados)
    except zap.FalhaDeSeguranca as erro:
        lot.registrar(lote, AcaoPonto.ENVIO_FALHOU, request, str(erro)[:400])
        messages.error(request, str(erro))
        return redirect(f"{reverse('workspace:pendencias_ponto')}?lote={lote.pk}")

    lote.situacao = SituacaoLote.PROCESSANDO
    lote.save(update_fields=["situacao", "atualizado_em"])
    lot.registrar(
        lote,
        AcaoPonto.ENVIO_REAL_INICIADO if producao else AcaoPonto.TESTE_EXECUTADO,
        request,
        f"{len(envios)} mensagens",
    )

    try:
        resultado = zap.despachar(lote, envios)
    except zap.FalhaDeIntegracao as erro:
        zap.fechar_lote(lote, zap.Resultado(enviados=0, falhas=len(envios)))
        lot.registrar(lote, AcaoPonto.ENVIO_FALHOU, request, str(erro)[:400])
        messages.error(request, str(erro))
        return redirect(f"{reverse('workspace:pendencias_ponto')}?lote={lote.pk}")

    zap.fechar_lote(lote, resultado)
    lot.registrar(
        lote,
        AcaoPonto.ENVIO_CONCLUIDO,
        request,
        f"{resultado.enviados} enviadas · {resultado.falhas} falhas",
    )

    onde = "para o telefone de teste" if lote.em_teste else "para os colaboradores"
    messages.success(
        request,
        f"Envio concluído {onde}: {resultado.enviados} mensagens enviadas, "
        f"{resultado.falhas} falhas.",
    )
    return redirect(f"{reverse('workspace:pendencias_ponto')}?lote={lote.pk}")


@login_required
def ponto_progresso(request: HttpRequest, pk: int) -> JsonResponse:
    """§26 — o polling. JSON pequeno, sem dado pessoal."""
    lot.exigir(lot.pode_ler(request.user, cache=_cache(request)))
    lote = get_object_or_404(LotePonto, pk=pk)
    return JsonResponse(zap.progresso(lote))


@login_required
def ponto_historico(request: HttpRequest) -> HttpResponse:
    """§28 — os lotes já processados."""
    lot.exigir(lot.pode_ler(request.user, cache=_cache(request)))
    # As contagens vêm do banco. Contar em template obrigaria a carregar todos
    # os envios de todos os lotes para descobrir quantos deram certo.
    lotes = (
        LotePonto.objects.select_related("quem_importou")
        .annotate(
            n_colaboradores=Count("colaboradores", distinct=True),
            n_sucesso=Count(
                "envios", filter=Q(envios__situacao=SituacaoEnvio.ENVIADO), distinct=True
            ),
            n_falha=Count(
                "envios", filter=Q(envios__situacao=SituacaoEnvio.ERRO), distinct=True
            ),
        )[:LIMITE_HISTORICO]
    )
    return render(request, "workspace/ponto/historico.html", {"lotes": lotes})


@login_required
def ponto_lote(request: HttpRequest, pk: int) -> HttpResponse:
    """§29 — o detalhe de um lote: o cabeçalho e a linha de cada envio."""
    lot.exigir(lot.pode_ler(request.user, cache=_cache(request)))
    lote = get_object_or_404(
        LotePonto.objects.select_related("quem_importou"), pk=pk
    )
    return render(
        request,
        "workspace/ponto/lote.html",
        {
            "lote": lote,
            "resumo": lot.resumo(lote),
            "envios": lote.envios.select_related("colaborador"),
            "eventos": lote.eventos.select_related("quem"),
            "telefone_teste_mascarado": motor.mascarar_telefone(
                motor.normalizar_telefone(lote.telefone_teste)
            ),
        },
    )
