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
from workspace.services import resultados

RAIZ = Path(__file__).resolve().parent.parent.parent
BUNDLE = RAIZ / "workspace" / "static" / "workspace" / "js" / "echarts.min.js"
TOKENS = RAIZ / "workspace" / "static" / "workspace" / "src" / "tokens.css"


@pytest.fixture
def espelho(db):
    """O espelho com série — e com o que os testes precisam PROVAR.

    Treze meses, dois serviços e **receita orçada preenchida**. A primeira
    versão tinha seis meses, um serviço e nenhum orçado: os testes da janela, do
    filtro e da linha de percentual passavam sem provar nada, porque não havia
    o que estreitar nem o que comparar.

    Cenário pobre é a forma mais silenciosa de um teste não proteger.
    """
    from datetime import timedelta

    from django.utils import timezone

    from resultados.models import CompetenciaResultado, Contrato, Fonte

    hoje = timezone.localdate()
    competencia = hoje.replace(day=1)

    def _contrato(codigo, servico):
        # `layer` é DERIVADA do ROB pelo espelho — não é campo do contrato. Por
        # isso este cenário não a fixa: o filtro de layer é exercitado pela
        # tradução em `_estreitar_por_atributo`, e não por um valor plantado.
        return Contrato.objects.create(
            fonte=Fonte.PLATFORM, chave_externa=f"plt-{codigo}", codigo=codigo,
            nome_cliente=f"Cliente {codigo}", servico=servico,
            centro_custo="1042", regional="Sudeste",
            inicio_vigencia=hoje - timedelta(days=800),
            fim_vigencia=hoje + timedelta(days=300),
            valor_mensal=Decimal("100000"),
        )

    contratos = [_contrato("C-CFTV", "cftv"), _contrato("C-ALAR", "alarme")]

    # Treze meses, para a janela ter o que estreitar.
    for atras in range(13):
        total = competencia.year * 12 + (competencia.month - 1) - atras
        ano, mes = total // 12, total % 12 + 1
        for contrato in contratos:
            CompetenciaResultado.objects.create(
                fonte=Fonte.SANKHYA,
                chave_externa=f"snk-{contrato.codigo}-{ano}{mes:02d}",
                contrato=contrato, centro_custo="1042", ano=ano, mes=mes,
                receita_bruta=Decimal("1298267.36"),
                # ORÇADO preenchido: sem ele não há segunda barra nem linha de
                # percentual, e os testes da faixa comparada passariam vazios.
                receita_orcada=Decimal("1200000.00"),
                margem_contribuicao=Decimal("-38132.23"),
                ebitda=Decimal("-96352.11"),
            )
    return contratos


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
        # `dataset` OU `series[].data`: a série temporal e a comparada usam
        # `dataset` com dimensões nomeadas, e a rosca, o bullet e a dispersão
        # levam o dado no próprio item — a segunda forma é a que aceita cor e
        # tamanho por ponto. Exigir só a primeira reprovaria os tipos novos.
        tem_dado = bool(option.get("dataset", {}).get("source")) or any(
            s.get("data") for s in option.get("series", [])
        )
        assert tem_dado, "option serializada sem dado nenhum"


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
        rotulo_linha="% do orçado", linha=[Decimal("125"), Decimal("133")],
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


# ── O rótulo girado — a sobreposição ────────────────────────────────


def test_o_rotulo_do_ponto_e_girado():
    """Na horizontal, `R$ 1,19 Mi` mede mais que a largura de uma barra de
    treze — e os rótulos viram uma mancha. Foi o que aconteceu na primeira
    versão desta onda, e o que o Portal GPS resolve girando o texto."""
    bloco = series.serie_temporal(_pontos(), chave="x", titulo="t")

    assert bloco.option["series"][0]["label"]["rotate"] == 90


def test_o_que_nao_cabe_some_em_vez_de_transbordar():
    """Barra baixa demais para o texto fica SEM rótulo. O número continua na
    tabela irmã, que é onde se confere."""
    bloco = series.serie_temporal(_pontos(), chave="x", titulo="t")

    assert bloco.option["series"][0]["labelLayout"]["hideOverlap"] is True


def test_nas_barras_comparadas_o_rotulo_vai_dentro_da_barra():
    """Com duas séries lado a lado e treze meses, rótulo em cima não cabe de
    jeito nenhum."""
    bloco = series.barras_comparadas(
        [("01/26", Decimal("100"), Decimal("80"))],
        chave="x", titulo="t", rotulo_a="A", rotulo_b="B",
    )

    for serie in bloco.option["series"][:2]:
        assert serie["label"]["rotate"] == 90
        assert serie["label"]["position"] == "insideBottom"


