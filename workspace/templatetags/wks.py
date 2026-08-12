"""Filtros de template do Workspace."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django import template
from django.utils import formats

register = template.Library()


@register.filter
def data_extenso(valor, com_ano: bool = True) -> str:
    """'7 de agosto de 2026' — mês em minúscula, como manda o português.

    O locale pt-BR do Django devolve os meses capitalizados ("Agosto"), o que
    está errado em português: nome de mês e dia da semana são substantivos
    comuns. `date:"F"` sozinho produz "07 de Agosto de 2026" em toda tela.
    """
    if not valor:
        return ""
    formato = "j \\d\\e F \\d\\e Y" if com_ano else "j \\d\\e F"
    return formats.date_format(valor, formato).lower()


@register.filter
def moeda(valor) -> str:
    """`12400` → `12.400,00`. Sem separador de milhar, coluna de dinheiro não
    se lê: `R$ 13720,00` exige contar dígitos.

    Não uso `intcomma` do humanize para não acrescentar app ao INSTALLED_APPS
    por um filtro, e porque humanize depende de `USE_THOUSAND_SEPARATOR`, que é
    global e afetaria telas antigas.
    """
    if valor is None or valor == "":
        return "—"
    try:
        numero = Decimal(str(valor))
    except (InvalidOperation, ValueError):
        return "—"
    # Formata em en-US (1,234.56) e troca os separadores — evita depender de
    # locale do sistema, que varia entre a máquina do dev e o contêiner.
    inteiro, _, decimais = f"{numero:,.2f}".partition(".")
    return f"{inteiro.replace(',', '.')},{decimais}"
