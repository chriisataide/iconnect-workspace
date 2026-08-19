"""Notificações do Workspace — quem avisar, e quando não avisar.

O problema que este módulo resolve: hoje, se o gestor devolve um pedido, a pessoa
só descobre abrindo a tela. E se a cadeia anda, o próximo aprovador também. É
assim que um pedido fica cinco dias parado sem que ninguém tenha culpa.

## O que este módulo NÃO faz

Não notifica comunicado para a empresa inteira. Fan-out exige público-alvo, que é
do domínio CNT/COM e entra na onda C — e notificação disparada para todos sem
segmentação é o caminho mais curto para o sino ser ignorado.

Não manda e-mail nem push. A `Central de Notificações` é o canal do V1; e-mail
tem regra de frequência, digest e opt-out próprios, que merecem decisão explícita
em vez de nascerem como efeito colateral.
"""

from __future__ import annotations

from django.db import transaction
from django.urls import reverse

from workspace.models.notificacao import Notificacao, TipoNotificacao
from workspace.services import aprovacao as apr


def criar(
    destinatario,
    tipo: str,
    titulo: str,
    corpo: str = "",
    url: str = "",
    dominio: str = "",
    origem_id: str = "",
) -> Notificacao | None:
    """Cria o aviso, ou devolve `None` quando ele seria repetição.

    O dedupe olha só o NÃO LIDO. Se a pessoa já leu e o mesmo evento voltou a
    acontecer — pedido devolvido, corrigido e reenviado ao mesmo aprovador —, é
    evento novo e ela precisa saber.
    """
    if destinatario is None or getattr(destinatario, "pk", None) is None:
        return None

    if origem_id:
        ja_avisado = (
            Notificacao.objects.de(destinatario)
            .nao_lidas()
            .filter(tipo=tipo, dominio=dominio, origem_id=origem_id)
            .exists()
        )
        if ja_avisado:
            return None

    return Notificacao.objects.create(
        destinatario=destinatario,
        tipo=tipo,
        titulo=titulo[:200],
        corpo=corpo[:300],
        url=url[:300],
        dominio=dominio,
        origem_id=str(origem_id)[:64],
    )


# ── Leitura ─────────────────────────────────────────────────────────


def para(pessoa, limite: int | None = None):
    """As notificações da pessoa, mais recentes primeiro."""
    consulta = Notificacao.objects.de(pessoa).recentes()
    return consulta[:limite] if limite else consulta


def quantas_nao_lidas(pessoa) -> int:
    """O número do sino. Uma consulta, sem carregar linha."""
    return Notificacao.objects.de(pessoa).nao_lidas().count()


@transaction.atomic
def marcar_lidas(pessoa, ids=None) -> int:
    """Marca como lidas. Sem `ids`, marca todas as não lidas da pessoa."""
    from django.utils import timezone

    consulta = Notificacao.objects.de(pessoa).nao_lidas()
    if ids is not None:
        consulta = consulta.filter(pk__in=ids)
    return consulta.update(lida_em=timezone.now())


# ── Ouvintes ────────────────────────────────────────────────────────


def _url_da_bandeja() -> str:
    return reverse("workspace:aprovacoes")


def _url_das_minhas() -> str:
    return reverse("workspace:minhas_solicitacoes")


def _avisar_que_o_papel_nao_tem_dono(solicitacao, etapa) -> None:
    """O pedido parou num papel que ninguém ocupa. Avisa quem pode consertar.

    Sem isto, este é o jeito mais silencioso de o produto perder um pedido: a
    cadeia manda para "Compras", ninguém tem o papel de Compras, e a etapa não
    aparece na bandeja de pessoa nenhuma. O solicitante vê "aguardando
    aprovação" para sempre, e do outro lado não há lado.

    A URL leva à tela de papéis, e não à bandeja: quem recebe este aviso não
    tem o que decidir — tem o que conceder.
    """
    from identidade.services.administracao import quem_administra
    from workspace.services.mapa_aprovacao import papeis_sem_titular

    if etapa.papel_id not in papeis_sem_titular():
        return

    nome = etapa.papel.nome if etapa.papel_id else "?"
    for pessoa in quem_administra():
        criar(
            destinatario=pessoa,
            tipo=TipoNotificacao.APROVACAO_SEM_DONO,
            titulo=f"{solicitacao.titulo} parou: ninguém tem o papel {nome}",
            corpo=f"Enquanto o papel {nome} estiver vago, este pedido não "
            "aparece na bandeja de ninguém.",
            url=reverse("workspace:pessoas"),
            dominio=solicitacao.dominio,
            origem_id=str(solicitacao.pk),
        )


