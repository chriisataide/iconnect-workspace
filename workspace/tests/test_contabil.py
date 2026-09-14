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


def test_narrativa_da_pagina_e_unica_no_modo_normal_e_apresentacao(client, espelho, diretoria):
    client.force_login(diretoria)
    for modo in ("", "&apresentacao=1"):
        html = client.get(reverse("workspace:resultados") + "?mes=2026-09" + modo).content.decode()
        ids = ["destaques", "contratos", "dinheiro", "contabil", "rentabilidade", "vencimentos", "projetos"]
        posicoes = [html.index('id="' + chave + '"') for chave in ids]
        assert posicoes == sorted(posicoes)
        assert html.count('id="grafico-dados-mix"') == 1
        assert 'Mix por serviço</h3>' not in html
        assert html.count('id="rentabilidade"') == 1


def test_mix_tem_rotulos_legiveis_e_tabela_completa():
    bloco = svc._grafico_do_mix({"mix": [
        {"servico": "manutencao", "quantidade": 2, "valor": Decimal(25)},
        {"servico": "projeto_turnkey", "quantidade": 3, "valor": Decimal(75)},
    ]})
    assert [c.titulo for c in bloco.colunas] == ["Serviço", "Contratos", "Valor mensal", "Participação"]
    assert bloco.linhas[0][0:2] == ["Manutenção", "2"]
    label = bloco.option["series"][0]["data"][0]["label"]["formatter"]
    assert "\\n" not in label
    assert "\n" in label
    assert "25,0%" in label


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


# ── C6 · a cascata da DRE ───────────────────────────────────────────


def test_a_cascata_vai_da_receita_ao_ebitda(client, espelho, diretoria):
    """A ordem é a contábil, e é ela que faz o gráfico contar a história."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09")
    passos = [celulas[0] for celulas, _ in faixa.conteudo["cascata"].linhas_com_url]

    assert passos[0] == "Receita Bruta"
    assert passos[-1] == "EBITDA"
    assert "Receita Líquida" in passos
    assert "Margem de Contribuição" in passos


def test_a_cascata_fecha_no_MESMO_numero_da_tabela(client, espelho, diretoria):
    """Duas leituras da mesma aritmética, na mesma faixa. Se discordarem, uma
    delas está errada e ninguém sabe qual."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09")
    ultima = faixa.conteudo["cascata"].linhas[-1]

    from workspace.graficos import formato as fmt

    assert ultima[0] == "EBITDA"
    assert ultima[2] == fmt.moeda(
        faixa.conteudo["totais"]["realizado_ajustado"]
    )


def test_o_patamar_NAO_soma_de_novo(client, espelho, diretoria):
    """Subtotal é uma foto do estado. Somado como movimento, contaria o mesmo
    dinheiro duas vezes e o EBITDA sairia dobrado."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09")
    linhas = {celulas[0]: celulas for celulas, _ in faixa.conteudo["cascata"].linhas_com_url}

    assert linhas["Receita Líquida"][1] == "—", "patamar não tem movimento"
    # Receita líquida = 1000 − 150 = 850, e o acumulado não pulou.
    from workspace.graficos import formato as fmt

    assert linhas["Receita Líquida"][2] == fmt.moeda(Decimal("850"))


def test_o_degrau_do_INDIRETO_sai_das_linhas_SEM_contrato(
    client, espelho, diretoria, plano
):
    """A correção de um erro meu.

    A primeira versão tirava o indireto de `degrau_dre`, com `41601`, `41602`,
    `41701` e `41801` marcados como indiretos. Dava 88 mil enquanto a faixa do
    dinheiro logo acima mostrava 234 mil.

    O MESMO grupo carrega as duas coisas: a telefonia de um contrato é custo
    direto dele, a da administração é rateio. O que faz um custo ser indireto é
    a linha não ter contrato.
    """
    from resultados.models import ContaContabil, Fonte, ResultadoPorConta

    ResultadoPorConta.objects.create(
        fonte=Fonte.SANKHYA, chave_externa="snk-cc1042-202609-41602001",
        contrato=None, centro_custo="1042", ano=2026, mes=9,
        conta=ContaContabil.objects.get(codigo="41602001"),
        codigo_origem="41602001", valor_realizado=Decimal("30"),
    )
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09")
    linhas = {c[0]: c for c, _ in faixa.conteudo["cascata"].linhas_com_url}

    from workspace.graficos import formato as fmt

    assert linhas["Indireto"][1] == fmt.moeda(Decimal("-30"))
    # E o rateio NÃO entrou em "Demais", que é onde a conta 41602 mora.
    assert linhas["Demais"][1] == fmt.moeda(Decimal("0"))


def test_cada_degrau_LEVA_ao_grupo_de_contas_dele(client, espelho, diretoria):
    """É o que transforma "o EBITDA caiu" em "o EBITDA caiu, e é 41504" sem
    ninguém procurar."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09")
    por_passo = dict(
        (celulas[0], url)
        for celulas, url in faixa.conteudo["cascata"].linhas_com_url
    )

    assert "expandir=41101" in por_passo["Pessoal"]
    assert "expandir=31201" in por_passo["Impostos"]
    assert por_passo["Receita Líquida"] == "", "patamar não é grupo de contas"


