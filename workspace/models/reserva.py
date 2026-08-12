"""Reserva de recursos — salas, veículos, equipamentos.

## O único requisito que não pode falhar

**Duas reservas do mesmo recurso não podem se sobrepor.** Todo o resto deste
módulo é conveniência; isto é a razão de ele existir. Um sistema de reserva que
aceita choque é pior que a planilha compartilhada que ele substitui, porque a
planilha pelo menos deixa o conflito visível.

## Por que a garantia não está no banco

O jeito certo em PostgreSQL é `ExclusionConstraint` com `tstzrange` e o operador
`&&`. Isso é **exclusivo do Postgres**: o desenvolvimento roda SQLite, e a
migração nem aplicaria. Uma constraint que existe em produção e não em
desenvolvimento é pior que nenhuma — o teste local passa e o comportamento real é
outro.

A garantia mora em `services/reserva.py`, dentro de uma transação com
`select_for_update()` na linha do **recurso**. Serializa por recurso, não por
tabela, então duas salas diferentes seguem sendo reservadas em paralelo.

`select_for_update()` é no-op no SQLite — e lá não faz falta, porque o SQLite
serializa escrita no banco inteiro. As duas pontas ficam corretas por caminhos
diferentes, o que está documentado aqui para ninguém "otimizar" o lock depois.

## Encostadas são permitidas

Reserva que termina 11:00 e outra que começa 11:00 **não** é conflito. É o caso
mais comum da vida real, e tratá-lo como choque faria a sala parecer lotada com
metade do dia livre.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class TipoRecurso(models.TextChoices):
    SALA = "sala", "Sala"
    VEICULO = "veiculo", "Veículo"
    EQUIPAMENTO = "equipamento", "Equipamento"


class SituacaoReserva(models.TextChoices):
    CONFIRMADA = "confirmada", "Confirmada"
    CANCELADA = "cancelada", "Cancelada"


class RecursoQuerySet(models.QuerySet):
    def ativos(self):
        return self.filter(ativo=True)


class Recurso(models.Model):
    """Algo que só uma pessoa usa por vez."""

    codigo = models.SlugField(max_length=40, unique=True)
    nome = models.CharField(max_length=120)
    tipo = models.CharField(
        max_length=20, choices=TipoRecurso.choices, default=TipoRecurso.SALA,
        db_index=True,
    )
    descricao = models.CharField(max_length=200, blank=True)

    unidade = models.ForeignKey(
        "identidade.Unidade",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recursos",
        help_text="Onde o recurso fica. Vazio = disponível a toda a empresa.",
    )
    capacidade = models.PositiveSmallIntegerField(
        null=True, blank=True, help_text="Pessoas, para sala. Vazio quando não se aplica."
    )
    # Horas. Recurso preso por três meses bloqueia todo mundo, e o pedido de
    # bloqueio longo tem de passar por alguém — não por um formulário de reserva.
    duracao_maxima_horas = models.PositiveSmallIntegerField(
        default=8, help_text="Acima disto a reserva é recusada."
    )

    ativo = models.BooleanField(default=True, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    objects = RecursoQuerySet.as_manager()

    class Meta:
        # Tipo na ordem do enum (sala é o mais reservado), depois nome.
        ordering = ["tipo", "nome"]
        verbose_name = "recurso"
        verbose_name_plural = "recursos"
        indexes = [
            models.Index(fields=["ativo", "tipo", "nome"], name="wks_recurso_idx"),
        ]

    def __str__(self) -> str:
        return self.nome


class ReservaQuerySet(models.QuerySet):
    def confirmadas(self):
        return self.filter(situacao=SituacaoReserva.CONFIRMADA)

    def de(self, pessoa):
        if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
            return self.none()
        return self.filter(solicitante=pessoa)

    def futuras(self, agora=None):
        return self.filter(fim__gte=agora or timezone.now())

    def que_conflitam(self, recurso, inicio, fim):
        """As reservas confirmadas que se sobrepõem à janela.

        `inicio < outra.fim AND fim > outra.inicio` — estrito nas duas pontas, e
        é o estrito que permite encostadas: uma reserva 10-11 e outra 11-12 não
        se sobrepõem, porque `11 > 11` é falso.
        """
        return self.confirmadas().filter(
            recurso=recurso, inicio__lt=fim, fim__gt=inicio
        )


class Reserva(models.Model):
    """Uma janela de uso de um recurso."""

    recurso = models.ForeignKey(
        Recurso, on_delete=models.PROTECT, related_name="reservas"
    )
    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservas_workspace",
    )
    inicio = models.DateTimeField(db_index=True)
    fim = models.DateTimeField(db_index=True)
    motivo = models.CharField(
        max_length=200,
        blank=True,
        help_text="Opcional. Quem vê a agenda entende por que o recurso está preso.",
    )

    situacao = models.CharField(
        max_length=20, choices=SituacaoReserva.choices,
        default=SituacaoReserva.CONFIRMADA, db_index=True,
    )
    cancelado_em = models.DateTimeField(null=True, blank=True)
    cancelado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reservas_canceladas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    objects = ReservaQuerySet.as_manager()

    class Meta:
        ordering = ["inicio"]
        verbose_name = "reserva"
        verbose_name_plural = "reservas"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(fim__gt=models.F("inicio")),
                name="wks_reserva_fim_depois_do_inicio",
            )
        ]
        indexes = [
            # O acesso mais quente é a busca de conflito:
            # WHERE recurso=? AND situacao='confirmada' AND inicio < ? AND fim > ?
            models.Index(
                fields=["recurso", "situacao", "inicio", "fim"],
                name="wks_reserva_conflito_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.recurso} · {timezone.localtime(self.inicio):%d/%m %H:%M}"

    def clean(self) -> None:
        if self.inicio and self.fim and self.fim <= self.inicio:
            raise ValidationError({"fim": "O fim tem de ser depois do início."})

    @property
    def duracao(self) -> timedelta:
        return self.fim - self.inicio

    @property
    def em_curso(self) -> bool:
        agora = timezone.now()
        return (
            self.situacao == SituacaoReserva.CONFIRMADA
            and self.inicio <= agora < self.fim
        )

    @property
    def passou(self) -> bool:
        return self.fim <= timezone.now()

    @property
    def pode_cancelar(self) -> bool:
        """Cancelar o que já terminou não muda nada e confunde o histórico."""
        return self.situacao == SituacaoReserva.CONFIRMADA and not self.passou
