"""`Compromisso` — o valor aprovado e ainda não pago.

## O problema que este modelo resolve

O sistema sabe o **orçamento** (`CentroCusto.orcamento_mensal`) e o **realizado**
(`MovimentacaoFinanceira` agregada). Não sabia o meio do caminho.

    Dois gestores aprovam R$ 12.000 cada no mesmo dia, num CC com R$ 15.000 de
    saldo. Os dois veem "58% consumido" e os dois aprovam de boa-fé. O estouro
    só aparece no fechamento.

Sem `Compromisso`, a barra tripla que especifiquei em Financeiro e Compras é
ficção — mostra um número errado com aparência de precisão, que é pior que não
mostrar número.

## Ciclo de vida

    aprovação  ──▶  ativo  ──▶  baixado    (a movimentação real entrou)
                      └────▶  cancelado  (solicitação cancelada, pedido morreu)

`baixado` não é apagado: o histórico de "o que foi comprometido em setembro" é
justamente o dado que permite explicar o fechamento depois.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class SituacaoCompromisso(models.TextChoices):
    ATIVO = "ativo", "Ativo (aprovado, não pago)"
    BAIXADO = "baixado", "Baixado (movimentação lançada)"
    CANCELADO = "cancelado", "Cancelado"


def competencia_de(momento: date | None = None) -> date:
    """Primeiro dia do mês. A competência é o mês, não o dia."""
    base = momento or timezone.localdate()
    return base.replace(day=1)


class CompromissoQuerySet(models.QuerySet):
    def ativos(self):
        return self.filter(situacao=SituacaoCompromisso.ATIVO)

    def do_centro_custo(self, codigo: str, competencia: date | None = None):
        consulta = self.filter(centro_custo_codigo=codigo)
        if competencia is not None:
            consulta = consulta.filter(competencia=competencia_de(competencia))
        return consulta

    def total(self) -> Decimal:
        """Soma dos valores. Vazio é zero, não None — o chamador faria aritmética."""
        return self.aggregate(t=models.Sum("valor"))["t"] or Decimal("0")


class Compromisso(models.Model):
    """Uma reserva de orçamento criada por uma aprovação."""

    solicitacao = models.ForeignKey(
        "workspace.SolicitacaoAprovacao",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="compromissos",
    )
    # Repetidos da solicitação de propósito: quando ela é apagada, o
    # compromisso baixado ainda precisa dizer de onde veio, para explicar o
    # fechamento do mês.
    dominio = models.CharField(max_length=40, db_index=True)
    origem_id = models.CharField(max_length=40, blank=True)
    descricao = models.CharField(max_length=200)

    # Código, não FK: `CentroCusto` mora em `dashboard` e o Workspace é folha.
    # A resolução do código para o objeto é de quem precisa do objeto.
    centro_custo_codigo = models.CharField(max_length=20, db_index=True)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    competencia = models.DateField(
        db_index=True, help_text="Primeiro dia do mês de referência."
    )

    situacao = models.CharField(
        max_length=20,
        choices=SituacaoCompromisso.choices,
        default=SituacaoCompromisso.ATIVO,
        db_index=True,
    )
    # Id da MovimentacaoFinanceira que baixou. Referência frouxa pelo mesmo
    # motivo do centro de custo.
    movimentacao_id = models.CharField(max_length=40, blank=True)

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="compromissos_criados",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    baixado_em = models.DateTimeField(null=True, blank=True)

    objects = CompromissoQuerySet.as_manager()

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "compromisso"
        verbose_name_plural = "compromissos"
        indexes = [
            models.Index(
                fields=["centro_custo_codigo", "competencia", "situacao"],
                name="wks_comp_cc_idx",
            ),
        ]
        constraints = [
            # Uma aprovação escritura UM compromisso. Sem isto, um retry do
            # sinal dobraria o comprometido do centro de custo — e o número
            # errado com aparência de precisão é o pior resultado possível.
            models.UniqueConstraint(
                fields=["solicitacao"],
                condition=models.Q(solicitacao__isnull=False),
                name="wks_comp_uma_por_solicitacao",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.centro_custo_codigo} · {self.valor} · {self.get_situacao_display()}"

    def clean(self) -> None:
        if self.valor is not None and self.valor <= 0:
            raise ValidationError({"valor": "Compromisso de valor zero ou negativo não existe."})
        if not self.centro_custo_codigo:
            raise ValidationError({"centro_custo_codigo": "Obrigatório."})
