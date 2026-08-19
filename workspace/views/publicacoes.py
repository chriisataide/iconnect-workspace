"""A redação — onde comunicado e notícia são escritos, dentro do portal.

`@login_required` e `pode()`: publicar é ato em nome da empresa. A tela também
mostra o que NÃO está no ar (rascunho, agendado, expirado), que é informação de
quem escreve e de mais ninguém.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from identidade.models import Departamento, Unidade
from workspace.models.comunicacao import Prioridade, Publicacao, TipoPublicacao
from workspace.services import publicacao as pub


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


def _garantir(request: HttpRequest) -> None:
    if not pub.pode_publicar(request.user, cache=_cache(request)):
        # 403 e não tela vazia, pela mesma razão do painel de indicadores: uma
        # redação vazia para quem nunca vai publicar faz a pessoa achar que a
        # empresa parou de comunicar.
        raise PermissionDenied("Esta tela é de quem publica comunicados.")


def _quando(bruta: str | None):
    """Data e hora do formulário, ou `None`.

    Valor inválido vira `None` em vez de erro: o texto do comunicado é o que
    custa caro para reescrever, e perdê-lo porque alguém digitou a data errada
    seria trocar um campo por uma tela inteira.
    """
    if not bruta:
        return None
    quando = parse_datetime(bruta.strip())
    if quando is None:
        return None
    return timezone.make_aware(quando) if timezone.is_naive(quando) else quando


@login_required
def publicacoes(request: HttpRequest) -> HttpResponse:
    """A lista de quem escreve — inclusive o que não está no ar."""
    _garantir(request)
    cache = _cache(request)

    return render(
        request,
        "workspace/publicacoes/lista.html",
        {
            "publicacoes": list(pub.redacao(request.user, cache=cache)),
            "arquivadas": list(pub.arquivadas(request.user, cache=cache)),
        },
    )


@login_required
def publicacao_editar(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    """Uma tela para criar e para editar.

    Duas telas divergiriam na terceira semana — e a validação que existe só numa
    delas é a porta por onde entra o comunicado sem título.
    """
    _garantir(request)
    cache = _cache(request)
    publicacao = get_object_or_404(Publicacao, pk=pk) if pk else None

    if request.method == "POST":
        try:
            salva = pub.salvar(
                request.user,
                publicacao,
                titulo=request.POST.get("titulo", ""),
                tipo=request.POST.get("tipo", TipoPublicacao.COMUNICADO),
                resumo=request.POST.get("resumo", ""),
                corpo=request.POST.get("corpo", ""),
                prioridade=request.POST.get("prioridade") or 0,
                fixado=bool(request.POST.get("fixado")),
                # Dois botões, um formulário: "Salvar rascunho" e "Publicar".
                # O estado sai de QUAL botão foi clicado, e não de uma caixinha
                # que a pessoa esquece de marcar.
                publicar=request.POST.get("acao") == "publicar",
                publicar_em=_quando(request.POST.get("publicar_em")),
                expira_em=_quando(request.POST.get("expira_em")),
                unidades=request.POST.getlist("unidades"),
                departamentos=request.POST.getlist("departamentos"),
                imagem=request.FILES.get("imagem"),
                anexo=request.FILES.get("anexo"),
                cache=cache,
            )
        except pub.PublicacaoError as falha:
            messages.error(request, str(falha))
        else:
            messages.success(
                request,
                f"{salva.get_tipo_display()} "
                + ("publicado." if salva.publicado else "salvo como rascunho."),
            )
            return redirect(reverse("workspace:publicacoes"))

    return render(
        request,
        "workspace/publicacoes/editar.html",
        {
            "publicacao": publicacao,
            "tipos": TipoPublicacao.choices,
            "prioridades": Prioridade.choices,
            "unidades": Unidade.objects.order_by("nome"),
            "departamentos": Departamento.objects.order_by("nome"),
            "alvo_unidades": (
                {u.pk for u in publicacao.unidades.all()} if publicacao else set()
            ),
            "alvo_departamentos": (
                {d.pk for d in publicacao.departamentos.all()} if publicacao else set()
            ),
        },
    )


@login_required
def publicacao_acao(request: HttpRequest, pk: int) -> HttpResponse:
    """Publicar, despublicar, arquivar ou excluir. Sempre `POST`."""
    _garantir(request)
    if request.method != "POST":
        return redirect(reverse("workspace:publicacoes"))

    publicacao = get_object_or_404(Publicacao, pk=pk)
    acoes = {
        "publicar": pub.publicar,
        "despublicar": pub.despublicar,
        "arquivar": pub.arquivar,
        "excluir": pub.excluir,
    }
    funcao = acoes.get(request.POST.get("acao", ""))
    if funcao is None:
        messages.error(request, "Ação desconhecida.")
        return redirect(reverse("workspace:publicacoes"))

    titulo = publicacao.titulo
    try:
        funcao(publicacao, request.user, cache=_cache(request))
    except pub.PublicacaoError as falha:
        messages.error(request, str(falha))
    else:
        messages.success(request, f"{titulo} · {request.POST['acao']}.")

    return redirect(reverse("workspace:publicacoes"))
