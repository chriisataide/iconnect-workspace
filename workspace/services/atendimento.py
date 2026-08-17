"""ATD — a fila de quem ATENDE o pedido, depois de aprovado.

## O buraco que este módulo fecha

`SituacaoServico` sempre teve `EM_ATENDIMENTO` e `CONCLUIDA`, e
`SolicitacaoServico.concluir()` sempre existiu. **Nada no produto os usava**:
nenhuma rota, nenhuma view, nenhum serviço. Um pedido era aprovado e parava ali
para sempre, a não ser que alguém editasse pelo `/admin/`.

Duas consequências, e as duas atingiam justamente o que o catálogo promete:

1. **O prazo real medido nunca aconteceria.** `prazo_medido()` lê
   `solicitacoes.concluidas()`, que seria sempre vazio — o card diria "prazo
   estimado" para sempre, e é o prazo MEDIDO que constrói confiança no catálogo
   (a promessa de que o número na tela veio da realidade, não de um chute).
2. **Quem pediu não sabia se ia chegar.** Aprovado, "esperando: —", silêncio. E
   quem some do radar depois de aprovar treina a pessoa a mandar e-mail
   perguntando — que é o comportamento que o Workspace inteiro existe para
   substituir.

## Quem vê qual fila

O roteamento já existia e não foi reinventado: `ItemCatalogo.dominio` diz para
onde o pedido vai (`rh.ferias`, `fin.reembolso`). O que faltava era a
PERMISSÃO — `rh.atender`, `fin.atender` —, e ela segue o vocabulário existente,
com escopo no sufixo (`.global`, `.unidade`).

A fila de cada pessoa sai dos domínios QUE EXISTEM no catálogo, e não da lista
de módulos. A primeira versão vinha dos módulos e perdeu os chamados de TI em
silêncio: `ti.chamado` — o equipamento parado, o pedido mais comum do produto —
não pertence a módulo nenhum.

Uma pessoa vê a união das filas que pode atender. Sem nenhuma permissão de
atendimento, a tela não é sua e responde 403: fila de trabalho alheio não é
informação institucional.

## A volta: "não resolveu"

Concluir era ponto final. Só o atendente podia dar o pedido por encerrado, e
quem pediu não tinha caminho nenhum para discordar — o notebook continuava sem
ligar e a pessoa abria um SEGUNDO pedido.

Três coisas quebravam de uma vez nessa segunda abertura: o histórico do mesmo
problema ficava partido em dois, o primeiro pedido entrava nos indicadores como
*resolvido rápido*, e `prazo_medido()` passava a medir o tempo até o
fechamento em vez do tempo até a solução. Fila que só quem atende pode fechar
sempre acaba assim: mede o fechamento, não a entrega.

`reabrir()` devolve o pedido à fila — o MESMO pedido, com o mesmo número e a
mesma linha do tempo — e limpa `concluido_em`, que é o que tira a medição
falsa da conta.

## O que este módulo NÃO faz

Não reabre a DECISÃO de aprovação. Aprovar é do APR, e reabrir o atendimento
não desfaz a aprovação: ela continua valendo, porque o que se contesta é a
entrega, não a autorização. Devolver daqui também é diferente de reprovar: é
dizer "não consigo atender assim" — falta informação, o item está errado —, e o
pedido volta para quem pediu, não para quem aprovou.
"""

from __future__ import annotations

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from identidade.services.autorizacao import pode
from workspace.models.catalogo import (
    PRAZO_REABERTURA_DIAS,
    ItemCatalogo,
    SituacaoServico,
    SolicitacaoServico,
)
from workspace.models.notificacao import TipoNotificacao
from workspace.services import catalogo as svc

# O sufixo que forma a permissão de atender a partir do domínio do módulo:
# `rh.` → `rh.atender`. Prefixo e não valor exato porque o escopo vive no fim
# da permissão (`rh.atender.global`), como no resto do vocabulário.
SUFIXO_ATENDER = "atender"

# As situações que aparecem na fila. `APROVADA` é o que chegou; `EM_ATENDIMENTO`
# é o que alguém já assumiu — e continua na fila, porque some-lo faria a pessoa
# perder de vista o próprio trabalho em curso.
NA_FILA = [SituacaoServico.APROVADA, SituacaoServico.EM_ATENDIMENTO]