def test_o_percentual_da_linha_nao_gira():
    """Ele é curto, e é a leitura principal do bloco — no benchmark ele aparece
    numa etiqueta escura sobre a linha."""
    bloco = series.barras_comparadas(
        [("01/26", Decimal("100"), Decimal("80"))],
        chave="x", titulo="t", rotulo_a="A", rotulo_b="B",
        rotulo_linha="%", linha=[Decimal("125")],
    )
    linha = bloco.option["series"][2]["label"]

    assert "rotate" not in linha
    assert linha["backgroundColor"] == series.COR_LINHA


# ── A faixa do dinheiro ─────────────────────────────────────────────


def test_a_faixa_do_dinheiro_compara_realizado_com_orcado(client, espelho, diretoria):
    """Dois números lado a lado dizem quanto; a razão entre eles diz se está
    onde deveria — e é a primeira coisa que alguém procura na reunião."""
    client.force_login(diretoria)

    html = client.get(reverse("workspace:resultados")).content.decode()
    corpo = re.search(
        r'id="grafico-dados-receita"[^>]*>(.*?)</script>', html, re.S
    ).group(1)
    option = json.loads(corpo)

    assert [s["name"] for s in option["series"]] == ["Realizado", "Orçado", "% do orçado"]
    assert option["series"][2]["yAxisIndex"] == 1


def test_mes_sem_orcado_nao_vira_ponto_em_zero_na_linha():
    """Um ponto em zero seria lido como "não cumpriu nada" — e o que houve foi
    ninguém ter orçado."""
    from workspace.services import resultados as svc

    class Linha:
        def __init__(self, mes, re_, or_):
            self.ano, self.mes = 2026, mes
            self.receita_bruta, self.receita_orcada = re_, or_

    bloco = svc._bloco_comparado(
        [Linha(1, Decimal("100"), Decimal("80")), Linha(2, Decimal("100"), None)],
        "receita_bruta", "receita_orcada", "x", "t",
    )
    fonte = bloco.option["dataset"]["source"]

    assert fonte[0][3] is not None
    assert fonte[1][2] is None, "sem orçado, sem barra clara"
    assert fonte[1][3] is None, "sem orçado, sem ponto na linha"


def test_o_ebitda_nao_ganha_par_inventado(client, espelho, diretoria):
    """O espelho não traz EBITDA orçado. Inventar um denominador para ter a
    linha seria a pior forma de completar um gráfico."""
    client.force_login(diretoria)

    html = client.get(reverse("workspace:resultados")).content.decode()
    corpo = re.search(
        r'id="grafico-dados-ebitda"[^>]*>(.*?)</script>', html, re.S
    ).group(1)
    option = json.loads(corpo)

    assert len(option["series"]) == 1


# ── Os filtros ──────────────────────────────────────────────────────


def test_a_janela_estreita_a_serie(client, espelho, diretoria):
    """A outra metade da sobreposição: girar o rótulo resolveu uma, e poder
    estreitar a janela é a que a pessoa controla."""
    client.force_login(diretoria)

    def pontos(query):
        html = client.get(
            reverse("workspace:resultados") + query
        ).content.decode()
        corpo = re.search(
            r'id="grafico-dados-receita"[^>]*>(.*?)</script>', html, re.S
        ).group(1)
        return len(json.loads(corpo)["dataset"]["source"])

    assert pontos("") == 13
    assert pontos("?janela=6") == 6
    assert pontos("?janela=3") == 3


def test_a_janela_tem_piso_e_teto(client, espelho, diretoria):
    """Três é o mínimo em que uma tendência existe. E `?janela=999` é uma URL
    digitada errada, não um ataque."""
    from workspace.services import resultados as svc

    assert svc.ler_filtros({"janela": "1"}).meses == 3
    assert svc.ler_filtros({"janela": "999"}).meses == svc.MESES_DA_SERIE
    assert svc.ler_filtros({"janela": "abacaxi"}).meses == svc.MESES_DA_SERIE


