"""A tabela contábil — bloco D.

"Sei que meu contrato vale 30 milhões, mas preciso saber com o que gastei."

## O que estes testes protegem

- **O detalhe fecha com o total.** É a única coisa que o bloco D não pode
  errar: uma tabela que não bate com o número logo acima dela destrói a
  confiança na tela inteira.
- **Despesa tem SINAL.** Sem ele o total soma receita com custo e vira um
  número que não significa nada.
- **A expansão vive na URL.** Mandar o link já aberto no ponto certo é o que
  faz a reunião andar.
- **Conta fora do plano não some.** Ela entra no total e aparece nomeada.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.services import resultados as svc


HOJE = date(2026, 9, 1)


@pytest.fixture
def plano(db):
    from io import StringIO

    from django.core.management import call_command

    call_command("semear_plano_de_contas", "--aplicar", stdout=StringIO())


@pytest.fixture
def espelho(db, plano):
    """Um contrato, um mês, e o razão que soma exatamente o agregado."""
    from resultados.models import (
        CompetenciaResultado,
        ContaContabil,
        Contrato,
        Fonte,
        ResultadoPorConta,
    )

    contrato = Contrato.objects.create(
        fonte=Fonte.PLATFORM, chave_externa="plt-C-1", codigo="C-1",
        nome_cliente="Cliente 1", servico="monitoramento",
        centro_custo="1042", regional="Sudeste", valor_mensal=Decimal("100000"),
    )
    CompetenciaResultado.objects.create(
        fonte=Fonte.SANKHYA, chave_externa="snk-C-1-202609", contrato=contrato,
        centro_custo="1042", ano=2026, mes=9,
        receita_bruta=Decimal("1000"), impostos=Decimal("150"),
        custo_direto=Decimal("600"), margem_contribuicao=Decimal("250"),
    )

    def lancar(codigo, valor, orcado=None):
        ResultadoPorConta.objects.create(
            fonte=Fonte.SANKHYA, chave_externa=f"snk-C-1-202609-{codigo}",
            contrato=contrato, centro_custo="1042", ano=2026, mes=9,
            conta=ContaContabil.objects.filter(codigo=codigo).first(),
            codigo_origem=codigo,
            valor_realizado=Decimal(valor),
            valor_orcado=Decimal(orcado) if orcado else None,
        )

    lancar("31101001", "1000", "1030")     # receita
    lancar("31201001", "150", "150")       # imposto
    lancar("41101001", "400", "380")       # pessoal
    lancar("41101002", "200", "220")       # pessoal, segunda analítica
    return contrato


@pytest.fixture
def diretoria(db):
    pessoa = f.pessoa("diretor_contabil", nome="Diretor")
    f.lotar(pessoa, centro_custo_codigo="1042")
    f.atribuir(
        pessoa,
        f.papel("diretoria_contabil", ["eco.ler.global"], escopo="global"),
        escopo="global",
    )
    return pessoa


def _faixa(client, query=""):
    resposta = client.get(reverse("workspace:resultados") + query)
    for faixa in resposta.context["faixas"]:
        if faixa.chave == "contabil":
            return resposta, faixa
    return resposta, None


# ── A reconciliação — o que não pode errar ──────────────────────────


def test_o_detalhe_fecha_com_o_agregado(client, espelho, diretoria):
    """Receita − impostos − custos, das MESMAS linhas que a tabela mostra.

    Um total calculado à parte pode discordar da soma visível, e detalhe que
    não bate com o total destrói a confiança na tela inteira.
    """
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09")

    # 1000 − 150 − 600 = 250
    assert faixa.conteudo["totais"]["realizado_ajustado"] == Decimal("250")


def test_a_receita_liquida_e_bruta_menos_impostos(client, espelho, diretoria):
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09")

    assert faixa.conteudo["receita_liquida"] == Decimal("850")


def test_a_soma_dos_grupos_e_o_total(client, espelho, diretoria):
    """O total sai das mesmas linhas, e este teste é o que amarra os dois."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09")

    soma = sum(
        (g["realizado_ajustado"] for g in faixa.conteudo["grupos"]), Decimal("0")
    )
    assert soma == faixa.conteudo["totais"]["realizado_ajustado"]


