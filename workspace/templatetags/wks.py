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


@register.simple_tag
def estatico(caminho: str) -> str:
    """`{% static %}` com versão em desenvolvimento.

    Em produção o `ManifestStaticFilesStorage` já põe o hash no NOME do arquivo,
    e o navegador nunca serve um velho. Em desenvolvimento não há hash nenhum, e
    `/static/workspace/js/workspace.js` é a mesma URL para sempre — então o
    navegador guarda a versão da manhã e continua servindo ela à tarde.

    Isso não é teoria: uma tela inteira pareceu quebrada porque o navegador
    tinha o JS de antes do stepper existir, e o CSS de antes do `[hidden]`. O
    diagnóstico dado foi "não está funcionando", e estava — só que o código que
    rodava não era o código do disco. Hora de trabalho perdida procurando um
    defeito que não existia.

    `?v=<mtime>` resolve, custa um `stat` por tag e some sozinho em produção.
    """
    from django.conf import settings
    from django.contrib.staticfiles import finders
    from django.templatetags.static import static

    url = static(caminho)
    if not settings.DEBUG:
        return url

    caminho_no_disco = finders.find(caminho)
    if not caminho_no_disco:
        return url

    import os

    return f"{url}?v={int(os.path.getmtime(caminho_no_disco))}"


@register.filter
def dias_desde(quando) -> int:
    """Quantos dias corridos desde então.

    `timesince` do Django diria "3 dias, 4 horas", e a fila precisa do NÚMERO
    para comparar com o prazo prometido do item — "3" ao lado de "prazo: 5" se
    lê de relance; "3 dias, 4 horas" ao lado de "5 dias" não.
    """
    if not quando:
        return 0
    from django.utils import timezone

    return max(0, (timezone.now() - quando).days)


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


@register.simple_tag(takes_context=True)
def codigo_da_tela(context) -> str:
    """O código desta tela, ou vazio quando ela não tem um.

    Derivado de `request.resolver_match` e não escrito em cada template, de
    propósito: são quarenta arquivos, e o primeiro que esquecesse o código
    ficaria mudo justamente na tela que alguém tentasse endereçar. Aqui o
    cabeçalho e o registro não têm como divergir — ou a tela está em
    `enderecamento.TELAS` e o código aparece, ou não está e não aparece nada.

    Vazio é resposta legítima: rota de ação (aprovar, cancelar, baixar) não é
    lugar e não tem endereço. Ver `enderecamento.Tela`.
    """
    from workspace import enderecamento as end

    caminho = getattr(context.get("request"), "path", "")
    tela = end.por_caminho(caminho)
    return tela.codigo if tela else ""


@register.simple_tag
def produto() -> str:
    """O nome do produto, de `settings.PRODUTO_NOME`.

    Tag e não context processor porque `500.html` é renderizada **sem contexto**
    pelo handler padrão do Django — um `{{ produto_nome }}` sairia vazio
    justamente na tela que a pessoa vê quando tudo deu errado, e ela ficaria
    sem saber de que sistema é o erro.
    """
    from django.conf import settings

    return settings.PRODUTO_NOME


@register.simple_tag
def marca() -> str:
    """A empresa dona da marca — o `alt` do logo. Ver `PRODUTO_MARCA`."""
    from django.conf import settings

    return settings.PRODUTO_MARCA
