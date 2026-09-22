"""O motor das pendências de ponto: planilha, telefone, agrupamento, mensagem.

Nenhum teste aqui toca banco, rede ou Docker. O motor recebe bytes e devolve
dados — é o que permite cobrir a regra de telefone, que é onde a automação
original errava, sem subir n8n nenhum.
"""

from __future__ import annotations

import io

import openpyxl
import pytest

from workspace.services import ponto

CABECALHO = [
    "Data", "Código", "Senha", "CPF", "Funcionário", "Local de Trabalho",
    "Entrada", "Pausa", "Retorno", "Saída", "Jornada", "Observação", None, "Telefone",
]


def planilha(linhas: list[dict], cabecalho=None) -> bytes:
    """Monta um XLSX em memória com o mesmo formato do export do PontoTel."""
    colunas = CABECALHO if cabecalho is None else cabecalho
    livro = openpyxl.Workbook()
    aba = livro.active
    aba.append(colunas)
    for linha in linhas:
        aba.append([linha.get(c) for c in colunas])
    buffer = io.BytesIO()
    livro.save(buffer)
    return buffer.getvalue()


def linha(**campos):
    base = {
        "Data": "15/09/2026",
        "Código": "1511",
        "Senha": "3789",
        "CPF": "11122233344",
        "Funcionário": "JOAO SILVA",
        "Local de Trabalho": "COMERCIAL - Campinas",
        "Entrada": "08:00",
        "Pausa": "12:00",
        "Retorno": "13:00",
        "Saída": "18:00",
        "Jornada": "08:00 - 12:00 - 13:00 - 18:00",
        "Observação": "",
        "Telefone": "(019) 98888-7777",
    }
    base.update(campos)
    return base


# ── Telefone ────────────────────────────────────────────────────────
#
# O grupo mais importante do arquivo. A automação original reprovava 57 de 57
# telefones da planilha real por causa do zero do DDD, e como o modo de teste
# troca o destino antes do envio, nada denunciava o erro.


@pytest.mark.parametrize(
    "bruto,esperado",
    [
        ("(019) 98888-7777", "5519988887777"),   # o formato do PontoTel, com zero
        ("(19) 99555-0001", "5519995550001"),    # sem o zero
        ("19995550001", "5519995550001"),        # só dígitos, sem DDI
        ("5519995550001", "5519995550001"),      # já completo
        ("+55 (19) 99555-0001", "5519995550001"),
        ("  (019) 98888-7777  ", "5519988887777"),
    ],
)
def test_telefone_valido_vira_ddi_ddd_numero(bruto, esperado):
    assert ponto.normalizar_telefone(bruto) == esperado


@pytest.mark.parametrize(
    "bruto",
    [
        "",
        None,
        "   ",
        "=VLOOKUP(A1;Base!A:B;2;0)",   # §35 — fórmula não é telefone
        "=PROCV(A1;Base!A:B;2;0)",
        "1934567890",                  # fixo: não recebe WhatsApp
        "(19) 3456-7890",
        "123",
        "abcdefghijk",
        "00000000000",
    ],
)
def test_telefone_invalido_vira_vazio(bruto):
    assert ponto.normalizar_telefone(bruto) == ""


def test_o_zero_do_ddd_e_removido_e_nao_confundido_com_ddi():
    """`019` é o DDD 19 com zero de tronco, não um DDI."""
    assert ponto.normalizar_telefone("(019) 98888-7777") == "5519988887777"
    assert ponto.normalizar_telefone("(19) 98888-7777") == "5519988887777"


def test_mascara_esconde_o_meio_e_mantem_o_fim():
    assert ponto.mascarar_telefone("5519995550001") == "(19) 9****-0001"
    assert ponto.mascarar_telefone("") == ""


# ── Leitura da planilha ─────────────────────────────────────────────


def test_xlsx_valido_e_lido():
    linhas = ponto.ler_planilha(planilha([linha()]), "ajuste.xlsx")
    assert len(linhas) == 1
    assert linhas[0]["Funcionário"] == "JOAO SILVA"