def test_o_filtro_de_servico_move_o_grafico_do_dinheiro(client, espelho, diretoria):
    """Duas faixas discordando sobre o mesmo filtro, na mesma tela, é o defeito
    que faz alguém deixar de confiar no número — e ele não dá erro."""
    client.force_login(diretoria)

    def total(query):
        html = client.get(
            reverse("workspace:resultados") + query
        ).content.decode()
        achado = re.search(
            r'id="grafico-dados-receita"[^>]*>(.*?)</script>', html, re.S
        )
        if not achado:
            return 0
        fonte = json.loads(achado.group(1))["dataset"]["source"]
        return sum(p[1] or 0 for p in fonte)

    inteiro = total("")
    recortado = total("?servico=cftv")

    assert inteiro > 0
    assert recortado < inteiro, "o filtro não chegou ao gráfico"


def test_filtro_sem_nenhum_contrato_mostra_vazio_e_nao_tudo(client, espelho, diretoria):
    """Tupla vazia em `Escopo` significa "a empresa inteira". Um filtro que não
    casa com nada precisa dizer "nada", e não "tudo"."""
    from workspace.services import resultados as svc
    from workspace.providers import resultados as contrato_res

    recorte = svc._estreitar_por_atributo(
        contrato_res.Escopo(), svc.ler_filtros({"servico": "nao-existe"})
    )

    assert recorte.contratos == ("",)


def test_o_seletor_de_servico_so_oferece_o_que_existe(client, espelho, diretoria):
    """Uma opção que não devolve linha nenhuma é pior que a ausência dela."""
    client.force_login(diretoria)

    contexto = client.get(reverse("workspace:resultados")).context

    assert contexto["servicos"], "o espelho tem serviço, o seletor precisa listar"
    assert all(isinstance(s, str) and s for s in contexto["servicos"])


# ── O resto do catálogo ─────────────────────────────────────────────


def test_a_cascata_usa_uma_base_transparente():
    """O ECharts não tem série de cascata. A receita é barra EMPILHADA com uma
    série de base transparente: a base sobe até onde o passo começa."""
    bloco = series.cascata(
        [("Conquistas", Decimal("300")), ("Perdas", Decimal("-120"))],
        chave="x", titulo="Movimento", inicial=Decimal("1000"),
    )
    base, passos = bloco.option["series"]

    assert base["itemStyle"]["color"] == "transparent"
    assert base["stack"] == passos["stack"]
    assert base["silent"] is True


def test_a_cascata_desce_a_base_no_passo_negativo():
    """Numa queda a base fica no valor de CHEGADA, e o bloco visível sobe até o
    de partida. Com a base no de partida, a barra sairia do gráfico."""
    bloco = series.cascata(
        [("Perdas", Decimal("-120"))], chave="x", titulo="t", inicial=Decimal("1000")
    )
    bases = bloco.option["series"][0]["data"]

    # [início=0, passo=880, final=0]
    assert bases[1] == 880.0


def test_a_cascata_fecha_no_acumulado():
    bloco = series.cascata(
        [("A", Decimal("300")), ("B", Decimal("-120"))],
        chave="x", titulo="t", inicial=Decimal("1000"),
    )

    assert bloco.linhas[-1][2] == fmt.moeda(Decimal("1180"))


def test_a_cascata_pinta_ganho_e_perda_e_escreve_o_valor():
    """Cor nunca sozinha: verde e vermelho, com o número dentro da barra."""
    bloco = series.cascata(
        [("A", Decimal("300")), ("B", Decimal("-120"))], chave="x", titulo="t"
    )
    dados = bloco.option["series"][1]["data"]

    assert dados[0]["itemStyle"]["color"] == series.COR_POSITIVO
    assert dados[1]["itemStyle"]["color"] == series.COR_NEGATIVO
    assert dados[1]["rotulo"] == fmt.moeda_curta(Decimal("-120"))


def test_a_barra_de_composicao_e_uma_categoria_so():
    bloco = series.barra_composicao(
        [("cftv", Decimal("300")), ("alarme", Decimal("100"))],
        chave="x", titulo="Mix",
    )

    assert bloco.option["yAxis"]["data"] == [""]
    assert len(bloco.option["series"]) == 2
    assert all(s["stack"] == "total" for s in bloco.option["series"])


def test_a_composicao_calcula_a_participacao_na_tabela():
    bloco = series.barra_composicao(
        [("cftv", Decimal("300")), ("alarme", Decimal("100"))],
        chave="x", titulo="Mix",
    )

    assert bloco.linhas[0][2] == "75,0%"
    assert bloco.linhas[1][2] == "25,0%"