class AtendimentoError(Exception):
    """O pedido não pode andar assim — já concluído, ou de outra fila."""


def _raiz(dominio: str) -> str:
    """`rh.` e `ti.acesso` viram `rh` e `ti`: a permissão é por departamento,
    não por serviço."""
    return dominio.split(".", 1)[0]


def permissao_de(dominio: str) -> str:
    return f"{_raiz(dominio)}.{SUFIXO_ATENDER}"


def prefixos_que_atende(pessoa, cache: dict | None = None) -> list[str]:
    """As fatias de catálogo que esta pessoa atende.

    Sai dos DOMÍNIOS QUE EXISTEM no catálogo, e não da lista de módulos. A
    primeira versão vinha dos módulos e deixou os chamados de TI de fora sem
    fazer barulho: o módulo "Redes" declara `ti.acesso`, e `ti.chamado` — o
    equipamento parado, que é o pedido mais comum do produto — não pertence a
    módulo nenhum. Fila que perde uma fatia inteira em silêncio é pior que fila
    que não existe, porque ninguém procura o que acha que está sendo atendido.

    Pelo catálogo, um item novo num domínio novo entra na fila de quem tem a
    permissão daquele departamento, sem ninguém precisar lembrar de uma segunda
    lista.
    """
    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        return []

    raizes = sorted(
        {
            _raiz(dominio)
            for dominio in ItemCatalogo.objects.filter(ativo=True)
            .values_list("dominio", flat=True)
            .distinct()
            if dominio
        }
    )
    return [
        f"{raiz}."
        for raiz in raizes
        if pode(pessoa, f"{raiz}.{SUFIXO_ATENDER}", cache=cache)
    ]


def atende_alguma_coisa(pessoa, cache: dict | None = None) -> bool:
    return bool(prefixos_que_atende(pessoa, cache=cache))


def fila_de(pessoa, cache: dict | None = None):
    """O que espera trabalho desta pessoa, mais antigo primeiro.

    Mais antigo primeiro, e não por valor ou por urgência declarada: fila que se
    reordena sozinha é fila em que o pedido pequeno de janeiro nunca é atendido.
    """
    prefixos = prefixos_que_atende(pessoa, cache=cache)
    if not prefixos:
        return SolicitacaoServico.objects.none()

    return (
        SolicitacaoServico.objects.filter(
            svc.q_dominios(prefixos, campo="item__dominio"),
            situacao__in=NA_FILA,
        )
        .select_related("item", "solicitante", "atendente")
        # `eventos` junto: a linha do que voltou mostra o motivo da reabertura,
        # e sem isto seria uma consulta por linha para descobrir que a imensa
        # maioria delas nunca voltou.
        .prefetch_related("anexos", "despesas", "eventos")
        .order_by("criado_em")
    )


def _garantir_que_pode(solicitacao: SolicitacaoServico, quem, cache=None) -> None:
    if not pode(quem, permissao_de(solicitacao.item.dominio), cache=cache):
        raise AtendimentoError("Este pedido não é da sua fila.")
    if solicitacao.situacao not in NA_FILA:
        raise AtendimentoError(
            f"O pedido está {solicitacao.get_situacao_display().lower()} — "
            "não há o que atender."
        )


def _avisar_pessoa(
    pessoa,
    solicitacao: SolicitacaoServico,
    tipo: str,
    titulo: str,
    corpo: str = "",
    url: str = "",
) -> None:
    from workspace.services import notificacoes as nt

    nt.criar(
        pessoa,
        tipo=tipo,
        titulo=titulo,
        corpo=corpo,
        url=url or reverse("workspace:minhas_solicitacoes"),
        dominio=solicitacao.item.dominio,
        origem_id=str(solicitacao.pk),
    )


def _avisar(solicitacao: SolicitacaoServico, tipo: str, titulo: str, corpo: str = "") -> None:
    """Avisa quem PEDIU — o destinatário de quase tudo que acontece aqui.

    A reabertura é a exceção, e vai pelo `_avisar_pessoa`: ela é a resposta de
    quem pediu, e mandá-la de volta para ele avisaria a pessoa do que ela
    acabou de fazer.
    """
    _avisar_pessoa(solicitacao.solicitante, solicitacao, tipo, titulo, corpo)


