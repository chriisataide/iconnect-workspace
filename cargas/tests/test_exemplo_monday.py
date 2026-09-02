"""A amostra anonimizada é fixture de verdade — e precisa continuar sendo.

O inventário real não é versionado: ele traz nome de cliente e de colaborador.
O que entra no git é a amostra de `docs/exemplos/`, e ela só vale se o conector
souber lê-la. Um exemplo que não é exercitado apodrece na primeira mudança da
API, e aí ele passa a ensinar errado.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cargas.conectores.monday import ConectorMonday

EXEMPLO = Path(__file__).resolve().parents[2] / "docs" / "exemplos" / "monday-inventario-exemplo.json"


@pytest.fixture
def boards():
    return json.loads(EXEMPLO.read_text(encoding="utf-8"))


def test_a_amostra_nao_carrega_dado_real(boards):
    """O JSON de verdade fica fora do git — este aqui é o que entra no lugar.

    A varredura é boba de propósito: ela não sabe distinguir um nome inventado
    de um real. O que ela pega é o descuido de colar o arquivo verdadeiro por
    cima deste, que é como dado de cliente entra num repositório.
    """
    bruto = EXEMPLO.read_text(encoding="utf-8")

    assert "ANONIMIZADA" in bruto, "a amostra precisa se declarar amostra"
    for board in boards:
        assert board["id"].startswith("1000000"), "ids da amostra são sintéticos"
    assert "@" not in bruto, "e-mail numa amostra versionada é vazamento"


def test_o_conector_le_a_amostra_do_jeito_que_ela_esta(boards, settings):
    """Se o parsing mudar e a amostra não, este teste cai — e é o ponto.

    A amostra é o contrato entre o levantamento e o conector.
    """
    settings.MONDAY_BOARDS = {
        "projeto": {
            "board": 1000000001,
            "colunas": {
                "situacao": "status",
                "responsavel": "person",
                "prazo": "date4",
                "percentual_concluido": "numeros",
                "contrato": "conexao_contrato",
                "cliente": "espelho_cliente",
            },
        }
    }
    projeto = boards[0]
    item = {"_entidade": "projeto", "_config": settings.MONDAY_BOARDS["projeto"],
            **projeto["_amostra"]}

    (registro,) = list(ConectorMonday().normalizar([item]))

    assert registro.chave_externa == "2000000001"
    assert registro.dados["nome"] == "Troca de CFTV — Unidade Fictícia I"
    assert registro.dados["situacao"] == "em_andamento"
    assert registro.dados["percentual_concluido"] == 45
    assert registro.dados["contrato"] == "3000000007"
    assert registro.dados["bloqueado"] is False
    # O mirror da amostra vem VAZIO — é exatamente a armadilha documentada.
    assert "cliente" not in registro.dados


def test_a_amostra_tem_um_mirror_vazio(boards):
    """Se alguém "consertar" a amostra preenchendo o mirror, o teste acima
    deixa de provar a armadilha. Este aqui protege o que aquele testa."""
    valores = boards[0]["_amostra"]["column_values"]
    mirror = next(v for v in valores if v["type"] == "mirror")

    assert not mirror["text"], "o mirror vazio É o exemplo — não preencha"


def test_o_exemplo_de_configuracao_aponta_para_a_amostra():
    """`monday-boards-exemplo.py` e o JSON precisam falar dos mesmos boards.

    Documentação que exemplifica ids que não existem no exemplo ao lado é como
    alguém copia uma configuração que nunca funcionou.
    """
    exemplo = (EXEMPLO.parent / "monday-boards-exemplo.py").read_text(encoding="utf-8")

    assert "1000000001" in exemplo and "1000000002" in exemplo