def test_o_titulo_da_cascata_diz_o_MES_e_nao_o_periodo(client, espelho, diretoria):
    """`_titulo` escreveria "últimos 12 meses", que é o recorte dos gráficos da
    faixa acima. Um gráfico de um mês rotulado como doze é o tipo de erro que
    ninguém percebe porque nada parece errado."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09&periodo=12m")

    assert faixa.conteudo["cascata"].titulo.endswith("09/2026")
    assert "meses" not in faixa.conteudo["cascata"].titulo


# ── D3 · os três controles ──────────────────────────────────────────


def test_ver_numeros_alterna_entre_reais_e_percentual(client, espelho, diretoria):
    """"Quanto do meu contrato foi para pessoal?" é a pergunta em que a tabela é
    usada de verdade, e ela se responde em percentual."""
    client.force_login(diretoria)

    _, reais = _faixa(client, "?mes=2026-09")
    _, pct = _faixa(client, "?mes=2026-09&numeros=pct")

    assert not reais.conteudo["percentual"]
    assert pct.conteudo["percentual"]
    assert "numeros=pct" in reais.conteudo["url_modo"]
    assert "numeros=pct" not in pct.conteudo["url_modo"], "o link volta"


def test_o_modo_padrao_NAO_vai_para_a_url(client, espelho, diretoria):
    """Carregá-lo deixaria `?numeros=reais` em todo link compartilhado."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09")

    assert "numeros" not in faixa.conteudo["url_recolher_tudo"]


def test_o_percentual_e_calculado_em_TODA_coluna_de_dinheiro(
    client, espelho, diretoria
):
    """Uma coluna que continuasse em reais faria a linha somar grandezas
    diferentes."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09&numeros=pct")
    pessoal = next(g for g in faixa.conteudo["grupos"] if g["codigo"] == "41101")

    for campo in ("pct_realizado", "pct_ajustado", "pct_orcado", "pct_folga"):
        assert pessoal[campo] is not None, campo


def test_sem_ajuste_a_celula_e_TRACO_nos_dois_modos(client, espelho, diretoria):
    """Mostrar "0,0%" num modo e "—" no outro faria a mesma ausência parecer
    duas coisas diferentes conforme o botão apertado."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09&numeros=pct")
    pessoal = next(g for g in faixa.conteudo["grupos"] if g["codigo"] == "41101")

    assert pessoal["ajustes"] == Decimal("0")
    assert pessoal["pct_ajustes"] is None


def test_expandir_tudo_abre_todos_os_grupos(client, espelho, diretoria):
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09&expandir=tudo")

    assert faixa.conteudo["tudo_aberto"]
    assert all(g["aberto"] for g in faixa.conteudo["grupos"])


def test_expandir_tudo_passa_por_cima_do_teto(client, espelho, diretoria):
    """O teto de oito existe contra URL forjada com duzentos códigos. "Tudo" é
    um pedido explícito, e é o `tfoot` grudado que segura a linha de total no
    lugar quando a tabela cresce."""
    assert len(svc.ler_filtros({"expandir": "tudo"}).expandidos) == 1
    assert svc.ler_filtros({"expandir": "tudo"}).tudo_aberto


