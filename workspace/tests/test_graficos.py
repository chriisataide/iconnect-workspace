"""Gráficos com biblioteca — a option montada em Python e a tabela irmã.

Os que mais protegem esta onda:

1. **Todo gráfico tem tabela irmã, com os mesmos números.** Sem JavaScript o
   gráfico não existe; a tabela é o FALLBACK, e não acessibilidade.
2. **Os números vêm do servidor, formatados.** O `formatter` do ECharts é a
   string `{@rotulo}` — zero função em JS, uma implementação de pt-BR só.
3. **O bundle não é o pacote completo.** O tree-shaking corta 40%, e um `import`
   a mais desfaz isso sem ninguém notar.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.graficos import formato as fmt
from workspace.graficos import series

RAIZ = Path(__file__).resolve().parent.parent.parent
BUNDLE = RAIZ / "workspace" / "static" / "workspace" / "js" / "echarts.min.js"
TOKENS = RAIZ / "workspace" / "static" / "workspace" / "src" / "tokens.css"


@pytest.fixture
def espelho(db):
    """O espelho com série — sem ele a faixa financeira não desenha nada.

    Mesmo cuidado de `test_svg_desenha.py`: um teste de gráfico sem dado passa
    com e sem a correção, e não protege coisa alguma.
    """
    from datetime import timedelta

    from django.utils import timezone

    from resultados.models import CompetenciaResultado, Contrato, Fonte

    hoje = timezone.localdate()
    competencia = hoje.replace(day=1)
    contrato = Contrato.objects.create(
        fonte=Fonte.PLATFORM, chave_externa="plt-C-GR", codigo="C-GR",
        nome_cliente="Cliente do gráfico", servico="cftv",
        centro_custo="1042", regional="Sudeste",
        inicio_vigencia=hoje - timedelta(days=400),
        fim_vigencia=hoje + timedelta(days=300),
        valor_mensal=Decimal("100000"),
    )
    for atras in range(6):
        total = competencia.year * 12 + (competencia.month - 1) - atras
        ano, mes = total // 12, total % 12 + 1
        CompetenciaResultado.objects.create(
            fonte=Fonte.SANKHYA, chave_externa=f"snk-C-GR-{ano}{mes:02d}",
            contrato=contrato, centro_custo="1042", ano=ano, mes=mes,
            receita_bruta=Decimal("1298267.36"),
            margem_contribuicao=Decimal("-38132.23"),
            ebitda=Decimal("-96352.11"),
        )
    return contrato


@pytest.fixture
def diretoria(db):
    pessoa = f.pessoa("diretor_gr", nome="Diretor")
    f.lotar(pessoa, centro_custo_codigo="1042")
    f.atribuir(
        pessoa,
        f.papel("diretoria_graficos", ["eco.ler.global"], escopo="global"),
        escopo="global",
    )
    return pessoa


def _pontos(n=3):
    return [
        ("09/25", Decimal("1298267.36")),
        ("10/25", Decimal("-96352.11")),
        ("11/25", None),
    ][:n]


# ── 1. A tabela irmã ────────────────────────────────────────────────


def test_todo_bloco_traz_a_tabela_com_a_mesma_quantidade_de_pontos():
    """No caminho anterior a tabela era acessibilidade. Aqui ela é o FALLBACK:
    sem JS o `<div>` fica vazio, e é ela que continua respondendo."""
    bloco = series.serie_temporal(_pontos(), chave="x", titulo="Receita")

    assert len(bloco.linhas) == len(bloco.option["dataset"]["source"])
    assert len(bloco.linhas) == 3


def test_a_tabela_e_o_grafico_dizem_o_mesmo_numero(client):
    """Duas implementações da mesma regra divergem, e divergem no caso raro.

    O gráfico usa `moeda_curta` e a tabela usa `moeda` — escalas diferentes de
    propósito —, mas **o valor por trás é o mesmo objeto**, e é isso que este
    teste amarra.
    """
    bloco = series.serie_temporal(_pontos(), chave="x", titulo="Receita")
    fonte = bloco.option["dataset"]["source"]

    for indice, (mes, valor) in enumerate(_pontos()):
        assert fonte[indice][0] == mes == bloco.linhas[indice][0]
        assert fonte[indice][2] == fmt.moeda_curta(valor)
        assert bloco.linhas[indice][1] == fmt.moeda(valor)


def test_a_tabela_irma_sai_aberta_no_html(client, espelho, diretoria):
    """`open` no HTML e o JS fecha depois de desenhar.

    Escrever `open` condicionalmente deixaria a tabela fechada para quem não tem
    JavaScript — que é exatamente quem depende dela.
    """
    client.force_login(diretoria)

    html = client.get(reverse("workspace:resultados")).content.decode()

    aberturas = re.findall(r'<details class="au-gr-tabela"[^>]*\bopen\b', html)
    assert len(aberturas) >= 2, "toda tabela irmã nasce aberta"


def test_nenhum_grafico_sai_sem_tabela(client, espelho, diretoria):
    """A tag renderiza os dois juntos e não há como pedir metade — é a forma
    mais barata de garantir que a regra não seja esquecida."""
    client.force_login(diretoria)

    html = client.get(reverse("workspace:resultados")).content.decode()

    telas = re.findall(r'data-grafico-tela="([^"]+)"', html)
    tabelas = re.findall(r'data-grafico-tabela="([^"]+)"', html)
    assert telas, "a tela precisa ter gráfico para o teste valer"
    assert set(telas) == set(tabelas)


# ── 2. Os números vêm do servidor ───────────────────────────────────


def test_o_formatador_e_string_e_nao_funcao():
    """`{@dimensão}` é resolvido pelo ECharts contra o dado bruto — conferido no
    fonte da 6.1.0, `lib/model/mixin/dataFormat.js`.

    Se isto virar uma função em JS, a formatação pt-BR passa a existir em dois
    lugares: aqui e lá. E a tabela irmã usa a daqui.
    """
    bloco = series.serie_temporal(_pontos(), chave="x", titulo="Receita")
    rotulo = bloco.option["series"][0]["label"]

    assert rotulo["show"] is True
    assert rotulo["formatter"] == "{@rotulo}"
    assert "rotulo" in bloco.option["dataset"]["dimensions"]


def test_a_option_serializa_em_json_com_decimal_e_data(client, espelho, diretoria):
    """`Decimal` não é JSON. Um `TypeError` aqui derruba a tela inteira."""
    client.force_login(diretoria)

    html = client.get(reverse("workspace:resultados")).content.decode()
    blocos = re.findall(
        r'<script type="application/json" id="grafico-dados-[^"]+"[^>]*>(.*?)</script>',
        html, re.S,
    )

    assert blocos
    for corpo in blocos:
        option = json.loads(corpo)
        assert option["dataset"]["source"]


def test_o_bloco_de_dados_leva_o_nonce_da_requisicao(client, espelho, diretoria):
    """`<script type="application/json">` não executa — é dado. Ele ganha nonce
    mesmo assim: depender de "o navegador provavelmente não bloqueia bloco de
    dados" não é base para decisão de segurança (ADR-040)."""
    client.force_login(diretoria)

    resposta = client.get(reverse("workspace:resultados"))
    html = resposta.content.decode()
    nonce = resposta.wsgi_request.csp_nonce

    assert f'nonce="{nonce}"' in html
    assert re.search(
        r'<script type="application/json" id="grafico-dados-[^"]+" nonce="[^"]+"',
        html,
    )


