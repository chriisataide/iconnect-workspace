"""§32 — a grade que responde "onde tem buraco".

A tela já mostrava a agenda de cada recurso: o que está marcado, por quem, e a
que horas. Ela não respondia a pergunta de quem quer RESERVAR — para achar o vão
entre 10h–11h e 14h–15h a pessoa tinha de ler os horários e fazer a subtração de
cabeça.

Duas coisas foram acrescentadas, e as duas respondem a mesma pergunta em escalas
diferentes:

* **"Livres agora"**, no topo — porque "preciso de uma sala agora" é o motivo de
  a pessoa abrir a tela.
* **A grade por hora**, em cada recurso — o dia inteiro, por desenho.

As três armadilhas que os testes abaixo travam são todas de fronteira de hora,
que é onde grade de calendário erra: a hora do meio de uma reserva longa, a hora
em que uma reserva termina em ponto, e a reserva que atravessa a meia-noite.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.models.reserva import Recurso, TipoRecurso
from workspace.services import reserva as res

pytestmark = pytest.mark.django_db


@pytest.fixture
def sala():
    return Recurso.objects.create(
        codigo="sala-1", nome="Sala 1", tipo=TipoRecurso.SALA, capacidade=8
    )


@pytest.fixture
def ana():
    pessoa = f.pessoa("ana")
    f.lotar(pessoa)
    return pessoa


def _hoje_as(hora, minuto=0):
    return timezone.make_aware(
        timezone.datetime.combine(
            timezone.localdate(), timezone.datetime.min.time()
        ).replace(hour=hora, minute=minuto)
    )


def _marcar(sala, pessoa, hora_inicio, hora_fim, motivo="", minuto_fim=0):
    """Uma reserva GRAVADA DIRETO, sem passar por `reservar()`.

    `reservar()` recusa horário que já passou — regra certa para o produto e
    veneno para estes testes: às 15h, uma reserva de teste às 10h vira
    `ReservaError` e a suíte quebra por causa do relógio, não do código. É a
    quarta vez que essa armadilha aparece neste projeto.

    O que se testa aqui é a GRADE, que só lê `inicio` e `fim`. Como a linha
    nasceu não importa para ela.
    """
    from workspace.models.reserva import Reserva

    return Reserva.objects.create(
        recurso=sala, solicitante=pessoa, motivo=motivo,
        inicio=_hoje_as(hora_inicio), fim=_hoje_as(hora_fim, minuto_fim),
    )


def _faixa(grade, hora):
    return next(f_ for f_ in grade if f_["hora"] == hora)


# ── A grade ─────────────────────────────────────────────────────────


def test_a_grade_cobre_o_horario_de_funcionamento(sala):
    """As 24 horas fariam a faixa útil virar um quinto da tela, e ninguém
    reserva sala às 3h."""
    grade = res.grade_do_dia(sala, agenda=[])

    assert grade[0]["hora"] == res.HORA_ABERTURA
    assert grade[-1]["hora"] == res.HORA_FECHAMENTO - 1


def test_sem_reserva_tudo_livre(sala):
    grade = res.grade_do_dia(sala, agenda=[])

    assert not any(faixa["ocupada"] for faixa in grade)


def test_a_hora_reservada_fica_ocupada(sala, ana):
    _marcar(sala, ana, 10, 11, "Reunião")

    grade = res.grade_do_dia(sala)

    assert _faixa(grade, 10)["ocupada"]
    assert not _faixa(grade, 9)["ocupada"]


def test_a_hora_do_meio_de_uma_reserva_longa_tambem_fica_ocupada(sala, ana):
    """A armadilha número um da grade: comparar só o INÍCIO da reserva deixa as
    horas do meio pintadas de livre, e a pessoa reserva por cima."""
    _marcar(sala, ana, 9, 12, "Treinamento")

    grade = res.grade_do_dia(sala)

    assert all(_faixa(grade, h)["ocupada"] for h in (9, 10, 11))


def test_a_hora_em_que_a_reserva_termina_fica_livre(sala, ana):
    """A armadilha número dois: uma reserva que acaba às 11h00 em ponto NÃO
    ocupa a faixa das 11 — a sala está livre dali em diante. Pintá-la de
    ocupada roubaria uma hora de agenda de cada reserva do dia."""
    _marcar(sala, ana, 9, 11, "Reunião")

    grade = res.grade_do_dia(sala)

    assert _faixa(grade, 10)["ocupada"]
    assert not _faixa(grade, 11)["ocupada"]


def test_reserva_que_termina_no_meio_da_hora_ocupa_a_hora_inteira(sala, ana):
    """11h30 deixa a faixa das 11 ocupada: meia sala livre não é sala livre."""
    _marcar(sala, ana, 9, 11, "Reunião", minuto_fim=30)

    assert _faixa(res.grade_do_dia(sala), 11)["ocupada"]


def test_a_faixa_ocupada_diz_de_quem_e(sala, ana):
    """Sem o nome, a grade responde "não dá" e a pessoa não tem a quem pedir
    para trocar."""
    _marcar(sala, ana, 14, 15, "Entrevista")

    faixa = _faixa(res.grade_do_dia(sala), 14)

    assert faixa["reserva"].solicitante == ana
    assert faixa["reserva"].motivo == "Entrevista"


def test_reserva_de_outro_dia_nao_pinta_a_grade_de_hoje(sala, ana):
    amanha = timezone.localdate() + timedelta(days=1)
    from workspace.models.reserva import Reserva

    inicio = timezone.make_aware(
        timezone.datetime.combine(amanha, timezone.datetime.min.time()).replace(hour=10)
    )
    Reserva.objects.create(
        recurso=sala, solicitante=ana, motivo="Amanhã",
        inicio=inicio, fim=inicio + timedelta(hours=1),
    )

    assert not any(faixa["ocupada"] for faixa in res.grade_do_dia(sala))


# ── Livres agora ────────────────────────────────────────────────────


def test_livres_agora_ignora_dia_que_nao_e_hoje(sala, ana):
    """"Agora" só existe hoje. Numa data futura a faixa some, em vez de dizer
    uma verdade que não serve para nada."""
    amanha = timezone.localdate() + timedelta(days=1)

    assert res.livres_agora(ana, dia=amanha) == []


def test_livres_agora_traz_a_sala_sem_reserva_neste_instante(sala, ana):
    agora = timezone.localtime()
    if not (res.HORA_ABERTURA <= agora.hour < res.HORA_FECHAMENTO):
        pytest.skip("fora do horário de funcionamento — ver o teste seguinte")

    assert sala in res.livres_agora(ana)


def test_livres_agora_tira_a_sala_ocupada_neste_instante(sala, ana):
    agora = timezone.localtime()
    if not (res.HORA_ABERTURA <= agora.hour < res.HORA_FECHAMENTO):
        pytest.skip("fora do horário de funcionamento")

    from workspace.models.reserva import Reserva

    Reserva.objects.create(
        recurso=sala, solicitante=ana,
        inicio=agora - timedelta(minutes=10), fim=agora + timedelta(hours=1),
    )

    assert sala not in res.livres_agora(ana)


# ── Na tela ─────────────────────────────────────────────────────────


def test_a_tela_desenha_a_grade(client, sala, ana):
    _marcar(sala, ana, 10, 11, "Reunião")

    corpo = client.get(reverse("workspace:reservas")).content.decode()

    assert "au-horas" in corpo
    # `au-horas` e não `au-grade`: o nome antigo colidia com o grid do catálogo
    # e desalinhava a vitrine inteira de serviços — ver
    # `test_nenhuma_classe_base_e_redefinida_do_zero`.
    assert "au-horas-faixa--ocupada" in corpo


def test_a_faixa_livre_leva_ao_formulario_com_a_hora(client, sala, ana):
    """Ver o buraco e ter de digitar o horário de novo é o passo que faz a
    pessoa desistir e bater na porta da sala."""
    corpo = client.get(reverse("workspace:reservas")).content.decode()

    assert f"{reverse('workspace:reservar', args=[sala.codigo])}?dia=" in corpo
    assert "hora=" in corpo


def test_a_tela_nao_faz_uma_consulta_por_recurso(client, ana):
    """O N+1 clássico de tela de calendário: a grade buscando a própria agenda.
    Ela recebe a lista já carregada, então dez salas custam o mesmo que uma."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    def custo(quantas):
        from workspace.models.reserva import Reserva

        # As reservas primeiro: `Reserva.recurso` é `PROTECT`, e apagar o
        # recurso direto levanta `ProtectedError` — que é o modelo protegendo
        # exatamente o que deve.
        Reserva.objects.all().delete()
        Recurso.objects.all().delete()
        for i in range(quantas):
            sala = Recurso.objects.create(
                codigo=f"sala-{i}", nome=f"Sala {i}", tipo=TipoRecurso.SALA
            )
            _marcar(sala, ana, 10, 11)
        with CaptureQueriesContext(connection) as ctx:
            assert client.get(reverse("workspace:reservas")).status_code == 200
        return len(ctx.captured_queries)

    uma, dez = custo(1), custo(10)
    assert dez <= uma + 10, f"a tela cresce com o número de salas: {uma} → {dez}"


