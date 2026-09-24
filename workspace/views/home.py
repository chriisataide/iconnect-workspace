"""Home do Workspace — aberta, e agora contextual. §50 e §51.

A home era a única tela do produto **sem o trilho**, e o trilho é onde moram
todos os contadores que o Workspace já sabia calcular sobre a pessoa. O
resultado: a tela em que ela cai ao entrar era a que menos sabia sobre ela — um
card condicional (aprovações) e o resto igual para o estagiário e para o diretor.

Os cards vêm de `services/painel`, que também alimenta o trilho. Os números são
calculados UMA vez por requisição: a view pede primeiro, o processador de
contexto reaproveita. Sem isso, dar contexto à home custaria oito consultas a
mais na tela mais visitada do produto.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import formats, timezone

from workspace.acesso import pessoa_da_requisicao
from workspace.launcher import AppSpec, apps_disponiveis
from workspace.models import Publicacao, TipoPublicacao
from workspace.models.catalogo import ItemCatalogo
from workspace.services import painel

#: Quantos cabem em cada card da home. O resto fica no "Ver todos", que
#: mostra quantos sobraram — sem o número, ninguém sabe que há mais para ler.
LIMITE_COMUNICADOS = 4
LIMITE_NOTICIAS = 3


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
    pessoa = pessoa_da_requisicao(request)

    # `para(request.user)` e não `publicadas()`: o público-alvo do §9 só vale
    # se a home o respeitar. `request.user` e não `pessoa` — a pessoa de
    # referência do hub aberto serve para calcular ALCANCE de serviço, e usá-la
    # aqui mostraria ao visitante anônimo o comunicado dirigido ao departamento
    # dela. Anônimo cai no ramo sem lotação e recebe só o que é geral.
    publicadas = Publicacao.objects.para(request.user)

    # O total do catálogo é a promessa concreta do card "Pedir um serviço" —
    # "19 serviços" convence a clicar; "peça o que precisa" não. Sem filtro por
    # permissão de propósito: é a home pública, e aqui o número é informação,
    # não lista de ações.
    total_servicos = ItemCatalogo.objects.filter(ativo=True).count()

    # `contadores()` ANTES do render, e é o que torna os cards de graça: o
    # processador de contexto vai pedir os mesmos números para montar o trilho e
    # encontrar o resultado memoizado na requisição.
    contagens = painel.contadores(request)

    comunicados = publicadas.do_tipo(TipoPublicacao.COMUNICADO)
    noticias = publicadas.do_tipo(TipoPublicacao.NOTICIA)

    return render(
        request,
        "workspace/home.html",
        {
            # Estava fixo em `False` e `""`, então a home dizia "Bem-vindo ao
            # Workspace" para todo mundo — inclusive para quem tinha acabado de
            # entrar. A saudação por nome existia no template e nunca acontecia.
            "autenticado": request.user.is_authenticated,
            "nome": (
                request.user.get_short_name()
                if request.user.is_authenticated
                else ""
            ),
            "hoje": _hoje(),
            "apps": [_para_tela(spec) for spec in apps_disponiveis(pessoa)],
            "total_servicos": total_servicos,
            # §50 — os cards desta pessoa, do mais caro de ignorar ao mais
            # barato. Função pura sobre `contagens`: sete cards custam as mesmas
            # consultas que os três fixos de antes.
            "cards": painel.cards(contagens, total_servicos),
            "comunicados": comunicados[:LIMITE_COMUNICADOS],
            "noticias": noticias[:LIMITE_NOTICIAS],
            "mais_comunicados": max(comunicados.count() - LIMITE_COMUNICADOS, 0),
            "mais_noticias": max(noticias.count() - LIMITE_NOTICIAS, 0),
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
