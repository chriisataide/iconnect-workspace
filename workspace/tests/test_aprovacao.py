"""Motor de aprovação — uma bandeja para férias, reembolso e compra."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.models import (
    RegraAprovacao,
    SituacaoEtapa,
    SituacaoSolicitacao,
    SolicitacaoAprovacao,
    TipoAprovador,
)
from workspace.services import aprovacao as apr
from workspace.services.aprovacao import AprovacaoError, Decisao


# ── Cenário base ────────────────────────────────────────────────────


@pytest.fixture
def equipe():
    """Solicitante → gestor → diretor, com regra de duas faixas."""
    diretor = f.pessoa("diretor")
    gestor = f.pessoa("gestor")
    ana = f.pessoa("ana")
    f.lotar(diretor)
    f.lotar(gestor, gestor=diretor)
    f.lotar(ana, gestor=gestor)

    papel_diretoria = f.papel("diretoria", ["apr.aprovar.global"], escopo="global")
    f.atribuir(diretor, papel_diretoria)

    RegraAprovacao.objects.create(
        dominio="*", valor_minimo=Decimal("0"), tipo=TipoAprovador.GESTOR_DIRETO, ordem=10
    )
    RegraAprovacao.objects.create(
        dominio="*",
        valor_minimo=Decimal("10000"),
        tipo=TipoAprovador.PAPEL,
        papel=papel_diretoria,
        ordem=20,
    )
    return {"ana": ana, "gestor": gestor, "diretor": diretor, "papel": papel_diretoria}


def cria(solicitante, valor=None, dominio="fin.reembolso", **kwargs):
    return apr.criar(
        dominio=dominio, titulo="Pedido", solicitante=solicitante, valor=valor, **kwargs
    )


# ── Cadeia por faixa de valor ───────────────────────────────────────


@pytest.mark.django_db
def test_valor_baixo_so_precisa_do_gestor(equipe):
    s = cria(equipe["ana"], Decimal("840"))
    etapas = list(s.etapas.order_by("ordem"))
    assert len(etapas) == 1
    assert etapas[0].aprovador == equipe["gestor"]


@pytest.mark.django_db
def test_valor_alto_acrescenta_a_diretoria(equipe):
    s = cria(equipe["ana"], Decimal("12400"))
    etapas = list(s.etapas.order_by("ordem"))
    assert len(etapas) == 2
    assert etapas[0].aprovador == equipe["gestor"]
    assert etapas[1].papel == equipe["papel"]
    assert etapas[1].aprovador is None, "etapa por papel não é de ninguém em particular"


@pytest.mark.django_db
def test_sem_valor_usa_so_a_faixa_zero(equipe):
    """Férias não têm valor. Regra de R$ 10.000 não pode casar com elas."""
    s = cria(equipe["ana"], valor=None, dominio="rh.ferias")
    assert s.etapas.count() == 1


@pytest.mark.django_db
def test_regra_especifica_do_dominio_substitui_a_generica(equipe):
    """Configurar "reembolso é diferente" não pode somar as duas cadeias."""
    outro_gestor = f.pessoa("outro_gestor")
    RegraAprovacao.objects.create(
        dominio="fin.reembolso",
        valor_minimo=Decimal("0"),
        tipo=TipoAprovador.NOMINAL,
        aprovador=outro_gestor,
        ordem=10,
    )
    s = cria(equipe["ana"], Decimal("500"), dominio="fin.reembolso")
    etapas = list(s.etapas.order_by("ordem"))
    assert len(etapas) == 1
    assert etapas[0].aprovador == outro_gestor


@pytest.mark.django_db
def test_sem_regra_nenhuma_nao_aprova_sozinho():
    """Auto-aprovar por falta de configuração é como R$ 50 mil passa sem ninguém ver."""
    ana = f.pessoa("ana")
    s = cria(ana, Decimal("50000"))
    assert s.etapas.count() == 0
    assert s.situacao == SituacaoSolicitacao.AGUARDANDO


@pytest.mark.django_db
def test_gestor_nao_cadastrado_gera_etapa_pulada_com_motivo(equipe):
    """O dossiê precisa mostrar que faltou organograma, não omitir a etapa."""
    solto = f.pessoa("solto")  # sem Lotacao
    s = cria(solto, Decimal("500"))
    etapa = s.etapas.get()
    assert etapa.situacao == SituacaoEtapa.PULADA
    assert "organograma" in etapa.motivo_pulo.lower()
    assert s.situacao == SituacaoSolicitacao.AGUARDANDO, "pular não é aprovar"


# ── Regra 1 · Ninguém aprova o próprio pedido ───────────────────────


@pytest.mark.django_db
def test_solicitante_nao_decide_o_proprio_pedido(equipe):
    s = cria(equipe["ana"], Decimal("840"))
    with pytest.raises(AprovacaoError, match="próprio pedido"):
        apr.decidir(s, equipe["ana"], Decisao.APROVAR)


@pytest.mark.django_db
def test_nem_com_permissao_global_aprova_o_proprio(equipe):
    """A regra é absoluta. Permissão global não é escape."""
    diretor = equipe["diretor"]
    s = cria(diretor, Decimal("50000"))
    with pytest.raises(AprovacaoError, match="próprio pedido"):
        apr.decidir(s, diretor, Decisao.APROVAR)


@pytest.mark.django_db
def test_etapa_cujo_aprovador_e_o_solicitante_e_pulada(equipe):
    """Regra nominal apontando para quem pediu: pula e a de cima decide.

    Acontece de verdade quando a empresa nomeia "o coordenador X aprova compras
    de material" e é o próprio X quem precisa do material.
    """
    RegraAprovacao.objects.filter(ordem=10).delete()
    RegraAprovacao.objects.create(
        dominio="*",
        valor_minimo=Decimal("0"),
        tipo=TipoAprovador.NOMINAL,
        aprovador=equipe["ana"],
        ordem=10,
    )

    s = cria(equipe["ana"], Decimal("12400"))
    etapas = list(s.etapas.order_by("ordem"))

    assert etapas[0].situacao == SituacaoEtapa.PULADA
    assert "próprio solicitante" in etapas[0].motivo_pulo
    assert etapas[1].situacao == SituacaoEtapa.PENDENTE
    assert s.etapa_atual == etapas[1], "a cadeia segue para a diretoria"


# ── Decisão ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_aprovacao_de_uma_etapa_conclui(equipe):
    s = cria(equipe["ana"], Decimal("840"))
    s = apr.decidir(s, equipe["gestor"], Decisao.APROVAR)

    assert s.situacao == SituacaoSolicitacao.APROVADA
    assert s.decidido_em is not None


@pytest.mark.django_db
def test_cadeia_de_duas_etapas_precisa_das_duas(equipe):
    s = cria(equipe["ana"], Decimal("12400"))

    s = apr.decidir(s, equipe["gestor"], Decisao.APROVAR)
    assert s.situacao == SituacaoSolicitacao.AGUARDANDO, "ainda falta a diretoria"

    s = apr.decidir(s, equipe["diretor"], Decisao.APROVAR)
    assert s.situacao == SituacaoSolicitacao.APROVADA


@pytest.mark.django_db
def test_devolver_encerra_e_nao_volta_uma_etapa(equipe):
    """Cadeia que anda para trás produz estado que ninguém explica."""
    s = cria(equipe["ana"], Decimal("12400"))
    s = apr.decidir(s, equipe["gestor"], Decisao.DEVOLVER, "sem cotação")

    assert s.situacao == SituacaoSolicitacao.DEVOLVIDA
    assert s.etapas.filter(situacao=SituacaoEtapa.PENDENTE).count() == 1, (
        "a etapa da diretoria fica pendente mas a solicitação está encerrada"
    )


@pytest.mark.django_db
def test_devolver_exige_justificativa(equipe):
    s = cria(equipe["ana"], Decimal("840"))
    with pytest.raises(AprovacaoError, match="exige justificativa"):
        apr.decidir(s, equipe["gestor"], Decisao.DEVOLVER, "   ")


@pytest.mark.django_db
def test_decisao_desconhecida_e_rejeitada(equipe):
    s = cria(equipe["ana"], Decimal("840"))
    with pytest.raises(AprovacaoError, match="Decisão desconhecida"):
        apr.decidir(s, equipe["gestor"], "talvez")


@pytest.mark.django_db
def test_quem_nao_e_da_cadeia_nao_decide(equipe):
    estranho = f.pessoa("estranho")
    s = cria(equipe["ana"], Decimal("840"))
    with pytest.raises(AprovacaoError, match="Sem permissão"):
        apr.decidir(s, estranho, Decisao.APROVAR)


@pytest.mark.django_db
def test_anonimo_nao_decide(equipe):
    from django.contrib.auth.models import AnonymousUser

    s = cria(equipe["ana"], Decimal("840"))
    with pytest.raises(AprovacaoError, match="Sem permissão"):
        apr.decidir(s, AnonymousUser(), Decisao.APROVAR)


@pytest.mark.django_db
def test_etapa_por_papel_e_decidida_por_quem_tem_o_papel(equipe):
    outro_diretor = f.pessoa("outro_diretor")
    f.atribuir(outro_diretor, equipe["papel"])

    s = cria(equipe["ana"], Decimal("12400"))
    apr.decidir(s, equipe["gestor"], Decisao.APROVAR)
    s = apr.decidir(s, outro_diretor, Decisao.APROVAR)

    assert s.situacao == SituacaoSolicitacao.APROVADA


# ── Regra 2 · Idempotência ──────────────────────────────────────────


@pytest.mark.django_db
def test_decidir_duas_vezes_nao_avanca_duas(equipe):
    """Duplo-clique e retry de push chegam duas vezes."""
    s = cria(equipe["ana"], Decimal("840"))
    apr.decidir(s, equipe["gestor"], Decisao.APROVAR)

    with pytest.raises(AprovacaoError, match="já está aprovada"):
        apr.decidir(s, equipe["gestor"], Decisao.APROVAR)


@pytest.mark.django_db
def test_nao_decide_solicitacao_devolvida(equipe):
    s = cria(equipe["ana"], Decimal("840"))
    apr.decidir(s, equipe["gestor"], Decisao.DEVOLVER, "faltou nota")
    with pytest.raises(AprovacaoError, match="já está devolvida"):
        apr.decidir(s, equipe["gestor"], Decisao.APROVAR)


@pytest.mark.django_db
def test_solicitacao_inexistente(equipe):
    s = cria(equipe["ana"], Decimal("840"))
    pk = s.pk
    SolicitacaoAprovacao.objects.filter(pk=pk).delete()
    s.pk = pk
    with pytest.raises(AprovacaoError, match="não encontrada"):
        apr.decidir(s, equipe["gestor"], Decisao.APROVAR)


@pytest.mark.django_db
def test_sem_etapa_pendente_nao_decide():
    ana, gestor = f.pessoa("ana"), f.pessoa("gestor")
    f.lotar(gestor)
    f.lotar(ana, gestor=gestor)
    f.atribuir(gestor, f.papel("g", ["apr.aprovar.global"], escopo="global"))
    s = cria(ana, Decimal("500"))  # nenhuma regra → zero etapa

    with pytest.raises(AprovacaoError, match="Nenhuma etapa pendente"):
        apr.decidir(s, gestor, Decisao.APROVAR)


# ── Regra 3 · Delegação não é caso especial ─────────────────────────


@pytest.mark.django_db
def test_delegado_decide_no_lugar_do_titular(equipe):
    substituto = f.pessoa("substituto")
    hoje = timezone.localdate()
    f.delegar(equipe["gestor"], substituto, hoje, hoje + timedelta(days=7))

    s = cria(equipe["ana"], Decimal("840"))
    s = apr.decidir(s, substituto, Decisao.APROVAR)

    assert s.situacao == SituacaoSolicitacao.APROVADA


@pytest.mark.django_db
def test_auditoria_registra_quem_devia_e_quem_fez(equipe):
    """"Quem devia" e "quem fez" não são a mesma pergunta."""
    substituto = f.pessoa("substituto")
    hoje = timezone.localdate()
    f.delegar(equipe["gestor"], substituto, hoje, hoje + timedelta(days=7))

    s = cria(equipe["ana"], Decimal("840"))
    apr.decidir(s, substituto, Decisao.APROVAR)

    etapa = s.etapas.get()
    assert etapa.aprovador == equipe["gestor"], "quem devia"
    assert etapa.decidido_por == substituto, "quem fez"


@pytest.mark.django_db
def test_delegacao_vencida_nao_permite_decidir(equipe):
    substituto = f.pessoa("substituto")
    hoje = timezone.localdate()
    f.delegar(equipe["gestor"], substituto, hoje - timedelta(days=30), hoje - timedelta(days=1))

    s = cria(equipe["ana"], Decimal("840"))
    with pytest.raises(AprovacaoError, match="Sem permissão"):
        apr.decidir(s, substituto, Decisao.APROVAR)


# ── Cancelamento ────────────────────────────────────────────────────


@pytest.mark.django_db
def test_solicitante_cancela_o_proprio_pedido(equipe):
    s = cria(equipe["ana"], Decimal("840"))
    s = apr.decidir(s, equipe["ana"], Decisao.CANCELAR)

    assert s.situacao == SituacaoSolicitacao.CANCELADA
    assert s.etapas.filter(situacao=SituacaoEtapa.PENDENTE).count() == 0


@pytest.mark.django_db
def test_estranho_nao_cancela(equipe):
    s = cria(equipe["ana"], Decimal("840"))
    with pytest.raises(AprovacaoError, match="Sem permissão para cancelar"):
        apr.decidir(s, f.pessoa("estranho"), Decisao.CANCELAR)


@pytest.mark.django_db
def test_quem_tem_permissao_sobre_o_solicitante_cancela(equipe):
    s = cria(equipe["ana"], Decimal("840"))
    s = apr.decidir(s, equipe["diretor"], Decisao.CANCELAR)
    assert s.situacao == SituacaoSolicitacao.CANCELADA


# ── Lote ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_lote_aprova_todas(equipe):
    solicitacoes = [cria(equipe["ana"], Decimal("100")) for _ in range(3)]
    decididas, falhas = apr.decidir_em_lote(solicitacoes, equipe["gestor"], Decisao.APROVAR)

    assert len(decididas) == 3
    assert falhas == []
    assert all(s.situacao == SituacaoSolicitacao.APROVADA for s in decididas)


@pytest.mark.django_db
def test_lote_nao_aborta_tudo_quando_uma_falha(equipe):
    """Cancelar as 5 boas por causa de 1 é o pior resultado possível."""
    boas = [cria(equipe["ana"], Decimal("100")) for _ in range(2)]
    propria = cria(equipe["gestor"], Decimal("100"))  # o gestor não aprova a dele

    decididas, falhas = apr.decidir_em_lote(
        boas + [propria], equipe["gestor"], Decisao.APROVAR
    )

    assert len(decididas) == 2, "as boas passaram"
    assert len(falhas) == 1
    assert falhas[0][0] == propria.pk
    assert "próprio pedido" in falhas[0][1]


# ── Bandeja ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_bandeja_traz_o_que_espera_por_mim(equipe):
    cria(equipe["ana"], Decimal("100"))
    cria(equipe["ana"], Decimal("200"))

    ids = {s.pk for s in apr.pendentes_para(equipe["gestor"])}
    assert len(ids) == 2


@pytest.mark.django_db
def test_bandeja_nao_traz_a_propria_solicitacao(equipe):
    cria(equipe["gestor"], Decimal("100"))
    assert apr.pendentes_para(equipe["gestor"]).count() == 0


@pytest.mark.django_db
def test_bandeja_inclui_etapa_por_papel(equipe):
    cria(equipe["ana"], Decimal("12400"))
    apr.decidir(SolicitacaoAprovacao.objects.get(), equipe["gestor"], Decisao.APROVAR)

    assert apr.pendentes_para(equipe["diretor"]).count() == 1


@pytest.mark.django_db
def test_bandeja_inclui_delegacao_recebida(equipe):
    substituto = f.pessoa("substituto")
    hoje = timezone.localdate()
    f.delegar(equipe["gestor"], substituto, hoje, hoje + timedelta(days=7))
    cria(equipe["ana"], Decimal("100"))

    assert apr.pendentes_para(substituto).count() == 1


@pytest.mark.django_db
def test_bandeja_ordena_mais_antiga_primeiro(equipe):
    """Quem está esperando mais é quem precisa aparecer no topo."""
    nova = cria(equipe["ana"], Decimal("100"))
    antiga = cria(equipe["ana"], Decimal("200"))
    SolicitacaoAprovacao.objects.filter(pk=antiga.pk).update(
        criado_em=timezone.now() - timedelta(days=5)
    )

    ordem = [s.pk for s in apr.pendentes_para(equipe["gestor"])]
    assert ordem == [antiga.pk, nova.pk]


@pytest.mark.django_db
def test_bandeja_de_anonimo_e_vazia():
    from django.contrib.auth.models import AnonymousUser

    assert apr.pendentes_para(AnonymousUser()).count() == 0
    assert apr.pendentes_para(None).count() == 0


@pytest.mark.django_db
def test_bandeja_sem_papel_nem_delegacao(equipe):
    """Quem só tem etapas nominais não deve gerar filtro por papel vazio."""
    sem_papel = f.pessoa("sem_papel")
    assert apr.pendentes_para(sem_papel).count() == 0


@pytest.mark.django_db
def test_resumo_da_bandeja(equipe):
    cria(equipe["ana"], Decimal("840"))
    antiga = cria(equipe["ana"], Decimal("1000"))
    SolicitacaoAprovacao.objects.filter(pk=antiga.pk).update(
        criado_em=timezone.now() - timedelta(days=3)
    )

    resumo = apr.resumo_da_bandeja(equipe["gestor"])
    assert resumo["quantidade"] == 2
    assert resumo["valor_represado"] == Decimal("1840")
    assert resumo["dias_mais_antiga"] == 3


@pytest.mark.django_db
def test_resumo_vazio(equipe):
    resumo = apr.resumo_da_bandeja(equipe["gestor"])
    assert resumo == {
        "quantidade": 0,
        "valor_represado": Decimal("0"),
        "dias_mais_antiga": 0,
        "solicitacoes": [],
    }


@pytest.mark.django_db
def test_resumo_ignora_solicitacao_sem_valor(equipe):
    """Férias não somam ao valor represado, mas contam na quantidade."""
    cria(equipe["ana"], valor=None, dominio="rh.ferias")
    resumo = apr.resumo_da_bandeja(equipe["gestor"])
    assert resumo["quantidade"] == 1
    assert resumo["valor_represado"] == Decimal("0")


# ── Sinal para o domínio ────────────────────────────────────────────


@pytest.mark.django_db
def test_sinal_avisa_o_dominio_ao_aprovar(equipe):
    """APR não conhece o efeito. O domínio ouve e aplica."""
    recebidos = []

    def ouvinte(sender, solicitacao, decisao, quem, **kwargs):
        recebidos.append((solicitacao.pk, decisao, quem))

    apr.aprovacao_decidida.connect(ouvinte)
    try:
        s = cria(equipe["ana"], Decimal("840"))
        apr.decidir(s, equipe["gestor"], Decisao.APROVAR)
    finally:
        apr.aprovacao_decidida.disconnect(ouvinte)

    assert len(recebidos) == 1
    assert recebidos[0][1] == Decisao.APROVAR
    assert recebidos[0][2] == equipe["gestor"]


@pytest.mark.django_db
def test_sinal_avisa_ao_devolver_e_ao_cancelar(equipe):
    decisoes = []

    def ouvinte(sender, solicitacao, decisao, quem, **kwargs):
        decisoes.append(decisao)

    apr.aprovacao_decidida.connect(ouvinte)
    try:
        apr.decidir(cria(equipe["ana"], Decimal("100")), equipe["gestor"],
                    Decisao.DEVOLVER, "motivo")
        apr.decidir(cria(equipe["ana"], Decimal("100")), equipe["ana"], Decisao.CANCELAR)
    finally:
        apr.aprovacao_decidida.disconnect(ouvinte)

    assert decisoes == [Decisao.DEVOLVER, Decisao.CANCELAR]


# ── Histórico e dossiê ──────────────────────────────────────────────


@pytest.mark.django_db
def test_historico_em_ordem_para_a_timeline(equipe):
    s = cria(equipe["ana"], Decimal("12400"))
    apr.decidir(s, equipe["gestor"], Decisao.APROVAR, "ok pra mim")

    etapas = list(apr.historico(s))
    assert [e.ordem for e in etapas] == [1, 2]
    assert etapas[0].justificativa == "ok pra mim"


@pytest.mark.django_db
def test_dados_carregam_o_dossie_do_dominio(equipe):
    """APR não conhece o schema; só transporta."""
    s = cria(
        equipe["ana"], Decimal("840"),
        dados={"notas": 3, "politica_ok": True, "cc_consumido_pct": 68},
    )
    s.refresh_from_db()
    assert s.dados["notas"] == 3
    assert s.dados["cc_consumido_pct"] == 68


@pytest.mark.django_db
def test_dias_esperando(equipe):
    s = cria(equipe["ana"], Decimal("100"))
    SolicitacaoAprovacao.objects.filter(pk=s.pk).update(
        criado_em=timezone.now() - timedelta(days=4)
    )
    s.refresh_from_db()
    assert s.dias_esperando == 4


@pytest.mark.django_db
def test_dias_esperando_congela_na_decisao(equipe):
    s = cria(equipe["ana"], Decimal("100"))
    s = apr.decidir(s, equipe["gestor"], Decisao.APROVAR)
    assert s.dias_esperando == 0, "conta até a decisão, não até agora"


@pytest.mark.django_db
def test_str_dos_modelos(equipe):
    s = cria(equipe["ana"], Decimal("840"))
    assert "fin.reembolso" in str(s)
    assert str(s.etapas.get()).startswith(str(s.pk))
    assert "≥" in str(RegraAprovacao.objects.first())


# ── Validação de regra ──────────────────────────────────────────────


@pytest.mark.django_db
def test_regra_por_papel_exige_papel():
    from django.core.exceptions import ValidationError

    r = RegraAprovacao(dominio="*", tipo=TipoAprovador.PAPEL)
    with pytest.raises(ValidationError, match="exige o papel"):
        r.clean()


@pytest.mark.django_db
def test_regra_nominal_exige_aprovador():
    from django.core.exceptions import ValidationError

    r = RegraAprovacao(dominio="*", tipo=TipoAprovador.NOMINAL)
    with pytest.raises(ValidationError, match="exige o aprovador"):
        r.clean()


@pytest.mark.django_db
def test_regra_recusa_valor_negativo():
    from django.core.exceptions import ValidationError

    r = RegraAprovacao(dominio="*", tipo=TipoAprovador.GESTOR_DIRETO, valor_minimo=Decimal("-1"))
    with pytest.raises(ValidationError, match="negativo"):
        r.clean()


@pytest.mark.django_db
def test_regra_gestor_direto_nao_exige_nada_mais():
    RegraAprovacao(dominio="*", tipo=TipoAprovador.GESTOR_DIRETO).clean()


@pytest.mark.django_db
def test_etapa_exige_aprovador_ou_papel(equipe):
    from django.core.exceptions import ValidationError

    from workspace.models import EtapaAprovacao

    s = cria(equipe["ana"], Decimal("100"))
    with pytest.raises(ValidationError, match="aprovador nominal ou de papel"):
        EtapaAprovacao(solicitacao=s, ordem=99).clean()


# ── Escopo mais amplo decide etapa de outro ─────────────────────────


@pytest.mark.django_db
def test_quem_tem_escopo_maior_decide_etapa_de_subordinado(equipe):
    """O diretor tem `apr.aprovar.global` e pode decidir a etapa do gestor.

    É o caminho de destravamento: gestor sumiu, sem delegação registrada, e a
    solicitação não pode ficar presa. Fica auditado em `decidido_por`.
    """
    s = cria(equipe["ana"], Decimal("840"))
    etapa = s.etapas.get()
    assert etapa.aprovador == equipe["gestor"]

    s = apr.decidir(s, equipe["diretor"], Decisao.APROVAR, "gestor de licença")

    assert s.situacao == SituacaoSolicitacao.APROVADA
    etapa.refresh_from_db()
    assert etapa.aprovador == equipe["gestor"], "quem devia"
    assert etapa.decidido_por == equipe["diretor"], "quem fez"


@pytest.mark.django_db
def test_guarda_contra_concluir_duas_vezes(equipe):
    """`_concluir` é chamado de dois pontos; o guarda impede disparar o sinal
    do domínio duas vezes para a mesma aprovação."""
    s = cria(equipe["ana"], Decimal("840"))
    s = apr.decidir(s, equipe["gestor"], Decisao.APROVAR)
    assert s.situacao == SituacaoSolicitacao.APROVADA

    assert apr._concluir_se_nao_ha_pendencia(s, equipe["gestor"]) is False


@pytest.mark.django_db
def test_queryset_filtra_por_dominio(equipe):
    cria(equipe["ana"], Decimal("100"), dominio="fin.reembolso")
    cria(equipe["ana"], valor=None, dominio="rh.ferias")

    assert SolicitacaoAprovacao.objects.do_dominio("rh.ferias").count() == 1
    assert SolicitacaoAprovacao.objects.do_dominio("fin.reembolso").count() == 1


@pytest.mark.django_db
def test_gerente_nao_decide_etapa_de_diretoria(equipe):
    """O furo que a busca por cobertura encontrou.

    A etapa por papel `diretoria` existe justamente para impor a faixa de valor.
    Um gerente com `apr.aprovar.equipe` NÃO pode decidi-la — se pudesse, a
    cadeia por faixa de valor seria decorativa.
    """
    gerente = f.pessoa("gerente_qualquer")
    f.atribuir(gerente, f.papel("gerente_p", ["apr.aprovar.equipe"], escopo="equipe"))

    s = cria(equipe["ana"], Decimal("12400"))
    apr.decidir(s, equipe["gestor"], Decisao.APROVAR)

    etapa = s.etapas.order_by("ordem").last()
    assert etapa.papel == equipe["papel"], "a etapa pendente é a de diretoria"

    with pytest.raises(AprovacaoError, match="Sem permissão"):
        apr.decidir(s, gerente, Decisao.APROVAR)


@pytest.mark.django_db
def test_papel_errado_nao_decide_etapa_de_outro_papel(equipe):
    """Ter algum papel não basta — tem de ser o papel da etapa."""
    outro = f.pessoa("outro")
    f.atribuir(outro, f.papel("fiscal", ["apr.aprovar.global"], escopo="global"))

    s = cria(equipe["ana"], Decimal("12400"))
    apr.decidir(s, equipe["gestor"], Decisao.APROVAR)

    with pytest.raises(AprovacaoError, match="Sem permissão"):
        apr.decidir(s, outro, Decisao.APROVAR)
