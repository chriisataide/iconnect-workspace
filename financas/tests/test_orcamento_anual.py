"""O orçamento anual do lado do domínio — o que `financas` promete ao contrato.

Do lado do Workspace, `workspace/tests/test_orcamento_anual.py` prova a
**promessa**: o teto não muda sem revisão, os dois orçados não se fundem, a
grade é de quem responde pelo centro de custo.

Daqui, o que se prova é a **implementação**: que os models guardam o que dizem
guardar, e que as bordas do `/admin/` não abrem a porta que o contrato fechou.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from financas.models import (
    CentroCusto,
    LinhaOrcamento,
    OrcamentoAnual,
    RevisaoOrcamento,
    SituacaoOrcamento,
)

pytestmark = pytest.mark.django_db

ANO = 2026


@pytest.fixture
def centro(db):
    return CentroCusto.objects.create(codigo="1042", nome="Operação SP")


def test_o_total_do_delta_soma_a_revisao_inteira(centro):
    """É o número que a tela mostra ao lado da revisão: quanto o ano mudou."""
    orcamento = OrcamentoAnual.objects.create(centro_custo=centro, ano=ANO)
    revisao = RevisaoOrcamento.objects.create(
        orcamento=orcamento, numero=1, motivo="reajuste",
        deltas={"7": "15000.00", "9": "-8000.00"},
    )

    assert revisao.total_do_delta == Decimal("7000.00")


def test_o_total_do_delta_de_uma_revisao_sem_delta_e_zero(centro):
    orcamento = OrcamentoAnual.objects.create(centro_custo=centro, ano=ANO)
    revisao = RevisaoOrcamento.objects.create(
        orcamento=orcamento, numero=1, motivo="nada", deltas={}
    )

    assert revisao.total_do_delta == Decimal("0")


def test_um_orcamento_por_centro_e_ano(centro):
    """Dois orçamentos do mesmo ano produziriam dois tetos para o mesmo mês — e
    a bandeja não teria o que mostrar."""
    OrcamentoAnual.objects.create(centro_custo=centro, ano=ANO)

    with pytest.raises(IntegrityError), transaction.atomic():
        OrcamentoAnual.objects.create(centro_custo=centro, ano=ANO)


def test_uma_linha_por_mes(centro):
    orcamento = OrcamentoAnual.objects.create(centro_custo=centro, ano=ANO)
    LinhaOrcamento.objects.create(orcamento=orcamento, mes=7, valor=Decimal("100"))

    with pytest.raises(IntegrityError), transaction.atomic():
        LinhaOrcamento.objects.create(orcamento=orcamento, mes=7, valor=Decimal("200"))


def test_mes_fora_do_calendario_e_recusado_pelo_banco(centro):
    """A checagem no BANCO e não só no serviço: um `bulk_create` numa migração
    de dados não passa por serviço nenhum."""
    orcamento = OrcamentoAnual.objects.create(centro_custo=centro, ano=ANO)

    for mes in (0, 13):
        with pytest.raises(IntegrityError), transaction.atomic():
            LinhaOrcamento.objects.create(
                orcamento=orcamento, mes=mes, valor=Decimal("100")
            )


def test_o_numero_da_revisao_e_unico_no_orcamento(centro):
    """É por este número que a empresa conversa — duas "revisão 2" no mesmo ano
    tornam a frase ambígua."""
    orcamento = OrcamentoAnual.objects.create(centro_custo=centro, ano=ANO)
    RevisaoOrcamento.objects.create(orcamento=orcamento, numero=1, motivo="a")

    with pytest.raises(IntegrityError), transaction.atomic():
        RevisaoOrcamento.objects.create(orcamento=orcamento, numero=1, motivo="b")


def test_o_total_do_ano_soma_as_linhas(centro):
    orcamento = OrcamentoAnual.objects.create(centro_custo=centro, ano=ANO)
    for mes in range(1, 13):
        LinhaOrcamento.objects.create(
            orcamento=orcamento, mes=mes, valor=Decimal("1000")
        )

    assert orcamento.total == Decimal("12000")


def test_mes_sem_linha_devolve_none_e_nao_zero(centro):
    """Sem teto definido não há denominador, e a bandeja precisa dizer "sem
    orçamento" em vez de mostrar 0% — que o aprovador leria como folga."""
    orcamento = OrcamentoAnual.objects.create(centro_custo=centro, ano=ANO)

    assert orcamento.do_mes(7) is None
    assert orcamento.total == Decimal("0")


def test_editavel_so_em_rascunho(centro):
    """O ADR-037 em uma linha."""
    orcamento = OrcamentoAnual.objects.create(centro_custo=centro, ano=ANO)
    assert orcamento.editavel is True
    assert orcamento.vigente is False

    orcamento.situacao = SituacaoOrcamento.VIGENTE
    assert orcamento.editavel is False
    assert orcamento.vigente is True

    orcamento.situacao = SituacaoOrcamento.ENCERRADO
    assert orcamento.editavel is False
    assert orcamento.vigente is False


# ── O /admin/ não abre a porta que o contrato fechou ────────────────


def test_a_revisao_e_somente_leitura_no_admin(centro, rf):
    """Editável, a revisão viraria o jeito de mudar o teto sem motivo nem
    autor — que é exatamente o que o ADR-037 existe para impedir."""
    from financas.admin import RevisaoOrcamentoInline

    inline = RevisaoOrcamentoInline(OrcamentoAnual, admin.site)

    assert inline.has_add_permission(rf.get("/")) is False
    assert set(inline.readonly_fields) == set(inline.fields)


def test_a_situacao_do_orcamento_e_somente_leitura_no_admin():
    """Mudar a situação aqui permitiria devolver um vigente ao rascunho e
    reescrever o ano sem revisão nenhuma — o caminho exato que a onda fechou."""
    from financas.admin import OrcamentoAnualAdmin

    opcoes = OrcamentoAnualAdmin(OrcamentoAnual, admin.site)

    assert "situacao" in opcoes.readonly_fields
    assert "vigorou_por" in opcoes.readonly_fields


def test_a_coluna_de_total_do_admin_mostra_o_ano(centro):
    from financas.admin import OrcamentoAnualAdmin

    orcamento = OrcamentoAnual.objects.create(centro_custo=centro, ano=ANO)
    LinhaOrcamento.objects.create(orcamento=orcamento, mes=1, valor=Decimal("2500"))
    opcoes = OrcamentoAnualAdmin(OrcamentoAnual, admin.site)

    assert opcoes.total(orcamento) == "R$ 2500.00"
