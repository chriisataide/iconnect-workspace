"""Quem aprova o quê, por área — o mapa que a tela de papéis mostra.

## Por que este módulo existe separado

Ele nasceu dentro de `identidade/services/administracao.py`, e a suíte reprovou
na hora: **`identidade` é a raiz da dependência e não pode conhecer o
workspace**. A função lê `RegraAprovacao`, que é um modelo do workspace — o
import inverteu a seta que o projeto inteiro depende para não virar um novelo.

Foi um teste de arquitetura que pegou (`test_isolamento`), não uma revisão
humana, e é exatamente para isso que ele existe: a violação era invisível em
tempo de execução e teria ficado.

O lugar certo é aqui. A tela de papéis mora no workspace de qualquer jeito; o
que ela pede a `identidade` é conceder e revogar, e isso continua lá.
"""

from __future__ import annotations

from identidade.models import AtribuicaoPapel
from workspace.models.aprovacao import RegraAprovacao, TipoAprovador


def papeis_sem_titular() -> set[int]:
    """Os papéis de aprovação que ninguém ocupa hoje.

    Uma consulta só, devolvendo ids: a tela de "minhas solicitações" precisa
    marcar as etapas paradas, e perguntar por linha custaria uma consulta por
    pedido numa tela que já é uma lista.

    Só papéis que APARECEM em regra de aprovação. Papel sem titular que não
    aprova nada não trava pedido nenhum, e listá-lo aqui transformaria a marca
    de "parado" em ruído.
    """
    usados = set(
        RegraAprovacao.objects.filter(ativa=True, tipo=TipoAprovador.PAPEL)
        .exclude(papel__isnull=True)
        .values_list("papel_id", flat=True)
    )
    if not usados:
        return set()

    ocupados = set(
        AtribuicaoPapel.objects.vigentes()
        .filter(papel_id__in=usados)
        .values_list("papel_id", flat=True)
    )
    return usados - ocupados


def resumo_de_aprovacao() -> list[dict]:
    """Quem aprova o quê, por área — a pergunta que a tela existe para responder.

    Sai das REGRAS de aprovação cruzadas com quem tem o papel de cada uma: é a
    única fonte que não mente, porque é a mesma que o motor usa para montar a
    cadeia. Uma lista mantida à mão diria o que alguém achava que era verdade.
    """
    linhas: list[dict] = []
    regras = (
        RegraAprovacao.objects.filter(ativa=True, tipo=TipoAprovador.PAPEL)
        .select_related("papel")
        .order_by("dominio", "ordem")
    )
    for regra in regras:
        pessoas = [
            a.user
            for a in AtribuicaoPapel.objects.vigentes()
            .filter(papel=regra.papel)
            .select_related("user")
        ]
        linhas.append(
            {
                "dominio": regra.dominio,
                "papel": regra.papel,
                "acima_de": regra.valor_minimo,
                "pessoas": pessoas,
                # Área sem ninguém é o defeito que esta tela existe para
                # mostrar: a cadeia manda o pedido para um papel que não tem
                # dono, e ele fica parado sem que ninguém seja avisado.
                "orfa": not pessoas,
            }
        )
    return linhas
