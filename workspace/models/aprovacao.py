"""APR — o motor de aprovação. Uma bandeja, não cinco.

Férias, reembolso e compra caem na **mesma fila**, porque aprovação é aprovação
e o domínio é dado de roteamento. O gestor tem uma fila; se tivesse cinco,
esqueceria quatro.

## O que este módulo NÃO sabe

Não sabe o que é um reembolso. Sabe que existe *algo* de R$ 840, no centro de
custo 1042, pedido pela Ana, que precisa de decisão. O domínio é dono do objeto;
APR é dono do fluxo.

A ligação é frouxa de propósito — `dominio` + `origem_id`, não
`GenericForeignKey`. Motivo: GFK cria dependência de `ContentType` em toda
consulta da bandeja, e a bandeja é a tela mais carregada do produto. Com string
+ id, listar 20 solicitações é uma query.

## Cadeia por faixa de valor

`RegraAprovacao` responde "acima de X, acrescente uma etapa de tipo Y". A cadeia
de uma solicitação é a soma das regras cujo `valor_minimo` ela alcança. Assim:

    R$   500 → gestor direto
    R$ 5.000 → gestor direto + gestor do centro de custo
    R$ 50.000 → gestor direto + gestor do CC + diretoria

Os limites são **dados, não código** — a pergunta "qual o teto por nível?" ainda
não foi respondida, e chutar em código significaria refatorar depois.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class SituacaoSolicitacao(models.TextChoices):
    AGUARDANDO = "aguardando", "Aguardando aprovação"
    APROVADA = "aprovada", "Aprovada"
    DEVOLVIDA = "devolvida", "Devolvida"
    CANCELADA = "cancelada", "Cancelada"


class SituacaoEtapa(models.TextChoices):
    PENDENTE = "pendente", "Pendente"
    APROVADA = "aprovada", "Aprovada"
    DEVOLVIDA = "devolvida", "Devolvida"
    PULADA = "pulada", "Pulada"


class TipoAprovador(models.TextChoices):
    GESTOR_DIRETO = "gestor_direto", "Gestor direto do solicitante"
    PAPEL = "papel", "Quem tiver o papel"
    NOMINAL = "nominal", "Pessoa específica"


class RegraAprovacao(models.Model):
    """Acima de `valor_minimo`, acrescente uma etapa deste tipo."""

    dominio = models.CharField(
        max_length=40,
        default="*",
        help_text="`*` vale para todos. `fin.reembolso` só para reembolso.",
        db_index=True,
    )
    valor_minimo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        help_text="A etapa entra quando o valor alcança este mínimo. 0 = sempre.",
    )
    tipo = models.CharField(max_length=20, choices=TipoAprovador.choices)
    papel = models.ForeignKey(
        "identidade.Papel",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="regras_aprovacao",
    )
    aprovador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="regras_aprovacao",
    )
    ordem = models.PositiveSmallIntegerField(default=10)
    ativa = models.BooleanField(default=True, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["dominio", "ordem", "valor_minimo"]
        verbose_name = "regra de aprovação"
        verbose_name_plural = "regras de aprovação"
        indexes = [
            models.Index(fields=["dominio", "ativa", "ordem"], name="wks_regra_apr_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.dominio} ≥ {self.valor_minimo} → {self.get_tipo_display()}"

    def clean(self) -> None:
        if self.tipo == TipoAprovador.PAPEL and not self.papel_id:
            raise ValidationError({"papel": "Tipo `papel` exige o papel."})
        if self.tipo == TipoAprovador.NOMINAL and not self.aprovador_id:
            raise ValidationError({"aprovador": "Tipo `nominal` exige o aprovador."})
        if self.valor_minimo < 0:
            raise ValidationError({"valor_minimo": "Não pode ser negativo."})


class SolicitacaoQuerySet(models.QuerySet):
    def aguardando(self):
        return self.filter(situacao=SituacaoSolicitacao.AGUARDANDO)

    def do_dominio(self, dominio: str):
        return self.filter(dominio=dominio)


class SolicitacaoAprovacao(models.Model):
    """Algo que precisa de decisão. O domínio guarda o quê; aqui está o fluxo."""

    dominio = models.CharField(max_length=40, db_index=True)
    origem_id = models.CharField(
        max_length=40, blank=True, help_text="Id do objeto no domínio de origem."
    )

    titulo = models.CharField(max_length=200)
    resumo = models.CharField(max_length=300, blank=True)
    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="solicitacoes_aprovacao"
    )

    # Nula de propósito: férias não têm valor, e forçar 0 faria toda regra de
    # faixa de valor casar com elas.
    valor = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    centro_custo_codigo = models.CharField(max_length=20, blank=True, db_index=True)

    situacao = models.CharField(
        max_length=20,
        choices=SituacaoSolicitacao.choices,
        default=SituacaoSolicitacao.AGUARDANDO,
        db_index=True,
    )

    # Dossiê que o domínio quer expor ao aprovador sem que APR conheça o schema.
    dados = models.JSONField(default=dict, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    decidido_em = models.DateTimeField(null=True, blank=True)

    objects = SolicitacaoQuerySet.as_manager()

    class Meta:
        ordering = ["criado_em"]  # mais antiga primeiro: é quem está esperando
        verbose_name = "solicitação de aprovação"
        verbose_name_plural = "solicitações de aprovação"
        indexes = [
            models.Index(fields=["situacao", "criado_em"], name="wks_solic_bandeja_idx"),
            models.Index(fields=["dominio", "origem_id"], name="wks_solic_origem_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.dominio} · {self.titulo}"

    @property
    def etapa_atual(self):
        """A etapa que está esperando decisão, ou None."""
        return self.etapas.filter(situacao=SituacaoEtapa.PENDENTE).order_by("ordem").first()

    @property
    def dias_esperando(self) -> int:
        fim = self.decidido_em or timezone.now()
        return (fim - self.criado_em).days


class EtapaAprovacao(models.Model):
    """Um degrau da cadeia.

    `aprovador` nominal e `papel` são alternativos: etapa por papel não é de
    ninguém em particular — é de quem tiver o papel. É assim que fila de
    aprovação funciona de verdade, e é o que permite alguém aprovar quando o
    titular está de férias sem precisar de delegação explícita.
    """

    solicitacao = models.ForeignKey(
        SolicitacaoAprovacao, on_delete=models.CASCADE, related_name="etapas"
    )
    ordem = models.PositiveSmallIntegerField()

    aprovador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="etapas_como_aprovador",
    )
    papel = models.ForeignKey(
        "identidade.Papel",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="etapas_aprovacao",
    )

    situacao = models.CharField(
        max_length=20, choices=SituacaoEtapa.choices, default=SituacaoEtapa.PENDENTE, db_index=True
    )

    # Quem DE FATO decidiu. Diferente de `aprovador` quando houve delegação ou
    # quando a etapa era por papel. Registrar os dois é requisito de auditoria:
    # "quem devia" e "quem fez" não são a mesma pergunta.
    decidido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="etapas_decididas",
    )
    decidido_em = models.DateTimeField(null=True, blank=True)
    justificativa = models.TextField(blank=True)
    motivo_pulo = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["solicitacao", "ordem"]
        verbose_name = "etapa de aprovação"
        verbose_name_plural = "etapas de aprovação"
        constraints = [
            models.UniqueConstraint(
                fields=["solicitacao", "ordem"], name="wks_etapa_ordem_unica"
            )
        ]
        indexes = [
            models.Index(fields=["aprovador", "situacao"], name="wks_etapa_bandeja_idx"),
        ]

    def __str__(self) -> str:
        quem = self.aprovador or self.papel or "?"
        return f"{self.solicitacao_id} · #{self.ordem} · {quem}"

    def clean(self) -> None:
        if not self.aprovador_id and not self.papel_id:
            raise ValidationError("A etapa precisa de aprovador nominal ou de papel.")