def test_a_empilhada_escreve_o_valor_absoluto_no_segmento():
    """Empilhada percentual mostra proporção e ESCONDE tamanho: duas linhas de
    100% parecem iguais quando uma vale dez e a outra dez mil."""
    bloco = series.empilhada_percentual(
        ["Sudeste", "Sul"],
        [("cftv", [Decimal("10"), Decimal("10000")])],
        chave="x", titulo="t",
    )
    dados = bloco.option["series"][0]["data"]

    assert dados[0]["rotulo"] == fmt.curto(Decimal("10"))
    assert dados[1]["rotulo"] == fmt.curto(Decimal("10000"))
    assert bloco.option["series"][0]["label"]["position"] == "inside"


def test_a_rosca_tem_buraco_e_o_total_no_centro():
    """Rosca e não pizza: o buraco é onde mora o total, e é ele que responde a
    primeira pergunta."""
    bloco = series.rosca(
        [("cftv", Decimal("300")), ("alarme", Decimal("100"))],
        chave="x", titulo="Mix",
    )

    assert bloco.option["series"][0]["radius"] == ["55%", "75%"]
    assert bloco.option["title"]["text"] == fmt.moeda_curta(Decimal("400"))


def test_o_medidor_tem_faixas_com_nome_e_quantidade():
    """Um medidor diz onde a média caiu e esconde a distribuição. Média 78 com
    metade abaixo de 50 é outra conversa."""
    bloco = series.medidor(
        Decimal("78"), chave="x", titulo="Score",
        quantidade_por_faixa={"crítico": 4, "atenção": 9, "bom": 12},
    )

    assert len(bloco.option["series"][0]["axisLine"]["lineStyle"]["color"]) == 3
    assert [linha[1] for linha in bloco.linhas] == ["4", "9", "12"]
    assert all(
        nome in linha[0]
        for nome, linha in zip(("crítico", "atenção", "bom"), bloco.linhas)
    )


def test_o_medidor_sem_amostra_nao_aponta_para_zero():
    """Um ponteiro em zero seria lido como nota zero."""
    bloco = series.medidor(
        None, chave="x", titulo="Score", quantidade_por_faixa={"bom": 0}
    )

    assert bloco.option["series"][0]["pointer"]["show"] is False
    assert bloco.option["series"][0]["detail"]["formatter"] == "—"


def test_o_bullet_marca_a_meta_e_escreve_se_atingiu():
    """A `markLine` é a leitura "passou ou não passou" sem ler número. A palavra
    fica na tabela, porque quem lê a tabela não vê a linha."""
    bloco = series.bullet(
        [("Sudeste", Decimal("120"), Decimal("100")),
         ("Sul", Decimal("80"), Decimal("100"))],
        chave="x", titulo="t",
    )
    marcas = bloco.option["series"][0]["markLine"]["data"]

    assert len(marcas) == 2
    assert [linha[3] for linha in bloco.linhas] == ["sim", "não"]


def test_o_bullet_calcula_a_altura_pela_quantidade():
    """Três itens com 260px de altura viram três tarjas gordas separadas por
    vazio."""
    dois = series.bullet(
        [("a", Decimal("1"), Decimal("1")), ("b", Decimal("1"), Decimal("1"))],
        chave="x", titulo="t",
    )
    seis = series.bullet(
        [(str(i), Decimal("1"), Decimal("1")) for i in range(6)], chave="y", titulo="t"
    )

    assert seis.altura > dois.altura


def test_a_dispersao_dimensiona_o_ponto_pelo_valor():
    """Sem piso, o contrato pequeno vira um ponto que ninguém acha; sem teto, o
    maior cobre os vizinhos."""
    bloco = series.dispersao(
        [("CT-1", Decimal("100"), Decimal("12"), Decimal("10")),
         ("CT-2", Decimal("900"), Decimal("3"), Decimal("100"))],
        chave="x", titulo="t",
    )
    tamanhos = [p["symbolSize"] for p in bloco.option["series"][0]["data"]]

    assert min(tamanhos) >= 8
    assert max(tamanhos) <= 34
    assert tamanhos[1] > tamanhos[0]


def test_a_dispersao_desenha_o_limiar_quando_existe():
    """Sem a linha da margem mínima, o quadrante que importa — grande e pouco
    rentável — não tem fronteira visível."""
    com = series.dispersao(
        [("CT-1", Decimal("100"), Decimal("12"), Decimal("10"))],
        chave="x", titulo="t", limiar_y=Decimal("10"),
    )
    sem = series.dispersao(
        [("CT-1", Decimal("100"), Decimal("12"), Decimal("10"))],
        chave="y", titulo="t",
    )

    assert com.option["series"][0]["markLine"]["data"] == [{"yAxis": 10.0}]
    assert sem.option["series"][0]["markLine"]["data"] == []


