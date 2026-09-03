"""Perfurar — Onda 11, mecanismo 1, isolado na faixa do dinheiro.

Os que mais protegem:

1. **A URL reproduz a tela.** Colar o endereço numa mensagem mostra exatamente
   o que a pessoa estava vendo — é metade do valor de existir uma tela em vez
   de um relatório.
2. **Perfurar funciona sem JavaScript.** A tabela irmã tem a MESMA URL num
   `<a>`, montada em Python. Não são duas implementações.
3. **O último nível diz que é o último.** Beco sem saída silencioso é pior que
   a ausência do nível.
"""

from __future__ import annotations

import re
from datetime import timedelta
from decimal import Decimal
from urllib.parse import parse_qs, urlparse

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from resultados.models import CompetenciaResultado, Contrato, Fonte
from workspace.services import resultados as svc

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()
COMPETENCIA = HOJE.replace(day=1)


@pytest.fixture
def espelho(db):
    """Duas regionais, três centros de custo, quatro contratos.

    A hierarquia inteira precisa existir para a perfuração ter o que descer —
    com uma regional só, o teste de "descer um degrau" passa sem descer nada.
    """

    def _contrato(codigo, regional, cc, servico="cftv", valor="100000"):
        contrato = Contrato.objects.create(
            fonte=Fonte.PLATFORM, chave_externa=f"plt-{codigo}", codigo=codigo,
            nome_cliente=f"Cliente {codigo}", servico=servico,
            centro_custo=cc, regional=regional,
            inicio_vigencia=HOJE - timedelta(days=800),
            fim_vigencia=HOJE + timedelta(days=300),
            valor_mensal=Decimal(valor),
        )
        for atras in range(6):
            total = COMPETENCIA.year * 12 + (COMPETENCIA.month - 1) - atras
            ano, mes = total // 12, total % 12 + 1
            CompetenciaResultado.objects.create(
                fonte=Fonte.SANKHYA, chave_externa=f"snk-{codigo}-{ano}{mes:02d}",
                contrato=contrato, centro_custo=cc, ano=ano, mes=mes,
                receita_bruta=Decimal(valor), receita_orcada=Decimal("95000"),
                margem_contribuicao=Decimal("12000"), ebitda=Decimal("7000"),
            )
        return contrato

    return [
        _contrato("CT-100", "Sudeste", "1042"),
        _contrato("CT-101", "Sudeste", "1042", valor="80000"),
        _contrato("CT-200", "Sudeste", "1055", valor="60000"),
        _contrato("CT-300", "Sul", "2050", valor="50000"),
    ]


@pytest.fixture
def diretoria(db):
    pessoa = f.pessoa("diretor_perf", nome="Diretor")
    f.lotar(pessoa, centro_custo_codigo="1042")
    f.atribuir(
        pessoa,
        f.papel("diretoria_perfuracao", ["eco.ler.global"], escopo="global"),
        escopo="global",
    )
    return pessoa


def _faixa(client, query=""):
    resposta = client.get(reverse("workspace:resultados") + query)
    return resposta, resposta.context["por_chave"]["dinheiro"].conteudo


# ── 1. O estado mora na URL ─────────────────────────────────────────


def test_a_url_com_filtros_reproduz_a_mesma_tela(client, espelho, diretoria):
    """Ida e volta: descer pela URL dá o mesmo que descer pelo clique."""
    client.force_login(diretoria)

    _, raiz = _faixa(client)
    destino = raiz["perfuracao"].urls[0]

    _, descido = _faixa(client, "?" + urlparse(destino).query)

    assert [m.rotulo for m in descido["migalhas"]] == ["Empresa", "Sudeste"]


def test_o_nivel_e_derivado_dos_filtros_e_nao_lido_da_url(client, espelho, diretoria):
    """Um `?nivel=cc` ao lado de `?cc=1042` seria uma segunda verdade sobre o
    mesmo fato, e as duas discordariam no dia em que alguém editasse a URL."""
    assert svc.nivel_de(svc.ler_filtros({})) == 0
    assert svc.nivel_de(svc.ler_filtros({"regional": "Sudeste"})) == 1
    assert svc.nivel_de(svc.ler_filtros({"regional": "Sudeste", "cc": "1042"})) == 2
    # Sem a regional, o CC sozinho NÃO conta como nível 2: a trilha ficaria com
    # um buraco no meio.
    assert svc.nivel_de(svc.ler_filtros({"cc": "1042"})) == 0


