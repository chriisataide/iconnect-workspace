"""MKT — o radar de oportunidades. §23.

## O problema, e por que o catálogo não o resolve

Marketing já tinha um item de catálogo: "Evento ou patrocínio", com valor,
centro de custo e cadeia de aprovação por faixa. Ele responde bem a uma
pergunta — *aprove esta feira* — e não responde a outra, que é onde a empresa
perde dinheiro.

Alguém encaminha um e-mail sobre uma feira de outubro. O prazo para reservar
stand com preço de inscrição antecipada é junho. O e-mail vira uma conversa, a
conversa esfria, e em agosto alguém lembra: o stand acabou, ou o preço dobrou.
O item de catálogo não podia ajudar, porque ele só existe **depois** de alguém
ter decidido pedir.

O que faltava não era um pedido. Era a lista do que existe, com a data em que a
decisão precisa acontecer.

## Este módulo NÃO aprova nada

Quando a empresa decide ir, abre-se o item de catálogo `evento`, que já passa
pelo gestor e pela diretoria conforme a faixa e já confere o orçamento do centro
de custo. `Oportunidade.solicitacao` guarda o elo.

Um segundo fluxo de aprovação para o mesmo dinheiro seria a duplicação que a
frota já mostrou de perto: dois caminhos para a mesma decisão, e nenhum dos dois
sabendo do outro.

## "Descartada" guarda o motivo, e é o campo mais útil da tabela

Sem ele, a mesma feira volta todo ano e a discussão recomeça do zero. Com ele, a
resposta de doze meses atrás — "público não é o nosso", "o custo não fechou com
o retorno" — está do lado do convite.

## Nada aqui é coletado automaticamente

O cadastro é manual, por decisão explícita: varrer sites de feira para preencher
esta tabela seria coleta automatizada de terceiros, e não é o que este produto
faz. O `site` é um link que alguém colou.
"""

from __future__ import annotations

from datetime import date

from django.conf import settings
from django.db import models
from django.utils import timezone


class TipoOportunidade(models.TextChoices):
    """Na ordem de frequência com que aparecem na caixa de entrada."""

    FEIRA = "feira", "Feira ou exposição"
    CONGRESSO = "congresso", "Congresso ou seminário"
    PATROCINIO = "patrocinio", "Patrocínio"
    PREMIO = "premio", "Prêmio ou selo"
    MIDIA = "midia", "Mídia ou publicidade"
    PARCERIA = "parceria", "Parceria ou associação"


class SituacaoOportunidade(models.TextChoices):
    # A caixa de entrada: alguém soube que existe e ninguém olhou ainda.
    RADAR = "radar", "No radar"
    AVALIANDO = "avaliando", "Em avaliação"
    # Decidido que vai — e a partir daqui quem manda é o pedido do catálogo.
    APROVADA = "aprovada", "Aprovada — pedido aberto"
    DESCARTADA = "descartada", "Descartada"
    REALIZADA = "realizada", "Realizada"


#: Decidido de um jeito ou de outro. A oportunidade sai do radar.
SITUACOES_FECHADAS = (
    SituacaoOportunidade.APROVADA,
    SituacaoOportunidade.DESCARTADA,
    SituacaoOportunidade.REALIZADA,
)


class OportunidadeQuerySet(models.QuerySet):
    def abertas(self):
        return self.exclude(situacao__in=SITUACOES_FECHADAS)

    def com_prazo(self):
        return self.abertas().filter(prazo_decisao__isnull=False)