@pytest.mark.parametrize(
    "tipo,argumentos",
    [
        ("cascata", {"passos": []}),
        ("barra_composicao", {"partes": []}),
        ("rosca", {"fatias": []}),
        ("bullet", {"itens": []}),
        ("dispersao", {"pontos": []}),
    ],
)
def test_todo_tipo_vazio_devolve_bloco_sem_option(tipo, argumentos):
    """Sem ponto nenhum não se desenha eixo com escala inventada."""
    bloco = getattr(series, tipo)(chave="x", titulo="t", **argumentos)

    assert bloco.option == {}
    assert bloco.vazio is True


def test_todo_tipo_do_catalogo_traz_tabela_irma():
    """A regra que não muda com o tipo. Um `Bloco` sem `linhas` é um gráfico sem
    fallback, e sem JS ele não existe."""
    casos = [
        series.serie_temporal([("01/26", Decimal("1"))], chave="a", titulo="t"),
        series.barras_comparadas(
            [("01/26", Decimal("1"), Decimal("2"))], chave="b", titulo="t",
            rotulo_a="A", rotulo_b="B",
        ),
        series.cascata([("A", Decimal("1"))], chave="c", titulo="t"),
        series.barra_composicao([("A", Decimal("1"))], chave="d", titulo="t"),
        series.empilhada_percentual(["X"], [("A", [Decimal("1")])], chave="e", titulo="t"),
        series.rosca([("A", Decimal("1"))], chave="f", titulo="t"),
        series.medidor(Decimal("50"), chave="g", titulo="t"),
        series.bullet([("A", Decimal("1"), Decimal("1"))], chave="h", titulo="t"),
        series.dispersao(
            [("A", Decimal("1"), Decimal("1"), Decimal("1"))], chave="i", titulo="t"
        ),
    ]

    for bloco in casos:
        assert bloco.linhas, f"{bloco.chave} não tem tabela irmã"
        assert bloco.colunas, f"{bloco.chave} não tem cabeçalho de tabela"
        assert bloco.resumo, f"{bloco.chave} não tem resumo para o aria-label"


# ── Farol e mapa de calor: os que NÃO são gráfico ───────────────────


def test_o_farol_sem_amostra_e_cinza_e_nao_vermelho():
    """Pintar de vermelho o que ninguém mediu manda alguém correr atrás do
    problema errado: ausência de caso não é o pior caso."""
    f_ = series.farol(None, critico=Decimal("5"), atencao=Decimal("10"))

    assert f_.situacao == series.FAROL_INDEFINIDO
    assert f_.rotulo == "sem amostra"
    assert f_.valor == fmt.VAZIO


def test_o_farol_inverte_quando_menor_e_melhor():
    """Turnover, absenteísmo, custo. Sem a inversão, quem perdeu metade da
    equipe apareceria em verde."""
    turnover = series.farol(
        Decimal("8.4"), critico=Decimal("5"), atencao=Decimal("3"),
        maior_melhor=False,
    )
    margem = series.farol(Decimal("8.4"), critico=Decimal("5"), atencao=Decimal("10"))

    assert turnover.situacao == series.FAROL_CRITICO
    assert margem.situacao == series.FAROL_ATENCAO


def test_o_farol_sempre_tem_rotulo_textual():
    """Cor nunca sozinha — e num farol a cor é a única coisa que existe."""
    for situacao in (series.FAROL_BOM, series.FAROL_ATENCAO, series.FAROL_CRITICO):
        assert series.ROTULO_DO_FAROL[situacao]


def test_o_farol_renderiza_o_rotulo_ao_lado_da_marca():
    from django.template import Context, Template

    saida = Template("{% load graficos %}{% farol objeto %}").render(
        Context({"objeto": series.farol(Decimal("2"), critico=Decimal("5"), atencao=Decimal("10"))})
    )

    assert "au-farol--critico" in saida
    assert "crítico" in saida, "o texto ao lado da cor"
    assert "2,0%" in saida


