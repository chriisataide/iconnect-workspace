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

## O rótulo é GIRADO, e é assim que treze meses cabem

Com o texto na horizontal, `R$ 1,19 Mi` mede mais que a largura de uma barra de
treze — e os rótulos se sobrepõem até virarem uma mancha. Foi o que aconteceu na
primeira versão desta onda, e o que o Portal GPS resolve girando o texto em 90°
e pondo-o **dentro** da barra.

Girado, o rótulo ocupa a ALTURA, que sobra, em vez da largura, que falta. É a
razão de `label.rotate: 90` estar em todo tipo daqui — e de a fonte ser 10px:
o rótulo é conferência, não manchete.

Barra baixa demais para caber o texto dentro fica sem rótulo, e não com o texto
transbordando: `labelLayout.hideOverlap` deixa o ECharts esconder o que não cabe.
O número continua na tabela irmã, que é onde se confere.

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
ALTURA = 300

#: Espaço reservado ACIMA da área de desenho quando o rótulo fica em cima da
#: barra e é girado.
#:
#: Girado, `R$ 262 Mil` mede cerca de sessenta pixels de altura — e com o padrão
#: de 28 ele era **cortado pela borda do gráfico**. Apareceu na tela: o rótulo da
#: barra mais alta do EBITDA saía pela metade.
#:
#: Setenta e quatro, e não "o suficiente": abaixo disso o corte volta na
#: primeira série que tiver um valor de sete dígitos. Era 68 enquanto o rótulo
#: era 10px em peso normal; girado, um número em negrito de 11px mede cerca de
#: 10% a mais, e a folga acompanha — senão a mudança que tornou o número legível
#: seria a mesma que o cortaria.
FOLGA_DO_ROTULO = 74

#: As cores saem dos tokens do produto, e não da paleta do ECharts.
#:
#: Valores literais e não `var(--au-…)`: o ECharts desenha em SVG mas escreve a
#: cor como atributo de preenchimento, e `var()` num atributo de SVG não resolve.
#: A duplicação é conferida por `test_toda_cor_do_grafico_existe_nos_tokens`.
#: REALIZADO × ORÇADO — o par que se repete em toda a tela.
#:
#: Era `#3539a9` contra `#a0a2e1`: o mesmo azul em duas claridades, e a queixa
#: da revisão ("a paleta é lavada") estava certa — dois tons do mesmo matiz não
#: se separam de relance.
#:
#: A revisão pedia "azul-aço contra âmbar". Medido, esse par dá **1,33:1** de
#: contraste entre as séries: em escala de cinza as duas barras viram uma só, e
#: "cor nunca sozinha" cai junto. O par abaixo tem o matiz que se pediu E
#: **5,26:1** de luminância — melhor que os 3,79:1 de antes.
#:
#: Os valores moram em `--au-chart-*` no `tokens.css`, com a medição escrita lá.
COR_PRINCIPAL = "#2b2e8a"   # --au-chart-re
COR_SECUNDARIA = "#f59e0b"  # --au-chart-or
#: A terceira de uma série categórica. Ardósia neutra, e não um terceiro azul:
#: `#7376d3` foi a primeira escolha e a guarda de contraste a reprovou — branco
#: sobre ela dá 3,99:1, abaixo do piso de 4,0 para rótulo dentro da barra.
#: Esta dá 4,76:1, e ainda separa de RE (2,37:1) e de OR (2,22:1).
COR_TERCIARIA = "#64748b"   # --au-chart-terceira

#: A LINHA DA RAZÃO. Neutra escura, e não âmbar.
#:
#: Âmbar era `--au-warning`, e passou a ser a cor do ORÇADO — a linha ficaria
#: igual a uma das barras. E ela nunca foi um aviso: é a razão entre as duas
#: séries, que pode ser boa ou ruim.
COR_LINHA = "#0f172a"       # --au-chart-linha

#: A faixa "atenção" do medidor. SEPARADA de `COR_LINHA`, que era quem fazia
#: este papel — no medidor a cor é semântica, e ali âmbar quer dizer atenção
#: mesmo. Um símbolo servindo aos dois papéis fez a linha da razão parecer um
#: alerta durante toda a vida anterior deste arquivo.
COR_ATENCAO = "#d97706"     # --au-warning

#: A série do PERÍODO COMPARADO — F1. O mesmo azul do realizado, mais claro:
#: ela é a MESMA grandeza noutro tempo, e uma cor nova diria que é outra coisa.
#: O tracejado é o que carrega a diferença, e ele sobrevive à escala de cinza.
COR_COMPARADO = "#7376d3"   # --au-accent-400
COR_NEGATIVO = "#dc2626"    # --au-danger
# `--au-success-text`, e não `--au-success`. O verde mais claro (`#059669`) não
# aceita rótulo dentro da barra: branco sobre ele dá 3,77:1 e escuro dá 3,69:1 —
# nenhum dos dois chega aos 4,5:1 exigidos. Com este, branco dá 5,48:1.
# A cascata pinta o passo de ganho com ele E escreve o valor dentro.
COR_POSITIVO = "#047857"    # --au-success-text
#: O fundo da cápsula do percentual. Igual à linha: a cápsula É a linha
#: rotulada, e duas cores ali fariam parecer duas informações. Branco sobre ela
#: dá 17,85:1 — é o que garante que o VALOR nunca se perde, nem onde o traço
#: cruza a barra escura.
COR_LINHA_ETIQUETA = "#0f172a"  # --au-chart-linha
COR_TEXTO = "#475569"       # --au-brand-600, que é --au-text-muted no claro
COR_GRADE = "#c7c8ed"       # --au-accent-200


@dataclass
class Coluna:
    """Uma coluna da tabela irmã."""

    titulo: str
    numerica: bool = True


@dataclass(frozen=True)
class Ponto:
    """Um ponto que LEVA a algum lugar — a perfuração.

    `url` é montada em **Python**, e não no JavaScript. O clique só navega para
    onde o servidor já disse que dá; a tabela irmã usa a mesma `url` num `<a>`,
    e por isso perfurar continua funcionando sem JavaScript nenhum.

    Montar a URL no JS exigiria replicar ali a regra de qual filtro pertence a
    qual nível — e essa regra mudaria de lugar sozinha na primeira dimensão nova.
    """

    rotulo: str
    valor: Decimal | None
    url: str = ""


@dataclass
class Migalha:
    """Um degrau da trilha, sempre clicável.

    Trilha e não botão "voltar": quem desceu três níveis precisa poder subir
    dois, e um botão só sobe um. E ela fica SEMPRE visível — descobrir onde se
    está pela ausência de dado é como a pessoa conclui que a tela quebrou.
    """

    rotulo: str
    url: str = ""
    atual: bool = False


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
    #: Uma URL por linha da tabela, paralela a `linhas`. Vazia quando o bloco não
    #: perfura. É ela que faz a tabela irmã funcionar sem JavaScript.
    urls: list[str] = field(default_factory=list)
    #: O texto do último nível: "daqui não desce mais, e é por isto".
    fronteira: str = ""
    #: `True` quando clicar RECORTA no mesmo nível, em vez de descer um.
    cruzado: bool = False
    #: O aviso de que o próximo clique troca o recorte mais antigo. Vazio quando
    #: ainda há espaço.
    aviso_de_substituicao: str = ""

    @property
    def vazio(self) -> bool:
        return not self.linhas

    @property
    def perfura(self) -> bool:
        return any(self.urls)

    @property
    def linhas_com_url(self):
        """`[(celulas, url), …]` — o que o template percorre."""
        return list(zip(self.linhas, self.urls or [""] * len(self.linhas)))


#: O rótulo dentro da barra CLARA. Não é branco, e a razão é medida:
#:
#:   branco sobre #a0a2e1 ....... 2,2:1   reprova em qualquer critério
#:   #475569 sobre #a0a2e1 ...... 3,4:1   o que havia — e o que gerou a queixa
#:   #212369 sobre #a0a2e1 ...... 5,8:1   este
#:
#: Branco dentro da barra escura e este dentro da clara é a única combinação em
#: que os dois números passam. Pintar os dois de branco atenderia ao pedido e
#: apagaria metade deles.
#:
#: É `--au-accent-800`, e não uma cor inventada para a ocasião: há um teste
#: exigindo que toda `COR_*` daqui exista em `tokens.css`, e ele me barrou —
#: uma cor que só o gráfico conhece é o começo de uma segunda paleta.
COR_ROTULO_ESCURO = "#212369"


