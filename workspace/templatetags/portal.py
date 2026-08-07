"""Filtros de template do Portal."""

from __future__ import annotations

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
