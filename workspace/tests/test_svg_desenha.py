"""Coordenada de SVG é texto ASCII com ponto — e o Django localiza número.

## O defeito que este arquivo existe para impedir

Os dois gráficos da tela de Resultados ficaram **em branco por semanas**, e
nenhum dos 3.207 testes apontou.

`LANGUAGE_CODE = "pt-br"` faz o Django renderizar `{{ 10.52 }}` como `10,52`.
Está certo numa tabela e é **inválido** num atributo de SVG: a gramática de
`x=""` é ASCII com ponto decimal. Com vírgula, o navegador descarta o `<rect>`
inteiro.

Sem exceção, sem 500, sem linha no log do servidor. O `<svg>` está no HTML, a
classe está no CSS, o teste que existia afirmava as duas coisas — e a tela
mostrava um retângulo branco de 140 pixels.

## Por que ele varre a tela renderizada, e não os arquivos

Porque o defeito não está no template: `x="{{ barra.x }}"` está correto. Ele
nasce no encontro entre um `float` e a localização, e só existe depois do render.

`workspace/services/grafico.py` corrige na origem — as coordenadas saem de lá
como string. Este teste é o que descobre o próximo SVG que não passar por lá.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from resultados.models import CompetenciaResultado, Contrato, Fonte

#: Atributos cujo valor o navegador lê como número. Um valor com vírgula neles
#: não é "meio errado": o elemento inteiro é descartado.
NUMERICOS = (
    "x", "y", "width", "height", "x1", "y1", "x2", "y2",
    "cx", "cy", "r", "rx", "ry", "offset", "stroke-width",
)

COM_VIRGULA = re.compile(
    r'\b(?:' + "|".join(NUMERICOS) + r')="[^"]*\d,\d[^"]*"'
)

#: As telas com desenho. Lista à mão e não descoberta automática: uma varredura
#: de todas as rotas erraria nas que exigem argumento, e a lista força quem
#: acrescentar um gráfico a passar por aqui.
COM_SVG = (
    "workspace:resultados",
    "workspace:aprovacoes",
    "workspace:indicadores",
    "workspace:universidade_painel",
    "workspace:orcamento",
    "workspace:home",
)


HOJE = timezone.localdate()
COMPETENCIA = HOJE.replace(day=1)


@pytest.fixture
def espelho(db):
    """O espelho COM série — e é o detalhe que faz este arquivo valer.

    Escrito depois de a primeira versão passar sem a correção: sem provedor com
    dado, a série sai vazia, o template mostra o estado vazio, e não há
    coordenada nenhuma para conferir. Um teste que passa antes e depois da
    correção não protege coisa alguma.
    """
    contrato = Contrato.objects.create(
        fonte=Fonte.PLATFORM, chave_externa="plt-C-SVG", codigo="C-SVG",
        nome_cliente="Cliente do gráfico", servico="cftv",
        centro_custo="1042", regional="Sudeste",
        inicio_vigencia=HOJE - timedelta(days=400),
        fim_vigencia=HOJE + timedelta(days=300),
        valor_mensal=Decimal("100000"),
    )
    for atras in range(6):
        total = COMPETENCIA.year * 12 + (COMPETENCIA.month - 1) - atras
        ano, mes = total // 12, total % 12 + 1
        CompetenciaResultado.objects.create(
            fonte=Fonte.SANKHYA,
            chave_externa=f"snk-C-SVG-{ano}{mes:02d}",
            contrato=contrato, centro_custo="1042", ano=ano, mes=mes,
            # Um valor que produz coordenada QUEBRADA — `10.52`, `157.49`. Com
            # números redondos a série sairia em inteiros e o defeito não
            # apareceria nem sem a correção.
            receita_bruta=Decimal("123456.78"),
            # E um EBITDA negativo, que é o que põe o zero no meio do eixo e
            # gera `linha_zero` fracionária.
            margem_contribuicao=Decimal("-4321.99"),
            ebitda=Decimal("-4321.99"),
        )
    return contrato


@pytest.fixture
def diretoria(db):
    pessoa = f.pessoa("diretor", nome="Diretor")
    f.lotar(pessoa, centro_custo_codigo="1042")
    f.atribuir(
        pessoa,
        f.papel(
            "diretoria_svg",
            [
                "eco.ler.global", "ind.ler.global", "apr.aprovar.global",
                "hab.ler.unidade", "fin.orcamento.ler.global",
            ],
            escopo="global",
        ),
        escopo="global",
    )
    return pessoa


@pytest.mark.django_db
@pytest.mark.parametrize("rota", COM_SVG)
def test_nenhum_atributo_de_svg_sai_com_virgula(client, espelho, diretoria, rota):
    """O teste que os gráficos em branco custaram.

    Ele não pergunta se o `<svg>` existe — o antigo perguntava isso, e passava.
    Ele pergunta se o navegador consegue LER o que está dentro.
    """
    client.force_login(diretoria)

    conteudo = client.get(reverse(rota)).content.decode()
    achados = COM_VIRGULA.findall(conteudo)

    assert not achados, (
        f"{rota}: {len(achados)} atributo(s) de SVG com vírgula decimal — o "
        f"navegador descarta o elemento em silêncio. Exemplos: {achados[:5]}. "
        "Formate a coordenada em Python; ver `workspace/services/grafico.py`."
    )


@pytest.mark.django_db
def test_o_grafico_de_resultados_desenha_barras_de_verdade(client, espelho, diretoria):
    """Não basta o `<rect>` existir: ele precisa ter altura maior que zero.

    Um `height="0"` é tão invisível quanto um `height="1,5"`, e sai de uma série
    toda zerada — que é um caso legítimo e precisa de estado vazio, não de um
    gráfico transparente.
    """
    from decimal import Decimal

    from workspace.services import grafico

    serie = grafico.barras(
        [("01/26", Decimal("100")), ("02/26", Decimal("-40")), ("03/26", Decimal("0"))]
    )

    assert len(serie.barras) == 3
    assert all(float(b.altura) > 0 for b in serie.barras), "barra sem altura não existe"
    assert serie.barras[1].negativa is True
    # Zero no MEIO quando há negativo, e não na base: é o que faz o EBITDA
    # negativo apontar para baixo em vez de virar uma barra minúscula para cima.
    assert 0 < float(serie.linha_zero) < grafico.ALTURA


def test_a_coordenada_sempre_usa_ponto():
    from workspace.services import grafico

    assert grafico.coordenada(10.52) == "10.52"
    assert grafico.coordenada(176.0) == "176", "sem cauda de zero"
    assert grafico.coordenada(0.5) == "0.5", "e sem arredondar para zero"
    assert "," not in grafico.coordenada(1234.56)


@pytest.mark.django_db
def test_a_serie_vazia_diz_isso_em_vez_de_desenhar_nada(client, diretoria):  # noqa: ARG001
    """Série sem ponto nenhum não vira um SVG vazio — vira uma frase.

    SVG vazio e SVG com coordenada inválida têm a MESMA aparência na tela, e
    foi por isso que o defeito da vírgula durou tanto: quem olhou concluiu "não
    tem dado".
    """
    from workspace.services import grafico

    serie = grafico.barras([])

    assert serie.vazia is True
    assert serie.barras == []