def test_o_json_escapa_fecha_script():
    """`</script>` dentro do bloco fecharia o bloco, e o resto viraria HTML."""
    from django.template import Context, Template

    class BlocoFalso:
        chave = "x"
        option = {"titulo": "</script><img onerror=alert(1)>"}

    saida = Template(
        "{% load graficos %}{% dados_do_grafico bloco %}"
    ).render(Context({"bloco": BlocoFalso(), "request": None}))

    assert "</script><img" not in saida
    assert "\\u003C" in saida


def test_valor_ausente_nao_vira_zero():
    """Mês sem dado entra no eixo, fica sem barra, e a tabela escreve "—".

    Zero é uma afirmação; ausência é outra — restrição 5, no gráfico.
    """
    bloco = series.serie_temporal(
        [("01/26", Decimal("100")), ("02/26", None)], chave="x", titulo="t"
    )

    assert bloco.option["dataset"]["source"][1][1] is None
    assert bloco.linhas[1][1] == fmt.VAZIO
    assert bloco.linhas[1][1] != "0"


# ── 3. O bundle ─────────────────────────────────────────────────────


def test_o_bundle_existe_e_esta_versionado():
    """O artefato vai versionado para que o deploy e o CI nunca precisem de Node
    — a mesma razão pela qual o PDF não usa ECharts SSR (ADR-041)."""
    assert BUNDLE.exists(), "rode `npm run build` em build/echarts/"


