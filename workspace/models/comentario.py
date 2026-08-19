"""Comentário numa solicitação — o degrau que faltava no workflow (§45).

## O que ele conserta

Um atendente precisa perguntar "qual o número de série do equipamento?". Hoje
tem duas saídas, e as duas são ruins:

* **Devolver.** Bounce do pedido inteiro para quem pediu, com o pedido saindo da
  fila, perdendo a posição e voltando como se estivesse errado. Devolver quer
  dizer "corrija e reenvie", e não é isso que ele quer dizer.
* **Mandar mensagem por fora.** Funciona, e some. Três meses depois ninguém sabe
  por que aquele pedido demorou onze dias — a explicação está no WhatsApp de
  duas pessoas.

O comentário é a terceira: o pedido continua onde está, a pergunta fica no
próprio pedido, e o histórico responde sozinho.

## Interno e visível, e por que os dois

Nem tudo que a área escreve é para quem pediu. "Conferir se o contrato com o
fornecedor cobre isso" é nota entre atendentes; "precisamos do número de série"
é pergunta ao solicitante.

Com um tipo só, o produto obriga a escolher entre dois males: ou toda nota
interna vaza, ou nenhuma pergunta chega. A flag existe para que a área possa
escrever as duas coisas no mesmo lugar.

**O padrão é VISÍVEL.** Nota interna que vaza é constrangimento; pergunta que
não chega é o pedido parado — e o segundo acontece toda semana, o primeiro
quase nunca. O padrão protege contra o erro frequente.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class ComentarioQuerySet(models.QuerySet):
    def visiveis_para(self, solicitacao, pessoa, atende: bool = False):
        """O que esta pessoa pode ler neste pedido.

        Quem ATENDE vê tudo. Quem PEDIU vê só o que não é interno — e nem
        precisa ser o solicitante: quem não atende e não pediu não vê nada,
        porque nem chega nesta consulta.
        """
        do_pedido = self.filter(solicitacao=solicitacao)
        return do_pedido if atende else do_pedido.filter(interno=False)


class ComentarioSolicitacao(models.Model):
    """Uma fala no pedido. Nunca editada, nunca apagada.

    Sem edição de propósito: o comentário entra no histórico do pedido, e
    histórico que muda depois não serve para explicar o que aconteceu. Correção
    é um comentário novo — do mesmo jeito que a correção de um relatório emitido
    é outro relatório.
    """

    solicitacao = models.ForeignKey(
        "workspace.SolicitacaoServico",
        on_delete=models.CASCADE,
        related_name="comentarios",
    )
    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="comentarios"
    )
    texto = models.TextField()

    # Ver o docstring do módulo: o padrão é VISÍVEL, e é deliberado.
    interno = models.BooleanField(
        default=False,
        help_text="Só quem atende vê. Em branco, quem pediu também lê.",
    )

    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = ComentarioQuerySet.as_manager()

    class Meta:
        # Mais antigo primeiro: é uma conversa, e conversa se lê de cima para
        # baixo. O resto do produto ordena por mais recente porque são listas
        # de trabalho, não diálogos.
        ordering = ["criado_em"]
        verbose_name = "comentário"
        verbose_name_plural = "comentários"
        indexes = [
            models.Index(
                fields=["solicitacao", "criado_em"], name="wks_coment_pedido_idx"
            ),
        ]

    def __str__(self) -> str:
        marca = " (interno)" if self.interno else ""
        return f"{self.autor} em {self.solicitacao_id}{marca}"