def test_descer_preserva_os_outros_filtros(client, espelho, diretoria):
    """Perder a janela de seis meses ao descer um nível é como alguém conclui
    que o filtro "não funciona"."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?janela=6&servico=cftv")
    destino = parse_qs(urlparse(faixa["perfuracao"].urls[0]).query)

    assert destino["janela"] == ["6"]
    assert destino["servico"] == ["cftv"]
    assert destino["regional"] == ["Sudeste"]


def test_subir_na_trilha_limpa_os_niveis_de_baixo(client, espelho, diretoria):
    """Subir para a regional com o centro de custo ainda no filtro mostraria a
    regional recortada por um CC que a trilha diz não estar mais ativo."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?regional=Sudeste&cc=1042&contrato=CT-100")
    para_a_regional = next(m for m in faixa["migalhas"] if m.rotulo == "Sudeste")
    parametros = parse_qs(urlparse(para_a_regional.url).query)

    assert parametros["regional"] == ["Sudeste"]
    assert "cc" not in parametros
    assert "contrato" not in parametros


def test_a_trilha_aparece_mesmo_na_raiz(client, espelho, diretoria):
    """Sem isso ela nasceria no primeiro clique e sumiria no último — que é
    quando a pessoa mais precisa saber onde está."""
    client.force_login(diretoria)

    _, faixa = _faixa(client)

    assert [m.rotulo for m in faixa["migalhas"]] == ["Empresa"]
    assert faixa["migalhas"][0].atual is True


def test_a_trilha_marca_o_degrau_atual(client, espelho, diretoria):
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?regional=Sudeste&cc=1042")

    assert [m.atual for m in faixa["migalhas"]] == [False, False, True]


