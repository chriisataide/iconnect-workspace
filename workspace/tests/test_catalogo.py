"""Catálogo de serviços — uma fila de pedido, não cinco."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.catalogo_inicial import CATALOGO_INICIAL
from workspace.models import (
    Compromisso,
    GrupoCatalogo,
    ItemCatalogo,
    RegraAprovacao,
    SituacaoServico,
    SolicitacaoServico,
    TipoAprovador,
)
from workspace.providers import orcamento as provedor
from workspace.providers.orcamento import OrcamentoProvider
from workspace.services import aprovacao as apr
from workspace.services import catalogo as svc
from workspace.services.catalogo import SolicitacaoError


def item(**kwargs) -> ItemCatalogo:
    dados = {
        "chave": "teste",
        "nome": "Item de teste",
        "grupo": GrupoCatalogo.EQUIPAMENTO,
        "dominio": "ti.chamado",
    }
    return ItemCatalogo.objects.create(**{**dados, **kwargs})


@pytest.fixture
def equipe():
    diretor, gestor, ana = (f.pessoa(n) for n in ("diretor", "gestor", "ana"))
    f.lotar(diretor)
    f.lotar(gestor, gestor=diretor)
    f.lotar(ana, gestor=gestor, centro_custo_codigo="1042")
    RegraAprovacao.objects.create(dominio="*", tipo=TipoAprovador.GESTOR_DIRETO, ordem=10)
    return {"ana": ana, "gestor": gestor, "diretor": diretor}


# ── O catálogo semente ──────────────────────────────────────────────


@pytest.mark.django_db
def test_semear_cria_todos_os_itens():
    saida = StringIO()
    call_command("semear_catalogo", "--aplicar", stdout=saida)
    assert ItemCatalogo.objects.count() == len(CATALOGO_INICIAL)


@pytest.mark.django_db
def test_semear_e_reexecutavel():
    call_command("semear_catalogo", "--aplicar", stdout=StringIO())
    antes = ItemCatalogo.objects.count()
    saida = StringIO()
    call_command("semear_catalogo", "--aplicar", stdout=saida)
    assert ItemCatalogo.objects.count() == antes
    assert f"já existiam  {antes}" in saida.getvalue()


@pytest.mark.django_db
def test_simulacao_nao_grava():
    saida = StringIO()
    call_command("semear_catalogo", stdout=saida)
    assert "SIMULAÇÃO" in saida.getvalue()
    assert ItemCatalogo.objects.count() == 0


@pytest.mark.django_db
def test_item_invalido_e_relatado_e_nao_gravado(monkeypatch):
    """`full_clean` antes de gravar: item com 5 campos obrigatórios entraria e
    só seria descoberto quando alguém tentasse usar."""
    ruim = {
        "chave": "ruim",
        "nome": "Ruim",
        "grupo": GrupoCatalogo.EQUIPAMENTO,
        "dominio": "x",
        "campos": [
            {"chave": f"c{i}", "rotulo": f"C{i}", "obrigatorio": True} for i in range(5)
        ],
    }
    monkeypatch.setattr("workspace.management.commands.semear_catalogo.CATALOGO_INICIAL", [ruim])

    saida = StringIO()
    call_command("semear_catalogo", "--aplicar", stdout=saida)
    assert "INVÁLIDOS" in saida.getvalue()
    assert ItemCatalogo.objects.count() == 0


def test_nenhum_item_semente_tem_mais_de_tres_campos_obrigatorios():
    """A regra de produto: formulário com muitos campos livres faz o usuário
    desistir e mandar e-mail."""
    for spec in CATALOGO_INICIAL:
        obrigatorios = [c for c in spec.get("campos", []) if c.get("obrigatorio")]
        assert len(obrigatorios) <= 3, f"{spec['chave']}: {len(obrigatorios)} obrigatórios"


def test_nenhum_grupo_tem_nome_de_departamento():
    """O usuário navega por problema, não por departamento."""
    rotulos = " ".join(g.label.lower() for g in GrupoCatalogo)
    for proibido in ("rh", "ti", "financeiro", "compras", "logística", "jurídico "):
        assert proibido not in rotulos.split(), f"{proibido!r} é departamento, não intenção"


def test_todo_item_semente_declara_dominio():
    """Sem domínio o pedido não sabe para onde ir."""
    for spec in CATALOGO_INICIAL:
        assert spec.get("dominio"), spec["chave"]


def test_epi_e_reciclagem_nao_passam_por_aprovacao():
    """Negar EPI é risco, não economia. E negar reciclagem de NR trava a
    operação, porque habilitação vencida bloqueia despacho."""
    por_chave = {s["chave"]: s for s in CATALOGO_INICIAL}
    for chave in ("epi", "reciclagem-nr"):
        assert por_chave[chave]["limite_auto_aprovacao"] == Decimal("0")


# ── Validação do item ───────────────────────────────────────────────


@pytest.mark.django_db
def test_campos_deve_ser_lista():
    with pytest.raises(ValidationError, match="lista"):
        ItemCatalogo(chave="x", nome="X", grupo=GrupoCatalogo.DINHEIRO,
                     dominio="d", campos={"nao": "lista"}).clean()


@pytest.mark.django_db
def test_campo_sem_chave_e_rejeitado():
    with pytest.raises(ValidationError, match="precisa de `chave`"):
        ItemCatalogo(chave="x", nome="X", grupo=GrupoCatalogo.DINHEIRO,
                     dominio="d", campos=[{"rotulo": "Sem chave"}]).clean()


@pytest.mark.django_db
def test_campo_que_nao_e_dicionario_e_rejeitado():
    with pytest.raises(ValidationError, match="Campo inválido"):
        ItemCatalogo(chave="x", nome="X", grupo=GrupoCatalogo.DINHEIRO,
                     dominio="d", campos=["texto solto"]).clean()


@pytest.mark.django_db
def test_chave_de_campo_repetida_e_rejeitada():
    with pytest.raises(ValidationError, match="repetida"):
        ItemCatalogo(
            chave="x", nome="X", grupo=GrupoCatalogo.DINHEIRO, dominio="d",
            campos=[{"chave": "a"}, {"chave": "a"}],
        ).clean()


@pytest.mark.django_db
def test_tipo_de_campo_desconhecido_e_rejeitado():
    with pytest.raises(ValidationError, match="Tipo desconhecido"):
        ItemCatalogo(
            chave="x", nome="X", grupo=GrupoCatalogo.DINHEIRO, dominio="d",
            campos=[{"chave": "a", "tipo": "planilha"}],
        ).clean()


@pytest.mark.django_db
def test_mais_de_tres_campos_obrigatorios_e_rejeitado():
    with pytest.raises(ValidationError, match="O máximo é 3"):
        ItemCatalogo(
            chave="x", nome="X", grupo=GrupoCatalogo.DINHEIRO, dominio="d",
            campos=[{"chave": f"c{i}", "obrigatorio": True} for i in range(4)],
        ).clean()


@pytest.mark.django_db
def test_quatro_campos_sendo_tres_obrigatorios_passa():
    ItemCatalogo(
        chave="x", nome="X", grupo=GrupoCatalogo.DINHEIRO, dominio="d",
        campos=[
            {"chave": "a", "obrigatorio": True},
            {"chave": "b", "obrigatorio": True},
            {"chave": "c", "obrigatorio": True},
            {"chave": "d", "obrigatorio": False},
        ],
    ).clean()


@pytest.mark.django_db
def test_limite_negativo_e_rejeitado():
    with pytest.raises(ValidationError, match="negativo"):
        ItemCatalogo(chave="x", nome="X", grupo=GrupoCatalogo.DINHEIRO, dominio="d",
                     limite_auto_aprovacao=Decimal("-1")).clean()


@pytest.mark.django_db
def test_str_do_item():
    assert str(item(nome="Notebook")) == "Notebook"


# ── Catálogo por pessoa ─────────────────────────────────────────────


@pytest.mark.django_db
def test_anonimo_nao_ve_catalogo():
    """Pedir exige saber quem pede — o catálogo é área pessoal."""
    from django.contrib.auth.models import AnonymousUser

    item()
    assert svc.catalogo_para(AnonymousUser()) == []
    assert svc.catalogo_para(None) == []


@pytest.mark.django_db
def test_item_sem_permissao_e_visivel_a_todos(equipe):
    item()
    assert len(svc.catalogo_para(equipe["ana"])) == 1


@pytest.mark.django_db
def test_item_com_permissao_e_filtrado(equipe):
    """Item que aparece e recusa no envio é pior que item que não aparece."""
    item(chave="restrito", permissao="fin.admin")
    assert svc.catalogo_para(equipe["ana"]) == []

    f.atribuir(equipe["ana"], f.papel("adm", ["fin.admin.global"], escopo="global"))
    assert len(svc.catalogo_para(equipe["ana"])) == 1


@pytest.mark.django_db
def test_item_inativo_nao_aparece(equipe):
    item(ativo=False)
    assert svc.catalogo_para(equipe["ana"]) == []


@pytest.mark.django_db
def test_agrupado_por_intencao(equipe):
    item(chave="a", grupo=GrupoCatalogo.DINHEIRO)
    item(chave="b", grupo=GrupoCatalogo.DINHEIRO)
    item(chave="c", grupo=GrupoCatalogo.VIAGEM)

    grupos = svc.agrupado_para(equipe["ana"])
    assert set(grupos) == {"Dinheiro", "Viagem"}
    assert len(grupos["Dinheiro"]) == 2


# ── Prazo real medido ───────────────────────────────────────────────


@pytest.mark.django_db
def test_prazo_cai_no_prometido_sem_historico(equipe):
    it = item(prazo_prometido_dias=12)
    dias, medido = svc.prazo_medido(it)
    assert (dias, medido) == (12, False)


@pytest.mark.django_db
def test_prazo_ainda_prometido_com_poucas_conclusoes(equipe):
    """Duas conclusões rápidas fariam a tela prometer 1 dia para sempre."""
    it = item(prazo_prometido_dias=12)
    for _ in range(4):
        _concluir_em(it, equipe["ana"], dias=2)

    dias, medido = svc.prazo_medido(it)
    assert (dias, medido) == (12, False)


@pytest.mark.django_db
def test_prazo_vira_medido_com_historico_bastante(equipe):
    """Prazo prometido que ninguém cumpre destrói a confiança mais rápido que
    prazo longo e honesto."""
    it = item(prazo_prometido_dias=2)
    for dias in (8, 9, 10, 11, 12):
        _concluir_em(it, equipe["ana"], dias=dias)

    dias, medido = svc.prazo_medido(it)
    assert medido is True
    assert dias == 10, "mediana, não média — a cauda não distorce"


def _concluir_em(it, pessoa, dias: int):
    agora = timezone.now()
    s = SolicitacaoServico.objects.create(item=it, solicitante=pessoa)
    SolicitacaoServico.objects.filter(pk=s.pk).update(
        criado_em=agora - timedelta(days=dias),
        concluido_em=agora,
        situacao=SituacaoServico.CONCLUIDA,
    )
    return s


# ── Verificação antes do envio ──────────────────────────────────────


@pytest.mark.django_db
def test_campo_obrigatorio_faltando_bloqueia(equipe):
    it = item(campos=[{"chave": "motivo", "rotulo": "Motivo", "obrigatorio": True}])
    impedimentos = svc.verificar(it, equipe["ana"], dados={})
    assert [i.campo for i in impedimentos] == ["motivo"]
    assert "Motivo é obrigatório" in impedimentos[0].motivo


@pytest.mark.django_db
def test_campo_obrigatorio_em_branco_tambem_bloqueia(equipe):
    it = item(campos=[{"chave": "motivo", "rotulo": "Motivo", "obrigatorio": True}])
    assert svc.verificar(it, equipe["ana"], dados={"motivo": "   "})


@pytest.mark.django_db
def test_campo_opcional_nao_bloqueia(equipe):
    it = item(campos=[{"chave": "obs", "rotulo": "Obs", "obrigatorio": False}])
    assert svc.verificar(it, equipe["ana"], dados={}) == []


@pytest.mark.django_db
def test_valor_exigido_e_ausente_bloqueia(equipe):
    it = item(exige_valor=True)
    assert any(i.campo == "valor" for i in svc.verificar(it, equipe["ana"]))


@pytest.mark.django_db
def test_item_inativo_bloqueia(equipe):
    it = item(ativo=False)
    assert any(i.campo == "item" for i in svc.verificar(it, equipe["ana"]))


@pytest.mark.django_db
def test_sem_permissao_bloqueia(equipe):
    it = item(permissao="fin.admin")
    assert any("acesso" in i.motivo for i in svc.verificar(it, equipe["ana"]))


@pytest.mark.django_db
def test_sem_centro_de_custo_na_lotacao_bloqueia_e_diz_o_que_fazer(equipe):
    sem_cc = f.pessoa("sem_cc")
    f.lotar(sem_cc)
    it = item(exige_centro_custo=True)

    impedimentos = svc.verificar(it, sem_cc)
    assert any("RH" in i.motivo for i in impedimentos), "diz o próximo passo"


# ── Pedir ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_solicitar_cria_e_vai_para_aprovacao(equipe):
    it = item(dominio="fin.reembolso")
    s = svc.solicitar(it, equipe["ana"])

    assert s.situacao == SituacaoServico.AGUARDANDO_APROVACAO
    assert s.aprovacao is not None
    assert s.aprovacao.solicitante == equipe["ana"]
    assert s.aprovacao.dominio == "fin.reembolso"


@pytest.mark.django_db
def test_solicitar_recusa_pedido_invalido(equipe):
    it = item(campos=[{"chave": "motivo", "rotulo": "Motivo", "obrigatorio": True}])
    with pytest.raises(SolicitacaoError, match="Motivo é obrigatório"):
        svc.solicitar(it, equipe["ana"], dados={})


@pytest.mark.django_db
def test_centro_de_custo_vem_da_identidade(equipe):
    """O usuário não digita centro de custo."""
    it = item(exige_centro_custo=True, exige_valor=True)
    s = svc.solicitar(it, equipe["ana"], valor=Decimal("500"))
    assert s.centro_custo_codigo == "1042"


@pytest.mark.django_db
def test_dados_do_formulario_chegam_ao_dossie(equipe):
    it = item(campos=[{"chave": "motivo", "rotulo": "Motivo", "obrigatorio": True}])
    s = svc.solicitar(it, equipe["ana"], dados={"motivo": "notebook quebrou"})

    assert s.aprovacao.dados["campos"]["motivo"] == "notebook quebrou"
    assert s.aprovacao.dados["item"] == it.chave


# ── Auto-aprovação dentro da política ───────────────────────────────


class ProviderFolgado(OrcamentoProvider):
    key = "folgado"

    def orcamento_mensal(self, centro_custo_codigo):
        return Decimal("100000")

    def realizado_no_mes(self, centro_custo_codigo, competencia):
        return Decimal("0")


class ProviderApertado(OrcamentoProvider):
    key = "apertado"

    def orcamento_mensal(self, centro_custo_codigo):
        return Decimal("100")

    def realizado_no_mes(self, centro_custo_codigo, competencia):
        return Decimal("100")


@pytest.fixture
def provider_temporario():
    anterior = provedor.obter()
    yield lambda p: provedor.registrar(p)
    provedor.limpar()
    if anterior is not None:
        provedor.registrar(anterior)


@pytest.mark.django_db
def test_dentro_do_limite_nao_vai_para_fila_humana(equipe, provider_temporario):
    """A maioria dos portais manda 100% para aprovação manual, e é por isso que
    parecem lentos."""
    provider_temporario(ProviderFolgado())
    it = item(exige_valor=True, exige_centro_custo=True,
              limite_auto_aprovacao=Decimal("200"))

    s = svc.solicitar(it, equipe["ana"], valor=Decimal("150"))

    assert s.auto_aprovada is True
    assert s.situacao == SituacaoServico.APROVADA
    assert s.aprovacao is None


@pytest.mark.django_db
def test_acima_do_limite_vai_para_a_cadeia(equipe, provider_temporario):
    provider_temporario(ProviderFolgado())
    it = item(exige_valor=True, exige_centro_custo=True,
              limite_auto_aprovacao=Decimal("200"))

    s = svc.solicitar(it, equipe["ana"], valor=Decimal("250"))
    assert s.auto_aprovada is False
    assert s.aprovacao is not None


@pytest.mark.django_db
def test_dentro_do_limite_mas_sem_orcamento_vai_para_a_cadeia(equipe, provider_temporario):
    """Dentro do limite E dentro do orçamento. Só o limite não basta."""
    provider_temporario(ProviderApertado())
    it = item(exige_valor=True, exige_centro_custo=True,
              limite_auto_aprovacao=Decimal("200"))

    s = svc.solicitar(it, equipe["ana"], valor=Decimal("150"))
    assert s.auto_aprovada is False


@pytest.mark.django_db
def test_item_sem_limite_sempre_exige_aprovacao(equipe):
    it = item(limite_auto_aprovacao=None)
    assert svc.solicitar(it, equipe["ana"]).auto_aprovada is False


@pytest.mark.django_db
def test_item_de_limite_zero_e_sem_valor_auto_aprova(equipe):
    """EPI, atestado, declaração: não há o que aprovar."""
    it = item(limite_auto_aprovacao=Decimal("0"))
    s = svc.solicitar(it, equipe["ana"])
    assert s.auto_aprovada is True


@pytest.mark.django_db
def test_auto_aprovada_escritura_compromisso(equipe, provider_temporario):
    """Automático não pode significar invisível: o orçamento é reservado igual."""
    provider_temporario(ProviderFolgado())
    it = item(exige_valor=True, exige_centro_custo=True,
              limite_auto_aprovacao=Decimal("500"))

    svc.solicitar(it, equipe["ana"], valor=Decimal("400"))

    comp = Compromisso.objects.get()
    assert comp.valor == Decimal("400")
    assert comp.centro_custo_codigo == "1042"


# ── Reação à decisão ────────────────────────────────────────────────


@pytest.mark.django_db
def test_aprovar_reflete_no_pedido_de_servico(equipe):
    it = item(dominio="fin.reembolso")
    s = svc.solicitar(it, equipe["ana"])

    apr.decidir(s.aprovacao, equipe["gestor"], apr.Decisao.APROVAR)

    s.refresh_from_db()
    assert s.situacao == SituacaoServico.APROVADA


@pytest.mark.django_db
def test_devolver_traz_o_motivo_para_o_solicitante(equipe):
    """Devolução sem motivo obriga a adivinhar, e adivinhar gera um segundo
    envio igualmente errado."""
    it = item()
    s = svc.solicitar(it, equipe["ana"])

    apr.decidir(s.aprovacao, equipe["gestor"], apr.Decisao.DEVOLVER, "faltou a nota fiscal")

    s.refresh_from_db()
    assert s.situacao == SituacaoServico.DEVOLVIDA
    assert s.motivo_devolucao == "faltou a nota fiscal"


@pytest.mark.django_db
def test_aprovacao_sem_servico_associado_nao_quebra(equipe):
    """Aprovação criada direto por um domínio, sem passar pelo catálogo."""
    a = apr.criar(dominio="x", titulo="direto", solicitante=equipe["ana"], valor=None)
    apr.decidir(a, equipe["gestor"], apr.Decisao.APROVAR)  # não levanta
    assert SolicitacaoServico.objects.count() == 0


# ── Minhas solicitações e cancelamento ──────────────────────────────


@pytest.mark.django_db
def test_minhas_traz_so_as_minhas(equipe):
    it = item()
    svc.solicitar(it, equipe["ana"])
    svc.solicitar(it, equipe["gestor"])

    assert svc.minhas(equipe["ana"]).count() == 1


@pytest.mark.django_db
def test_minhas_de_anonimo_e_vazio():
    from django.contrib.auth.models import AnonymousUser

    assert svc.minhas(AnonymousUser()).count() == 0
    assert svc.minhas(None).count() == 0


@pytest.mark.django_db
def test_cancelar_o_proprio_pedido(equipe):
    it = item()
    s = svc.solicitar(it, equipe["ana"])
    s = svc.cancelar(s, equipe["ana"])

    assert s.situacao == SituacaoServico.CANCELADA
    s.aprovacao.refresh_from_db()
    assert s.aprovacao.situacao == "cancelada"


@pytest.mark.django_db
def test_outro_nao_cancela_meu_pedido(equipe):
    it = item()
    s = svc.solicitar(it, equipe["ana"])
    with pytest.raises(SolicitacaoError, match="Só quem pediu"):
        svc.cancelar(s, equipe["gestor"])


@pytest.mark.django_db
def test_nao_cancela_o_que_ja_foi_concluido(equipe):
    it = item()
    s = svc.solicitar(it, equipe["ana"])
    s.concluir()
    with pytest.raises(SolicitacaoError, match="já está concluída"):
        svc.cancelar(s, equipe["ana"])


@pytest.mark.django_db
def test_cancelar_libera_o_orcamento(equipe, provider_temporario):
    provider_temporario(ProviderFolgado())
    it = item(exige_valor=True, exige_centro_custo=True, dominio="com.requisicao")
    s = svc.solicitar(it, equipe["ana"], valor=Decimal("5000"))
    apr.decidir(s.aprovacao, equipe["gestor"], apr.Decisao.APROVAR)

    from workspace.services import orcamento as orc

    assert orc.resumo("1042").comprometido == Decimal("5000")

    svc.cancelar(s, equipe["ana"])
    assert orc.resumo("1042").comprometido == Decimal("0")


@pytest.mark.django_db
def test_cancelar_pedido_auto_aprovado(equipe, provider_temporario):
    """Auto-aprovado não tem aprovação para cancelar — o caminho tem de existir."""
    provider_temporario(ProviderFolgado())
    it = item(limite_auto_aprovacao=Decimal("0"))
    s = svc.solicitar(it, equipe["ana"])

    s = svc.cancelar(s, equipe["ana"])
    assert s.situacao == SituacaoServico.CANCELADA


# ── Propriedades do modelo ──────────────────────────────────────────


@pytest.mark.django_db
def test_dias_para_concluir_e_none_enquanto_aberta(equipe):
    it = item()
    s = svc.solicitar(it, equipe["ana"])
    assert s.dias_para_concluir is None
    assert s.em_aberto is True


@pytest.mark.django_db
def test_concluir_registra_a_data(equipe):
    it = item()
    s = svc.solicitar(it, equipe["ana"])
    s.concluir()

    assert s.situacao == SituacaoServico.CONCLUIDA
    assert s.concluido_em is not None
    assert s.em_aberto is False


@pytest.mark.django_db
def test_queryset_abertas_e_concluidas(equipe):
    it = item()
    aberta = svc.solicitar(it, equipe["ana"])
    concluida = svc.solicitar(it, equipe["ana"])
    concluida.concluir()

    assert list(SolicitacaoServico.objects.abertas()) == [aberta]
    assert list(SolicitacaoServico.objects.concluidas()) == [concluida]


@pytest.mark.django_db
def test_str_da_solicitacao(equipe):
    it = item(nome="Reembolso")
    s = svc.solicitar(it, equipe["ana"])
    assert str(s) == "Reembolso · ana"


@pytest.mark.django_db
def test_campos_obrigatorios_do_item():
    it = item(campos=[
        {"chave": "a", "obrigatorio": True},
        {"chave": "b", "obrigatorio": False},
    ])
    assert it.campos_obrigatorios == ["a"]


# ── Ponta a ponta ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_do_catalogo_ate_a_conclusao(equipe, provider_temporario):
    """O fluxo completo: navegar → pedir → aprovar → concluir → prazo medido."""
    provider_temporario(ProviderFolgado())
    call_command("semear_catalogo", "--aplicar", stdout=StringIO())

    grupos = svc.agrupado_para(equipe["ana"])
    assert "Dinheiro" in grupos

    reembolso = ItemCatalogo.objects.get(chave="reembolso")
    # Arquivo de verdade, não o nome dele: o campo `comprovantes` é do tipo
    # `arquivo`, e desde os anexos reais um texto não satisfaz mais a
    # obrigatoriedade. Era esse o ponto.
    s = svc.solicitar(
        reembolso, equipe["ana"],
        valor=Decimal("840"),
        arquivos={"comprovantes": [
            SimpleUploadedFile("cupom.jpg", b"\xff\xd8\xff\xe0" + b"0" * 32,
                               content_type="image/jpeg")
        ]},
    )
    assert s.anexos.get().nome_original == "cupom.jpg"

    assert s.situacao == SituacaoServico.AGUARDANDO_APROVACAO, "840 > limite de 200"
    assert s.aprovacao.etapa_atual.aprovador == equipe["gestor"]

    apr.decidir(s.aprovacao, equipe["gestor"], apr.Decisao.APROVAR)
    s.refresh_from_db()
    assert s.situacao == SituacaoServico.APROVADA
    assert Compromisso.objects.get().valor == Decimal("840")

    s.concluir()
    assert s.dias_para_concluir == 0


@pytest.mark.django_db
def test_item_com_valor_mas_sem_centro_de_custo_auto_aprova(equipe):
    """Existe item com valor que não é rateado a centro de custo — sem CC não
    há orçamento a consultar, então só o limite decide."""
    it = item(
        exige_valor=True, exige_centro_custo=False,
        limite_auto_aprovacao=Decimal("500"),
    )
    s = svc.solicitar(it, equipe["ana"], valor=Decimal("300"))

    assert s.auto_aprovada is True
    assert s.centro_custo_codigo == ""
    assert Compromisso.objects.count() == 0, "sem CC, nada a comprometer"


@pytest.mark.django_db
def test_grupos_seguem_a_ordem_de_frequencia_nao_a_alfabetica(equipe):
    """Alfabética põe "Desenvolvimento" primeiro e "Equipamento e acesso" em
    quarto — quando equipamento é o que a maioria vem pedir."""
    item(chave="a", grupo=GrupoCatalogo.JURIDICO)
    item(chave="b", grupo=GrupoCatalogo.EQUIPAMENTO)
    item(chave="c", grupo=GrupoCatalogo.DINHEIRO)
    item(chave="d", grupo=GrupoCatalogo.DESENVOLVIMENTO)

    rotulos = list(svc.agrupado_para(equipe["ana"]))
    assert rotulos == [
        "Equipamento e acesso", "Dinheiro", "Desenvolvimento", "Jurídico",
    ]


@pytest.mark.django_db
def test_grupo_sem_item_nao_aparece(equipe):
    item(chave="so_um", grupo=GrupoCatalogo.VIAGEM)
    assert list(svc.agrupado_para(equipe["ana"])) == ["Viagem"]