def _rotulo(
    dimensao: str = "rotulo",
    cor: str = COR_ROTULO_ESCURO,
    dentro: bool = False,
) -> dict:
    """O rótulo por ponto — GIRADO em 90°, e sempre em NEGRITO.

    É o que faz treze meses caberem, e é o que o Portal GPS faz. Na horizontal,
    `R$ 1,19 Mi` mede mais que a largura de uma barra de treze e os rótulos
    viram uma mancha.

    **O negrito valia só para o rótulo de dentro, e estava errado.** O
    raciocínio era que fora da barra o fundo é branco e o peso normal bastaria —
    `#475569` sobre branco dá 7,5:1, contraste de sobra. Mas contraste não era o
    problema: em 10px e peso normal, girado, o número LIA como legenda, e não
    como dado. Quem abriu a tela disse que os valores em cima das colunas
    atrapalhavam a visualização, e o número que passa no contraste e não é lido
    está tão errado quanto o que não passa.

    O que muda com o fundo é a COR, não o peso — ver `cor_do_rotulo`.

    `hideOverlap` fica no `labelLayout` de quem chama: o que não couber some, e
    o número continua na tabela irmã.
    """
    return {
        "show": True,
        # A dimensão nomeada, resolvida contra o dado bruto. Conferido no fonte
        # da 6.1.0, `lib/model/mixin/dataFormat.js`.
        "formatter": f"{{@{dimensao}}}",
        "rotate": 90,
        "position": "insideBottom" if dentro else "top",
        # `align: "left"` NOS DOIS CASOS, e isto é a correção de um defeito real.
        #
        # Com `rotate: 90`, `align` decide para que lado o texto cresce a partir
        # do ponto de ancoragem. `"left"` faz ele subir; `"center"` faz ele ficar
        # CENTRADO na âncora — ou seja, metade acima e metade ABAIXO dela.
        #
        # Fora da barra a âncora fica na borda de cima, então `"center"` jogava
        # metade do número por cima da barra. Numa barra navy escura com texto
        # navy escuro, essa metade sumia. Foi relatado três vezes como "o valor
        # está preto", e a cor estava certa desde a primeira: o que estava errado
        # era o alinhamento.
        "align": "left",
        "verticalAlign": "middle",
        "distance": 6,
        "fontSize": 11,
        "fontWeight": "bold",
        "color": cor,
    }


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
            # A folga para o rótulo girado. Sem ela, o da barra mais alta é
            # cortado pela borda — e o corte não avisa: ele simplesmente some.
            "grid": {
                "left": 8, "right": 8, "top": FOLGA_DO_ROTULO, "bottom": 8,
                "containLabel": True,
            },
            "series": [
                {
                    "type": tipo,
                    "name": rotulo_serie or titulo,
                    "encode": {"x": "mes", "y": "valor"},
                    "itemStyle": {"color": COR_PRINCIPAL},
                    "barMaxWidth": 34,
                    "smooth": False,
                    "label": _rotulo(),
                    "labelLayout": {"hideOverlap": True},
                }
            ],
        }
    )
    if negativos:
        # Com valor negativo o rótulo em cima sobrepõe o eixo. Dentro da barra
        # que desce há espaço, e o branco garante contraste sobre o azul.
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
    #: A série do período COMPARADO — F1. Alinhada por POSIÇÃO e não por
    #: rótulo: os meses têm nomes diferentes (09/25 contra 09/26), e casar por
    #: nome não casaria nada.
    comparado: list[Decimal | None] | None = None,
    rotulo_comparado: str = "",
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
    comparado = comparado or [None] * len(pontos)
    fonte = [
        [
            mes,
            float(a) if a is not None else None,
            float(b) if b is not None else None,
            float(c) if c is not None else None,
            formatar(a),
            formatar(b),
            formatar_linha(c),
            float(d) if d is not None else None,
        ]
        for (mes, a, b), c, d in zip(pontos, linha, comparado)
    ]

    option = _base(altura)
    option.update(
        {
            "dataset": {
                "dimensions": [
                    "mes", "a", "b", "linha", "rotulo_a", "rotulo_b",
                    "rotulo_linha", "comparado",
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
            # Folga menor que a das outras: aqui o rótulo das barras fica DENTRO
            # delas, e só a etiqueta do percentual sobe. Ela não gira e mede
            # cerca de vinte pixels.
            "grid": {"left": 8, "right": 8, "top": 34, "bottom": 30, "containLabel": True},
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
                    "barMaxWidth": 26,
                    # DENTRO da barra e girado, como no Portal GPS: com duas
                    # séries lado a lado e treze meses, rótulo em cima não cabe
                    # de jeito nenhum.
                    "label": _rotulo("rotulo_a", cor="#ffffff", dentro=True),
                    "labelLayout": {"hideOverlap": True},
                },
                {
                    "type": "bar",
                    "name": rotulo_b,
                    "encode": {"x": "mes", "y": "b"},
                    "itemStyle": {"color": COR_SECUNDARIA},
                    "barMaxWidth": 26,
                    "label": _rotulo("rotulo_b", dentro=True),
                    "labelLayout": {"hideOverlap": True},
                },
            ],
        }
    )

    if any(v is not None for v in comparado):
        # LINHA e não terceira barra — F1.
        #
        # Com doze meses, três barras por mês são trinta e seis barras, e o
        # rótulo dentro delas deixa de caber. A linha atravessa as barras sem
        # disputar largura com elas, e é a convenção para "o mesmo período,
        # antes".
        #
        # No eixo da ESQUERDA (`yAxisIndex` ausente = 0), porque ela está em
        # reais como as barras. A linha da razão é a única do eixo direito —
        # duas linhas em escalas diferentes seriam duas verdades sobre a mesma
        # altura na tela.
        option["series"].append(
            {
                "type": "line",
                "name": rotulo_comparado or "Período anterior",
                "encode": {"x": "mes", "y": "comparado"},
                "itemStyle": {"color": COR_COMPARADO},
                # TRACEJADA: é o que diz "isto não é deste período" sem depender
                # de cor — a mesma regra que faz o trimestre parcial ser
                # hachurado.
                "lineStyle": {
                    "color": COR_COMPARADO, "width": 2, "type": "dashed",
                },
                "symbolSize": 5,
                "z": 5,
                # SEM rótulo por ponto. As barras já carregam o valor dentro, e
                # uma terceira etiqueta por mês torna o gráfico ilegível — que é
                # exatamente a queixa que originou o filtro de período.
                "label": {"show": False},
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
                "z": 10,
                # O percentual NÃO gira: ele é curto, e é a leitura principal do
                # bloco — no GPS ele aparece numa etiqueta escura sobre a linha.
                "label": {
                    "show": True,
                    "formatter": "{@rotulo_linha}",
                    "position": "top",
                    "fontSize": 10,
                    "fontWeight": "bold",
                    "color": "#ffffff",
                    # A ETIQUETA é mais escura que a linha. Branco sobre
                    # `#d97706` dá 3,19:1 e reprova; sobre `#b45309`, 5,02:1.
                    # A linha continua clara — ela é traço, não fundo de texto.
                    "backgroundColor": COR_LINHA_ETIQUETA,
                    "padding": [2, 4],
                    "borderRadius": 3,
                },
                "labelLayout": {"hideOverlap": True},
            }
        )

    colunas = [Coluna("Mês", numerica=False), Coluna(rotulo_a), Coluna(rotulo_b)]
    tem_comparado = any(v is not None for v in comparado)
    if tem_comparado:
        colunas.append(Coluna(rotulo_comparado or "Período anterior"))
    if any(v is not None for v in linha):
        colunas.append(Coluna(rotulo_linha or "Razão"))

    linhas = []
    for (mes, a, b), c, d in zip(pontos, linha, comparado):
        celulas = [mes, formatar_tabela(a), formatar_tabela(b)]
        if tem_comparado:
            # A tabela irmã ganha a coluna junto. Sem isso, quem não tem
            # JavaScript veria a comparação sumir — e ela é o conteúdo, não o
            # enfeite.
            celulas.append(formatar_tabela(d))
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


