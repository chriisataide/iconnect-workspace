"""Os atalhos da paleta — código da tela, prefixos e número do pedido.

O que estes testes protegem, em ordem de gravidade:

1. **O prefixo não amplia alcance.** `p:` é atalho para uma lista que a pessoa
   já pode abrir; para quem não pode, ele não existe — e não existe em silêncio,
   porque um grupo vazio contaria que há um diretório do outro lado da porta.
2. **O recorte continua no `WHERE`.** `s:` vira `origem__in`, não filtro depois
   de recuperar. Filtrar em Python devolveria o acervo inteiro para jogar fora,
   e o limite da consulta cortaria as linhas erradas.
3. **O código é um destino, não uma busca.** Quem digita "02.2" está indo, não
   procurando.
"""

from __future__ import annotations

import pytest

from identidade.tests import fabricas as f
from workspace.models import (
    Documento,
    GrupoCatalogo,
    ItemCatalogo,
    SituacaoDocumento,
    TipoDocumento,
)
from workspace.services.busca import buscar

pytestmark = pytest.mark.django_db


@pytest.fixture
def acervo():
    """Um serviço e um documento que casam com a MESMA palavra.

    De propósito: um prefixo que separasse coisas que já não se confundem não
    provaria nada. É com "reembolso" nos dois que `s:` e `d:` mostram serventia.
    """
    dono = f.pessoa("dono")
    f.lotar(dono)
    item = ItemCatalogo.objects.create(
        chave="reembolso", nome="Reembolso de despesa", grupo=GrupoCatalogo.DINHEIRO,
        dominio="fin.reembolso", prazo_prometido_dias=5,
        campos=[{"chave": "valor", "rotulo": "Valor", "obrigatorio": True}],
    )
    Documento.objects.create(
        slug="politica-reembolso", titulo="Política de reembolso",
        tipo=TipoDocumento.POP, situacao=SituacaoDocumento.VIGENTE, dono=dono,
        resumo="O que a empresa paga de volta", publico_alvo=["*"],
    )
    return item


# ── O código da tela ────────────────────────────────────────────────


def test_o_codigo_leva_a_tela():
    grupos = buscar("02.2")

    assert list(grupos) == ["Ir para"]
    (achado,) = grupos["Ir para"]
    assert achado.titulo == "Aprovações"
    assert achado.url == "/workspace/aprovacoes/"


def test_o_codigo_nao_traz_mais_nada_junto(acervo):
    """Um resultado só, e a busca para aí.

    Quem digitou o código já decidiu para onde vai; oferecer seis linhas junto
    devolve a ele a decisão que ele acabou de tomar.
    """
    assert list(buscar("00")) == ["Ir para"]


def test_o_codigo_e_resultado_e_nao_redirecionamento():
    """A busca devolve um destino para a pessoa escolher, e não navega sozinha.

    Navegar a cada tecla levaria embora quem está a meio de digitar "02.1" e
    passou por "02".
    """
    assert buscar("02")["Ir para"][0].url == "/workspace/servicos/"


# ── Os prefixos ─────────────────────────────────────────────────────


def test_prefixo_de_servico_deixa_o_documento_de_fora(acervo):
    grupos = buscar("s: reembolso")

    assert list(grupos) == ["Serviços"]
    assert [r.titulo for r in grupos["Serviços"]] == ["Reembolso de despesa"]


def test_prefixo_de_documento_deixa_o_servico_de_fora(acervo):
    grupos = buscar("d: reembolso")

    assert list(grupos) == ["Documentação"]
    assert [r.titulo for r in grupos["Documentação"]] == ["Política de reembolso"]


def test_sem_prefixo_a_busca_larga_traz_os_dois(acervo):
    grupos = buscar("reembolso")

    assert "Serviços" in grupos
    assert "Documentação" in grupos


def test_prefixo_nao_traz_aplicativo_nem_acao(acervo):
    """Prefixo é recorte, e aplicativo e ação não têm origem no índice.

    Deixá-los passar faria `d: financeiro` devolver o tile do Financeiro — que
    não é documento nenhum, e é justamente o que a pessoa acabou de excluir.
    """
    assert "Aplicativos" not in buscar("d: financeiro")
    assert "Ação" not in buscar("s: quero pedir reembolso")


def test_prefixo_desconhecido_e_texto_comum(acervo):
    """`x: reembolso` é tratado como texto, e não como erro.

    Falhar aqui ensinaria a evitar os dois-pontos — e há gente que escreve
    "assunto: reembolso" sem pensar em prefixo nenhum. O resultado é o mesmo da
    busca larga: o serviço E o documento.
    """
    grupos = buscar("x: reembolso")

    assert "Serviços" in grupos
    assert "Documentação" in grupos


def test_prefixo_sozinho_ainda_nao_e_busca(acervo):
    """`s:` sem termo cai no mesmo limite de qualquer consulta curta."""
    assert buscar("s:") == {}
    assert buscar("s: ") == {}