def test_o_bundle_nao_e_o_pacote_completo():
    """O tree-shaking corta 40%, e um `import` a mais desfaz isso em silêncio.

    O teto é generoso de propósito: ele não existe para vigiar quilobytes, e sim
    para reprovar o dia em que alguém trocar o build customizado por
    `import * from "echarts"`, que passa de 1 MB.
    """
    kb = BUNDLE.stat().st_size / 1024

    assert kb < 800, f"o bundle tem {kb:.0f} KB — o pacote completo tem 1.095"
    assert kb > 200, "pequeno demais para conter os seis tipos de gráfico"


def test_a_entrada_do_build_nao_importa_o_pacote_completo():
    """O guard do tree-shaking, na ENTRADA e não no minificado.

    Procurar nomes de série no bundle não funciona: o núcleo do ECharts tem uma
    camada de compatibilidade que cita `sunburst` e `sankey` em texto mesmo sem
    o gráfico entrar. Foi o que este teste descobriu ao reprovar por engano.

    O que se pode afirmar com precisão é o que está escrito na entrada: importar
    de `"echarts"` puxa o pacote inteiro; importar de `"echarts/core"` e
    `"echarts/charts"` é o caminho com tree-shaking.
    """
    entrada = (RAIZ / "build" / "echarts" / "entrada.js").read_text(encoding="utf-8")

    assert 'from "echarts/core"' in entrada
    assert 'from "echarts"' not in entrada, (
        "importar de `echarts` traz o pacote completo — 1.095 KB"
    )
    assert 'from "echarts/renderers"' in entrada

    # Só as linhas de import, e não o arquivo inteiro: o comentário do arquivo
    # explica por que o canvas ficou de fora, e citar o nome não é importá-lo.
    imports = "\n".join(
        linha for linha in entrada.splitlines() if linha.strip().startswith("import")
    )
    assert "CanvasRenderer" not in imports, "só o SVGRenderer entra no bundle"
    assert "SVGRenderer" in imports


def test_o_js_pede_o_renderizador_svg_na_inicializacao():
    """Canvas não dá texto selecionável, não tem árvore de acessibilidade e
    piora o PDF. Ele custa 7 KB a MENOS — a escolha é de qualidade, não de peso.
    """
    js = (
        RAIZ / "workspace" / "static" / "workspace" / "js" / "echarts-adb.js"
    ).read_text(encoding="utf-8")

    assert 'renderer: "svg"' in js


def test_o_bundle_so_carrega_nas_telas_com_grafico(client, espelho, diretoria):
    """217 KB comprimidos é caro demais para a home, o catálogo e as reservas,
    que não desenham nada."""
    client.force_login(diretoria)

    com = client.get(reverse("workspace:resultados")).content.decode()
    sem = client.get(reverse("workspace:home")).content.decode()

    assert "echarts.min.js" in com
    assert "echarts.min.js" not in sem


# ── As cores e o formato ────────────────────────────────────────────


def test_toda_cor_do_grafico_existe_nos_tokens():
    """As cores são literais na option — `var(--au-…)` não resolve em atributo
    de SVG. A duplicação é deliberada, e este teste é o que a amarra."""
    tokens = TOKENS.read_text(encoding="utf-8").lower()

    for nome in dir(series):
        if not nome.startswith("COR_"):
            continue
        valor = getattr(series, nome)
        if valor == "#ffffff":
            continue
        assert valor.lower() in tokens, f"{nome}={valor} não existe em tokens.css"


@pytest.mark.parametrize(
    "valor,esperado",
    [
        (1298267.36, "R$ 1,30 Mi"),
        (-96352.11, "R$ -96 Mil"),
        (1234, "R$ 1.234"),
        (9999, "R$ 9.999"),
        (10000, "R$ 10 Mil"),
        # O arredondamento conferido DEPOIS: 999.999 vira `1,00 Mi`, e não
        # `1.000 Mil`, que está certo na conta e errado na tela.
        (999999, "R$ 1,00 Mi"),
        (0, "R$ 0"),
        (None, "—"),
    ],
)
def test_a_escala_curta_segue_o_benchmark(valor, esperado):
    assert fmt.moeda_curta(valor) == esperado


def test_o_percentual_tem_uma_casa_e_sinal_opcional():
    assert fmt.percentual(-7.4) == "-7,4%"
    assert fmt.percentual(2.9, com_sinal=True) == "+2,9%"
    assert fmt.percentual(2.9) == "2,9%"
    assert fmt.percentual(None) == "—"


def test_a_moeda_usa_ponto_no_milhar_e_virgula_no_decimal():
    assert fmt.moeda(Decimal("1298267.36")) == "R$ 1.298.267,36"
    assert fmt.moeda(Decimal("-38132.23")) == "R$ -38.132,23"


