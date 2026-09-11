"""O plano de contas — D2.

## O que estes testes protegem

- **O plano é cadastro, não espelho.** A carga da madrugada não o reescreve.
- **A analítica herda o degrau do grupo.** Repetir seria vinte lugares para
  divergir, e o vigésimo primeiro nasceria sem nenhum.
- **Conta desconhecida não some.** O código que a fonte mandou fica gravado, e a
  despesa continua no total — despesa que desaparece porque o plano está
  desatualizado é o defeito que ninguém procura no lugar certo.
- **As duas contas da ADB existem.** `41504` e `41505` não estão na referência,
  e são justamente as que fazem o detalhamento ensinar alguma coisa aqui.
"""

from __future__ import annotations

from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.db.models import ProtectedError

from resultados.models import (
    ContaContabil,
    DegrauDRE,
    NaturezaConta,
    ResultadoPorConta,
)
from resultados.plano_de_contas import PLANO, codigo_analitico, total_de_contas


def _semear(*args) -> str:
    saida = StringIO()
    call_command("semear_plano_de_contas", *args, stdout=saida)
    return saida.getvalue()


@pytest.fixture
def plano(db):
    _semear("--aplicar")


# ── A estrutura ─────────────────────────────────────────────────────


@pytest.mark.django_db
def test_sem_aplicar_nao_grava():
    saida = _semear()

    assert ContaContabil.objects.count() == 0
    assert "SIMULAÇÃO" in saida


def test_semeia_o_plano_inteiro(plano):
    assert ContaContabil.objects.count() == total_de_contas() == 149
    assert ContaContabil.objects.filter(pai__isnull=True).count() == len(PLANO)


def test_a_analitica_aponta_para_o_grupo(plano):
    conta = ContaContabil.objects.get(codigo="41101001")

    assert conta.nome == "Salários"
    assert conta.pai.codigo == "41101"
    assert not conta.sintetica
    assert conta.pai.sintetica


def test_a_analitica_HERDA_o_degrau_do_grupo(plano):
    """O degrau mora no grupo. Copiá-lo para cada analítica seria vinte lugares
    para divergir — e a vigésima primeira nasceria sem degrau nenhum, sumindo
    da cascata em silêncio."""
    grupo = ContaContabil.objects.get(codigo="41101")
    analitica = ContaContabil.objects.get(codigo="41101001")

    assert grupo.degrau_dre == DegrauDRE.PESSOAL
    assert analitica.degrau_dre == "", "a analítica não guarda o degrau"
    assert analitica.degrau == DegrauDRE.PESSOAL, "mas responde por ele"


def test_as_duas_contas_da_ADB_existem(plano):
    """`41504` e `41505` não estão no plano de referência — o benchmark é de
    outro ramo. São elas que mostram o turnkey que estourou no equipamento e o
    contrato de manutenção que parece rentável e não é."""
    equipamento = ContaContabil.objects.get(codigo="41504")
    garantia = ContaContabil.objects.get(codigo="41505")

    assert "SEGURANÇA ELETRÔNICA" in equipamento.nome
    assert garantia.nome == "GARANTIA E RETRABALHO"
    assert equipamento.filhas.filter(nome="Geradores de neblina e recargas").exists()
    assert garantia.filhas.filter(nome="Substituição em garantia").exists()


def test_toda_conta_de_resultado_tem_degrau(plano):
    """Grupo sem degrau some da cascata sem avisar.

    As financeiras e as não operacionais ficam de fora de propósito: a DRE deste
    produto vai da receita ao EBITDA, e EBITDA é ANTES de juros. Incluí-las
    faria a cascata não fechar com o número que a faixa do dinheiro mostra.
    """
    sem_degrau = ContaContabil.objects.filter(pai__isnull=True, degrau_dre="")

    assert set(sem_degrau.values_list("natureza", flat=True)) <= {
        NaturezaConta.FINANCEIRO, NaturezaConta.NAO_OPERACIONAL
    }


