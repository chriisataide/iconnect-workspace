"""Cada regra encontrando exatamente o que ela promete.

Uma regra que nunca foi vista achando alguma coisa é uma regra que ninguém sabe
se funciona — e no painel ela aparece como "sem ocorrências", que é
indistinguível de "está tudo em ordem".
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.excecoes import ingestao, proprias

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()


# ── Organograma ─────────────────────────────────────────────────────


def test_lotacao_sem_centro_de_custo(db):
    f.lotar(f.pessoa("com", nome="Com CC"), centro_custo_codigo="1042")
    f.lotar(f.pessoa("sem", nome="Sem CC"), centro_custo_codigo="")

    achados = proprias.LotacaoSemCentroDeCusto().avaliar(0)

    assert [o.titulo for o in achados] == ["Sem CC"]


def test_pessoa_sem_papel_vigente(db):
    com = f.pessoa("com", nome="Com Papel")
    f.lotar(com, centro_custo_codigo="1042")
    f.atribuir(com, f.papel("rh", ["rh.admin.global"], escopo="global"), escopo="global")
    f.lotar(f.pessoa("sem", nome="Sem Papel"), centro_custo_codigo="1042")

    achados = proprias.PessoaSemPapelVigente().avaliar(0)

    assert [o.titulo for o in achados] == ["Sem Papel"]


def test_papel_vencido_nao_conta_como_papel(db):
    """Papel vencido é o mesmo que papel nenhum: a fila não abre.

    Se `vigentes()` não filtrasse por data, a pessoa sumiria desta regra e o
    sintoma apareceria do outro lado — um pedido que para de ser atendido.
    """
    pessoa = f.pessoa("vencido", nome="Papel Vencido")
    f.lotar(pessoa, centro_custo_codigo="1042")
    f.atribuir(
        pessoa, f.papel("rh", ["rh.admin.global"], escopo="global"),
        escopo="global", inicio=HOJE - timedelta(days=60), fim=HOJE - timedelta(days=1),
    )

    assert [o.titulo for o in proprias.PessoaSemPapelVigente().avaliar(0)] == [
        "Papel Vencido"
    ]


def test_papel_vencendo_dentro_da_janela(db):
    pessoa = f.pessoa("ana", nome="Ana Souza")
    f.lotar(pessoa)
    f.atribuir(
        pessoa, f.papel("rh", ["rh.admin.global"], escopo="global"),
        escopo="global", fim=HOJE + timedelta(days=10),
    )
    longe = f.pessoa("bruno", nome="Bruno Lima")
    f.lotar(longe)
    f.atribuir(
        longe, f.papel("ti", ["ti.admin.global"], escopo="global"),
        escopo="global", fim=HOJE + timedelta(days=200),
    )

    achados = proprias.PapelVencendo().avaliar(30)

    assert len(achados) == 1
    assert "Ana Souza" in achados[0].titulo


# ── Esteira ─────────────────────────────────────────────────────────


@pytest.fixture
def pedido_atrasado(db):
    from workspace.models import GrupoCatalogo, ItemCatalogo
    from workspace.models.catalogo import SolicitacaoServico
    from workspace.services import catalogo as svc

    item = ItemCatalogo.objects.create(
        chave="cadeira", nome="Cadeira", grupo=GrupoCatalogo.EQUIPAMENTO,
        dominio="com.requisicao", prazo_prometido_dias=3,
        limite_auto_aprovacao=Decimal("0"),
        campos=[{"chave": "o_que", "rotulo": "O quê", "obrigatorio": True}],
    )
    f.atribuir(
        f.lotar(f.pessoa("compras", nome="Time Compras")).user,
        f.papel("compras", ["com.atender.global"], escopo="global"), escopo="global",
    )
    ana = f.pessoa("ana", nome="Ana Souza")
    f.lotar(ana)
    pedido = svc.solicitar(item, ana, {"o_que": "Cadeira"})
    SolicitacaoServico.objects.filter(pk=pedido.pk).update(
        criado_em=timezone.now() - timedelta(days=10)
    )
    return pedido


def test_solicitacao_parada_alem_do_prazo_PROMETIDO(pedido_atrasado):
    """A régua é o prazo que a pessoa VIU ao pedir, e não um número escolhido
    na regra. Cobrar por outro seria mudar a medida depois do jogo."""
    achados = proprias.SolicitacaoParada().avaliar(0)

    assert len(achados) == 1
    assert achados[0].papel, "a área que atende aparece na linha"


def test_pedido_no_prazo_nao_entra(db):
    from workspace.models import GrupoCatalogo, ItemCatalogo
    from workspace.services import catalogo as svc

    item = ItemCatalogo.objects.create(
        chave="cadeira", nome="Cadeira", grupo=GrupoCatalogo.EQUIPAMENTO,
        dominio="com.requisicao", prazo_prometido_dias=30,
        limite_auto_aprovacao=Decimal("0"),
        campos=[{"chave": "o_que", "rotulo": "O quê", "obrigatorio": True}],
    )
    ana = f.pessoa("ana", nome="Ana Souza")
    f.lotar(ana)
    svc.solicitar(item, ana, {"o_que": "Cadeira"})

    assert proprias.SolicitacaoParada().avaliar(0) == []


def test_a_area_que_atende_sai_do_papel_e_nao_de_uma_segunda_lista(db):
    """`permissoes` é JSONField, e o `contains` de JSON não existe no SQLite.

    A primeira versão consultava com `permissoes__contains` e estourava
    `NotSupportedError` em desenvolvimento — funcionando em produção. É a pior
    forma de um defeito existir: ele só aparece para quem está desenvolvendo.
    """
    f.papel("compras", ["com.atender.global"], escopo="global")

    assert proprias._papel_da_area("com.requisicao") == "compras"
    assert proprias._papel_da_area("nada.disso") == ""


def test_aprovacao_pendente_alem_da_janela(db):
    from workspace.models.aprovacao import (
        EtapaAprovacao,
        SituacaoEtapa,
        SolicitacaoAprovacao,
    )

    chefe = f.pessoa("chefe", nome="Chefe Silva")
    f.lotar(chefe)
    aprovacao = SolicitacaoAprovacao.objects.create(
        dominio="fin", titulo="Adiantamento de viagem",
        solicitante=chefe, valor=Decimal("500"),
    )
    SolicitacaoAprovacao.objects.filter(pk=aprovacao.pk).update(
        criado_em=timezone.now() - timedelta(days=9)
    )
    EtapaAprovacao.objects.create(
        solicitacao=aprovacao, ordem=10, aprovador=chefe,
        situacao=SituacaoEtapa.PENDENTE,
    )

    achados = proprias.AprovacaoPendente().avaliar(3)

    assert len(achados) == 1
    assert achados[0].responsavel == "Chefe Silva"
    assert "Adiantamento" in achados[0].titulo


def test_aprovacao_recente_nao_entra(db):
    from workspace.models.aprovacao import (
        EtapaAprovacao,
        SituacaoEtapa,
        SolicitacaoAprovacao,
    )

    chefe = f.pessoa("chefe", nome="Chefe Silva")
    f.lotar(chefe)
    aprovacao = SolicitacaoAprovacao.objects.create(
        dominio="fin", titulo="Recente", solicitante=chefe, valor=Decimal("100"),
    )
    EtapaAprovacao.objects.create(
        solicitacao=aprovacao, ordem=10, aprovador=chefe,
        situacao=SituacaoEtapa.PENDENTE,
    )

    assert proprias.AprovacaoPendente().avaliar(3) == []


# ── Acervo ──────────────────────────────────────────────────────────


def test_leitura_obrigatoria_conta_por_DOCUMENTO_e_nao_por_pessoa(db):
    """A lista de quem não leu uma política é dado sobre gente — vira uma tela
    de vigilância. Aqui a linha é o documento, e o número é quantos faltam."""
    from workspace.models.conteudo import Documento, SituacaoDocumento, TipoDocumento

    dono = f.pessoa("dono", nome="Dono")
    f.lotar(dono)
    f.lotar(f.pessoa("ana", nome="Ana"))
    Documento.objects.create(
        slug="politica", titulo="Política de viagem", tipo=TipoDocumento.POLITICA,
        situacao=SituacaoDocumento.VIGENTE, dono=dono, publico_alvo=["*"],
        leitura_obrigatoria=True,
    )

    achados = proprias.LeituraObrigatoriaNaoConfirmada().avaliar(0)

    assert [o.titulo for o in achados] == ["Política de viagem"]
    assert "não confirmaram" in achados[0].detalhe


def test_normativo_sem_revisao_ha_mais_de_um_ano(db):
    from workspace.models.conteudo import Documento, SituacaoDocumento, TipoDocumento

    dono = f.pessoa("dono", nome="Dono Silva")
    f.lotar(dono)
    velho = Documento.objects.create(
        slug="pop-antigo", titulo="POP antigo", tipo=TipoDocumento.POP,
        situacao=SituacaoDocumento.VIGENTE, dono=dono, publico_alvo=["*"],
    )
    Documento.objects.create(
        slug="pop-novo", titulo="POP novo", tipo=TipoDocumento.POP,
        situacao=SituacaoDocumento.VIGENTE, dono=dono, publico_alvo=["*"],
    )
    Documento.objects.filter(pk=velho.pk).update(
        atualizado_em=timezone.now() - timedelta(days=400)
    )

    achados = proprias.NormativoSemRevisao().avaliar(365)

    assert [o.titulo for o in achados] == ["POP antigo"]
    assert achados[0].responsavel == "Dono Silva", "o dono do documento, e não o R.H."


# ── Reservas ────────────────────────────────────────────────────────


def test_reserva_confirmada_cuja_janela_passou(db):
    from workspace.models.reserva import Recurso, Reserva, SituacaoReserva, TipoRecurso

    ana = f.pessoa("ana", nome="Ana Souza")
    f.lotar(ana)
    sala = Recurso.objects.create(
        codigo="sala-1", nome="Sala 1", tipo=TipoRecurso.SALA, ativo=True
    )
    Reserva.objects.create(
        recurso=sala, solicitante=ana,
        inicio=timezone.now() - timedelta(days=2),
        fim=timezone.now() - timedelta(days=2, hours=-1),
        situacao=SituacaoReserva.CONFIRMADA, motivo="Reunião",
    )
    Reserva.objects.create(
        recurso=sala, solicitante=ana,
        inicio=timezone.now() + timedelta(days=1),
        fim=timezone.now() + timedelta(days=1, hours=1),
        situacao=SituacaoReserva.CONFIRMADA, motivo="Futuro",
    )

    achados = proprias.ReservaSemUso().avaliar(7)

    assert len(achados) == 1
    assert achados[0].responsavel == "Ana Souza"


# ── Orçamento ───────────────────────────────────────────────────────


def test_cc_sem_orcamento_e_nao_avaliada_sem_dominio_financeiro(db, monkeypatch):
    """Lista vazia seria lida como "todos os CCs têm orçamento" — o oposto da
    verdade."""
    from workspace.providers import orcamento as provedor

    monkeypatch.setattr(provedor, "obter", lambda: None)

    assert proprias.CentroDeCustoSemOrcamento().disponivel() is False
    assert proprias.CentroDeCustoComprometido().disponivel() is False


def test_cc_sem_orcamento_encontra_quem_nao_tem_teto(db):
    from decimal import Decimal as D

    from financas.models import CentroCusto

    CentroCusto.objects.create(codigo="1042", nome="Operações", ativo=True)
    CentroCusto.objects.create(
        codigo="2050", nome="Administrativo", ativo=True, orcamento_mensal=D("50000")
    )

    achados = proprias.CentroDeCustoSemOrcamento().avaliar(0)

    assert [o.chave for o in achados] == ["cc:1042"]


# ── Ingestão ────────────────────────────────────────────────────────


def test_fonte_nao_configurada_nao_conta_como_atrasada(db, monkeypatch):
    """Ela não está atrasada — ela nunca foi ligada.

    Num ambiente de desenvolvimento não estar ligada é o normal, e contá-la
    encheria o painel de exceções que ninguém pode resolver.
    """
    from django.core.management import call_command

    from workspace.providers import frescor as contrato

    call_command("semear_fontes", "--aplicar", verbosity=0)
    provedor = contrato.obter()
    assert provedor is not None

    achados = ingestao.FonteAtrasada().avaliar(0)

    assert achados == [], "nenhuma fonte tem credencial neste ambiente"


def test_fonte_configurada_e_atrasada_vira_ocorrencia(db, monkeypatch, tmp_path):
    from django.core.management import call_command

    from cargas.models import ExecucaoCarga, FonteDados, StatusCarga

    call_command("semear_fontes", "--aplicar", verbosity=0)
    csv = FonteDados.objects.get(chave="csv")
    csv.idade_maxima_aceitavel = timedelta(hours=1)
    csv.save()
    velho = timezone.now() - timedelta(hours=5)
    ExecucaoCarga.objects.create(
        fonte=csv, iniciada_em=velho, terminada_em=velho, status=StatusCarga.SUCESSO
    )
    monkeypatch.setattr("django.conf.settings.CARGAS_CSV_DIR", str(tmp_path))

    achados = ingestao.FonteAtrasada().avaliar(0)

    assert [o.chave for o in achados] == ["fonte:csv"]


def test_divergencia_aberta_vira_ocorrencia_com_os_dois_valores(db):
    from django.core.management import call_command

    from cargas.models import Divergencia

    call_command("semear_fontes", "--aplicar", verbosity=0)
    Divergencia.objects.create(
        entidade="contrato", chave_externa="CT-100", campo="valor_mensal",
        fonte_a="sankhya", valor_a="11000", fonte_b="iconnect_platform",
        valor_b="12000",
    )

    achados = ingestao.DivergenciaEntreFontes().avaliar(0)

    assert len(achados) == 1
    assert "11000" in achados[0].detalhe and "12000" in achados[0].detalhe


def test_divergencia_resolvida_sai_da_lista(db):
    from django.core.management import call_command

    from cargas.models import Divergencia

    call_command("semear_fontes", "--aplicar", verbosity=0)
    Divergencia.objects.create(
        entidade="contrato", chave_externa="CT-1", campo="x",
        fonte_a="a", valor_a="1", fonte_b="b", valor_b="2",
        resolvida_em=timezone.now(),
    )

    assert ingestao.DivergenciaEntreFontes().avaliar(0) == []


# ── Os cantos ───────────────────────────────────────────────────────


def test_etapa_por_PAPEL_endereca_o_papel_e_nao_uma_pessoa(db):
    """Etapa de área não tem aprovador nomeado: quem responde é o papel.

    Sem este caminho, a linha viria com o responsável em branco — e uma exceção
    sem dono é exceção que ninguém resolve.
    """
    from workspace.models.aprovacao import (
        EtapaAprovacao,
        SituacaoEtapa,
        SolicitacaoAprovacao,
    )

    financeiro = f.pessoa("fin", nome="Time Financeiro")
    f.lotar(financeiro)
    papel = f.papel("financeiro", ["fin.atender.global"], escopo="global")
    f.atribuir(financeiro, papel, escopo="global")

    quem_pede = f.pessoa("ana", nome="Ana Souza")
    f.lotar(quem_pede)
    aprovacao = SolicitacaoAprovacao.objects.create(
        dominio="fin", titulo="Reembolso", solicitante=quem_pede,
        valor=Decimal("900"),
    )
    SolicitacaoAprovacao.objects.filter(pk=aprovacao.pk).update(
        criado_em=timezone.now() - timedelta(days=8)
    )
    EtapaAprovacao.objects.create(
        solicitacao=aprovacao, ordem=10, papel=papel,
        situacao=SituacaoEtapa.PENDENTE,
    )

    (achado,) = proprias.AprovacaoPendente().avaliar(3)

    assert achado.papel == "financeiro"
    assert achado.responsavel == "Time Financeiro"


def test_documento_com_todos_confirmando_sai_da_regra(db):
    """`faltam == 0` é o caminho que prova que a regra sabe parar de cobrar."""
    from workspace.models.conteudo import (
        ConfirmacaoLeitura,
        Documento,
        SituacaoDocumento,
        TipoDocumento,
    )

    dono = f.pessoa("dono", nome="Dono")
    f.lotar(dono)
    documento = Documento.objects.create(
        slug="politica", titulo="Política", tipo=TipoDocumento.POLITICA,
        situacao=SituacaoDocumento.VIGENTE, dono=dono, publico_alvo=["*"],
        leitura_obrigatoria=True,
    )
    ConfirmacaoLeitura.objects.create(
        documento=documento, pessoa=dono, versao=documento.versao
    )

    assert proprias.LeituraObrigatoriaNaoConfirmada().avaliar(0) == []


def test_cc_acima_do_teto_vira_ocorrencia(db):
    """Noventa e não cem: em cem já estourou, e a exceção existe para aparecer
    ANTES. Uma regra que só acusa o que já aconteceu é um relatório."""
    from decimal import Decimal as D

    from financas.models import CentroCusto, Lancamento
    from workspace.models.orcamento import competencia_de

    centro = CentroCusto.objects.create(
        codigo="1042", nome="Operações", ativo=True, orcamento_mensal=D("10000")
    )
    Lancamento.objects.create(
        centro_custo=centro, competencia=competencia_de(None),
        valor=D("9500"), descricao="gasto do mês",
    )

    achados = proprias.CentroDeCustoComprometido().avaliar(90)

    assert [o.chave for o in achados] == ["cc:1042"]
    assert "%" in achados[0].detalhe


def test_cc_sem_teto_nao_aparece_tambem_na_regra_do_comprometido(db):
    """O mesmo centro de custo em duas linhas do painel por dois motivos que são
    um só é ruído — e ensina a ignorar as duas."""
    from financas.models import CentroCusto

    CentroCusto.objects.create(codigo="1042", nome="Operações", ativo=True)

    assert proprias.CentroDeCustoComprometido().avaliar(90) == []


def test_regra_sem_chave_e_recusada():
    from workspace import excecoes as reg

    class Anonima(reg.RegraBase):
        pass

    with pytest.raises(ValueError, match="chave"):
        reg.registrar(Anonima())


def test_chave_duplicada_e_erro():
    """Duas regras com a mesma chave significa que uma some em silêncio — e a
    que some é sempre a que alguém acabou de escrever."""
    from workspace import excecoes as reg

    class Uma(reg.RegraBase):
        chave = "duplicada-de-teste"

    reg.registrar(Uma())
    try:
        with pytest.raises(ValueError, match="Já existe regra"):
            reg.registrar(Uma())
    finally:
        reg.limpar()
        reg.semear()


def test_semear_de_novo_nao_derruba_a_subida():
    """`ready()` pode rodar mais de uma vez conforme o servidor."""
    from workspace import excecoes as reg

    reg.semear()
    reg.semear()

    # 19 desde a Onda 8, quando a conciliação de centro de custo ganhou
    # avaliador — ela esperava o orçamento anual existir.
    assert len(reg.todas()) == 19


def test_a_base_responde_a_tudo_sem_fazer_nada():
    """Herdar é opcional — o protocolo é o que vale —, mas quem herda não deve
    precisar escrever dois métodos vazios para começar."""
    from workspace import excecoes as reg

    regra = reg.RegraBase()

    assert regra.disponivel() is True
    assert regra.avaliar(0) == []
    assert "RegraBase" in repr(regra)


def test_titulares_de_papel_vazio_e_lista_vazia():
    from workspace import excecoes as reg

    assert reg.titulares("") == []


def test_varios_titulares_aparecem_como_um_e_mais_n(db):
    from workspace import excecoes as reg

    papel = f.papel("rh", ["rh.admin.global"], escopo="global")
    for nome in ("Ana Souza", "Bruno Lima", "Carla Dias"):
        pessoa = f.pessoa(nome.split()[0].lower(), nome=nome)
        f.lotar(pessoa)
        f.atribuir(pessoa, papel, escopo="global")

    assert reg.quem_responde("rh").endswith("e mais 2")