# ── Os tipos restantes do catálogo ──────────────────────────────────


def cascata(
    passos: list[tuple[str, Decimal]],
    *,
    chave: str,
    titulo: str,
    inicial: Decimal | None = None,
    rotulo_inicial: str = "Início",
    rotulo_final: str = "Final",
    #: Rótulos de `passos` que são SUBTOTAL, e não movimento — C6.
    #:
    #: Uma cascata da DRE sem eles é ilegível: entre a receita e o EBITDA há
    #: onze deduções, e quem lê precisa dos dois marcos do meio — receita
    #: líquida e margem de contribuição — para saber onde está. Sem marco, o
    #: gráfico é uma escada de onze degraus sem patamar.
    #:
    #: O subtotal é desenhado do ZERO, com o valor acumulado, e NÃO move o
    #: acumulador: ele é uma foto do estado, e somá-lo contaria o mesmo dinheiro
    #: duas vezes.
    subtotais: tuple[str, ...] = (),
    #: Uma URL por passo, paralela a `passos`. É o que faz cada degrau LEVAR ao
    #: detalhamento — o clique abre o grupo de contas correspondente.
    urls: list[str] | None = None,
    formatar=fmt.moeda_curta,
    formatar_tabela=fmt.moeda,
    altura: int = ALTURA,
) -> Bloco:
    """Cascata (*waterfall*) — "conquista × perda (ROB)" do benchmark.

    O ECharts não tem série de cascata. A receita conhecida é uma barra
    **empilhada** com uma série de base **transparente**: a base sobe até onde o
    passo começa, e a parte visível é o passo.

    `inicial` desenha a coluna de partida e a de chegada. Sem ela o gráfico é só
    o movimento — que é o caso de "conquistas e perdas do mês", onde o saldo
    inicial não é o assunto.

    Positivo em verde, negativo em vermelho, **e o valor escrito dentro**: cor
    nunca sozinha.
    """
    if not passos:
        return Bloco(chave=chave, titulo=titulo, option={}, altura=altura)

    rotulos: list[str] = []
    bases: list[float | None] = []
    valores: list[float] = []
    textos: list[str] = []
    cores: list[str] = []

    acumulado = inicial or Decimal("0")
    if inicial is not None:
        rotulos.append(rotulo_inicial)
        bases.append(0)
        valores.append(float(acumulado))
        textos.append(formatar(acumulado))
        cores.append(COR_PRINCIPAL)

    for rotulo, delta in passos:
        rotulos.append(rotulo)
        if rotulo in subtotais:
            # SUBTOTAL: coluna cheia desde o zero, com o acumulado. Não mexe no
            # acumulador — ele é uma foto do estado, e somá-lo contaria o mesmo
            # dinheiro duas vezes.
            bases.append(0)
            valores.append(float(acumulado))
            textos.append(formatar(acumulado))
            cores.append(COR_PRINCIPAL)
            continue
        # A base é o menor dos dois extremos: numa queda, ela fica no valor de
        # chegada e o bloco visível sobe até o de partida.
        base = min(acumulado, acumulado + delta)
        bases.append(float(base))
        valores.append(abs(float(delta)))
        textos.append(formatar(delta))
        cores.append(COR_POSITIVO if delta >= 0 else COR_NEGATIVO)
        acumulado += delta

    if inicial is not None:
        rotulos.append(rotulo_final)
        bases.append(0)
        valores.append(float(acumulado))
        textos.append(formatar(acumulado))
        cores.append(COR_PRINCIPAL)

    option = _base(altura)
    option.update(
        {
            "xAxis": {
                "type": "category",
                "data": rotulos,
                "axisLabel": {"color": COR_TEXTO, "fontSize": 11},
                "axisTick": {"show": False},
                "axisLine": {"lineStyle": {"color": COR_GRADE}},
            },
            "yAxis": _eixo_de_valor(),
            "series": [
                {
                    # A base invisível. `stack` compartilhado é o que a empilha
                    # debaixo do passo; `transparent` é o que a esconde sem
                    # tirá-la do empilhamento.
                    "type": "bar",
                    "name": "base",
                    "stack": "cascata",
                    "silent": True,
                    "itemStyle": {"color": "transparent"},
                    "emphasis": {"itemStyle": {"color": "transparent"}},
                    "data": bases,
                    "tooltip": {"show": False},
                    "legendHoverLink": False,
                },
                {
                    "type": "bar",
                    "name": titulo,
                    "stack": "cascata",
                    "barMaxWidth": 40,
                    "data": [
                        {
                            "value": valor,
                            "itemStyle": {"color": cor},
                            "rotulo": texto,
                            # POR ITEM, e não na série: cada passo da cascata tem
                            # a sua cor (ganho verde, perda vermelha, total
                            # navy), e uma cor de rótulo só serviria a um deles.
                            "label": {"color": cor_do_rotulo(cor)},
                        }
                        for valor, cor, texto in zip(valores, cores, textos)
                    ],
                    "label": {
                        "show": True,
                        # `{@rotulo}` não vale aqui: os dados são objetos e não
                        # `dataset`. O ECharts expõe o item cru em `{c}`… mas ele
                        # traz o valor, não o texto. `data.rotulo` é lido por
                        # `{@rotulo}` mesmo assim — o `retrieveRawValue` procura
                        # a dimensão no item bruto.
                        "formatter": "{@rotulo}",
                        "rotate": 90,
                        "position": "inside",
                        "fontSize": 11,
                        "fontWeight": "bold",
                    },
                    "labelLayout": {"hideOverlap": True},
                },
            ],
            # Sem legenda: a série de base não deve aparecer nela, e uma legenda
            # de um item só é ruído.
            "legend": {"show": False},
        }
    )

    # A TABELA IRMÃ repete a mesma aritmética, subtotal incluído.
    #
    # Se ela somasse o subtotal como movimento, contaria o mesmo dinheiro duas
    # vezes e terminaria num acumulado diferente do gráfico ao lado — duas
    # verdades na mesma faixa, e a tabela é justamente onde alguém vai conferir.
    linhas = []
    urls_da_tabela: list[str] = []
    acumulado = inicial or Decimal("0")
    if inicial is not None:
        linhas.append(
            [rotulo_inicial, formatar_tabela(acumulado), formatar_tabela(acumulado)]
        )
        urls_da_tabela.append("")
    for indice, (rotulo, delta) in enumerate(passos):
        if rotulo in subtotais:
            linhas.append([rotulo, "—", formatar_tabela(acumulado)])
        else:
            acumulado += delta
            linhas.append(
                [rotulo, formatar_tabela(delta), formatar_tabela(acumulado)]
            )
        urls_da_tabela.append(urls[indice] if urls else "")
    if inicial is not None:
        linhas.append([rotulo_final, "—", formatar_tabela(acumulado)])
        urls_da_tabela.append("")

    return Bloco(
        chave=chave,
        titulo=titulo,
        option=option,
        colunas=[
            Coluna("Passo", numerica=False), Coluna("Movimento"),
            Coluna("Acumulado"),
        ],
        linhas=linhas,
        urls=urls_da_tabela if urls else [],
        resumo=(
            f"{titulo}: {len(passos)} movimentos, terminando em "
            f"{formatar_tabela(acumulado)}. Os números estão na tabela abaixo."
        ),
        altura=altura,
    )


def _luminancia(cor: str) -> float:
    """Luminância relativa da WCAG, de `#rrggbb`.

    Existe para uma decisão só: rótulo branco ou escuro dentro do segmento. A
    paleta categórica mistura tons escuros (`#3539a9`) e claros (`#a0a2e1`), e
    pintar todos de branco — que era o que estava aqui — apaga o texto sobre os
    claros. Não é preferência: `#ffffff` sobre `#a0a2e1` dá 2,2:1, e o mínimo
    para texto pequeno é 4,5:1.
    """
    canais = []
    for inicio in (1, 3, 5):
        c = int(cor[inicio:inicio + 2], 16) / 255
        canais.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * canais[0] + 0.7152 * canais[1] + 0.0722 * canais[2]