@transaction.atomic
def assumir(solicitacao: SolicitacaoServico, quem, cache=None) -> SolicitacaoServico:
    """Alguém pôs o nome nisto.

    Assumir é o que transforma uma pilha em trabalho de gente: sem dono, o
    pedido fica esperando "o setor", e setor nenhum atende nada.
    """
    _garantir_que_pode(solicitacao, quem, cache=cache)

    if solicitacao.atendente_id and solicitacao.atendente_id != getattr(quem, "pk", None):
        raise AtendimentoError(
            f"{solicitacao.atendente.get_full_name()} já assumiu este pedido."
        )

    solicitacao.atendente = quem
    solicitacao.situacao = SituacaoServico.EM_ATENDIMENTO
    solicitacao.save(update_fields=["atendente", "situacao"])

    from workspace.services import historico as hst

    hst.registrar(
        solicitacao, hst.Acao.ASSUMIDA, quem=quem,
        observacao=f"Assumido por {quem.get_full_name()}.",
    )
    _avisar(
        solicitacao,
        TipoNotificacao.PEDIDO_EM_ATENDIMENTO,
        f"{solicitacao.item.nome} está sendo atendido",
        f"{quem.get_full_name()} assumiu o seu pedido.",
    )
    return solicitacao


@transaction.atomic
def concluir(solicitacao: SolicitacaoServico, quem, cache=None) -> SolicitacaoServico:
    """Entregue. É esta chamada que alimenta o prazo REAL do catálogo."""
    _garantir_que_pode(solicitacao, quem, cache=cache)

    if solicitacao.atendente_id is None:
        # Concluir sem assumir é normal para o pedido de dois minutos, e negar
        # isso só produziria dois cliques para o mesmo fim. Mas o nome fica.
        solicitacao.atendente = quem

    solicitacao.situacao = SituacaoServico.CONCLUIDA
    solicitacao.concluido_em = timezone.now()
    solicitacao.save(update_fields=["atendente", "situacao", "concluido_em"])

    from workspace.services import historico as hst

    hst.registrar(solicitacao, hst.Acao.CONCLUIDA, quem=quem)
    _avisar(
        solicitacao,
        TipoNotificacao.PEDIDO_CONCLUIDO,
        f"{solicitacao.item.nome} foi concluído",
        f"Atendido por {quem.get_full_name()}.",
    )
    return solicitacao


@transaction.atomic
def devolver(solicitacao: SolicitacaoServico, quem, motivo: str, cache=None) -> SolicitacaoServico:
    """Não dá para atender assim — e o motivo é obrigatório.

    Devolver daqui não é reprovar: a aprovação continua valendo. É "faltou
    informação" ou "o item está errado", e o pedido volta para quem pediu.

    Sem motivo, quem recebe de volta tem de adivinhar — e adivinhar gera um
    segundo envio igualmente errado. É a mesma regra da devolução na aprovação.
    """
    _garantir_que_pode(solicitacao, quem, cache=cache)

    motivo = (motivo or "").strip()
    if not motivo:
        raise AtendimentoError("Diga o que falta para você conseguir atender.")

    solicitacao.situacao = SituacaoServico.DEVOLVIDA
    solicitacao.motivo_devolucao = motivo
    solicitacao.save(update_fields=["situacao", "motivo_devolucao"])

    from workspace.services import historico as hst

    hst.registrar(
        solicitacao, hst.Acao.DEVOLVIDA, quem=quem, observacao=motivo
    )
    _avisar(
        solicitacao,
        TipoNotificacao.PEDIDO_DEVOLVIDO,
        f"{solicitacao.item.nome} voltou para você",
        motivo,
    )
    return solicitacao


