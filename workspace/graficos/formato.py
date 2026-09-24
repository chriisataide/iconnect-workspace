"""Número em pt-BR — e a fonte ÚNICA dele.

## Por que a formatação mora aqui, e não no JavaScript

O ECharts formata em en-US por padrão: `1,234,567.89`. O caminho óbvio seria
escrever um `formatter` em JS com `Intl.NumberFormat('pt-BR')` — e aí a mesma
regra existiria em dois lugares, o gráfico e a **tabela irmã**, que precisa
mostrar exatamente os mesmos números.

Duas implementações da mesma regra divergem. Sempre. E divergem no caso raro —
o negativo, o zero, o valor entre 999 mil e 1 milhão — que é justamente onde
alguém vai reparar.

## Como o número formatado chega ao gráfico sem uma linha de JS

`formatter` do ECharts aceita um **template em string** com `{@dimensão}`, que é
resolvido contra o dado bruto (conferido no fonte da 6.1.0,
`lib/model/mixin/dataFormat.js`). Então o Python manda o texto pronto como uma
dimensão a mais do `dataset`, e o `formatter` é `"{@rotulo}"`.

Zero função em JavaScript. Os números vêm do servidor, sempre — inclusive a
vírgula.

## As escalas

O benchmark escreve "Mil" e "Mi", e não `1.234.567`. Num eixo de treze meses, o
número por extenso ocupa a largura de três meses e o eixo vira uma parede.

Três faixas, e os cortes têm motivo:

    abaixo de 10 mil     `1.234`      abreviar não encurta nada
    até 999 mil          `840 Mil`    sem casa decimal: `840,3 Mil` é ruído
    de 1 milhão          `1,23 Mi`    duas casas, porque a primeira decide

O corte em 10 mil, e não em mil: `1 Mil` para 1.234 erra 19% no que a pessoa lê,
e `1.234` já cabe. Abreviação existe para caber, não por estilo.

O arredondamento é conferido depois de aplicado: 999.999 vira `1,00 Mi`, e não
`1.000 Mil` — o segundo é aritmeticamente correto e visualmente idiota.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

MIL = Decimal("1000")
MILHAO = Decimal("1000000")

#: O que se escreve quando não há número. Nunca "0" — restrição 5 do produto:
#: sem amostra, "—". Zero é uma afirmação; ausência é outra.
VAZIO = "—"


def _decimal(valor) -> Decimal | None:
    if valor is None:
        return None
    try:
        return Decimal(str(valor))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _milhar(inteiro: str) -> str:
    """`1234567` → `1.234.567`. Ponto como separador de milhar, em pt-BR."""
    partes = []
    while len(inteiro) > 3:
        partes.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    partes.insert(0, inteiro)
    return ".".join(partes)


def numero(valor, casas: int = 0) -> str:
    """`1234567.89` → `1.234.568`. Milhar com ponto, decimal com vírgula."""
    d = _decimal(valor)
    if d is None:
        return VAZIO
    quantizado = d.quantize(Decimal(1) if casas == 0 else Decimal(f"0.{'0' * casas}"))
    sinal = "-" if quantizado < 0 else ""
    texto = str(abs(quantizado))
    inteiro, _, fracao = texto.partition(".")
    formatado = _milhar(inteiro)
    if casas:
        formatado = f"{formatado},{fracao.ljust(casas, '0')}"
    return f"{sinal}{formatado}"


def moeda(valor, casas: int = 2) -> str:
    """`R$ 1.234.567,89`. O prefixo entra aqui — a tabela e o gráfico usam o mesmo."""
    d = _decimal(valor)
    if d is None:
        return VAZIO
    return f"R$ {numero(d, casas)}"


#: Abaixo disto o número por extenso já cabe, e abreviar só piora a leitura.
PISO_DA_ABREVIACAO = Decimal("10000")


def curto(valor) -> str:
    """`1.234.567` → `1,23 Mi`. É a escala do eixo, e a do rótulo por ponto."""
    d = _decimal(valor)
    if d is None:
        return VAZIO

    magnitude = abs(d)
    if magnitude >= MILHAO:
        return f"{numero(d / MILHAO, 2)} Mi"

    if magnitude >= PISO_DA_ABREVIACAO:
        milhares = (d / MIL).quantize(Decimal(1))
        # A conferência DEPOIS do arredondamento: 999.999 arredonda para 1.000
        # milhares, e `1.000 Mil` está certo na conta e errado na tela.
        if abs(milhares) >= 1000:
            return f"{numero(d / MILHAO, 2)} Mi"
        return f"{numero(milhares, 0)} Mil"

    return numero(d, 0)


def moeda_curta(valor) -> str:
    """`R$ 1,23 Mi`. O que vai em cima da barra."""
    d = _decimal(valor)
    if d is None:
        return VAZIO
    return f"R$ {curto(d)}"


def contabil_curto(valor) -> str:
    """`R$ 1,30 Mi` e `(R$ 201 Mil)` — negativo entre parênteses, como no balanço.

    É o formato da cascata: numa escada de deduções, o sinal de menos grudado
    no número (`R$ -201 Mil`) some a um metro da tela; o parêntese não.
    """
    d = _decimal(valor)
    if d is None:
        return VAZIO
    return f"(R$ {curto(abs(d))})" if d < 0 else f"R$ {curto(d)}"


def percentual(valor, casas: int = 1, com_sinal: bool = False) -> str:
    """`-7.4` → `-7,4%`. Uma casa, como no benchmark.

    `com_sinal` põe `+` no positivo. Serve para variação, onde a direção é a
    informação — e não serve para participação, onde `+30%` de um total é ruído.
    """
    d = _decimal(valor)
    if d is None:
        return VAZIO
    prefixo = "+" if com_sinal and d > 0 else ""
    return f"{prefixo}{numero(d, casas)}%"
