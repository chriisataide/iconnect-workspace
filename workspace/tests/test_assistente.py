"""§3 — o assistente que responde antes de encaminhar.

## A ordem é o produto

    pergunta → a base responde? → sim: responde e oferece o caminho
                                → não: identifica a área e oferece o que fazer

Um assistente que encaminha primeiro é uma árvore de menus: a pessoa escolhe
"R.H." e recebe a mesma lista que já estava na tela. Um que responde primeiro
tira a pergunta da mesa do setor, que é o objetivo declarado do §3.

## Determinístico, e por quê

Mesma decisão de `intencao`: o problema não é compreender linguagem, é casar
termos que alguém cadastrou de propósito. Um modelo traria latência por tecla,
custo por pergunta, e — o pior — respostas inventadas sobre política interna,
que é justamente o assunto em que errar custa caro.

## As duas armadilhas que os testes travam

1. **Substring.** A primeira versão fazia `palavra in " ".join(termos)`, e
   "qual a **cor** do céu" respondia sobre **cor**respondência com toda a
   confiança do mundo. Num assistente isso é pior que não responder: a pessoa lê
   uma resposta plausível sobre outro assunto e vai embora.
2. **Palavra do título valendo como termo curado.** "pedir" aparece no título de
   metade da base, e "como faço para pedir um notebook" respondia sobre acesso a
   sistema. Termo cadastrado vale o dobro — quem escreveu "capacete" na lista
   sabia que alguém perguntaria assim; quem escreveu "Como pedir acesso a um
   sistema?" só estava escrevendo português.
"""

from __future__ import annotations

import json

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.models.faq import AreaFAQ, PerguntaFrequente
from workspace.services import assistente as asst
from workspace.services.assistente import FAQError

pytestmark = pytest.mark.django_db


@pytest.fixture
def base():
    ferias = PerguntaFrequente.objects.create(
        area=AreaFAQ.RH, pergunta="Como solicitar férias?",
        resposta="Abra “Férias” no catálogo.",
        palavras_chave=["ferias", "descanso", "folga"],
        url_acao="/workspace/servicos/ferias/", rotulo_acao="Pedir férias",
        prioridade=90,
    )
    carta = PerguntaFrequente.objects.create(
        area=AreaFAQ.PROCESSOS, pergunta="Chegou uma carta para mim. Como sei?",
        resposta="Você recebe aviso no sino.",
        palavras_chave=["carta", "correspondencia", "encomenda"],
        prioridade=80,
    )
    return {"ferias": ferias, "carta": carta}


@pytest.fixture
def mantenedor():
    pessoa = f.pessoa("editor")
    f.lotar(pessoa)
    f.atribuir(pessoa, f.papel("faq", ["faq.manter.global"], escopo="global"))
    return pessoa


# ── Responder ───────────────────────────────────────────────────────


def test_responde_pela_palavra_chave(base):
    resposta = asst.responder("como peço minhas férias")

    assert resposta.faq == base["ferias"]
    assert not resposta.sem_resposta


def test_responde_por_sinonimo_cadastrado(base):
    """"folga" não aparece na pergunta nem na resposta — só na lista. É o campo
    inteiro justificado num teste."""
    assert asst.responder("quero tirar uma folga").faq == base["ferias"]


def test_oferece_o_caminho_junto_da_resposta(base):
    """Responder e encaminhar, não responder OU encaminhar. É o que transforma
    a base de texto em primeira camada de atendimento."""
    acoes = asst.responder("como peço férias").acoes

    assert acoes[0] == {"rotulo": "Pedir férias", "url": "/workspace/servicos/ferias/"}


def test_substring_nao_conta_como_casamento(base):
    """"cor" é substring de "correspondencia". A primeira versão respondia sobre
    correspondência para quem perguntou a cor do céu."""
    resposta = asst.responder("qual a cor do ceu")

    assert resposta.faq is None
    assert resposta.sem_resposta


