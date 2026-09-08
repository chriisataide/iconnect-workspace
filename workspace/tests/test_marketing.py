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


# ── Os editais públicos no radar ────────────────────────────────────
#
# Eles vêm do espelho, e NÃO viram `Oportunidade`. A razão é a que decidiu o
# desenho inteiro: uma `Oportunidade` é registro NOSSO — alguém cadastrou,
# alguém decidiu, e o motivo do descarte fica guardado. Um edital é registro do
# GOVERNO. Numa tabela só, a carga da madrugada seguinte sobrescreveria o texto
# escrito à mão, que é a única coisa que o radar guarda de verdade.


@pytest.fixture
def edital(db):
    from datetime import timedelta

    from django.utils import timezone
    from resultados.models import EditalPublico

    return EditalPublico.objects.create(
        fonte="pncp",
        chave_externa="00509968000148-1-004225/2025",
        numero_controle="00509968000148-1-004225/2025",
        objeto="Contratação de serviços de vigilância armada",
        orgao="Ministério da Fazenda",
        uf="BA",
        municipio="Salvador",
        valor_estimado=Decimal("5871050.16"),
        encerramento_proposta=timezone.now() + timedelta(days=15),
        termo_casado="vigilancia",
        link="https://pncp.gov.br/app/editais/00509968000148/2025/4225",
    )


def test_o_radar_mostra_o_edital_espelhado(client, cenario, edital):
    client.force_login(cenario["mkt"])

    corpo = client.get(reverse("workspace:marketing")).content.decode()

    assert "Editais públicos com proposta aberta" in corpo
    assert "vigilância armada" in corpo
    assert "Salvador" in corpo


def test_o_edital_mostra_QUAL_termo_o_trouxe(client, cenario, edital):
    """A triagem por palavra é nossa e vai errar nas primeiras semanas. Sem este
    campo na tela, "por que este edital de merenda entrou?" não tem resposta e a
    lista de termos nunca melhora."""
    client.force_login(cenario["mkt"])

    corpo = client.get(reverse("workspace:marketing")).content.decode()

    assert "vigilancia" in corpo
    assert edital.chave_externa in corpo, "procedência na tela"


def test_edital_encerrado_nao_aparece(client, cenario, db):
    """A pergunta da tela é "o que ainda dá para disputar". Um edital vencido é
    ruído — mas a LINHA fica no espelho: apagá-la faria a mesma disputa voltar
    do zero no ano seguinte."""
    from datetime import timedelta

    from django.utils import timezone
    from resultados.models import EditalPublico

    EditalPublico.objects.create(
        fonte="pncp", chave_externa="x-1/2024", numero_controle="x-1/2024",
        objeto="Vigilância que já encerrou", uf="BA",
        encerramento_proposta=timezone.now() - timedelta(days=2),
        termo_casado="vigilancia",
    )
    client.force_login(cenario["mkt"])

    corpo = client.get(reverse("workspace:marketing")).content.decode()

    assert "que já encerrou" not in corpo
    assert EditalPublico.objects.count() == 1, "a linha fica no espelho"


def test_sem_provedor_a_tela_diz_o_que_falta_e_nao_quebra(client, cenario):
    """O radar tem vida própria sem o PNCP. Derrubar a tela porque uma fonte
    externa não respondeu seria trocar uma faixa vazia por uma tela de erro."""
    from workspace.providers import resultados as contrato

    guardados = dict(contrato._provedores)
    contrato.limpar()
    try:
        client.force_login(cenario["mkt"])
        resposta = client.get(reverse("workspace:marketing"))

        assert resposta.status_code == 200
        assert "Nenhum edital no espelho" in resposta.content.decode()
    finally:
        contrato.limpar()
        contrato._provedores.update(guardados)


# ── O filtro do bloco de editais ────────────────────────────────────
#
# Ele nasceu de um número: a primeira carga real do PNCP trouxe 526 editais
# abertos, e o bloco cortava em 40 SEM dizer. Quem lia os quarenta concluía que
# tinha visto tudo — o pior modo de uma tela errar, porque ela não parece
# errada.