def test_a_trilha_nao_leva_dado_pessoal_na_url(client, espelho, diretoria):
    """A query string vai para o histórico do navegador, para o log do servidor
    e para o corpo do e-mail em que alguém cola o link."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?regional=Sudeste")
    tudo = " ".join(m.url for m in faixa["migalhas"]) + " ".join(
        faixa["perfuracao"].urls
    )

    for proibido in ("cpf", "email", "@", "nome_cliente"):
        assert proibido not in tudo.lower()


# ── 2. Sem JavaScript ───────────────────────────────────────────────


def test_a_tabela_irma_tem_o_mesmo_link_do_grafico(client, espelho, diretoria):
    """Não são duas implementações: as duas leem `bloco.urls`, montada em
    Python. É o que faz descer continuar funcionando com o script desligado."""
    client.force_login(diretoria)

    resposta, faixa = _faixa(client)
    html = resposta.content.decode().replace("&amp;", "&")
    do_grafico = faixa["perfuracao"].urls

    for url in do_grafico:
        assert f'<a href="{url}"' in html, f"a tabela irmã não leva a {url}"


def test_a_url_do_ponto_vem_do_servidor_e_nao_do_javascript(client, espelho, diretoria):
    """Montar a URL no JS exigiria replicar ali a hierarquia — e ela mudaria de
    lugar sozinha na primeira dimensão nova."""
    client.force_login(diretoria)

    _, faixa = _faixa(client)
    fonte = faixa["perfuracao"].option["dataset"]["source"]

    assert faixa["perfuracao"].option["dataset"]["dimensions"][3] == "url"
    assert all(linha[3].startswith("/workspace/resultados/") for linha in fonte)


def test_o_javascript_so_navega_para_caminho_deste_produto():
    """URL absoluta vinda de dado seria um redirecionamento aberto com passos
    extras."""
    from pathlib import Path

    js = (
        Path(__file__).resolve().parent.parent
        / "static" / "workspace" / "js" / "echarts-adb.js"
    ).read_text(encoding="utf-8")

    assert 'destino.charAt(0) === "/"' in js


def test_a_barra_clicavel_anuncia_que_e_clicavel(client, espelho, diretoria):
    """Sem o cursor de mão, a perfuração é um segredo."""
    client.force_login(diretoria)

    _, faixa = _faixa(client)

    assert faixa["perfuracao"].option["series"][0]["cursor"] == "pointer"


# ── 3. A fronteira ──────────────────────────────────────────────────


def test_o_ultimo_nivel_diz_que_e_o_ultimo(client, espelho, diretoria):
    """Perfurar até o contrato funciona; até a ocorrência, não — o detalhe
    operacional mora no Platform."""
    client.force_login(diretoria)

    resposta, faixa = _faixa(client, "?regional=Sudeste&cc=1042&contrato=CT-100")

    assert faixa["perfuracao"].fronteira
    assert "iConnect Platform" in faixa["perfuracao"].fronteira
    assert "au-gr-fronteira" in resposta.content.decode()


def test_no_ultimo_nivel_nao_ha_barra_para_clicar(client, espelho, diretoria):
    """Beco sem saída silencioso é pior que a ausência do nível: quem clicou e
    não viu nada acontecer conclui que a tela quebrou."""
    client.force_login(diretoria)

    resposta, faixa = _faixa(client, "?regional=Sudeste&cc=1042&contrato=CT-100")

    assert faixa["perfuracao"].vazio is True
    assert faixa["perfuracao"].perfura is False
    assert "data-perfura=" not in resposta.content.decode()


# ── A hierarquia ────────────────────────────────────────────────────


def test_cada_nivel_agrupa_pela_dimensao_seguinte(client, espelho, diretoria):
    client.force_login(diretoria)

    _, raiz = _faixa(client)
    _, na_regional = _faixa(client, "?regional=Sudeste")
    _, no_cc = _faixa(client, "?regional=Sudeste&cc=1042")

    assert {linha[0] for linha in raiz["perfuracao"].linhas} == {"Sudeste", "Sul"}
    assert {linha[0] for linha in na_regional["perfuracao"].linhas} == {"1042", "1055"}
    assert {linha[0] for linha in no_cc["perfuracao"].linhas} == {"CT-100", "CT-101"}


def test_a_perfuracao_respeita_o_escopo_da_pessoa(client, espelho):
    """Uma segunda consulta poderia oferecer uma regional que a pessoa não
    alcança — o que revelaria a existência dela."""
    gerente = f.pessoa("gerente_perf", nome="Gerente")
    unidade = f.unidade("SE", "Sudeste")
    f.lotar(gerente, uni=unidade, centro_custo_codigo="1042")
    f.atribuir(
        gerente,
        f.papel("gerente_perfuracao", ["eco.ler.departamento"], escopo="departamento"),
        escopo="departamento",
    )
    client.force_login(gerente)

    _, faixa = _faixa(client)
    categorias = {linha[0] for linha in faixa["perfuracao"].linhas}

    assert "Sul" not in categorias, "a perfuração vazou fora do escopo"


def test_a_perfuracao_ordena_pelo_maior(client, espelho, diretoria):
    """A ordem da lista é a ordem de olhar: o que pesa mais vem primeiro."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?regional=Sudeste")
    valores = [linha[0] for linha in faixa["perfuracao"].linhas]

    assert valores == ["1042", "1055"], "1042 soma mais que 1055"


def test_sem_carteira_conectada_a_perfuracao_nao_estoura(client, espelho, diretoria):
    """A instalação sem integração continua sendo uma instalação válida."""
    from workspace.providers import resultados as contrato

    guardados = dict(contrato._provedores)
    contrato._provedores.pop(contrato.ProvedorCarteira, None)
    try:
        client.force_login(diretoria)
        resposta, faixa = _faixa(client)
        assert resposta.status_code == 200
        assert faixa["perfuracao"].vazio is True
    finally:
        contrato._provedores.clear()
        contrato._provedores.update(guardados)


# ── Mecanismo 2: filtrar cruzado, e a tarja ─────────────────────────


def test_o_filtro_ativo_aparece_em_tarja_com_o_x_para_remover(client, espelho, diretoria):
    """"Filtro invisível é a principal fonte de 'esse número está errado' que
    não está."" """
    client.force_login(diretoria)

    resposta = client.get(reverse("workspace:resultados") + "?servico=cftv")
    html = resposta.content.decode()

    assert "Filtrado por:" in html
    assert "Serviço" in html and "cftv" in html
    assert "au-tarja-x" in html, "sem o X, a tarja informa e não deixa desfazer"
    assert "Limpar tudo" in html


