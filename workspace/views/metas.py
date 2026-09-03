"""Metas, avaliação e PDI (14) — o quadro de uma pessoa.

## Todo mundo vê o próprio quadro

`met.ler.proprio` está no autoatendimento. É a diferença entre um sistema de
metas e um sistema de avaliação secreta — e é o que faz a tela ser usada pela
pessoa, e não só pelo gestor dela.

## A fronteira

GET do próprio quadro é autoatendimento. Escrever meta exige `met.definir` sobre
a pessoa; aprovar, reabrir e apurar exigem `met.aprovar` — e `pode()` faz o
trabalho do alcance, pelo organograma.

## Nenhuma tela lista pessoas com nota

`equipe_de()` devolve **situação**, e a tela do R.H. devolve **contagem**.
Restrição 8, e é aqui que ela é mais fácil de violar sem perceber: uma coluna de
nota ao lado de uma lista de nomes é uma planilha de desempenho, e ela circula.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from workspace.models.meta import (
    AcaoDesenvolvimento,
    CicloMetas,
    GrupoMeta,
    Meta,
    QuadroMetas,
)
from workspace.services import metas as svc


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


def _ciclo(request: HttpRequest) -> CicloMetas:
    chave = request.GET.get("ciclo", "") or request.POST.get("ciclo", "")
    if chave:
        ciclo = CicloMetas.objects.filter(chave=chave).first()
        if ciclo is None:
            raise Http404("Ciclo desconhecido.")
        return ciclo
    ciclo = svc.ciclo_corrente()
    if ciclo is None:
        # Sem ciclo nenhum a tela não tem o que mostrar — e a mensagem diz o que
        # falta, em vez de renderizar um quadro vazio que parece defeito.
        raise Http404(
            "Nenhum ciclo de metas cadastrado. Rode `semear_ciclo_metas --aplicar`."
        )
    return ciclo


def _pessoa(request: HttpRequest, pessoa_id: int | None):
    if pessoa_id is None:
        return request.user
    return get_object_or_404(get_user_model(), pk=pessoa_id, is_active=True)


@login_required
def metas(request: HttpRequest, pessoa_id: int | None = None) -> HttpResponse:
    """O quadro — o meu, por padrão; o de um liderado, quando pedido."""
    ciclo = _ciclo(request)
    alvo = _pessoa(request, pessoa_id)

    try:
        contexto = svc.tela_do_quadro(alvo, ciclo, request.user, cache=_cache(request))
    except svc.SemMetas as sem:
        raise PermissionDenied(str(sem))

    contexto["equipe"] = svc.equipe_de(request.user, ciclo, cache=_cache(request))
    contexto["resumo"] = (
        svc.resumo_por_situacao(ciclo) if contexto["equipe"] else None
    )
    return render(request, "workspace/metas.html", contexto)


@require_POST
@login_required
def abrir_quadro(request: HttpRequest, pessoa_id: int) -> HttpResponse:
    ciclo = _ciclo(request)
    alvo = _pessoa(request, pessoa_id)
    try:
        svc.abrir_quadro(alvo, ciclo, request.user, cache=_cache(request))
    except svc.MetaError as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, f"Quadro de {alvo.nome} aberto em rascunho.")
    return redirect(f"{_url_do_quadro(alvo, request.user)}?ciclo={ciclo.chave}")


def _url_do_quadro(alvo, quem) -> str:
    from django.urls import reverse

    if alvo.pk == getattr(quem, "pk", None):
        return reverse("workspace:metas")
    return reverse("workspace:metas_de", kwargs={"pessoa_id": alvo.pk})


@login_required
def meta_editar(request: HttpRequest, quadro_id: int) -> HttpResponse:
    """Uma meta por vez. Formulário simples, e a fórmula à vista."""
    quadro = get_object_or_404(
        QuadroMetas.objects.select_related("ciclo", "pessoa"), pk=quadro_id
    )
    if not svc.pode_ver(quadro, request.user, cache=_cache(request)):
        raise PermissionDenied("Este quadro não é seu nem de quem você lidera.")

    meta = None
    if request.GET.get("meta") or request.POST.get("meta"):
        meta = Meta.objects.filter(
            pk=request.GET.get("meta") or request.POST.get("meta"), quadro=quadro
        ).first()
        if meta is None:
            # Filtrado POR QUADRO na consulta: um `pk` de meta de outro quadro
            # escreveria na avaliação de outra pessoa.
            raise Http404("Meta desconhecida neste quadro.")

    if request.method == "POST":
        try:
            svc.salvar_meta(
                quadro,
                request.user,
                meta,
                descricao=request.POST.get("descricao", ""),
                fator_1=request.POST.get("fator_1", ""),
                fator_2=request.POST.get("fator_2", ""),
                grupo=request.POST.get("grupo", ""),
                peso=request.POST.get("peso", 1),
                alvo=request.POST.get("alvo"),
                tipo_calculo=request.POST.get("tipo_calculo", "direto"),
                detalhamento=request.POST.get("detalhamento", ""),
                cache=_cache(request),
            )
        except svc.MetaError as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Meta salva.")
            return redirect(
                f"{_url_do_quadro(quadro.pessoa, request.user)}"
                f"?ciclo={quadro.ciclo.chave}"
            )

    return render(
        request,
        "workspace/meta_editar.html",
        {
            "quadro": quadro,
            "meta": meta,
            "fatores": svc.cat.todos(),
            # As escolhas vêm da VIEW e não de um caminho de atributo no
            # template. `quadro.metas.model.grupo.field.choices` funciona e é o
            # tipo de linha que quebra numa atualização do Django sem nada no
            # teste apontar para ela.
            "grupos": GrupoMeta.choices,
            "pode_definir": svc.pode_definir(quadro, request.user, cache=_cache(request)),
        },
    )


@require_POST
@login_required
def meta_remover(request: HttpRequest, quadro_id: int) -> HttpResponse:
    quadro = get_object_or_404(QuadroMetas, pk=quadro_id)
    meta = Meta.objects.filter(pk=request.POST.get("meta") or 0, quadro=quadro).first()
    if meta is None:
        raise Http404("Meta desconhecida neste quadro.")
    try:
        svc.remover_meta(meta, request.user, cache=_cache(request))
    except svc.MetaError as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, "Meta removida.")
    return redirect(
        f"{_url_do_quadro(quadro.pessoa, request.user)}?ciclo={quadro.ciclo.chave}"
    )


@require_POST
@login_required
def quadro_acao(request: HttpRequest, quadro_id: int) -> HttpResponse:
    """Aprovar, reabrir e apurar — os três atos que mudam o estado do quadro.

    Uma view para os três porque o destino e a checagem são os mesmos; o que
    muda é uma linha. Três views divergiriam no redirecionamento, que é
    justamente o que a pessoa percebe.
    """
    quadro = get_object_or_404(
        QuadroMetas.objects.select_related("ciclo", "pessoa"), pk=quadro_id
    )
    if not svc.pode_ver(quadro, request.user, cache=_cache(request)):
        raise PermissionDenied("Este quadro não é seu nem de quem você lidera.")

    acao = request.POST.get("acao", "")
    try:
        if acao == "aprovar":
            svc.aprovar(quadro, request.user, cache=_cache(request))
            messages.success(request, "Quadro aprovado. As metas ficam como estão.")
        elif acao == "reabrir":
            svc.reabrir(
                quadro, request.user, request.POST.get("motivo", ""),
                cache=_cache(request),
            )
            messages.warning(request, "Quadro reaberto. O motivo ficou registrado.")
        elif acao == "apurar":
            svc.apurar(quadro, request.user, cache=_cache(request))
            nao = len(quadro.nao_apuradas)
            if nao:
                # "Não apurada" não é zero, e a mensagem diz isso na hora — sem
                # ela, quem apurou leria a nota como se fosse sobre tudo.
                messages.warning(
                    request,
                    f"Quadro apurado. {nao} meta(s) ficaram SEM apuração — o "
                    "motivo está em cada uma, e elas não entram na nota.",
                )
            else:
                messages.success(request, "Quadro apurado.")
        else:
            raise Http404("Ação desconhecida.")
    except svc.MetaError as erro:
        messages.error(request, str(erro))

    return redirect(
        f"{_url_do_quadro(quadro.pessoa, request.user)}?ciclo={quadro.ciclo.chave}"
    )


# ── PDI ─────────────────────────────────────────────────────────────


@login_required
def desenvolvimento(request: HttpRequest, pessoa_id: int | None = None) -> HttpResponse:
    """O PDI. Escrito pela PESSOA — o gestor lê, e não redige por ela."""
    ciclo = _ciclo(request)
    alvo = _pessoa(request, pessoa_id)

    if not svc._alcanca(request.user, svc.PERMISSAO, alvo, cache=_cache(request)):
        raise PermissionDenied("Este plano de desenvolvimento não é seu.")

    if request.method == "POST":
        try:
            svc.salvar_pdi(
                alvo, ciclo, request.user, cache=_cache(request),
                responsabilidades=request.POST.get("responsabilidades", ""),
                interesses=request.POST.get("interesses", ""),
                aspiracao_curta=request.POST.get("aspiracao_curta", ""),
                aspiracao_longa=request.POST.get("aspiracao_longa", ""),
            )
        except svc.MetaError as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, "Plano de desenvolvimento salvo.")
            return redirect(
                f"{request.path}?ciclo={ciclo.chave}"
            )

    plano = svc.pdi_de(alvo, ciclo)
    return render(
        request,
        "workspace/desenvolvimento.html",
        {
            "alvo": alvo,
            "ciclo": ciclo,
            "ciclos": list(CicloMetas.objects.all()[:12]),
            "plano": plano,
            "acoes": list(plano.acoes.all()) if plano else [],
            "sou_eu": alvo.pk == request.user.pk,
            "editavel": ciclo.situacao != "fechado",
        },
    )


@require_POST
@login_required
def acao_pdi(request: HttpRequest, pessoa_id: int | None = None) -> HttpResponse:
    """Acrescenta ou conclui uma ação do PDI."""
    from django.urls import reverse

    ciclo = _ciclo(request)
    alvo = _pessoa(request, pessoa_id)
    # `reverse` e não um caminho escrito à mão. O caminho literal já estava
    # errado — a rota mora sob `metas/`, e o teste do mês inválido devolvia 404
    # em vez da mensagem. Caminho em texto é uma cópia da URLconf que envelhece
    # sozinha.
    destino = (
        reverse("workspace:desenvolvimento")
        if alvo.pk == request.user.pk
        else reverse("workspace:desenvolvimento_de", kwargs={"pessoa_id": alvo.pk})
    )
    destino = f"{destino}?ciclo={ciclo.chave}"

    plano = svc.pdi_de(alvo, ciclo)
    if plano is None:
        raise Http404("Este plano de desenvolvimento ainda não existe.")

    try:
        if request.POST.get("acao") == "concluir":
            item = AcaoDesenvolvimento.objects.filter(
                pk=request.POST.get("item") or 0, plano=plano
            ).first()
            if item is None:
                raise Http404("Ação desconhecida neste plano.")
            svc.concluir_acao(item, request.user, cache=_cache(request))
            messages.success(request, "Ação concluída.")
        else:
            svc.acrescentar_acao(
                plano,
                request.user,
                descricao=request.POST.get("descricao", ""),
                mes=request.POST.get("mes", 0),
                ano=request.POST.get("ano", 0),
                cache=_cache(request),
            )
            messages.success(request, "Ação registrada.")
    except svc.MetaError as erro:
        messages.error(request, str(erro))

    return redirect(destino)
