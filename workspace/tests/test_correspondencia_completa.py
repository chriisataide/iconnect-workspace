"""§6 — a correspondência com o ciclo fechado.

O módulo já registrava e já avisava. Faltavam três coisas, e as três aparecem
quando algo dá errado:

1. **Empresa e rastreio.** Encomenda sumida virava uma conversa de três dias
   porque ninguém sabia por onde ela veio nem com que número.
2. **A data de chegada digitável.** A recepção nem sempre registra na hora — a
   pilha de sexta entra na segunda —, e gravar "segunda" fazia o prazo da
   intimação começar a contar dois dias tarde.
3. **A confirmação de quem recebeu.** `retirado_em` é a recepção dizendo
   "entreguei"; `confirmado_em` é a pessoa dizendo "recebi". Enquanto só existia
   o primeiro, a única versão registrada dos fatos era a de quem entregou — e é
   exatamente essa que não vale nada quando a intimação some.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.models.correspondencia import (
    Correspondencia,
    SituacaoCorrespondencia,
    TipoCorrespondencia,
)
from workspace.services import correspondencia as cor
from workspace.services.correspondencia import CorrespondenciaError

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    recepcao, ana = f.pessoa("recepcao"), f.pessoa("ana")
    f.lotar(recepcao)
    f.lotar(ana)
    f.atribuir(recepcao, f.papel("rec", ["cor.registrar.global"], escopo="global"))
    return {"recepcao": recepcao, "ana": ana}


def registrar(cenario, **extras):
    dados = {
        "tipo": TipoCorrespondencia.ENCOMENDA,
        "remetente": "Loja Alfa",
        "destinatario": cenario["ana"],
    }
    dados.update(extras)
    return cor.registrar(cenario["recepcao"], **dados)


# ── Empresa e rastreio ──────────────────────────────────────────────


def test_empresa_e_remetente_sao_campos_diferentes(cenario):
    """Remetente é QUEM mandou; empresa é POR ONDE veio. Num campo só, uma das
    duas sempre se perde — e são as duas perguntas que a recepção faz ao
    procurar um extravio."""
    registro = registrar(cenario, empresa="Correios", numero_rastreio="BR123456789BR")

    assert registro.remetente == "Loja Alfa"
    assert registro.empresa == "Correios"
    assert registro.numero_rastreio == "BR123456789BR"


def test_o_rastreio_aparece_na_fila_da_recepcao(client, cenario):
    registrar(cenario, empresa="Correios", numero_rastreio="BR123456789BR")
    client.force_login(cenario["recepcao"])

    corpo = client.get(reverse("workspace:correspondencias")).content.decode()

    assert "BR123456789BR" in corpo
    assert "Correios" in corpo


# ── A data de chegada ───────────────────────────────────────────────


def test_a_data_de_chegada_e_digitavel(cenario):
    ontem = timezone.now() - timedelta(days=3)
    registro = registrar(cenario, recebido_em=ontem)

    assert registro.recebido_em.date() == ontem.date()
    assert registro.dias_esperando == 3


def test_sem_data_digitada_vale_agora(cenario):
    registro = registrar(cenario)

    # `localtime(...)` antes do `.date()`: o campo guarda UTC, e depois das 21h
    # aqui o UTC já está no dia seguinte.
    assert timezone.localtime(registro.recebido_em).date() == timezone.localdate()


def test_data_invalida_nao_impede_o_registro(client, cenario):
    """Recusar a correspondência inteira porque alguém digitou `31/02`
    deixaria a intimação sem entrar em lugar nenhum."""
    client.force_login(cenario["recepcao"])

    client.post(
        reverse("workspace:registrar_correspondencia"),
        {
            "tipo": TipoCorrespondencia.CARTA,
            "destinatario": cenario["ana"].pk,
            "recebido_em": "31/02/2026",
        },
    )

    assert Correspondencia.objects.count() == 1


def test_a_data_nao_escorrega_para_o_dia_anterior(client, cenario):
    """`00:00` no fuso local cai no dia anterior em UTC — o prazo da intimação
    passaria a contar um dia antes do que a recepção escreveu."""
    client.force_login(cenario["recepcao"])

    client.post(
        reverse("workspace:registrar_correspondencia"),
        {
            "tipo": TipoCorrespondencia.INTIMACAO,
            "destinatario": cenario["ana"].pk,
            "recebido_em": "2026-03-10",
        },
    )

    assert Correspondencia.objects.get().recebido_em.date() == date(2026, 3, 10)


# ── A confirmação de quem recebeu ───────────────────────────────────


def test_entregar_nao_confirma_sozinho(cenario):
    """As duas metades são versões DIFERENTES do mesmo fato, e é por isso que
    uma não pode valer pela outra."""
    registro = registrar(cenario)
    cor.entregar(registro, cenario["recepcao"])

    assert registro.situacao == SituacaoCorrespondencia.ENTREGUE
    assert registro.confirmado_em is None
    assert registro.espera_confirmacao


def test_o_destinatario_confirma(cenario):
    registro = registrar(cenario)
    cor.entregar(registro, cenario["recepcao"])

    cor.confirmar(registro, cenario["ana"])

    assert registro.confirmada
    assert not registro.espera_confirmacao


def test_so_o_destinatario_confirma(cenario):
    """Nem a recepção, nem quem administra: uma confirmação que outro pode dar
    no seu lugar não confirma nada."""
    registro = registrar(cenario)
    cor.entregar(registro, cenario["recepcao"])

    with pytest.raises(CorrespondenciaError, match="Só quem recebeu"):
        cor.confirmar(registro, cenario["recepcao"])


def test_nao_da_para_confirmar_o_que_nao_foi_entregue(cenario):
    registro = registrar(cenario)

    with pytest.raises(CorrespondenciaError, match="ainda não foi entregue"):
        cor.confirmar(registro, cenario["ana"])


def test_confirmar_duas_vezes_e_silencioso(cenario):
    """Duplo clique e voltar-no-navegador são o modo normal de isto acontecer,
    e um erro aqui assustaria sem motivo — já está registrado."""
    registro = registrar(cenario)
    cor.entregar(registro, cenario["recepcao"])
    cor.confirmar(registro, cenario["ana"])
    primeira = registro.confirmado_em

    cor.confirmar(registro, cenario["ana"])

    registro.refresh_from_db()
    assert registro.confirmado_em == primeira


def test_a_tela_pede_a_confirmacao_de_quem_recebeu(client, cenario):
    registro = registrar(cenario)
    cor.entregar(registro, cenario["recepcao"])
    client.force_login(cenario["ana"])

    corpo = client.get(reverse("workspace:correspondencias")).content.decode()

    assert "Confirme o que você recebeu" in corpo
    assert reverse("workspace:confirmar_correspondencia", args=[registro.pk]) in corpo


def test_a_tela_para_de_pedir_depois_de_confirmado(client, cenario):
    registro = registrar(cenario)
    cor.entregar(registro, cenario["recepcao"])
    cor.confirmar(registro, cenario["ana"])
    client.force_login(cenario["ana"])

    corpo = client.get(reverse("workspace:correspondencias")).content.decode()

    assert "Confirme o que você recebeu" not in corpo


def test_confirmar_pela_tela(client, cenario):
    registro = registrar(cenario)
    cor.entregar(registro, cenario["recepcao"])
    client.force_login(cenario["ana"])

    resposta = client.post(
        reverse("workspace:confirmar_correspondencia", args=[registro.pk])
    )

    assert resposta.status_code == 302
    registro.refresh_from_db()
    assert registro.confirmada


def test_confirmar_correspondencia_de_outro_e_recusado(client, cenario):
    """O mesmo defeito que já vazou uma vez neste produto: ação em nome de
    alguém sem conferir de quem é o objeto."""
    registro = registrar(cenario)
    cor.entregar(registro, cenario["recepcao"])
    bruno = f.pessoa("bruno")
    f.lotar(bruno)
    client.force_login(bruno)

    client.post(reverse("workspace:confirmar_correspondencia", args=[registro.pk]))

    registro.refresh_from_db()
    assert not registro.confirmada


def test_confirmar_exige_sessao(client, cenario):
    registro = registrar(cenario)

    resposta = client.post(
        reverse("workspace:confirmar_correspondencia", args=[registro.pk])
    )

    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/entrar/")
