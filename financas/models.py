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

from django.conf import settings
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


# ── Orçamento anual e revisão ───────────────────────────────────────
#
# O que a Onda 8 resolve, e a decisão que ela tomou antes de criar model:
#
# JÁ EXISTIAM DOIS ORÇADOS neste produto. O de `CentroCusto.orcamento_mensal`,
# um número por centro de custo, sem ano e sem histórico, que a bandeja de
# aprovação usa para dizer "isto cabe?". E o de
# `resultados.CompetenciaResultado.receita_orcada`, por centro de custo e mês,
# espelhado do Sankhya, que a tela de Resultados usa para dizer "o mês fechou
# onde deveria?".
#
# Eles NÃO se fundem. O primeiro é o teto de operação e é nosso; o segundo é o
# orçado contábil e é do Sankhya. Quando divergem, isso é divergência entre
# fontes — a regra que a ingestão já criou —, e não algo que um `if` resolve.
# Ver ADR-036.
#
# O defeito que sobrou, e que estes três models corrigem: o teto era um campo
# que qualquer pessoa com `is_staff` editava no `/admin/` sem deixar rastro.


class SituacaoOrcamento(models.TextChoices):
    """Três estados, e o do meio é o produto.

    `rascunho` é onde se monta o ano; `vigente` é onde se para de escrever;
    `encerrado` é o ano que passou. Sem o degrau do meio, o teto seria editável
    o ano inteiro — que é exatamente o que esta onda veio consertar.
    """

    RASCUNHO = "rascunho", "Rascunho"
    VIGENTE = "vigente", "Vigente"
    ENCERRADO = "encerrado", "Encerrado"


class OrcamentoAnualQuerySet(models.QuerySet):
    def vigentes(self):
        return self.filter(situacao=SituacaoOrcamento.VIGENTE)


class OrcamentoAnual(models.Model):
    """O teto de um centro de custo, mês a mês, num ano.

    Anual e não mensal solto porque o orçamento é um ATO de planejamento anual —
    é assim que a empresa o discute, e é assim que o benchmark o organiza
    (módulo 20: "anual e revisão orçamentária"). Doze números soltos não têm
    dono, não têm data de aprovação e não têm o que revisar.
    """

    centro_custo = models.ForeignKey(
        CentroCusto, on_delete=models.CASCADE, related_name="orcamentos"
    )
    ano = models.PositiveSmallIntegerField(db_index=True)
    situacao = models.CharField(
        max_length=10,
        choices=SituacaoOrcamento.choices,
        default=SituacaoOrcamento.RASCUNHO,
        db_index=True,
    )
    #: Por que este ano é assim. Preenchido na montagem, e não na revisão — a
    #: revisão tem o motivo dela.
    observacao = models.CharField(max_length=300, blank=True)

    #: Quem pôs em vigor, e quando. `SET_NULL` porque a pessoa pode sair da
    #: empresa e o orçamento continua sendo o registro de um ato dela.
    vigorou_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orcamentos_vigorados",
    )
    vigorou_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(default=timezone.now, editable=False)

    objects = OrcamentoAnualQuerySet.as_manager()

    class Meta:
        verbose_name = "orçamento anual"
        verbose_name_plural = "orçamentos anuais"
        ordering = ["-ano", "centro_custo__codigo"]
        constraints = [
            models.UniqueConstraint(
                fields=["centro_custo", "ano"], name="fin_orcamento_um_por_ano"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.centro_custo.codigo} · {self.ano}"

    @property
    def vigente(self) -> bool:
        return self.situacao == SituacaoOrcamento.VIGENTE

    @property
    def editavel(self) -> bool:
        """Só em rascunho. Vigente muda por REVISÃO — ver ADR-037."""
        return self.situacao == SituacaoOrcamento.RASCUNHO

    @property
    def total(self) -> Decimal:
        return sum((linha.valor for linha in self.linhas.all()), Decimal("0"))

    def do_mes(self, mes: int) -> Decimal | None:
        """O teto de um mês. `None` quando a linha não existe.

        `None` e não zero, pela mesma razão de `CentroCusto.orcamento_mensal`:
        sem teto definido não há denominador, e a bandeja precisa dizer "sem
        orçamento" em vez de mostrar 0% — que o aprovador leria como folga.
        """
        for linha in self.linhas.all():
            if linha.mes == mes:
                return linha.valor
        return None


class LinhaOrcamento(models.Model):
    """O teto de um mês. Uma linha por mês, e não doze campos numa tabela.

    Uma revisão quase sempre mexe em UM mês — o reajuste entrou em julho, a obra
    escorregou para setembro. Com doze colunas, cada revisão reescreveria a
    linha inteira e o delta por mês teria de ser reconstruído por diferença.
    """

    orcamento = models.ForeignKey(
        OrcamentoAnual, on_delete=models.CASCADE, related_name="linhas"
    )
    mes = models.PositiveSmallIntegerField()
    valor = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))

    class Meta:
        verbose_name = "linha de orçamento"
        verbose_name_plural = "linhas de orçamento"
        ordering = ["mes"]
        constraints = [
            models.UniqueConstraint(
                fields=["orcamento", "mes"], name="fin_linha_um_por_mes"
            ),
            models.CheckConstraint(
                condition=models.Q(mes__gte=1) & models.Q(mes__lte=12),
                name="fin_linha_mes_no_calendario",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.orcamento} · {self.mes:02d} · R$ {self.valor}"


class RevisaoOrcamento(models.Model):
    """A única forma de mexer num orçamento vigente.

    É a regra do benchmark — *"só pode gastar se tiver recurso e fizer a revisão
    orçamentária"* — implementada pelo lado que importa: **o teto não muda sem
    revisão**. Antes desta onda, alguém com `is_staff` editava
    `CentroCusto.orcamento_mensal` e ninguém ficava sabendo.

    Mesmo desenho da reabertura de um quadro de metas (ADR-035): o ato é
    legítimo, e o que não pode é acontecer em silêncio.
    """

    orcamento = models.ForeignKey(
        OrcamentoAnual, on_delete=models.CASCADE, related_name="revisoes"
    )
    #: 1, 2, 3… dentro do orçamento. É por este número que a empresa conversa —
    #: "a segunda revisão do 1042".
    numero = models.PositiveSmallIntegerField()
    motivo = models.CharField(max_length=300)

    #: O DELTA por mês: `{"7": "15000.00", "9": "-8000.00"}`.
    #:
    #: O delta e não o valor final. Guardar o final faria a pergunta "quanto
    #: mudou?" exigir reconstruir a série inteira por diferença — e é essa a
    #: pergunta que se faz numa revisão orçamentária.
    deltas = models.JSONField(default=dict)

    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="revisoes_de_orcamento",
    )
    criada_em = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        verbose_name = "revisão orçamentária"
        verbose_name_plural = "revisões orçamentárias"
        ordering = ["orcamento", "numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["orcamento", "numero"], name="fin_revisao_numero_unico"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.orcamento} · revisão {self.numero}"

    @property
    def total_do_delta(self) -> Decimal:
        return sum((Decimal(v) for v in self.deltas.values()), Decimal("0"))


ZERO = Decimal("0")
