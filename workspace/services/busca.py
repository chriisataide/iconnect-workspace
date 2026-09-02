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
from workspace import enderecamento as end
from workspace.launcher import apps_disponiveis
from workspace.models.busca import EntradaIndice, OrigemIndice
from workspace.services import intencao
from workspace.services.indice import normalizar  # noqa: F401 — reexportado

LIMITE_POR_GRUPO = 6
MIN_CARACTERES = 2

# ── Os prefixos ─────────────────────────────────────────────────────
#
# Declarados aqui e ANUNCIADOS no campo (`_shell.html`). Prefixo que existe e
# ninguém sabe é atalho de quem escreveu o código: o benchmark do Portal GPS põe
# "Digite P: para pessoas ou D: para documentos" dentro do próprio placeholder,
# e é a razão de as pessoas de lá usarem.
#
# `p:` NÃO está aqui: pessoa não vive no índice, e o porquê está em `_pessoas()`.
PREFIXOS: dict[str, tuple[str, ...]] = {
    "s": (OrigemIndice.SERVICO.value,),
    "d": (OrigemIndice.DOCUMENTO.value,),
}

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


@dataclass(frozen=True)
class Recorte:
    """O que a pessoa digitou, depois de tirado o prefixo.

    `origens=None` quer dizer "sem recorte" — a busca larga de sempre. Uma
    tupla vazia nunca acontece: prefixo que não recorta nada não é prefixo.
    """

    texto: str
    origens: tuple[str, ...] | None = None
    pessoas: bool = False

    @property
    def restrita(self) -> bool:
        return self.pessoas or self.origens is not None


def _casa(termo: str, *campos: str) -> bool:
    return any(termo in normalizar(campo) for campo in campos if campo)


def _recorte(consulta: str, pessoa) -> Recorte:
    """Lê o prefixo, se houver, e devolve o resto.

    Prefixo desconhecido NÃO vira erro nem grupo vazio: `x: nota fiscal` é
    tratado como texto comum, que é o que ele parece para quem digitou. Falhar
    aqui ensinaria a evitar os dois-pontos.
    """
    bruta = (consulta or "").strip()

    # `#123` — o número do pedido. Sem espaço depois do `#`, porque é assim que
    # as pessoas escrevem número de chamado em qualquer sistema.
    if bruta.startswith("#") and bruta[1:].strip().isdigit():
        return Recorte(texto=bruta, origens=(OrigemIndice.SOLICITACAO.value,))

    inicial, sep, resto = bruta.partition(":")
    if not sep:
        return Recorte(texto=bruta)

    chave = inicial.strip().casefold()
    resto = resto.strip()
    if not resto:
        # `s:` sozinho ainda não é uma busca. Devolver o bruto deixa o
        # `MIN_CARACTERES` recusar, como qualquer consulta curta.
        return Recorte(texto=bruta)

    if chave in PREFIXOS:
        return Recorte(texto=resto, origens=PREFIXOS[chave])
    if chave == "p" and _pode_ver_pessoas(pessoa):
        return Recorte(texto=resto, pessoas=True)
    return Recorte(texto=bruta)


def _pode_ver_pessoas(pessoa) -> bool:
    """Quem já enxerga o organograma na tela de Pessoas e papéis.

    O prefixo `p:` não amplia alcance nenhum: ele é um atalho para a lista que
    a pessoa já pode abrir. Para quem não administra papéis, `p:` não existe —
    `p: joão` cai na busca comum, sem grupo vazio e sem aviso, porque avisar
    contaria que existe um diretório do outro lado da porta.
    """
    if pessoa is None or not getattr(pessoa, "is_authenticated", False):
        return False
    from identidade.services import administracao as adm

    return adm.pode_administrar(pessoa)


