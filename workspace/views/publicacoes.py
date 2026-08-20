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
    # O QUE A TELA DEVOLVE QUANDO A GRAVAÇÃO FALHA.
    #
    # Antes, um erro de validação re-renderizava o formulário a partir do
    # OBJETO — que é `None` numa publicação nova. O comunicado inteiro
    # desaparecia da tela, sobrando uma faixa vermelha em cima de campos
    # vazios. Perder o texto por causa de uma data digitada errada é o tipo de
    # coisa que faz alguém parar de usar a tela e voltar para o e-mail.
    valores = _valores_de(publicacao)

    if request.method == "POST":
        valores = _valores_do_post(request)
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
            "valores": valores,
            "tipos": TipoPublicacao.choices,
            "prioridades": Prioridade.choices,
            "unidades": Unidade.objects.order_by("nome"),
            "departamentos": Departamento.objects.order_by("nome"),
            "alvo_unidades": valores["unidades"],
            "alvo_departamentos": valores["departamentos"],
        },
    )


def _valores_de(publicacao: Publicacao | None) -> dict:
    """O que preencher no formulário a partir do objeto (ou do nada)."""
    if publicacao is None:
        return {
            "titulo": "", "tipo": TipoPublicacao.COMUNICADO, "resumo": "", "corpo": "",
            "prioridade": Prioridade.NORMAL.value, "fixado": False,
            "publicar_em": "", "expira_em": "",
            "unidades": set(), "departamentos": set(),
        }
    return {
        "titulo": publicacao.titulo,
        "tipo": publicacao.tipo,
        "resumo": publicacao.resumo,
        "corpo": publicacao.corpo,
        "prioridade": publicacao.prioridade,
        "fixado": publicacao.fixado,
        "publicar_em": _para_campo(publicacao.publicar_em),
        "expira_em": _para_campo(publicacao.expira_em),
        "unidades": {u.pk for u in publicacao.unidades.all()},
        "departamentos": {d.pk for d in publicacao.departamentos.all()},
    }


def _valores_do_post(request: HttpRequest) -> dict:
    """O que a pessoa acabou de digitar — para devolver intacto quando falha.

    Os arquivos NÃO voltam, e não há como fazê-los voltar: o navegador não
    aceita valor inicial em `<input type="file">`, por segurança. É por isso
    que a ajuda ao lado do campo avisa para reanexar.
    """
    inteiros = lambda chave: {  # noqa: E731 - duas linhas, uma expressão
        int(v) for v in request.POST.getlist(chave) if v.isdigit()
    }
    return {
        "titulo": request.POST.get("titulo", ""),
        "tipo": request.POST.get("tipo", TipoPublicacao.COMUNICADO),
        "resumo": request.POST.get("resumo", ""),
        "corpo": request.POST.get("corpo", ""),
        # INT e não a string crua: o template compara com os valores de
        # `Prioridade.choices`, que são inteiros. `"1" == 1` é falso, e o
        # `<select>` voltaria em "Normal" depois de um erro — trocando a
        # prioridade da pessoa em silêncio, no exato momento em que ela já
        # está irritada com a tela.
        "prioridade": _inteiro(request.POST.get("prioridade"), Prioridade.NORMAL.value),
        "fixado": bool(request.POST.get("fixado")),
        "publicar_em": request.POST.get("publicar_em", ""),
        "expira_em": request.POST.get("expira_em", ""),
        "unidades": inteiros("unidades"),
        "departamentos": inteiros("departamentos"),
    }


def _inteiro(bruto, padrao: int) -> int:
    try:
        return int(bruto)
    except (TypeError, ValueError):
        return padrao


def _para_campo(momento) -> str:
    r"""`datetime` → o formato que `<input type="datetime-local">` entende.

    Feito aqui e não no template porque o formulário passou a ler de um dicionário
    (para poder devolver o que a pessoa digitou), e `|date:'Y-m-d\TH:i'` sobre
    uma string já formatada devolveria vazio.
    """
    if not momento:
        return ""
    return timezone.localtime(momento).strftime("%Y-%m-%dT%H:%M")


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