@pytest.fixture
def tres_editais(db):
    """Três estados, três termos — o mínimo para um filtro provar alguma coisa."""
    from datetime import timedelta

    from django.utils import timezone
    from resultados.models import EditalPublico

    base = timezone.now()
    dados = (
        ("BA", "Salvador", "vigilancia", "Vigilância armada para o campus", 1),
        ("SP", "Santos", "cftv", "Aquisição de câmeras CFTV para o porto", 2),
        ("SP", "Campinas", "portaria", "Limpeza, conservação e portaria", 3),
    )
    for i, (uf, cidade, termo, objeto, dias) in enumerate(dados):
        EditalPublico.objects.create(
            fonte="pncp",
            chave_externa=f"1111111100011{i}-1-00000{i}/2026",
            numero_controle=f"1111111100011{i}-1-00000{i}/2026",
            objeto=objeto,
            orgao=f"Prefeitura de {cidade}",
            uf=uf,
            municipio=cidade,
            encerramento_proposta=base + timedelta(days=dias),
            termo_casado=termo,
        )


def test_filtra_por_uf(client, cenario, tres_editais):
    client.force_login(cenario["mkt"])

    radar = client.get(reverse("workspace:marketing"), {"uf": "SP"}).context["editais"]

    assert radar.total == 2
    assert {e.uf for e in radar.editais} == {"SP"}


def test_filtra_pelo_termo_que_casou(client, cenario, tres_editais):
    """É o filtro que a poda usa: "portaria" trouxe 154 dos 526 na primeira
    carga, e um deles era um contrato de limpeza e copeiragem."""
    client.force_login(cenario["mkt"])

    radar = client.get(
        reverse("workspace:marketing"), {"termo": "portaria"}
    ).context["editais"]

    assert radar.total == 1
    assert "Limpeza" in radar.editais[0].objeto


def test_a_busca_varre_objeto_E_orgao(client, cenario, tres_editais):
    """Duas perguntas, uma caixa. Separadas, digitar o órgão no campo do objeto
    devolve vazio e a pessoa conclui que não há nada."""
    client.force_login(cenario["mkt"])
    pedir = lambda q: client.get(  # noqa: E731
        reverse("workspace:marketing"), {"busca": q}
    ).context["editais"]

    assert pedir("câmeras").total == 1, "casou pelo objeto"
    assert pedir("Santos").total == 1, "casou pelo órgão"
    assert pedir("prefeitura").total == 3, "os três órgãos são prefeituras"
    assert pedir("cameras").total == 1, "sem acento acha com acento"
    assert pedir("VIGILÂNCIA").total == 1, "e sem depender da caixa"


def test_os_filtros_se_somam(client, cenario, tres_editais):
    client.force_login(cenario["mkt"])

    radar = client.get(
        reverse("workspace:marketing"), {"uf": "SP", "termo": "cftv"}
    ).context["editais"]

    assert radar.total == 1


def test_as_opcoes_do_filtro_saem_do_espelho_e_nao_das_27_ufs(
    client, cenario, tres_editais
):
    """Oferecer um estado que a carga não trouxe é oferecer um filtro que
    devolve vazio — e a pessoa culpa a tela, não a carga."""
    client.force_login(cenario["mkt"])

    radar = client.get(reverse("workspace:marketing")).context["editais"]

    assert radar.ufs == ["BA", "SP"]
    assert radar.termos == ["cftv", "portaria", "vigilancia"]


def test_escolher_uma_uf_nao_apaga_as_outras_da_caixa(
    client, cenario, tres_editais
):
    """Se as opções saíssem do resultado filtrado, escolher "BA" deixaria só
    "BA" na caixa — e não haveria como voltar sem editar a URL."""
    client.force_login(cenario["mkt"])

    radar = client.get(reverse("workspace:marketing"), {"uf": "BA"}).context["editais"]

    assert radar.ufs == ["BA", "SP"]


