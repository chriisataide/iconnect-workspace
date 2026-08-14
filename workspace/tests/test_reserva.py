"""Reserva de recursos — e o único requisito que não pode falhar.

**Duas reservas do mesmo recurso não podem se sobrepor.** Todo o resto deste
módulo é conveniência. Um sistema de reserva que aceita choque é pior que a
planilha compartilhada que ele substitui, porque a planilha pelo menos deixa o
conflito visível.

A garantia não está no banco: `ExclusionConstraint` com `tstzrange` é exclusivo
do PostgreSQL, e o desenvolvimento roda SQLite — constraint que existe em produção
e não em desenvolvimento é pior que nenhuma. Ela mora em `services/reserva.py`,
então **estes testes são a única prova de que ela funciona.**
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.models import Papel
from identidade.tests import fabricas as f
from workspace.models.reserva import (
    Recurso,
    Reserva,
    SituacaoReserva,
    TipoRecurso,
)
from workspace.services import reserva as res

pytestmark = pytest.mark.django_db


def _base():
    """A próxima hora cheia. Base única para o teste não brigar com o relógio."""
    return (timezone.now() + timedelta(hours=1)).replace(
        minute=0, second=0, microsecond=0
    )


def na_agenda(hora: int):
    """Um horário do PRÓXIMO dia útil, dentro dos `HORARIOS` do formulário.

    Só para os testes que passam pela TELA. Eles usavam `daqui(n)`, e isso os
    fazia depender da hora em que alguém rodasse a suíte: a partir das 13h,
    `daqui(4)` caía depois das 17:00 — fora da agenda que o formulário oferece —
    e o teste de conflito reprovava com "horário inválido", que não é o defeito
    que ele procura. De manhã, passava.

    É o segundo flake por relógio desta suíte; o outro publicava com data de
    hoje às 08:00 e falhava de madrugada. Teste que depende da hora do dia não
    é teste, é sorte — e o serviço continua sendo exercitado com `daqui()`,
    porque ali a agenda comercial não entra na conta.
    """
    dia = timezone.localtime() + timedelta(days=1)
    while dia.weekday() >= 5:  # sábado e domingo não têm agenda
        dia += timedelta(days=1)
    return dia.replace(hour=hora, minute=0, second=0, microsecond=0)


def daqui(horas: float):
    """Deslocamento a partir da próxima hora cheia.

    Somar sobre uma base fixa, e não truncar depois de somar: truncar fazia
    `daqui(0.5)` cair na hora ATUAL — passado — e o caso de "encostada antes"
    reprovava por um motivo que não era o testado.
    """
    return _base() + timedelta(hours=horas)


@pytest.fixture
def cenario():
    ana, bruno, facilities = (f.pessoa(n) for n in ("ana", "bruno", "facilities"))
    for pessoa in (ana, bruno, facilities):
        f.lotar(pessoa)

    papel = f.papel("logistica", ["res.admin.global"], escopo="global")
    f.atribuir(facilities, papel)

    sala = Recurso.objects.create(
        codigo="sala-reuniao", nome="Sala de reunião", tipo=TipoRecurso.SALA,
        capacidade=8, duracao_maxima_horas=8,
    )
    carro = Recurso.objects.create(
        codigo="van-1", nome="Van 1", tipo=TipoRecurso.VEICULO,
        duracao_maxima_horas=12,
    )
    return {
        "ana": ana, "bruno": bruno, "facilities": facilities,
        "sala": sala, "carro": carro,
    }


# ── O requisito que não pode falhar ─────────────────────────────────


def test_sobreposicao_e_recusada(cenario):
    res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4))

    with pytest.raises(res.ReservaError):
        res.reservar(cenario["sala"], cenario["bruno"], daqui(3), daqui(5))

    assert Reserva.objects.confirmadas().count() == 1


@pytest.mark.parametrize(
    ("inicio", "fim", "conflita"),
    [
        (5, 7, True),      # começa no meio
        (3, 5, True),      # termina no meio
        (3, 7, True),      # engole a existente
        (4.5, 5.5, True),  # inteiramente dentro
        (4, 6, True),      # exatamente igual
        (6, 8, False),     # encostada DEPOIS
        (2, 4, False),     # encostada ANTES
        (8, 10, False),    # bem depois
    ],
)
def test_todas_as_formas_de_sobreposicao(cenario, inicio, fim, conflita):
    """A tabela inteira, porque errar um caso é o suficiente.

    Os dois casos `False` de encostada são os mais importantes: reserva que
    termina 11:00 e outra que começa 11:00 NÃO é conflito, e tratá-las como
    choque faria a sala parecer lotada com metade do dia livre.
    """
    res.reservar(cenario["sala"], cenario["ana"], daqui(4), daqui(6))

    if conflita:
        with pytest.raises(res.ReservaError):
            res.reservar(cenario["sala"], cenario["bruno"], daqui(inicio), daqui(fim))
    else:
        assert res.reservar(cenario["sala"], cenario["bruno"], daqui(inicio), daqui(fim))


def test_recursos_diferentes_no_mesmo_horario(cenario):
    """O lock é por RECURSO. Duas salas diferentes seguem em paralelo."""
    res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4))
    assert res.reservar(cenario["carro"], cenario["bruno"], daqui(2), daqui(4))


def test_reserva_cancelada_libera_o_horario(cenario):
    reserva = res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4))
    res.cancelar(reserva, cenario["ana"])

    assert res.reservar(cenario["sala"], cenario["bruno"], daqui(2), daqui(4))


def test_erro_de_conflito_diz_quem_e_quando(cenario):
    """"Horário indisponível" faz a pessoa tentar às cegas; com o nome ela
    resolve por conversa, que é mais rápido."""
    res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4), motivo="Reunião")

    with pytest.raises(res.ReservaError) as falha:
        res.reservar(cenario["sala"], cenario["bruno"], daqui(3), daqui(5))

    mensagem = str(falha.value)
    assert "ana" in mensagem.lower()
    assert f"{timezone.localtime(daqui(2)):%H:%M}" in mensagem


# ── A janela ────────────────────────────────────────────────────────


def test_fim_antes_do_inicio(cenario):
    with pytest.raises(res.ReservaError):
        res.reservar(cenario["sala"], cenario["ana"], daqui(4), daqui(2))


def test_janela_de_duracao_zero(cenario):
    with pytest.raises(res.ReservaError):
        res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(2))


def test_nao_reserva_no_passado(cenario):
    """Reservar no passado não bloqueia nada e suja a agenda."""
    with pytest.raises(res.ReservaError):
        res.reservar(cenario["sala"], cenario["ana"], daqui(-4), daqui(-2))


def test_duracao_maxima_do_recurso(cenario):
    """Recurso preso por três meses bloqueia todo mundo."""
    with pytest.raises(res.ReservaError) as falha:
        res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(2 + 9))

    assert "8 horas" in str(falha.value)
    # A van aceita 12 — o limite é por recurso, não global.
    assert res.reservar(cenario["carro"], cenario["ana"], daqui(2), daqui(2 + 10))


def test_antecedencia_maxima(cenario):
    """Pega o erro de digitação de ano, que é o caso real."""
    longe = timezone.now() + res.ANTECEDENCIA_MAXIMA + timedelta(days=2)

    with pytest.raises(res.ReservaError) as falha:
        res.reservar(cenario["sala"], cenario["ana"], longe, longe + timedelta(hours=1))

    assert "antecedência" in str(falha.value)


def test_janela_incompleta(cenario):
    with pytest.raises(res.ReservaError):
        res.reservar(cenario["sala"], cenario["ana"], None, daqui(4))


def test_recurso_inativo(cenario):
    cenario["sala"].ativo = False
    cenario["sala"].save()

    with pytest.raises(res.ReservaError):
        res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4))


def test_anonimo_nao_reserva(cenario):
    from django.contrib.auth.models import AnonymousUser

    with pytest.raises(res.ReservaError):
        res.reservar(cenario["sala"], AnonymousUser(), daqui(2), daqui(4))


# ── Cancelar ────────────────────────────────────────────────────────


def test_so_quem_reservou_cancela(cenario):
    reserva = res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4))

    with pytest.raises(res.ReservaError):
        res.cancelar(reserva, cenario["bruno"])


def test_quem_administra_recurso_cancela(cenario):
    """Sala presa por quem saiu de férias precisa ser liberada por alguém."""
    reserva = res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4))

    res.cancelar(reserva, cenario["facilities"])

    reserva.refresh_from_db()
    assert reserva.situacao == SituacaoReserva.CANCELADA
    assert reserva.cancelado_por == cenario["facilities"]


def test_nao_cancela_duas_vezes(cenario):
    reserva = res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4))
    res.cancelar(reserva, cenario["ana"])

    with pytest.raises(res.ReservaError):
        res.cancelar(reserva, cenario["ana"])


def test_nao_cancela_o_que_ja_terminou(cenario):
    """Cancelar o que passou não muda nada e confunde o histórico."""
    reserva = res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4))
    Reserva.objects.filter(pk=reserva.pk).update(
        inicio=daqui(-4), fim=daqui(-2)
    )
    reserva.refresh_from_db()

    with pytest.raises(res.ReservaError):
        res.cancelar(reserva, cenario["ana"])


# ── Agenda ──────────────────────────────────────────────────────────


def test_agenda_do_dia_mostra_o_que_esta_ocupado(cenario):
    """A tela mostra a agenda ANTES do formulário: sem isso a pessoa tenta por
    adivinhação."""
    res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4))

    agenda = list(res.agenda_do_dia(cenario["sala"], timezone.localdate()))

    assert len(agenda) == 1


def test_agenda_nao_mostra_cancelada(cenario):
    reserva = res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4))
    res.cancelar(reserva, cenario["ana"])

    assert not list(res.agenda_do_dia(cenario["sala"], timezone.localdate()))


def test_agenda_de_outro_dia(cenario):
    res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4))
    amanha = timezone.localdate() + timedelta(days=1)

    assert not list(res.agenda_do_dia(cenario["sala"], amanha))


def test_agrupados_na_ordem_do_enum(cenario):
    """Sala primeiro, que é o mais reservado — não alfabética."""
    grupos = list(res.agrupados_para(cenario["ana"]))

    assert grupos == ["Sala", "Veículo"]


def test_recurso_inativo_sai_da_vitrine(cenario):
    cenario["carro"].ativo = False
    cenario["carro"].save()

    assert list(res.agrupados_para(cenario["ana"])) == ["Sala"]


def test_em_curso_e_passou(cenario):
    reserva = res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4))
    assert not reserva.em_curso
    assert not reserva.passou
    assert reserva.pode_cancelar
    assert reserva.duracao == timedelta(hours=2)

    Reserva.objects.filter(pk=reserva.pk).update(inicio=daqui(-1), fim=daqui(1))
    reserva.refresh_from_db()
    assert reserva.em_curso


# ── As telas ────────────────────────────────────────────────────────


def test_vitrine_e_publica(client, cenario):
    """A agenda e a reserva são abertas na rede da empresa."""
    resposta = client.get(reverse("workspace:reservas"))

    assert resposta.status_code == 200
    assert "Sala de reunião" in resposta.content.decode()


def test_reservar_e_aberto(client, cenario):
    resposta = client.get(reverse("workspace:reservar", args=("sala-reuniao",)))

    assert resposta.status_code == 200


def test_dia_invalido_na_url_mostra_hoje(client, cenario):
    """`?dia=abacaxi` é editável na barra de endereço — a resposta certa é hoje,
    não erro 500."""
    resposta = client.get(reverse("workspace:reservas"), {"dia": "abacaxi"})

    assert resposta.status_code == 200
    assert resposta.context["dia"] == timezone.localdate()


def test_reserva_pela_tela(client, cenario):
    client.force_login(cenario["ana"])
    # `na_agenda` e não `daqui`: o formulário só oferece 08:00–17:00, e rodar a
    # suíte às 15h fazia `daqui(3)` cair fora dela.
    inicio = na_agenda(9)

    resposta = client.post(
        reverse("workspace:reservar", args=("sala-reuniao",)),
        {
            "dia": timezone.localtime(inicio).strftime("%Y-%m-%d"),
            "de": timezone.localtime(inicio).strftime("%H:%M"),
            "ate": timezone.localtime(inicio + timedelta(hours=1)).strftime("%H:%M"),
            "motivo": "Reunião de fechamento",
        },
    )

    assert resposta.status_code == 302
    reserva = Reserva.objects.get()
    assert reserva.solicitante == cenario["ana"]
    assert reserva.motivo == "Reunião de fechamento"


def test_conflito_pela_tela_mostra_o_motivo(client, cenario):
    res.reservar(
        cenario["sala"], cenario["bruno"],
        na_agenda(9), na_agenda(11), motivo="Visita",
    )
    client.force_login(cenario["ana"])
    inicio = na_agenda(10)

    corpo = client.post(
        reverse("workspace:reservar", args=("sala-reuniao",)),
        {
            "dia": timezone.localtime(inicio).strftime("%Y-%m-%d"),
            "de": timezone.localtime(inicio).strftime("%H:%M"),
            "ate": timezone.localtime(inicio + timedelta(hours=1)).strftime("%H:%M"),
        },
    ).content.decode()

    assert "já está reservado" in corpo
    assert "bruno" in corpo.lower()


def test_hora_invalida_pela_tela(client, cenario):
    client.force_login(cenario["ana"])

    corpo = client.post(
        reverse("workspace:reservar", args=("sala-reuniao",)),
        {"dia": "2026-08-20", "de": "abacaxi", "ate": "10:00"},
    ).content.decode()

    assert "inválida" in corpo
    assert not Reserva.objects.exists()


def test_campo_faltando_pela_tela(client, cenario):
    client.force_login(cenario["ana"])

    corpo = client.post(
        reverse("workspace:reservar", args=("sala-reuniao",)), {"dia": "2026-08-20"}
    ).content.decode()

    assert "Informe o dia" in corpo


def test_minhas_reservas(client, cenario):
    res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4))
    res.reservar(cenario["carro"], cenario["bruno"], daqui(2), daqui(4))

    client.force_login(cenario["ana"])
    corpo = client.get(reverse("workspace:minhas_reservas")).content.decode()

    assert "Sala de reunião" in corpo
    assert "Van 1" not in corpo, "reserva de outra pessoa não aparece"


def test_cancelar_pela_tela(client, cenario):
    reserva = res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4))
    client.force_login(cenario["ana"])

    client.post(reverse("workspace:cancelar_reserva", args=(reserva.pk,)))

    reserva.refresh_from_db()
    assert reserva.situacao == SituacaoReserva.CANCELADA


def test_get_nao_cancela(client, cenario):
    reserva = res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4))
    client.force_login(cenario["ana"])

    client.get(reverse("workspace:cancelar_reserva", args=(reserva.pk,)))

    reserva.refresh_from_db()
    assert reserva.situacao == SituacaoReserva.CONFIRMADA


def test_cancelar_de_outro_mostra_erro(client, cenario):
    reserva = res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4))
    client.force_login(cenario["bruno"])

    resposta = client.post(
        reverse("workspace:cancelar_reserva", args=(reserva.pk,)), follow=True
    )

    assert "Só quem reservou" in resposta.content.decode()


def test_tile_de_reservas_e_destino_real(client, cenario):
    resposta = client.get(reverse("workspace:home"))
    tile = next(a for a in resposta.context["apps"] if a.chave == "reservas")

    assert tile.disponivel
    assert tile.destino == reverse("workspace:reservas")


def test_reserva_de_hoje_aparece_no_meu_dia(cenario):
    from workspace.services import meu_dia as md

    res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4), motivo="Reunião")

    bloco = next(
        b for b in md.para(cenario["ana"])["blocos"] if b.chave == "reservas_hoje"
    )
    assert bloco.itens[0].titulo == "Sala de reunião"
    assert not bloco.urgente, "é lembrete, não pendência"


def test_telas_sem_estilo_inline(client, cenario):
    res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4))
    client.force_login(cenario["ana"])

    for rota, args in [
        ("workspace:reservas", ()),
        ("workspace:reservar", ("sala-reuniao",)),
        ("workspace:minhas_reservas", ()),
    ]:
        corpo = client.get(reverse(rota, args=args)).content.decode()
        assert "style=" not in corpo, f"{rota} tem estilo inline"


def test_str_dos_models(cenario):
    reserva = res.reservar(cenario["sala"], cenario["ana"], daqui(2), daqui(4))

    assert str(cenario["sala"]) == "Sala de reunião"
    assert "Sala de reunião" in str(reserva)


def test_clean_do_model(cenario):
    from django.core.exceptions import ValidationError

    reserva = Reserva(
        recurso=cenario["sala"], solicitante=cenario["ana"],
        inicio=daqui(4), fim=daqui(2),
    )
    with pytest.raises(ValidationError):
        reserva.clean()


def test_papel_de_logistica_administra_recurso():
    """Facilities: quem cuida de material também cuida de sala e veículo."""
    from io import StringIO

    from django.core.management import call_command

    call_command("semear_papeis", "--aplicar", stdout=StringIO())
    logistica = Papel.objects.get(chave="logistica")

    assert "res.admin.global" in logistica.permissoes
    assert "cor.registrar.global" in logistica.permissoes


def test_autoatendimento_inclui_reservar():
    from identidade.papeis import AUTOATENDIMENTO

    assert "res.reservar.proprio" in AUTOATENDIMENTO
    assert "cor.ler.proprio" in AUTOATENDIMENTO


def test_minhas_de_anonimo_e_vazio():
    from django.contrib.auth.models import AnonymousUser

    assert not res.minhas(AnonymousUser()).exists()
    assert not res.minhas(None).exists()
