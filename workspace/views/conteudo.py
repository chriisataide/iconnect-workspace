"""Documentação — o acervo, a leitura de um documento, e a redação dele.

A redação entrou no §37 pelo mesmo motivo da de comunicados: o acervo podia ser
LIDO e não podia ser MANTIDO. Criar um POP exigia o `/admin/` do Django, que
pede `is_staff` — e quem escreve procedimento é a área que o executa, não quem
administra o banco. Na prática, publicar norma significava pedir para outra
pessoa.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date

from identidade.models import Departamento, Unidade
from workspace.acesso import pessoa_da_requisicao
from workspace.models.conteudo import Documento, TipoDocumento
from workspace.services import conteudo as cnt


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


def documentacao(request: HttpRequest) -> HttpResponse:
    """A vitrine, agrupada por tipo.

    Duas pessoas nesta view, de propósito:

    - `pessoa` decide o ALCANCE — quais documentos o acervo mostra. É onde a
      pessoa de referência do hub aberto continua valendo, porque saber que um
      POP existe é informação institucional.
    - `quem` decide o que é PESSOAL — quantas leituras faltam confirmar. Isso é
      de uma pessoa, e o visitante anônimo estava vendo o número de outra: o
      contador dizia "3 pendentes" para quem nunca entrou, contando os
      documentos que uma conta específica ainda não tinha lido.
    """
    cache = _cache(request)
    pessoa = pessoa_da_requisicao(request)
    quem = request.user if request.user.is_authenticated else None

    categoria = request.GET.get("categoria", "")
    texto = request.GET.get("q", "")
    categorias = cnt.categorias_de(pessoa, cache=cache)
    # Categoria forjada na URL vira "sem filtro" e não lista vazia: a pessoa
    # colou um link velho, e uma tela vazia faz o acervo parecer apagado.
    if categoria not in categorias:
        categoria = ""

    grupos = [
        {"rotulo": rotulo, "documentos": documentos}
        for rotulo, documentos in cnt.agrupado_para(
            pessoa, cache=cache, categoria=categoria, texto=texto
        ).items()
    ]
    return render(
        request,
        "workspace/documentacao.html",
        {
            "grupos": grupos,
            "autenticado": quem is not None,
            "pendentes": (
                len(cnt.pendentes_de_leitura(quem, cache=cache)) if quem else 0
            ),
            "total": sum(len(g["documentos"]) for g in grupos),
            # §37 — filtros e recentes.
            "categorias": categorias,
            "categoria_atual": categoria,
            "busca": texto,
            "filtrado": bool(categoria or texto.strip()),
            # Os recentes ignoram o filtro de propósito: eles respondem "o que
            # mudou", que é outra pergunta — e recalculá-los a cada filtro faria
            # a faixa piscar sem motivo.
            "recentes": cnt.recentes_para(pessoa, cache=cache),
            # §37 — quem MANTÉM o acervo chega por aqui.
            "mantem_acervo": cnt.pode_publicar(request.user, cache=cache),
        },
    )


def documento(request: HttpRequest, slug: str) -> HttpResponse:
    """A leitura. Vencido e revogado abrem, com aviso — ver `cnt.pode_ver`."""
    doc = get_object_or_404(Documento.objects.select_related("dono", "revoga"), slug=slug)
    cache = _cache(request)
    pessoa = pessoa_da_requisicao(request)

    if not cnt.pode_ver(doc, pessoa, cache=cache):
        raise PermissionDenied("Você não tem acesso a este documento.")

    substituto = doc.revogado_por.filter(situacao="vigente").first()
    return render(
        request,
        "workspace/documento.html",
        {
            "documento": doc,
            "autenticado": True,
            "ja_confirmou": cnt.ja_confirmou(doc, pessoa),
            "cobertura": cnt.cobertura_de_leitura(doc),
            "e_dono": getattr(pessoa, "pk", None) == doc.dono_id,
            # Documento revogado sem para onde ir é um beco: a pessoa descobre
            # que o texto não vale e não sabe qual vale.
            "substituto": substituto,
            # Quem pode anexar o ARQUIVO (§33). `request.user` e não `pessoa`:
            # anexar é ato em nome de alguém, e a pessoa de referência do hub
            # aberto não pode publicar documento da empresa.
            "pode_publicar": cnt.pode_publicar(request.user, cache=cache),
        },
    )


@login_required
def confirmar_leitura(request: HttpRequest, slug: str) -> HttpResponse:
    """POST apenas: confirmação é escrita, e GET não muda estado.

    Sem isso, o pré-carregamento de link do navegador registraria conformidade
    que a pessoa nunca declarou — e é exatamente esse registro que se leva para
    uma audiência.

    Pelo mesmo motivo, `@login_required`: é a declaração de que uma pessoa
    NOMEADA leu um normativo. Ler o documento continua aberto; assinar que leu,
    não — a confirmação anônima entraria com o nome de outra pessoa, e é essa
    linha que a empresa apresenta quando precisa provar conformidade.
    """
    doc = get_object_or_404(Documento, slug=slug)
    pessoa = request.user
    if request.method != "POST":
        return redirect(reverse("workspace:documento", args=(slug,)))

    if not cnt.pode_ver(doc, pessoa, cache=_cache(request)):
        raise PermissionDenied("Você não tem acesso a este documento.")

    try:
        cnt.confirmar(doc, pessoa)
    except cnt.ConteudoError as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, f"Leitura de {doc.titulo} confirmada.")

    return redirect(reverse("workspace:documento", args=(slug,)))


@login_required
def baixar_documento(request: HttpRequest, slug: str) -> HttpResponse:
    """Entrega o arquivo do documento — §33.

    Autoriza ANTES de entregar, como o anexo de solicitação. O arquivo mora em
    armazenamento sem URL pública justamente para que esta seja a única porta:
    política interna, POP com desenho de instalação e contrato-modelo não devem
    ficar num caminho que o nginx serve sem perguntar quem é.
    """
    from django.http import FileResponse, Http404

    documento = get_object_or_404(Documento, slug=slug)
    if not cnt.pode_ver(documento, request.user, cache=_cache(request)):
        raise PermissionDenied("Este documento não é do seu alcance.")
    if not documento.arquivo:
        raise Http404("Este documento não tem arquivo.")

    return FileResponse(
        documento.arquivo.open("rb"),
        as_attachment=True,
        filename=documento.arquivo_nome or f"{documento.slug}.pdf",
    )


@login_required
def anexar_documento(request: HttpRequest, slug: str) -> HttpResponse:
    """Sobe o arquivo de um documento existente — §33."""
    if request.method != "POST":
        return redirect(reverse("workspace:documento", args=[slug]))

    documento = get_object_or_404(Documento, slug=slug)
    arquivo = request.FILES.get("arquivo")
    if arquivo is None:
        messages.error(request, "Escolha um arquivo.")
        return redirect(reverse("workspace:documento", args=[slug]))

    try:
        cnt.anexar_arquivo(documento, arquivo, request.user, cache=_cache(request))
    except cnt.DocumentoError as falha:
        messages.error(request, str(falha))
    else:
        messages.success(request, "Arquivo anexado.")

    return redirect(reverse("workspace:documento", args=[slug]))


# ── A redação do acervo — §37 ───────────────────────────────────────


@login_required
def documentos(request: HttpRequest) -> HttpResponse:
    """A lista de quem MANTÉM a norma — inclusive o que saiu do ar.

    Diferente da vitrine, e a diferença é o ponto: quem escreve precisa ver
    justamente o rascunho, o vencido e o revogado, porque é isso que dá trabalho
    a ele. A vitrine mostra o que vale hoje.
    """
    cache = _cache(request)
    if not cnt.pode_publicar(request.user, cache=cache):
        # 403 e não uma lista vazia, pela mesma razão da redação de comunicados:
        # um acervo vazio para quem nunca vai publicar faz a pessoa achar que a
        # empresa não tem norma nenhuma.
        raise PermissionDenied("Esta tela é de quem publica documentos.")

    return render(
        request,
        "workspace/documentos.html",
        {
            "documentos": list(cnt.redacao(request.user, cache=cache)),
            "a_vencer": list(cnt.a_vencer()),
            "vencidos": list(cnt.vencidos()),
        },
    )


@login_required
def documento_editar(request: HttpRequest, slug: str | None = None) -> HttpResponse:
    """Uma tela para criar e para editar.

    Duas telas divergiriam na terceira semana — e a validação que existe só numa
    delas é a porta por onde entra o POP sem título.
    """
    cache = _cache(request)
    if not cnt.pode_publicar(request.user, cache=cache):
        raise PermissionDenied("Esta tela é de quem publica documentos.")

    doc = get_object_or_404(Documento, slug=slug) if slug else None

    if request.method == "POST":
        try:
            salvo = cnt.salvar(
                request.user,
                doc,
                slug=request.POST.get("slug", ""),
                titulo=request.POST.get("titulo", ""),
                tipo=request.POST.get("tipo", ""),
                categoria=request.POST.get("categoria", ""),
                resumo=request.POST.get("resumo", ""),
                corpo=request.POST.get("corpo", ""),
                versao=request.POST.get("versao", ""),
                unidades=request.POST.getlist("unidades"),
                departamentos=request.POST.getlist("departamentos"),
                leitura_obrigatoria=bool(request.POST.get("leitura_obrigatoria")),
                vigencia_inicio=parse_date(request.POST.get("vigencia_inicio") or ""),
                vigencia_fim=parse_date(request.POST.get("vigencia_fim") or ""),
                # Dois botões, um formulário: o estado sai de QUAL botão foi
                # clicado, e não de uma caixinha que a pessoa esquece de marcar.
                publicar=request.POST.get("acao") == "publicar",
                arquivo=request.FILES.get("arquivo"),
                cache=cache,
            )
        except cnt.DocumentoError as falha:
            messages.error(request, str(falha))
        else:
            messages.success(
                request,
                f"{salvo.titulo} "
                + ("publicado." if salvo.vigente else "salvo como rascunho."),
            )
            return redirect(reverse("workspace:documentos"))

    alvo_unidades, alvo_departamentos = cnt.alvo_para_tela(doc)
    return render(
        request,
        "workspace/documento_editar.html",
        {
            "documento": doc,
            "tipos": TipoDocumento.choices,
            # As categorias que já existem viram sugestão no formulário: texto
            # livre sem lista vira "Segurança", "segurança" e "SEGURANCA" como
            # três assuntos diferentes na mesma tabela.
            "categorias": sorted(
                {
                    c
                    for c in Documento.objects.exclude(categoria="")
                    .values_list("categoria", flat=True)
                    .distinct()
                }
            ),
            "unidades": Unidade.objects.order_by("nome"),
            "departamentos": Departamento.objects.order_by("nome"),
            "alvo_unidades": alvo_unidades,
            "alvo_departamentos": alvo_departamentos,
        },
    )


@login_required
def documento_revogar(request: HttpRequest, slug: str) -> HttpResponse:
    """Tira da vitrine sem apagar — o histórico da norma é o que explica uma
    ocorrência antiga."""
    if request.method != "POST":
        return redirect(reverse("workspace:documentos"))

    doc = get_object_or_404(Documento, slug=slug)
    try:
        cnt.revogar(doc, request.user, cache=_cache(request))
    except cnt.DocumentoError as falha:
        messages.error(request, str(falha))
    else:
        messages.success(request, f"{doc.titulo} revogado — sai da vitrine e fica no acervo.")

    return redirect(reverse("workspace:documentos"))