# ── `#` — o número do pedido ────────────────────────────────────────


def test_o_numero_acha_o_proprio_pedido(acervo):
    from workspace.services import catalogo as svc

    ana = f.pessoa("ana")
    f.lotar(ana)
    pedido = svc.solicitar(acervo, ana, {"valor": "120"})

    grupos = buscar(f"#{pedido.pk}", ana)

    assert [r.titulo for r in grupos["Minhas solicitações"]] == [
        f"Reembolso de despesa · #{pedido.pk}"
    ]


def test_o_numero_do_pedido_alheio_nao_aparece(acervo):
    """O recorte por sujeito continua no `WHERE`, com prefixo ou sem.

    O prefixo restringe a ORIGEM; ele nunca toca em quem pode ver o quê. Se
    tocasse, `#` seria um enumerador de pedidos da empresa inteira.
    """
    from workspace.services import catalogo as svc

    ana, bruno = f.pessoa("ana"), f.pessoa("bruno")
    f.lotar(ana)
    f.lotar(bruno)
    pedido = svc.solicitar(acervo, ana, {"valor": "120"})

    assert buscar(f"#{pedido.pk}", bruno) == {}


# ── `p:` — pessoas ──────────────────────────────────────────────────


def test_pessoas_para_quem_administra_papeis(acervo):
    quem_administra = f.pessoa("rh", nome="Rita Pires")
    f.lotar(quem_administra, cargo="Especialista de R.H.")
    f.atribuir(quem_administra, f.papel("rh", ["rh.admin.global"], escopo="global"))

    ana = f.pessoa("ana", nome="Ana Souza")
    f.lotar(ana, dep=f.departamento("OPS", "Operações"), cargo="Auxiliar")

    grupos = buscar("p: souza", quem_administra)

    (achada,) = grupos["Pessoas"]
    assert achada.titulo == "Ana Souza"
    assert achada.subtitulo == "Auxiliar · Operações"


def test_o_prefixo_de_pessoas_nao_existe_para_quem_nao_administra(acervo):
    """Para quem não administra papéis, `p:` NÃO é prefixo.

    `p: ana` cai na busca comum — sem grupo "Pessoas", sem grupo vazio e sem
    aviso. Avisar contaria que existe um diretório do outro lado da porta, que
    é a contagem que o índice foi desenhado para não vazar.
    """
    ana = f.pessoa("ana", nome="Ana Souza")
    f.lotar(ana, cargo="Auxiliar")

    grupos = buscar("p: souza", ana)

    assert "Pessoas" not in grupos


def test_anonimo_nao_tem_prefixo_de_pessoas(acervo):
    """O visitante do hub aberto não enxerga gente.

    Vale a pena testar separado de quem está logado e não administra: são dois
    caminhos diferentes na mesma função, e o do anônimo é o que sai antes de
    tocar o banco.
    """
    from django.contrib.auth.models import AnonymousUser

    f.lotar(f.pessoa("ana", nome="Ana Souza"), cargo="Auxiliar")

    assert "Pessoas" not in buscar("p: souza", AnonymousUser())
    assert "Pessoas" not in buscar("p: souza", None)


def test_pessoas_para_de_procurar_no_limite_do_grupo(acervo):
    """Sete pessoas casam, seis aparecem.

    O corte existe para a paleta continuar sendo uma lista que se lê de relance.
    Sem ele, digitar `p: silva` num organograma de duzentas pessoas devolveria
    uma tela de rolagem dentro de um campo de busca.
    """
    from workspace.services.busca import LIMITE_POR_GRUPO

    quem_administra = f.pessoa("rh", nome="Rita Pires")
    f.lotar(quem_administra)
    f.atribuir(quem_administra, f.papel("rh", ["rh.admin.global"], escopo="global"))

    for i in range(LIMITE_POR_GRUPO + 1):
        pessoa = f.pessoa(f"silva{i}", nome=f"Pessoa Silva {i}")
        f.lotar(pessoa, cargo="Auxiliar")

    assert len(buscar("p: silva", quem_administra)["Pessoas"]) == LIMITE_POR_GRUPO


def test_pessoas_nao_mostra_e_mail_nem_centro_de_custo(acervo):
    """O que aparece é nome, cargo e área — o que a tela de papéis já mostra.

    Grade com e-mail e documento, exportável por quem abrir a tela, é a primeira
    coisa que a leitura do benchmark marcou como não copiar.
    """
    quem_administra = f.pessoa("rh", nome="Rita Pires")
    f.lotar(quem_administra)
    f.atribuir(quem_administra, f.papel("rh", ["rh.admin.global"], escopo="global"))

    ana = f.pessoa("ana", nome="Ana Souza")
    f.lotar(ana, cargo="Auxiliar", centro_custo_codigo="1042")

    (achado,) = buscar("p: souza", quem_administra)["Pessoas"]

    assert "@" not in achado.titulo + achado.subtitulo
    assert "1042" not in achado.subtitulo
