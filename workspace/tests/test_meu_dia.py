"""Meu dia e a Central de Notificações.

Duas coisas aqui merecem teste por si:

1. **Nenhum widget nasce vazio (ADR-012).** Bloco sem dado não existe no
   contexto — não é um bloco vazio, é ausência. Dez cartões zerados são piores
   que um app launcher.
2. **A federação pelo contrato de provider.** É o que separa este produto de um
   launcher: um chamado atribuído no iConnect Platform aparece no Meu dia sem que
   o Workspace saiba o que é um `Ticket`.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.models import Notificacao, TipoNotificacao
from workspace.models.catalogo import (
    GrupoCatalogo,
    ItemCatalogo,
    SituacaoServico,
    SolicitacaoServico,
)
from workspace.models.aprovacao import RegraAprovacao, TipoAprovador
from workspace.providers import registry
from workspace.providers.base import PendingItemDTO, WorkspaceProvider
from workspace.services import aprovacao as apr
from workspace.services import meu_dia as md
from workspace.services import notificacoes as nt

pytestmark = pytest.mark.django_db


@pytest.fixture
def equipe():
    gestor, ana = f.pessoa("gestor"), f.pessoa("ana")
    f.lotar(gestor, centro_custo_codigo="1000")
    f.lotar(ana, gestor=gestor, centro_custo_codigo="1042")
    RegraAprovacao.objects.create(dominio="*", tipo=TipoAprovador.GESTOR_DIRETO, ordem=10)
    return {"gestor": gestor, "ana": ana}


@pytest.fixture
def item():
    return ItemCatalogo.objects.create(
        chave="compra",
        nome="Comprar algo",
        descricao_curta="Material",
        grupo=GrupoCatalogo.DINHEIRO,
        dominio="com.requisicao",
        icone="cart",
        exige_valor=True,
        prazo_prometido_dias=5,
        campos=[{"chave": "o_que", "rotulo": "O que", "obrigatorio": True}],
    )


def _pedir(item, quem, valor="1200"):
    from workspace.services import catalogo as svc

    return svc.solicitar(item, quem, dados={"o_que": "x"}, valor=Decimal(valor))


# ── Nenhum widget nasce vazio ───────────────────────────────────────


def test_dia_limpo_nao_tem_bloco_nenhum(equipe):
    contexto = md.para(equipe["ana"])

    assert contexto["blocos"] == []
    assert contexto["vazio"] is True
    assert contexto["total"] == 0


def test_tela_de_dia_limpo_diz_boa_noticia(client, equipe):
    """Dia limpo é boa notícia, não falta de dado. "Nenhum registro encontrado"
    transformaria isso em erro."""
    client.force_login(equipe["ana"])
    corpo = client.get(reverse("workspace:meu_dia")).content.decode()

    assert "Seu dia está limpo." in corpo
    assert "au-dia-bloco" not in corpo


def test_bloco_aparece_so_quando_tem_dado(equipe, item):
    _pedir(item, equipe["ana"])

    chaves = {b.chave for b in md.para(equipe["gestor"])["blocos"]}
    assert chaves == {"aprovacoes"}, "só o bloco com dado"


# ── Os blocos do Workspace ──────────────────────────────────────────


def test_aprovacoes_traz_valor_represado(equipe, item):
    _pedir(item, equipe["ana"], valor="1200")
    _pedir(item, equipe["ana"], valor="800")

    bloco = next(b for b in md.para(equipe["gestor"])["blocos"] if b.chave == "aprovacoes")

    assert bloco.total == 2
    assert "2.000,00" in bloco.resumo
    assert bloco.urgente, "inação aqui bloqueia OUTRA pessoa"


def test_devolvida_aparece_para_quem_pediu(equipe, item):
    solicitacao = _pedir(item, equipe["ana"])
    apr.decidir(
        solicitacao.aprovacao, equipe["gestor"], apr.Decisao.DEVOLVER, "Falta o orçamento."
    )

    bloco = next(b for b in md.para(equipe["ana"])["blocos"] if b.chave == "devolvidas")

    assert bloco.itens[0].subtitulo == "Falta o orçamento."
    assert bloco.urgente, "a bola está com o solicitante e ele pode não saber"


def test_devolvida_nao_aparece_para_o_aprovador(equipe, item):
    solicitacao = _pedir(item, equipe["ana"])
    apr.decidir(solicitacao.aprovacao, equipe["gestor"], apr.Decisao.DEVOLVER, "motivo")

    chaves = {b.chave for b in md.para(equipe["gestor"])["blocos"]}
    assert "devolvidas" not in chaves


def test_atrasada_conta_do_prazo_prometido(equipe, item):
    """Prazo que ninguém cobra deixa de existir em três meses."""
    solicitacao = _pedir(item, equipe["ana"])
    SolicitacaoServico.objects.filter(pk=solicitacao.pk).update(
        criado_em=timezone.now() - timedelta(days=9)  # prazo é 5
    )

    bloco = next(b for b in md.para(equipe["ana"])["blocos"] if b.chave == "atrasadas")

    assert bloco.itens[0].dias == 4
    assert not bloco.urgente, "é munição para cobrar, não ação da pessoa"


def test_dentro_do_prazo_nao_e_atraso(equipe, item):
    _pedir(item, equipe["ana"])

    chaves = {b.chave for b in md.para(equipe["ana"])["blocos"]}
    assert "atrasadas" not in chaves


def test_concluida_nao_conta_como_atraso(equipe, item):
    solicitacao = _pedir(item, equipe["ana"])
    SolicitacaoServico.objects.filter(pk=solicitacao.pk).update(
        criado_em=timezone.now() - timedelta(days=30), situacao=SituacaoServico.CONCLUIDA
    )

    assert "atrasadas" not in {b.chave for b in md.para(equipe["ana"])["blocos"]}


def test_ordem_dos_blocos_e_a_mensagem(equipe, item):
    """Primeiro o que bloqueia outra pessoa, depois o que bloqueia você."""
    devolvida = _pedir(item, equipe["ana"])
    apr.decidir(devolvida.aprovacao, equipe["gestor"], apr.Decisao.DEVOLVER, "motivo")
    _pedir(item, equipe["ana"], valor="500")

    ordem = [b.chave for b in md.para(equipe["gestor"])["blocos"]]
    assert ordem[0] == "aprovacoes"

    ordem_ana = [b.chave for b in md.para(equipe["ana"])["blocos"]]
    assert ordem_ana.index("devolvidas") < len(ordem_ana)


def test_recorte_do_bloco_informa_o_excedente(equipe, item):
    for _ in range(md.LIMITE_POR_BLOCO + 3):
        _pedir(item, equipe["ana"], valor="100")

    bloco = next(b for b in md.para(equipe["gestor"])["blocos"] if b.chave == "aprovacoes")

    assert len(bloco.itens) == md.LIMITE_POR_BLOCO
    assert bloco.excedente == 3, "corte silencioso mentiria sobre o tamanho da fila"


# ── Federação pelo contrato de provider ─────────────────────────────


class ProviderFalso(WorkspaceProvider):
    key = "falso"
    label = "Domínio de teste"

    def __init__(self, itens=None, explode=False):
        self._itens = itens or []
        self._explode = explode

    def pending_items(self, pessoa):
        if self._explode:
            raise RuntimeError("domínio fora do ar")
        return self._itens


@pytest.fixture
def provider_temporario():
    anteriores = list(registry.all())
    registrados = []

    def registrar(provider):
        registry.register(provider, substituir=True)
        registrados.append(provider.key)
        return provider

    yield registrar

    for chave in registrados:
        registry.unregister(chave)
    for anterior in anteriores:
        registry.register(anterior, substituir=True)


def test_pendencia_de_dominio_aparece_no_meu_dia(equipe, provider_temporario):
    """O que separa isto de um app launcher."""
    provider_temporario(
        ProviderFalso(
            [
                PendingItemDTO(
                    origem="falso",
                    titulo="#123 · Câmera sem imagem",
                    url="/tickets/123/",
                    subtitulo="Cliente Vega",
                    icone="ticket",
                    prioridade=30,
                )
            ]
        )
    )

    bloco = next(
        b for b in md.para(equipe["ana"])["blocos"] if b.chave == "dominio:falso"
    )

    assert bloco.titulo == "Domínio de teste"
    assert bloco.itens[0].titulo == "#123 · Câmera sem imagem"
    assert bloco.icone == "ticket"


def test_dominio_ordena_por_prioridade(equipe, provider_temporario):
    provider_temporario(
        ProviderFalso(
            [
                PendingItemDTO(origem="falso", titulo="baixa", url="/a/", prioridade=0),
                PendingItemDTO(origem="falso", titulo="crítica", url="/b/", prioridade=30),
            ]
        )
    )

    bloco = next(b for b in md.para(equipe["ana"])["blocos"] if b.chave == "dominio:falso")
    assert [i.titulo for i in bloco.itens] == ["crítica", "baixa"]


def test_provider_que_estoura_nao_derruba_a_tela(client, equipe, item, provider_temporario):
    """Falha de agregador é degradação, não erro.

    Se o iConnect estiver com problema, "meu dia" ainda tem de mostrar aprovação
    e pedido devolvido — que são dado do próprio Workspace.
    """
    provider_temporario(ProviderFalso(explode=True))
    _pedir(item, equipe["ana"])

    client.force_login(equipe["gestor"])
    resposta = client.get(reverse("workspace:meu_dia"))

    assert resposta.status_code == 200
    chaves = {b.chave for b in resposta.context["blocos"]}
    assert "aprovacoes" in chaves
    assert "dominio:falso" not in chaves


def test_provider_sem_pendencia_nao_cria_bloco(equipe, provider_temporario):
    provider_temporario(ProviderFalso([]))

    assert not any(
        b.chave.startswith("dominio:") for b in md.para(equipe["ana"])["blocos"]
    )


# ── Notificações ────────────────────────────────────────────────────


def test_chegar_a_vez_notifica_o_aprovador(equipe, item):
    """O buraco que isto fecha: hoje o aprovador descobre abrindo a tela."""
    _pedir(item, equipe["ana"], valor="1200")

    aviso = Notificacao.objects.de(equipe["gestor"]).get()
    assert aviso.tipo == TipoNotificacao.VEZ_DE_APROVAR
    assert "Comprar algo" in aviso.titulo
    assert "R$ 1.200,00" in aviso.corpo
    assert aviso.url == reverse("workspace:aprovacoes")
    assert not aviso.lida


def test_solicitante_nao_e_notificado_do_proprio_pedido(equipe, item):
    _pedir(item, equipe["ana"])

    assert not Notificacao.objects.de(equipe["ana"]).exists()


def test_devolucao_notifica_com_o_motivo(equipe, item):
    solicitacao = _pedir(item, equipe["ana"])
    apr.decidir(
        solicitacao.aprovacao, equipe["gestor"], apr.Decisao.DEVOLVER, "Falta o orçamento."
    )

    aviso = Notificacao.objects.de(equipe["ana"]).get()
    assert aviso.tipo == TipoNotificacao.PEDIDO_DEVOLVIDO
    assert aviso.corpo == "Falta o orçamento."


def test_aprovacao_notifica_o_solicitante(equipe, item):
    solicitacao = _pedir(item, equipe["ana"])
    apr.decidir(solicitacao.aprovacao, equipe["gestor"], apr.Decisao.APROVAR)

    aviso = Notificacao.objects.de(equipe["ana"]).get()
    assert aviso.tipo == TipoNotificacao.PEDIDO_APROVADO


def test_cancelar_o_proprio_pedido_nao_gera_aviso(equipe, item):
    """Ele acabou de clicar em cancelar."""
    from workspace.services import catalogo as svc

    solicitacao = _pedir(item, equipe["ana"])
    svc.cancelar(solicitacao, equipe["ana"])

    tipos = set(Notificacao.objects.de(equipe["ana"]).values_list("tipo", flat=True))
    assert TipoNotificacao.PEDIDO_CANCELADO not in tipos


def test_etapa_por_papel_nao_gera_aviso(equipe, item):
    """"Diretoria" são três pessoas. Três linhas apontando para o mesmo pedido
    deixariam duas órfãs quando uma aprovasse."""
    papel = f.papel("diretoria", ["apr.aprovar.global"], escopo="global")
    RegraAprovacao.objects.create(
        dominio="*", valor_minimo=Decimal("1000"), tipo=TipoAprovador.PAPEL,
        papel=papel, ordem=20,
    )
    diretor = f.pessoa("diretor")
    f.lotar(diretor)
    f.atribuir(diretor, papel)

    _pedir(item, equipe["ana"], valor="5000")

    assert not Notificacao.objects.de(diretor).exists()
    assert Notificacao.objects.de(equipe["gestor"]).exists(), "a etapa nominal avisa"


def test_dedupe_olha_so_o_nao_lido(equipe, item):
    solicitacao = _pedir(item, equipe["ana"])
    etapa = solicitacao.aprovacao.etapa_atual

    nt.ao_chegar_a_vez(None, solicitacao=solicitacao.aprovacao, etapa=etapa)
    assert Notificacao.objects.de(equipe["gestor"]).count() == 1, "não repete o não lido"

    nt.marcar_lidas(equipe["gestor"])
    nt.ao_chegar_a_vez(None, solicitacao=solicitacao.aprovacao, etapa=etapa)

    assert Notificacao.objects.de(equipe["gestor"]).count() == 2, (
        "depois de lida, o mesmo evento voltando é evento novo"
    )


def test_contador_do_sino_conta_so_nao_lidas(equipe, item):
    _pedir(item, equipe["ana"])
    assert nt.quantas_nao_lidas(equipe["gestor"]) == 1

    nt.marcar_lidas(equipe["gestor"])
    assert nt.quantas_nao_lidas(equipe["gestor"]) == 0


def test_sino_aparece_na_casca_com_o_numero(client, equipe, item):
    _pedir(item, equipe["ana"])
    client.force_login(equipe["gestor"])
    corpo = client.get(reverse("workspace:home")).content.decode()

    assert "au-sino--ativo" in corpo
    assert "au-sino-contagem" in corpo


@pytest.mark.parametrize(
    "rota",
    [
        "workspace:home",
        "workspace:meu_dia",
        "workspace:notificacoes",
        "workspace:servicos",
        "workspace:minhas_solicitacoes",
        "workspace:aprovacoes",
    ],
)
def test_sino_aparece_em_toda_tela_autenticada(client, equipe, item, rota):
    """O bug que isto trava: a casca usava a variável `autenticado`, preenchida
    por CADA view. Bastou uma view nova não preencher para a topbar perder o
    sino e o nome do usuário — sem quebrar nada, sem erro, sem teste falhando.

    Casca não pode depender de cada view lembrar de um detalhe da casca.
    """
    _pedir(item, equipe["ana"])
    client.force_login(equipe["gestor"])
    corpo = client.get(reverse(rota)).content.decode()

    assert "au-sino" in corpo, f"{rota} não tem o sino"
    assert "au-sino-contagem" in corpo, f"{rota} não tem o contador"
    assert "au-usuario" in corpo, f"{rota} não mostra quem está logado"


def test_sino_sem_contador_quando_tudo_lido(client, equipe):
    """Sino com "0" permanente é a coisa que se aprende a não olhar."""
    client.force_login(equipe["gestor"])
    corpo = client.get(reverse("workspace:home")).content.decode()

    assert "au-sino-contagem" not in corpo


def test_abrir_a_central_nao_marca_como_lida(client, equipe, item):
    """Marcar em massa ao abrir faz a pessoa perder o aviso que ainda não leu."""
    _pedir(item, equipe["ana"])
    client.force_login(equipe["gestor"])
    client.get(reverse("workspace:notificacoes"))

    assert nt.quantas_nao_lidas(equipe["gestor"]) == 1


def test_marcar_lidas_pela_tela(client, equipe, item):
    _pedir(item, equipe["ana"])
    client.force_login(equipe["gestor"])
    resposta = client.post(reverse("workspace:marcar_lidas"))

    assert resposta.status_code == 302
    assert nt.quantas_nao_lidas(equipe["gestor"]) == 0


def test_marcar_lidas_por_get_nao_altera_nada(client, equipe, item):
    """Estado não muda em GET — link pré-carregado pelo navegador limparia o sino."""
    _pedir(item, equipe["ana"])
    client.force_login(equipe["gestor"])
    client.get(reverse("workspace:marcar_lidas"))

    assert nt.quantas_nao_lidas(equipe["gestor"]) == 1


def test_voltar_recusa_destino_fora_do_workspace(client, equipe, item):
    """`voltar` vem do formulário. Sem validação, é redirecionamento aberto."""
    _pedir(item, equipe["ana"])
    client.force_login(equipe["gestor"])
    resposta = client.post(
        reverse("workspace:marcar_lidas"), {"voltar": "https://exemplo.invalido/"}
    )

    assert resposta["Location"] == reverse("workspace:notificacoes")


def test_voltar_aceita_destino_interno(client, equipe, item):
    _pedir(item, equipe["ana"])
    client.force_login(equipe["gestor"])
    resposta = client.post(
        reverse("workspace:marcar_lidas"), {"voltar": reverse("workspace:meu_dia")}
    )

    assert resposta["Location"] == reverse("workspace:meu_dia")


def test_ninguem_ve_notificacao_de_outro(equipe, item):
    _pedir(item, equipe["ana"])

    assert not Notificacao.objects.de(equipe["ana"]).exists()
    assert Notificacao.objects.de(equipe["gestor"]).count() == 1


def test_central_exige_login(client):
    for rota in ("workspace:meu_dia", "workspace:notificacoes"):
        resposta = client.get(reverse(rota))
        assert resposta.status_code == 302
        assert "/login" in resposta["Location"]


def test_criar_sem_destinatario_e_ignorado():
    assert nt.criar(None, TipoNotificacao.PEDIDO_APROVADO, "x") is None


def test_marcar_lidas_com_ids(equipe, item):
    _pedir(item, equipe["ana"], valor="100")
    _pedir(item, equipe["ana"], valor="200")
    avisos = list(Notificacao.objects.de(equipe["gestor"]))
    assert len(avisos) == 2

    nt.marcar_lidas(equipe["gestor"], ids=[avisos[0].pk])

    assert nt.quantas_nao_lidas(equipe["gestor"]) == 1


def test_marcar_lida_no_model_e_idempotente(equipe, item):
    _pedir(item, equipe["ana"])
    aviso = Notificacao.objects.de(equipe["gestor"]).get()

    aviso.marcar_lida()
    primeira = aviso.lida_em
    aviso.marcar_lida()

    assert aviso.lida_em == primeira
    assert aviso.lida


def test_str_da_notificacao(equipe, item):
    _pedir(item, equipe["ana"])
    aviso = Notificacao.objects.de(equipe["gestor"]).get()

    assert "gestor" in str(aviso)


def test_anonimo_nao_tem_notificacao():
    from django.contrib.auth.models import AnonymousUser

    assert not Notificacao.objects.de(AnonymousUser()).exists()
    assert not Notificacao.objects.de(None).exists()
    assert nt.quantas_nao_lidas(AnonymousUser()) == 0
