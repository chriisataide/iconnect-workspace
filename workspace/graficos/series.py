"""A `option` do ECharts, montada em Python.

## Por que aqui e não no JavaScript

**Os números vêm do servidor, sempre.** O JS deste produto lê um bloco de dados
e chama `setOption` — ele não soma, não converte e não formata. Se o gráfico
mostra um número diferente da tabela ao lado, há um lugar só para procurar.

E a tabela irmã sai do MESMO objeto: `Bloco` carrega a option e as linhas da
tabela, montadas juntas, com os mesmos textos formatados.

## A tabela irmã é FALLBACK, e não enfeite

No desenho anterior — SVG calculado em Python — a tabela era acessibilidade: o
gráfico existia sem JavaScript. Aqui não existe: sem JS, o `<div>` do gráfico
fica vazio.

Por isso todo bloco carrega `<table>` com os mesmos números, e por isso ela abre
por padrão quando não há JS. O benchmark faz isso naturalmente — em quase toda
tela o gráfico convive com a grade, e é na grade que a pessoa confere.

## Cor nunca sozinha

O benchmark depende de verde/amarelo/vermelho em quase tudo. Aqui toda
codificação por cor vem com rótulo: o valor fica **dentro ou em cima** do
elemento, e a série tem nome na legenda. Cor é reforço, e não o dado.

## O que este módulo NÃO faz

Não consulta banco, não conhece contrato nem competência, e não decide o que é
receita. Ele recebe pontos e devolve um objeto que o ECharts entende — a
semântica fica em `workspace/services/resultados.py`, onde alguém a encontra.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from workspace.graficos import formato as fmt

#: Altura padrão do gráfico, em pixels. Casada com o CSS `.au-gr-tela`.
ALTURA = 260

#: As cores saem dos tokens do produto, e não da paleta do ECharts.
#:
#: Valores literais e não `var(--au-…)`: o ECharts desenha em SVG mas escreve a
#: cor como atributo de preenchimento, e `var()` num atributo de SVG não resolve.
#: A duplicação é conferida por `test_toda_cor_do_grafico_existe_nos_tokens`.
COR_PRINCIPAL = "#3539a9"   # --au-accent-600
COR_SECUNDARIA = "#a0a2e1"  # --au-accent-300
COR_LINHA = "#d97706"       # --au-warning
COR_NEGATIVO = "#dc2626"    # --au-danger
COR_POSITIVO = "#059669"    # --au-success
COR_TEXTO = "#475569"       # --au-brand-600, que é --au-text-muted no claro
COR_GRADE = "#c7c8ed"       # --au-accent-200


@dataclass
class Coluna:
    """Uma coluna da tabela irmã."""

    titulo: str
    numerica: bool = True


@dataclass
class Bloco:
    """Um gráfico e a tabela que diz o mesmo.

    Os dois saem juntos de propósito: montar a tabela noutro lugar é como ela
    acaba mostrando outro número.
    """

    chave: str
    titulo: str
    option: dict
    colunas: list[Coluna] = field(default_factory=list)
    linhas: list[list[str]] = field(default_factory=list)
    #: O resumo em texto, para `aria-label`. `aria.enabled` do ECharts descreve a
    #: estrutura; isto descreve o ASSUNTO, que é o que interessa a quem não vê.
    resumo: str = ""
    altura: int = ALTURA

    @property
    def vazio(self) -> bool:
        return not self.linhas


def _eixo_de_valor(rotulos_curtos: bool = True) -> dict:
    return {
        "type": "value",
        "axisLabel": {
            "color": COR_TEXTO,
            # `{@…}` não vale em eixo — ele não tem dado por trás. O eixo usa o
            # formatador nativo do ECharts, que é en-US; então o Python define
            # os TICKS e o texto deles vira categoria. Ver `_eixo_com_ticks`.
            "fontSize": 11,
        },
        "splitLine": {"lineStyle": {"color": COR_GRADE, "type": "dashed"}},
        "axisLine": {"show": False},
        "axisTick": {"show": False},
    }


def _base(altura: int = ALTURA) -> dict:
    """O esqueleto comum: grade apertada, sem título dentro do gráfico.

    O título fica em HTML, fora do `<svg>`: dentro, ele não é lido por leitor de
    tela na ordem certa e não é selecionável.
    """
    return {
        # Acessibilidade nativa do ECharts. Ela descreve a estrutura do gráfico;
        # não substitui a tabela irmã, e o prompt é explícito nisso.
        "aria": {"enabled": True},
        "animation": False,
        "grid": {"left": 8, "right": 8, "top": 28, "bottom": 8, "containLabel": True},
        "textStyle": {
            "fontFamily": "inherit",
            "color": COR_TEXTO,
        },
        "tooltip": {
            "trigger": "axis",
            "axisPointer": {"type": "shadow"},
            "confine": True,
        },
    }


def serie_temporal(
    pontos: list[tuple[str, Decimal | None]],
    *,
    chave: str,
    titulo: str,
    rotulo_serie: str = "",
    formatar=fmt.moeda_curta,
    formatar_tabela=fmt.moeda,
    tipo: str = "bar",
    altura: int = ALTURA,
) -> Bloco:
    """Barras (ou linha) de N meses, com **o valor em cima de cada ponto**.

    `pontos` é `[(rótulo, valor), …]`. Valor `None` é um mês SEM DADO, e não um
    mês de zero: ele entra no eixo, fica sem barra, e a tabela escreve "—".

    O rótulo por ponto é o que você pediu ao ver o gráfico sem números. Ele vem
    formatado do Python, como uma dimensão a mais do `dataset` — e o
    `formatter` é a string `{@rotulo}`, sem uma linha de JS.
    """
    if not pontos:
        return Bloco(chave=chave, titulo=titulo, option={}, altura=altura)

    # `dataset.source` com `dimensions` nomeadas. A terceira dimensão é o TEXTO
    # já formatado — é ela que `{@rotulo}` resolve.
    fonte = [
        [mes, (float(valor) if valor is not None else None), formatar(valor)]
        for mes, valor in pontos
    ]
    negativos = any(v is not None and v < 0 for _, v in pontos)

    option = _base(altura)
    option.update(
        {
            "dataset": {
                "dimensions": ["mes", "valor", "rotulo"],
                "source": fonte,
            },
            "xAxis": {
                "type": "category",
                "axisLabel": {"color": COR_TEXTO, "fontSize": 11},
                "axisTick": {"show": False},
                "axisLine": {"lineStyle": {"color": COR_GRADE}},
            },
            "yAxis": _eixo_de_valor(),
            "series": [
                {
                    "type": tipo,
                    "name": rotulo_serie or titulo,
                    "encode": {"x": "mes", "y": "valor"},
                    "itemStyle": {"color": COR_PRINCIPAL},
                    "barMaxWidth": 34,
                    "smooth": False,
                    "label": {
                        "show": True,
                        # A dimensão nomeada, resolvida contra o dado bruto.
                        # Conferido no fonte da 6.1.0, `dataFormat.js`.
                        "formatter": "{@rotulo}",
                        # Negativo embaixo da barra; positivo em cima. Com
                        # `top` fixo, o rótulo do negativo cai dentro do eixo.
                        "position": "top",
                        "fontSize": 10,
                        "color": COR_TEXTO,
                    },
                    "tooltip": {"valueFormatter": None},
                }
            ],
        }
    )
    if negativos:
        # Com valor negativo o rótulo `top` sobrepõe o eixo. `insideBottom` põe
        # o texto dentro da barra que desce, que é onde há espaço.
        option["series"][0]["label"]["position"] = "inside"
        option["series"][0]["label"]["color"] = "#ffffff"

    return Bloco(
        chave=chave,
        titulo=titulo,
        option=option,
        colunas=[Coluna("Mês", numerica=False), Coluna(rotulo_serie or "Valor")],
        linhas=[[mes, formatar_tabela(valor)] for mes, valor in pontos],
        resumo=_resumo(titulo, pontos, formatar_tabela),
        altura=altura,
    )


def barras_comparadas(
    pontos: list[tuple[str, Decimal | None, Decimal | None]],
    *,
    chave: str,
    titulo: str,
    rotulo_a: str,
    rotulo_b: str,
    rotulo_linha: str = "",
    linha: list[Decimal | None] | None = None,
    formatar=fmt.moeda_curta,
    formatar_tabela=fmt.moeda,
    formatar_linha=fmt.percentual,
    altura: int = ALTURA,
) -> Bloco:
    """Duas séries de barra e uma linha em eixo próprio — a 1.1.02 do benchmark.

    É o tipo que responde "como as duas coisas andaram juntas, e o que a razão
    entre elas fez". A linha vai em `yAxisIndex: 1` porque ela quase sempre é
    percentual, e um percentual no eixo de reais some.

    **Valores negativos com o zero no meio do eixo:** o ECharts faz isso sozinho
    quando o mínimo é negativo, desde que o eixo não tenha `min` fixado. Não
    fixamos — e há teste afirmando que o zero não é a base.
    """
    if not pontos:
        return Bloco(chave=chave, titulo=titulo, option={}, altura=altura)

    linha = linha or [None] * len(pontos)
    fonte = [
        [
            mes,
            float(a) if a is not None else None,
            float(b) if b is not None else None,
            float(c) if c is not None else None,
            formatar(a),
            formatar(b),
            formatar_linha(c),
        ]
        for (mes, a, b), c in zip(pontos, linha)
    ]

    option = _base(altura)
    option.update(
        {
            "dataset": {
                "dimensions": [
                    "mes", "a", "b", "linha", "rotulo_a", "rotulo_b", "rotulo_linha",
                ],
                "source": fonte,
            },
            # A legenda é o que faz a cor não estar sozinha: cada série tem nome
            # escrito, e não só um quadradinho colorido.
            "legend": {
                "bottom": 0,
                "icon": "roundRect",
                "itemHeight": 8,
                "textStyle": {"color": COR_TEXTO, "fontSize": 11},
            },
            "grid": {"left": 8, "right": 8, "top": 28, "bottom": 30, "containLabel": True},
            "xAxis": {
                "type": "category",
                "axisLabel": {"color": COR_TEXTO, "fontSize": 11},
                "axisTick": {"show": False},
                "axisLine": {"lineStyle": {"color": COR_GRADE}},
            },
            "yAxis": [
                _eixo_de_valor(),
                {
                    **_eixo_de_valor(),
                    "splitLine": {"show": False},
                    "position": "right",
                },
            ],
            "series": [
                {
                    "type": "bar",
                    "name": rotulo_a,
                    "encode": {"x": "mes", "y": "a"},
                    "itemStyle": {"color": COR_PRINCIPAL},
                    "barMaxWidth": 22,
                    "label": {
                        "show": True, "formatter": "{@rotulo_a}",
                        "position": "top", "fontSize": 9, "color": COR_TEXTO,
                    },
                },
                {
                    "type": "bar",
                    "name": rotulo_b,
                    "encode": {"x": "mes", "y": "b"},
                    "itemStyle": {"color": COR_SECUNDARIA},
                    "barMaxWidth": 22,
                    "label": {
                        "show": True, "formatter": "{@rotulo_b}",
                        "position": "top", "fontSize": 9, "color": COR_TEXTO,
                    },
                },
            ],
        }
    )

    if any(v is not None for v in linha):
        option["series"].append(
            {
                "type": "line",
                "name": rotulo_linha or "Razão",
                "yAxisIndex": 1,
                "encode": {"x": "mes", "y": "linha"},
                "itemStyle": {"color": COR_LINHA},
                "lineStyle": {"color": COR_LINHA, "width": 2},
                "symbolSize": 6,
                "label": {
                    "show": True, "formatter": "{@rotulo_linha}",
                    "position": "top", "fontSize": 9, "color": COR_LINHA,
                },
            }
        )

    colunas = [Coluna("Mês", numerica=False), Coluna(rotulo_a), Coluna(rotulo_b)]
    if any(v is not None for v in linha):
        colunas.append(Coluna(rotulo_linha or "Razão"))

    linhas = []
    for (mes, a, b), c in zip(pontos, linha):
        celulas = [mes, formatar_tabela(a), formatar_tabela(b)]
        if any(v is not None for v in linha):
            celulas.append(formatar_linha(c))
        linhas.append(celulas)

    return Bloco(
        chave=chave,
        titulo=titulo,
        option=option,
        colunas=colunas,
        linhas=linhas,
        resumo=(
            f"{titulo}: {rotulo_a} e {rotulo_b} em {len(pontos)} meses. "
            "Os números estão na tabela abaixo."
        ),
        altura=altura,
    )


def _resumo(titulo: str, pontos, formatar) -> str:
    """O `aria-label` do contêiner: assunto, extremos e período.

    Não é a leitura ponto a ponto — isso é papel da tabela. É o que uma pessoa
    diria em voz alta ao olhar o gráfico de longe.
    """
    validos = [(m, v) for m, v in pontos if v is not None]
    if not validos:
        return f"{titulo}: sem dado no período."
    maior = max(validos, key=lambda p: p[1])
    menor = min(validos, key=lambda p: p[1])
    return (
        f"{titulo}, {len(pontos)} meses de {pontos[0][0]} a {pontos[-1][0]}. "
        f"Maior em {maior[0]}, {formatar(maior[1])}. "
        f"Menor em {menor[0]}, {formatar(menor[1])}. "
        "Os números estão na tabela abaixo."
    )