def test_a_tarja_aparece_no_modo_apresentacao(client, espelho, diretoria):
    """O defeito era literal: `?apresentacao=1&layer=1` escondia a barra de
    filtros inteira e mostrava números recortados sem nada dizendo que eram.

    Numa reunião, projetado.
    """
    client.force_login(diretoria)

    html = client.get(
        reverse("workspace:resultados") + "?apresentacao=1&servico=cftv"
    ).content.decode()

    assert "Filtrado por:" in html, "em apresentação o filtro ficava invisível"
    assert "au-filtros--resultados" not in html, "e os CONTROLES continuam escondidos"


def test_sem_filtro_nao_ha_tarja_nem_limpar_tudo(client, espelho, diretoria):
    """Uma tarja vazia dizendo "filtrado por: nada" é ruído."""
    client.force_login(diretoria)

    html = client.get(reverse("workspace:resultados")).content.decode()

    assert "Filtrado por:" not in html
    assert "Limpar tudo" not in html


def test_o_x_da_tarja_e_um_link_e_funciona_sem_javascript(client, espelho, diretoria):
    """Remover um filtro é navegar para a mesma tela sem ele."""
    client.force_login(diretoria)

    resposta = client.get(reverse("workspace:resultados") + "?servico=cftv")
    tarja = resposta.context["filtros_ativos"][0]

    assert "servico" not in parse_qs(urlparse(tarja.url_remover).query)


def test_remover_a_regional_limpa_os_niveis_de_baixo(client, espelho, diretoria):
    """A regional recortada por um CC que a tela diz não estar ativo é um número
    que não bate com nada."""
    client.force_login(diretoria)

    resposta = client.get(
        reverse("workspace:resultados") + "?regional=Sudeste&cc=1042&contrato=CT-100"
    )
    regional = next(
        t for t in resposta.context["filtros_ativos"] if t.chave == "regional"
    )
    restante = parse_qs(urlparse(regional.url_remover).query)

    assert "regional" not in restante
    assert "cc" not in restante
    assert "contrato" not in restante


def test_limpar_tudo_preserva_competencia_e_janela(client, espelho, diretoria):
    """Competência não é filtro: é o assunto da tela. E limpar a janela
    devolveria treze meses a quem escolheu seis — surpresa, não limpeza."""
    client.force_login(diretoria)

    resposta = client.get(
        reverse("workspace:resultados") + "?servico=cftv&janela=6&regional=Sudeste"
    )
    limpa = parse_qs(urlparse(resposta.context["url_limpar"]).query)

    assert limpa["janela"] == ["6"]
    assert "competencia" in limpa
    assert "servico" not in limpa
    assert "regional" not in limpa


def test_o_quarto_filtro_cruzado_substitui_o_mais_antigo_e_avisa(
    client, espelho, diretoria
):
    """Quatro recortes simultâneos produzem um número que ninguém explica de
    cabeça — e recusar o clique seria pior: a pessoa clicaria de novo achando
    que não pegou."""
    filtros = svc.ler_filtros(
        {"servico": "cftv", "layer": "1", "deficitario": "1"}
    )
    base = reverse("workspace:resultados")

    # Já há três cruzados; um QUARTO parâmetro cruzável não existe, então
    # trocar um dos três não substitui nada.
    _, trocou = svc.cruzar(filtros, base, "servico", "alarme")
    assert trocou is False, "trocar um filtro que já está ativo não substitui"

    # Com apenas dois ativos, o terceiro entra sem substituir.
    dois = svc.ler_filtros({"servico": "cftv", "layer": "1"})
    _, trocou = svc.cruzar(dois, base, "deficitario", "1")
    assert trocou is False


def test_o_limite_de_cruzados_e_declarado_e_nao_magico():
    assert svc.MAXIMO_DE_CRUZADOS == 3
    assert set(svc.CRUZAVEIS) == {"servico", "layer", "deficitario"}


# ── Mecanismo 3: pivotar ────────────────────────────────────────────


