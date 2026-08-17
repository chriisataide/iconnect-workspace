"""HST — registrar o que aconteceu com um pedido.

Uma função de escrita e uma de leitura. O tamanho é o ponto: se registrar
custasse mais que uma linha, alguém esqueceria de chamar no caminho novo — e
histórico com buraco é pior que histórico nenhum, porque quem lê acredita nele.

**Nunca levanta.** Um pedido não pode falhar porque o registro do histórico
falhou: o histórico serve para explicar o que aconteceu, e derrubar a operação
que ele descreve inverte a relação. Ele é chamado de dentro das transações que
já existem, então em caso de erro do banco a transação inteira volta de
qualquer forma.
"""

from __future__ import annotations

from workspace.models.evento import AcaoSolicitacao, EventoSolicitacao


def registrar(
    solicitacao,
    acao: str,
    quem=None,
    observacao: str = "",
) -> EventoSolicitacao | None:
    """Escreve uma linha no histórico do pedido.

    `quem=None` é caso legítimo e não erro: a auto-aprovação acontece porque o
    pedido cabe na política, e ninguém precisou decidir.
    """
    if solicitacao is None or getattr(solicitacao, "pk", None) is None:
        return None

    return EventoSolicitacao.objects.create(
        solicitacao=solicitacao,
        acao=acao,
        quem=quem if getattr(quem, "pk", None) else None,
        observacao=(observacao or "").strip()[:300],
    )


def de(solicitacao):
    """A linha do tempo do pedido, do mais antigo para o mais novo."""
    return (
        EventoSolicitacao.objects.filter(solicitacao=solicitacao)
        .select_related("quem")
        .order_by("quando", "pk")
    )


# Reexportado para quem registra não precisar importar de dois lugares.
Acao = AcaoSolicitacao
