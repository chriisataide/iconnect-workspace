"""O carregador — o que é igual para as quatro fontes.

Testado com um conector falso de propósito. O que se prova aqui — idempotência,
contagem honesta, precedência, parcial que preserva o que entrou — é comum aos
quatro conectores porque **nenhum deles grava**. Se um dia um conector gravar
sozinho, estes testes continuarão passando e não valerão mais nada; é por isso
que `test_isolamento` guarda a direção e este arquivo guarda o comportamento.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cargas.carregador import CargaError, carregar
from cargas.conectores import Janela, Registro
from cargas.models import Divergencia, ExecucaoCarga, RegraPrecedencia, StatusCarga
from resultados.models import Contrato

pytestmark = pytest.mark.django_db


# ── Idempotência ────────────────────────────────────────────────────


def test_reprocessar_a_mesma_janela_nao_duplica_nem_altera(fontes, conector, contrato_bruto):
    """O teste que mais protege esta onda.

    O operador roda de novo por precaução — sempre roda. Se a segunda passada
    escrevesse, `importado_em` avançaria em tudo e a idade do dado na tela
    viraria ficção: o espelho inteiro diria "há 2 min" sem nada realmente novo.
    """
    conector("csv", [contrato_bruto()])

    primeira = carregar("csv", aplicar=True)
    antes = Contrato.objects.get(codigo="C-100")
    carimbo_antes = antes.importado_em

    segunda = carregar("csv", aplicar=True)
    depois = Contrato.objects.get(codigo="C-100")

    assert primeira.criados == 1 and primeira.ignorados == 0
    assert segunda.criados == 0 and segunda.atualizados == 0
    assert segunda.ignorados == 1, "conteúdo idêntico tem de ser IGNORADO, não regravado"
    assert Contrato.objects.count() == 1
    assert depois.importado_em == carimbo_antes, "o relógio não pode avançar sem mudança"


def test_mudanca_de_verdade_atualiza_e_conta(fontes, conector, contrato_bruto):
    conector("csv", [contrato_bruto()])
    carregar("csv", aplicar=True)

    conector("csv", [contrato_bruto(valor_mensal=13500)])
    segunda = carregar("csv", aplicar=True)

    assert segunda.atualizados == 1 and segunda.ignorados == 0
    assert Contrato.objects.get(codigo="C-100").valor_mensal == Decimal("13500")


def test_decimal_escrito_de_outro_jeito_nao_conta_como_mudanca(
    fontes, conector, contrato_bruto
):
    """`12000` e `Decimal("12000.00")` são o mesmo dinheiro.

    Sem a comparação tolerante, toda carga acharia que tudo mudou e `ignorados`
    seria sempre zero — o contador que prova a idempotência ao operador.
    """
    conector("csv", [contrato_bruto(valor_mensal=12000)])
    carregar("csv", aplicar=True)

    conector("csv", [contrato_bruto(valor_mensal=Decimal("12000.00"))])
    assert carregar("csv", aplicar=True).ignorados == 1


# ── Simulação ───────────────────────────────────────────────────────


def test_simulacao_nao_grava_e_fica_marcada(fontes, conector, contrato_bruto):
    """A execução é registrada; o espelho não é tocado.

    A marca `simulacao` existe para o carimbo de frescor nunca sair de uma
    simulação — a tela diria que o dado chegou quando nada foi escrito.
    """
    conector("csv", [contrato_bruto()])

    resultado = carregar("csv")

    assert resultado.criados == 1, "a simulação precisa RELATAR o que faria"
    assert not Contrato.objects.exists()
    assert resultado.execucao.simulacao is True


# ── Falha no meio ───────────────────────────────────────────────────


def test_falha_no_meio_deixa_a_carga_parcial_e_o_espelho_integro(
    fontes, conector, contrato_bruto
):
    """O que entrou é bom e fica.

    Envolver a carga inteira numa transação faria o oposto: uma linha ruim na
    quinta hora descartaria cinco horas de dado bom, e a tela ficaria com a
    carga de ontem sem ninguém entender por quê.
    """
    conector(
        "csv",
        [contrato_bruto("C-1"), contrato_bruto("C-2"), contrato_bruto("C-3")],
        quebra_em=2,
    )

    resultado = carregar("csv", aplicar=True)

    assert resultado.status == StatusCarga.PARCIAL
    assert "caiu no meio" in resultado.erro_resumo
    assert set(Contrato.objects.values_list("codigo", flat=True)) == {"C-1", "C-2"}


def test_falha_antes_da_primeira_linha_e_falha_e_nao_parcial(fontes, conector):
    """Parcial quer dizer "veio parte". Nada veio: é falha.

    Chamar isso de parcial faria a tela mostrar "carga parcial" para uma fonte
    que nunca respondeu, e o operador procuraria o dado que entrou.
    """
    conector("csv", [Registro("contrato", "x", {})], quebra_em=0)

    resultado = carregar("csv", aplicar=True)

    assert resultado.status == StatusCarga.FALHA


def test_erro_de_programacao_no_conector_vira_carga_parcial_e_nao_traceback(
    fontes, conector, contrato_bruto
):
    """Um `KeyError` no `normalizar` de um conector não pode derrubar o cron.

    Sem isto, a janela de carga das outras três fontes nunca começaria — e o
    motivo ficaria num log que ninguém lê, em vez de na tela de fontes.
    """
    conector(
        "csv",
        [contrato_bruto("C-1"), contrato_bruto("C-2")],
        quebra_normalizando=1,
    )

    resultado = carregar("csv", aplicar=True)

    assert resultado.status == StatusCarga.PARCIAL
    assert resultado.erro_resumo
    assert "\n" not in resultado.erro_resumo, "uma linha, sem traceback"
    assert Contrato.objects.filter(codigo="C-1").exists(), "o que entrou fica"


def test_fonte_nao_configurada_nao_e_a_mesma_coisa_que_fonte_quebrada(fontes, conector):
    """Rodar sem o Sankhya configurado é estado normal em desenvolvimento.

    A execução fica registrada para a tela poder dizer "não configurada" em vez
    de "nunca carregou" — que são frases sobre coisas diferentes.
    """
    conector("sankhya", [], disponivel=False)

    resultado = carregar("sankhya", aplicar=True)

    assert resultado.status == StatusCarga.FALHA
    assert "não está configurada" in resultado.erro_resumo


# ── Rejeição de registro ────────────────────────────────────────────


def test_registro_sem_chave_externa_e_rejeitado_e_a_carga_segue(
    fontes, conector, contrato_bruto
):
    """Sem chave de origem não há idempotência.

    A carga seguinte criaria uma segunda linha, e a receita do mês dobraria em
    silêncio. Rejeitar UMA linha e seguir é melhor que recusar o arquivo: quem
    preencheu à mão erra uma linha, não trezentas.
    """
    conector(
        "csv",
        [Registro("contrato", "", {"codigo": "C-9"}), contrato_bruto("C-1")],
    )

    resultado = carregar("csv", aplicar=True)

    assert resultado.rejeitados == 1
    assert resultado.criados == 1
    assert resultado.status == StatusCarga.SUCESSO


def test_entidade_desconhecida_e_rejeitada(fontes, conector):
    conector("csv", [Registro("planeta", "x", {"nome": "Marte"})])

    assert carregar("csv", aplicar=True).rejeitados == 1


# ── Precedência ─────────────────────────────────────────────────────


def test_conflito_resolve_pela_regra_e_registra_a_divergencia(
    fontes, conector, contrato_bruto
):
    """Resolver NÃO é concordar.

    O número entra na tela pela regra, e a divergência aparece na tela de fontes
    com os dois valores lado a lado — para alguém ir descobrir por que os dois
    sistemas discordam. Silenciar aqui trocaria um problema visível por um
    invisível.
    """
    conector("iconnect_platform", [contrato_bruto(valor_mensal=12000)])
    carregar("iconnect_platform", aplicar=True)

    # `semear_fontes` declara: valor_mensal é do Sankhya, porque valor é o que
    # foi FATURADO — e é o faturado que fecha com a contabilidade.
    conector("sankhya", [contrato_bruto(valor_mensal=11000)])
    resultado = carregar("sankhya", aplicar=True)

    assert Contrato.objects.get(codigo="C-100").valor_mensal == Decimal("11000")
    assert resultado.divergencias >= 1
    divergencia = Divergencia.objects.get(campo="valor_mensal")
    assert divergencia.fonte_a == "iconnect_platform"
    assert divergencia.fonte_b == "sankhya"
    assert divergencia.fonte_vencedora == "sankhya"


def test_a_fonte_perdedora_nao_sobrescreve_o_campo_do_vencedor(
    fontes, conector, contrato_bruto
):
    """O Sankhya manda em `valor_mensal`; o Platform manda em `fim_vigencia`.

    Uma linha pode ter os dois — e é o caso normal, não a exceção.
    """
    conector("sankhya", [contrato_bruto(valor_mensal=11000)])
    carregar("sankhya", aplicar=True)

    conector(
        "iconnect_platform",
        [contrato_bruto(valor_mensal=99999, fim_vigencia=date(2027, 6, 30))],
    )
    carregar("iconnect_platform", aplicar=True)

    contrato = Contrato.objects.get(codigo="C-100")
    assert contrato.valor_mensal == Decimal("11000"), "o Platform não manda no valor"
    assert contrato.fim_vigencia == date(2027, 6, 30), "mas manda na vigência"


def test_sem_regra_declarada_a_ultima_carga_vence(fontes, conector, contrato_bruto):
    """Campo sem regra não trava a carga.

    Exigir uma regra por campo faria toda coluna nova precisar de uma decisão de
    negócio antes de existir — e o efeito prático seria ninguém acrescentar
    coluna nenhuma.
    """
    RegraPrecedencia.objects.filter(campo="regional").delete()
    conector("sankhya", [contrato_bruto(regional="Sudeste")])
    carregar("sankhya", aplicar=True)

    conector("iconnect_platform", [contrato_bruto(regional="Sul")])
    carregar("iconnect_platform", aplicar=True)

    assert Contrato.objects.get(codigo="C-100").regional == "Sul"


# ── Registro da execução ────────────────────────────────────────────


def test_a_execucao_guarda_as_contagens_e_a_janela(fontes, conector, contrato_bruto):
    conector("csv", [contrato_bruto("C-1"), contrato_bruto("C-2")])
    janela = Janela(de=date(2026, 8, 1), ate=date(2026, 8, 31))

    carregar("csv", janela, aplicar=True)
    execucao = ExecucaoCarga.objects.filter(status=StatusCarga.SUCESSO).latest("iniciada_em")

    assert (execucao.lidos, execucao.criados) == (2, 2)
    assert execucao.janela_de == date(2026, 8, 1)
    assert execucao.terminada_em is not None


def test_fonte_sem_cadastro_nao_carrega(db, conector):
    """Carga sem `FonteDados` seria dado sem procedência — e o espelho todo
    depende de a procedência existir."""
    conector("csv", [])

    with pytest.raises(CargaError, match="não está cadastrada"):
        carregar("csv", aplicar=True)


def test_fonte_desativada_nao_carrega(fontes, conector):
    """Desativar é a forma de parar uma fonte que está mandando lixo.

    Se a carga rodasse assim mesmo, desativar não serviria para nada — e é o
    único freio que quem opera tem às três da manhã.
    """
    fontes["csv"].ativa = False
    fontes["csv"].save()
    conector("csv", [])

    with pytest.raises(CargaError, match="desativada"):
        carregar("csv", aplicar=True)