@transaction.atomic
def reabrir(solicitacao: SolicitacaoServico, quem, motivo: str) -> SolicitacaoServico:
    """"Não resolveu" — o pedido volta para a fila, e é o MESMO pedido.

    ## Quem pode

    Só quem pediu. Concluir é a palavra de quem entregou; reabrir é a palavra de
    quem recebeu, e é justamente por serem duas pessoas diferentes que a
    segunda significa alguma coisa. O atendente que se arrependeu de concluir
    simplesmente assume o pedido de novo — não precisa deste caminho.

    ## Por que não é um pedido novo

    Era o que acontecia antes, na falta desta função: a pessoa abria outro. O
    mesmo problema virava dois números, o primeiro fechava a estatística como
    *resolvido em 1 dia*, e o atendente do segundo começava do zero sem saber
    que já havia uma tentativa.

    Aqui `concluido_em` volta a ser nulo. É a linha que importa para o prazo do
    catálogo: enquanto o pedido estiver reaberto ele SAI da conta do prazo
    medido, e quando for concluído de verdade a conta será do dia do pedido até
    a solução — não até a primeira tentativa.

    ## Para onde ele volta

    Para as mãos de quem atendeu, quando ainda há alguém: quem disse "pronto" é
    quem precisa ouvir "não está". Sem atendente (a pessoa saiu da empresa), o
    pedido volta a `APROVADA` e a fila inteira o vê — é melhor que ficar preso
    a um nome que não existe mais.

    A APROVAÇÃO NÃO É REFEITA. O que se contesta é a entrega, não a
    autorização — e mandar o gestor aprovar de novo o mesmo notebook que ele já
    aprovou transformaria uma reclamação em burocracia.
    """
    if solicitacao.solicitante_id != getattr(quem, "pk", None):
        raise AtendimentoError("Só quem pediu pode dizer que não resolveu.")

    if solicitacao.situacao != SituacaoServico.CONCLUIDA:
        raise AtendimentoError(
            f"O pedido está {solicitacao.get_situacao_display().lower()} — "
            "só o que foi concluído pode ser reaberto."
        )

    if not solicitacao.pode_reabrir:
        # A mensagem diz o caminho, e não só o "não": passado o prazo, aquilo
        # já é problema novo, e novo pedido é a resposta certa.
        raise AtendimentoError(
            f"O prazo de {PRAZO_REABERTURA_DIAS} dias para reabrir já passou. "
            "Abra um novo pedido."
        )

    motivo = (motivo or "").strip()
    if not motivo:
        # Mesma regra da devolução, pelo mesmo motivo: "não resolveu" sem dizer
        # o quê devolve o pedido para a mesma pessoa que já tentou uma vez, sem
        # nada de novo para ela fazer diferente.
        raise AtendimentoError("Diga o que continua sem resolver.")

    atendente = solicitacao.atendente
    solicitacao.situacao = (
        SituacaoServico.EM_ATENDIMENTO if atendente else SituacaoServico.APROVADA
    )
    solicitacao.concluido_em = None
    solicitacao.reaberturas += 1
    solicitacao.save(update_fields=["situacao", "concluido_em", "reaberturas"])

    from workspace.services import historico as hst

    hst.registrar(solicitacao, hst.Acao.REABERTA, quem=quem, observacao=motivo)

    if atendente:
        _avisar_pessoa(
            atendente,
            solicitacao,
            TipoNotificacao.PEDIDO_REABERTO,
            f"{solicitacao.item.nome} voltou: não resolveu",
            motivo,
            url=reverse("workspace:fila"),
        )
    return solicitacao


# ── O que a tela mostra no topo ─────────────────────────────────────


def resumo_da_fila(pessoa, cache: dict | None = None) -> dict:
    """Três números que respondem "como está a minha fila?".

    Atrasado é medido contra o prazo PROMETIDO do item, e não contra um SLA
    inventado aqui: é o mesmo número que a pessoa viu quando pediu, e cobrar
    por outro seria mudar a régua depois do jogo.
    """
    fila = list(fila_de(pessoa, cache=cache))
    agora = timezone.now()

    atrasados = [
        s for s in fila
        if (agora - s.criado_em).days > s.item.prazo_prometido_dias
    ]
    meus = [s for s in fila if s.atendente_id == getattr(pessoa, "pk", None)]

    return {
        "total": len(fila),
        "meus": len(meus),
        "atrasados": len(atrasados),
        # O número que diz se "concluído" significa alguma coisa. Fila que só
        # conta o que entra e o que sai parece saudável mesmo quando metade do
        # que saiu está voltando.
        "reabertos": len([s for s in fila if s.reaberturas]),
        "solicitacoes": fila,
    }