def ao_chegar_a_vez(sender, solicitacao, etapa, **kwargs) -> None:
    """Avisa quem tem a etapa da vez.

    Só etapa NOMINAL. Etapa por papel não tem destinatário único — "Diretoria"
    são três pessoas, e criar três linhas aqui significaria que aprovar uma
    deixaria duas notificações órfãs apontando para um pedido já decidido.
    Para essas, o aviso é o contador da bandeja, que reflete o estado real.

    **Menos quando o papel não tem ninguém.** Aí não há bandeja em que o pedido
    apareça: a etapa não tem destinatário, e o contador de todo mundo continua
    zerado enquanto o pedido espera para sempre. Esse é o único caso em que
    etapa por papel gera aviso — e ele vai para quem pode conceder o papel, que
    é a única pessoa capaz de tirar o pedido dali.
    """
    if etapa.aprovador_id is None:
        if etapa.papel_id:
            _avisar_que_o_papel_nao_tem_dono(solicitacao, etapa)
        return

    # Reusa o filtro de moeda em vez de formatar aqui: dois lugares formatando
    # dinheiro divergem, e é a segunda cópia que esquece o separador de milhar.
    from workspace.templatetags.wks import moeda

    de = solicitacao.solicitante.get_short_name() or solicitacao.solicitante.get_username()
    corpo = f"De {de}"
    if solicitacao.valor:
        corpo += f" · R$ {moeda(solicitacao.valor)}"

    criar(
        destinatario=etapa.aprovador,
        tipo=TipoNotificacao.VEZ_DE_APROVAR,
        titulo=f"{solicitacao.titulo} espera sua decisão",
        corpo=corpo,
        url=_url_da_bandeja(),
        dominio=solicitacao.dominio,
        origem_id=str(solicitacao.pk),
    )


_TITULO_POR_DECISAO = {
    apr.Decisao.APROVAR: ("{titulo} foi aprovado", TipoNotificacao.PEDIDO_APROVADO),
    apr.Decisao.DEVOLVER: ("{titulo} foi devolvido", TipoNotificacao.PEDIDO_DEVOLVIDO),
    apr.Decisao.REJEITAR: ("{titulo} foi reprovado", TipoNotificacao.PEDIDO_REJEITADO),
    apr.Decisao.CANCELAR: ("{titulo} foi cancelado", TipoNotificacao.PEDIDO_CANCELADO),
}


def ao_decidir(sender, solicitacao, decisao, quem, **kwargs) -> None:
    """Avisa o solicitante do desfecho.

    Aprovação de etapa intermediária NÃO gera aviso: `aprovacao_decidida` só é
    emitido quando o pedido inteiro se resolve. Avisar a cada degrau faria um
    pedido de R$ 400.000 render três notificações que dizem quase nada.
    """
    entrada = _TITULO_POR_DECISAO.get(decisao)
    if entrada is None:  # pragma: no cover - Decisao só tem três valores
        return
    molde, tipo = entrada

    # Cancelamento pelo próprio solicitante não vira aviso: ele acabou de clicar.
    if decisao == apr.Decisao.CANCELAR and getattr(quem, "pk", None) == solicitacao.solicitante_id:
        return

    motivo = ""
    if decisao in (apr.Decisao.DEVOLVER, apr.Decisao.REJEITAR):
        etapa = solicitacao.etapas.exclude(justificativa="").order_by("-decidido_em").first()
        motivo = etapa.justificativa if etapa else ""
        # O motivo VAI no corpo do aviso, e não só na tela. Quem foi reprovado
        # precisa saber por quê no momento em que descobre que foi.

    criar(
        destinatario=solicitacao.solicitante,
        tipo=tipo,
        titulo=molde.format(titulo=solicitacao.titulo),
        corpo=motivo,
        url=_url_das_minhas(),
        dominio=solicitacao.dominio,
        origem_id=str(solicitacao.pk),
    )


def conectar() -> None:
    """Liga os ouvintes. Chamado no `ready()` do app."""
    apr.vez_de.connect(ao_chegar_a_vez, dispatch_uid="workspace.notificacoes.vez")
    apr.aprovacao_decidida.connect(
        ao_decidir, dispatch_uid="workspace.notificacoes.decidida"
    )