def test_pivotar_reagrupa_sem_mudar_de_nivel(client, espelho, diretoria):
    """O mesmo número por outra dimensão — o seletor no canto do bloco."""
    client.force_login(diretoria)

    _, por_regional = _faixa(client)
    _, por_servico = _faixa(client, "?dim=servico")

    assert "regional" in por_regional["perfuracao"].titulo
    assert "serviço" in por_servico["perfuracao"].titulo
    # Pivotar NÃO desce: a trilha continua na empresa.
    assert [m.rotulo for m in por_servico["migalhas"]] == ["Empresa"]


def test_pivotar_e_link_e_funciona_sem_javascript(client, espelho, diretoria):
    """Um `<select>` que submete no `change` não abre em nova aba, não entra no
    histórico e não funciona sem script."""
    client.force_login(diretoria)

    resposta = client.get(reverse("workspace:resultados"))
    html = resposta.content.decode()

    assert 'class="au-pivotar"' in html
    assert 'class="au-pivotar-opcao" href=' in html


def test_a_dimensao_desconhecida_cai_na_hierarquia(client, espelho, diretoria):
    """`?dim=abacaxi` é uma URL digitada errada, não um ataque."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?dim=abacaxi")

    assert "regional" in faixa["perfuracao"].titulo


def test_pivotar_para_atributo_cruza_em_vez_de_descer(client, espelho, diretoria):
    """Regional, CC e contrato trocam o NÍVEL; serviço e layer reagrupam sem
    descer, e ali o clique vira filtro cruzado."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?dim=servico")
    destino = parse_qs(urlparse(faixa["perfuracao"].urls[0]).query)

    assert faixa["perfuracao"].cruzado is True
    assert "servico" in destino
    assert "regional" not in destino, "cruzar não desce um nível"


# ── Mecanismo 4: detalhar ───────────────────────────────────────────


def test_o_detalhe_bate_com_o_agregado(client, espelho, diretoria):
    """O teste que sustenta a confiança na tela inteira.

    Detalhe que não bate com o agregado a destrói — e a pessoa some com o
    número, não com a tela.
    """
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?regional=Sudeste")
    agregado = faixa["totais"]["receita_bruta"]

    detalhe = client.get(
        reverse("workspace:resultados_detalhe") + "?regional=Sudeste"
    ).context

    assert detalhe["total_das_linhas"] == agregado


def test_o_detalhe_herda_os_filtros_e_mostra_quais(client, espelho, diretoria):
    client.force_login(diretoria)

    resposta = client.get(
        reverse("workspace:resultados_detalhe") + "?regional=Sudeste&servico=cftv"
    )

    assert {t.chave for t in resposta.context["filtros_ativos"]} == {
        "regional", "servico"
    }
    assert "Filtrado por:" in resposta.content.decode()


def test_o_detalhe_e_link_explicito_e_nao_clique_no_grafico(client, espelho, diretoria):
    """Descer para as linhas é outra pergunta, e não uma variação da mesma."""
    client.force_login(diretoria)

    html = client.get(reverse("workspace:resultados") + "?servico=cftv").content.decode()

    assert "Detalhamento" in html
    assert "/workspace/resultados/detalhe/" in html


def test_o_detalhe_traz_a_procedencia_de_cada_linha(client, espelho, diretoria):
    """Este é o nível mais fundo da tela, e é aqui que alguém confere contra o
    ERP. Sem a chave externa, "de onde vem esse número" não tem resposta."""
    client.force_login(diretoria)

    html = client.get(reverse("workspace:resultados_detalhe")).content.decode()

    assert "au-detalhe-procedencia" in html
    assert "sankhya:" in html


def test_o_detalhe_vazio_diz_que_e_ausencia_e_nao_zero(client, espelho, diretoria):
    client.force_login(diretoria)

    html = client.get(
        reverse("workspace:resultados_detalhe") + "?servico=nao-existe"
    ).content.decode()

    assert "Não é zero" in html


def test_quem_nao_tem_escopo_nao_abre_o_detalhe(client, espelho):
    de_fora = f.pessoa("almoxarife_det", nome="Almoxarife")
    f.lotar(de_fora, centro_custo_codigo="9999")
    f.atribuir(
        de_fora, f.papel("estoque_det", ["est.ler.global"], escopo="global"),
        escopo="global",
    )
    client.force_login(de_fora)

    assert client.get(reverse("workspace:resultados_detalhe")).status_code == 403


# ── O contrato de dados ─────────────────────────────────────────────


