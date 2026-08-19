"""Busca universal — objeto, ação e conhecimento no mesmo campo.

## Duas fontes, de propósito

1. **O índice** (`EntradaIndice`) — serviço, documento, comunicado, notícia.
   Conteúdo com público-alvo no banco, recortado no `WHERE`.
2. **O launcher** — os aplicativos. Vivem em memória, já filtrados por
   `apps_disponiveis(pessoa)`. Ver `services/indice.py` para o motivo de não
   estarem no índice.

Juntar é explícito e não há ranking global entre as duas: o resultado é agrupado
por origem, então "Financeiro" (aplicativo) e "Reembolso" (serviço) não competem
por posição — cada um aparece no seu grupo. Ranking global entre coisas de
naturezas diferentes é onde a relevância começa a parecer aleatória.

## O recorte acontece no banco

`EntradaIndice.objects.para_sujeitos(...)` é um `WHERE ... IN`, não um filtro em
Python. É a regra da Etapa 5 §5.10, e o motivo é concreto: filtrar depois de
recuperar faz a contagem vazar. "8 resultados" que viram 3 na tela conta ao
usuário que existem cinco coisas que ele não pode ver.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Q
from django.urls import reverse

from identidade.services.autorizacao import subjects_de
from workspace.launcher import apps_disponiveis
from workspace.models.busca import EntradaIndice, OrigemIndice
from workspace.services import intencao
from workspace.services.indice import normalizar  # noqa: F401 — reexportado

LIMITE_POR_GRUPO = 6
MIN_CARACTERES = 2

# Ordem dos grupos na tela: primeiro o que se RESOLVE, depois o que se LÊ,
# depois para onde se VAI. Quem busca "reembolso" quer pedir um, não ler a
# política sobre ele — e quem quer a política reconhece o grupo seguinte.
ORDEM_DOS_GRUPOS = (
    (OrigemIndice.SERVICO, "Serviços"),
    # O que é DA PESSOA vem logo depois do que ela pode pedir: quem digita
    # "reembolso março" procura o próprio pedido, não a política sobre ele.
    (OrigemIndice.SOLICITACAO, "Minhas solicitações"),
    (OrigemIndice.FAQ, "Perguntas frequentes"),
    (OrigemIndice.DOCUMENTO, "Documentação"),
    (OrigemIndice.CURSO, "Universidade"),
    (OrigemIndice.RECURSO, "Reservas"),
    (OrigemIndice.CORRESPONDENCIA, "Correspondências"),
    (OrigemIndice.COMUNICADO, "Comunicados"),
    (OrigemIndice.NOTICIA, "Notícias"),
)


@dataclass(frozen=True)
class Resultado:
    origem: str
    titulo: str
    subtitulo: str
    url: str
    icone: str
    disponivel: bool = True


def _casa(termo: str, *campos: str) -> bool:
    return any(termo in normalizar(campo) for campo in campos if campo)


def buscar(consulta: str, pessoa=None) -> dict[str, list[Resultado]]:
    """Resultados agrupados por origem. Consulta curta devolve vazio."""
    termo = normalizar(consulta)
    if len(termo) < MIN_CARACTERES:
        return {}

    grupos: dict[str, list[Resultado]] = {}

    # 0 · A AÇÃO, quando a frase pede uma.
    #
    # Primeiro grupo do dicionário, e é o único que aparece com UM item: quando
    # a pessoa escreveu "quero solicitar férias", oferecer seis opções é devolver
    # a ela o trabalho que ela acabou de delegar.
    acao = intencao.interpretar(consulta)
    if acao is not None:
        grupos["Ação"] = [
            Resultado(
                origem="acao",
                titulo=acao.rotulo,
                subtitulo=acao.item.descricao_curta,
                url=reverse("workspace:pedir", args=(acao.item.chave,)),
                icone=acao.item.icone or "spark",
            )
        ]

    # 1 · Aplicativos, do launcher em memória.
    apps = [
        Resultado(
            origem="app",
            titulo=spec.nome,
            subtitulo=spec.descricao,
            url=_url_do_app(spec),
            icone=spec.icone,
            disponivel=spec.disponivel,
        )
        for spec in apps_disponiveis(pessoa)
        if _casa(termo, spec.nome, spec.descricao, spec.chave)
    ]

    # 2 · Conteúdo, do índice, recortado no WHERE.
    #
    # UMA consulta para todos os grupos, e o agrupamento em Python sobre o
    # resultado já recortado: uma consulta por grupo multiplicaria por quatro o
    # custo do `JOIN` de sujeitos a cada tecla digitada.
    #
    # E a busca é por PALAVRA, não pela frase inteira. `texto__contains="quero solicitar
    # ferias"` não achava a política de férias, porque nenhum documento contém
    # essa frase — a busca em linguagem natural devolvia a ação certa e zero
    # conhecimento.
    #
    # Palavras combinadas com E: quem digita "politica de viagem" quer o
    # documento que fala das duas coisas, não a união de tudo que fala de uma.
    palavras = intencao.termos_significativos(consulta) or [termo]
    encontradas = _no_indice(palavras, pessoa, juntar_com_e=True)

    # E com queda para OU.
    #
    # E é o certo para "politica de viagem": quem digita duas palavras quer o
    # documento que fala das duas. Mas frase conversacional sempre traz uma
    # palavra que não está em texto nenhum — "minha nr-35 está vencendo" tem
    # "vencendo", e o E devolvia zero enquanto a ação certa aparecia acima. Ficava
    # a impressão de que a busca não funciona, na mesma tela em que ela acertou.
    #
    # A segunda consulta só acontece quando a primeira falha, e nunca durante
    # digitação normal de uma ou duas palavras.
    if not encontradas and len(palavras) > 1:
        encontradas = _no_indice(palavras, pessoa, juntar_com_e=False)

    por_origem: dict[str, list[Resultado]] = {}
    for entrada in encontradas:
        por_origem.setdefault(entrada.origem, []).append(
            Resultado(
                origem=entrada.origem,
                titulo=entrada.titulo,
                subtitulo=entrada.subtitulo,
                url=entrada.url,
                icone=entrada.icone,
            )
        )

    for origem, rotulo in ORDEM_DOS_GRUPOS:
        achados = por_origem.get(origem.value)
        if achados:
            grupos[rotulo] = achados[:LIMITE_POR_GRUPO]

    # Aplicativos por último no dicionário: são navegação, e quem digita já sabe
    # para onde vai. O que ele não sabe é que existe um serviço que resolve.
    if apps:
        grupos["Aplicativos"] = apps[:LIMITE_POR_GRUPO]

    return grupos


def _no_indice(palavras, pessoa, *, juntar_com_e: bool):
    """Consulta o índice, com o recorte por sujeito no `WHERE`."""
    condicao = Q()
    for palavra in palavras:
        parte = Q(texto__contains=palavra)
        condicao = (condicao & parte) if juntar_com_e else (condicao | parte)

    return list(
        EntradaIndice.objects.para_sujeitos(subjects_de(pessoa))
        .filter(condicao)
        .order_by("origem", "titulo")[: LIMITE_POR_GRUPO * len(ORDEM_DOS_GRUPOS) * 2]
    )


def _url_do_app(spec) -> str:
    if spec.url_direta:
        return spec.url_direta
    if spec.url_name:
        # `args` porque a página de módulo é uma rota parametrizada pela chave.
        # Sem eles, buscar "RH" estourava NoReverseMatch e derrubava a busca
        # inteira — não só o resultado do módulo.
        return reverse(spec.url_name, args=spec.url_args)
    return ""