def buscar(consulta: str, pessoa=None) -> dict[str, list[Resultado]]:
    """Resultados agrupados por origem. Consulta curta devolve vazio."""
    # 0 · O CÓDIGO DA TELA, antes de tudo.
    #
    # Um resultado só, e a busca para aqui: quem digitou "02.2" não está
    # procurando, está indo. Oferecer mais seis linhas junto seria devolver a
    # decisão que a pessoa acabou de tomar.
    #
    # E é um RESULTADO, não um redirecionamento: navegar sozinho a cada tecla
    # levaria embora quem está no meio de digitar "02.1" e passou por "02".
    tela = end.por_codigo(consulta)
    if tela is not None and tela.url:
        return {
            "Ir para": [
                Resultado(
                    origem="tela",
                    titulo=tela.nome,
                    subtitulo=tela.codigo,
                    url=tela.url,
                    icone="seta",
                )
            ]
        }

    recorte = _recorte(consulta, pessoa)
    termo = normalizar(recorte.texto)
    if len(termo) < MIN_CARACTERES:
        return {}

    if recorte.pessoas:
        return _pessoas(termo)

    grupos: dict[str, list[Resultado]] = {}

    # 0 · A AÇÃO, quando a frase pede uma.
    #
    # Primeiro grupo do dicionário, e é o único que aparece com UM item: quando
    # a pessoa escreveu "quero solicitar férias", oferecer seis opções é devolver
    # a ela o trabalho que ela acabou de delegar.
    acao = None if recorte.restrita else intencao.interpretar(consulta)
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
    apps = [] if recorte.restrita else [
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
    palavras = intencao.termos_significativos(recorte.texto) or [termo]
    encontradas = _no_indice(palavras, pessoa, juntar_com_e=True, origens=recorte.origens)

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
        encontradas = _no_indice(
            palavras, pessoa, juntar_com_e=False, origens=recorte.origens
        )

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


def _no_indice(palavras, pessoa, *, juntar_com_e: bool, origens=None):
    """Consulta o índice, com o recorte por sujeito no `WHERE`.

    O prefixo também vira `WHERE`, e não filtro depois: com `s:`, buscar
    "reembolso" tem de custar as linhas de serviço, não o acervo inteiro para
    jogar fora — e o limite da consulta se aplicaria às linhas erradas, deixando
    de fora serviços que deveriam aparecer.
    """
    condicao = Q()
    for palavra in palavras:
        parte = Q(texto__contains=palavra)
        condicao = (condicao & parte) if juntar_com_e else (condicao | parte)

    consulta = EntradaIndice.objects.para_sujeitos(subjects_de(pessoa)).filter(condicao)
    if origens is not None:
        consulta = consulta.filter(origem__in=origens)

    return list(
        consulta.order_by("origem", "titulo")[
            : LIMITE_POR_GRUPO * len(ORDEM_DOS_GRUPOS) * 2
        ]
    )


def _pessoas(termo: str) -> dict[str, list[Resultado]]:
    """O prefixo `p:` — quem, e não o quê.

    Fora do índice de propósito. O índice existe para conteúdo com público-alvo
    gravado, e pessoa não tem público-alvo: quem pode ver a lista de gente é
    quem administra papéis, e isso já foi decidido em `_pode_ver_pessoas()`,
    antes de chegar aqui.

    O que aparece é NOME, CARGO e ÁREA — o que a tela de Pessoas e papéis já
    mostra. E-mail e centro de custo ficam de fora: o benchmark tem grade de CPF
    e e-mail com botão de exportar, e é a primeira coisa que a leitura marcou
    como não copiar.

    O casamento é em Python sobre uma consulta só. Com o organograma da ADB — na
    casa das centenas de lotações — isso é mais barato do que um `LIKE` por
    campo, e para em `LIMITE_POR_GRUPO`. No dia em que o diretório crescer uma
    ordem de grandeza, isto vira `Q(user__nome__icontains=...)`; até lá, índice
    para uma tabela deste tamanho é otimização sem medida.
    """
    from identidade.services import administracao as adm

    achados = []
    for lotacao in adm.pessoas_administraveis():
        nome = lotacao.user.get_full_name() or lotacao.user.get_short_name()
        area = lotacao.departamento.nome if lotacao.departamento else ""
        if not _casa(termo, nome, lotacao.cargo, area):
            continue
        achados.append(
            Resultado(
                origem="pessoa",
                titulo=nome,
                subtitulo=" · ".join(p for p in (lotacao.cargo, area) if p),
                # Âncora na linha da pessoa: cair no topo de uma lista de
                # duzentos nomes é o mesmo que não ter encontrado.
                url=f"{reverse('workspace:pessoas')}#cc-{lotacao.user_id}",
                icone="users",
            )
        )
        if len(achados) >= LIMITE_POR_GRUPO:
            break

    return {"Pessoas": achados} if achados else {}


def _url_do_app(spec) -> str:
    if spec.url_direta:
        return spec.url_direta
    if spec.url_name:
        # `args` porque a página de módulo é uma rota parametrizada pela chave.
        # Sem eles, buscar "RH" estourava NoReverseMatch e derrubava a busca
        # inteira — não só o resultado do módulo.
        return reverse(spec.url_name, args=spec.url_args)
    return ""
