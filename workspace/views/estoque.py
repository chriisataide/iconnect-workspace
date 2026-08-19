"""EST — a tela do estoque, e a do que voltou de campo. §15.

O modelo e o serviço existiam desde a onda de Suprimentos; a tela, não. Na
prática isso significava que o razão só era alimentado pela conclusão de um
pedido — dava para GASTAR estoque pelo produto e não dava para repor, contar,
nem registrar o que voltou de uma unidade desativada, que é o §15 inteiro.

Uma tela, três públicos, e a divisão é por permissão:

    log.ler                 vê saldo, reversa e razão
    log.movimentar          registra entrada e entrada de reversa
    log.inventario.contar   registra a contagem física

`contar` é separado de `movimentar` por segregação de função: quem tira material
da prateleira não deveria ser quem declara quanto sobrou.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from identidade.models import Unidade
from workspace.models.estoque import CondicaoMaterial, Material, TipoMovimento
from workspace.services import estoque as est
from workspace.services.estoque import EstoqueError


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


def _unidade_escolhida(request: HttpRequest):
    """A unidade do filtro, ou a de quem está olhando.

    Padrão na unidade da pessoa e não em "todas": o saldo é por unidade, e a
    primeira pergunta de quem abre a tela é sobre a prateleira que ela alcança.
    O `?unidade=` continua permitindo ver as outras — quem controla patrimônio
    precisa da empresa inteira.
    """
    bruta = request.GET.get("unidade", "")
    if bruta == "todas":
        return None, "todas"
    if bruta.isdigit():
        unidade = Unidade.objects.filter(pk=int(bruta)).first()
        if unidade is not None:
            return unidade, str(unidade.pk)
    unidade = est.unidade_de(request.user)
    return unidade, str(unidade.pk) if unidade else "todas"


@login_required
def estoque(request: HttpRequest) -> HttpResponse:
    """Saldo, o que voltou de campo, e o razão do material escolhido."""
    cache = _cache(request)
    if not est.pode_ler(request.user, cache=cache):
        # 403 e não tela vazia: "o estoque está zerado" para quem não pode ver
        # estoque é mentira, e mentira que faz a pessoa procurar o material que
        # está lá.
        raise PermissionDenied("Você não tem acesso ao estoque.")

    unidade, filtro_unidade = _unidade_escolhida(request)
    saldos = list(est.disponivel_para(request.user, unidade=unidade))

    # O razão de UM material, quando a pessoa escolhe um. Sem escolha, nada — o
    # razão da empresa inteira é uma lista sem pergunta por trás.
    codigo = request.GET.get("material", "")
    material = Material.objects.filter(codigo=codigo).first() if codigo else None
    razao = est.razao_de(material, unidade=unidade, limite=50) if material else ()

    return render(
        request,
        "workspace/estoque.html",
        {
            "saldos": saldos,
            "em_falta": [linha for linha in saldos if linha.abaixo_do_minimo],
            "reversas": est.reversas(unidade=unidade, limite=30),
            "resumo_reversa": est.resumo_de_reversa(unidade=unidade),
            "material": material,
            "razao": razao,
            "materiais": Material.objects.filter(ativo=True).order_by("nome"),
            "unidades": Unidade.objects.order_by("nome"),
            "unidade": unidade,
            "filtro_unidade": filtro_unidade,
            "condicoes": CondicaoMaterial.choices,
            "movimenta": est.pode_movimentar(request.user, cache=cache),
            "conta": est.pode_contar(request.user, cache=cache),
        },
    )


def _de_volta(request: HttpRequest) -> HttpResponse:
    """Redireciona preservando o filtro de unidade.

    Sem isto, registrar uma reversa em Campinas jogava a pessoa de volta na
    unidade dela — e a linha que ela acabou de gravar não aparecia, o que se lê
    como "não salvou".
    """
    destino = reverse("workspace:estoque")
    unidade = request.POST.get("volta_unidade", "")
    return redirect(f"{destino}?unidade={unidade}" if unidade else destino)


def _material_do_post(request: HttpRequest) -> Material | None:
    return Material.objects.filter(codigo=request.POST.get("material", "")).first()


def _unidade_do_post(request: HttpRequest):
    bruta = request.POST.get("unidade", "")
    if bruta.isdigit():
        return Unidade.objects.filter(pk=int(bruta)).first()
    return est.unidade_de(request.user)


@login_required
def registrar_movimento(request: HttpRequest) -> HttpResponse:
    """Entrada, entrada de reversa ou contagem. Uma rota, porque é uma tela.

    O que decide é o `tipo` do formulário — três rotas para três verbos do mesmo
    razão multiplicariam a mesma checagem de permissão por três.
    """
    if request.method != "POST":
        return redirect(reverse("workspace:estoque"))

    cache = _cache(request)
    tipo = request.POST.get("tipo", "")
    material = _material_do_post(request)
    unidade = _unidade_do_post(request)

    if material is None:
        messages.error(request, "Escolha o material.")
        return _de_volta(request)
    if unidade is None:
        messages.error(request, "Escolha a unidade.")
        return _de_volta(request)

    # A permissão é conferida por TIPO, e não uma vez na entrada da view: contar
    # o inventário é permissão separada de movimentar, e uma checagem só faria a
    # segregação de função existir no papel e não no produto.
    exigida = est.pode_contar if tipo == TipoMovimento.AJUSTE else est.pode_movimentar
    if not exigida(request.user, cache=cache):
        raise PermissionDenied("Você não pode registrar este movimento.")

    try:
        quantidade = int(request.POST.get("quantidade", ""))
    except (TypeError, ValueError):
        messages.error(request, "A quantidade tem de ser um número.")
        return _de_volta(request)

    observacao = (request.POST.get("observacao") or "").strip()

    try:
        if tipo == TipoMovimento.REVERSA:
            movimento = est.entrada_de_reversa(
                material,
                unidade,
                quantidade,
                request.POST.get("condicao", ""),
                quem=request.user,
                unidade_origem=_unidade_de_origem(request),
                cliente=(request.POST.get("cliente") or "").strip()[:120],
                patrimonio=(request.POST.get("patrimonio") or "").strip()[:40],
                observacao=observacao[:300],
            )
        elif tipo in (TipoMovimento.ENTRADA, TipoMovimento.AJUSTE):
            movimento = est.movimentar(
                material,
                unidade,
                tipo,
                quantidade,
                quem=request.user,
                observacao=observacao[:300],
            )
        else:
            messages.error(request, "Tipo de movimento desconhecido.")
            return _de_volta(request)
    except EstoqueError as erro:
        messages.error(request, str(erro))
    else:
        messages.success(
            request,
            f"{movimento.get_tipo_display()} registrada — "
            f"{material.nome} agora tem {movimento.saldo_posterior} em {unidade.nome}.",
        )

    return _de_volta(request)


def _unidade_de_origem(request: HttpRequest):
    bruta = request.POST.get("unidade_origem", "")
    return Unidade.objects.filter(pk=int(bruta)).first() if bruta.isdigit() else None