def test_palavra_do_titulo_vale_menos_que_termo_cadastrado(base):
    """"pedir" está no título de meia base e não distingue nada."""
    PerguntaFrequente.objects.create(
        area=AreaFAQ.TI, pergunta="Como pedir acesso a um sistema?",
        resposta="Abra “Acesso a um sistema”.",
        palavras_chave=["acesso", "senha", "login"], prioridade=95,
    )
    PerguntaFrequente.objects.create(
        area=AreaFAQ.COMPRAS, pergunta="Como peço um notebook?",
        resposta="Abra “Notebook”.", palavras_chave=["notebook", "laptop"],
        prioridade=50,
    )

    resposta = asst.responder("como faço para pedir um notebook")

    assert "Notebook" in resposta.texto, (
        "a palavra do título venceu o termo cadastrado — e a prioridade maior "
        "da outra pergunta escondeu o erro"
    )


def test_prioridade_desempata_com_a_mesma_pontuacao(base):
    PerguntaFrequente.objects.create(
        area=AreaFAQ.RH, pergunta="Férias coletivas",
        resposta="Outra coisa.", palavras_chave=["ferias"], prioridade=10,
    )

    assert asst.responder("ferias").faq == base["ferias"]


def test_pergunta_curta_demais_nao_procura(base):
    """"oi" e "ok" casariam com meia base."""
    resposta = asst.responder("oi")

    assert resposta.sem_resposta
    assert resposta.faq is None


def test_frase_so_com_palavras_vazias_nao_procura(base):
    assert asst.responder("como faço para").sem_resposta


def test_pergunta_desativada_nao_responde(base):
    PerguntaFrequente.objects.filter(pk=base["ferias"].pk).update(ativo=False)

    assert asst.responder("como peço férias").faq is None


def test_filtrar_por_area_restringe(base):
    """O painel pode perguntar dentro de uma área — e aí a resposta de outra
    área não deve aparecer, mesmo casando melhor."""
    assert asst.responder("carta", area=AreaFAQ.RH).faq is None
    assert asst.responder("carta", area=AreaFAQ.PROCESSOS).faq == base["carta"]


def test_as_outras_que_casaram_viram_sugestao(base):
    """A pergunta certa costuma ser a segunda quando a primeira erra, e obrigar
    a reescrever perde a pessoa."""
    PerguntaFrequente.objects.create(
        area=AreaFAQ.RH, pergunta="Férias coletivas",
        resposta="Outra coisa.", palavras_chave=["ferias", "coletivas"], prioridade=10,
    )

    rotulos = [a["rotulo"] for a in asst.responder("ferias").acoes]
    assert "Férias coletivas" in rotulos


# ── Encaminhar quando a base não cobre ──────────────────────────────


def test_sem_resposta_encaminha_pelo_catalogo(base):
    """O segundo degrau do §3, e ele usa o motor que já existe — reimplementar
    criaria duas verdades sobre como a empresa fala."""
    from decimal import Decimal

    from workspace.models.catalogo import GrupoCatalogo, ItemCatalogo

    ItemCatalogo.objects.create(
        chave="notebook", nome="Notebook", grupo=GrupoCatalogo.EQUIPAMENTO,
        dominio="com.requisicao", prazo_prometido_dias=12,
        limite_auto_aprovacao=Decimal("0"),
        termos=["laptop", "computador"], campos=[],
    )

    resposta = asst.responder("quero um laptop novo")

    assert resposta.sem_resposta, "não havia FAQ — tem de entrar na fila de FAQ nova"
    assert "Notebook" in resposta.texto
    assert resposta.acoes[0]["url"] == "/workspace/servicos/notebook/"


def test_sem_resposta_e_sem_item_oferece_o_catalogo(base):
    resposta = asst.responder("qual a cor do ceu")

    assert resposta.acoes == [{"rotulo": "Ver o catálogo", "url": "/workspace/servicos/"}]


def test_o_assistente_nunca_abre_pedido_sozinho(base):
    """Ele oferece o LINK; quem clica é a pessoa. Assistente que executa a
    partir de texto livre é o jeito mais rápido de alguém pedir férias sem
    querer."""
    from workspace.models.catalogo import SolicitacaoServico

    asst.responder("quero solicitar férias agora")

    assert not SolicitacaoServico.objects.exists()


# ── As listas da tela ───────────────────────────────────────────────


def test_por_area_esconde_area_vazia(base):
    """Treze áreas em que nove estão vazias ensina que o assistente não sabe
    nada, mesmo quando ele sabe."""
    areas = [g["area"] for g in asst.por_area()]

    assert set(areas) == {AreaFAQ.RH, AreaFAQ.PROCESSOS}