def test_o_mapa_de_calor_e_tabela_e_nao_grafico():
    """Menor, legível sem JavaScript, e com o número selecionável — que é o que
    uma grade de score existe para permitir."""
    from django.template import Context, Template

    mapa = series.mapa_calor_tabela(
        ["jan", "fev"],
        [("CT-100", [Decimal("12"), Decimal("3")])],
        chave="x", titulo="Score", critico=Decimal("5"), atencao=Decimal("10"),
    )
    saida = Template("{% load graficos %}{% mapa_calor mapa %}").render(
        Context({"mapa": mapa})
    )

    assert "<table" in saida
    assert "data-grafico-tela" not in saida, "não é gráfico: não inicializa nada"
    assert "au-calor-celula--bom" in saida
    assert "au-calor-celula--critico" in saida
    # A cor é reforço: o número está escrito na célula.
    assert "12,0%" in saida
    # E a legenda NOMEIA as faixas.
    assert "atenção" in saida


def test_o_mapa_de_calor_vazio_diz_isso():
    from django.template import Context, Template

    mapa = series.mapa_calor_tabela(
        [], [], chave="x", titulo="Score", critico=Decimal("5"), atencao=Decimal("10")
    )
    saida = Template("{% load graficos %}{% mapa_calor mapa %}").render(
        Context({"mapa": mapa})
    )

    assert mapa.vazio is True
    assert "Não é zero" in saida


def test_o_bundle_nao_carrega_o_heatmap():
    """O mapa de calor virou tabela; manter a série no bundle traria 45 KB que
    nada desenha."""
    entrada = (RAIZ / "build" / "echarts" / "entrada.js").read_text(encoding="utf-8")
    imports = "\n".join(
        linha for linha in entrada.splitlines() if linha.strip().startswith("import")
    )

    assert "HeatmapChart" not in imports
    assert "VisualMapComponent" not in imports


def test_o_rotulo_girado_em_cima_tem_folga_para_nao_ser_cortado():
    """Apareceu na tela: o rótulo da barra mais alta do EBITDA saía pela metade.

    Girado, `R$ 262 Mil` mede cerca de sessenta pixels de altura. Com a folga
    padrão de 28, ele era cortado pela borda do gráfico — e o corte não avisa:
    ele simplesmente some.
    """
    # Só valores POSITIVOS: com negativo o rótulo vai para dentro da barra, e o
    # caso que este teste protege é o do rótulo em cima.
    positivos = [("09/25", Decimal("1298267.36")), ("10/25", Decimal("1100000"))]

    for bloco in (
        series.serie_temporal(positivos, chave="a", titulo="t"),
        series.barras_por_categoria(
            [series.Ponto("Sudeste", Decimal("84000"))], chave="b", titulo="t"
        ),
    ):
        rotulo = bloco.option["series"][0]["label"]
        assert rotulo["rotate"] == 90 and rotulo["position"] == "top"
        assert bloco.option["grid"]["top"] >= series.FOLGA_DO_ROTULO, (
            f"{bloco.chave}: rótulo girado em cima sem folga — ele será cortado"
        )


def test_com_negativo_o_rotulo_desce_para_dentro_e_nao_precisa_de_folga():
    """Em cima, o rótulo do valor negativo cairia dentro do eixo."""
    bloco = series.serie_temporal(
        [("01/26", Decimal("100")), ("02/26", Decimal("-40"))], chave="x", titulo="t"
    )

    assert bloco.option["series"][0]["label"]["position"] == "inside"


def test_a_comparada_precisa_de_menos_folga_porque_o_rotulo_vai_dentro():
    """Só a etiqueta do percentual sobe, e ela não gira."""
    bloco = series.barras_comparadas(
        [("01/26", Decimal("100"), Decimal("80"))],
        chave="x", titulo="t", rotulo_a="A", rotulo_b="B",
        rotulo_linha="%", linha=[Decimal("125")],
    )

    assert bloco.option["series"][0]["label"]["position"] == "insideBottom"
    assert 20 < bloco.option["grid"]["top"] < series.FOLGA_DO_ROTULO


# ── As faixas 3 a 7 — passo 6 ───────────────────────────────────────


@pytest.fixture
def massa(db):
    """A massa das três fontes, plantada pelo conector de CSV.

    É o que responde à pergunta "não daria para fazer um dado mockado?": ele já
    existe, e não é mock — é o ESPELHO, cheio por arquivo em vez de por API. A
    tela lê do espelho, e o espelho não sabe quem o encheu.
    """
    from django.core.management import call_command

    call_command("semear_fontes", "--aplicar", verbosity=0)
    call_command("semear_resultados", "--aplicar", verbosity=0)


