"""Home do Workspace — pública.

O Workspace é a porta de entrada da empresa e **não exige login**: quem chega vê
o hub e escolhe o sistema. O tile do iConnect é o único caminho para o login do
sistema principal — antes havia três (topbar, tile, faixa), o que faz o usuário
hesitar sobre se levam ao mesmo lugar.

A personalização do briefing original (saudação, pendências, aprovações) exige
identidade, o que colide com "sem login". Resolvido de forma progressiva: a
página funciona anônima e, havendo sessão, cumprimenta pelo nome. Nada aqui
redireciona para autenticação.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import formats, timezone

from workspace.launcher import AppSpec, apps_disponiveis
from workspace.models import Publicacao, TipoPublicacao
from workspace.models.catalogo import ItemCatalogo

LIMITE_CARD = 4


@dataclass(frozen=True)
class AppNaTela:
    """`AppSpec` com a URL já resolvida.

    Resolver `url_name` no template exigiria `{% url %}` dentro de `{% if %}`
    aninhado, que quebra silenciosamente quando a rota não existe. Resolver
    aqui deixa o template burro, que é onde ele deve estar.
    """

    chave: str
    nome: str
    descricao: str
    icone: str
    cor: str
    cor_bg: str
    disponivel: bool
    destaque: bool
    destino: str


def home(request: HttpRequest) -> HttpResponse:
    autenticado = request.user.is_authenticated
    pessoa = request.user if autenticado else None

    publicadas = Publicacao.objects.publicadas()

    return render(
        request,
        "workspace/home.html",
        {
            "autenticado": autenticado,
            "nome": _primeiro_nome(request) if autenticado else "",
            "hoje": _hoje(),
            "apps": [_para_tela(spec) for spec in apps_disponiveis(pessoa)],
            # O total do catálogo é a promessa concreta do card "Pedir um
            # serviço" — "19 serviços" convence a clicar; "peça o que precisa"
            # não. Sem filtro por permissão de propósito: é a home pública, e
            # aqui o número é informação, não lista de ações.
            "total_servicos": ItemCatalogo.objects.filter(ativo=True).count(),
            "comunicados": publicadas.do_tipo(TipoPublicacao.COMUNICADO)[:LIMITE_CARD],
            "noticias": publicadas.do_tipo(TipoPublicacao.NOTICIA)[:LIMITE_CARD],
        },
    )


def _para_tela(spec: AppSpec) -> AppNaTela:
    return AppNaTela(
        chave=spec.chave,
        nome=spec.nome,
        descricao=spec.descricao,
        icone=spec.icone,
        cor=spec.cor,
        cor_bg=spec.cor_bg,
        disponivel=spec.disponivel,
        destaque=spec.destaque,
        destino=spec.url_direta
        or (reverse(spec.url_name, args=spec.url_args) if spec.url_name else ""),
    )


def _primeiro_nome(request: HttpRequest) -> str:
    """Só o primeiro nome — 'Olá Christopher', não 'Olá Christopher Ataide'."""
    completo = (request.user.get_full_name() or request.user.get_username()).strip()
    return completo.split()[0] if completo else ""


def _hoje() -> str:
    """'Sexta-feira, 7 de agosto' — locale do Django, não strftime.

    Duas correções sobre o padrão: o `text-transform: capitalize` do CSS
    maiusculiza *toda* palavra ("Sexta-Feira, 7 De Agosto"), e o locale pt-BR
    do Django devolve o mês capitalizado ("Agosto"). Em português só a
    primeira letra da frase leva maiúscula.
    """
    agora = timezone.localtime()
    texto = f"{formats.date_format(agora, 'l')}, {formats.date_format(agora, 'j \\d\\e F')}".lower()
    return texto[:1].upper() + texto[1:]