def cor_do_rotulo(fundo: str) -> str:
    """Branco ou quase-preto, o que contrastar mais com `fundo`."""
    luz = _luminancia(fundo)
    contra_branco = 1.05 / (luz + 0.05)
    contra_escuro = (luz + 0.05) / (_luminancia(COR_ROTULO_ESCURO) + 0.05)
    return "#ffffff" if contra_branco >= contra_escuro else COR_ROTULO_ESCURO


def _paleta(quantos: int) -> list[str]:
    """Cores para série categórica, em ordem de contraste decrescente.

    Repete a partir da sexta: com mais de cinco categorias, o gráfico já está
    dizendo que a categoria errada foi escolhida — e repetir cor é melhor que
    inventar uma que não passa no contraste.
    """
    base = [COR_PRINCIPAL, COR_SECUNDARIA, COR_TERCIARIA, COR_POSITIVO, COR_NEGATIVO]
    return [base[i % len(base)] for i in range(quantos)]


def barra_composicao(
    partes: list[tuple[str, Decimal]],
    *,
    chave: str,
    titulo: str,
    formatar=fmt.moeda_curta,
    formatar_tabela=fmt.moeda,
    altura: int = 120,
) -> Bloco:
    """Uma barra horizontal única, empilhada — a composição de um total.

    É o "mix da carteira": uma linha só, cada segmento uma categoria, o valor
    **dentro do segmento** e a legenda embaixo.

    Altura menor que o padrão de propósito: uma barra não precisa de 260px, e
    ocupar esse espaço faria a composição parecer mais importante que a série.
    """
    if not partes:
        return Bloco(chave=chave, titulo=titulo, option={}, altura=altura)

    total = sum((valor for _, valor in partes), Decimal("0"))
    cores = _paleta(len(partes))

    option = _base(altura)
    option.update(
        {
            "grid": {"left": 8, "right": 8, "top": 8, "bottom": 34, "containLabel": True},
            "xAxis": {"type": "value", "show": False},
            "yAxis": {"type": "category", "data": [""], "show": False},
            "legend": {
                "bottom": 0,
                "icon": "roundRect",
                "itemHeight": 8,
                "textStyle": {"color": COR_TEXTO, "fontSize": 11},
            },
            "tooltip": {"trigger": "item", "confine": True},
            "series": [
                {
                    "type": "bar",
                    "name": nome,
                    "stack": "total",
                    "barMaxWidth": 34,
                    "itemStyle": {"color": cor},
                    "data": [{"value": float(valor), "rotulo": formatar(valor)}],
                    # O valor DENTRO do segmento: é o que faz a cor não estar
                    # sozinha numa barra em que os rótulos só existem na legenda.
                    "label": {
                        "show": True,
                        "formatter": "{@rotulo}",
                        "position": "inside",
                        "fontSize": 11,
                        "fontWeight": "bold",
                        "color": cor_do_rotulo(cor),
                    },
                    "labelLayout": {"hideOverlap": True},
                }
                for (nome, valor), cor in zip(partes, cores)
            ],
        }
    )

    return Bloco(
        chave=chave,
        titulo=titulo,
        option=option,
        colunas=[Coluna("Categoria", numerica=False), Coluna("Valor"), Coluna("Participação")],
        linhas=[
            [
                nome,
                formatar_tabela(valor),
                fmt.percentual(valor / total * 100) if total else fmt.VAZIO,
            ]
            for nome, valor in partes
        ],
        resumo=(
            f"{titulo}: {len(partes)} categorias, total de {formatar_tabela(total)}. "
            "Os números estão na tabela abaixo."
        ),
        altura=altura,
    )


def empilhada_percentual(
    categorias: list[str],
    series_por_nome: list[tuple[str, list[Decimal]]],
    *,
    chave: str,
    titulo: str,
    formatar=fmt.curto,
    formatar_tabela=fmt.numero,
    altura: int = ALTURA,
) -> Bloco:
    """Barras horizontais empilhadas, com o **valor absoluto** em cada segmento.

    Empilhada percentual mostra proporção e esconde tamanho: duas linhas de 100%
    parecem iguais quando uma vale dez e a outra dez mil. O valor dentro do
    segmento devolve o tamanho — é a mesma razão pela qual o benchmark escreve o
    número dentro de cada pedaço.
    """
    if not categorias or not series_por_nome:
        return Bloco(chave=chave, titulo=titulo, option={}, altura=altura)

    cores = _paleta(len(series_por_nome))
    option = _base(altura)
    option.update(
        {
            "grid": {"left": 8, "right": 8, "top": 8, "bottom": 34, "containLabel": True},
            "xAxis": {"type": "value", "show": False},
            "yAxis": {
                "type": "category",
                "data": categorias,
                "axisLabel": {"color": COR_TEXTO, "fontSize": 11},
                "axisTick": {"show": False},
                "axisLine": {"show": False},
            },
            "legend": {
                "bottom": 0, "icon": "roundRect", "itemHeight": 8,
                "textStyle": {"color": COR_TEXTO, "fontSize": 11},
            },
            "series": [
                {
                    "type": "bar",
                    "name": nome,
                    "stack": "total",
                    "barMaxWidth": 26,
                    "itemStyle": {"color": cor},
                    "data": [
                        {"value": float(v), "rotulo": formatar(v)} for v in valores
                    ],
                    "label": {
                        "show": True, "formatter": "{@rotulo}",
                        "position": "inside", "fontSize": 11,
                        "fontWeight": "bold", "color": cor_do_rotulo(cor),
                    },
                    "labelLayout": {"hideOverlap": True},
                }
                for (nome, valores), cor in zip(series_por_nome, cores)
            ],
        }
    )

    linhas = []
    for indice, categoria in enumerate(categorias):
        celulas = [categoria]
        for _, valores in series_por_nome:
            celulas.append(formatar_tabela(valores[indice]))
        linhas.append(celulas)

    return Bloco(
        chave=chave,
        titulo=titulo,
        option=option,
        colunas=[Coluna("Categoria", numerica=False)]
        + [Coluna(nome) for nome, _ in series_por_nome],
        linhas=linhas,
        resumo=f"{titulo}: {len(categorias)} categorias. Os números estão na tabela abaixo.",
        altura=altura,
    )


def rosca(
    fatias: list[tuple[str, Decimal]],
    *,
    chave: str,
    titulo: str,
    centro_rotulo: str = "",
    centro_valor: str = "",
    formatar_tabela=fmt.moeda,
    altura: int = ALTURA,
) -> Bloco:
    """Rosca com o total no centro.

    Rosca e não pizza: o buraco no meio é onde mora o total, e é ele que
    responde a primeira pergunta. Sem o centro preenchido, a rosca é uma pizza
    com menos tinta.

    Máximo prático de cinco a seis fatias — acima disso a legenda é maior que o
    desenho, e a leitura é a da tabela.
    """
    if not fatias:
        return Bloco(chave=chave, titulo=titulo, option={}, altura=altura)

    total = sum((valor for _, valor in fatias), Decimal("0"))
    cores = _paleta(len(fatias))

    option = _base(altura)
    option.pop("grid", None)
    option.update(
        {
            "tooltip": {"trigger": "item", "confine": True},
            "legend": {
                "bottom": 0, "icon": "circle", "itemHeight": 8,
                "textStyle": {"color": COR_TEXTO, "fontSize": 11},
            },
            # O total no centro, como texto do próprio gráfico.
            "title": {
                "text": centro_valor or fmt.moeda_curta(total),
                "subtext": centro_rotulo or "total",
                "left": "center",
                "top": "38%",
                "textStyle": {"fontSize": 18, "color": COR_TEXTO},
                "subtextStyle": {"fontSize": 11, "color": COR_TEXTO},
            },
            "series": [
                {
                    "type": "pie",
                    "radius": ["55%", "75%"],
                    "center": ["50%", "45%"],
                    "avoidLabelOverlap": True,
                    "itemStyle": {"borderColor": "#ffffff", "borderWidth": 2},
                    # O nome E o valor no rótulo externo: cor nunca sozinha, e a
                    # legenda embaixo não diz quanto.
                    "label": {
                        "show": True,
                        "formatter": "{b}\n{d}%",
                        "fontSize": 11,
                        "fontWeight": "bold",
                        "color": COR_ROTULO_ESCURO,
                    },
                    "labelLine": {"length": 8, "length2": 8},
                    "data": [
                        {"name": nome, "value": float(valor), "itemStyle": {"color": cor}}
                        for (nome, valor), cor in zip(fatias, cores)
                    ],
                }
            ],
        }
    )

    return Bloco(
        chave=chave,
        titulo=titulo,
        option=option,
        colunas=[Coluna("Fatia", numerica=False), Coluna("Valor"), Coluna("Participação")],
        linhas=[
            [
                nome,
                formatar_tabela(valor),
                fmt.percentual(valor / total * 100) if total else fmt.VAZIO,
            ]
            for nome, valor in fatias
        ],
        resumo=(
            f"{titulo}: {len(fatias)} fatias, total de {formatar_tabela(total)}. "
            "Os números estão na tabela abaixo."
        ),
        altura=altura,
    )