def test_toda_faixa_com_dado_tem_grafico(client, massa, diretoria):
    """Uma faixa de números sem desenho é uma tabela com título — e a onda 10
    existe para que ela não seja isso."""
    client.force_login(diretoria)

    html = client.get(reverse("workspace:resultados")).content.decode()
    desenhados = set(re.findall(r'data-grafico-tela="([^"]+)"', html))

    for esperado in (
        "receita", "ebitda", "perfuracao", "carteira", "mix",
        "vencimentos", "projetos-situacao", "projetos-marcos", "satisfacao",
    ):
        assert esperado in desenhados, f"a faixa de {esperado} ficou sem gráfico"
    assert 'data-mapa-calor="quadro"' in html, "o quadro de pessoas ficou sem mapa"


def test_todo_grafico_da_tela_tem_tabela_irma(client, massa, diretoria):
    client.force_login(diretoria)

    html = client.get(reverse("workspace:resultados")).content.decode()

    telas = re.findall(r'data-grafico-tela="([^"]+)"', html)
    tabelas = re.findall(r'data-grafico-tabela="([^"]+)"', html)
    assert set(telas) == set(tabelas)


def test_a_dispersao_deixa_de_fora_quem_nao_tem_amostra_e_diz_quantos(
    client, massa, diretoria
):
    """Um contrato que faturou uma vez apareceria no quadrante errado por falta
    de histórico, e não por desempenho."""
    client.force_login(diretoria)

    resposta = client.get(reverse("workspace:resultados"))
    conteudo = resposta.context["por_chave"]["contratos"].conteudo

    no_grafico = len(conteudo["grafico"].linhas)
    na_carteira = len(conteudo["carteira"])
    assert no_grafico + conteudo["fora_do_grafico"] == na_carteira
    if conteudo["fora_do_grafico"]:
        assert "ficaram de fora do gráfico" in resposta.content.decode() or \
               "ficou de fora do gráfico" in resposta.content.decode()


def test_a_dispersao_marca_o_limiar_de_margem(client, massa, diretoria):
    """Sem a linha, o quadrante que importa não tem fronteira visível."""
    client.force_login(diretoria)

    grafico = client.get(reverse("workspace:resultados")).context[
        "por_chave"
    ]["contratos"].conteudo["grafico"]

    marcas = grafico.option["series"][0]["markLine"]["data"]
    assert marcas and marcas[0]["yAxis"] == float(resultados.MARGEM_MINIMA)


def test_o_mapa_do_quadro_inverte_os_limiares(client, massa, diretoria):
    """Turnover de 8,4% é crítico, não excelente. Sem a inversão, quem perdeu
    metade da equipe apareceria em verde."""
    client.force_login(diretoria)

    mapa = client.get(reverse("workspace:resultados")).context[
        "por_chave"
    ]["pessoas"].conteudo["mapa"]

    situacoes = {c.situacao for _, celulas in mapa.linhas for c in celulas}
    assert series.FAROL_CRITICO in situacoes, (
        "com turnover acima de 5% em algum CC, alguma célula tem de ser crítica"
    )


def test_a_satisfacao_mostra_o_numero_dentro_do_segmento(client, massa, diretoria):
    """Uma barra de 100% esconde se ela vale doze respostas ou mil — e doze é o
    número real desta massa."""
    client.force_login(diretoria)

    grafico = client.get(reverse("workspace:resultados")).context[
        "por_chave"
    ]["satisfacao"].conteudo["grafico"]

    for serie in grafico.option["series"]:
        assert serie["label"]["position"] == "inside"
        assert serie["data"][0]["rotulo"].isdigit()


def test_os_projetos_ganham_dois_graficos_e_nao_um(client, massa, diretoria):
    """A rosca responde "como está a carteira" e o bullet responde "o que vence
    antes do quê". Espremê-las num só produziria um que não responde nenhuma."""
    client.force_login(diretoria)

    conteudo = client.get(reverse("workspace:resultados")).context[
        "por_chave"
    ]["projetos"].conteudo

    assert conteudo["grafico"].option["series"][0]["type"] == "pie"
    assert conteudo["grafico_marcos"].option["series"][0]["type"] == "bar"


def test_os_vencimentos_usam_barra_porque_a_ordem_importa(client, massa, diretoria):
    """As faixas são cumulativas no tempo. Uma rosca ordena por tamanho e perde
    a única coisa que importa — qual vence antes."""
    client.force_login(diretoria)

    grafico = client.get(reverse("workspace:resultados")).context[
        "por_chave"
    ]["vencimentos"].conteudo["grafico"]

    assert grafico.option["series"][0]["type"] == "bar"
    assert [linha[0] for linha in grafico.linhas] == [
        "até 30 dias", "até 60 dias", "até 90 dias", "até 180 dias"
    ]