def test_o_endpoint_aplica_o_mesmo_escopo_da_tela(client, espelho):
    """O erro clássico: a tela filtra por regional e a API devolve tudo."""
    gerente = f.pessoa("gerente_dados", nome="Gerente")
    unidade = f.unidade("SE2", "Sudeste")
    f.lotar(gerente, uni=unidade, centro_custo_codigo="1042")
    f.atribuir(
        gerente,
        f.papel("gerente_dados_papel", ["eco.ler.departamento"], escopo="departamento"),
        escopo="departamento",
    )
    client.force_login(gerente)

    corpo = client.get(reverse("workspace:resultados_dados")).json()

    assert corpo["escopo"]["centros_custo"] == ["1042"], (
        "a API devolveu escopo mais largo que o da tela"
    )


def test_o_anonimo_nao_le_o_endpoint_de_dados(client, espelho):
    resposta = client.get(reverse("workspace:resultados_dados"))

    assert resposta.status_code == 302
    assert "/entrar/" in resposta["Location"]


def test_quem_nao_tem_escopo_recebe_403_no_endpoint(client, espelho):
    de_fora = f.pessoa("almoxarife_dados", nome="Almoxarife")
    f.lotar(de_fora, centro_custo_codigo="9999")
    f.atribuir(
        de_fora, f.papel("estoque_dados", ["est.ler.global"], escopo="global"),
        escopo="global",
    )
    client.force_login(de_fora)

    assert client.get(reverse("workspace:resultados_dados")).status_code == 403


def test_o_endpoint_respeita_a_janela_e_os_filtros(client, espelho, diretoria):
    client.force_login(diretoria)

    corpo = client.get(
        reverse("workspace:resultados_dados") + "?janela=3&regional=Sudeste"
    ).json()

    assert len(corpo["meses"]) == 3
    assert corpo["escopo"]["regionais"] == ["Sudeste"]


def test_o_endpoint_nao_devolve_dado_pessoal(client, espelho, diretoria):
    """O JSON sai do prédio tão fácil quanto o PDF."""
    client.force_login(diretoria)

    bruto = client.get(reverse("workspace:resultados_dados")).content.decode().lower()

    for proibido in ("cpf", "@", "nome_cliente", "responsavel"):
        assert proibido not in bruto


# ── O modo apresentação ─────────────────────────────────────────────


def test_apresentar_preserva_os_filtros(client, espelho, diretoria):
    """Antes ele levava só a competência: clicar com um recorte ativo trocava os
    números em silêncio, no caminho entre a tela e o projetor."""
    client.force_login(diretoria)

    resposta = client.get(
        reverse("workspace:resultados") + "?servico=cftv&janela=6&regional=Sudeste"
    )
    destino = parse_qs(urlparse(resposta.context["url_apresentar"]).query)

    assert destino["apresentacao"] == ["1"]
    assert destino["servico"] == ["cftv"]
    assert destino["regional"] == ["Sudeste"]
    assert destino["janela"] == ["6"]


def test_o_pdf_carrega_os_filtros_ativos_no_rodape(client, espelho, diretoria, monkeypatch):
    """Pior que na tela: o PDF é lido dias depois, longe dela, por gente que não
    escolheu o recorte.

    A afirmação é sobre o TEXTO que entra no documento, e não sobre os bytes: o
    reportlab comprime o fluxo de conteúdo, e procurar a frase no PDF binário
    daria um teste que passa por acaso e falha quando a compressão mudar.
    """
    from workspace.services import pdf_resultados

    capturado = {}
    original = pdf_resultados.Paragraph

    def espiao(texto, estilo):
        capturado.setdefault("textos", []).append(str(texto))
        return original(texto, estilo)

    monkeypatch.setattr(pdf_resultados, "Paragraph", espiao)
    client.force_login(diretoria)

    client.get(reverse("workspace:resultados_pdf") + "?servico=cftv&regional=Sudeste")
    com_recorte = " ".join(capturado["textos"])

    capturado.clear()
    client.get(reverse("workspace:resultados_pdf"))
    sem_recorte = " ".join(capturado["textos"])

    assert "Recorte aplicado" in com_recorte
    assert "Serviço: cftv" in com_recorte
    assert "Sem recorte" in sem_recorte