#: As faixas do medidor, na ordem do pior para o melhor. Cada uma tem NOME —
#: cor nunca sozinha, e num medidor a cor é quase tudo o que existe.
FAIXAS_PADRAO: tuple[tuple[Decimal, str, str], ...] = (
    (Decimal("50"), "crítico", COR_NEGATIVO),
    (Decimal("75"), "atenção", COR_ATENCAO),
    (Decimal("100"), "bom", COR_POSITIVO),
)


def medidor(
    valor: Decimal | None,
    *,
    chave: str,
    titulo: str,
    faixas: tuple = FAIXAS_PADRAO,
    maximo: Decimal = Decimal("100"),
    quantidade_por_faixa: dict[str, int] | None = None,
    sufixo: str = "",
    altura: int = 220,
) -> Bloco:
    """Ponteiro com faixas de governança — o Score PEC do benchmark.

    A tabela irmã traz a **quantidade por faixa**, e não só o ponteiro: um
    medidor diz onde a média caiu e esconde a distribuição. Média 78 com metade
    dos contratos abaixo de 50 é uma conversa diferente de média 78 com todos
    entre 70 e 85 — e o benchmark mostra as duas coisas lado a lado.

    `valor` `None` desenha o medidor **sem ponteiro** e a tela diz "sem
    amostra". Um ponteiro em zero seria lido como nota zero.
    """
    quantidade_por_faixa = quantidade_por_faixa or {}
    if valor is None and not quantidade_por_faixa:
        return Bloco(chave=chave, titulo=titulo, option={}, altura=altura)

    # `axisLine.lineStyle.color` do ECharts é uma lista de `[proporção, cor]`,
    # com a proporção acumulada de 0 a 1.
    cores = [[float(limite / maximo), cor] for limite, _, cor in faixas]

    option = _base(altura)
    option.pop("grid", None)
    option.pop("tooltip", None)
    option.update(
        {
            "series": [
                {
                    "type": "gauge",
                    "min": 0,
                    "max": float(maximo),
                    "startAngle": 200,
                    "endAngle": -20,
                    "radius": "94%",
                    "center": ["50%", "62%"],
                    "axisLine": {"lineStyle": {"width": 16, "color": cores}},
                    "pointer": {"show": valor is not None, "width": 4},
                    "progress": {"show": False},
                    "axisTick": {"show": False},
                    "splitLine": {"length": 8, "lineStyle": {"color": "#ffffff", "width": 2}},
                    "axisLabel": {"distance": 22, "fontSize": 10, "color": COR_TEXTO},
                    "anchor": {"show": True, "size": 8, "itemStyle": {"color": COR_TEXTO}},
                    "detail": {
                        "valueAnimation": False,
                        "fontSize": 24,
                        "color": COR_TEXTO,
                        "offsetCenter": [0, "42%"],
                        # `{value}` é o formatador nativo do gauge — e ele é o
                        # ÚNICO lugar do catálogo onde não dá para usar
                        # `{@dimensão}`, porque o gauge não tem `dataset`. Por
                        # isso o valor entra já arredondado, e o sufixo vem
                        # pronto do Python.
                        "formatter": f"{{value}}{sufixo}" if valor is not None else "—",
                    },
                    "data": [
                        {
                            "value": float(round(valor, 1)) if valor is not None else 0,
                            "name": titulo,
                        }
                    ],
                    "title": {"show": False},
                }
            ]
        }
    )

    linhas = []
    for limite, nome, _ in faixas:
        linhas.append(
            [
                f"{nome} · até {fmt.numero(limite)}{sufixo}",
                fmt.numero(quantidade_por_faixa.get(nome, 0)),
            ]
        )

    return Bloco(
        chave=chave,
        titulo=titulo,
        option=option,
        colunas=[Coluna("Faixa", numerica=False), Coluna("Quantidade")],
        linhas=linhas,
        resumo=(
            f"{titulo}: {fmt.numero(valor, 1)}{sufixo}."
            if valor is not None
            else f"{titulo}: sem amostra."
        )
        + " A distribuição por faixa está na tabela abaixo.",
        altura=altura,
    )


def bullet(
    itens: list[tuple[str, Decimal | None, Decimal | None]],
    *,
    chave: str,
    titulo: str,
    rotulo_valor: str = "Realizado",
    rotulo_meta: str = "Meta",
    formatar=fmt.curto,
    formatar_tabela=fmt.numero,
    altura: int = 0,
) -> Bloco:
    """Barra fina com a meta marcada — o que cabe numa célula de tabela.

    `itens` é `[(rótulo, valor, meta), …]`. A meta vira uma `markLine` vertical:
    ela cruza a barra no ponto do alvo, e a leitura é "passou ou não passou" sem
    ler número nenhum.

    Altura calculada pela quantidade de linhas: um bullet de três itens com
    260px de altura vira três tarjas gordas separadas por vazio.
    """
    if not itens:
        return Bloco(chave=chave, titulo=titulo, option={}, altura=altura or 120)

    altura = altura or max(90, 34 * len(itens) + 40)
    rotulos = [rotulo for rotulo, _, _ in itens]
    valores = [
        {"value": float(v) if v is not None else None, "rotulo": formatar(v)}
        for _, v, _ in itens
    ]
    metas = [float(m) if m is not None else None for _, _, m in itens]

    option = _base(altura)
    option.update(
        {
            "grid": {"left": 8, "right": 8, "top": 8, "bottom": 8, "containLabel": True},
            "xAxis": {"type": "value", "show": False},
            "yAxis": {
                "type": "category",
                "data": rotulos,
                "inverse": True,
                "axisLabel": {"color": COR_TEXTO, "fontSize": 11},
                "axisTick": {"show": False},
                "axisLine": {"show": False},
            },
            "series": [
                {
                    "type": "bar",
                    "name": rotulo_valor,
                    "barMaxWidth": 12,
                    "itemStyle": {"color": COR_PRINCIPAL, "borderRadius": 2},
                    "data": valores,
                    "label": {
                        "show": True, "formatter": "{@rotulo}",
                        "position": "right", "fontSize": 11,
                        "fontWeight": "bold", "color": COR_ROTULO_ESCURO,
                    },
                    "labelLayout": {"hideOverlap": True},
                    "markLine": {
                        "symbol": "none",
                        "silent": True,
                        "lineStyle": {"color": COR_NEGATIVO, "width": 2},
                        "label": {"show": False},
                        "data": [
                            {"xAxis": meta, "yAxis": indice}
                            for indice, meta in enumerate(metas)
                            if meta is not None
                        ],
                    },
                }
            ],
        }
    )

    return Bloco(
        chave=chave,
        titulo=titulo,
        option=option,
        colunas=[
            Coluna("Item", numerica=False),
            Coluna(rotulo_valor),
            Coluna(rotulo_meta),
            Coluna("Atingiu", numerica=False),
        ],
        linhas=[
            [
                rotulo,
                formatar_tabela(valor),
                formatar_tabela(meta),
                # A palavra, e não só a marca no gráfico: quem lê a tabela não
                # vê a `markLine`.
                ("sim" if (valor is not None and meta is not None and valor >= meta)
                 else "não" if (valor is not None and meta is not None) else "—"),
            ]
            for rotulo, valor, meta in itens
        ],
        resumo=f"{titulo}: {len(itens)} itens contra a meta. Detalhe na tabela abaixo.",
        altura=altura,
    )


