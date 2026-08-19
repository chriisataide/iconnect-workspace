"""§56 e §57 — a camada de IA desacoplada, e a busca que faltava metade.

## §56 — por que uma camada, e não uma chamada

Trocar de fornecedor de IA não pode ser uma varredura por `import openai` em
oito arquivos. A camada segue o padrão que o projeto já usa em
`providers/orcamento.py`; a diferença é o que acontece **quando não há ninguém
registrado**.

A regra que sustenta o resto: **nenhuma tela depende de IA.** Sem provedor, todo
método devolve `None` e cada superfície tem o caminho determinístico que já
tinha. Um assistente que só responde com o provedor de pé falha no dia do
incidente — e é no dia do incidente que as pessoas perguntam onde fica alguma
coisa.

## §57 — a busca achava o item e não achava o pedido

O índice cobria serviços, documentos, comunicados e notícias. Quem digitava
"reembolso março" achava o item de catálogo "Reembolso" e não achava o próprio
pedido — que é o que a pessoa procura.

O que entrou: perguntas frequentes, cursos, recursos reserváveis (as três
institucionais, `*`) e solicitações e correspondências (as duas PESSOAIS,
recortadas por `pessoa:N` no `WHERE`).
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.models.busca import EntradaIndice, OrigemIndice
from workspace.providers import ia
from workspace.providers.ia import Analise, ProvedorIA
from workspace.services import assistente as asst
from workspace.services import indice as idx

pytestmark = pytest.mark.django_db


class ProvedorFalso(ProvedorIA):
    key = "falso"
    label = "Provedor de teste"

    def __init__(self, resposta="Resposta gerada.", analise=None, explode=False):
        self._resposta = resposta
        self._analise = analise
        self._explode = explode

    def responder(self, pergunta, contexto=""):
        if self._explode:
            raise RuntimeError("o fornecedor caiu")
        return self._resposta

    def analisar_documento(self, texto, tipo="contrato"):
        return self._analise


@pytest.fixture
def sem_ia():
    ia.limpar()
    yield
    ia.limpar()


@pytest.fixture
def com_ia(sem_ia):
    provedor = ProvedorFalso()
    ia.registrar(provedor, substituir=True)
    yield provedor
    ia.limpar()


# ── §56 · a camada ──────────────────────────────────────────────────


def test_sem_provedor_tudo_devolve_none(sem_ia):
    """`None` é resposta legítima e não erro: é o que permite a superfície ter
    caminho determinístico sem perguntar se há provedor."""
    assert ia.disponivel() is False
    assert ia.responder("oi") is None
    assert ia.analisar_documento("texto") is None
    assert ia.redigir({}) is None
    assert ia.classificar("x", ["a", "b"]) is None
    assert ia.ordenar_por_semantica("x", ["a"]) is None


def test_registrar_e_obter(com_ia):
    assert ia.disponivel()
    assert ia.obter() is com_ia
    assert ia.responder("como peço férias") == "Resposta gerada."


def test_dois_provedores_sem_substituir_e_erro(com_ia):
    """Dois registrados significa que um some em silêncio — e duas telas
    responderiam com modelos diferentes sobre o mesmo assunto."""
    with pytest.raises(ValueError, match="Já existe provedor"):
        ia.registrar(ProvedorFalso())


def test_objeto_que_nao_e_provedor_e_recusado(sem_ia):
    with pytest.raises(TypeError, match="ProvedorIA"):
        ia.registrar(object())


def test_provedor_sem_chave_e_recusado(sem_ia):
    class SemChave(ProvedorIA):
        label = "x"

    with pytest.raises(ValueError, match="`key`"):
        ia.registrar(SemChave())


def test_provedor_que_estoura_nao_derruba_a_tela(sem_ia):
    """A regra 3 do contrato de provider: provedor que levanta exceção degrada o
    recurso, nunca a página. Sem isto, o dia em que a API do fornecedor ficar
    fora seria o dia em que o portal inteiro fica fora."""
    ia.registrar(ProvedorFalso(explode=True), substituir=True)

    assert ia.responder("qualquer coisa") is None


def test_provedor_que_nao_implementa_um_metodo_devolve_none(sem_ia):
    """Um provedor implementa só o que oferece — obrigar os seis faria quem só
    faz análise de contrato escrever cinco `return None`."""
    ia.registrar(ProvedorFalso(), substituir=True)

    assert ia.redigir({"a": 1}) is None


def test_a_ressalva_juridica_mora_no_contrato():
    """§25 — a análise é apoio e não substitui parecer jurídico. A frase fica no
    contrato para que nenhum provedor possa omiti-la."""
    assert "não substitui a análise jurídica profissional" in Analise.RESSALVA


def test_a_analise_separa_resumo_riscos_e_recomendacoes():
    """Um bloco de texto único obrigaria o template a fatiar a saída do modelo
    por marcador — que muda sem avisar."""
    analise = Analise(
        resumo="Contrato de prestação de serviço.",
        riscos=["Multa de 30% sem teto."],
        pontos_criticos=["Reajuste anual não indexado."],
        recomendacoes=["Negociar o teto da multa."],
        campos={"vigencia": "24 meses"},
    )

    assert analise.riscos == ["Multa de 30% sem teto."]
    assert analise.campos["vigencia"] == "24 meses"


# ── §56 · o assistente sem e com IA ─────────────────────────────────


@pytest.fixture
def base_de_faq(db):
    from workspace.models.faq import PerguntaFrequente

    PerguntaFrequente.objects.create(
        area="rh",
        pergunta="Como solicitar férias?",
        resposta="Procure o R.H. da sua unidade.",
        palavras_chave=["ferias", "descanso"],
        prioridade=90,
    )


def test_a_base_curada_responde_antes_da_ia(base_de_faq, com_ia):
    """A ordem não muda: base curada, motor de intenção, IA. Inverter faria o
    assistente responder por aproximação uma pergunta que tem resposta escrita e
    conferida — e a resposta conferida é a razão de a base existir."""
    resposta = asst.responder("como solicitar férias")

    assert "Procure o R.H." in resposta.texto
    assert resposta.de_ia is False


def test_a_ia_e_o_ultimo_degrau(base_de_faq, com_ia):
    resposta = asst.responder("qual a política de dividendos da holding")

    assert resposta.texto == "Resposta gerada."
    assert resposta.de_ia is True
    # `sem_resposta` continua verdadeiro: é o sinal que diz a quem mantém a base
    # qual pergunta falta escrever.
    assert resposta.sem_resposta is True


def test_sem_ia_o_assistente_continua_respondendo(base_de_faq, sem_ia):
    """O ponto do §56 em um teste."""
    curada = asst.responder("como solicitar férias")
    desconhecida = asst.responder("qual a política de dividendos da holding")

    assert "Procure o R.H." in curada.texto
    assert desconhecida.sem_resposta
    assert desconhecida.de_ia is False
    assert "catálogo" in desconhecida.texto


def test_o_contexto_enviado_nao_leva_a_base_inteira(base_de_faq, sem_ia):
    """Mandar a base num contexto seria enviar para fora todo o conteúdo interno
    a cada pergunta."""
    contexto = asst._contexto_do_portal()

    assert "Procure o R.H." not in contexto
    assert "Áreas do portal" in contexto


def test_a_tela_marca_a_resposta_gerada(base_de_faq, com_ia, client):
    """Texto escrito e conferido tem outro peso que texto gerado por
    aproximação, e apagar a diferença é o que faz alguém citar o portal numa
    reunião com informação que ninguém revisou."""
    resposta = client.get(
        reverse("workspace:assistente"), {"q": "política de dividendos da holding"}
    )

    assert resposta.json()["de_ia"] is True


# ── §57 · a busca global ────────────────────────────────────────────


@pytest.fixture
def cenario():
    unidade = f.unidade()
    ana, bruno = f.pessoa("ana"), f.pessoa("bruno")
    f.lotar(ana, uni=unidade)
    f.lotar(bruno, uni=unidade)
    return {"unidade": unidade, "ana": ana, "bruno": bruno}


def buscar(client, termo):
    return client.get(reverse("workspace:buscar"), {"q": termo}).content.decode()


def test_a_faq_entra_na_busca(cenario, client):
    """A base do assistente era buscável POR ELE e não pela busca do portal."""
    from workspace.models.faq import PerguntaFrequente

    PerguntaFrequente.objects.create(
        area="rh", pergunta="Como enviar nota fiscal de PJ?",
        resposta="Pelo card Pagamento de PJ.", palavras_chave=["nota fiscal", "pj"],
    )
    client.force_login(cenario["ana"])

    assert "Como enviar nota fiscal de PJ?" in buscar(client, "nota fiscal")


def test_faq_desativada_sai_do_indice(cenario, client):
    from workspace.models.faq import PerguntaFrequente

    pergunta = PerguntaFrequente.objects.create(
        area="rh", pergunta="Pergunta velha", resposta="x", palavras_chave=["velha"]
    )
    pergunta.ativo = False
    pergunta.save()

    assert not EntradaIndice.objects.filter(origem=OrigemIndice.FAQ).exists()


def test_o_curso_entra_na_busca(cenario, client):
    from workspace.models.habilitacao import Curso, TipoCurso

    Curso.objects.create(
        codigo="nr-35", nome="NR-35 Trabalho em altura", tipo=TipoCurso.NR,
        descricao="Reciclagem bienal.",
    )
    client.force_login(cenario["ana"])

    assert "NR-35" in buscar(client, "altura")


def test_o_recurso_reservavel_entra_na_busca(cenario, client):
    """Quem digita "auditório" quer marcar o auditório, e antes disto a busca só
    achava a palavra se ela aparecesse num comunicado."""
    from workspace.models.reserva import Recurso, TipoRecurso

    Recurso.objects.create(
        codigo="auditorio", nome="Auditório", tipo=TipoRecurso.SALA,
        descricao="Treinamento e apresentação",
    )
    client.force_login(cenario["ana"])

    corpo = buscar(client, "auditorio")
    assert "Auditório" in corpo
    assert reverse("workspace:reservar", args=["auditorio"]) in corpo


def test_a_solicitacao_da_pessoa_entra_na_busca(cenario, client):
    from workspace.models.catalogo import GrupoCatalogo, ItemCatalogo
    from workspace.services import catalogo as svc

    item = ItemCatalogo.objects.create(
        chave="reembolso", nome="Reembolso de despesa",
        grupo=GrupoCatalogo.DINHEIRO, dominio="rh.reembolso",
    )
    svc.solicitar(item, cenario["ana"], {})
    client.force_login(cenario["ana"])

    assert "Reembolso de despesa" in buscar(client, "reembolso")


def test_a_solicitacao_de_um_nao_aparece_para_o_outro(cenario, client):
    """O recorte acontece no `WHERE`: o pedido de alguém não entra nem na
    CONTAGEM de resultado de mais ninguém."""
    from workspace.models.catalogo import GrupoCatalogo, ItemCatalogo
    from workspace.services import catalogo as svc

    from workspace.models.catalogo import SolicitacaoServico

    item = ItemCatalogo.objects.create(
        chave="adiantamento", nome="Adiantamento de viagem",
        grupo=GrupoCatalogo.DINHEIRO, dominio="rh.adiantamento",
    )
    svc.solicitar(item, cenario["ana"], {})

    pedido = SolicitacaoServico.objects.get()
    client.force_login(cenario["bruno"])
    corpo = buscar(client, "adiantamento")

    # O ITEM de catálogo aparece — ele é institucional. O PEDIDO da Ana, não.
    assert f"#{pedido.pk}" not in corpo


def test_o_rascunho_nao_entra_na_busca(cenario, client):
    """Rascunho não é pedido: ele está no formulário, não na esteira."""
    from workspace.models.catalogo import GrupoCatalogo, ItemCatalogo
    from workspace.services import catalogo as svc

    item = ItemCatalogo.objects.create(
        chave="compra", nome="Compra de material",
        grupo=GrupoCatalogo.ESPACO, dominio="log.compra",
    )
    svc.salvar_rascunho(item, cenario["ana"], {})

    assert not EntradaIndice.objects.filter(origem=OrigemIndice.SOLICITACAO).exists()


def test_o_formulario_do_pedido_nao_vai_para_o_indice(cenario, client):
    """Ali moram atestado, dados bancários e motivo de afastamento — um índice
    que varre isso transforma a caixa de busca num vazador de dado sensível."""
    from workspace.models.catalogo import GrupoCatalogo, ItemCatalogo, TipoCampo
    from workspace.services import catalogo as svc

    item = ItemCatalogo.objects.create(
        chave="afastamento", nome="Afastamento", grupo=GrupoCatalogo.TRABALHO,
        dominio="rh.ausencia",
        campos=[{"chave": "motivo", "rotulo": "Motivo", "tipo": TipoCampo.TEXTO}],
    )
    svc.solicitar(item, cenario["ana"], {"motivo": "cirurgia cardiaca"})

    entrada = EntradaIndice.objects.get(origem=OrigemIndice.SOLICITACAO)
    assert "cirurgia" not in entrada.texto


def test_a_correspondencia_da_pessoa_entra_na_busca(cenario, client):
    from workspace.models.correspondencia import Correspondencia, TipoCorrespondencia

    Correspondencia.objects.create(
        tipo=TipoCorrespondencia.ENCOMENDA, remetente="Loja Alfa",
        destinatario=cenario["ana"], recebido_por=cenario["bruno"],
        numero_rastreio="BR123456789",
    )
    client.force_login(cenario["ana"])

    assert "BR123456789" in buscar(client, "BR123456789") or "Encomenda" in buscar(
        client, "alfa"
    )


def test_correspondencia_sem_destinatario_nao_entra(cenario):
    """Sem sujeito a quem endereçar, `*` entregaria à empresa inteira o que
    chegou para alguém."""
    from workspace.models.correspondencia import Correspondencia, TipoCorrespondencia

    Correspondencia.objects.create(
        tipo=TipoCorrespondencia.CARTA, nome_no_envelope="ilegível",
        recebido_por=cenario["bruno"],
    )

    assert not EntradaIndice.objects.filter(
        origem=OrigemIndice.CORRESPONDENCIA
    ).exists()


def test_o_anonimo_nao_acha_pedido_de_ninguem(cenario, client):
    from workspace.models.catalogo import GrupoCatalogo, ItemCatalogo
    from workspace.services import catalogo as svc

    item = ItemCatalogo.objects.create(
        chave="ferias", nome="Férias", grupo=GrupoCatalogo.TRABALHO,
        dominio="rh.ferias",
    )
    svc.solicitar(item, cenario["ana"], {})
    from workspace.models.catalogo import SolicitacaoServico

    corpo = buscar(client, "ferias")

    # O grupo de resultado da solicitação não aparece. A checagem é pelo
    # TÍTULO indexado e não pelo nome do grupo: "Minhas solicitações" também é
    # uma ação do motor de intenção, e casaria por acidente.
    #
    # Este teste pegou um vazamento de verdade: a busca usava
    # `pessoa_da_requisicao()` — a pessoa de REFERÊNCIA do hub aberto —, então o
    # visitante anônimo procurava COMO uma pessoa real e via, com nome e número,
    # os pedidos dela.
    assert f"Férias · #{SolicitacaoServico.objects.get().pk}" not in corpo


def test_reindexar_cobre_todas_as_origens(cenario):
    """Sinal e reindexação saem da MESMA tabela: listas diferentes é como uma
    origem passa a existir só depois de alguém rodar o comando à mão."""
    from workspace.models.faq import PerguntaFrequente
    from workspace.models.habilitacao import Curso, TipoCurso
    from workspace.models.reserva import Recurso, TipoRecurso

    PerguntaFrequente.objects.create(area="rh", pergunta="P", resposta="R")
    Curso.objects.create(codigo="c", nome="Curso", tipo=TipoCurso.NR)
    Recurso.objects.create(codigo="r", nome="Sala", tipo=TipoRecurso.SALA)
    EntradaIndice.objects.all().delete()

    contagem = idx.reindexar()

    assert contagem["faq"] == 1
    assert contagem["cursos"] == 1
    assert contagem["recursos"] == 1


# ── §7 · a fila mostra situação e prioridade ────────────────────────


def test_a_prioridade_e_derivada_do_prazo_prometido(cenario):
    """Prioridade declarada é sempre a mesma história: no terceiro mês todo
    mundo marca "urgente", e a coluna deixa de significar qualquer coisa."""
    from datetime import timedelta

    from django.utils import timezone

    from workspace.models.catalogo import (
        GrupoCatalogo,
        ItemCatalogo,
        SolicitacaoServico,
    )
    from workspace.services import catalogo as svc

    item = ItemCatalogo.objects.create(
        chave="troca", nome="Troca de equipamento", grupo=GrupoCatalogo.EQUIPAMENTO,
        dominio="ti.chamado", prazo_prometido_dias=3,
    )
    pedido = svc.solicitar(item, cenario["ana"], {})

    assert pedido.prioridade == "normal"

    SolicitacaoServico.objects.filter(pk=pedido.pk).update(
        criado_em=timezone.now() - timedelta(days=3)
    )
    pedido.refresh_from_db()
    assert pedido.prioridade == "no_limite"

    SolicitacaoServico.objects.filter(pk=pedido.pk).update(
        criado_em=timezone.now() - timedelta(days=9)
    )
    pedido.refresh_from_db()
    assert pedido.prioridade == "atrasado"
    assert pedido.prioridade_rotulo == "Atrasado"


def test_pedido_encerrado_nao_tem_prioridade(cenario):
    """Cobrar prazo de quem já foi atendido é ruído na única tela que mede
    trabalho em curso."""
    from workspace.models.catalogo import (
        GrupoCatalogo,
        ItemCatalogo,
        SituacaoServico,
    )
    from workspace.services import catalogo as svc

    item = ItemCatalogo.objects.create(
        chave="x", nome="X", grupo=GrupoCatalogo.EQUIPAMENTO, dominio="ti.chamado",
        prazo_prometido_dias=0,
    )
    pedido = svc.solicitar(item, cenario["ana"], {})
    pedido.situacao = SituacaoServico.CONCLUIDA
    pedido.save()

    assert pedido.prioridade == "normal"


def test_a_fila_mostra_situacao_e_prioridade(cenario, client):
    from decimal import Decimal

    from workspace.models.catalogo import GrupoCatalogo, ItemCatalogo
    from workspace.services import catalogo as svc

    atendente = f.pessoa("suporte")
    f.lotar(atendente, uni=cenario["unidade"])
    f.atribuir(atendente, f.papel("ti", ["ti.atender.global"], escopo="global"))
    item = ItemCatalogo.objects.create(
        chave="chamado", nome="Equipamento quebrado",
        grupo=GrupoCatalogo.EQUIPAMENTO, dominio="ti.chamado",
        # Auto-aprovado: cai direto na fila, que é o caminho mais comum do
        # produto — e o único em que esta tela tem o que mostrar.
        limite_auto_aprovacao=Decimal("0"),
    )
    svc.solicitar(item, cenario["ana"], {})
    client.force_login(atendente)

    corpo = client.get(reverse("workspace:fila")).content.decode()

    assert "Prioridade" in corpo
    assert "No prazo" in corpo


def test_o_anonimo_so_alcanca_o_que_e_institucional(cenario, client):
    """Antes do §57 o mesmo caminho já entregava ao visitante o documento
    dirigido ao departamento da pessoa de referência — menos visível e
    igualmente errado."""
    from workspace.models.conteudo import Documento, SituacaoDocumento, TipoDocumento

    dep = f.departamento("FIN", "Financeiro")
    dono = f.pessoa("primeira")
    f.lotar(dono, dep=dep)
    Documento.objects.create(
        slug="politica-restrita", titulo="Política de adiantamento",
        tipo=TipoDocumento.POLITICA, situacao=SituacaoDocumento.VIGENTE,
        publico_alvo=[f"depto:{dep.pk}"], dono=dono,
    )
    Documento.objects.create(
        slug="politica-geral", titulo="Política de conduta",
        tipo=TipoDocumento.POLITICA, situacao=SituacaoDocumento.VIGENTE,
        publico_alvo=["*"], dono=dono,
    )

    corpo = buscar(client, "politica")

    assert "Política de conduta" in corpo
    assert "Política de adiantamento" not in corpo
