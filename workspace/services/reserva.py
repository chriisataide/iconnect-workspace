"""Reservar sem choque de horário.

A garantia de não sobreposição mora aqui, e não no banco — ver a docstring de
`models/reserva.py` para o motivo (`ExclusionConstraint` é exclusivo do Postgres,
e constraint que existe em produção e não em desenvolvimento é pior que nenhuma).

O desenho: `select_for_update()` na linha do RECURSO, dentro de uma transação.
Serializa por recurso, então duas salas diferentes seguem sendo reservadas em
paralelo. Travar a tabela de reservas faria a empresa inteira esperar por quem
está marcando uma sala.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from workspace.models.reserva import (
    Recurso,
    Reserva,
    SituacaoReserva,
    TipoRecurso,
)

# Reserva com um mês de antecedência é planejamento; com um ano é alguém
# segurando o recurso. O limite é generoso e existe para pegar erro de digitação
# de ano, que é o caso real ("2027" no lugar de "2026").
ANTECEDENCIA_MAXIMA = timedelta(days=180)


class ReservaError(Exception):
    """Reserva inválida — choque, janela impossível, recurso inativo."""


# ── Consulta ────────────────────────────────────────────────────────


def recursos_para(pessoa):
    """Recursos ativos.

    Sem filtro por unidade: quem está na base de Salvador pode precisar reservar
    a sala da matriz para uma reunião com a diretoria. A unidade aparece na tela
    como informação, não como barreira.
    """
    return Recurso.objects.ativos().select_related("unidade")


def agrupados_para(pessoa) -> dict[str, list[Recurso]]:
    """Por tipo, na ordem de declaração do enum — sala primeiro, que é o mais
    reservado."""
    por_tipo: dict[str, list[Recurso]] = {}
    for recurso in recursos_para(pessoa):
        por_tipo.setdefault(recurso.tipo, []).append(recurso)

    agrupado: dict[str, list[Recurso]] = {}
    for tipo in TipoRecurso:
        itens = por_tipo.get(tipo.value)
        if itens:
            agrupado[tipo.label] = itens
    return agrupado


def agenda_do_dia(recurso: Recurso, dia=None):
    """As reservas confirmadas de um recurso num dia.

    Existe para a tela mostrar o que já está ocupado ANTES de a pessoa escolher
    o horário. Formulário que só diz "conflito" depois do envio faz a pessoa
    tentar por adivinhação.
    """
    dia = dia or timezone.localdate()
    inicio = timezone.make_aware(
        timezone.datetime.combine(dia, timezone.datetime.min.time())
    )
    return (
        Reserva.objects.confirmadas()
        .filter(recurso=recurso, inicio__lt=inicio + timedelta(days=1), fim__gt=inicio)
        .select_related("solicitante")
        .order_by("inicio")
    )


def minhas(pessoa):
    """As reservas da pessoa, futuras primeiro."""
    return (
        Reserva.objects.de(pessoa)
        .select_related("recurso", "recurso__unidade")
        .order_by("-inicio")
    )


def conflitos(recurso: Recurso, inicio, fim, ignorar: Reserva | None = None):
    """As reservas que impedem esta janela. Vazio = pode reservar."""
    consulta = Reserva.objects.que_conflitam(recurso, inicio, fim).select_related(
        "solicitante"
    )
    return consulta.exclude(pk=ignorar.pk) if ignorar else consulta


# ── Reservar ────────────────────────────────────────────────────────


def _validar_janela(recurso: Recurso, inicio, fim) -> None:
    """O que é impossível independentemente de quem já reservou."""
    if not inicio or not fim:
        raise ReservaError("Informe o início e o fim.")
    if fim <= inicio:
        raise ReservaError("O fim tem de ser depois do início.")

    agora = timezone.now()
    if inicio < agora:
        # Reservar no passado não bloqueia nada e suja a agenda. Registrar uso
        # que já aconteceu é outra funcionalidade, com outro nome.
        raise ReservaError("Não é possível reservar um horário que já passou.")
    if inicio > agora + ANTECEDENCIA_MAXIMA:
        raise ReservaError(
            f"Reserva com mais de {ANTECEDENCIA_MAXIMA.days} dias de antecedência "
            "precisa passar pelo responsável do recurso."
        )

    limite = timedelta(hours=recurso.duracao_maxima_horas)
    if fim - inicio > limite:
        raise ReservaError(
            f"{recurso.nome} pode ser reservado por até "
            f"{recurso.duracao_maxima_horas} horas seguidas."
        )


@transaction.atomic
def reservar(recurso: Recurso, pessoa, inicio, fim, motivo: str = "") -> Reserva:
    """Cria a reserva, ou levanta explicando quem já está no horário.

    `select_for_update` na linha do RECURSO: entre a checagem de conflito e o
    `create` existe uma janela, e sem o lock duas pessoas clicando ao mesmo
    segundo reservariam a mesma sala. Travar por recurso, e não a tabela, mantém
    salas diferentes em paralelo.
    """
    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        raise ReservaError("Reservar exige saber quem reservou.")

    # Relê o recurso COM lock. Usar o objeto que veio de fora deixaria o lock
    # sem efeito — é a linha do banco que precisa estar travada, não a instância.
    travado = Recurso.objects.select_for_update().filter(pk=recurso.pk).first()
    if travado is None or not travado.ativo:
        raise ReservaError("Este recurso não está disponível.")

    _validar_janela(travado, inicio, fim)

    choques = list(conflitos(travado, inicio, fim))
    if choques:
        primeiro = choques[0]
        de = timezone.localtime(primeiro.inicio)
        ate = timezone.localtime(primeiro.fim)
        quem = primeiro.solicitante.get_short_name() or primeiro.solicitante.get_username()
        # Diz QUEM e QUANDO. "Horário indisponível" faz a pessoa tentar de novo
        # às cegas; com o nome ela resolve por conversa, que é mais rápido.
        raise ReservaError(
            f"{travado.nome} já está reservado por {quem} "
            f"de {de:%H:%M} a {ate:%H:%M} em {de:%d/%m}."
        )

    return Reserva.objects.create(
        recurso=travado, solicitante=pessoa, inicio=inicio, fim=fim, motivo=motivo[:200]
    )


@transaction.atomic
def cancelar(reserva: Reserva, quem) -> Reserva:
    """Cancela. Só o solicitante, ou quem administra recurso."""
    from identidade.services.autorizacao import pode

    e_o_solicitante = reserva.solicitante_id == getattr(quem, "pk", None)
    if not e_o_solicitante and not pode(quem, "res.admin.global"):
        raise ReservaError("Só quem reservou pode cancelar.")
    if not reserva.pode_cancelar:
        raise ReservaError(
            "Reserva já cancelada."
            if reserva.situacao == SituacaoReserva.CANCELADA
            else "Reserva já terminou — cancelar não muda nada."
        )

    reserva.situacao = SituacaoReserva.CANCELADA
    reserva.cancelado_em = timezone.now()
    reserva.cancelado_por = quem
    reserva.save(update_fields=["situacao", "cancelado_em", "cancelado_por"])
    return reserva