def test_o_codigo_analitico_e_sequencial_dentro_do_grupo():
    assert codigo_analitico("41101", 0) == "41101001"
    assert codigo_analitico("41101", 20) == "41101021"


# ── Idempotência ────────────────────────────────────────────────────


def test_rodar_de_novo_nao_duplica(plano):
    saida = _semear("--aplicar")

    assert ContaContabil.objects.count() == total_de_contas()
    assert "0 criada(s) · 0 atualizada(s)" in saida


def test_atualiza_o_nome_sem_recriar_a_conta(plano):
    """Recriar mudaria o `pk` e soltaria todo lançamento apontado para ela."""
    conta = ContaContabil.objects.get(codigo="41101001")
    pk_original = conta.pk
    conta.nome = "outro nome"
    conta.save(update_fields=["nome"])

    _semear("--aplicar")

    conta.refresh_from_db()
    assert conta.pk == pk_original
    assert conta.nome == "Salários"


def test_a_conta_com_lancamento_nao_pode_ser_apagada(plano):
    """`PROTECT` e não `CASCADE`: apagar uma conta levaria junto a despesa que
    passou por ela, e o total do mês encolheria sem nada explicar."""
    conta = ContaContabil.objects.get(codigo="41101001")
    ResultadoPorConta.objects.create(
        fonte="sankhya", chave_externa="x", centro_custo="1042",
        ano=2026, mes=9, conta=conta, codigo_origem="41101001",
        valor_realizado=Decimal("100"),
    )

    with pytest.raises(ProtectedError):
        conta.delete()


# ── A conta que a fonte mandou e o plano não conhece ────────────────


def test_conta_desconhecida_NAO_faz_a_despesa_sumir(db):
    """O caso que decide o desenho do bloco D.

    Se a linha fosse descartada, o total do contrato ficaria menor que a soma
    dos lançamentos dele — e ninguém procuraria o erro no plano de contas.
    Guardá-la com `conta` nula e `codigo_origem` preenchido põe o problema na
    tela, que é onde alguém conserta.
    """
    linha = ResultadoPorConta.objects.create(
        fonte="sankhya", chave_externa="y", centro_custo="1042",
        ano=2026, mes=9, conta=None, codigo_origem="49999",
        valor_realizado=Decimal("500"),
    )

    assert linha.conta_id is None
    assert linha.codigo_origem == "49999"
    assert ResultadoPorConta.objects.filter(conta__isnull=True).count() == 1


def test_o_codigo_de_origem_e_guardado_MESMO_quando_a_conta_resolve(plano):
    """É ele que prova de onde a linha veio no dia em que o plano de contas for
    reorganizado."""
    conta = ContaContabil.objects.get(codigo="41101001")
    linha = ResultadoPorConta.objects.create(
        fonte="sankhya", chave_externa="z", centro_custo="1042",
        ano=2026, mes=9, conta=conta, codigo_origem="41101001",
        valor_realizado=Decimal("100"),
    )

    assert linha.codigo_origem == conta.codigo


# ── As colunas do bloco D ───────────────────────────────────────────


def test_realizado_ajustado_soma_a_coluna_do_meio(db):
    """A dinâmica não é `realizado | orçado | variação`. A terceira coluna é
    onde a operação declara o que já aconteceu e ainda não bateu na
    contabilidade — sem ela a reunião vira briga sobre o número."""
    linha = ResultadoPorConta(
        valor_realizado=Decimal("1000"), ajustes=Decimal("250")
    )

    assert linha.realizado_ajustado == Decimal("1250")


def test_orcado_ausente_e_diferente_de_orcado_zero(db):
    """Zero seria lido como "orçaram nada e gastaram", e a variação daria 100%.
    Vazio diz "ninguém orçou", que é outra conversa."""
    linha = ResultadoPorConta(valor_realizado=Decimal("1000"))

    assert linha.valor_orcado is None
