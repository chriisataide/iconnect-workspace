"""Correspondências — o valor está no aviso, não no cadastro.

Uma carta chega, fica na recepção, e a pessoa nunca sabe. Duas semanas depois é
uma intimação com prazo vencido. Registrar sem notificar troca a pilha na mesa por
uma pilha no banco de dados — e a segunda é pior, porque ninguém passa por ela
sem querer.

Por isso o teste mais importante deste arquivo é `test_registrar_avisa_o_destinatario`.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from django.conf import settings

from identidade.tests import fabricas as f
from workspace.models import Notificacao, TipoNotificacao
from workspace.models.correspondencia import (
    Correspondencia,
    SituacaoCorrespondencia,
    TipoCorrespondencia,
)
from workspace.services import correspondencia as cor

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    ana, bruno, recepcao = (f.pessoa(n) for n in ("ana", "bruno", "recepcao"))
    unidade = f.unidade("MTZ", "Matriz")
    for pessoa in (ana, bruno, recepcao):
        f.lotar(pessoa, uni=unidade)

    papel = f.papel("logistica", ["cor.registrar.global"], escopo="global")
    f.atribuir(recepcao, papel)

    return {"ana": ana, "bruno": bruno, "recepcao": recepcao, "unidade": unidade}


def registrar(cenario, **kwargs):
    padrao = {
        "tipo": TipoCorrespondencia.CARTA,
        "remetente": "Banco Central",
        "destinatario": cenario["ana"],
    }
    return cor.registrar(cenario["recepcao"], **{**padrao, **kwargs})


# ── O aviso ─────────────────────────────────────────────────────────


def test_registrar_avisa_o_destinatario(cenario):
    """A razão de o módulo existir."""
    registrar(cenario)

    aviso = Notificacao.objects.de(cenario["ana"]).get()
    assert aviso.tipo == TipoNotificacao.CORRESPONDENCIA_RECEBIDA
    assert "Carta para você" in aviso.titulo
    assert "Banco Central" in aviso.corpo
    assert aviso.url == reverse("workspace:correspondencias")


def test_intimacao_avisa_com_prazo_legal(cenario):
    registrar(cenario, tipo=TipoCorrespondencia.INTIMACAO)

    aviso = Notificacao.objects.de(cenario["ana"]).get()
    assert "prazo legal" in aviso.titulo


def test_sem_destinatario_nao_avisa_ninguem(cenario):
    """Não há a quem avisar — e inventar um destinatário para fechar a fila
    faria a correspondência chegar à pessoa errada."""
    registrar(cenario, destinatario=None, nome_no_envelope="A/C Financeiro")

    assert not Notificacao.objects.exists()


def test_identificar_avisa_na_hora(cenario):
    """É o único momento em que a pessoa pode saber que algo chegou: no
    registro, ninguém sabia quem era."""
    registro = registrar(cenario, destinatario=None, nome_no_envelope="Ana P.")
    assert not Notificacao.objects.exists()

    cor.identificar(registro, cenario["ana"], cenario["recepcao"])

    assert Notificacao.objects.de(cenario["ana"]).count() == 1


def test_so_o_destinatario_e_avisado(cenario):
    registrar(cenario)

    assert not Notificacao.objects.de(cenario["bruno"]).exists()


# ── Urgência derivada do tipo ───────────────────────────────────────


@pytest.mark.parametrize(
    "tipo", [TipoCorrespondencia.INTIMACAO, TipoCorrespondencia.MULTA]
)
def test_tipo_com_prazo_legal_e_urgente(cenario, tipo):
    """Derivado, não pedido no formulário: quem registra não tem como saber que
    intimação tem prazo, e o remetente não avisa."""
    registro = registrar(cenario, tipo=tipo)

    assert registro.urgente


@pytest.mark.parametrize(
    "tipo",
    [
        TipoCorrespondencia.CARTA,
        TipoCorrespondencia.ENCOMENDA,
        TipoCorrespondencia.DOCUMENTO,
    ],
)
def test_tipo_comum_nao_e_urgente(cenario, tipo):
    assert not registrar(cenario, tipo=tipo).urgente


# ── Permissão ───────────────────────────────────────────────────────


def test_quem_nao_opera_a_recepcao_nao_registra(cenario):
    with pytest.raises(cor.CorrespondenciaError):
        cor.registrar(
            cenario["ana"], tipo=TipoCorrespondencia.CARTA, destinatario=cenario["bruno"]
        )


def test_a_fila_nao_e_publica(cenario):
    """Correspondência revela quem recebe intimação e de quem — informação
    sensível sobre a vida da pessoa. A fila é de quem opera a recepção, e não
    de gestores."""
    registrar(cenario)

    assert cor.fila(cenario["recepcao"]).count() == 1
    assert cor.fila(cenario["ana"]).count() == 0
    assert cor.nao_identificadas(cenario["ana"]).count() == 0


def test_a_pessoa_ve_a_propria(cenario):
    registrar(cenario)

    assert cor.minhas(cenario["ana"]).count() == 1
    assert cor.minhas(cenario["bruno"]).count() == 0


def test_anonimo_nao_ve_nada(cenario):
    from django.contrib.auth.models import AnonymousUser

    registrar(cenario)

    assert cor.minhas(AnonymousUser()).count() == 0
    assert cor.aguardando_de(None) == 0


# ── Registro ────────────────────────────────────────────────────────


def test_sem_destinatario_e_sem_nome_e_recusado(cenario):
    """Sem FK e sem nome, ninguém se reconhece na fila — a correspondência nasce
    perdida."""
    with pytest.raises(cor.CorrespondenciaError):
        registrar(cenario, destinatario=None, nome_no_envelope="")


def test_tipo_invalido(cenario):
    with pytest.raises(cor.CorrespondenciaError):
        registrar(cenario, tipo="telepatia")


def test_nome_no_envelope_permite_reconhecimento(cenario):
    """É o nome COMO VEIO, e é o que faz alguém se achar na fila de não
    identificados."""
    registro = registrar(
        cenario, destinatario=None, nome_no_envelope="ANNA PRADO"
    )

    assert not registro.identificada
    assert registro.nome_no_envelope == "ANNA PRADO"
    assert registro in list(cor.nao_identificadas(cenario["recepcao"]))


# ── Entrega ─────────────────────────────────────────────────────────


def test_entregar_registra_quem_retirou(cenario):
    registro = registrar(cenario)

    cor.entregar(registro, cenario["recepcao"])

    registro.refresh_from_db()
    assert registro.situacao == SituacaoCorrespondencia.ENTREGUE
    assert registro.retirado_por == cenario["ana"]
    assert registro.retirado_em is not None


def test_retirada_por_terceiro(cenario):
    """Secretária, colega, motoboy. Forçar que seja o destinatário faria a
    recepção registrar mentira para fechar a fila — e aí a trilha não vale."""
    registro = registrar(cenario)

    cor.entregar(registro, cenario["recepcao"], retirado_por=cenario["bruno"])

    registro.refresh_from_db()
    assert registro.retirado_por == cenario["bruno"]
    assert registro.destinatario == cenario["ana"]


def test_nao_entrega_duas_vezes(cenario):
    registro = registrar(cenario)
    cor.entregar(registro, cenario["recepcao"])

    with pytest.raises(cor.CorrespondenciaError):
        cor.entregar(registro, cenario["recepcao"])


def test_entregue_sai_da_fila(cenario):
    registro = registrar(cenario)
    cor.entregar(registro, cenario["recepcao"])

    assert cor.fila(cenario["recepcao"]).count() == 0
    assert cor.aguardando_de(cenario["ana"]) == 0
    assert cor.minhas(cenario["ana"]).count() == 1, "segue no histórico"


def test_devolver_exige_motivo(cenario):
    """Devolução sem motivo é sumiço."""
    registro = registrar(cenario)

    with pytest.raises(cor.CorrespondenciaError):
        cor.devolver(registro, cenario["recepcao"], motivo="   ")

    cor.devolver(registro, cenario["recepcao"], motivo="Pessoa desligada em maio.")
    registro.refresh_from_db()
    assert registro.situacao == SituacaoCorrespondencia.DEVOLVIDA
    assert "desligada" in registro.observacao


def test_nao_devolve_o_que_ja_saiu(cenario):
    registro = registrar(cenario)
    cor.entregar(registro, cenario["recepcao"])

    with pytest.raises(cor.CorrespondenciaError):
        cor.devolver(registro, cenario["recepcao"], motivo="x")


def test_identificar_o_que_ja_tem_destinatario(cenario):
    registro = registrar(cenario)

    with pytest.raises(cor.CorrespondenciaError):
        cor.identificar(registro, cenario["bruno"], cenario["recepcao"])


def test_identificar_o_que_ja_saiu(cenario):
    registro = registrar(cenario, destinatario=None, nome_no_envelope="X")
    registro.situacao = SituacaoCorrespondencia.DEVOLVIDA
    registro.save()

    with pytest.raises(cor.CorrespondenciaError):
        cor.identificar(registro, cenario["ana"], cenario["recepcao"])


def test_identificar_exige_permissao(cenario):
    registro = registrar(cenario, destinatario=None, nome_no_envelope="X")

    with pytest.raises(cor.CorrespondenciaError):
        cor.identificar(registro, cenario["ana"], cenario["bruno"])


def test_entregar_exige_permissao(cenario):
    registro = registrar(cenario)

    with pytest.raises(cor.CorrespondenciaError):
        cor.entregar(registro, cenario["ana"])


def test_devolver_exige_permissao(cenario):
    registro = registrar(cenario)

    with pytest.raises(cor.CorrespondenciaError):
        cor.devolver(registro, cenario["ana"], motivo="x")


# ── Ordem e contagem ────────────────────────────────────────────────


def test_urgente_vem_primeiro_na_fila(cenario):
    """Numa fila de retirada, prazo legal vem antes — e entre iguais, o que
    espera há mais tempo."""
    registrar(cenario, tipo=TipoCorrespondencia.CARTA, remetente="Comum")
    registrar(cenario, tipo=TipoCorrespondencia.INTIMACAO, remetente="Fórum")

    fila = list(cor.fila(cenario["recepcao"]))

    assert fila[0].remetente == "Fórum"


def test_dias_esperando(cenario):
    registro = registrar(cenario)
    Correspondencia.objects.filter(pk=registro.pk).update(
        recebido_em=timezone.now() - timedelta(days=5)
    )
    registro.refresh_from_db()

    assert registro.dias_esperando == 5


def test_dias_esperando_para_do_que_foi_retirado(cenario):
    """Depois da retirada, o contador congela: "há 40 dias" numa entregue é
    ruído."""
    registro = registrar(cenario)
    cor.entregar(registro, cenario["recepcao"])
    registro.refresh_from_db()

    assert registro.dias_esperando == 0


# ── As telas ────────────────────────────────────────────────────────


def test_tela_exige_login(client, cenario):
    resposta = client.get(reverse("workspace:correspondencias"))

    assert resposta.status_code == 302
    assert settings.LOGIN_URL in resposta["Location"]


def test_quem_nao_opera_nao_ve_o_formulario(client, cenario):
    registrar(cenario)
    client.force_login(cenario["ana"])
    corpo = client.get(reverse("workspace:correspondencias")).content.decode()

    assert "Banco Central" in corpo, "vê a própria"
    assert "Registrar o que chegou" not in corpo
    assert "Fila da recepção" not in corpo


def test_quem_opera_ve_a_fila_e_o_formulario(client, cenario):
    registrar(cenario)
    client.force_login(cenario["recepcao"])
    corpo = client.get(reverse("workspace:correspondencias")).content.decode()

    assert "Fila da recepção" in corpo
    assert "Registrar o que chegou" in corpo


def test_registrar_pela_tela(client, cenario):
    client.force_login(cenario["recepcao"])

    resposta = client.post(
        reverse("workspace:registrar_correspondencia"),
        {
            "tipo": TipoCorrespondencia.ENCOMENDA,
            "destinatario": cenario["ana"].pk,
            "remetente": "Mercado Livre",
            "descricao": "Caixa pequena",
        },
        follow=True,
    )

    assert Correspondencia.objects.count() == 1
    assert "O destinatário foi avisado" in resposta.content.decode()


def test_registrar_sem_destinatario_pela_tela(client, cenario):
    client.force_login(cenario["recepcao"])

    resposta = client.post(
        reverse("workspace:registrar_correspondencia"),
        {"tipo": TipoCorrespondencia.CARTA, "nome_no_envelope": "A/C RH"},
        follow=True,
    )

    corpo = resposta.content.decode()
    assert "registrada" in corpo
    # A frase exata da mensagem, e não a palavra solta: o estado vazio da tela
    # diz "você é avisado aqui e no sino", e procurar "avisado" no HTML inteiro
    # casava com o texto estático.
    assert "O destinatário foi avisado" not in corpo, "não há quem avisar"


def test_registrar_invalido_pela_tela_mostra_o_motivo(client, cenario):
    client.force_login(cenario["recepcao"])

    corpo = client.post(
        reverse("workspace:registrar_correspondencia"),
        {"tipo": TipoCorrespondencia.CARTA},
        follow=True,
    ).content.decode()

    assert "Informe o destinatário" in corpo
    assert not Correspondencia.objects.exists()


def test_registrar_sem_permissao_pela_tela(client, cenario):
    client.force_login(cenario["ana"])

    corpo = client.post(
        reverse("workspace:registrar_correspondencia"),
        {"tipo": TipoCorrespondencia.CARTA, "destinatario": cenario["bruno"].pk},
        follow=True,
    ).content.decode()

    assert "não pode registrar" in corpo


def test_identificar_pela_tela(client, cenario):
    registro = registrar(cenario, destinatario=None, nome_no_envelope="Ana")
    client.force_login(cenario["recepcao"])

    resposta = client.post(
        reverse("workspace:identificar_correspondencia", args=(registro.pk,)),
        {"destinatario": cenario["ana"].pk},
        follow=True,
    )

    registro.refresh_from_db()
    assert registro.destinatario == cenario["ana"]
    assert "foi avisado" in resposta.content.decode()


def test_identificar_sem_escolher_pela_tela(client, cenario):
    registro = registrar(cenario, destinatario=None, nome_no_envelope="Ana")
    client.force_login(cenario["recepcao"])

    resposta = client.post(
        reverse("workspace:identificar_correspondencia", args=(registro.pk,)),
        {},
        follow=True,
    )

    assert "Escolha o destinatário" in resposta.content.decode()


def test_entregar_pela_tela(client, cenario):
    registro = registrar(cenario)
    client.force_login(cenario["recepcao"])

    client.post(reverse("workspace:entregar_correspondencia", args=(registro.pk,)))

    registro.refresh_from_db()
    assert registro.situacao == SituacaoCorrespondencia.ENTREGUE


@pytest.mark.parametrize(
    "rota",
    [
        "workspace:registrar_correspondencia",
        "workspace:entregar_correspondencia",
        "workspace:identificar_correspondencia",
    ],
)
def test_get_nao_muda_estado(client, cenario, rota):
    """Estado não muda em GET — link pré-carregado pelo navegador fecharia a
    fila da recepção sozinho."""
    registro = registrar(cenario)
    client.force_login(cenario["recepcao"])

    args = () if rota.endswith("registrar_correspondencia") else (registro.pk,)
    client.get(reverse(rota, args=args))

    registro.refresh_from_db()
    assert registro.situacao == SituacaoCorrespondencia.AGUARDANDO
    assert Correspondencia.objects.count() == 1


def test_lista_de_destinatarios_e_o_organograma(client, cenario):
    """Os 1432 usuários do iConnect não trabalham aqui — a lista vem de quem
    tem lotação."""
    from django.contrib.auth import get_user_model

    get_user_model().objects.create_user("tecnico-do-iconnect@exemplo.com", password="x")
    client.force_login(cenario["recepcao"])

    pessoas = client.get(reverse("workspace:correspondencias")).context["pessoas"]

    assert "tecnico-do-iconnect" not in [p.email for p in pessoas]
    assert cenario["ana"] in list(pessoas)


def test_correspondencia_aparece_no_meu_dia(cenario):
    from workspace.services import meu_dia as md

    registrar(cenario, tipo=TipoCorrespondencia.INTIMACAO, remetente="Fórum")

    bloco = next(
        b for b in md.para(cenario["ana"])["blocos"] if b.chave == "correspondencia"
    )
    assert bloco.urgente, "intimação parada é o caso que o módulo evita"
    assert "Fórum" in bloco.itens[0].subtitulo


def test_retirada_sai_do_meu_dia(cenario):
    from workspace.services import meu_dia as md

    registro = registrar(cenario)
    cor.entregar(registro, cenario["recepcao"])

    assert "correspondencia" not in {b.chave for b in md.para(cenario["ana"])["blocos"]}


def test_tile_de_correspondencias_e_destino_real(client, cenario):
    resposta = client.get(reverse("workspace:home"))
    tile = next(a for a in resposta.context["apps"] if a.chave == "correspondencias")

    assert tile.disponivel
    assert tile.destino == reverse("workspace:correspondencias")


def test_tela_sem_estilo_inline(client, cenario):
    registrar(cenario, destinatario=None, nome_no_envelope="X")
    client.force_login(cenario["recepcao"])

    corpo = client.get(reverse("workspace:correspondencias")).content.decode()
    assert "style=" not in corpo


def test_str_do_model(cenario):
    identificada = registrar(cenario)
    anonima = registrar(cenario, destinatario=None, nome_no_envelope="A/C RH")
    sem_nada = Correspondencia(
        tipo=TipoCorrespondencia.CARTA, recebido_por=cenario["recepcao"]
    )

    assert "ana" in str(identificada)
    assert "A/C RH" in str(anonima)
    assert "não identificado" in str(sem_nada)


def test_entregar_o_que_ja_saiu_pela_tela_mostra_o_motivo(client, cenario):
    """Dois cliques em "Retirada" — o segundo tem de dizer o que houve, e não
    voltar em silêncio como se tivesse funcionado."""
    registro = registrar(cenario)
    cor.entregar(registro, cenario["recepcao"])
    client.force_login(cenario["recepcao"])

    resposta = client.post(
        reverse("workspace:entregar_correspondencia", args=(registro.pk,)), follow=True
    )

    assert "já está entregue" in resposta.content.decode()


def test_identificar_o_que_ja_tem_dono_pela_tela_mostra_o_motivo(client, cenario):
    registro = registrar(cenario)
    client.force_login(cenario["recepcao"])

    resposta = client.post(
        reverse("workspace:identificar_correspondencia", args=(registro.pk,)),
        {"destinatario": cenario["bruno"].pk},
        follow=True,
    )

    assert "já tem destinatário" in resposta.content.decode()
    registro.refresh_from_db()
    assert registro.destinatario == cenario["ana"], "o destinatário não mudou"