def dispersao(
    pontos: list[tuple[str, Decimal, Decimal, Decimal]],
    *,
    chave: str,
    titulo: str,
    rotulo_x: str = "Receita",
    rotulo_y: str = "Margem",
    formatar_x=fmt.moeda_curta,
    formatar_y=fmt.percentual,
    #: O tooltip mostra o número EXATO. A abreviação serve ao eixo, onde não
    #: cabe mais; quem passa o mouse num ponto quer o valor, e "R$ 1.234" no
    #: lugar de "R$ 1.234,50" é o tipo de arredondamento que reaparece como
    #: divergência numa conferência contra o ERP.
    formatar_x_exato=fmt.moeda,
    limiar_y: Decimal | None = None,
    altura: int = 300,
) -> Bloco:
    """Receita × margem, com o tamanho do ponto pelo valor mensal.

    Adição nossa, e não do benchmark. Ela responde a pergunta que nenhuma das
    outras responde: **quais contratos são grandes E pouco rentáveis** — o
    quadrante direito-inferior, que é onde o dinheiro está e a margem não.

    `pontos` é `[(rótulo, x, y, tamanho), …]`. `limiar_y` desenha a linha da
    margem mínima: sem ela, o quadrante que importa não tem fronteira visível.

    **Três coisas dizem "este é o problema", e não uma.** A posição abaixo da
    linha, a COR vermelha do ponto e o texto no tooltip. Só a posição não
    bastava: alguém olhou este gráfico e disse "não entendi como ler" — e estava
    certo, porque a explicação de como lê-lo morava num comentário do template,
    que é o único lugar da tela onde o usuário não olha.
    """
    if not pontos:
        return Bloco(chave=chave, titulo=titulo, option={}, altura=altura)

    tamanhos = [float(t) for _, _, _, t in pontos] or [1.0]
    maior = max(tamanhos) or 1.0

    def abaixo(y: Decimal) -> bool:
        return limiar_y is not None and y < limiar_y

    # Os limites da área do quadrante. "Muito" é a METADE do maior faturamento,
    # e não um valor fixo: uma carteira de contratos de 30 mil e outra de 3
    # milhões têm o mesmo desenho, e um corte absoluto serviria a uma só.
    receitas = [float(x) for _, x, _, _ in pontos]
    meia_receita = max(receitas) / 2 if receitas else 0.0
    margens = [float(y) for _, _, y, _ in pontos]
    piso_y = min(margens + [float(limiar_y) if limiar_y is not None else 0.0])

    option = _base(altura)
    option.update(
        {
            # O TOOLTIP É `richText`, E O SEPARADOR É `\n` — corrigido em
            # 17/09/2026, depois de `<br>` aparecer LITERAL na tela.
            #
            # ## O caminho até aqui, para ninguém refazer
            #
            # O texto das três linhas vive no `name` do item, porque é lá que o
            # pt-BR formatado em Python cabe inteiro — a regra de formato fica
            # num lugar só. Mas o ECharts **escapa o valor** que substitui em
            # `{b}`: medido no navegador contra este bundle, `CT-101<br>…`
            # chegava ao DOM como `CT-101&lt;br&gt;…`.
            #
            # Três saídas foram medidas, e duas não servem:
            #
            # 1. `<br>` LITERAL no template do formatter funciona — só o VALOR
            #    é escapado, o template não. Mas então os números teriam de vir
            #    por `{a}{b}{c}{d}`, e `{c}` traz o array cru, sem pt-BR.
            # 2. Dimensões extras em `value` para `{c2}`/`{c3}`: medido, chega
            #    literal. `{cN}` não existe neste caminho.
            # 3. `renderMode: "richText"`: o tooltip é desenhado como texto e
            #    não como HTML, então não há o que escapar, e `\n` quebra linha
            #    de verdade. Medido: três `<text>` no SVG.
            #
            # Função no `formatter` não é opção em nenhuma delas: a `option`
            # viaja como JSON, e função não sobrevive à serialização.
            #
            # O PREÇO do richText é que ele não herda o CSS dos tooltips HTML
            # das outras telas — daí o estilo explícito abaixo, que repete o
            # visual padrão. E "abaixo do mínimo" perde o negrito: a cor
            # vermelha do ponto e a posição sob a linha continuam dizendo o
            # mesmo, que é a razão de serem três sinais e não um.
            "tooltip": {
                "trigger": "item",
                "confine": True,
                "renderMode": "richText",
                "formatter": "{b}",
                "backgroundColor": "#ffffff",
                "borderColor": "#cbd5e1",
                "borderWidth": 1,
                "padding": [8, 10],
                "textStyle": {"color": COR_LINHA, "fontSize": 12, "lineHeight": 18},
            },
            # A UNIDADE NO NOME DO EIXO. Sem ela, "25" no eixo vertical e
            # "30,000" no horizontal são dois números sem grandeza, e a pessoa
            # tem de deduzir qual é qual. Foi a primeira coisa que faltou quando
            # alguém disse "não entendi como ler".
            "xAxis": {
                **_eixo_de_valor(),
                "name": f"{rotulo_x} (R$)",
                "nameLocation": "middle",
                "nameGap": 28,
                "nameTextStyle": {"color": COR_TEXTO, "fontSize": 11},
            },
            "yAxis": {
                **_eixo_de_valor(),
                "name": f"{rotulo_y} (%)",
                "nameLocation": "middle",
                "nameGap": 40,
                "nameTextStyle": {"color": COR_TEXTO, "fontSize": 11},
                # String e não função: `{value}` é template do ECharts, e um
                # `Intl` em JS poria a regra de formato num segundo lugar.
                "axisLabel": {
                    **_eixo_de_valor()["axisLabel"], "formatter": "{value}%"
                },
            },
            "series": [
                {
                    "type": "scatter",
                    "name": titulo,
                    "symbolSize": 8,
                    "itemStyle": {"opacity": 0.8},
                    "data": [
                        {
                            # `name` É o texto do tooltip. Ver a nota em
                            # `tooltip`, acima.
                            "name": (
                                f"{rotulo}\n{rotulo_x}: {formatar_x_exato(x)}"
                                f"\n{rotulo_y}: {formatar_y(y)}"
                                + ("\nabaixo do mínimo" if abaixo(y) else "")
                            ),
                            "value": [float(x), float(y)],
                            # O tamanho proporcional, entre 8 e 34 pixels. Sem
                            # piso, o contrato pequeno vira um ponto que ninguém
                            # acha; sem teto, o maior cobre os vizinhos.
                            "symbolSize": 8 + 26 * (float(t) / maior),
                            "rotulo": rotulo,
                            # VERMELHO abaixo do limiar. A posição sozinha exige
                            # que a pessoa siga a linha tracejada com o olho até
                            # cada ponto; a cor responde de relance.
                            "itemStyle": {
                                "color": COR_NEGATIVO if abaixo(y) else COR_PRINCIPAL
                            },
                            # O RÓTULO por item, com o texto LITERAL.
                            #
                            # `formatter` sem chave nenhuma é renderizado como
                            # está — e com o nome do contrato aqui, o gráfico
                            # deixa de depender de `{@rotulo}` resolver contra
                            # uma dimensão que este tipo de série não declara.
                            "label": {
                                "show": bool(abaixo(y)),
                                "formatter": rotulo,
                            },
                        }
                        for rotulo, x, y, t in pontos
                    ],
                    # O RÓTULO SÓ NOS QUE ESTÃO ABAIXO DO LIMIAR — ver o
                    # `label: {show: False}` por item, acima.
                    #
                    # Nomear todos os contratos enche o gráfico, o `hideOverlap`
                    # apaga a maioria, e o que sobra é aleatório: os que
                    # aparecem são os que couberam, não os que importam. Nomear
                    # só os vermelhos deixa a leitura em uma frase — "estes
                    # quatro estão abaixo da margem, e este é grande".
                    # SEM `formatter` na série: cada item traz o seu, com o
                    # nome do contrato literal. O que fica aqui é só a
                    # aparência, que é igual para todos.
                    "label": {
                        "show": True,
                        "position": "top", "fontSize": 10,
                        "fontWeight": "bold", "color": COR_NEGATIVO,
                    },
                    "labelLayout": {"hideOverlap": True},
                    "markLine": (
                        {
                            "symbol": "none",
                            "silent": True,
                            "lineStyle": {"color": COR_NEGATIVO, "type": "dashed"},
                            "label": {
                                "formatter": formatar_y(limiar_y),
                                "color": COR_NEGATIVO,
                                "fontSize": 10,
                            },
                            "data": [{"yAxis": float(limiar_y)}],
                        }
                        if limiar_y is not None
                        else {"data": []}
                    ),
                    # O QUADRANTE, NOMEADO DENTRO DO GRÁFICO.
                    #
                    # A linha tracejada dizia onde a margem mínima passa, e o
                    # vermelho dizia quem está abaixo dela. Nenhum dos dois
                    # dizia POR QUE olhar para lá — e "por que olhar" é a única
                    # pergunta que este gráfico existe para responder.
                    #
                    # A área vai da metade direita do eixo X para baixo do
                    # limiar: é onde mora o contrato que fatura muito e rende
                    # pouco, que é o caro de descobrir tarde. `silent` para não
                    # roubar o clique nem o tooltip dos pontos que estão dentro
                    # dela.
                    "markArea": (
                        {
                            "silent": True,
                            "itemStyle": {"color": COR_NEGATIVO, "opacity": 0.06},
                            "label": {
                                "show": True,
                                "position": "insideBottomRight",
                                "formatter": "fatura muito, rende pouco",
                                "color": COR_NEGATIVO,
                                "fontSize": 10,
                                "fontWeight": "bold",
                            },
                            "data": [[
                                {"xAxis": float(meia_receita), "yAxis": float(piso_y)},
                                {"xAxis": "max", "yAxis": float(limiar_y)},
                            ]],
                        }
                        if limiar_y is not None
                        else {"data": []}
                    ),
                }
            ],
        }
    )

    return Bloco(
        chave=chave,
        titulo=titulo,
        option=option,
        colunas=[
            Coluna("Item", numerica=False), Coluna(rotulo_x), Coluna(rotulo_y),
            Coluna("Situação", numerica=False),
        ],
        # A tabela irmã ganha a mesma terceira informação que o gráfico: a cor
        # não pode ser o único lugar onde "abaixo do mínimo" está escrito.
        linhas=[
            [
                rotulo,
                formatar_x(x),
                formatar_y(y),
                "abaixo do mínimo" if abaixo(y) else "ok",
            ]
            for rotulo, x, y, _ in pontos
        ],
        resumo=(
            f"{titulo}: {len(pontos)} pontos, {rotulo_x} contra {rotulo_y}. "
            "Os números estão na tabela abaixo."
        ),
        altura=altura,
    )


