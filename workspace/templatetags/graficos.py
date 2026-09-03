"""As tags que põem um `Bloco` na tela — o gráfico e a tabela irmã, juntos.

Mora em `workspace/templatetags/` e não em `workspace/graficos/templatetags/`
porque o Django só descobre biblioteca de tag dentro de um app INSTALADO, e
`workspace.graficos` é um pacote, não um app. Ao lado de `wks.py`, que é onde
alguém procura.

Uma tag e não duas: um `{% grafico %}` sem `{% tabela %}` ao lado é justamente o
que o prompt proíbe, e a forma mais barata de garantir que não aconteça é não
existir jeito de pedir só metade.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()

#: O que `</script>` faria dentro de um bloco JSON: fecharia o bloco e o resto
#: viraria HTML. Django escapa isto no `json_script`; como montamos o bloco à
#: mão para pôr o nonce, o escape vem junto.
ESCAPES = {
    ord(">"): "\\u003E",
    ord("<"): "\\u003C",
    ord("&"): "\\u0026",
}


class Codificador(json.JSONEncoder):
    """`Decimal` e data não são JSON. Aqui eles viram número e texto ISO.

    `float(Decimal)` perde precisão a partir de 2^53 — e um valor de contrato não
    chega perto disso. O que NÃO pode virar float é dinheiro que volta para o
    banco; aqui ele só desenha.
    """

    def default(self, o):
        if isinstance(o, Decimal):
            return float(o)
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        return super().default(o)


@register.simple_tag(takes_context=True)
def dados_do_grafico(context, bloco):
    """O bloco de dados, com o nonce da requisição.

    `<script type="application/json">` não é executado — é dado. Ele ganha nonce
    mesmo assim: `script-src` tem nonce desde a Onda 9.5, e depender de "o
    navegador provavelmente não bloqueia bloco de dados" não é base para uma
    decisão de segurança (ADR-040).
    """
    requisicao = context.get("request")
    nonce = getattr(requisicao, "csp_nonce", "")
    corpo = json.dumps(bloco.option, cls=Codificador, ensure_ascii=False)
    return format_html(
        '<script type="application/json" id="{}" nonce="{}" '
        'data-grafico="{}">{}</script>',
        f"grafico-dados-{bloco.chave}",
        nonce,
        bloco.chave,
        mark_safe(corpo.translate(ESCAPES)),
    )


@register.inclusion_tag("graficos/_bloco.html", takes_context=True)
def grafico(context, bloco, aberta=False):
    """O gráfico E a tabela irmã.

    `aberta` abre o `<details>` da tabela por padrão. Use quando a tabela é o
    conteúdo principal e o gráfico é o resumo — na faixa financeira é o
    contrário.
    """
    return {
        "bloco": bloco,
        "aberta": aberta,
        "request": context.get("request"),
    }


@register.inclusion_tag("graficos/_farol.html")
def farol(objeto):
    """O farol — `<span>` com classe e rótulo textual.

    Tag própria e não `{% include %}` solto: o farol aparece dentro de célula de
    tabela em várias telas, e `include with` em `<td>` é onde alguém esquece o
    `with` e renderiza vazio.
    """
    return {"farol": objeto}


@register.inclusion_tag("graficos/_mapa_calor.html")
def mapa_calor(mapa):
    """A grade com faixa por célula. Sem ECharts — ver `series.MapaDeCalor`."""
    return {"mapa": mapa}