def test_recolher_tudo_volta_ao_estado_fechado(client, espelho, diretoria):
    client.force_login(diretoria)

    _, aberto = _faixa(client, "?mes=2026-09&expandir=tudo")
    assert "expandir" not in aberto.conteudo["url_recolher_tudo"]


def test_fechar_UM_grupo_com_tudo_aberto_fecha_so_ele(client, espelho, diretoria):
    """Sem isto, o clique num grupo com tudo aberto não faria nada — e a pessoa
    clicaria de novo achando que não pegou."""
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09&expandir=tudo")
    pessoal = next(g for g in faixa.conteudo["grupos"] if g["codigo"] == "41101")

    assert "expandir=" in pessoal["url_alternar"]
    assert "41101" not in pessoal["url_alternar"].split("expandir=")[1].split("&")[0]


# ── O espelho sabe dizer "não sei" ──────────────────────────────────


def test_custo_ausente_e_NULO_e_nao_zero(db, plano):
    """A correção de 10/09/2026, e a razão dela.

    `custo_direto` tinha `default=0`. O "custo ausente" — receita lançada e
    custo que ainda não chegou da contabilidade — ficava gravado como `0,00`, e
    a cascata da DRE lia isso como "não gastou nada", inflando a margem de
    contribuição pela receita líquida inteira do contrato.

    Os campos ORÇADOS ao lado já eram anuláveis exatamente por essa razão: a
    regra valia para metade dos campos.
    """
    from resultados.models import CompetenciaResultado, Contrato, Fonte

    contrato = Contrato.objects.create(
        fonte=Fonte.PLATFORM, chave_externa="p-x", codigo="C-X",
        nome_cliente="Cliente", servico="monitoramento", centro_custo="1042",
    )
    linha = CompetenciaResultado.objects.create(
        fonte=Fonte.SANKHYA, chave_externa="s-x", contrato=contrato,
        centro_custo="1042", ano=2026, mes=9,
        receita_bruta=Decimal("1000"),
    )

    linha.refresh_from_db()
    assert linha.custo_direto is None, "sem informar, é DESCONHECIDO"
    assert linha.margem_contribuicao is None


def test_zero_continua_sendo_um_numero(db, plano):
    """Um mês em que o custo foi de fato zero é outra coisa, e o espelho precisa
    saber dizer as duas."""
    from resultados.models import CompetenciaResultado, Contrato, Fonte

    contrato = Contrato.objects.create(
        fonte=Fonte.PLATFORM, chave_externa="p-y", codigo="C-Y",
        nome_cliente="Cliente", servico="monitoramento", centro_custo="1042",
    )
    linha = CompetenciaResultado.objects.create(
        fonte=Fonte.SANKHYA, chave_externa="s-y", contrato=contrato,
        centro_custo="1042", ano=2026, mes=9,
        receita_bruta=Decimal("1000"), custo_direto=Decimal("0"),
    )

    linha.refresh_from_db()
    assert linha.custo_direto == Decimal("0")
    assert linha.custo_direto is not None


def test_o_aviso_sai_do_AGREGADO_e_nao_da_deducao(client, espelho, diretoria, db):
    """Antes o campo não distinguia "não gastou" de "não sei", e isto era
    deduzido do razão — contrato com receita e nenhuma linha de custo. A dedução
    funcionava e tinha um falso positivo: o contrato que de fato não gastou nada
    no mês entrava na lista."""
    from resultados.models import CompetenciaResultado

    CompetenciaResultado.objects.filter(contrato=espelho).update(custo_direto=None)
    client.force_login(diretoria)

    _, faixa = _faixa(client, "?mes=2026-09")

    assert faixa.conteudo["sem_custo"] == ["C-1"]


def test_a_soma_IGNORA_o_desconhecido(db):
    """Somá-lo como zero faria o total de um mês com custo ausente parecer
    completo. O aviso é quem diz que falta linha — a soma não pode mentir junto."""
    from resultados import services as res

    class _L:
        def __init__(self, receita, mc):
            self.receita_bruta = Decimal(receita)
            self.margem_contribuicao = Decimal(mc) if mc is not None else None

    # 300 de margem sobre 2000 de receita = 15%. A linha sem margem não vira 0.
    assert res.margem_pct([_L("1000", "300"), _L("1000", None)]) == Decimal("15.00")