# ── Os dois que NÃO são gráfico ─────────────────────────────────────


#: As faixas do farol, do pior para o melhor. `nome` é o que vai escrito ao
#: lado — cor nunca sozinha, e num farol a cor é a única coisa que existe.
FAROL_CRITICO = "critico"
FAROL_ATENCAO = "atencao"
FAROL_BOM = "bom"
FAROL_INDEFINIDO = "indefinido"

ROTULO_DO_FAROL = {
    FAROL_CRITICO: "crítico",
    FAROL_ATENCAO: "atenção",
    FAROL_BOM: "bom",
    FAROL_INDEFINIDO: "sem amostra",
}


@dataclass(frozen=True)
class Farol:
    """Não é gráfico: é um `<span>` com classe e **rótulo textual**.

    Desenhar um círculo colorido de 10px com ECharts custaria um contêiner, uma
    inicialização e 217 KB de biblioteca para pintar um ponto. E o ponto sozinho
    não diz nada a quem não distingue as cores.

    `situacao` vira classe CSS; `rotulo` vira texto ao lado. Os dois sempre.
    """

    situacao: str
    valor: str = ""

    @property
    def rotulo(self) -> str:
        return ROTULO_DO_FAROL.get(self.situacao, ROTULO_DO_FAROL[FAROL_INDEFINIDO])


def farol(
    valor: Decimal | None,
    *,
    critico: Decimal,
    atencao: Decimal,
    maior_melhor: bool = True,
    formatar=fmt.percentual,
) -> Farol:
    """A faixa de um valor. `None` devolve **indefinido**, e nunca "crítico".

    Sem amostra não é o pior caso: é ausência de caso. Pintar de vermelho o que
    ninguém mediu manda alguém correr atrás do problema errado.
    """
    if valor is None:
        return Farol(situacao=FAROL_INDEFINIDO, valor=fmt.VAZIO)

    texto = formatar(valor)
    if maior_melhor:
        situacao = (
            FAROL_CRITICO if valor < critico
            else FAROL_ATENCAO if valor < atencao
            else FAROL_BOM
        )
    else:
        # Turnover, absenteísmo, custo: menor é melhor, e os limiares invertem.
        situacao = (
            FAROL_CRITICO if valor > critico
            else FAROL_ATENCAO if valor > atencao
            else FAROL_BOM
        )
    return Farol(situacao=situacao, valor=texto)


@dataclass(frozen=True)
class Celula:
    """Uma célula do mapa de calor: o texto e a faixa."""

    texto: str
    situacao: str = FAROL_INDEFINIDO


@dataclass
class MapaDeCalor:
    """Uma TABELA com classe de faixa por célula — e não um `heatmap`.

    O prompt do catálogo dá as duas opções e recomenda a tabela. As razões:

    - ela é **menor**: zero bytes de biblioteca, e o mapa de calor costuma ser a
      grade inteira de uma tela;
    - ela continua legível **sem JavaScript**, que é o pior cenário do resto do
      catálogo e o normal aqui;
    - o número fica **selecionável e copiável**, e uma grade de score existe para
      alguém copiar uma linha dela para um e-mail.

    A cor é reforço: cada célula traz o número escrito, e a legenda nomeia as
    faixas.
    """

    chave: str
    titulo: str
    colunas: list[str]
    linhas: list[tuple[str, list[Celula]]]
    legenda: list[tuple[str, str]] = field(default_factory=list)

    @property
    def vazio(self) -> bool:
        return not self.linhas


def mapa_calor_tabela(
    colunas: list[str],
    linhas: list[tuple[str, list[Decimal | None]]],
    *,
    chave: str,
    titulo: str,
    critico: Decimal,
    atencao: Decimal,
    maior_melhor: bool = True,
    formatar=fmt.percentual,
) -> MapaDeCalor:
    """A grade do Score PEC: uma linha por item, uma coluna por período."""
    return MapaDeCalor(
        chave=chave,
        titulo=titulo,
        colunas=colunas,
        linhas=[
            (
                nome,
                [
                    Celula(
                        texto=(f := farol(
                            valor, critico=critico, atencao=atencao,
                            maior_melhor=maior_melhor, formatar=formatar,
                        )).valor,
                        situacao=f.situacao,
                    )
                    for valor in valores
                ],
            )
            for nome, valores in linhas
        ],
        legenda=[
            (FAROL_BOM, ROTULO_DO_FAROL[FAROL_BOM]),
            (FAROL_ATENCAO, ROTULO_DO_FAROL[FAROL_ATENCAO]),
            (FAROL_CRITICO, ROTULO_DO_FAROL[FAROL_CRITICO]),
        ],
    )


