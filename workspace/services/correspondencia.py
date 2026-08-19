"""Registrar, avisar, entregar.

O aviso é o produto. Registrar sem notificar troca a pilha na mesa da recepção
por uma pilha no banco de dados — e a segunda é pior, porque ninguém passa por
ela sem querer.
"""

from __future__ import annotations

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from identidade.services.autorizacao import pode
from workspace.models.correspondencia import (
    Correspondencia,
    SituacaoCorrespondencia,
    TipoCorrespondencia,
)
from workspace.models.notificacao import TipoNotificacao

PERMISSAO_REGISTRAR = "cor.registrar.global"


class CorrespondenciaError(Exception):
    """Registro ou entrega inválidos."""


# ── Consulta ────────────────────────────────────────────────────────


def minhas(pessoa):
    """As correspondências da pessoa, aguardando primeiro."""
    return (
        Correspondencia.objects.de(pessoa)
        .select_related("unidade", "recebido_por")
        .order_by("situacao", "-urgente", "recebido_em")
    )


def aguardando_de(pessoa) -> int:
    return Correspondencia.objects.de(pessoa).aguardando().count()


def fila(pessoa, cache: dict | None = None):
    """A fila da recepção. Exige permissão — é dado de outras pessoas.

    Correspondência revela quem recebe intimação e de quem, o que é informação
    sensível sobre a vida da pessoa. A fila não é pública nem para gestores: é
    de quem opera a recepção.
    """
    if not pode(pessoa, PERMISSAO_REGISTRAR, cache=cache):
        return Correspondencia.objects.none()
    return (
        Correspondencia.objects.aguardando()
        .select_related("destinatario", "unidade")
        .order_by("-urgente", "recebido_em")
    )


def nao_identificadas(pessoa, cache: dict | None = None):
    if not pode(pessoa, PERMISSAO_REGISTRAR, cache=cache):
        return Correspondencia.objects.none()
    return Correspondencia.objects.sem_destinatario().select_related("unidade")


# ── Registrar ───────────────────────────────────────────────────────


@transaction.atomic
def registrar(
    quem,
    tipo: str,
    remetente: str = "",
    descricao: str = "",
    destinatario=None,
    nome_no_envelope: str = "",
    unidade=None,
    observacao: str = "",
    empresa: str = "",
    numero_rastreio: str = "",
    recebido_em=None,
    foto=None,
    cache: dict | None = None,
) -> Correspondencia:
    """Registra e AVISA o destinatário, quando ele é conhecido."""
    if not pode(quem, PERMISSAO_REGISTRAR, cache=cache):
        raise CorrespondenciaError("Você não pode registrar correspondência.")
    if tipo not in TipoCorrespondencia.values:
        raise CorrespondenciaError("Tipo de correspondência inválido.")
    if destinatario is None and not nome_no_envelope.strip():
        # Sem FK e sem nome, ninguém se reconhece na fila — a correspondência
        # nasce perdida.
        raise CorrespondenciaError(
            "Informe o destinatário ou o nome como veio no envelope."
        )

    correspondencia = Correspondencia.objects.create(
        tipo=tipo,
        remetente=remetente[:160],
        descricao=descricao[:200],
        destinatario=destinatario,
        nome_no_envelope=nome_no_envelope[:160],
        unidade=unidade,
        observacao=observacao[:200],
        empresa=empresa[:120],
        numero_rastreio=numero_rastreio[:60],
        foto=foto or "",
        recebido_por=quem,
        # A data de chegada é digitável porque a recepção nem sempre registra na
        # hora: a pilha de sexta entra na segunda, e gravar "segunda" faria o
        # prazo da intimação começar a contar dois dias tarde.
        **({"recebido_em": recebido_em} if recebido_em else {}),
    )

    _avisar(correspondencia)
    return correspondencia


def _avisar(correspondencia: Correspondencia) -> None:
    """Notifica o destinatário. Silencioso quando não há um.

    Reusa a Central de Notificações da onda B em vez de mandar e-mail: e-mail
    tem regra de frequência, digest e opt-out próprios, que merecem decisão
    explícita e não nascem como efeito colateral de um cadastro.
    """
    from workspace.services import notificacoes as nt

    if correspondencia.destinatario_id is None:
        return

    urgencia = " · com prazo legal" if correspondencia.urgente else ""
    onde = f" na {correspondencia.unidade}" if correspondencia.unidade_id else ""
    nt.criar(
        destinatario=correspondencia.destinatario,
        tipo=TipoNotificacao.CORRESPONDENCIA_RECEBIDA,
        titulo=f"{correspondencia.get_tipo_display()} para você{urgencia}",
        corpo=(
            f"De {correspondencia.remetente}{onde}."
            if correspondencia.remetente
            else f"Aguardando retirada{onde}."
        ),
        url=reverse("workspace:correspondencias"),
        dominio="cor.correspondencia",
        origem_id=str(correspondencia.pk),
    )


