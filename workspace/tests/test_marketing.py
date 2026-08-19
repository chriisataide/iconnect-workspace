"""§23 — o radar de oportunidades, e o que ele deliberadamente não faz.

## O problema

Marketing já tinha o item "Evento ou patrocínio" no catálogo, com valor, centro
de custo e cadeia de aprovação por faixa. Ele responde bem a uma pergunta —
*aprove esta feira* — e não responde à outra, que é onde a empresa perde
dinheiro.

Alguém encaminha um e-mail sobre uma feira de outubro. O prazo para reservar
stand com inscrição antecipada é junho. O e-mail vira conversa, a conversa
esfria, e em agosto alguém lembra: o stand acabou. O item de catálogo não podia
ajudar, porque ele só existe **depois** de alguém ter decidido pedir.

## O que estes testes guardam

1. **O radar não aprova nada.** Decidir ir é gastar dinheiro, e esse caminho já
   existe. Um segundo fluxo para o mesmo dinheiro seria a duplicação que a frota
   mostrou de perto.
2. **O aviso é sobre o PRAZO DE DECISÃO**, não sobre a data do evento — é o
   prazo que se perde.
3. **Descartar exige motivo.** Sem ele a mesma feira volta todo ano e a
   discussão recomeça do zero.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.models.marketing import (
    Oportunidade,
    SituacaoOportunidade,
    TipoOportunidade,
)
from workspace.models.notificacao import Notificacao, TipoNotificacao
from workspace.services import marketing as mkt
from workspace.services.marketing import MarketingError

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    mkt_pessoa, ana, leitor = (f.pessoa(n) for n in ("marketing", "ana", "leitor"))
    for pessoa in (mkt_pessoa, ana, leitor):
        f.lotar(pessoa)
    f.atribuir(
        mkt_pessoa,
        f.papel("mkt", ["mkt.atender.global", "mkt.ler.global"], escopo="global"),
    )
    f.atribuir(leitor, f.papel("mktler", ["mkt.ler.global"], escopo="global"))
    return {"mkt": mkt_pessoa, "ana": ana, "leitor": leitor}


def registrar(cenario, **extras):
    dados = {
        "titulo": "Feira Intersolar 2027",
        "tipo": TipoOportunidade.FEIRA,
        "prazo_decisao": timezone.localdate() + timedelta(days=5),
    }
    dados.update(extras)
    return mkt.registrar(cenario["mkt"], **dados)


# ── Cadastrar ───────────────────────────────────────────────────────


def test_quem_nao_opera_nao_cadastra(cenario):
    with pytest.raises(MarketingError, match="não pode cadastrar"):
        mkt.registrar(cenario["ana"], titulo="x", tipo=TipoOportunidade.FEIRA)


def test_oportunidade_sem_nome_recusa(cenario):
    with pytest.raises(MarketingError, match="nome"):
        registrar(cenario, titulo="  ")


def test_tipo_invalido_recusa(cenario):
    with pytest.raises(MarketingError, match="Tipo"):
        registrar(cenario, tipo="churrasco")


def test_evento_que_termina_antes_de_comecar_recusa(cenario):
    hoje = timezone.localdate()

    with pytest.raises(MarketingError, match="termina antes"):
        registrar(cenario, data_inicio=hoje, data_fim=hoje - timedelta(days=1))


def test_a_oportunidade_nasce_no_radar(cenario):
    assert registrar(cenario).situacao == SituacaoOportunidade.RADAR


def test_editar_atualiza_a_mesma_linha(cenario):
    oportunidade = registrar(cenario)

    mkt.registrar(
        cenario["mkt"],
        titulo="Feira Intersolar 2027 — São Paulo",
        tipo=TipoOportunidade.FEIRA,
        oportunidade=oportunidade,
    )
    oportunidade.refresh_from_db()

    assert Oportunidade.objects.count() == 1
    assert "São Paulo" in oportunidade.titulo


def test_quem_cadastrou_fica_registrado(cenario):
    assert registrar(cenario).criado_por == cenario["mkt"]


# ── O prazo ─────────────────────────────────────────────────────────


def test_o_prazo_que_conta_e_o_de_decisao_e_nao_o_do_evento(cenario):
    """A feira de outubro tem inscrição antecipada em junho — avisar em setembro
    é avisar depois que o stand acabou."""
    hoje = timezone.localdate()
    registrar(
        cenario,
        data_inicio=hoje + timedelta(days=200),
        prazo_decisao=hoje + timedelta(days=3),
    )

    assert len(mkt.com_prazo_estourando()) == 1


def test_evento_distante_com_prazo_distante_nao_alerta(cenario):
    hoje = timezone.localdate()
    registrar(cenario, prazo_decisao=hoje + timedelta(days=200))

    assert mkt.com_prazo_estourando() == []


def test_prazo_perdido_e_derivado_e_so_conta_enquanto_aberta(cenario):
    """Uma feira realizada em 2024 tem prazo no passado e não é problema de
    ninguém."""
    oportunidade = registrar(
        cenario, prazo_decisao=timezone.localdate() - timedelta(days=3)
    )
    assert oportunidade.prazo_perdido

    mkt.decidir(oportunidade, cenario["mkt"], SituacaoOportunidade.REALIZADA)

    assert not oportunidade.prazo_perdido


def test_oportunidade_sem_prazo_nao_entra_no_alerta(cenario):
    registrar(cenario, prazo_decisao=None)

    assert mkt.com_prazo_estourando() == []
    assert Oportunidade.objects.abertas().count() == 1


def test_o_perdido_vem_antes_do_que_ainda_da_tempo(cenario):
    hoje = timezone.localdate()
    registrar(cenario, titulo="Ainda dá", prazo_decisao=hoje + timedelta(days=5))
    registrar(cenario, titulo="Perdida", prazo_decisao=hoje - timedelta(days=2))

    assert mkt.com_prazo_estourando()[0].titulo == "Perdida"


def test_a_lista_abre_pelo_prazo_mais_proximo_e_sem_prazo_por_ultimo(cenario):
    """Em SQLite o nulo ordena ANTES — sem `nulls_last`, a lista abriria com o
    que não tem prazo nenhum."""
    hoje = timezone.localdate()
    registrar(cenario, titulo="Sem prazo", prazo_decisao=None)
    registrar(cenario, titulo="Urgente", prazo_decisao=hoje + timedelta(days=1))

    assert [o.titulo for o in mkt.radar()] == ["Urgente", "Sem prazo"]


# ── Decidir ─────────────────────────────────────────────────────────


def test_descartar_exige_motivo(cenario):
    """É o campo mais útil da tabela: sem ele a mesma feira volta todo ano e a
    discussão recomeça do zero."""
    oportunidade = registrar(cenario)

    with pytest.raises(MarketingError, match="por que foi descartada"):
        mkt.decidir(
            oportunidade, cenario["mkt"], SituacaoOportunidade.DESCARTADA
        )


def test_descartar_com_motivo_guarda_a_resposta(cenario):
    oportunidade = registrar(cenario)

    mkt.decidir(
        oportunidade, cenario["mkt"], SituacaoOportunidade.DESCARTADA,
        motivo="Público não é o nosso.",
    )

    assert oportunidade.motivo == "Público não é o nosso."
    assert not oportunidade.aberta


def test_aprovar_nao_exige_motivo(cenario):
    """Aprovar não precisa de justificativa aqui porque a justificativa é o
    pedido do catálogo — que exige "o que a empresa ganha com isso"."""
    oportunidade = registrar(cenario)

    mkt.decidir(oportunidade, cenario["mkt"], SituacaoOportunidade.APROVADA)

    assert oportunidade.situacao == SituacaoOportunidade.APROVADA


def test_o_radar_nao_aprova_gasto_nenhum(cenario):
    """A decisão inteira do módulo: aprovar aqui só MARCA. Nenhuma aprovação de
    valor é criada, nenhum orçamento é comprometido."""
    from workspace.models.aprovacao import SolicitacaoAprovacao
    from workspace.models.orcamento import Compromisso

    oportunidade = registrar(cenario, custo_estimado=Decimal("40000"))
    mkt.decidir(oportunidade, cenario["mkt"], SituacaoOportunidade.APROVADA)

    assert not SolicitacaoAprovacao.objects.exists()
    assert not Compromisso.objects.exists()


def test_o_elo_com_o_pedido_do_catalogo(cenario):
    """Quando a empresa decide ir, abre-se o item `evento` — e a oportunidade
    guarda o elo em vez de duplicar o fluxo."""
    from workspace.models.catalogo import (
        GrupoCatalogo,
        ItemCatalogo,
        SolicitacaoServico,
    )

    item = ItemCatalogo.objects.create(
        chave="evento", nome="Evento", grupo=GrupoCatalogo.DINHEIRO,
        dominio="mkt.evento",
    )
    pedido = SolicitacaoServico.objects.create(item=item, solicitante=cenario["mkt"])
    oportunidade = registrar(cenario)

    mkt.decidir(
        oportunidade, cenario["mkt"], SituacaoOportunidade.APROVADA,
        solicitacao=pedido,
    )

    assert oportunidade.solicitacao == pedido


def test_quem_nao_opera_nao_decide(cenario):
    oportunidade = registrar(cenario)

    with pytest.raises(MarketingError, match="não pode decidir"):
        mkt.decidir(oportunidade, cenario["leitor"], SituacaoOportunidade.APROVADA)


def test_situacao_invalida_recusa(cenario):
    oportunidade = registrar(cenario)

    with pytest.raises(MarketingError, match="Situação"):
        mkt.decidir(oportunidade, cenario["mkt"], "talvez")


def test_decidida_sai_do_radar(cenario):
    oportunidade = registrar(cenario)
    mkt.decidir(oportunidade, cenario["mkt"], SituacaoOportunidade.REALIZADA)

    assert not mkt.radar().exists()
    assert mkt.radar(SituacaoOportunidade.REALIZADA).count() == 1


# ── O período ───────────────────────────────────────────────────────


def test_periodo_de_um_dia_so(cenario):
    dia = date(2027, 5, 12)
    assert registrar(cenario, data_inicio=dia, data_fim=dia).periodo == "12/05/2027"


def test_periodo_dentro_do_mesmo_mes(cenario):
    oportunidade = registrar(
        cenario, data_inicio=date(2027, 5, 12), data_fim=date(2027, 5, 15)
    )

    assert oportunidade.periodo == "12 a 15/05/2027"


def test_periodo_entre_meses(cenario):
    oportunidade = registrar(
        cenario, data_inicio=date(2027, 5, 30), data_fim=date(2027, 6, 2)
    )

    assert oportunidade.periodo == "30/05 a 02/06/2027"


def test_sem_data_nao_ha_periodo(cenario):
    assert registrar(cenario).periodo == ""


# ── O aviso ─────────────────────────────────────────────────────────


def test_avisa_quem_opera_marketing(cenario):
    registrar(cenario, prazo_decisao=timezone.localdate() + timedelta(days=3))

    assert mkt.avisar_prazos() == 1

    aviso = Notificacao.objects.de(cenario["mkt"]).get()
    assert aviso.tipo == TipoNotificacao.PRAZO_DE_OPORTUNIDADE
    assert "3 dias" in aviso.titulo


def test_o_responsavel_tambem_e_avisado(cenario):
    """O responsável pode estar de férias — por isso quem opera recebe também."""
    registrar(cenario, responsavel=cenario["ana"])

    mkt.avisar_prazos()

    assert Notificacao.objects.de(cenario["ana"]).exists()
    assert Notificacao.objects.de(cenario["mkt"]).exists()


def test_o_aviso_de_prazo_vencido_diz_que_venceu(cenario):
    registrar(cenario, prazo_decisao=timezone.localdate() - timedelta(days=1))

    mkt.avisar_prazos()

    assert "venceu" in Notificacao.objects.de(cenario["mkt"]).get().titulo


def test_rodar_duas_vezes_nao_duplica(cenario):
    registrar(cenario)

    mkt.avisar_prazos()
    mkt.avisar_prazos()

    assert Notificacao.objects.de(cenario["mkt"]).count() == 1


def test_oportunidade_decidida_nao_avisa(cenario):
    oportunidade = registrar(cenario)
    mkt.decidir(
        oportunidade, cenario["mkt"], SituacaoOportunidade.DESCARTADA, motivo="Não."
    )

    assert mkt.avisar_prazos() == 0


def test_quem_opera_tambem_le(cenario):
    assert mkt.pode_ler(cenario["mkt"])
    assert mkt.pode_ler(cenario["leitor"])
    assert not mkt.pode_ler(cenario["ana"])


def test_o_resumo_conta_aberta_apertada_e_perdida(cenario):
    hoje = timezone.localdate()
    registrar(cenario, titulo="Longe", prazo_decisao=hoje + timedelta(days=200))
    registrar(cenario, titulo="Perto", prazo_decisao=hoje + timedelta(days=2))
    registrar(cenario, titulo="Perdida", prazo_decisao=hoje - timedelta(days=1))

    resumo = mkt.resumo()

    assert resumo == {"abertas": 3, "no_prazo_curto": 2, "perdidas": 1}


# ── O comando ───────────────────────────────────────────────────────


def test_avisar_marketing_sem_aplicar_nao_grava(cenario):
    from io import StringIO

    from django.core.management import call_command

    registrar(cenario)
    call_command("avisar_marketing", stdout=StringIO())

    assert not Notificacao.objects.exists()


def test_avisar_marketing_aplica(cenario):
    from io import StringIO

    from django.core.management import call_command

    registrar(cenario, prazo_decisao=timezone.localdate() - timedelta(days=1))
    saida = StringIO()
    call_command("avisar_marketing", "--aplicar", stdout=saida)

    assert "VENCIDO" in saida.getvalue()
    assert Notificacao.objects.exists()


def test_avisar_marketing_aceita_outra_antecedencia(cenario):
    from io import StringIO

    from django.core.management import call_command

    registrar(cenario, prazo_decisao=timezone.localdate() + timedelta(days=40))
    call_command("avisar_marketing", "--dias", "60", "--aplicar", stdout=StringIO())

    assert Notificacao.objects.exists()


# ── As telas ────────────────────────────────────────────────────────


def test_quem_nao_le_marketing_leva_403(cenario, client):
    client.force_login(cenario["ana"])

    assert client.get(reverse("workspace:marketing")).status_code == 403


def test_quem_so_le_nao_ve_o_formulario(cenario, client):
    client.force_login(cenario["leitor"])

    resposta = client.get(reverse("workspace:marketing"))

    assert resposta.context["opera"] is False
    assert "Registrar oportunidade" not in resposta.content.decode()


def test_cadastrar_pela_tela(cenario, client):
    client.force_login(cenario["mkt"])

    client.post(
        reverse("workspace:oportunidade_nova"),
        {
            "titulo": "Congresso ABES",
            "tipo": TipoOportunidade.CONGRESSO,
            "prazo_decisao": "2027-06-30",
            "custo_estimado": "12.500,00",
            "publico_estimado": "3000",
        },
    )

    oportunidade = Oportunidade.objects.get()
    assert oportunidade.custo_estimado == Decimal("12500.00")
    assert oportunidade.publico_estimado == 3000


def test_custo_mal_digitado_nao_perde_o_cadastro(cenario, client):
    """O custo é ESTIMADO, e perder o cadastro inteiro por causa dele seria
    trocar um campo opcional por uma tela."""
    client.force_login(cenario["mkt"])

    client.post(
        reverse("workspace:oportunidade_nova"),
        {"titulo": "Feira X", "tipo": TipoOportunidade.FEIRA, "custo_estimado": "caro"},
    )

    assert Oportunidade.objects.get().custo_estimado is None


def test_cadastrar_sem_titulo_nao_grava(cenario, client):
    client.force_login(cenario["mkt"])

    client.post(
        reverse("workspace:oportunidade_nova"),
        {"titulo": "", "tipo": TipoOportunidade.FEIRA},
    )

    assert not Oportunidade.objects.exists()


def test_quem_so_le_nao_cadastra_pela_tela(cenario, client):
    client.force_login(cenario["leitor"])

    client.post(
        reverse("workspace:oportunidade_nova"),
        {"titulo": "Feira X", "tipo": TipoOportunidade.FEIRA},
    )

    assert not Oportunidade.objects.exists()


def test_editar_pela_tela(cenario, client):
    oportunidade = registrar(cenario)
    client.force_login(cenario["mkt"])

    client.post(
        reverse("workspace:oportunidade_editar", args=[oportunidade.pk]),
        {"titulo": "Feira renomeada", "tipo": TipoOportunidade.FEIRA},
    )
    oportunidade.refresh_from_db()

    assert oportunidade.titulo == "Feira renomeada"
    assert Oportunidade.objects.count() == 1


def test_decidir_pela_tela(cenario, client):
    oportunidade = registrar(cenario)
    client.force_login(cenario["mkt"])

    client.post(
        reverse("workspace:oportunidade_decidir", args=[oportunidade.pk]),
        {"situacao": SituacaoOportunidade.DESCARTADA, "motivo": "Custo alto."},
    )
    oportunidade.refresh_from_db()

    assert oportunidade.situacao == SituacaoOportunidade.DESCARTADA


def test_descartar_sem_motivo_pela_tela_nao_muda_nada(cenario, client):
    oportunidade = registrar(cenario)
    client.force_login(cenario["mkt"])

    client.post(
        reverse("workspace:oportunidade_decidir", args=[oportunidade.pk]),
        {"situacao": SituacaoOportunidade.DESCARTADA},
    )
    oportunidade.refresh_from_db()

    assert oportunidade.situacao == SituacaoOportunidade.RADAR


def test_o_filtro_de_situacao_ignora_valor_forjado(cenario, client):
    registrar(cenario)
    client.force_login(cenario["mkt"])

    resposta = client.get(reverse("workspace:marketing"), {"situacao": "'; drop"})

    assert resposta.context["situacao_atual"] == ""
    assert len(resposta.context["oportunidades"]) == 1


def test_get_nas_acoes_volta_para_a_tela(cenario, client):
    oportunidade = registrar(cenario)
    client.force_login(cenario["mkt"])
    destino = reverse("workspace:marketing")

    assert client.get(reverse("workspace:oportunidade_nova"))["Location"] == destino
    assert (
        client.get(
            reverse("workspace:oportunidade_decidir", args=[oportunidade.pk])
        )["Location"]
        == destino
    )


def test_o_trilho_so_oferece_marketing_a_quem_cuida(cenario, client):
    client.force_login(cenario["ana"])
    assert reverse("workspace:marketing") not in client.get(
        reverse("workspace:meu_dia")
    ).content.decode()

    client.force_login(cenario["mkt"])
    assert reverse("workspace:marketing") in client.get(
        reverse("workspace:meu_dia")
    ).content.decode()


def test_o_prazo_apertado_vira_card_urgente_na_home(cenario, client):
    registrar(cenario, prazo_decisao=timezone.localdate() + timedelta(days=2))
    client.force_login(cenario["mkt"])

    cards = client.get(reverse("workspace:home")).context["cards"]
    card = next(c for c in cards if c.chave == "marketing")

    assert card.urgente
    assert card.contagem == 1