#: As cores por ano do comparativo trimestral — F2.
#:
#: Três, porque três anos é o teto do gráfico: a quarta barra por trimestre não
#: cabe com rótulo, e comparar quatro anos de uma vez não é uma pergunta que
#: alguém faça de pé numa reunião.
#:
#: O ano CORRENTE é o primeiro e o mais escuro — ele é o assunto, e os
#: anteriores são o contexto.
CORES_POR_ANO: tuple[str, ...] = (COR_PRINCIPAL, COR_SECUNDARIA, COR_COMPARADO)


def barras_por_ano(
    categorias: list[str],
    series: list[tuple[str, list[Decimal | None]]],
    *,
    chave: str,
    titulo: str,
    #: `(nome da série, categoria)` dos valores INCOMPLETOS — F2.
    #:
    #: Comparar um trimestre de dois meses com um de três, sem avisar, é o erro
    #: que mais gera decisão errada em reunião de resultado: a barra menor é
    #: lida como queda, e a queda não existe.
    parciais: dict[tuple[str, str], str] | None = None,
    formatar=fmt.moeda_curta,
    formatar_tabela=fmt.moeda,
    altura: int = ALTURA,
) -> Bloco:
    """Barras agrupadas por período, uma cor por ano — F2.

    ## O trimestre parcial é marcado de TRÊS formas

    Opacidade, borda tracejada e o texto "parcial (2 de 3 meses)" no rótulo.
    Três e não uma porque as duas primeiras somem em impressão preto-e-branco e
    para quem não distingue a diferença — e a regra do produto é que cor nunca
    vem sozinha. O texto é o que sobrevive a tudo, e é o que a tabela irmã leva.

    Não usa `decal` do ECharts: o gerador de padrão pode não estar no build
    customizado, e uma hachura que não desenha vira uma barra igual às outras
    sem ninguém perceber.
    """
    if not categorias or not series:
        return Bloco(chave=chave, titulo=titulo, option={}, altura=altura)

    parciais = parciais or {}
    option = _base(altura)
    option.update(
        {
            "legend": {
                "bottom": 0,
                "icon": "roundRect",
                "itemHeight": 8,
                "textStyle": {"color": COR_TEXTO, "fontSize": 11},
            },
            "grid": {
                "left": 8, "right": 8, "top": 34, "bottom": 30,
                "containLabel": True,
            },
            "xAxis": {
                "type": "category",
                "data": categorias,
                "axisLabel": {"color": COR_TEXTO, "fontSize": 11},
                "axisTick": {"show": False},
                "axisLine": {"lineStyle": {"color": COR_GRADE}},
            },
            "yAxis": _eixo_de_valor(),
            "series": [
                {
                    "type": "bar",
                    "name": nome,
                    "barMaxWidth": 22,
                    "data": [
                        _barra_do_ano(
                            valor, CORES_POR_ANO[i % len(CORES_POR_ANO)],
                            parciais.get((nome, categoria)), formatar,
                        )
                        for categoria, valor in zip(categorias, valores)
                    ],
                    "labelLayout": {"hideOverlap": True},
                }
                for i, (nome, valores) in enumerate(series)
            ],
        }
    )

    colunas = [Coluna("Período", numerica=False)] + [
        Coluna(nome) for nome, _ in series
    ]
    linhas = []
    for indice, categoria in enumerate(categorias):
        celulas = [categoria]
        for nome, valores in series:
            valor = valores[indice] if indice < len(valores) else None
            texto = formatar_tabela(valor) if valor is not None else "—"
            # A TABELA IRMÃ leva o aviso junto: sem JavaScript ela é o
            # conteúdo, e um "parcial" que só existe no gráfico não existe.
            aviso = parciais.get((nome, categoria))
            celulas.append(f"{texto} ({aviso})" if aviso else texto)
        linhas.append(celulas)

    return Bloco(
        chave=chave,
        titulo=titulo,
        option=option,
        colunas=colunas,
        linhas=linhas,
        resumo=(
            f"{titulo}: {len(series)} anos em {len(categorias)} períodos. "
            "Os números estão na tabela abaixo."
        ),
        altura=altura,
    )


def _barra_do_ano(valor, cor: str, aviso: str | None, formatar):
    """Uma barra. Parcial ganha opacidade, tracejado e o texto junto do rótulo."""
    if valor is None:
        return {"value": None}
    estilo = {"color": cor}
    rotulo = formatar(valor)
    if aviso:
        estilo |= {"opacity": 0.55, "borderColor": cor, "borderWidth": 1,
                   "borderType": "dashed"}
        rotulo = f"{rotulo}\n{aviso}"
    return {
        "value": float(valor),
        "itemStyle": estilo,
        "label": {
            "show": True,
            "position": "top",
            "formatter": rotulo,
            "fontSize": 10,
            "fontWeight": "bold" if aviso else "normal",
            "color": COR_ROTULO_ESCURO,
        },
    }


def barras_por_categoria(
    pontos: list[Ponto],
    *,
    chave: str,
    titulo: str,
    rotulo_serie: str = "",
    formatar=fmt.moeda_curta,
    formatar_tabela=fmt.moeda,
    fronteira: str = "",
    altura: int = ALTURA,
) -> Bloco:
    """Barras por categoria, e **cada barra leva a algum lugar**.

    É o tipo que faz a perfuração: uma barra por regional, por centro de custo
    ou por contrato, conforme o nível — e o clique desce um degrau.

    A `url` de cada ponto vem pronta do Python e viaja como dimensão do
    `dataset`. O JavaScript lê `params.data.url` e navega; ele não sabe qual
    filtro pertence a qual nível, e não precisa saber.

    A tabela irmã usa a **mesma** URL num `<a>`. É o que faz perfurar continuar
    funcionando com o JavaScript desligado — e o prompt é explícito nisso.
    """
    if not pontos:
        return Bloco(
            chave=chave, titulo=titulo, option={}, altura=altura, fronteira=fronteira
        )

    fonte = [
        [
            p.rotulo,
            float(p.valor) if p.valor is not None else None,
            formatar(p.valor),
            p.url,
        ]
        for p in pontos
    ]

    option = _base(altura)
    option.update(
        {
            "dataset": {
                "dimensions": ["categoria", "valor", "rotulo", "url"],
                "source": fonte,
            },
            "xAxis": {
                "type": "category",
                "axisLabel": {
                    "color": COR_TEXTO,
                    "fontSize": 11,
                    # Categoria tem nome de tamanho imprevisível — "Centro-Oeste"
                    # ao lado de "SP". Sem quebra, o eixo esconde metade.
                    "interval": 0,
                    "overflow": "break",
                    "width": 90,
                },
                "axisTick": {"show": False},
                "axisLine": {"lineStyle": {"color": COR_GRADE}},
            },
            "yAxis": _eixo_de_valor(),
            "grid": {
                "left": 8, "right": 8, "top": FOLGA_DO_ROTULO, "bottom": 8,
                "containLabel": True,
            },
            "series": [
                {
                    "type": "bar",
                    "name": rotulo_serie or titulo,
                    "encode": {"x": "categoria", "y": "valor"},
                    "itemStyle": {"color": COR_PRINCIPAL},
                    "barMaxWidth": 44,
                    "label": _rotulo(),
                    "labelLayout": {"hideOverlap": True},
                    # O cursor de mão é o que anuncia que a barra é clicável.
                    # Sem ele, a perfuração é um segredo.
                    "cursor": "pointer" if any(p.url for p in pontos) else "default",
                }
            ],
        }
    )

    return Bloco(
        chave=chave,
        titulo=titulo,
        option=option,
        colunas=[Coluna("Categoria", numerica=False), Coluna(rotulo_serie or "Valor")],
        linhas=[[p.rotulo, formatar_tabela(p.valor)] for p in pontos],
        urls=[p.url for p in pontos],
        resumo=(
            f"{titulo}: {len(pontos)} categorias. "
            + ("Cada uma abre o detalhe. " if any(p.url for p in pontos) else "")
            + "Os números estão na tabela abaixo."
        ),
        fronteira=fronteira,
        altura=altura,
    )