# ── Casos de borda ──────────────────────────────────────────────────


def test_serie_de_um_ponto_mostra_o_ponto():
    """Um ponto não é tendência — mas some se o gráfico decidir não desenhar."""
    bloco = series.serie_temporal([("09/25", Decimal("100"))], chave="x", titulo="t")

    assert len(bloco.option["dataset"]["source"]) == 1
    assert len(bloco.linhas) == 1


def test_serie_vazia_nao_gera_option_com_eixo():
    """Sem ponto nenhum não se desenha eixo com escala inventada: a tela diz que
    não há série."""
    bloco = series.serie_temporal([], chave="x", titulo="t")

    assert bloco.option == {}
    assert bloco.vazio is True


def test_serie_vazia_diz_isso_na_tela(client, espelho, diretoria):
    from django.template import Context, Template

    bloco = series.serie_temporal([], chave="x", titulo="Receita")
    saida = Template("{% load graficos %}{% grafico bloco %}").render(
        Context({"bloco": bloco, "request": None})
    )

    assert "Sem série" in saida
    assert "Não é zero" in saida
    assert "data-grafico-tela" not in saida


def test_serie_com_negativo_nao_fixa_o_minimo_do_eixo():
    """Com `min` fixado, o zero iria para a base e o EBITDA negativo viraria uma
    barra minúscula para cima. Sem ele, o ECharts põe o zero no meio."""
    bloco = series.serie_temporal(
        [("01/26", Decimal("100")), ("02/26", Decimal("-40"))], chave="x", titulo="t"
    )

    assert "min" not in bloco.option["yAxis"]


def test_serie_com_negativo_muda_a_posicao_do_rotulo():
    """Com `position: top`, o rótulo do valor negativo cai dentro do eixo."""
    so_positivo = series.serie_temporal(
        [("01/26", Decimal("100"))], chave="a", titulo="t"
    )
    com_negativo = series.serie_temporal(
        [("01/26", Decimal("100")), ("02/26", Decimal("-40"))], chave="b", titulo="t"
    )

    assert so_positivo.option["series"][0]["label"]["position"] == "top"
    assert com_negativo.option["series"][0]["label"]["position"] == "inside"


def test_o_resumo_em_texto_diz_o_assunto_e_os_extremos():
    """`aria.enabled` do ECharts descreve a ESTRUTURA. Isto descreve o assunto,
    que é o que interessa a quem não vê."""
    bloco = series.serie_temporal(_pontos(), chave="x", titulo="Receita")

    assert "Receita" in bloco.resumo
    assert "Maior em 09/25" in bloco.resumo
    assert "tabela abaixo" in bloco.resumo


def test_a_acessibilidade_nativa_do_echarts_esta_ligada():
    bloco = series.serie_temporal(_pontos(), chave="x", titulo="t")

    assert bloco.option["aria"]["enabled"] is True


# ── barras_comparadas — o tipo 1 do catálogo ────────────────────────


def test_barras_comparadas_poe_a_linha_em_eixo_proprio():
    """A linha quase sempre é percentual, e um percentual no eixo de reais some."""
    bloco = series.barras_comparadas(
        [("01/26", Decimal("100"), Decimal("80")),
         ("02/26", Decimal("120"), Decimal("90"))],
        chave="x", titulo="t", rotulo_a="Realizado", rotulo_b="Orçado",
        rotulo_linha="%RExOR", linha=[Decimal("125"), Decimal("133")],
    )

    linha = bloco.option["series"][2]
    assert linha["type"] == "line"
    assert linha["yAxisIndex"] == 1
    assert len(bloco.option["yAxis"]) == 2


def test_barras_comparadas_sem_linha_nao_inventa_a_serie():
    bloco = series.barras_comparadas(
        [("01/26", Decimal("100"), Decimal("80"))],
        chave="x", titulo="t", rotulo_a="A", rotulo_b="B",
    )

    assert len(bloco.option["series"]) == 2
    assert len(bloco.colunas) == 3


def test_barras_comparadas_tem_legenda_com_nome_escrito():
    """Cor nunca sozinha: cada série tem nome escrito, e não só um quadradinho."""
    bloco = series.barras_comparadas(
        [("01/26", Decimal("100"), Decimal("80"))],
        chave="x", titulo="t", rotulo_a="Realizado", rotulo_b="Orçado",
    )

    assert bloco.option["legend"]["bottom"] == 0
    assert [s["name"] for s in bloco.option["series"]] == ["Realizado", "Orçado"]