@transaction.atomic
def confirmar(correspondencia: Correspondencia, quem) -> Correspondencia:
    """O DESTINATÁRIO diz que recebeu — §6.

    É a outra metade de `entregar()`, e a distinção é o ponto: `entregar` é a
    recepção dizendo "entreguei", `confirmar` é a pessoa dizendo "recebi".
    Enquanto só existia o primeiro, a única versão registrada dos fatos era a de
    quem entregou — e é exatamente essa que não vale nada quando a intimação
    some e alguém precisa provar o que aconteceu.

    Só o destinatário confirma. Nem a recepção, nem quem administra: uma
    confirmação que outro pode dar no seu lugar não confirma nada.
    """
    if correspondencia.destinatario_id != getattr(quem, "pk", None):
        raise CorrespondenciaError("Só quem recebeu pode confirmar.")
    if correspondencia.situacao != SituacaoCorrespondencia.ENTREGUE:
        raise CorrespondenciaError(
            "Esta correspondência ainda não foi entregue pela recepção."
        )
    if correspondencia.confirmado_em is not None:
        # Silencioso e não erro: duplo clique e voltar-no-navegador são o modo
        # normal de isto acontecer, e uma mensagem de erro aqui assustaria sem
        # motivo — a confirmação já está registrada.
        return correspondencia

    correspondencia.confirmado_em = timezone.now()
    correspondencia.save(update_fields=["confirmado_em"])
    return correspondencia


@transaction.atomic
def identificar(correspondencia: Correspondencia, destinatario, quem, cache=None):
    """Aponta o destinatário de uma correspondência que chegou sem nome.

    Avisa depois de identificar: é o único momento em que a pessoa pode saber que
    algo chegou para ela, porque no registro ninguém sabia quem era.
    """
    if not pode(quem, PERMISSAO_REGISTRAR, cache=cache):
        raise CorrespondenciaError("Você não pode alterar correspondência.")
    if correspondencia.destinatario_id is not None:
        raise CorrespondenciaError("Esta correspondência já tem destinatário.")
    if not correspondencia.aguardando_retirada:
        raise CorrespondenciaError("Só faz sentido identificar o que ainda espera.")

    correspondencia.destinatario = destinatario
    correspondencia.save(update_fields=["destinatario"])
    _avisar(correspondencia)
    return correspondencia


# ── Entregar ────────────────────────────────────────────────────────


@transaction.atomic
def entregar(correspondencia: Correspondencia, quem, retirado_por=None, cache=None):
    """Registra a retirada.

    `retirado_por` pode ser outra pessoa: secretária, colega, motoboy. Forçar que
    seja o destinatário faria a recepção registrar mentira para fechar a fila — e
    aí a trilha deixa de valer.
    """
    if not pode(quem, PERMISSAO_REGISTRAR, cache=cache):
        raise CorrespondenciaError("Você não pode registrar entrega.")
    if not correspondencia.aguardando_retirada:
        raise CorrespondenciaError(
            f"Correspondência já está {correspondencia.get_situacao_display().lower()}."
        )

    correspondencia.situacao = SituacaoCorrespondencia.ENTREGUE
    correspondencia.retirado_em = timezone.now()
    correspondencia.retirado_por = retirado_por or correspondencia.destinatario
    correspondencia.save(
        update_fields=["situacao", "retirado_em", "retirado_por"]
    )
    return correspondencia


@transaction.atomic
def devolver(correspondencia: Correspondencia, quem, motivo: str = "", cache=None):
    """Devolve ao remetente. Exige motivo — devolução sem motivo é sumiço."""
    if not pode(quem, PERMISSAO_REGISTRAR, cache=cache):
        raise CorrespondenciaError("Você não pode devolver correspondência.")
    if not correspondencia.aguardando_retirada:
        raise CorrespondenciaError("Só o que aguarda pode ser devolvido.")
    if not motivo.strip():
        raise CorrespondenciaError("Informe o motivo da devolução.")

    correspondencia.situacao = SituacaoCorrespondencia.DEVOLVIDA
    correspondencia.observacao = motivo[:200]
    correspondencia.save(update_fields=["situacao", "observacao"])
    return correspondencia
