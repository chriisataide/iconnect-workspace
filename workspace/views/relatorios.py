"""Relatórios de campo — §34, §35 e §36.

Três telas: a lista, o formulário (o "assistente" do §35) e a página emitida,
desenhada para virar PDF pelo navegador.

Fechadas as três. Relatório de ocorrência descreve o que deu errado num local
com cliente e equipe identificados — é exatamente o tipo de documento que não
pode ficar aberto no hub.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date, parse_time

from workspace.models.relatorio import Relatorio, TipoRelatorio
from workspace.services import relatorio as rel


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


@login_required
def relatorios(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "workspace/relatorios/lista.html",
        {
            "relatorios": list(rel.visiveis_para(request.user, cache=_cache(request))),
            "tipos": TipoRelatorio.choices,
        },
    )


@login_required
def relatorio_editar(request: HttpRequest, pk: int | None = None) -> HttpResponse:
    """O assistente do §35 — o questionário estruturado do tipo escolhido.

    "Assistente" aqui é a ESTRUTURA, não IA: o que faz alguém desistir de um
    relatório de campo é a folha em branco. Cinco perguntas respondíveis são o
    que transforma "descreva a ocorrência" em algo que se responde.
    """
    documento = get_object_or_404(Relatorio, pk=pk) if pk else None
    if documento is not None and not rel.pode_ver(documento, request.user, cache=_cache(request)):
        raise PermissionDenied("Este relatório não é seu.")
    if documento is not None and not documento.editavel:
        return redirect(reverse("workspace:relatorio_ver", args=[documento.pk]))

    tipo = (
        documento.tipo
        if documento
        else request.GET.get("tipo") or request.POST.get("tipo") or TipoRelatorio.ENTREGA
    )

    if request.method == "POST":
        dados = {
            campo["chave"]: (request.POST.get(campo["chave"]) or "").strip()
            for campo in rel.questionario(tipo)
        }
        try:
            documento = rel.salvar(
                request.user,
                documento,
                tipo=tipo,
                titulo=request.POST.get("titulo", ""),
                dados=dados,
                cliente=request.POST.get("cliente", ""),
                local=request.POST.get("local", ""),
                ocorrido_em=parse_date(request.POST.get("ocorrido_em") or ""),
                horario=parse_time(request.POST.get("horario") or ""),
            )
            for arquivo in request.FILES.getlist("evidencias"):
                rel.anexar(documento, arquivo)
        except rel.RelatorioError as falha:
            # O rascunho NÃO foi gravado — volta ao formulário com o que a
            # pessoa digitou. Redirecionar aqui apagaria o texto, que é
            # justamente o que custa caro num relatório de campo.
            messages.error(request, str(falha))
            return _formulario(request, documento, tipo, dados)

        if request.POST.get("acao") != "emitir":
            messages.success(request, "Rascunho salvo.")
            return redirect(reverse("workspace:relatorio_editar", args=[documento.pk]))

        try:
            rel.emitir(documento, request.user)
        except rel.RelatorioError as falha:
            # O rascunho ESTÁ salvo; só a emissão falhou. A pessoa volta para o
            # formulário sabendo o que falta, e sem ter perdido nada.
            messages.error(request, str(falha))
            return redirect(reverse("workspace:relatorio_editar", args=[documento.pk]))

        messages.success(request, "Relatório emitido.")
        return redirect(reverse("workspace:relatorio_ver", args=[documento.pk]))

    return _formulario(request, documento, tipo, documento.dados if documento else {})


def _formulario(request: HttpRequest, documento, tipo: str, dados: dict) -> HttpResponse:
    """A tela do assistente, com os valores que a pessoa digitou.

    `dados` entra separado do `documento` porque na volta de um erro o
    documento pode não existir ainda — e o que ela escreveu precisa reaparecer
    do mesmo jeito.
    """
    return render(
        request,
        "workspace/relatorios/editar.html",
        {
            "relatorio": documento,
            "tipo": tipo,
            "tipos": TipoRelatorio.choices,
            "campos": [
                {
                    **campo,
                    "valor": (dados or {}).get(campo["chave"], ""),
                    "e_longo": campo.get("tipo") == "texto_longo",
                    "e_escolha": campo.get("tipo") == "escolha",
                    "ativo": rel.campo_ativo(campo, dados or {}),
                }
                for campo in rel.questionario(tipo)
            ],
        },
    )


@login_required
def relatorio_ver(request: HttpRequest, pk: int) -> HttpResponse:
    """A página do relatório na tela. O PDF é `relatorio_pdf`, logo abaixo.

    Este comentário dizia "sem geração de PDF no servidor" e ficou para trás
    quando o `reportlab` entrou — a rota que gera o arquivo está oito linhas
    abaixo. Comentário que descreve uma decisão revertida é pior que comentário
    nenhum: quem lê confia nele e vai procurar a impressão do navegador.
    """
    documento = get_object_or_404(
        Relatorio.objects.select_related("autor").prefetch_related("evidencias"), pk=pk
    )
    if not rel.pode_ver(documento, request.user, cache=_cache(request)):
        raise PermissionDenied("Este relatório não é seu.")

    return render(
        request,
        "workspace/relatorios/ver.html",
        {"relatorio": documento, "linhas": rel.para_impressao(documento)},
    )


@login_required
def relatorio_acao(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect(reverse("workspace:relatorios"))

    documento = get_object_or_404(Relatorio, pk=pk)
    acoes = {"emitir": rel.emitir, "cancelar": rel.cancelar}
    funcao = acoes.get(request.POST.get("acao", ""))
    if funcao is None:
        messages.error(request, "Ação desconhecida.")
        return redirect(reverse("workspace:relatorios"))

    try:
        funcao(documento, request.user)
    except rel.RelatorioError as falha:
        messages.error(request, str(falha))
    else:
        messages.success(request, f"{documento.titulo} · {request.POST['acao']}.")

    return redirect(reverse("workspace:relatorio_ver", args=[documento.pk]))


@login_required
def relatorio_pdf(request: HttpRequest, pk: int) -> HttpResponse:
    """O PDF gerado no servidor — §35 e §36.

    Gerado a cada pedido e não guardado: o documento é derivado do banco e
    reflete o estado atual. Um PDF salvo na emissão seria uma segunda verdade
    que envelhece — e é a que alguém encontraria depois.
    """
    from django.http import HttpResponse as Resposta

    from workspace.services import pdf as pdf_service

    documento = get_object_or_404(
        Relatorio.objects.select_related("autor").prefetch_related("evidencias"), pk=pk
    )
    if not rel.pode_ver(documento, request.user, cache=_cache(request)):
        raise PermissionDenied("Este relatório não é seu.")

    resposta = Resposta(pdf_service.gerar(documento), content_type="application/pdf")
    # `inline` e não `attachment`: quem clica em "PDF" quer CONFERIR antes de
    # mandar para o cliente, e forçar download obriga a abrir o gerenciador de
    # arquivos para ver o que já poderia estar na tela. O nome do arquivo vai
    # junto, então "salvar como" continua saindo certo.
    resposta["Content-Disposition"] = (
        f'inline; filename="{pdf_service.nome_do_arquivo(documento)}"'
    )
    return resposta