def test_cpf_e_senha_nunca_entram_nos_dados():
    """Dado sensível que a funcionalidade não usa não é guardado."""
    linhas = ponto.ler_planilha(planilha([linha()]), "ajuste.xlsx")
    assert "CPF" not in linhas[0]
    assert "Senha" not in linhas[0]
    assert "11122233344" not in str(linhas[0])


def test_arquivo_vazio_e_recusado():
    with pytest.raises(ponto.PlanilhaInvalida):
        ponto.ler_planilha(b"", "vazio.xlsx")


def test_arquivo_que_nao_e_planilha_e_recusado():
    with pytest.raises(ponto.PlanilhaInvalida):
        ponto.ler_planilha(b"isto aqui nao e um xlsx", "falso.xlsx")


def test_planilha_sem_colunas_obrigatorias_diz_quais_faltam():
    cabecalho = ["Data", "Local de Trabalho", "Pausa", "Retorno", "Saída"]
    with pytest.raises(ponto.PlanilhaInvalida) as erro:
        ponto.ler_planilha(planilha([{}], cabecalho=cabecalho), "ruim.xlsx")
    assert set(erro.value.colunas_ausentes) == {"Funcionário", "Entrada"}


def test_a_ordem_das_colunas_nao_importa():
    invertido = list(reversed(CABECALHO))
    linhas = ponto.ler_planilha(planilha([linha()], cabecalho=invertido), "ajuste.xlsx")
    assert linhas[0]["Funcionário"] == "JOAO SILVA"


def test_coluna_sem_titulo_e_ignorada():
    """O export real tem uma coluna em branco entre Observação e Telefone."""
    linhas = ponto.ler_planilha(planilha([linha()]), "ajuste.xlsx")
    assert None not in linhas[0]
    assert "" not in linhas[0]


def test_planilha_grande_demais_e_recusada():
    uma = linha()
    muitas = [uma] * (ponto.MAXIMO_LINHAS + 1)
    with pytest.raises(ponto.PlanilhaInvalida, match="máximo"):
        ponto.ler_planilha(planilha(muitas), "gigante.xlsx")


def test_csv_tambem_e_aceito():
    texto = "Data;Funcionário;Entrada;Pausa;Retorno;Saída;Telefone\n"
    texto += "15/09/2026;JOAO SILVA;;12:00;13:00;18:00;(019) 98888-7777\n"
    linhas = ponto.ler_planilha(texto.encode("utf-8"), "ajuste.csv")
    assert linhas[0]["Funcionário"] == "JOAO SILVA"


# ── Motivo da pendência ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "campos,esperado",
    [
        ({"Entrada": ""}, "ausência de marcação de entrada"),
        ({"Pausa": ""}, "ausência de marcação de pausa"),
        ({"Retorno": ""}, "ausência de marcação de retorno"),
        ({"Saída": ""}, "ausência de marcação de saída"),
        ({"Entrada": "", "Saída": ""}, "ausência de marcação de entrada e saída"),
        (
            {"Entrada": "", "Pausa": "", "Retorno": ""},
            "ausência de marcação de entrada, pausa e retorno",
        ),
    ],
)
def test_marcacao_vazia_vira_frase(campos, esperado):
    assert ponto.motivo_da_linha(linha(**campos)) == esperado


def test_tudo_preenchido_usa_a_observacao():
    dado = linha(Observação="Pares de marcações incompletos.  ")
    assert ponto.motivo_da_linha(dado) == "Pares de marcações incompletos"


def test_tudo_preenchido_e_sem_observacao_tem_frase_generica():
    assert ponto.motivo_da_linha(linha()) == ponto.MOTIVO_GENERICO


# ── Agrupamento — §11 ───────────────────────────────────────────────


def test_um_colaborador_com_cinco_linhas_vira_uma_mensagem():
    """O teste que o §39 pede: 5 linhas → 1 colaborador, 5 pendências, 1 mensagem."""
    linhas = [
        linha(Data=f"1{i}/09/2026", Entrada="") for i in range(1, 6)
    ]
    colaboradores = ponto.agrupar(ponto.ler_planilha(planilha(linhas), "a.xlsx"))

    assert len(colaboradores) == 1
    assert len(colaboradores[0].pendencias) == 5
    assert colaboradores[0].mensagem().count("Prezado(a)") == 1


