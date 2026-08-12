"""Assistente de ação — "quero solicitar férias" abre o pedido de férias.

O risco deste módulo não é errar: é **acertar demais**. Assistente que oferece
uma ação para toda palavra digitada transforma o topo dos resultados em ruído
permanente, e o usuário aprende a pular a primeira linha — que é justamente onde
a resposta certa aparece quando ele realmente pediu algo.

Por isso metade dos testes aqui verifica que `interpretar()` devolve `None`.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.models.catalogo import GrupoCatalogo, ItemCatalogo
from workspace.models.conteudo import Documento, SituacaoDocumento, TipoDocumento
from workspace.services import intencao
from workspace.services.busca import buscar

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalogo():
    def criar(chave, nome, termos=(), **kwargs):
        return ItemCatalogo.objects.create(
            chave=chave, nome=nome, termos=list(termos),
            descricao_curta=kwargs.pop("descricao", f"{nome} — descrição"),
            grupo=kwargs.pop("grupo", GrupoCatalogo.TRABALHO),
            dominio=kwargs.pop("dominio", "rh.x"),
            prazo_prometido_dias=kwargs.pop("prazo", 5),
            **kwargs,
        )

    itens = {
        "ferias": criar("ferias", "Férias", ["descanso", "tirar ferias"]),
        "reembolso": criar(
            "reembolso", "Reembolso",
            ["gastei", "taxi", "uber", "nota fiscal", "combustivel"],
            dominio="fin.reembolso", icone="wallet",
        ),
        "notebook": criar(
            "notebook", "Notebook", ["laptop", "computador", "maquina"],
            dominio="com.requisicao", icone="cube",
        ),
        "atestado": criar("atestado", "Enviar atestado", ["atestado medico", "fiquei doente"]),
    }
    return itens


# ── Quando há intenção ──────────────────────────────────────────────


@pytest.mark.parametrize(
    "frase",
    [
        "quero solicitar férias",
        "quero férias",
        "preciso de férias",
        "gostaria de solicitar ferias",
        "como faço para solicitar férias",
        "como solicito férias",
        "onde solicito ferias",
        "solicitar férias",
        "pedir ferias",
        "abrir ferias",
    ],
)
def test_prefixos_de_intencao(catalogo, frase):
    acao = intencao.interpretar(frase)

    assert acao is not None, f"{frase!r} não virou ação"
    assert acao.item.chave == "ferias"
    assert acao.explicita


def test_rotulo_diz_o_que_vai_acontecer(catalogo):
    """"Pedir: Férias" e não "Férias" — o rótulo tem de dizer que isto AGE."""
    acao = intencao.interpretar("quero férias")

    assert acao.rotulo == "Pedir: Férias"


def test_encontra_pelo_termo_e_nao_pelo_nome(catalogo):
    """O ponto do campo `termos`: a pessoa não sabe que o item se chama
    "Reembolso". Ela sabe que gastou com táxi."""
    acao = intencao.interpretar("preciso lançar o uber")

    assert acao.item.chave == "reembolso"
    assert acao.termo == "uber"


def test_termo_aparece_para_a_pessoa_poder_conferir(catalogo):
    """`termo` vai para a tela: explicar POR QUE este item apareceu é o que
    permite confiar no acerto e perceber o erro."""
    acao = intencao.interpretar("quero um laptop")

    assert acao.termo == "laptop"
    assert acao.item.chave == "notebook"


def test_sem_acento_funciona(catalogo):
    assert intencao.interpretar("quero ferias").item.chave == "ferias"


def test_frase_com_ruido_depois_do_termo(catalogo):
    """"quero pedir um notebook novo urgente" — o item está no meio da frase."""
    acao = intencao.interpretar("quero pedir um notebook novo urgente")

    assert acao.item.chave == "notebook"


def test_artigo_depois_do_prefixo_e_ignorado(catalogo):
    for frase in ("preciso de um notebook", "quero uma maquina", "solicitar o notebook"):
        assert intencao.interpretar(frase).item.chave == "notebook", frase


def test_sem_prefixo_mas_casamento_exato_vira_acao(catalogo):
    """"férias" sozinho é forte o bastante: a palavra É o item."""
    acao = intencao.interpretar("férias")

    assert acao.item.chave == "ferias"
    assert not acao.explicita, "não houve prefixo — o casamento é que decidiu"


# ── Quando NÃO há intenção ──────────────────────────────────────────


def test_consulta_solta_nao_vira_acao(catalogo):
    """O caso que evita o ruído permanente: buscar "política" é consulta."""
    assert intencao.interpretar("politica") is None


def test_frase_de_leitura_nao_vira_acao(catalogo):
    """"preciso ver a política de férias" quer LER, não pedir.

    Sem a regra de cobertura, o termo "ferias" no meio da frase ofereceria abrir
    um pedido de férias — e a pessoa que queria a regra sairia com um pedido.
    """
    assert intencao.interpretar("preciso ver a politica de ferias") is None


def test_prefixo_sozinho_nao_adivinha(catalogo):
    for frase in ("quero", "preciso", "solicitar", "quero de"):
        assert intencao.interpretar(frase) is None, frase


def test_ambiguidade_nao_vira_acao(catalogo):
    """Empate é ambiguidade, e ambiguidade não escolhe por conta própria.

    Escolher um dos dois acerta metade das vezes; não escolher deixa os dois nos
    resultados de busca, onde a pessoa decide em um clique.
    """
    ItemCatalogo.objects.create(
        chave="acesso-vpn", nome="Acesso VPN", termos=["acesso"],
        grupo=GrupoCatalogo.EQUIPAMENTO, dominio="ti.acesso", prazo_prometido_dias=1,
    )
    ItemCatalogo.objects.create(
        chave="acesso-sistema", nome="Acesso a sistema", termos=["acesso"],
        grupo=GrupoCatalogo.EQUIPAMENTO, dominio="ti.acesso", prazo_prometido_dias=1,
    )

    assert intencao.interpretar("quero acesso") is None


def test_termo_mais_especifico_desempata(catalogo):
    """Ambiguidade só quando o peso é IGUAL. "atestado medico" é mais
    específico que "atestado" e ganha sem hesitar."""
    ItemCatalogo.objects.create(
        chave="declaracao", nome="Declaração", termos=["atestado"],
        grupo=GrupoCatalogo.TRABALHO, dominio="rh.doc", prazo_prometido_dias=1,
    )

    acao = intencao.interpretar("quero um atestado medico")

    assert acao.item.chave == "atestado"


def test_item_inativo_nao_vira_acao(catalogo):
    catalogo["ferias"].ativo = False
    catalogo["ferias"].save()

    assert intencao.interpretar("quero férias") is None


def test_frase_sem_nada_do_catalogo(catalogo):
    assert intencao.interpretar("quero um unicornio azul") is None


def test_termo_curto_nao_casa(catalogo):
    """Termo de duas letras casaria com quase tudo."""
    ItemCatalogo.objects.create(
        chave="ti", nome="TI", termos=["ti"],
        grupo=GrupoCatalogo.EQUIPAMENTO, dominio="ti.x", prazo_prometido_dias=1,
    )

    assert intencao.interpretar("quero ti") is None


# ── Na busca ────────────────────────────────────────────────────────


@pytest.fixture
def pessoa():
    ana = f.pessoa("ana")
    f.lotar(ana)
    return ana


def test_acao_e_o_primeiro_grupo(catalogo, pessoa):
    """Primeiro porque é a resposta. Os outros grupos são o plano B."""
    grupos = list(buscar("quero solicitar ferias", pessoa))

    assert grupos[0] == "Ação"


def test_acao_tem_um_item_so(catalogo, pessoa):
    """Quem escreveu "quero solicitar férias" delegou a escolha. Devolver seis
    opções é devolver o trabalho."""
    grupos = buscar("quero solicitar ferias", pessoa)

    assert len(grupos["Ação"]) == 1


def test_acao_leva_ao_formulario_de_pedido(catalogo, pessoa):
    grupos = buscar("quero férias", pessoa)

    assert grupos["Ação"][0].url == reverse("workspace:pedir", args=("ferias",))


def test_busca_sem_intencao_nao_tem_grupo_de_acao(catalogo, pessoa):
    from workspace.services import indice as idx

    idx.reindexar()
    grupos = buscar("politica", pessoa)

    assert "Ação" not in grupos


def test_termos_tambem_alimentam_a_busca_normal(catalogo, pessoa):
    """Quem digita "uber" tem de achar Reembolso na lista de serviços, mesmo
    quando a frase não é intenção."""
    from workspace.services import indice as idx

    idx.reindexar()
    grupos = buscar("uber", pessoa)

    assert [r.titulo for r in grupos["Serviços"]] == ["Reembolso"]


def test_termo_nao_polui_o_subtitulo(catalogo, pessoa):
    """O termo serve para ENCONTRAR, não para ler. "uber" no subtítulo do
    resultado pareceria erro de cadastro."""
    from workspace.services import indice as idx

    idx.reindexar()
    resultado = buscar("uber", pessoa)["Serviços"][0]

    assert "uber" not in resultado.subtitulo.lower()


def test_acao_e_conhecimento_convivem(catalogo, pessoa):
    """A tela responde as duas perguntas: "quero férias" (agir) e o que a
    empresa diz sobre férias (ler)."""
    from workspace.services import indice as idx

    dono = f.pessoa("dono")
    Documento.objects.create(
        slug="politica-ferias", tipo=TipoDocumento.POLITICA,
        titulo="Politica de ferias", corpo="Trinta dias.",
        dono=dono, publico_alvo=["*"], situacao=SituacaoDocumento.VIGENTE,
    )
    idx.reindexar()

    grupos = buscar("quero solicitar ferias", pessoa)

    assert grupos["Ação"][0].titulo == "Pedir: Férias"
    assert "Politica de ferias" in [r.titulo for r in grupos["Documentação"]]
    assert list(grupos)[0] == "Ação"


def test_tela_destaca_o_grupo_de_acao(client, catalogo, pessoa):
    """Ação e link para ler não são o mesmo tipo de coisa. Tratar igual faz a
    ação passar como mais um resultado."""
    client.force_login(pessoa)
    corpo = client.get(
        reverse("workspace:buscar"), {"q": "quero solicitar ferias"}
    ).content.decode()

    assert "au-busca-grupo--acao" in corpo
    assert "Pedir: Férias" in corpo


def test_a_semente_do_catalogo_tem_termos():
    """Sem sinônimos o assistente só acha quem já sabe o nome do item — e quem
    sabe o nome não precisa de assistente."""
    from workspace.catalogo_inicial import CATALOGO_INICIAL

    sem_termos = [
        spec["chave"] for spec in CATALOGO_INICIAL if not spec.get("termos")
    ]
    assert not sem_termos, f"itens sem termos: {sem_termos}"


def test_semente_aplicada_permite_intencao_realista():
    """Frases que uma pessoa de verdade digitaria, contra a semente de verdade."""
    from io import StringIO

    from django.core.management import call_command

    call_command("semear_catalogo", "--aplicar", stdout=StringIO())

    esperado = {
        "quero solicitar ferias": "ferias",
        "preciso de um notebook novo": "notebook",
        "gastei com uber, quero reembolso": "reembolso",
        "meu equipamento parou de funcionar": "equipamento-quebrado",
        "preciso de um capacete": "epi",
        "quero solicitar home office": "home-office",
        "minha nr-35 esta vencendo": "reciclagem-nr",
        "quero reservar um carro": "veiculo",
    }
    for frase, chave in esperado.items():
        acao = intencao.interpretar(frase)
        assert acao is not None, f"{frase!r} não virou ação"
        assert acao.item.chave == chave, f"{frase!r} → {acao.item.chave}, esperado {chave}"


def test_fragmento_curto_nao_vira_acao(catalogo):
    """O furo que a assimetria entre as direções fecha.

    No casamento reverso — a frase é fragmento do termo — o peso é sempre igual
    ao tamanho da frase, então a regra de cobertura passava SEMPRE. Digitar "ace"
    oferecia "Pedir: Acesso a sistema"; alguém no meio de digitar recebia uma
    ação como se tivesse pedido.
    """
    ItemCatalogo.objects.create(
        chave="acesso-sistema", nome="Acesso a sistema", termos=[],
        grupo=GrupoCatalogo.EQUIPAMENTO, dominio="ti.acesso", prazo_prometido_dias=1,
    )

    assert intencao.interpretar("ace") is None
    assert intencao.interpretar("aces") is None
    # Já com o verbo, é pedido explícito e a ação vale.
    assert intencao.interpretar("quero ace") is not None


def test_fragmento_que_cobre_o_termo_vira_acao(catalogo):
    """"ferias" é o item inteiro, não um pedaço."""
    assert intencao.interpretar("ferias").item.chave == "ferias"
    assert intencao.interpretar("notebook").item.chave == "notebook"


def test_termos_significativos_limpa_a_frase():
    """O que a busca de conteúdo consome."""
    assert intencao.termos_significativos("quero solicitar ferias") == ["ferias"]
    assert intencao.termos_significativos("politica de viagem") == ["politica", "viagem"]
    assert intencao.termos_significativos("quero") == []


@pytest.mark.parametrize(
    "frase",
    [
        "qual a politica de viagens",
        "quais sao as regras de reembolso",
        "onde fica o pop de instalacao",
        "quero entender o procedimento",
        "como funciona o reembolso",
        "quanto e a diaria",
    ],
)
def test_frases_de_leitura_nunca_viram_acao(catalogo, frase):
    """O erro mais caro daqui: quem queria a regra sai com um pedido aberto —
    e isso gera trabalho para outra pessoa."""
    assert intencao.interpretar(frase) is None, frase
