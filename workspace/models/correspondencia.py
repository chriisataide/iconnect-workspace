"""Correspondência — o que chega na recepção e precisa achar o destinatário.

## O problema real

Uma carta chega, fica na recepção, e a pessoa nunca sabe. Duas semanas depois é
uma intimação com prazo vencido, ou um cartão de banco que foi devolvido.

O valor deste módulo **não é o cadastro** — é o aviso. Por isso ele só faz
sentido depois da onda B: registrar sem notificar seria trocar a pilha na mesa
por uma pilha no banco de dados.

## Tipo não é decoração

`intimacao` e `multa` têm prazo legal. O tipo existe para que esses dois entrem
como urgentes sem depender de quem registrou marcar a caixinha — a recepção não
tem como saber o que é urgente, e o remetente também não avisa.

## Destinatário não identificado é caso normal

Carta endereçada à empresa, nome escrito errado, encomenda sem etiqueta. Fingir
que isso não acontece produz um cadastro obrigatório que a recepção preenche com
qualquer nome — e aí a correspondência chega à pessoa errada, que é pior que
ficar na fila de não identificados.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from workspace.storage import ArmazenamentoPrivado, caminho_da_correspondencia


class TipoCorrespondencia(models.TextChoices):
    """Na ordem de frequência, e os dois primeiros com prazo legal."""

    INTIMACAO = "intimacao", "Intimação ou notificação judicial"
    MULTA = "multa", "Multa ou autuação"
    DOCUMENTO = "documento", "Documento"
    ENCOMENDA = "encomenda", "Encomenda"
    CARTA = "carta", "Carta"


# Tipos com prazo legal. Entram como urgentes sem depender de quem registrou
# marcar a caixinha — a recepção não tem como saber o que é urgente.
TIPOS_COM_PRAZO = (TipoCorrespondencia.INTIMACAO, TipoCorrespondencia.MULTA)


class SituacaoCorrespondencia(models.TextChoices):
    AGUARDANDO = "aguardando", "Aguardando retirada"
    ENTREGUE = "entregue", "Entregue"
    DEVOLVIDA = "devolvida", "Devolvida ao remetente"


class CorrespondenciaQuerySet(models.QuerySet):
    def de(self, pessoa):
        if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
            return self.none()
        return self.filter(destinatario=pessoa)

    def aguardando(self):
        return self.filter(situacao=SituacaoCorrespondencia.AGUARDANDO)

    def sem_destinatario(self):
        """A fila que a recepção precisa resolver."""
        return self.aguardando().filter(destinatario__isnull=True)


class Correspondencia(models.Model):
    """Algo físico que chegou e espera alguém."""

    tipo = models.CharField(
        max_length=20,
        choices=TipoCorrespondencia.choices,
        default=TipoCorrespondencia.CARTA,
        db_index=True,
    )
    remetente = models.CharField(max_length=160, blank=True)
    # A EMPRESA, separada do remetente. Não é redundância: o remetente é quem
    # mandou (uma pessoa, um órgão) e a empresa é por onde veio (Correios,
    # transportadora, cartório). São as duas perguntas que a recepção faz na
    # hora de procurar um extravio, e num campo só uma delas sempre se perde.
    empresa = models.CharField(
        max_length=120, blank=True, help_text="Correios, transportadora, cartório."
    )
    # Rastreio é o que permite responder "onde está" sem ligar para ninguém.
    # Sem ele, encomenda sumida vira uma conversa de três dias.
    numero_rastreio = models.CharField(max_length=60, blank=True, db_index=True)
    descricao = models.CharField(
        max_length=200,
        blank=True,
        help_text="O que é, para a pessoa reconhecer sem abrir.",
    )

    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="correspondencias",
        help_text="Vazio quando não foi possível identificar — é caso normal.",
    )
    # Texto livre além da FK: é o nome COMO VEIO no envelope. Quando a FK está
    # vazia, é isto que permite alguém se reconhecer na fila de não identificados.
    nome_no_envelope = models.CharField(max_length=160, blank=True)

    unidade = models.ForeignKey(
        "identidade.Unidade",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="correspondencias",
        help_text="Onde está guardada.",
    )

    urgente = models.BooleanField(
        default=False, help_text="Derivado do tipo quando há prazo legal."
    )
    situacao = models.CharField(
        max_length=20,
        choices=SituacaoCorrespondencia.choices,
        default=SituacaoCorrespondencia.AGUARDANDO,
        db_index=True,
    )

    recebido_em = models.DateTimeField(default=timezone.now, db_index=True)
    recebido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="correspondencias_recebidas",
    )
    retirado_em = models.DateTimeField(null=True, blank=True)
    retirado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="correspondencias_retiradas",
        help_text="Quem retirou de fato — pode não ser o destinatário.",
    )
    observacao = models.CharField(max_length=200, blank=True)

    # A foto do envelope, do lacre, do comprovante de entrega.
    #
    # Campo PRÓPRIO e não FK para `Anexo`: `Anexo.solicitacao` é obrigatório —
    # ele é o arquivo de um pedido do catálogo, não um arquivo qualquer. A FK
    # que estava aqui não podia ser preenchida por nada, e teria ficado nula
    # para sempre sem ninguém notar.
    #
    # Armazenamento privado, nunca MEDIA público: um envelope fotografado mostra
    # nome, endereço e às vezes o conteúdo.
    foto = models.FileField(
        upload_to=caminho_da_correspondencia,
        storage=ArmazenamentoPrivado(),
        max_length=255,
        blank=True,
    )

    # ── A confirmação de QUEM RECEBEU ────────────────────────────────
    #
    # Separada de `retirado_em`, e a distinção é o §6 inteiro: `retirado_em` é a
    # recepção dizendo "entreguei", `confirmado_em` é o destinatário dizendo
    # "recebi". Enquanto só existia o primeiro, a única versão registrada dos
    # fatos era a de quem entregou — e é exatamente essa que não vale nada
    # quando a intimação some.
    confirmado_em = models.DateTimeField(null=True, blank=True)

    objects = CorrespondenciaQuerySet.as_manager()

    class Meta:
        # Urgente primeiro, depois mais antiga: numa fila de retirada, o que
        # espera há mais tempo é o que corre risco.
        ordering = ["-urgente", "recebido_em"]
        verbose_name = "correspondência"
        verbose_name_plural = "correspondências"
        indexes = [
            models.Index(
                fields=["destinatario", "situacao"], name="wks_corresp_pessoa_idx"
            ),
            models.Index(
                fields=["situacao", "-urgente", "recebido_em"],
                name="wks_corresp_fila_idx",
            ),
        ]

    def __str__(self) -> str:
        quem = self.destinatario or self.nome_no_envelope or "não identificado"
        return f"{self.get_tipo_display()} · {quem}"

    def save(self, *args, **kwargs):
        # Derivado, não pedido no formulário: quem registra não tem como saber
        # que intimação tem prazo, e o remetente não avisa.
        if self.tipo in TIPOS_COM_PRAZO:
            self.urgente = True
        super().save(*args, **kwargs)

    @property
    def dias_esperando(self) -> int:
        fim = self.retirado_em or timezone.now()
        return (fim - self.recebido_em).days

    @property
    def aguardando_retirada(self) -> bool:
        return self.situacao == SituacaoCorrespondencia.AGUARDANDO

    @property
    def identificada(self) -> bool:
        return self.destinatario_id is not None

    @property
    def confirmada(self) -> bool:
        return self.confirmado_em is not None

    @property
    def espera_confirmacao(self) -> bool:
        """Entregue pela recepção e ainda sem a palavra de quem recebeu."""
        return (
            self.situacao == SituacaoCorrespondencia.ENTREGUE
            and self.confirmado_em is None
            and self.destinatario_id is not None
        )