def test_o_corte_da_lista_APARECE(client, cenario, db, monkeypatch):
    """Cortar em silêncio é pior que não listar: quem lê os que sobraram conclui
    que viu tudo, e não há nada na tela que o contradiga."""
    from datetime import timedelta

    from django.utils import timezone
    from resultados.models import EditalPublico

    monkeypatch.setattr("workspace.services.marketing.TETO_DA_LISTA", 3)
    base = timezone.now()
    for i in range(5):
        EditalPublico.objects.create(
            fonte="pncp",
            chave_externa=f"2222222200011{i}-1-00000{i}/2026",
            numero_controle=f"2222222200011{i}-1-00000{i}/2026",
            objeto="Vigilância patrimonial",
            orgao="Prefeitura",
            uf="BA",
            municipio="Salvador",
            encerramento_proposta=base + timedelta(days=i + 1),
            termo_casado="vigilancia",
        )

    client.force_login(cenario["mkt"])
    resposta = client.get(reverse("workspace:marketing"))
    radar = resposta.context["editais"]

    assert len(radar.editais) == 3 and radar.total == 5
    assert radar.cortada
    assert "de 5" in resposta.content.decode(), "o total aparece na tela"


def test_filtro_sem_resultado_NAO_manda_conferir_a_fonte(
    client, cenario, tres_editais
):
    """São dois vazios diferentes. "A carga não rodou" pede olhar a tela 99;
    "o filtro não achou" pede afrouxar o filtro. Uma frase só para os dois manda
    a pessoa investigar um servidor porque ela cruzou duas opções."""
    client.force_login(cenario["mkt"])

    corpo = client.get(
        reverse("workspace:marketing"), {"uf": "BA", "termo": "cftv"}
    ).content.decode()

    assert "Nenhum edital com esse recorte" in corpo
    assert "Nenhum edital no espelho" not in corpo
    assert "Fontes de dados" not in corpo


def test_filtrar_edital_nao_apaga_o_recorte_do_radar(client, cenario, tres_editais):
    """Dois filtros na mesma tela. Um que apaga o outro faz a pessoa achar que o
    portal esquece o que ela escolheu."""
    client.force_login(cenario["mkt"])

    corpo = client.get(
        reverse("workspace:marketing"), {"uf": "SP", "situacao": "avaliando"}
    ).content.decode()

    assert 'name="situacao" value="avaliando"' in corpo, "o form leva a situação"
    assert "uf=SP" in corpo, "os chips levam a UF"


# ── O vocabulário da tela ───────────────────────────────────────────


def test_a_tela_nao_chama_duas_coisas_diferentes_de_oportunidade(
    client, cenario, tres_editais, db
):
    """A queixa que originou isto: "não vejo necessidade em marketing ter essa
    opção", sobre o formulário de cadastro.

    O formulário registra feira, congresso, patrocínio e prêmio — nenhum deles é
    lead comercial. Ele É de marketing. O que não era de marketing era a
    PALAVRA: a tela se chamava "Oportunidades de marketing" e o formulário
    "Registrar oportunidade", enquanto o bloco logo abaixo passou a listar
    editais públicos — que são oportunidade comercial de verdade. Duas coisas
    com o mesmo nome na mesma tela, e a de cima lida com o sentido da de baixo.

    Este teste segura o rótulo, e não a função: apagar o formulário levaria
    junto o aviso de prazo, o motivo do descarte e o bloco "Precisa decidir".
    """
    client.force_login(cenario["mkt"])

    corpo = client.get(reverse("workspace:marketing")).content.decode()

    assert "Registrar evento ou patrocínio" in corpo
    assert "Eventos e patrocínios" in corpo
    assert "Registrar oportunidade" not in corpo
    assert "Oportunidades de marketing" not in corpo
    # O bloco dos editais mantém a palavra, e é o único que pode: ali ela está
    # certa.
    assert "Editais públicos com proposta aberta" in corpo