def test_sugestoes_iniciais_vem_por_prioridade(base):
    """Campo vazio com cursor piscando é a interface que faz a pessoa fechar o
    chat: ela não sabe o que ele sabe."""
    assert asst.sugestoes_iniciais()[0] == base["ferias"]


# ── A tela ──────────────────────────────────────────────────────────


def test_o_widget_aparece_em_toda_tela_do_portal(client, base):
    for rota in ("workspace:home", "workspace:servicos", "workspace:reservas"):
        corpo = client.get(reverse(rota)).content.decode()
        assert 'class="au-bot"' in corpo, rota


def test_o_widget_aparece_para_quem_nao_entrou(client, base):
    """"Como peço férias" é informação institucional. Pôr login na frente dela
    contradiz o hub aberto — e é justamente quem ainda não sabe onde ficam as
    coisas que mais precisa do assistente."""
    corpo = client.get(reverse("workspace:home")).content.decode()

    assert 'class="au-bot"' in corpo
    assert "Como solicitar férias?" in corpo


def test_o_endpoint_responde_em_json(client, base):
    resposta = client.get(reverse("workspace:assistente"), {"q": "como peço férias"})

    dados = json.loads(resposta.content)
    assert dados["pergunta"] == "Como solicitar férias?"
    assert dados["sem_resposta"] is False
    assert dados["acoes"][0]["url"] == "/workspace/servicos/ferias/"


def test_a_pagina_de_ajuda_funciona_sem_javascript(client, base):
    """O formulário do painel faz `GET` para cá. Uma primeira camada de
    atendimento que só funciona com JS carregado falha exatamente para quem está
    na rede ruim do canteiro de obra."""
    resposta = client.get(reverse("workspace:ajuda"), {"q": "férias"})

    corpo = resposta.content.decode()
    assert resposta.status_code == 200
    assert "Como solicitar férias?" in corpo
    assert "Você perguntou" in corpo


def test_a_pagina_de_ajuda_e_aberta(client, base):
    assert client.get(reverse("workspace:ajuda")).status_code == 200


# ── A administração da base (§3) ────────────────────────────────────


def test_quem_nao_mantem_nao_entra(client, base):
    colaborador = f.pessoa("ana")
    f.lotar(colaborador)
    client.force_login(colaborador)

    assert client.get(reverse("workspace:faq")).status_code == 403


def test_quem_mantem_ve_inclusive_as_desativadas(client, base, mantenedor):
    """O oposto do que o assistente mostra: desativar é o jeito de tirar uma
    resposta do ar sem perder o texto enquanto alguém reescreve."""
    PerguntaFrequente.objects.filter(pk=base["carta"].pk).update(ativo=False)
    client.force_login(mantenedor)

    corpo = client.get(reverse("workspace:faq")).content.decode()

    assert "Chegou uma carta" in corpo
    assert "Desativada" in corpo


def test_cadastrar_pela_tela(client, mantenedor):
    client.force_login(mantenedor)

    client.post(
        reverse("workspace:faq_nova"),
        {
            "area": AreaFAQ.SUPRIMENTOS, "pergunta": "Como peço uma van?",
            "resposta": "Abra Reservas.", "palavras_chave": "van\nveiculo\ncarro",
            "url_acao": "/workspace/reservas/", "rotulo_acao": "Reservar",
            "prioridade": "40", "ativo": "on",
        },
    )

    nova = PerguntaFrequente.objects.get(pergunta="Como peço uma van?")
    assert nova.palavras_chave == ["van", "veiculo", "carro"]
    assert nova.criado_por == mantenedor


def test_palavras_chave_uma_por_linha(client, mantenedor):
    """Separador por vírgula corromperia sinônimo que TEM vírgula dentro —
    "nota fiscal, NF" é um termo só."""
    client.force_login(mantenedor)

    client.post(
        reverse("workspace:faq_nova"),
        {
            "area": AreaFAQ.FINANCEIRO, "pergunta": "E a NF?",
            "resposta": "Anexe.", "palavras_chave": "nota fiscal, NF\nboleto\n\n  ",
        },
    )

    assert PerguntaFrequente.objects.get().palavras_chave == ["nota fiscal, NF", "boleto"]


