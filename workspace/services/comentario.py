"""WKF — a conversa dentro do pedido, e quem é avisado dela (§45).

## A regra que mais importa aqui

O comentário avisa o **outro lado**. Se quem atende escreveu, quem pediu recebe;
se quem pediu escreveu, quem atende recebe. Sem isso, o comentário é um bilhete
deixado numa tela que a pessoa não vai abrir — e o pedido continua parado com a
pergunta esperando.

Comentário INTERNO não avisa quem pediu, pelo motivo óbvio: ele nem aparece para
ela.

## Quem pode falar

Quem pediu e quem atende a fila daquele domínio. Ninguém mais — comentário é
parte do pedido, e o pedido é de duas partes.
"""

from __future__ import annotations

from django.db import transaction
from django.urls import reverse

from workspace.models.catalogo import SolicitacaoServico
from workspace.models.comentario import ComentarioSolicitacao
from workspace.models.notificacao import TipoNotificacao

#: Um comentário não é um documento. Acima disto é anexo, e o campo longo
#: convida a colar log inteiro dentro da conversa.
MAXIMO = 2000


class ComentarioError(Exception):
    """O comentário não pode ser gravado assim."""


def atende(solicitacao: SolicitacaoServico, pessoa, cache=None) -> bool:
    from identidade.services.autorizacao import pode
    from workspace.services import atendimento as atd

    return pode(pessoa, atd.permissao_de(solicitacao.item.dominio), cache=cache)


def pode_comentar(solicitacao: SolicitacaoServico, pessoa, cache=None) -> bool:
    if solicitacao.solicitante_id == getattr(pessoa, "pk", None):
        return True
    return atende(solicitacao, pessoa, cache=cache)


def de(solicitacao: SolicitacaoServico, pessoa, cache=None):
    """Os comentários que esta pessoa pode ler."""
    return ComentarioSolicitacao.objects.visiveis_para(
        solicitacao, pessoa, atende=atende(solicitacao, pessoa, cache=cache)
    ).select_related("autor")


@transaction.atomic
def comentar(
    solicitacao: SolicitacaoServico,
    pessoa,
    texto: str,
    interno: bool = False,
    cache=None,
) -> ComentarioSolicitacao:
    """Escreve e avisa o outro lado."""
    if not pode_comentar(solicitacao, pessoa, cache=cache):
        raise ComentarioError("Este pedido não é seu nem da sua fila.")

    texto = (texto or "").strip()
    if not texto:
        raise ComentarioError("Escreva alguma coisa.")
    if len(texto) > MAXIMO:
        raise ComentarioError(
            f"O comentário passa de {MAXIMO} caracteres. Use um anexo para o que "
            "for longo."
        )

    # Interno só faz sentido para quem atende: marcado por quem pediu, ele
    # esconderia a fala da própria pessoa dela mesma.
    interno = bool(interno) and atende(solicitacao, pessoa, cache=cache)

    comentario = ComentarioSolicitacao.objects.create(
        solicitacao=solicitacao, autor=pessoa, texto=texto, interno=interno
    )
    _avisar(comentario, pessoa, cache=cache)
    return comentario


def _avisar(comentario: ComentarioSolicitacao, quem, cache=None) -> None:
    """Avisa o OUTRO lado. Interno não sai da área."""
    from workspace.services import atendimento as atd
    from workspace.services import notificacoes as nt

    solicitacao = comentario.solicitacao
    resumo = comentario.texto[:200]
    titulo = f"{quem.get_full_name()} comentou em {solicitacao.item.nome}"

    if comentario.interno:
        # Nota entre atendentes: avisa quem já assumiu, e mais ninguém. A fila
        # inteira receber nota interna de um pedido que não é dela transforma o
        # sino em ruído.
        if solicitacao.atendente_id and solicitacao.atendente_id != quem.pk:
            nt.criar(
                destinatario=solicitacao.atendente,
                tipo=TipoNotificacao.COMENTARIO_NO_PEDIDO,
                titulo=titulo,
                corpo=resumo,
                url=reverse("workspace:atender", args=[solicitacao.pk]),
                dominio=solicitacao.item.dominio,
                origem_id=str(comentario.pk),
            )
        return

    if quem.pk == solicitacao.solicitante_id:
        # Quem pediu falou: avisa quem já assumiu. Se ninguém assumiu, o pedido
        # está na fila e o comentário será lido quando alguém pegar — avisar a
        # área inteira por um comentário seria ruído por definição.
        if solicitacao.atendente_id:
            nt.criar(
                destinatario=solicitacao.atendente,
                tipo=TipoNotificacao.COMENTARIO_NO_PEDIDO,
                titulo=titulo,
                corpo=resumo,
                url=reverse("workspace:atender", args=[solicitacao.pk]),
                dominio=solicitacao.item.dominio,
                origem_id=str(comentario.pk),
            )
        return

    # Quem atende falou: avisa quem pediu. É o caso que conserta o §45 — a
    # pergunta chega sem o pedido precisar ser devolvido.
    nt.criar(
        destinatario=solicitacao.solicitante,
        tipo=TipoNotificacao.COMENTARIO_NO_PEDIDO,
        titulo=titulo,
        corpo=resumo,
        url=reverse("workspace:minhas_solicitacoes"),
        dominio=solicitacao.item.dominio,
        origem_id=str(comentario.pk),
    )
