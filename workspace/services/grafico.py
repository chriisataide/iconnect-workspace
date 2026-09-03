"""Coordenadas de gráfico, calculadas em Python.

## Por que aqui e não no template

Porque a CSP é estrita: **zero `style=`**, e barra desenhada com `width: 42%`
inline não passa. Em SVG, `x`, `y`, `width` e `height` são ATRIBUTOS, e atributo
não é estilo — o gráfico entra sem uma linha de CSS inline e sem uma linha de JS.

E porque template não faz conta. `{% widthratio %}` resolve uma proporção e não
resolve escala com base negativa, que é o caso de margem de contribuição — o
gráfico do EBITDA tem barras para os dois lados.

## Coordenada de SVG é TEXTO, e não número

Este módulo devolve `x`, `y`, `largura` e `altura` como **string**, com ponto
decimal. Parece detalhe e não é: foi o defeito que deixou os dois gráficos da
tela de Resultados **em branco**, e ninguém viu por semanas.

O Django localiza número em template. Com `LANGUAGE_CODE = "pt-br"`, `{{ 10.52 }}`
renderiza `10,52` — que é o certo para um valor numa tabela e é **inválido** num
atributo de SVG. A gramática de `x=""` é ASCII com ponto; com vírgula, o
navegador descarta o `<rect>` inteiro. Sem erro no console, sem nada no log do
servidor: o gráfico simplesmente não está lá.

`{% localize off %}` no template resolveria — e cairia no dia em que alguém
escrevesse o próximo SVG. Formatar aqui resolve para todo template que use este
módulo, inclusive os que ainda não existem.

`valor` continua `Decimal`: ele vai para o `<title>`, que é texto para gente ler,
onde a vírgula é o certo.

## O que este módulo NÃO faz

Não escolhe cor, não escreve rótulo em português e não sabe o que é receita. Ele
converte uma lista de números numa lista de retângulos. Tudo o que é semântica
fica no template, onde alguém consegue ler.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

LARGURA = 720
ALTURA = 180
#: Espaço para o eixo. Sem ele a primeira barra encosta na borda e o gráfico
#: parece cortado.
MARGEM = 4


def coordenada(valor: float) -> str:
    """Um número pronto para entrar num atributo de SVG.

    Ponto decimal sempre, e sem zeros à toa: `10.52`, `176`, `0.5`. O `:g` corta
    a cauda de `176.0` sem transformar `0.5` em `0`.

    Público de propósito: quem escrever o próximo SVG deste produto precisa
    achar isto antes de escrever `x="{{ algo }}"`.
    """
    return f"{float(valor):g}"


@dataclass(frozen=True)
class Barra:
    #: STRING, e não `float`. Ver o cabeçalho do módulo: número em atributo de
    #: SVG passa pela localização do Django e sai com vírgula, e o navegador
    #: descarta o retângulo em silêncio.
    x: str
    y: str
    largura: str
    altura: str
    rotulo: str
    valor: Decimal
    #: `True` quando o valor é negativo. O template decide o que fazer com isso;
    #: aqui só se registra o fato.
    negativa: bool = False


@dataclass(frozen=True)
class Serie:
    barras: list[Barra]
    largura: int = LARGURA
    altura: int = ALTURA
    #: Onde fica o zero. Com valores só positivos ele é a base; com negativos,
    #: fica no meio — e é o que faz o EBITDA negativo apontar para baixo em vez
    #: de virar uma barra minúscula para cima.
    #:
    #: String pelo mesmo motivo das coordenadas da barra: ela vai para `y1`.
    linha_zero: str = coordenada(ALTURA)
    maximo: Decimal = Decimal("0")
    minimo: Decimal = Decimal("0")

    @property
    def vazia(self) -> bool:
        return not self.barras


def barras(
    pontos: list[tuple[str, Decimal]],
    largura: int = LARGURA,
    altura: int = ALTURA,
) -> Serie:
    """Uma série de barras. `pontos` é `[(rótulo, valor), ...]`, em ordem.

    Escala pelo maior valor ABSOLUTO, e não pelo intervalo: uma série que vai de
    98 a 100 desenhada de 98 a 100 vira um degrau enorme para uma variação de
    2% — que é a forma mais fácil de um gráfico honesto contar uma mentira.
    """
    if not pontos:
        return Serie(barras=[], largura=largura, altura=altura)

    valores = [valor for _, valor in pontos]
    maximo = max(valores)
    minimo = min(valores)
    teto = max(abs(maximo), abs(minimo)) or Decimal("1")

    tem_negativo = minimo < 0
    util = altura - MARGEM * 2
    zero = MARGEM + (util / 2 if tem_negativo else util)
    escala = (util / 2 if tem_negativo else util) / float(teto)

    passo = largura / len(pontos)
    # 62% do passo: a barra respira sem o vão virar o assunto do gráfico.
    espessura = max(passo * 0.62, 1.0)

    desenhadas = []
    for indice, (rotulo, valor) in enumerate(pontos):
        comprimento = abs(float(valor)) * escala
        negativa = valor < 0
        desenhadas.append(
            Barra(
                x=coordenada(round(indice * passo + (passo - espessura) / 2, 2)),
                y=coordenada(round(zero if negativa else zero - comprimento, 2)),
                largura=coordenada(round(espessura, 2)),
                # Altura mínima de meio pixel: barra de valor zero com altura
                # zero some, e sumir é diferente de valer zero.
                altura=coordenada(round(max(comprimento, 0.5), 2)),
                rotulo=rotulo,
                valor=valor,
                negativa=negativa,
            )
        )

    return Serie(
        barras=desenhadas,
        largura=largura,
        altura=altura,
        linha_zero=coordenada(round(zero, 2)),
        maximo=maximo,
        minimo=minimo,
    )


def da_serie(linhas, campo: str, **kwargs) -> Serie:
    """As barras de um campo da série de competências.

    O rótulo é `MM/AA` — mês e ano curtos. Só o mês faria janeiro de 2025 e
    janeiro de 2026 aparecerem como a mesma coluna numa série de treze meses.
    """
    pontos = [
        (f"{linha.mes:02d}/{str(linha.ano)[2:]}", getattr(linha, campo))
        for linha in linhas
    ]
    return barras(_somar_por_rotulo(pontos), **kwargs)


def _somar_por_rotulo(pontos):
    """Uma barra por MÊS, e não uma por linha.

    A série vem por contrato e por centro de custo; desenhá-la crua daria
    dezoito barras para agosto. O gráfico responde "como foi o mês", e o
    detalhe é a tabela abaixo dele.
    """
    somados: dict[str, Decimal] = {}
    ordem: list[str] = []
    for rotulo, valor in pontos:
        if rotulo not in somados:
            somados[rotulo] = Decimal("0")
            ordem.append(rotulo)
        somados[rotulo] += valor
    return [(rotulo, somados[rotulo]) for rotulo in ordem]