def test_resposta_vazia_e_recusada(mantenedor):
    """Pergunta sem resposta é pior que pergunta ausente: ela aparece na lista,
    a pessoa clica, e recebe o vazio — e conclui que o assistente não funciona."""
    with pytest.raises(FAQError, match="resposta é obrigatória"):
        asst.salvar_pergunta(
            mantenedor, area=AreaFAQ.RH, titulo="Como?", resposta="   "
        )


def test_pergunta_vazia_e_recusada(mantenedor):
    with pytest.raises(FAQError, match="pergunta é obrigatória"):
        asst.salvar_pergunta(mantenedor, area=AreaFAQ.RH, titulo="", resposta="x")


def test_area_invalida_e_recusada(mantenedor):
    with pytest.raises(FAQError, match="Área inválida"):
        asst.salvar_pergunta(mantenedor, area="fofoca", titulo="Q", resposta="R")


def test_link_externo_e_recusado(mantenedor):
    """Só caminho interno: link para fora envelhece sem ninguém perceber; o
    interno, quando quebra, dá 404 na cara de quem mantém."""
    with pytest.raises(FAQError, match="caminho interno"):
        asst.salvar_pergunta(
            mantenedor, area=AreaFAQ.RH, titulo="Q", resposta="R",
            url_acao="https://exemplo.invalido/",
        )


def test_salvar_sem_permissao_e_recusado(base):
    ana = f.pessoa("ana")
    f.lotar(ana)

    with pytest.raises(FAQError, match="não pode manter"):
        asst.salvar_pergunta(ana, area=AreaFAQ.RH, titulo="Q", resposta="R")


def test_editar_nao_duplica(client, base, mantenedor):
    client.force_login(mantenedor)

    client.post(
        reverse("workspace:faq_editar", args=[base["ferias"].pk]),
        {
            "area": AreaFAQ.RH, "pergunta": "Como tirar férias?",
            "resposta": "Abra “Férias”.", "palavras_chave": "ferias", "ativo": "on",
        },
    )

    assert PerguntaFrequente.objects.count() == 2
    base["ferias"].refresh_from_db()
    assert base["ferias"].pergunta == "Como tirar férias?"


def test_desmarcar_ativa_tira_do_assistente(client, base, mantenedor):
    client.force_login(mantenedor)

    client.post(
        reverse("workspace:faq_editar", args=[base["ferias"].pk]),
        {
            "area": AreaFAQ.RH, "pergunta": base["ferias"].pergunta,
            "resposta": base["ferias"].resposta, "palavras_chave": "ferias",
        },
    )

    assert asst.responder("ferias").faq is None


def test_excluir_pela_tela(client, base, mantenedor):
    """Aqui apagar É o certo, ao contrário do comunicado: FAQ não é registro do
    que a empresa disse num dia — é a resposta corrente. Resposta errada
    arquivada continua sendo achada por quem procura, e alguém a reativa."""
    client.force_login(mantenedor)

    client.post(reverse("workspace:faq_excluir", args=[base["carta"].pk]))

    assert not PerguntaFrequente.objects.filter(pk=base["carta"].pk).exists()


def test_excluir_por_get_nao_apaga(client, base, mantenedor):
    client.force_login(mantenedor)

    client.get(reverse("workspace:faq_excluir", args=[base["carta"].pk]))

    assert PerguntaFrequente.objects.filter(pk=base["carta"].pk).exists()


def test_a_tela_avisa_quando_faltam_palavras_chave(client, mantenedor):
    """O defeito mais comum da base é uma pergunta boa que ninguém acha porque
    a lista de termos está vazia."""
    PerguntaFrequente.objects.create(
        area=AreaFAQ.RH, pergunta="Sem termos", resposta="x", palavras_chave=[]
    )
    client.force_login(mantenedor)

    assert "sem palavras-chave" in client.get(reverse("workspace:faq")).content.decode()


def test_erro_de_validacao_volta_para_o_formulario(client, mantenedor):
    client.force_login(mantenedor)

    resposta = client.post(
        reverse("workspace:faq_nova"),
        {"area": AreaFAQ.RH, "pergunta": "Como?", "resposta": ""},
    )

    assert resposta.status_code == 200
    assert "resposta é obrigatória" in resposta.content.decode()
    assert not PerguntaFrequente.objects.exists()
