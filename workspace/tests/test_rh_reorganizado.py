"""§10 — o R.H. reorganizado, e a separação que ele obrigou.

## O achado que mudou o desenho

`dominio` decidia DUAS coisas ao mesmo tempo: em que módulo o item aparece, e de
quem é a fila que executa. As duas coincidem quase sempre — e quando não
coincidem, mover o item de lugar muda quem faz o trabalho.

Prestação de contas é exatamente esse caso. O colaborador procura reembolso no
R.H.; quem PAGA é o Financeiro. Atender "mover Reembolso para o R.H." trocando o
domínio poria o R.H. na fila de pagar despesa — que não é o que ninguém pediu.

Um campo `modulos_extras` chegou a existir para separar as duas perguntas — o
item apareceria no R.H. sem mudar de dono. A decisão de negócio dispensou-o: o
R.H. **faz a tratativa mesmo**, confere o comprovante e libera o pagamento. O
campo foi removido; esquema morto é pior que esquema nenhum.

## Pagamento de PJ e a privacidade

O §10 pede "evitar exposição de informações de terceiros". Não foi preciso
inventar nada, e é bom que os testes digam por quê: o produto já mostra a cada
pessoa só os pedidos dela, e anexo só é servido depois de autorizar. Um "módulo
de PJ" com listagem própria é justamente o que criaria o vazamento temido.

## As remoções

`declaracao`, `ferias`, `atestado` — e `home-office`, que saiu antes. Todas com
a mesma regra: some da tela, o dado fica.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.catalogo_inicial import CATALOGO_INICIAL
from workspace.models.catalogo import ItemCatalogo, SolicitacaoServico
from workspace.modulos import modulo_por_chave
from workspace.services import catalogo as svc

pytestmark = pytest.mark.django_db

SAIRAM = ["declaracao", "ferias", "atestado", "home-office"]


@pytest.fixture
def semeado():
    from io import StringIO

    from django.core.management import call_command

    call_command("semear_catalogo", "--aplicar", stdout=StringIO())


# ── O R.H. trata reembolso e PJ ─────────────────────────────────────


def test_reembolso_e_pj_sao_do_rh(semeado):
    """Não é troca de rótulo: `dominio` decide de quem é a FILA que executa.

    A pergunta "mover para o R.H. muda quem paga?" foi feita e respondida — o
    R.H. faz a tratativa mesmo: confere o comprovante e libera o pagamento.
    Este teste é o que registra a decisão em código.
    """
    from workspace.services import atendimento as atd

    for chave in ("prestacao-contas", "pagamento-pj"):
        item = ItemCatalogo.objects.get(chave=chave)
        assert item.dominio.startswith("rh."), chave
        assert atd.permissao_de(item.dominio) == "rh.atender", chave


def test_o_adiantamento_continua_no_financeiro(semeado):
    """Dinheiro que sai ANTES da despesa é do Financeiro. A prestação de contas
    de um adiantamento cruza os dois domínios de propósito — o R.H. confere os
    recibos, o Financeiro adiantou o valor."""
    from workspace.services import atendimento as atd

    item = ItemCatalogo.objects.get(chave="adiantamento")
    assert atd.permissao_de(item.dominio) == "fin.atender"


def test_a_cadeia_do_reembolso_e_gestor_depois_rh(semeado):
    """Sai de graça das regras que já existem: `*` ordem 10 é o gestor direto,
    `rh.` ordem 15 é a área. Nenhuma regra nova foi criada."""
    from decimal import Decimal

    from identidade.models import Lotacao
    from workspace.models.aprovacao import RegraAprovacao, TipoAprovador
    from workspace.services import aprovacao as apr

    papel_rh = f.papel("rh", ["rh.atender.global"], escopo="global")
    RegraAprovacao.objects.create(dominio="*", tipo=TipoAprovador.GESTOR_DIRETO, ordem=10)
    RegraAprovacao.objects.create(
        dominio="rh.", tipo=TipoAprovador.PAPEL, papel=papel_rh, ordem=15
    )

    gestor, ana = f.pessoa("gestor"), f.pessoa("ana")
    f.lotar(gestor, centro_custo_codigo="1000")
    f.lotar(ana, gestor=gestor, centro_custo_codigo="1000")
    rh = f.pessoa("rh")
    f.lotar(rh)
    f.atribuir(rh, papel_rh)

    item = ItemCatalogo.objects.get(chave="prestacao-contas")
    Lotacao.objects.filter(user=ana).update(centro_custo_codigo="1000")
    aprovacao = apr.criar(
        dominio=item.dominio, titulo=item.nome, solicitante=ana,
        valor=Decimal("500"), centro_custo_codigo="1000",
    )

    degraus = [
        (e.ordem, e.papel.chave if e.papel_id else "gestor")
        for e in aprovacao.etapas.order_by("ordem")
    ]
    # As etapas são renumeradas 1, 2, … — `RegraAprovacao.ordem` só define a
    # SEQUÊNCIA, não o número que a etapa carrega.
    assert degraus[:2] == [(1, "gestor"), (2, "rh")]


def test_o_financeiro_nao_ve_mais_reembolso_na_vitrine(semeado):
    chaves = [i.chave for i in svc.do_modulo(("fin.",))]

    assert "prestacao-contas" not in chaves
    assert "pagamento-pj" not in chaves
    assert "adiantamento" in chaves


def test_a_pagina_do_modulo_rh_mostra_os_dois(client, semeado):
    corpo = client.get(reverse("workspace:modulo", args=["rh"])).content.decode()

    assert "Prestação de contas" in corpo
    assert "Pagamento de PJ" in corpo


def test_o_campo_modulos_extras_nao_existe_mais():
    """Ele viveu uma tarde: nasceu para permitir "aparecer no R.H. sem mudar de
    dono", e a decisão de negócio foi que o R.H. muda de dono mesmo.

    Esquema morto é pior que esquema nenhum — ele está lá quando alguém
    finalmente precisar, e estará errado, porque foi desenhado para um caso que
    não aconteceu.
    """
    assert not hasattr(ItemCatalogo, "modulos_extras")


# ── Pagamento de PJ ─────────────────────────────────────────────────


def test_o_item_de_pj_existe_e_exige_a_nota(semeado):
    spec = next(s for s in CATALOGO_INICIAL if s["chave"] == "pagamento-pj")
    campos = {c["chave"]: c for c in spec["campos"]}

    assert campos["nota_fiscal"]["tipo"] == "arquivo"
    assert campos["nota_fiscal"]["obrigatorio"] is True
    assert campos["competencia"]["obrigatorio"] is True
    assert spec["exige_valor"] is True


def test_a_competencia_e_o_mes_do_servico(semeado):
    """A distinção mais confundida do pagamento de PJ, e a que faz o Financeiro
    lançar no mês errado quando ninguém diz."""
    spec = next(s for s in CATALOGO_INICIAL if s["chave"] == "pagamento-pj")
    competencia = next(c for c in spec["campos"] if c["chave"] == "competencia")

    assert "mês de referência do serviço" in competencia["ajuda"]


def test_pj_nao_ve_o_pedido_de_outro_pj(semeado):
    """A exigência de privacidade do §10, verificada em vez de afirmada."""
    item = ItemCatalogo.objects.get(chave="pagamento-pj")
    ana, bruno = f.pessoa("ana"), f.pessoa("bruno")
    f.lotar(ana, centro_custo_codigo="1000")
    f.lotar(bruno, centro_custo_codigo="1000")

    dela = svc.solicitar(
        item, ana, {"competencia": "08", "nota_fiscal": "x"},
        Decimal("5000"), arquivos={"nota_fiscal": _arquivo()},
    )

    assert dela in svc.minhas(ana)
    assert dela not in svc.minhas(bruno)


def test_a_nota_de_um_pj_nao_e_baixavel_por_outro(client, semeado):
    """Anexo é servido por view que autoriza — nunca por URL de mídia pública.
    Sem isso, a nota fiscal de um prestador estaria a um id de distância."""
    item = ItemCatalogo.objects.get(chave="pagamento-pj")
    ana, bruno = f.pessoa("ana"), f.pessoa("bruno")
    f.lotar(ana, centro_custo_codigo="1000")
    f.lotar(bruno, centro_custo_codigo="1000")
    pedido = svc.solicitar(
        item, ana, {"competencia": "08"}, Decimal("5000"),
        arquivos={"nota_fiscal": _arquivo()},
    )
    anexo = pedido.anexos.get()

    client.force_login(bruno)
    resposta = client.get(reverse("workspace:baixar_anexo", args=[anexo.pk]))

    assert resposta.status_code in (403, 404), "a nota de outro PJ foi entregue"


def _arquivo():
    from django.core.files.uploadedfile import SimpleUploadedFile

    return [SimpleUploadedFile("nf.pdf", b"%PDF-1.4 conteudo", content_type="application/pdf")]


# ── As remoções ─────────────────────────────────────────────────────


@pytest.mark.parametrize("chave", SAIRAM)
def test_item_removido_saiu_da_semente(chave):
    assert not any(s["chave"] == chave for s in CATALOGO_INICIAL)


def test_a_migracao_desativa_sem_apagar_o_historico():
    """`SolicitacaoServico.item` é `PROTECT`: se alguém trocar o `update` por um
    `delete`, este teste explode com `ProtectedError` em vez de deixar o
    histórico sumir em produção."""
    from importlib import import_module

    from django.apps import apps as registro

    from workspace.models.catalogo import GrupoCatalogo

    ana = f.pessoa("ana")
    f.lotar(ana)
    for chave in ("declaracao", "ferias", "atestado"):
        item = ItemCatalogo.objects.create(
            chave=chave, nome=chave, grupo=GrupoCatalogo.TRABALHO,
            dominio="rh.ausencia", prazo_prometido_dias=2,
            limite_auto_aprovacao=Decimal("0"), campos=[],
        )
        SolicitacaoServico.objects.create(item=item, solicitante=ana, dados={})

    import_module("workspace.migrations.0034_rh_reorganizado").aplicar(registro, None)

    for chave in ("declaracao", "ferias", "atestado"):
        item = ItemCatalogo.objects.get(chave=chave)
        assert item.ativo is False, chave
    assert SolicitacaoServico.objects.count() == 3, "histórico perdido"


def test_o_que_o_rh_mantem_continua(semeado):
    """O §10 lista o que FICA, e a lista importa tanto quanto a das remoções."""
    chaves = [i.chave for i in svc.do_modulo(("rh.",))]

    assert "abertura-vaga" in chaves
    assert "vaga-interna" in chaves


def test_o_assistente_nao_ficou_apontando_para_item_removido(semeado):
    """Apagar a FAQ junto com o item seria o erro fácil: quem pergunta "como
    peço férias" receberia silêncio e concluiria que o assistente não sabe nada
    — quando o que mudou foi o caminho."""
    from io import StringIO

    from django.core.management import call_command

    from workspace.services import assistente as asst

    call_command("semear_faq", "--aplicar", stdout=StringIO())
    resposta = asst.responder("como peço férias")

    assert resposta.faq is not None, "a pergunta ficou sem resposta"
    assert "/servicos/ferias/" not in (resposta.acoes[0]["url"] if resposta.acoes else "")


# ── §11 — o chamado que abre no iConnect ────────────────────────────


def test_o_card_de_chamado_leva_para_fora(semeado):
    """O §11 é explícito: o Workspace NÃO recria o sistema de chamados. Ordem de
    serviço, despacho de técnico e SLA de campo já existem lá, com histórico e
    com o cliente."""
    item = ItemCatalogo.objects.get(chave="chamado-predial-iconnect")

    assert item.leva_para_fora
    assert item.url_externa
    assert not item.campos, "item que sai daqui não tem formulário aqui"


def test_o_endereco_vem_das_settings(semeado):
    """Literal escrito à mão mandaria todo mundo para o iConnect de
    desenvolvimento — que é onde os dados não são reais."""
    from django.conf import settings

    item = ItemCatalogo.objects.get(chave="chamado-predial-iconnect")
    assert item.url_externa == settings.ICONNECT_URL


def test_o_card_avisa_que_sai_do_workspace(client, semeado):
    """A pessoa descobre ANTES de digitar. Link que muda de produto sem avisar
    é o que faz alguém perder o que escreveu do outro lado."""
    corpo = client.get(reverse("workspace:modulo", args=["operacoes"])).content.decode()

    assert "abre no iConnect" in corpo
    assert 'target="_blank"' in corpo
    assert 'rel="noopener"' in corpo


def test_o_card_externo_nao_abre_formulario(client, semeado):
    """Sem o campo `url_externa`, a única forma de atender o §11 seria um item
    que finge ser formulário e redireciona no POST — pior de todas, porque a
    pessoa preenche antes de descobrir."""
    corpo = client.get(reverse("workspace:modulo", args=["operacoes"])).content.decode()
    do_formulario = reverse("workspace:pedir", args=["chamado-predial-iconnect"])

    assert do_formulario not in corpo


def test_item_sem_url_externa_continua_normal(semeado):
    item = ItemCatalogo.objects.get(chave="prestacao-contas")

    assert not item.leva_para_fora


def test_manutencao_predial_foi_aposentada(semeado):
    """O chamado predial vive no iConnect Platform, que tem ordem de serviço,
    despacho, SLA e o histórico junto do cliente. Manter os dois criaria duas
    filas para o mesmo trabalho — e a segunda seria a que ninguém olha."""
    assert not any(s_["chave"] == "manutencao-predial" for s_ in CATALOGO_INICIAL)
    chaves = [i.chave for i in svc.do_modulo(("ops.",))]
    assert "manutencao-predial" not in chaves
    assert "chamado-predial-iconnect" in chaves
