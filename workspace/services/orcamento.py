"""Orçamento — os três números da barra tripla, e quem os escritura.

    realizado     o que já saiu           ← provider do domínio financeiro
    comprometido  aprovado e não pago     ← Compromisso, deste app
    este pedido   o que está em decisão   ← passado pelo chamador

É esse conjunto que transforma aprovação de carimbo em decisão: o aprovador vê o
efeito ANTES de decidir, não no fechamento.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from workspace.models.aprovacao import SolicitacaoAprovacao
from workspace.models.orcamento import (
    Compromisso,
    SituacaoCompromisso,
    competencia_de,
)
from workspace.providers import orcamento as provedor


@dataclass(frozen=True)
class ResumoOrcamento:
    """Os números de um centro de custo num mês.

    `orcamento is None` significa **não definido**, não zero. A tela precisa
    dizer "CC sem orçamento — não consigo calcular impacto" em vez de mostrar
    0%, que o aprovador leria como "tem folga".
    """

    centro_custo_codigo: str
    competencia: date
    orcamento: Decimal | None
    realizado: Decimal
    comprometido: Decimal

    @property
    def consumido(self) -> Decimal:
        return self.realizado + self.comprometido

    @property
    def disponivel(self) -> Decimal | None:
        if self.orcamento is None:
            return None
        return self.orcamento - self.consumido

    @property
    def tem_orcamento(self) -> bool:
        return self.orcamento is not None and self.orcamento > 0

    def percentual(self, adicional: Decimal | None = None) -> Decimal | None:
        """Percentual consumido, opcionalmente somando um pedido em decisão."""
        if not self.tem_orcamento:
            return None
        total = self.consumido + (adicional or Decimal("0"))
        return (total / self.orcamento * Decimal("100")).quantize(Decimal("0.1"))

    def cabe(self, valor: Decimal) -> bool:
        """Este valor cabe no que resta?

        Sem orçamento definido devolve `True`: o Portal não é quem barra por
        falta de cadastro — barrar aqui esconderia o problema real, que é o CC
        sem orçamento.
        """
        disponivel = self.disponivel
        if disponivel is None:
            return True
        return valor <= disponivel


def resumo(centro_custo_codigo: str, competencia: date | None = None) -> ResumoOrcamento:
    """Os três números. Sem provider registrado, orçamento e realizado ficam vazios."""
    mes = competencia_de(competencia)
    provider = provedor.obter()

    orcamento = provider.orcamento_mensal(centro_custo_codigo) if provider else None
    realizado = (
        provider.realizado_no_mes(centro_custo_codigo, mes) if provider else Decimal("0")
    )
    comprometido = (
        Compromisso.objects.ativos()
        .do_centro_custo(centro_custo_codigo, mes)
        .total()
    )

    return ResumoOrcamento(
        centro_custo_codigo=centro_custo_codigo,
        competencia=mes,
        orcamento=orcamento,
        realizado=realizado,
        comprometido=comprometido,
    )


# ── Escrituração ────────────────────────────────────────────────────


@transaction.atomic
def escriturar(solicitacao: SolicitacaoAprovacao, quem=None) -> Compromisso | None:
    """Cria o compromisso de uma solicitação aprovada.

    Devolve `None` — sem erro — quando não há o que comprometer: solicitação sem
    valor (férias) ou sem centro de custo. Levantar exceção aqui quebraria a
    aprovação de férias, que é legítima e não toca orçamento.

    Idempotente pela constraint: um retry do sinal não dobra o comprometido.
    """
    if not solicitacao.valor or solicitacao.valor <= 0:
        return None
    if not solicitacao.centro_custo_codigo:
        return None

    existente = Compromisso.objects.filter(solicitacao=solicitacao).first()
    if existente is not None:
        return existente

    return Compromisso.objects.create(
        solicitacao=solicitacao,
        dominio=solicitacao.dominio,
        origem_id=solicitacao.origem_id,
        descricao=solicitacao.titulo[:200],
        centro_custo_codigo=solicitacao.centro_custo_codigo,
        valor=solicitacao.valor,
        competencia=competencia_de(),
        criado_por=quem,
    )


@transaction.atomic
def baixar(compromisso: Compromisso, movimentacao_id: str = "") -> Compromisso:
    """A movimentação real entrou — o compromisso sai do comprometido.

    Não apaga: "o que foi comprometido em setembro" é o dado que permite
    explicar o fechamento depois.
    """
    if compromisso.situacao != SituacaoCompromisso.ATIVO:
        return compromisso

    compromisso.situacao = SituacaoCompromisso.BAIXADO
    compromisso.movimentacao_id = str(movimentacao_id or "")
    compromisso.baixado_em = timezone.now()
    compromisso.save(update_fields=["situacao", "movimentacao_id", "baixado_em"])
    return compromisso


@transaction.atomic
def cancelar(solicitacao: SolicitacaoAprovacao) -> int:
    """Solicitação cancelada ou devolvida libera o orçamento reservado."""
    return (
        Compromisso.objects.filter(solicitacao=solicitacao)
        .ativos()
        .update(situacao=SituacaoCompromisso.CANCELADO)
    )


# ── Ligação com o motor de aprovação ────────────────────────────────


def ao_decidir(sender, solicitacao, decisao, quem, **kwargs) -> None:
    """Ouvinte de `aprovacao_decidida`.

    É aqui que o motor de aprovação e o orçamento se encontram — sem que APR
    conheça `Compromisso` nem orçamento conheça cadeia de aprovação.
    """
    from workspace.services.aprovacao import Decisao

    if decisao == Decisao.APROVAR:
        escriturar(solicitacao, quem=quem)
    elif decisao in (Decisao.DEVOLVER, Decisao.CANCELAR):
        cancelar(solicitacao)


def conectar() -> None:
    """Liga o ouvinte. Chamado no `ready()` do app."""
    from workspace.services.aprovacao import aprovacao_decidida

    # `dispatch_uid` evita ouvinte duplicado quando `ready()` roda duas vezes —
    # acontece em teste e com autoreload do runserver, e duplicado dobraria o
    # comprometido.
    aprovacao_decidida.connect(ao_decidir, dispatch_uid="workspace.orcamento.ao_decidir")