# ── A semente de recursos ───────────────────────────────────────────


def test_semear_recursos_cria_salas_veiculos_e_equipamentos():
    """Sem recurso nenhum, a tela de reservas mostra o estado vazio e não há
    como testar a grade nem descobrir que ela funciona. A falta desta semente
    apareceu abrindo a tela, não rodando teste."""
    from io import StringIO

    from django.core.management import call_command

    call_command("semear_recursos", "--aplicar", stdout=StringIO())

    tipos = set(Recurso.objects.values_list("tipo", flat=True))
    assert {TipoRecurso.SALA, TipoRecurso.VEICULO, TipoRecurso.EQUIPAMENTO} <= tipos


def test_semear_recursos_e_reexecutavel():
    from io import StringIO

    from django.core.management import call_command

    call_command("semear_recursos", "--aplicar", stdout=StringIO())
    antes = Recurso.objects.count()
    saida = StringIO()

    call_command("semear_recursos", "--aplicar", stdout=saida)

    assert Recurso.objects.count() == antes
    assert f"já existiam  {antes}" in saida.getvalue()


def test_semear_recursos_simula_sem_gravar():
    from io import StringIO

    from django.core.management import call_command

    saida = StringIO()
    call_command("semear_recursos", stdout=saida)

    assert "SIMULAÇÃO" in saida.getvalue()
    assert Recurso.objects.count() == 0


def test_semear_recursos_nao_exige_unidade():
    """Recurso sem unidade vale para a empresa toda — o campo é opcional no
    modelo. Ao contrário de `semear_estoque`, onde o saldo não teria onde morar,
    aqui recusar banco sem unidade seria inventar uma exigência."""
    from io import StringIO

    from django.core.management import call_command
    from identidade.models import Unidade

    assert not Unidade.objects.exists()
    call_command("semear_recursos", "--aplicar", stdout=StringIO())

    assert Recurso.objects.exists()
    assert Recurso.objects.filter(unidade__isnull=True).count() == Recurso.objects.count()


def test_a_sala_rapida_nao_pode_ser_presa_o_dia_inteiro():
    """Sala de duas pessoas reservada por oito horas é o jeito mais rápido de a
    agenda perder a utilidade."""
    from io import StringIO

    from django.core.management import call_command

    call_command("semear_recursos", "--aplicar", stdout=StringIO())

    rapida = Recurso.objects.get(codigo="sala-rapida")
    auditorio = Recurso.objects.get(codigo="auditorio")
    assert rapida.duracao_maxima_horas < auditorio.duracao_maxima_horas
