"""Pessoas e papéis — a tela de quem aprova o quê.

Área de administração, e não de autoatendimento: exige identidade e a permissão
`rh.admin`. Ela responde três perguntas que antes só o `/admin/` respondia, e mal:

1. quem aprova cada área — e **qual área está sem ninguém**;
2. que papéis uma pessoa tem, com escopo e prazo;
3. em que **centro de custo** cada pessoa é debitada — e quais existem.

## Por que o centro de custo entrou aqui

`Lotacao.centro_custo_codigo` decide dinheiro em três lugares: o pedido do
catálogo o copia ao nascer, a bandeja monta a barra de orçamento com ele, e o
compromisso é baixado por ele. O campo era escrito pelo `semear` e por mais
nada. Quem entrasse na empresa depois da carga ficava sem centro de custo, o
primeiro pedido que exigisse um era recusado, e o R.H. — que é quem sabe a
resposta — não tinha onde digitá-la.

O cadastro dos centros em si mora no domínio financeiro, e continua morando: a
tela conversa pelo contrato de `workspace.services.orcamento`, sem importar
`financas`. Sem domínio financeiro instalado, a seção some em vez de quebrar.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from identidade.models import AtribuicaoPapel, ESCOPO_CHOICES, Papel
from identidade.services import administracao as adm
from identidade.services.administracao import AdministracaoError
from workspace.services import mapa_aprovacao as mapa
from workspace.services import orcamento as orc


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


def _garantir_acesso(request: HttpRequest) -> None:
    if not adm.pode_administrar(request.user, cache=_cache(request)):
        raise PermissionDenied("Esta tela é de quem administra papéis.")


@login_required
def pessoas(request: HttpRequest) -> HttpResponse:
    """A lista, com o mapa de aprovação por área em cima.

    O mapa vem primeiro de propósito: a pergunta que traz alguém a esta tela é
    quase sempre "por que o pedido de férias não chegou em ninguém?", e a
    resposta costuma ser uma área sem aprovador.
    """
    _garantir_acesso(request)

    lotacoes = list(adm.pessoas_administraveis())
    por_pessoa = []
    for lotacao in lotacoes:
        por_pessoa.append(
            {
                "lotacao": lotacao,
                "pessoa": lotacao.user,
                "atribuicoes": list(adm.atribuicoes_de(lotacao.user)),
            }
        )

    # Os centros vêm do domínio financeiro pelo contrato. Lista vazia quando
    # não há domínio registrado — e aí a tela esconde a seção em vez de
    # oferecer um cadastro que não grava em lugar nenhum.
    centros = orc.centros_de_custo()
    # Os códigos que aparecem em alguma lotação e NÃO existem no cadastro. É a
    # linha que explica "CC sem orçamento definido" na bandeja de aprovação,
    # e sem ela a divergência só aparece na hora de aprovar.
    conhecidos = {c.codigo for c in centros}
    orfaos = sorted(
        {
            lotacao.centro_custo_codigo
            for lotacao in lotacoes
            if lotacao.centro_custo_codigo
            and lotacao.centro_custo_codigo not in conhecidos
        }
    )

    return render(
        request,
        "workspace/pessoas.html",
        {
            "pessoas": por_pessoa,
            "mapa": mapa.resumo_de_aprovacao(),
            "papeis": adm.papeis_concedíveis(),
            "escopos": ESCOPO_CHOICES,
            "centros": centros,
            "centros_orfaos": orfaos,
        },
    )


@login_required
def definir_centro_custo(request: HttpRequest) -> HttpResponse:
    """Em que centro de custo esta pessoa é debitada. Sempre `POST`."""
    _garantir_acesso(request)
    if request.method != "POST":
        return redirect(reverse("workspace:pessoas"))

    from contas.models import Pessoa

    alvo = get_object_or_404(Pessoa, pk=request.POST.get("pessoa"))
    codigo = request.POST.get("centro_custo_codigo", "")
    try:
        adm.definir_centro_de_custo(alvo, codigo, request.user)
    except AdministracaoError as erro:
        messages.error(request, str(erro))
    else:
        messages.success(
            request,
            f"{alvo} passa a ser debitado em {codigo}." if codigo
            else f"{alvo} ficou sem centro de custo.",
        )

    return redirect(reverse("workspace:pessoas"))


@login_required
def salvar_centro_custo(request: HttpRequest) -> HttpResponse:
    """Cria ou atualiza um centro de custo. Sempre `POST`.

    O código é a IDENTIDADE e não um campo editável: ele está gravado na
    lotação de cada pessoa, em cada pedido já feito e em cada compromisso.
    Reenviar o mesmo código atualiza nome e orçamento; um código novo cria.
    """
    _garantir_acesso(request)
    if request.method != "POST":
        return redirect(reverse("workspace:pessoas"))

    bruto = (request.POST.get("orcamento_mensal") or "").strip().replace(",", ".")
    try:
        # Vazio continua sendo `None`, e não zero: a bandeja precisa dizer "CC
        # sem orçamento definido" em vez de mostrar 0%, que o aprovador leria
        # como "tem folga".
        orcamento = Decimal(bruto) if bruto else None
        if orcamento is not None and orcamento < 0:
            raise InvalidOperation
        salvo = orc.salvar_centro_de_custo(
            codigo=request.POST.get("codigo", ""),
            nome=request.POST.get("nome", ""),
            orcamento_mensal=orcamento,
            ativo=bool(request.POST.get("ativo")),
        )
    except InvalidOperation:
        messages.error(request, "Orçamento mensal inválido. Use um número, como 50000.")
    except orc.OrcamentoError as erro:
        messages.error(request, str(erro))
    else:
        if salvo is None:
            messages.error(
                request,
                "O cadastro financeiro não está disponível neste ambiente.",
            )
        else:
            messages.success(request, f"{salvo.codigo} · {salvo.nome} salvo.")

    return redirect(reverse("workspace:pessoas"))


@login_required
def conceder_papel(request: HttpRequest) -> HttpResponse:
    _garantir_acesso(request)
    if request.method != "POST":
        return redirect(reverse("workspace:pessoas"))

    from contas.models import Pessoa

    try:
        alvo = get_object_or_404(Pessoa, pk=request.POST.get("pessoa"))
        papel = get_object_or_404(Papel, pk=request.POST.get("papel"))
        adm.conceder(
            pessoa=alvo,
            papel=papel,
            escopo=request.POST.get("escopo", ""),
            quem=request.user,
            justificativa=request.POST.get("justificativa", ""),
            vigencia_fim=request.POST.get("vigencia_fim") or None,
        )
    except AdministracaoError as erro:
        messages.error(request, str(erro))
    else:
        messages.success(request, f"{papel} concedido a {alvo}.")

    return redirect(reverse("workspace:pessoas"))


@login_required
def revogar_papel(request: HttpRequest, pk: int) -> HttpResponse:
    _garantir_acesso(request)
    if request.method != "POST":
        return redirect(reverse("workspace:pessoas"))

    atribuicao = get_object_or_404(AtribuicaoPapel, pk=pk)
    try:
        adm.revogar(atribuicao, request.user, motivo=request.POST.get("motivo", ""))
    except AdministracaoError as erro:
        messages.error(request, str(erro))
    else:
        messages.success(
            request, f"{atribuicao.papel} encerrado para {atribuicao.user}."
        )

    return redirect(reverse("workspace:pessoas"))