def test_a_soma_das_contas_e_o_grupo(client, espelho, diretoria):
    """O nível 2 tem de fechar com o nível 1 — senão expandir mostra um número
    diferente do que estava fechado, que é a pior surpresa possível."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09")
    pessoal = next(g for g in faixa.conteudo["grupos"] if g["codigo"] == "41101")

    soma = sum((c["realizado_ajustado"] for c in pessoal["contas"]), Decimal("0"))
    assert soma == pessoal["realizado_ajustado"] == Decimal("-600")


# ── O sinal ─────────────────────────────────────────────────────────


def test_despesa_tem_SINAL_e_nao_so_cor(client, espelho, diretoria):
    """Cor nunca sozinha — e aqui pior que o normal: a tabela tem linha de
    receita e linha de despesa, e vermelho sobre um número já negativo diria a
    mesma coisa duas vezes enquanto deixa o positivo mudo."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09")
    por_codigo = {g["codigo"]: g for g in faixa.conteudo["grupos"]}

    assert por_codigo["31101"]["realizado_ajustado"] > 0, "receita entra"
    assert por_codigo["31201"]["realizado_ajustado"] < 0, "imposto sai"
    assert por_codigo["41101"]["realizado_ajustado"] < 0, "custo sai"


def test_o_percentual_usa_o_valor_ABSOLUTO(client, espelho, diretoria):
    """"Pessoal: −600, 70,6% da receita líquida" é como se lê em voz alta. Com
    o percentual negativo junto, a linha diria a direção duas vezes e a coluna
    deixaria de somar 100% entre as despesas."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09")
    pessoal = next(g for g in faixa.conteudo["grupos"] if g["codigo"] == "41101")

    assert pessoal["realizado_ajustado"] < 0
    assert pessoal["pct_da_receita"] > 0


def test_a_folga_e_orcado_menos_realizado(client, espelho, diretoria):
    """Positivo é FOLGA. Invertido, um número positivo significaria estouro, e
    a leitura de relance seria o oposto do que a cor sugere."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09")
    pessoal = next(g for g in faixa.conteudo["grupos"] if g["codigo"] == "41101")

    # orçado −600, realizado −600 → sem folga
    assert pessoal["orcado"] == Decimal("-600")
    assert pessoal["dif_or_re"] == Decimal("0")


# ── A hierarquia e a expansão ───────────────────────────────────────


def test_o_grupo_traz_as_contas_analiticas(client, espelho, diretoria):
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09")
    pessoal = next(g for g in faixa.conteudo["grupos"] if g["codigo"] == "41101")

    assert [c["codigo"] for c in pessoal["contas"]] == ["41101001", "41101002"]
    assert pessoal["contas"][0]["nome"] == "Salários"


def test_a_expansao_vive_na_URL(client, espelho, diretoria):
    """Na URL e não no navegador: mandar o link JÁ ABERTO no ponto certo é o que
    faz a reunião andar. Guardado em `sessionStorage`, o link chegaria fechado
    do outro lado."""
    client.force_login(diretoria)

    _, fechado = _faixa(client, "?mes=2026-09")
    _, aberto = _faixa(client, "?mes=2026-09&expandir=41101")

    def pessoal(faixa):
        return next(g for g in faixa.conteudo["grupos"] if g["codigo"] == "41101")

    assert not pessoal(fechado)["aberto"]
    assert pessoal(aberto)["aberto"]


def test_o_link_do_grupo_ABRE_quando_fechado_e_FECHA_quando_aberto(
    client, espelho, diretoria
):
    client.force_login(diretoria)

    _, fechado = _faixa(client, "?mes=2026-09")
    _, aberto = _faixa(client, "?mes=2026-09&expandir=41101")

    def pessoal(faixa):
        return next(g for g in faixa.conteudo["grupos"] if g["codigo"] == "41101")

    assert "expandir=41101" in pessoal(fechado)["url_alternar"]
    assert "expandir=41101" not in pessoal(aberto)["url_alternar"]


