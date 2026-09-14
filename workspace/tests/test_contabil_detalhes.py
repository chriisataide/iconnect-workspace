from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import Mock

from workspace.providers.resultados import ContaDTO, Procedencia
from workspace.services.contabil_detalhes import analisar
from workspace.services import resultados as svc
from workspace.providers.resultados import Escopo


def linha(**kwargs):
    return ContaDTO(procedencia=Procedencia("Sankhya"), **kwargs)


def sinal(natureza):
    return -1 if natureza in {"custo", "imposto", "indireto"} else 1


def test_desvio_respeita_receita_despesa_e_ajustes():
    receita = analisar([linha(realizado=Decimal(110), orcado=Decimal(100))], [], sinal)
    custo = analisar([linha(natureza="custo", realizado=Decimal(110), ajustes=Decimal(5), orcado=Decimal(100))], [], sinal)
    assert receita["desvio"] == 10
    assert receita["situacao"] == "favoravel"
    assert custo["desvio"] == -15
    assert custo["desvio_pct"] == -15
    assert custo["situacao"] == "desfavoravel"


def test_orcamento_parcial_ausente_e_zero_nao_se_confundem():
    parcial = analisar([linha(orcado=Decimal(10)), linha()], [], sinal)
    assert parcial["desvio"] is None
    assert parcial["orcamento_parcial"]
    ausente = analisar([linha()], [], sinal)
    assert not ausente["orcamento_parcial"]
    assert ausente["desvio"] is None
    zero = analisar([linha(orcado=Decimal(0))], [], sinal)
    assert zero["desvio"] == 0
    assert zero["desvio_pct"] is None
    assert zero["situacao"] == "previsto"


def test_composicao_reconcilia_e_historico_distingue_zero_de_ausencia():
    atuais = [linha(contrato="C1", centro_custo="10", realizado=Decimal(80)), linha(centro_custo="10", realizado=Decimal(20))]
    resultado = analisar(atuais, [linha(realizado=Decimal(50))], sinal)
    assert sum(c["valor"] for c in resultado["composicao"]) == 100
    assert resultado["anterior"] == 50
    assert resultado["variacao"] == 50
    assert resultado["variacao_pct"] == 100
    assert analisar(atuais, [], sinal)["anterior"] is None
    zero = analisar(atuais, [linha()], sinal)
    assert zero["anterior"] == 0
    assert zero["variacao_pct"] is None


def test_ajustes_compensados_continuam_visiveis_e_procedencia_e_real():
    data = datetime(2026, 9, 1, tzinfo=timezone.utc)
    a = ContaDTO(procedencia=Procedencia("Sankhya", "ref-1", data), ajustes=Decimal(5))
    b = linha(ajustes=Decimal(-5))
    resultado = analisar([a, b], [], sinal)
    assert len(resultado["ajustes"]) == 2
    assert resultado["ajustes"][0]["procedencia"].chave_externa == "ref-1"
    assert resultado["ultima_carga"] == data
    assert resultado["cargas_incompletas"]


def test_conta_desconhecida_nao_recebe_classificacao_financeira():
    resultado = analisar([linha(desconhecida=True, realizado=Decimal(110), orcado=Decimal(100))], [], sinal)
    assert resultado["situacao"] == "nao_classificado"


def test_mes_anterior_preserva_escopo_e_consulta_uma_vez(monkeypatch):
    atual = linha(grupo_codigo="41101", codigo="41101001", natureza="custo", realizado=Decimal(100))
    anterior = linha(grupo_codigo="41101", codigo="41101001", natureza="custo", realizado=Decimal(80))
    provedor = Mock()
    provedor.por_conta.side_effect = [[atual], [anterior]]
    monkeypatch.setattr(svc.contrato, "obter", lambda tipo: provedor)
    monkeypatch.setattr(svc, "_contratos_sem_custo", lambda *args: [])
    escopo = Escopo(centros_custo=("1042",), contratos=("C1",))
    faixa = svc.contabil(escopo, svc.Filtros(competencia=date(2026, 1, 1), expandidos=("41101",)))
    assert provedor.por_conta.call_count == 2
    assert provedor.por_conta.call_args.args == (escopo, date(2025, 12, 1), date(2025, 12, 31))
    grupo = faixa.conteudo["grupos"][0]
    assert grupo["analise"]["variacao"] == -20
    assert grupo["contas"][0]["analise"]["anterior"] == -80


def test_tabela_fechada_nao_consulta_historico(monkeypatch):
    provedor = Mock()
    provedor.por_conta.return_value = [linha(grupo_codigo="31101")]
    monkeypatch.setattr(svc.contrato, "obter", lambda tipo: provedor)
    monkeypatch.setattr(svc, "_contratos_sem_custo", lambda *args: [])
    svc.contabil(Escopo(), svc.Filtros(competencia=date(2026, 9, 1)))
    assert provedor.por_conta.call_count == 1


def test_detalhes_renderizam_sem_inventar_dados_e_escapam_referencia():
    from django.template.loader import render_to_string
    atual = ContaDTO(procedencia=Procedencia("Sankhya", "<script>alert(1)</script>"), ajustes=Decimal(5))
    html = render_to_string("workspace/resultados/_contabil_detalhes.html", {"analise": analisar([atual], [], sinal)})
    assert "Autor, data do ajuste e justificativa não foram informados" in html
    assert "Sem registros no mês anterior" in html
    assert "&lt;script&gt;" in html
    assert "<script>" not in html
