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
