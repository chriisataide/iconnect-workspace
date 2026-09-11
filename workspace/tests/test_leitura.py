"""A frase de leitura por bloco — B2.

Regra em Python, com número real. Nunca texto fixo, nunca modelo de linguagem.

## A regra que governa todas as outras

**Sem dado suficiente para uma afirmação verdadeira, o bloco não exibe frase.**
Frase genérica é pior que ausência: ela ocupa o lugar da informação e ensina a
não ler aquele espaço.

Por isso cada regra tem, aqui, um teste do caso em que ela NÃO deve falar — que
é o caso difícil e o único que a mantém honesta.

## E por que são três, e não onze

Cada frase é uma afirmação que pode ficar falsa. Onze afirmações que ninguém
revisa é como um painel passa a mentir devagar.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.services import resultados as svc


HOJE = date(2026, 9, 1)


class _Linha:
    """Uma linha de competência, com o mínimo que as regras leem."""

    def __init__(self, ano, mes, receita, mc, contrato="C-1"):
        self.ano, self.mes = ano, mes
        self.receita_bruta = Decimal(receita)
        self.margem_contribuicao = Decimal(mc)
        self.contrato = contrato


def _filtros(**parametros) -> svc.Filtros:
    return svc.ler_filtros(parametros, hoje=HOJE)


# ── A margem, contra o mês anterior ─────────────────────────────────


def test_a_frase_diz_a_variacao_em_PONTOS():
    """A margem já é percentual. "Caiu 12%" sobre 19% é ambíguo — pode ser 7 ou
    16,7 —, e as duas leituras levam a decisões diferentes."""
    conteudo = {
        "serie": [
            _Linha(2026, 8, "1000", "200"),   # 20%
            _Linha(2026, 9, "1000", "150"),   # 15%
        ]
    }

    frase = svc._leitura_do_dinheiro(conteudo, _filtros())

    assert "caiu 5,0 pontos" in frase
    assert "15,0%" in frase
    assert "08/2026" in frase


def test_a_alta_e_dita_como_alta():
    conteudo = {
        "serie": [_Linha(2026, 8, "1000", "150"), _Linha(2026, 9, "1000", "200")]
    }

    assert "subiu 5,0 pontos" in svc._leitura_do_dinheiro(conteudo, _filtros())


def test_um_ponto_no_singular():
    conteudo = {
        "serie": [_Linha(2026, 8, "1000", "200"), _Linha(2026, 9, "1000", "190")]
    }

    frase = svc._leitura_do_dinheiro(conteudo, _filtros())

    assert "1,0 ponto " in frase and "pontos" not in frase


def test_estavel_e_dito_como_estavel():
    """Zero de variação não é "caiu 0,0 pontos" — a frase precisa soar como o
    que aconteceu."""
    conteudo = {
        "serie": [_Linha(2026, 8, "1000", "200"), _Linha(2026, 9, "1000", "200")]
    }

    assert "estável" in svc._leitura_do_dinheiro(conteudo, _filtros())


def test_SEM_mes_anterior_NAO_ha_frase():
    """Comparar com nada e chamar de variação seria inventar o número mais
    importante da frase."""
    conteudo = {"serie": [_Linha(2026, 9, "1000", "150")]}

    assert svc._leitura_do_dinheiro(conteudo, _filtros()) == ""


def test_SEM_receita_NAO_ha_frase():
    """Margem sobre receita zero é divisão por zero, e "0%" seria lido como
    "margem zero" — que é outra coisa."""
    conteudo = {
        "serie": [_Linha(2026, 8, "0", "0"), _Linha(2026, 9, "0", "0")]
    }

    assert svc._leitura_do_dinheiro(conteudo, _filtros()) == ""


def test_serie_vazia_NAO_ha_frase():
    assert svc._leitura_do_dinheiro({"serie": []}, _filtros()) == ""


# ── Quem explica a variação ─────────────────────────────────────────


def test_nomeia_o_contrato_quando_UM_explica_o_bastante():
    """Sem isto a frase diz o que aconteceu e não onde olhar."""
    conteudo = {
        "serie": [
            _Linha(2026, 8, "500", "100", "CT-A"),
            _Linha(2026, 8, "500", "100", "CT-B"),
            _Linha(2026, 9, "500", "10", "CT-A"),   # despencou
            _Linha(2026, 9, "500", "100", "CT-B"),  # estável
        ]
    }

    assert "puxada por CT-A" in svc._leitura_do_dinheiro(conteudo, _filtros())


def test_NAO_nomeia_ninguem_quando_o_peso_e_dividido():
    """Com um limiar baixo a frase nomearia um contrato entre vários de peso
    parecido, e alguém cobraria a pessoa errada na reunião."""
    conteudo = {
        "serie": [
            _Linha(2026, 8, "500", "100", "CT-A"),
            _Linha(2026, 8, "500", "100", "CT-B"),
            _Linha(2026, 9, "500", "50", "CT-A"),
            _Linha(2026, 9, "500", "50", "CT-B"),
        ]
    }

    frase = svc._leitura_do_dinheiro(conteudo, _filtros())

    assert "puxada por" not in frase
    assert "caiu" in frase, "a frase continua — só o culpado é que some"


def test_o_limiar_de_culpa_e_MAIS_DA_METADE():
    """Era 40%, e este arquivo mostrou por que não servia: com dois contratos
    caindo igual, cada um pesa 50% e passava — nomeando um dos dois
    arbitrariamente."""
    assert svc.PESO_PARA_CULPAR == Decimal("50")


def test_nomeia_quando_um_explica_MAIS_que_os_outros_somados():
    conteudo = {
        "serie": [
            _Linha(2026, 8, "500", "100", "CT-A"),
            _Linha(2026, 8, "500", "100", "CT-B"),
            _Linha(2026, 9, "500", "30", "CT-A"),   # cai 70
            _Linha(2026, 9, "500", "70", "CT-B"),   # cai 30
        ]
    }

    assert "puxada por CT-A" in svc._leitura_do_dinheiro(conteudo, _filtros())


# ── A tabela contábil ───────────────────────────────────────────────


def test_diz_qual_grupo_consumiu_mais():
    """O grupo de MAIOR consumo, e não uma lista: a frase existe para dizer onde
    olhar primeiro, e três nomes numa frase não priorizam nada."""
    conteudo = {
        "grupos": [
            {"nome": "PESSOAL", "natureza": "custo", "pct_da_receita": Decimal("30"),
             "dif_or_re": Decimal("10")},
            {"nome": "TRANSPORTES", "natureza": "custo", "pct_da_receita": Decimal("5"),
             "dif_or_re": Decimal("1")},
        ]
    }

    frase = svc._leitura_do_contabil(conteudo)

    assert frase.startswith("Pessoal consumiu 30,0%")
    assert "TRANSPORTES" not in frase


def test_avisa_quando_o_maior_grupo_ESTOUROU_o_orcado():
    conteudo = {
        "grupos": [
            {"nome": "PESSOAL", "natureza": "custo", "pct_da_receita": Decimal("30"),
             "dif_or_re": Decimal("-500")},
        ]
    }

    assert "estourou o orçado em R$ 500,00" in svc._leitura_do_contabil(conteudo)


def test_a_receita_NAO_e_candidata_a_maior_consumo():
    """Ela consome 118% da receita líquida por definição, e venceria sempre."""
    conteudo = {
        "grupos": [
            {"nome": "RECEITAS", "natureza": "receita",
             "pct_da_receita": Decimal("118"), "dif_or_re": None},
            {"nome": "PESSOAL", "natureza": "custo",
             "pct_da_receita": Decimal("30"), "dif_or_re": None},
        ]
    }

    assert svc._leitura_do_contabil(conteudo).startswith("Pessoal")


def test_sem_grupo_de_custo_NAO_ha_frase():
    assert svc._leitura_do_contabil({"grupos": []}) == ""


# ── Os contratos ────────────────────────────────────────────────────


class _Contrato:
    def __init__(self, codigo, valor, margem):
        self.codigo = codigo
        self.valor_mensal = Decimal(valor)
        self.margem_contribuicao_pct = (
            Decimal(margem) if margem is not None else None
        )


def test_diz_quantos_estao_abaixo_da_margem_E_quanto_pesam():
    """Três contratos pequenos e três grandes pedem reações diferentes, e a
    contagem sozinha não separa os casos."""
    conteudo = {
        "carteira": [
            _Contrato("A", "100", "5"),
            _Contrato("B", "100", "8"),
            _Contrato("C", "800", "30"),
        ]
    }

    frase = svc._leitura_dos_contratos(conteudo)

    assert "2 contratos estão abaixo" in frase
    assert "20,0% da carteira" in frase


def test_um_contrato_no_singular():
    conteudo = {"carteira": [_Contrato("A", "100", "5"), _Contrato("B", "100", "30")]}

    assert "1 contrato está abaixo" in svc._leitura_dos_contratos(conteudo)


def test_carteira_saudavel_NAO_ganha_frase():
    """"Nenhum contrato está abaixo da margem" é uma frase que só ensina a
    ignorar o espaço onde ela aparece."""
    conteudo = {"carteira": [_Contrato("A", "100", "30")]}

    assert svc._leitura_dos_contratos(conteudo) == ""


def test_contrato_SEM_margem_nao_conta_como_abaixo():
    """`None` é "sem amostra", e tratá-lo como zero poria um contrato novo na
    lista dos deficitários."""
    conteudo = {"carteira": [_Contrato("A", "100", None)]}

    assert svc._leitura_dos_contratos(conteudo) == ""


# ── A montagem, e o que ela protege ─────────────────────────────────


def test_uma_regra_que_estoura_NAO_derruba_a_tela():
    """A frase é o acessório; o número é o conteúdo. Uma regra de leitura que
    derruba a Apresentação de Resultados no meio de uma reunião seria o pior
    troco possível por uma linha de texto."""
    faixa = svc.Faixa(chave="dinheiro", titulo="t", fonte="sankhya")
    faixa.conteudo = {"serie": "isto não é uma lista de linhas"}

    svc._com_leitura({"dinheiro": faixa}, _filtros())

    assert faixa.leitura == ""


def test_faixa_indisponivel_nao_ganha_frase():
    faixa = svc.Faixa(
        chave="dinheiro", titulo="t", fonte="sankhya", disponivel=False
    )

    svc._com_leitura({"dinheiro": faixa}, _filtros())

    assert faixa.leitura == ""


def test_toda_regra_esta_no_dicionario_e_nao_num_elif():
    """Faixa sem regra simplesmente não ganha frase, e acrescentar uma é uma
    linha — não um ramo novo num `elif` de onze braços."""
    assert set(svc.LEITURAS) == {"dinheiro", "contabil", "contratos"}


# ── Na tela ─────────────────────────────────────────────────────────


@pytest.fixture
def diretoria(db):
    pessoa = f.pessoa("diretor_leitura", nome="Diretor")
    f.lotar(pessoa, centro_custo_codigo="1042")
    f.atribuir(
        pessoa,
        f.papel("diretoria_leitura", ["eco.ler.global"], escopo="global"),
        escopo="global",
    )
    return pessoa


@pytest.mark.django_db
def test_a_frase_aparece_ABAIXO_do_carimbo(client, diretoria):
    """A frase LÊ o número; o carimbo diz de onde ele veio. Acima do carimbo,
    ela empurraria a procedência para debaixo do gráfico — e procedência que se
    procura é procedência que ninguém confere."""
    from resultados.models import CompetenciaResultado, Contrato, Fonte

    contrato = Contrato.objects.create(
        fonte=Fonte.PLATFORM, chave_externa="p1", codigo="C-1",
        nome_cliente="Cliente", servico="monitoramento", centro_custo="1042",
        valor_mensal=Decimal("1000"),
    )
    from django.utils import timezone

    hoje = timezone.localdate()
    for atras in (0, 1):
        total = hoje.year * 12 + (hoje.month - 1) - atras
        ano, mes = total // 12, total % 12 + 1
        CompetenciaResultado.objects.create(
            fonte=Fonte.SANKHYA, chave_externa=f"s-{ano}{mes:02d}",
            contrato=contrato, centro_custo="1042", ano=ano, mes=mes,
            receita_bruta=Decimal("1000"),
            margem_contribuicao=Decimal("200") if atras else Decimal("150"),
        )

    client.force_login(diretoria)
    corpo = client.get(reverse("workspace:resultados")).content.decode()

    assert "au-faixa-leitura" in corpo
    assert corpo.index("au-carimbo") < corpo.index("au-faixa-leitura")