def test_faixa_indisponivel_nao_ganha_grafico_vazio(client, diretoria):
    """Sem espelho, a faixa diz que a fonte não está conectada — e não desenha
    um eixo com escala inventada."""
    from workspace.providers import resultados as contrato

    guardados = dict(contrato._provedores)
    contrato.limpar()
    try:
        client.force_login(diretoria)
        resposta = client.get(reverse("workspace:resultados"))
        assert resposta.status_code == 200
        for chave in ("contratos", "projetos", "pessoas", "satisfacao"):
            conteudo = resposta.context["por_chave"][chave].conteudo or {}
            assert not conteudo.get("grafico"), f"{chave} desenhou sem fonte"
    finally:
        contrato.limpar()
        contrato._provedores.update(guardados)


# ── O que se lê dentro da barra, e o que se lê no gráfico ───────────


@pytest.mark.parametrize(
    "fundo,esperado",
    [
        (series.COR_PRINCIPAL, "#ffffff"),   # navy escuro
        (series.COR_SECUNDARIA, series.COR_ROTULO_ESCURO),  # lilás claro
        (series.COR_NEGATIVO, "#ffffff"),
    ],
)
def test_o_rotulo_dentro_da_barra_escolhe_a_cor_pelo_fundo(fundo, esperado):
    """Branco sobre `#a0a2e1` dá 2,2:1, e o mínimo é 4,5:1.

    Era branco fixo em quatro gráficos. O pedido foi "põe branco e negrito"; em
    metade das barras isso APAGARIA o número, então o negrito entrou e o branco
    virou "o que contrastar mais".
    """
    assert series.cor_do_rotulo(fundo) == esperado


def test_todo_rotulo_dentro_de_barra_passa_no_contraste():
    """A varredura da paleta inteira — a garantia que o teste acima não dá para
    uma cor nova que alguém acrescente ao `_paleta`."""
    for cor in series._paleta(5):
        escolhida = series.cor_do_rotulo(cor)
        claro = series._luminancia(cor)
        escuro = series._luminancia(escolhida)
        razao = (max(claro, escuro) + 0.05) / (min(claro, escuro) + 0.05)
        assert razao >= 4.0, f"{escolhida} sobre {cor} dá só {razao:.2f}:1"


def test_a_dispersao_pinta_de_vermelho_quem_esta_abaixo_do_limiar(espelho):
    """A posição sozinha exige seguir a linha tracejada com o olho até cada
    ponto. "Não entendi como ler" foi a resposta de quem abriu a tela."""
    bloco = series.dispersao(
        [("CT-1", Decimal("100"), Decimal("4"), Decimal("10")),
         ("CT-2", Decimal("200"), Decimal("22"), Decimal("30"))],
        chave="d", titulo="Dispersão", limiar_y=Decimal("10"),
    )

    pontos = bloco.option["series"][0]["data"]
    assert pontos[0]["itemStyle"]["color"] == series.COR_NEGATIVO
    assert pontos[1]["itemStyle"]["color"] == series.COR_PRINCIPAL


def test_a_dispersao_repete_por_escrito_o_que_a_cor_diz(espelho):
    """Cor nunca sozinha: a tabela irmã ganha a mesma coluna."""
    bloco = series.dispersao(
        [("CT-1", Decimal("100"), Decimal("4"), Decimal("10"))],
        chave="d", titulo="Dispersão", limiar_y=Decimal("10"),
    )

    assert bloco.colunas[-1].titulo == "Situação"
    assert bloco.linhas[0][-1] == "abaixo do mínimo"
    assert "abaixo do mínimo" in bloco.option["series"][0]["data"][0]["detalhe"]


def test_o_tooltip_da_dispersao_traz_o_numero_ja_formatado():
    """`formatter` é uma string, e o texto vem pronto do Python. Um `Intl` em JS
    poria a regra de pt-BR num segundo lugar."""
    bloco = series.dispersao(
        [("CT-1", Decimal("1234.5"), Decimal("8.4"), Decimal("10"))],
        chave="d", titulo="Dispersão",
    )

    assert bloco.option["tooltip"]["formatter"] == "{@detalhe}"
    assert "1.234,50" in bloco.option["series"][0]["data"][0]["detalhe"]
