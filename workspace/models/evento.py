"""HST — o que aconteceu com um pedido, e quem fez.

## Por que não bastava o que já existia

`EtapaAprovacao` guarda as DECISÕES: quem aprovou, quando, com que
justificativa. É auditoria de aprovação, e é boa. Mas um pedido tem vida fora
dela — nasceu, foi assumido por alguém, foi concluído, foi cancelado pelo
próprio solicitante, teve o acerto do adiantamento fechado. Nada disso deixava
rastro em lugar nenhum.

A pergunta que não se conseguia responder: **"esse pedido está parado há duas
semanas — o que aconteceu com ele?"**. A resposta vinha de juntar a data de
criação, a etapa de aprovação e o `concluido_em`, e mesmo assim sumia o que
importava: quem assumiu e largou, quem devolveu e por quê.

## Por que uma tabela, e não um campo JSON na solicitação

Um `historico = JSONField(default=list)` seria menos código e responderia à
tela. Não responderia a "quantos pedidos o Fulano concluiu em julho" sem varrer
JSON de todas as linhas, e é essa a segunda pergunta que sempre vem.

## O que este modelo NÃO faz

Não é log de sistema. Nada de acesso, leitura ou navegação entra aqui — só ATO
que muda o estado do pedido. Log que registra tudo é log que ninguém lê, e o
custo aparece na tabela que cresce sem que nada seja consultado.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class AcaoSolicitacao(models.TextChoices):
    """O vocabulário do histórico. Um verbo por linha, no passado."""

    # §43 — o rascunho guardado. Só a PRIMEIRA vez entra no histórico: cada
    # "salvar" seguinte é a mesma pessoa mexendo no próprio texto, e registrar
    # todos encheria a linha do tempo de eventos que não contam nada a ninguém.
    RASCUNHO_GUARDADO = "rascunho_guardado", "Rascunho guardado"
    CRIADA = "criada", "Pedido aberto"
    AUTO_APROVADA = "auto_aprovada", "Aprovado automaticamente"
    # Um degrau da cadeia, com a cadeia continuando. Separado de `APROVADA`
    # porque são fatos diferentes: um diz "fulano assinou", o outro diz "o
    # pedido está liberado". Numa cadeia de três degraus, dois dos três
    # aprovadores só aparecem por causa desta linha.
    ETAPA_APROVADA = "etapa_aprovada", "Aprovado num degrau"
    APROVADA = "aprovada", "Aprovado — liberado"
    DEVOLVIDA = "devolvida", "Devolvido para quem pediu"
    REJEITADA = "rejeitada", "Reprovado"
    CANCELADA = "cancelada", "Cancelado"
    ASSUMIDA = "assumida", "Atendimento assumido"
    CONCLUIDA = "concluida", "Concluído"
    REABERTA = "reaberta", "Reaberto — não resolveu"
    # O pedido que voltou, foi corrigido e seguiu de novo. Linha PRÓPRIA e não
    # `CRIADA` de novo: a timeline precisa distinguir "nasceu" de "voltou
    # corrigido", senão o mesmo pedido aparece nascendo duas vezes e ninguém
    # entende por que a cadeia de aprovação tem dois começos.
    REENVIADA = "reenviada", "Reenviado depois de corrigir"
    ACERTO = "acerto", "Acerto do adiantamento confirmado"


class EventoSolicitacao(models.Model):
    """Uma linha do histórico de um pedido."""

    solicitacao = models.ForeignKey(
        "workspace.SolicitacaoServico",
        on_delete=models.CASCADE,
        related_name="eventos",
    )

    acao = models.CharField(max_length=20, choices=AcaoSolicitacao.choices)

    # `SET_NULL` e nulo permitido: há ato sem gente. A auto-aprovação acontece
    # porque o pedido cabe na política, e inventar um autor para ela seria pior
    # que a coluna vazia — a tela precisa poder dizer "ninguém precisou decidir".
    quem = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="eventos_de_solicitacao",
    )

    observacao = models.CharField(
        max_length=300,
        blank=True,
        help_text="O motivo da devolução, o nome de quem assumiu, o valor do acerto.",
    )

    quando = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        # Do mais antigo para o mais novo: linha do tempo se lê de cima para
        # baixo, e inverter faria a tela mostrar o fim antes do começo.
        ordering = ["quando", "pk"]
        verbose_name = "evento da solicitação"
        verbose_name_plural = "eventos da solicitação"
        indexes = [
            models.Index(fields=["solicitacao", "quando"], name="wks_evento_idx"),
            # Para a segunda pergunta que sempre vem: "quantos o Fulano
            # concluiu em julho?".
            models.Index(fields=["quem", "acao", "quando"], name="wks_evento_quem_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_acao_display()} · {self.quando:%d/%m/%Y %H:%M}"
