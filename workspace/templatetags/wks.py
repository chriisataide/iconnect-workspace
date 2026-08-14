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
def rotulo_do_campo(chave: str, item) -> str:
    """A pergunta que a pessoa respondeu, e não a chave que o banco guarda.

    `dados` é um JSON de `{chave: resposta}`, e mostrar a chave crua faria o
    resumo dizer "tecnico_responsavel" em vez de "Responsável por ele, e como
    falar com ele". Quem sabe o rótulo é o item do catálogo — que é justamente
    onde ele pode ter mudado desde que o pedido foi feito. Neste caso o rótulo
    novo é o certo: a pergunta é a mesma, só está mais bem escrita.
    """
    for campo in getattr(item, "campos", None) or []:
        if campo.get("chave") == chave:
            return campo.get("rotulo") or chave
    # Campo que saiu do catálogo depois do pedido: sem rótulo a que recorrer, a
    # chave legível é melhor que sumir com a resposta.
    return str(chave).replace("_", " ").capitalize()


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