class Oportunidade(models.Model):
    """Uma feira, um patrocínio, um prêmio — e a data em que é preciso decidir."""

    titulo = models.CharField(max_length=200)
    tipo = models.CharField(
        max_length=15, choices=TipoOportunidade.choices, default=TipoOportunidade.FEIRA
    )
    organizador = models.CharField(max_length=160, blank=True)
    cidade = models.CharField(max_length=120, blank=True)
    # Link colado por alguém, nunca coletado automaticamente — ver o cabeçalho.
    site = models.URLField(max_length=300, blank=True)

    data_inicio = models.DateField(null=True, blank=True)
    data_fim = models.DateField(null=True, blank=True)

    # O CAMPO QUE É A RAZÃO DE EXISTIR DESTE MODELO.
    #
    # Não é a data do evento: é a data em que a resposta precisa estar dada —
    # fim da inscrição antecipada, prazo do edital, último dia para reservar
    # stand. Guardar só a data do evento faria o alerta chegar quando já não
    # adianta.
    prazo_decisao = models.DateField(
        null=True, blank=True, help_text="Até quando é preciso responder."
    )

    custo_estimado = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )
    publico_estimado = models.PositiveIntegerField(null=True, blank=True)
    # Por que vale a pena — o mesmo campo que o item de catálogo exige. Escrito
    # aqui antes da decisão, ele vira o texto do pedido em vez de ser inventado
    # na hora de pedir.
    retorno_esperado = models.TextField(blank=True)

    origem = models.CharField(
        max_length=200, blank=True, help_text="Como a empresa soube — e-mail, cliente, feira anterior."
    )
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="oportunidades",
    )

    situacao = models.CharField(
        max_length=15,
        choices=SituacaoOportunidade.choices,
        default=SituacaoOportunidade.RADAR,
        db_index=True,
    )
    # O campo mais útil da tabela. Sem ele a mesma feira volta todo ano e a
    # discussão recomeça do zero.
    motivo = models.CharField(
        max_length=300, blank=True, help_text="Por que foi descartada, ou o que decidiu."
    )

    # O ELO COM O PEDIDO. Este módulo não aprova nada: quando a empresa decide
    # ir, abre-se o item `evento` do catálogo, que já passa por gestor e
    # diretoria conforme a faixa e já confere o orçamento.
    #
    # `SET_NULL` porque a oportunidade sobrevive ao pedido: o histórico de "a
    # empresa foi a esta feira em 2025" não pode depender de o pedido continuar
    # existindo.
    solicitacao = models.ForeignKey(
        "workspace.SolicitacaoServico",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="oportunidades",
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="oportunidades_cadastradas",
    )

    objects = OportunidadeQuerySet.as_manager()

    class Meta:
        # Prazo mais próximo primeiro, e sem prazo por último. É a ordem de
        # quem precisa agir: `F().asc(nulls_last=True)` e não `prazo_decisao`
        # seco, porque em SQLite o nulo ordena ANTES — e a lista abriria com o
        # que não tem prazo nenhum.
        ordering = [models.F("prazo_decisao").asc(nulls_last=True), "-criado_em"]
        verbose_name = "oportunidade de marketing"
        verbose_name_plural = "oportunidades de marketing"
        indexes = [
            models.Index(fields=["situacao", "prazo_decisao"], name="wks_oport_idx"),
        ]

    def __str__(self) -> str:
        return self.titulo

    @property
    def aberta(self) -> bool:
        return self.situacao not in SITUACOES_FECHADAS

    @property
    def dias_para_decidir(self) -> int | None:
        if self.prazo_decisao is None:
            return None
        return (self.prazo_decisao - timezone.localdate()).days

    @property
    def prazo_perdido(self) -> bool:
        """Perdido é diferente de "não tem prazo", e a tela precisa distinguir.

        Só conta enquanto a oportunidade está aberta: uma feira realizada em
        2024 tem prazo no passado e não é problema de ninguém.
        """
        dias = self.dias_para_decidir
        return self.aberta and dias is not None and dias < 0

    @property
    def periodo(self) -> str:
        """'12 a 15/10/2026', ou só a data quando é um dia só."""
        if self.data_inicio is None:
            return ""
        if self.data_fim is None or self.data_fim == self.data_inicio:
            return self.data_inicio.strftime("%d/%m/%Y")
        if self.data_inicio.month == self.data_fim.month:
            return f"{self.data_inicio.day} a {self.data_fim.strftime('%d/%m/%Y')}"
        return (
            f"{self.data_inicio.strftime('%d/%m')} a "
            f"{self.data_fim.strftime('%d/%m/%Y')}"
        )
