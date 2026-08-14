"""RMB — reembolso item a item, e o acerto do adiantamento.

## Por que uma linha por compra, e não um valor só

O reembolso nasceu com um campo de valor e um campo de arquivos múltiplos: cinco
cupons somados à mão num número só. Quem aprova recebia "R$ 340,00" e cinco
imagens sem dizer qual é qual, e quem pediu não tinha onde escrever por que
gastou. Conferir era abrir cada anexo e refazer a soma.

`DespesaReembolso` é uma compra: **um comprovante, um valor, um motivo**. A soma
passa a ser do sistema, e o aprovador lê a lista em vez de reconstruí-la.

## Por que o vínculo com o adiantamento mora aqui

Adiantamento e reembolso eram dois pedidos que não se conheciam. Quem recebia
R$ 10 e gastava R$ 5 devolvia por fora — ou não devolvia, e a pendência só
aparecia quando alguém do Financeiro cruzasse as duas listas à mão.

Com `SolicitacaoServico.adiantamento` preenchido, o reembolso É a prestação de
contas daquele adiantamento: a diferença entre o gasto e o adiantado é calculada
e tem um lado obrigatório — a pessoa devolve o que sobrou, ou a empresa paga o
que faltou. É por isso que o campo é uma FK para a própria tabela e não um texto
livre: "adiantamento nº 12" digitado à mão não fecha conta nenhuma.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class SentidoAcerto(models.TextChoices):
    """Para que lado a diferença corre depois da prestação de contas."""

    DEVOLVER = "devolver", "A pessoa devolve à empresa"
    RECEBER = "receber", "A empresa paga à pessoa"
    QUITADO = "quitado", "Nada a acertar"


class DespesaReembolso(models.Model):
    """Uma compra dentro de um reembolso: comprovante, valor e motivo."""

    solicitacao = models.ForeignKey(
        "workspace.SolicitacaoServico",
        on_delete=models.CASCADE,
        related_name="despesas",
    )

    # A ordem em que a pessoa digitou. Reordenar por valor ou por data faria a
    # lista da tela deixar de casar com a lista que ela acabou de preencher.
    ordem = models.PositiveSmallIntegerField(default=0)

    valor = models.DecimalField(max_digits=12, decimal_places=2)
    motivo = models.CharField(
        max_length=200, help_text="Por que esta compra foi feita."
    )

    # `SET_NULL` e não `CASCADE`: se um dia o anexo for removido por expurgo, a
    # linha da despesa precisa continuar existindo — ela é o que fecha a conta
    # com o adiantamento, e apagá-la reabriria uma pendência já resolvida.
    anexo = models.OneToOneField(
        "workspace.Anexo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="despesa",
    )

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ordem", "pk"]
        verbose_name = "despesa de reembolso"
        verbose_name_plural = "despesas de reembolso"
        indexes = [
            models.Index(fields=["solicitacao", "ordem"], name="wks_despesa_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.motivo} · R$ {self.valor}"

    def clean(self) -> None:
        if self.valor is not None and self.valor <= Decimal("0"):
            raise ValidationError({"valor": "O valor da compra tem de ser positivo."})


class AcertoAdiantamento(models.Model):
    """O fechamento da conta entre um adiantamento e a sua prestação.

    Tabela própria, e não campos soltos na solicitação, porque isto é um evento
    financeiro com autor e data: quem confirmou, quando, por qual lado e com
    qual comprovante. Enfiar isso no JSON `dados` do pedido tornaria impossível
    responder "quais acertos ficaram em aberto neste mês" sem varrer JSON.
    """

    prestacao = models.OneToOneField(
        "workspace.SolicitacaoServico",
        on_delete=models.CASCADE,
        related_name="acerto",
        help_text="O reembolso que presta contas do adiantamento.",
    )

    sentido = models.CharField(max_length=10, choices=SentidoAcerto.choices)
    total_adiantado = models.DecimalField(max_digits=12, decimal_places=2)
    total_gasto = models.DecimalField(max_digits=12, decimal_places=2)
    # Sempre o módulo da diferença: o lado já está em `sentido`, e valor
    # negativo em relatório financeiro é lido errado por metade das pessoas.
    diferenca = models.DecimalField(max_digits=12, decimal_places=2)

    # Para onde o dinheiro vai. Na devolução é a conta da empresa (vem de
    # `settings`, e é copiada para cá porque conta bancária muda e o histórico
    # tem de dizer para onde foi na época). No recebimento é a conta da pessoa.
    dados_bancarios = models.TextField(blank=True)

    comprovante = models.OneToOneField(
        "workspace.Anexo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="acerto",
        help_text="Comprovante da devolução, quando sobrou dinheiro.",
    )

    confirmado_em = models.DateTimeField(auto_now_add=True)
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="acertos_confirmados",
    )

    class Meta:
        ordering = ["-confirmado_em"]
        verbose_name = "acerto de adiantamento"
        verbose_name_plural = "acertos de adiantamento"

    def __str__(self) -> str:
        return f"{self.get_sentido_display()} · R$ {self.diferenca}"
