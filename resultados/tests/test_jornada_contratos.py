from datetime import date
from decimal import Decimal
from urllib.parse import urlencode

import pytest
from resultados.models import Apontamento, Contrato, Area
from resultados.providers import EspelhoLocal
from workspace.providers.resultados import Escopo
from workspace.services import resultados as svc
from workspace.services.jornada import montar

pytestmark = pytest.mark.django_db


def criar(codigo, cc, area):
    return Contrato.objects.create(fonte="platform", chave_externa=codigo, codigo=codigo,
                                  centro_custo=cc, nome_cliente="Cliente " + codigo, area=area)


def apontar(chave, cc, valor, contrato=None, mes=9):
    return Apontamento.objects.create(fonte="sankhya", chave_externa=chave, centro_custo=cc,
        contrato=contrato, ano=2026, mes=mes, horas_normais=Decimal(100), he_total=Decimal(valor), he_ineficiencia=Decimal(valor))


def test_recorte_contratual_nao_atribui_total_do_cc_e_nao_vaza():
    area = Area.objects.create(codigo="a", nome="Área A")
    a, b = criar("A", "10", area), criar("B", "20", None)
    apontar("cc", "10", 100)
    apontar("a", "10", 30, a)
    apontar("b", "20", 50, b)
    p = EspelhoLocal()
    assert p.apontamentos(Escopo(), date(2026, 9, 1)).he_total == 150
    assert p.apontamentos(Escopo(contratos=("A",)), date(2026, 9, 1)).he_total == 30
    assert p.apontamentos(Escopo(areas=("a",)), date(2026, 9, 1)).he_total == 30
    assert p.apontamentos(Escopo(centros_custo=("10",)), date(2026, 9, 1)).he_total == 100
    assert p.apontamentos(Escopo(contratos=("inexistente",)), date(2026, 9, 1)) is None


def test_painel_meses_ausentes_e_rankings_reconciliam():
    a = criar("A", "10", None)
    apontar("a", "10", 30, a)
    apontar("cc", "10", 100)
    filtros = svc.Filtros(competencia=date(2026, 9, 1), periodo="3m")
    painel = montar(Escopo(), filtros, "he_total", lambda **kw: "/workspace/quadro/?" + urlencode(kw))
    assert painel["sem_vinculo"]
    assert painel["kpis"][1]["valor"] == 100
    assert painel["mensal"].option["series"][0]["data"] == [None, None, 100.0]
    assert painel["rankings"][2].linhas[0][0] == "A · Cliente A"
    assert "contrato=A" in painel["rankings"][2].urls[0]
    assert painel["rankings"][1].linhas[0][1] == "100,00"


def test_csv_chave_separa_cc_de_contrato():
    from cargas.carregador import _filtro_de_negocio
    assert _filtro_de_negocio("apontamento", {"centro_custo": "10", "ano": 2026, "mes": 9})["contrato"] is None
    assert _filtro_de_negocio("apontamento", {"contrato": 1, "centro_custo": "10", "ano": 2026, "mes": 9})["contrato"] == 1


def test_csv_contrato_inexistente_nao_vira_total_do_cc():
    from cargas.conectores.csv import ConectorCSV
    with pytest.raises(ValueError, match="Contrato de apontamento não encontrado"):
        ConectorCSV()._converter({"_entidade": "apontamento", "chave_externa": "x", "contrato": "nao-existe"})


def test_quadro_agregado_nao_e_repetido_por_contrato():
    from resultados.models import QuadroPessoas
    QuadroPessoas.objects.create(fonte="sankhya", chave_externa="q", centro_custo="10", ano=2026, mes=9, efetivo_ativo=20)
    provedor = EspelhoLocal()
    assert provedor.quadro(Escopo(centros_custo=("10",)), date(2026, 9, 1)).efetivo_ativo == 20
    assert provedor.quadro(Escopo(contratos=("A",)), date(2026, 9, 1)) is None


def test_comparacao_busca_mes_anterior_mesmo_com_periodo_mensal():
    a = criar("A", "10", None)
    apontar("antes", "10", 20, a, mes=8)
    apontar("agora", "10", 30, a)
    painel = montar(Escopo(), svc.Filtros(competencia=date(2026, 9, 1), periodo="mes"), "he_total", lambda **kw: "/")
    assert painel["comparacao"]["anterior"] == 20
    assert painel["comparacao"]["diferenca"] == 10
    assert painel["comparacao"]["variacao"] == 50
    assert len(painel["mensal"].linhas) == 1
    assert "A · Cliente A" in painel["leitura"]


def test_ranking_proporcional_soma_bases_e_nao_tira_media_dos_percentuais():
    area = Area.objects.create(codigo="a", nome="Área A")
    a, b = criar("A", "10", area), criar("B", "20", area)
    apontar("a", "10", 20, a)
    linha = apontar("b", "20", 30, b)
    linha.horas_normais = 300
    linha.save()
    painel = montar(Escopo(), svc.Filtros(competencia=date(2026, 9, 1)), "he_total", lambda **kw: "/", ranking="proporcional")
    assert painel["rankings"][0].linhas[0][1] == "12,50"  # 50 / 400, não média de 20% e 10%.
    assert painel["rankings"][2].linhas[0][0] == "A · Cliente A"


def test_cobertura_nao_confunde_registro_zero_com_ausencia_e_composicao_avisa():
    a, b = criar("A", "10", None), criar("B", "20", None)
    linha = apontar("a", "10", 0, a)
    linha.he_servico_extra = 4
    linha.horas_normais = 0
    linha.save()
    painel = montar(Escopo(), svc.Filtros(competencia=date(2026, 9, 1)), "he_total", lambda **kw: "/", ranking="proporcional")
    assert painel["cobertura"]["com_dados"] == 1
    assert painel["cobertura"]["total"] == 2
    assert painel["cobertura"]["sem_dados"][0]["codigo"] == "B"
    assert painel["sem_base"] > 0
    assert not painel["rankings"][2].linhas
    assert painel["detalhes"][0]["diferenca_composicao"] == -4
    assert painel["comparacao"]["diferenca"] is None
