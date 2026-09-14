from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from workspace.providers.resultados import ContratoDTO, Procedencia
from workspace.services.resumo_resultados import organizar_contratos


def contrato(codigo, margem, **campos):
    return ContratoDTO(procedencia=Procedencia("Platform"), codigo=codigo,
                       nome_cliente="Cliente " + codigo, margem_contribuicao_pct=margem,
                       valor_mensal=Decimal(1000), layer=campos.pop("layer", "1"), **campos)


def test_classifica_individualmente_e_identifica_cliente():
    carteira = [contrato("bom", Decimal(25)), contrato("baixo", Decimal(5)),
                contrato("ruim", Decimal(-5)), contrato("normal", Decimal(15)),
                contrato("sem", None), contrato("novo", Decimal(30), layer="sem_amostra")]
    grupos = organizar_contratos(carteira, [], date(2026, 9, 1), lambda c: "/?contrato=" + c)
    assert [i["referencia"] for i in grupos[0]["itens"]] == ["bom"]
    assert [i["referencia"] for i in grupos[1]["itens"]] == ["ruim", "baixo"]
    assert "Cliente bom" in grupos[0]["itens"][0]["sinal"]["titulo"]
    assert grupos[1]["itens"][0]["tipo"] == "contrato"


def test_vencimento_e_foco_manual_do_mesmo_contrato():
    foco = SimpleNamespace(origem_tipo="contrato", origem_ref="C1")
    carteira = [contrato("C1", Decimal(15), fim_vigencia=date(2026, 9, 20))]
    grupos = organizar_contratos(carteira, [foco], date(2026, 9, 1), lambda c: "/" + c)
    item = grupos[1]["itens"][0]
    assert item["foco"] is foco
    assert "20/09/2026" in item["motivo"]
    assert item["url"] == "/C1"


def test_sem_carteira_nao_produz_alerta_tecnico():
    grupos = organizar_contratos([], [], date(2026, 9, 1), lambda c: "/")
    assert all(not grupo["itens"] for grupo in grupos)
