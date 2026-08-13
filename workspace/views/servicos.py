"""Catálogo de serviços — as telas de pedir e acompanhar."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from workspace.acesso import pessoa_da_requisicao
from workspace.models.anexo import Anexo
from workspace.models.catalogo import ItemCatalogo, TipoCampo
from workspace.services import anexos as anx
from workspace.services import catalogo as svc
from workspace.services.anexos import AnexoError
from workspace.services.catalogo import SolicitacaoError


def _cache(request: HttpRequest) -> dict:
    """Cache de permissão por requisição. O middleware do ST-0xx cria isto;
    até lá, cada view garante o seu."""
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


def catalogo(request: HttpRequest) -> HttpResponse:
    """O catálogo agrupado por intenção, com prazo real medido."""
    cache = _cache(request)
    pessoa = pessoa_da_requisicao(request)
    grupos = []
    for rotulo, itens in svc.agrupado_para(pessoa, cache=cache).items():
        grupos.append(
            {
                "rotulo": rotulo,
                "itens": [
                    {"item": item, "prazo": svc.prazo_medido(item)} for item in itens
                ],
            }
        )

    minhas = svc.minhas(pessoa)
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


def pedir(request: HttpRequest, chave: str) -> HttpResponse:
    """Formulário de um item. Valida antes de enviar e bloqueia com o motivo."""
    item = get_object_or_404(ItemCatalogo, chave=chave, ativo=True)
    cache = _cache(request)
    pessoa = pessoa_da_requisicao(request)

    dados = {}
    arquivos = {}
    valor = None
    impedimentos = []

    if request.method == "POST":
        dados = {
            campo["chave"]: (request.POST.get(campo["chave"]) or "").strip()
            for campo in item.campos
            if campo.get("tipo") != TipoCampo.ARQUIVO
        }
        arquivos = {
            campo["chave"]: request.FILES.getlist(campo["chave"])
            for campo in item.campos
            if campo.get("tipo") == TipoCampo.ARQUIVO
        }
        valor = _valor_de(request.POST.get("valor"))

        try:
            solicitacao = svc.solicitar(
                item, pessoa, dados, valor, cache=cache, arquivos=arquivos
            )
        except (SolicitacaoError, AnexoError) as erro:
            # Revalida para devolver a lista completa por campo, e não só a
            # primeira mensagem: corrigir um erro por vez é o que faz o usuário
            # desistir no terceiro envio.
            impedimentos = svc.verificar(
                item, pessoa, dados, valor, cache=cache, arquivos=arquivos
            )
            if not impedimentos:
                # A revalidação não reproduziu a falha — só acontece se algo
                # falhou na gravação, não na validação. Formulário que recusa
                # sem dizer nada é pior que a mensagem crua.
                impedimentos = [svc.Impedimento("anexos", str(erro))]
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
        {
            **campo,
            "valor": dados.get(campo["chave"], ""),
            "erro": por_campo.get(campo["chave"]),
            # O template não compara string de tipo: a view resolve, como manda
            # o design system.
            "e_arquivo": campo.get("tipo") == TipoCampo.ARQUIVO,
        }
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
            "centro_custo": svc._centro_custo_de(pessoa),
            "maximo_anexos": anx.MAXIMO_POR_CAMPO,
        },
    )


def baixar_anexo(request: HttpRequest, pk: int) -> HttpResponse:
    """O único caminho até um anexo. Autoriza, então entrega.

    Não existe URL pública para estes arquivos: eles moram fora de MEDIA_ROOT e
    o storage não tem `base_url` (ver `workspace/storage.py`). Se esta view negar,
    não há segunda porta.
    """
    anexo = get_object_or_404(
        Anexo.objects.select_related("solicitacao", "solicitacao__aprovacao"), pk=pk
    )
    pessoa = pessoa_da_requisicao(request)

    if not anx.pode_baixar(pessoa, anexo, cache=_cache(request)):
        # 403 e não 404: quem chegou aqui tem o id de um anexo que existe, e
        # mentir sobre a existência não protege nada que o 403 já não proteja.
        raise PermissionDenied("Você não tem acesso a este anexo.")

    try:
        arquivo = anexo.arquivo.open("rb")
    except FileNotFoundError:
        # Metadado na tabela e arquivo ausente no disco: erro de operação, e a
        # tela precisa dizer "não está lá" em vez de estourar 500.
        raise Http404("Arquivo não encontrado no armazenamento.")

    # `as_attachment` sempre: comprovante e atestado não devem ser renderizados
    # inline no navegador — SVG e HTML abrem porta para XSS na nossa origem.
    return FileResponse(
        arquivo, as_attachment=True, filename=anexo.nome_original
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


def minhas_solicitacoes(request: HttpRequest) -> HttpResponse:
    solicitacoes = svc.minhas(pessoa_da_requisicao(request))
    return render(
        request,
        "workspace/servicos/minhas.html",
        {
            "solicitacoes": solicitacoes,
            "abertas": solicitacoes.filter(situacao__in=_ABERTAS).count(),
        },
    )


def cancelar(request: HttpRequest, pk: int) -> HttpResponse:
    pessoa = pessoa_da_requisicao(request)
    solicitacao = get_object_or_404(svc.minhas(pessoa), pk=pk)
    if request.method == "POST":
        try:
            svc.cancelar(solicitacao, pessoa)
            messages.success(request, "Solicitação cancelada.")
        except SolicitacaoError as erro:
            messages.error(request, str(erro))
    return redirect(reverse("workspace:minhas_solicitacoes"))