def test_a_expansao_PRESERVA_os_outros_filtros(client, espelho, diretoria):
    """Perder o recorte ao abrir um grupo é como alguém conclui que a tela
    esquece o que ele escolheu."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09&periodo=6m&servico=monitoramento")
    pessoal = next(g for g in faixa.conteudo["grupos"] if g["codigo"] == "41101")

    assert "periodo=6m" in pessoal["url_alternar"]
    assert "servico=monitoramento" in pessoal["url_alternar"]


def test_ha_teto_de_grupos_abertos():
    """Sem teto, uma URL forjada abriria os vinte e oito grupos e a linha de
    total sairia de vista — e é ela que faz a tabela ser conferível."""
    muitos = ",".join(f"4110{i}" for i in range(20))

    assert len(svc.ler_filtros({"expandir": muitos}).expandidos) == (
        svc.MAXIMO_EXPANDIDO
    )


def test_grupo_repetido_na_url_entra_uma_vez():
    assert svc.ler_filtros({"expandir": "41101,41101,41106"}).expandidos == (
        "41101", "41106"
    )


# ── A tabela é do MÊS ───────────────────────────────────────────────


def test_a_tabela_e_do_MES_e_nao_do_periodo(client, espelho, diretoria, plano):
    """O período move os gráficos; esta tabela responde "onde foi o dinheiro
    DESTE mês". Somar doze meses por conta produziria um número que não bate
    com nenhum fechamento contábil — e é contra o fechamento que se confere."""
    from resultados.models import ContaContabil, Fonte, ResultadoPorConta

    ResultadoPorConta.objects.create(
        fonte=Fonte.SANKHYA, chave_externa="snk-C-1-202608-41101001",
        contrato=espelho, centro_custo="1042", ano=2026, mes=8,
        conta=ContaContabil.objects.get(codigo="41101001"),
        codigo_origem="41101001", valor_realizado=Decimal("9999"),
    )
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09&periodo=12m")
    pessoal = next(g for g in faixa.conteudo["grupos"] if g["codigo"] == "41101")

    assert pessoal["realizado_ajustado"] == Decimal("-600"), (
        "o mês de agosto não pode entrar"
    )


# ── A conta que o plano não conhece ─────────────────────────────────


def test_conta_fora_do_plano_entra_no_total_e_APARECE(
    client, espelho, diretoria
):
    """Despesa que some porque o plano está desatualizado é o defeito que
    ninguém procura no lugar certo. Ela entra somada, nomeada, e a tela avisa
    quantas são."""
    from resultados.models import Fonte, ResultadoPorConta

    ResultadoPorConta.objects.create(
        fonte=Fonte.SANKHYA, chave_externa="snk-C-1-202609-49999",
        contrato=espelho, centro_custo="1042", ano=2026, mes=9,
        conta=None, codigo_origem="49999", valor_realizado=Decimal("70"),
    )
    client.force_login(diretoria)

    resposta, faixa = _faixa(client, "?mes=2026-09")

    assert faixa.conteudo["desconhecidas"] == 1
    desconhecida = next(
        g for g in faixa.conteudo["grupos"] if g["codigo"] == "49999"
    )
    assert desconhecida["nome"] == "Conta não cadastrada"
    assert "não está no plano de contas" in resposta.content.decode()


def test_a_conta_desconhecida_entra_como_POSITIVA_e_o_aviso_explica(
    client, espelho, diretoria
):
    """Sem natureza não há sinal a aplicar, e inventar um seria pior: um custo
    lançado como receita mudaria o resultado na direção errada, em silêncio. O
    aviso na tela é o que faz alguém cadastrar a conta e resolver de vez."""
    from resultados.models import Fonte, ResultadoPorConta

    ResultadoPorConta.objects.create(
        fonte=Fonte.SANKHYA, chave_externa="snk-C-1-202609-49999",
        contrato=espelho, centro_custo="1042", ano=2026, mes=9,
        conta=None, codigo_origem="49999", valor_realizado=Decimal("70"),
    )
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09")
    desconhecida = next(
        g for g in faixa.conteudo["grupos"] if g["codigo"] == "49999"
    )

    assert desconhecida["realizado_ajustado"] == Decimal("70")
    assert desconhecida["desconhecida"] is True


# ── O nível 3 ───────────────────────────────────────────────────────


def test_o_nivel_3_reparte_a_conta_por_contrato(espelho, diretoria, plano):
    """Só existe porque o Sankhya traz o contrato na linha do razão. Sem isso a
    coluna ficaria sempre vazia — e coluna sempre vazia é pior que a ausência
    dela, porque promete um detalhe que não vem."""
    escopo = svc.escopo_de(diretoria, cache={})
    filtros = svc.ler_filtros({"mes": "2026-09"})

    linhas = svc.contas_do_contrato(escopo, filtros, "41101001")

    assert [linha["contrato"] for linha in linhas] == ["C-1"]
    assert linhas[0]["realizado"] == Decimal("400")


def test_o_rateio_sem_contrato_aparece_NOMEADO_no_nivel_3(
    espelho, diretoria, plano
):
    """Some da lista, o nível 3 não fecha com o nível 2 logo acima."""
    from resultados.models import ContaContabil, Fonte, ResultadoPorConta

    ResultadoPorConta.objects.create(
        fonte=Fonte.SANKHYA, chave_externa="snk-cc1042-202609-41101001",
        contrato=None, centro_custo="1042", ano=2026, mes=9,
        conta=ContaContabil.objects.get(codigo="41101001"),
        codigo_origem="41101001", valor_realizado=Decimal("55"),
    )
    escopo = svc.escopo_de(diretoria, cache={})

    linhas = svc.contas_do_contrato(
        escopo, svc.ler_filtros({"mes": "2026-09"}), "41101001"
    )

    rateio = next(linha for linha in linhas if not linha["contrato"])
    assert rateio["rotulo"] == "Rateio do CC 1042"
    assert rateio["realizado"] == Decimal("55")


# ── Sem fonte e sem dado ────────────────────────────────────────────


def test_sem_lancamento_a_faixa_diz_o_que_falta(client, diretoria, plano, db):
    """Bloco vazio não some e não mente: ele diz o que falta."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09")

    assert not faixa.disponivel
    assert "lançamento por conta contábil" in faixa.motivo