def test_pessoas_diferentes_viram_grupos_diferentes():
    linhas = [linha(Funcionário="JOAO SILVA"), linha(Funcionário="MARIA LIMA")]
    assert len(ponto.agrupar(ponto.ler_planilha(planilha(linhas), "a.xlsx"))) == 2


def test_o_mesmo_dia_e_motivo_nao_entra_duas_vezes():
    """O export duplica linha quando a competência é reprocessada."""
    repetida = linha(Data="15/09/2026", Entrada="")
    colaboradores = ponto.agrupar(
        ponto.ler_planilha(planilha([repetida, repetida, repetida]), "a.xlsx")
    )
    assert len(colaboradores[0].pendencias) == 1


def test_as_pendencias_saem_em_ordem_de_data():
    linhas = [
        linha(Data="21/09/2026", Entrada=""),
        linha(Data="14/09/2026", Entrada=""),
        linha(Data="16/09/2026", Entrada=""),
    ]
    colaboradores = ponto.agrupar(ponto.ler_planilha(planilha(linhas), "a.xlsx"))
    assert [p.data for p in colaboradores[0].pendencias] == [
        "14/09/2026", "16/09/2026", "21/09/2026",
    ]


def test_o_telefone_vem_de_qualquer_linha_da_pessoa():
    linhas = [
        linha(Data="14/09/2026", Telefone="", Entrada=""),
        linha(Data="15/09/2026", Telefone="(019) 98888-7777", Entrada=""),
    ]
    colaborador = ponto.agrupar(ponto.ler_planilha(planilha(linhas), "a.xlsx"))[0]
    assert colaborador.telefone_normalizado == "5519988887777"


def test_colaborador_com_formula_no_telefone_nao_pode_enviar():
    dado = linha(Telefone="=VLOOKUP(A1;Base!A:B;2;0)", Entrada="")
    colaborador = ponto.agrupar(ponto.ler_planilha(planilha([dado]), "a.xlsx"))[0]
    assert colaborador.tem_telefone is False
    assert colaborador.motivo_sem_telefone == "Telefone não disponível"


def test_colaborador_com_telefone_errado_e_marcado_como_invalido():
    dado = linha(Telefone="(19) 3456-7890", Entrada="")
    colaborador = ponto.agrupar(ponto.ler_planilha(planilha([dado]), "a.xlsx"))[0]
    assert colaborador.motivo_sem_telefone == "Telefone inválido"


# ── Mensagem — §16 ──────────────────────────────────────────────────


def test_a_mensagem_tem_o_texto_aprovado_e_as_pendencias_no_lugar():
    linhas = [
        linha(Data="15/09/2026", Entrada=""),
        linha(Data="16/09/2026", Saída=""),
    ]
    mensagem = ponto.agrupar(ponto.ler_planilha(planilha(linhas), "a.xlsx"))[0].mensagem()

    assert mensagem.startswith("Prezado(a) colaborador(a),")
    assert "• 15/09/2026 — ausência de marcação de entrada" in mensagem
    assert "• 16/09/2026 — ausência de marcação de saída" in mensagem
    assert "PontoTel" in mensagem
    assert mensagem.rstrip().endswith("Recursos Humanos")
    assert "{pendencias}" not in mensagem


# ── A planilha real ─────────────────────────────────────────────────


def test_a_planilha_de_verdade_e_processada_inteira():
    """Regressão do bug do DDD: com o arquivo real, ninguém pode ficar sem telefone.

    Antes da correção do zero de tronco este número era 0 de 57.
    """
    from pathlib import Path

    from django.conf import settings

    caminho = (
        Path(settings.BASE_DIR)
        / "workspace/rh/integrations/ponto_whatsapp/arquivos/ajuste-de-ponto.xlsx"
    )
    if not caminho.exists():  # pragma: no cover - o arquivo não é versionado
        pytest.skip("a planilha de exemplo não está neste checkout")

    colaboradores = ponto.agrupar(ponto.ler_planilha(caminho.read_bytes(), caminho.name))

    assert len(colaboradores) == 57
    assert sum(len(c.pendencias) for c in colaboradores) == 94
    assert all(c.tem_telefone for c in colaboradores)
