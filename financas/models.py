"""Centro de custo e o que já saiu dele.

## Por que isto agora mora aqui

No projeto anterior, `CentroCusto` e `MovimentacaoFinanceira` eram do iConnect
Platform, e o Workspace lia de lá por um provider. Fazia sentido enquanto os dois
rodavam no mesmo processo.

Com os produtos separados por um link, restavam três saídas: uma API HTTP entre
eles, a bandeja de aprovação perder a barra tripla, ou o Workspace assumir o
orçamento. Assumimos — e o argumento não é de conveniência: **orçamento por
centro de custo é vida corporativa da empresa, não operação de atendimento ao
cliente**. Estava no iConnect por acidente de crescimento, não por desenho.

O que mudou de fato: nada na direção da dependência. `financas` implementa o
contrato `workspace.providers.orcamento.OrcamentoProvider` e se registra no
`ready()`, exatamente como o `dashboard` fazia. A costura sobreviveu à mudança de
casa, que era o ponto de existir uma costura.

## A divisão dos três números

    realizado     o que já saiu           ← Lancamento, deste app
    comprometido  aprovado e não pago     ← workspace.Compromisso
    este pedido   o que está em decisão   ← passado pela bandeja

O acoplamento é por **código** de centro de custo, string, e não por FK. É de
propósito: `workspace.Compromisso` nasce de uma aprovação e não deve travar
apagamento de centro de custo, nem exigir que o Workspace conheça este app.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db import models
from django.utils import timezone


def competencia_de(momento: date | None = None) -> date:
    """Primeiro dia do mês. A competência é o mês, não o dia.

    Duplica de propósito o helper de `workspace.models.orcamento`: replicar sete
    linhas é mais barato que este app importar do outro e inverter a direção da
    dependência que o contrato existe para proteger.
    """
    base = momento or timezone.localdate()
    return base.replace(day=1)


class CentroCustoQuerySet(models.QuerySet):
    def ativos(self):
        return self.filter(ativo=True)


class CentroCusto(models.Model):
    """Onde o dinheiro é debitado, e quanto pode sair por mês."""

    codigo = models.CharField(
        "código", max_length=20, unique=True,
        help_text="Como aparece na lotação da pessoa. É a chave de ligação.",
    )
    nome = models.CharField(max_length=120)

    # `null=True` e não `default=0`: sem orçamento definido não há denominador, e
    # a bandeja precisa dizer "CC sem orçamento" em vez de mostrar 0% — que o
    # aprovador leria como "tem folga". É a mesma distinção do contrato.
    orcamento_mensal = models.DecimalField(
        "orçamento mensal", max_digits=14, decimal_places=2, null=True, blank=True,
        help_text="Vazio significa não definido, que é diferente de zero.",
    )

    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(default=timezone.now, editable=False)

    objects = CentroCustoQuerySet.as_manager()

    class Meta:
        verbose_name = "centro de custo"
        verbose_name_plural = "centros de custo"
        ordering = ["codigo"]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.nome}"


class LancamentoQuerySet(models.QuerySet):
    def do_mes(self, codigo: str, competencia: date):
        return self.filter(
            centro_custo__codigo=codigo, competencia=competencia_de(competencia)
        )


class Lancamento(models.Model):
    """Uma saída de dinheiro já efetivada — o "realizado" da barra tripla."""

    centro_custo = models.ForeignKey(
        CentroCusto, on_delete=models.PROTECT, related_name="lancamentos"
    )
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    competencia = models.DateField(
        db_index=True, help_text="Primeiro dia do mês de referência."
    )
    descricao = models.CharField("descrição", max_length=200, blank=True)
    criado_em = models.DateTimeField(default=timezone.now, editable=False)

    objects = LancamentoQuerySet.as_manager()

    class Meta:
        verbose_name = "lançamento"
        verbose_name_plural = "lançamentos"
        ordering = ["-competencia", "-criado_em"]
        indexes = [
            models.Index(fields=["centro_custo", "competencia"], name="fin_lanc_cc_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.centro_custo.codigo} · R$ {self.valor} · {self.competencia:%m/%Y}"

    def save(self, *args, **kwargs):
        # Normaliza a competência para o dia 1 na gravação, e não só na consulta:
        # duas linhas do mesmo mês com dias diferentes somariam em buckets
        # distintos, e o realizado sairia menor do que é.
        self.competencia = competencia_de(self.competencia)
        super().save(*args, **kwargs)


ZERO = Decimal("0")
