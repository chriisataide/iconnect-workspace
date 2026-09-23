"""Os grupos recolhíveis do trilho — e por que só um abre.

## O que foi medido antes de mexer

    colaborador    11 itens no trilho   maior grupo: Consultar (6)
    gestor         15 itens             maior grupo: Consultar (6)
    diretoria      28 itens             maior grupo: ACOMPANHAR (14)

O trilho já é filtrado por permissão, e para quase todo mundo ele é curto. O que
estava errado era UM grupo: "Acompanhar" tinha virado o depósito de tudo que não
é pedir, atender ou aprovar.

## O que estes testes guardam

1. **O HTML fecha.** `<details>` aberto e não fechado aninha os grupos seguintes
   DENTRO do anterior — e some com metade do trilho quando um `{% if %}` de
   permissão é falso. O navegador não reclama; ele desenha errado.
2. **Um grupo aberto, e é o da tela.** Todos abertos desfaz a mudança; nenhum
   aberto esconde onde a pessoa está.
3. **Sem JavaScript.** `<details>` é nativo. Um trilho que só abre com JS é um
   trilho que não abre quando o bundle falha.
"""

from __future__ import annotations

import re

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace import navegacao

pytestmark = pytest.mark.django_db


def _trilho(client, url: str) -> str:
    corpo = client.get(url).content.decode()
    return corpo[corpo.index("au-rail"):] if "au-rail" in corpo else ""


def _abertos(corpo: str) -> list[str]:
    # `[^>]*?` entre a classe e o `open`: o `<details>` ganhou `data-grupo` para
    # o JS que lembra os grupos abertos, e uma regex que exigia os dois grudados
    # passou a devolver lista vazia — ou seja, o teste reprovava por causa de si
    # mesmo, e não do trilho.
    #
    # O nome agora vem de `.au-rail-grupo-nome` e não do texto solto do
    # `<summary>`: o rótulo ganhou um ícone ao lado — é por ele que se reconhece
    # o grupo com o trilho recolhido —, e `([^<]*)` depois do `<summary>` passou
    # a capturar a string vazia antes do `<svg>`. Mesmo defeito de antes, outra
    # causa: a regex descrevia a marcação em vez do dado.
    return re.findall(
        r'<details class="au-rail-secao"[^>]*?\bopen\b[^>]*>'
        r'\s*<summary class="au-rail-grupo">.*?'
        r'<span class="au-rail-grupo-nome">([^<]*)</span>',
        corpo,
        re.S,
    )


@pytest.fixture
def diretor(db):
    """Alguém com permissão em TODOS os grupos — o pior caso do trilho, e o
    único perfil em que a divisão de "Acompanhar" se prova."""
    pessoa = f.pessoa("dir_trilho", nome="Diretor")
    f.lotar(pessoa, uni=f.unidade())
    f.atribuir(
        pessoa,
        f.papel(
            "diretoria_trilho",
            [
                "eco.ler.global", "eco.carga.global", "ind.ler.global",
                "orc.ler.global", "met.ler.global",
                "pes.papel.global", "pes.ler.global",
                "com.publicar.global", "log.frota.ler.global",
                "log.estoque.ler.global", "apr.decidir.global",
            ],
            escopo="global",
        ),
        escopo="global",
    )
    return pessoa


# ── O HTML fecha ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url",
    ["/workspace/meu-dia/", "/workspace/servicos/", "/workspace/documentacao/"],
)
def test_o_trilho_fecha_todos_os_grupos_que_abre(client, diretor, url):
    """Este teste nasceu de um defeito real, e o defeito custou uma hora.

    A abertura de um grupo guardado ficou DENTRO do `{% if %}` de permissão e o
    fechamento FORA — um off-by-one, porque o `grep` conta a partir de 1 e o
    `list.insert` a partir de 0. Para quem TEM a permissão o HTML fechava
    certo; para quem não tem, sobrava um `</details>` que fechava a barra
    inteira mais cedo.

    O navegador não reclama disso. A suíte reclamou de um jeito que não parecia
    HTML: um teste de cadeia de aprovação passou a girar a 100% de CPU, e o
    ponto de travamento mudava a cada execução."""
    client.force_login(diretor)

    corpo = _trilho(client, url)

    assert corpo.count("<details") == corpo.count("</details>")


def test_o_trilho_fecha_tambem_para_quem_tem_pouca_permissao(client):
    """O caso que o teste acima não pega: colaborador comum, com três grupos."""
    pessoa = f.pessoa("ana")
    f.lotar(pessoa, uni=f.unidade())
    client.force_login(pessoa)

    corpo = _trilho(client, "/workspace/meu-dia/")

    assert corpo.count("<details") == corpo.count("</details>")
    assert corpo.count("<details") >= 3


# ── Um grupo aberto, e é o da tela ──────────────────────────────────


@pytest.mark.parametrize(
    "url,grupo",
    [
        ("/workspace/meu-dia/", "Hoje"),
        ("/workspace/documentacao/", "Consultar"),
        ("/workspace/servicos/", "Pedir"),
        ("/workspace/resultados/", "Resultados da empresa"),
    ],
)
def test_abre_o_grupo_da_tela_e_so_ele(client, diretor, url, grupo):
    client.force_login(diretor)

    assert _abertos(_trilho(client, url)) == [grupo]


@pytest.mark.parametrize(
    "rota,grupo",
    [
        ("excecoes", "resultados"),
        ("planos", "resultados"),
        ("orcamento", "resultados"),
        ("fontes", "resultados"),
        ("pessoas", "gestao"),
        ("publicacoes", "gestao"),
        ("universidade", "consultar"),
        ("aprovacoes", "aprovar"),
        ("frota", "atender"),
    ],
)
def test_o_mapa_manda_cada_rota_para_o_grupo_certo(rota, grupo):
    """Contra o MAPA e não contra a tela: estas telas devolvem 403 para quem
    não tem a permissão específica, e num 403 não há trilho para conferir. O
    mapa é o que decide, e é o que pode errar em silêncio."""
    assert navegacao.GRUPO_POR_ROTA[rota] == grupo


def test_rota_desconhecida_nao_derruba_o_trilho():
    """Rota nova sem entrada no mapa abre grupo nenhum — e não estoura.

    O caso inaceitável seria um `KeyError` numa tela nova: o trilho está em toda
    tela do produto, e uma exceção aqui derruba TODAS elas de uma vez."""
    class Requisicao:
        path = "/workspace/tela-que-ainda-nao-existe/"
        resolver_match = None

    assert navegacao.grupo_aberto(Requisicao()) == {"grupo_aberto": ""}


def test_fora_do_workspace_o_processador_nao_faz_nada():
    class Requisicao:
        path = "/admin/"
        resolver_match = None

    assert navegacao.grupo_aberto(Requisicao()) == {}


# ── A divisão do "Acompanhar" ───────────────────────────────────────


def test_acompanhar_virou_dois_grupos(client, diretor):
    """Catorze itens sob um verbo genérico. "Resultados da empresa" é o que a
    empresa produziu; "Gestão" é como ela se organiza."""
    client.force_login(diretor)

    corpo = _trilho(client, "/workspace/meu-dia/")
    # O nome do grupo mora em `.au-rail-grupo-nome` desde que o rótulo ganhou
    # ícone ao lado — ver a nota em `_abertos()`.
    grupos = re.findall(r'<span class="au-rail-grupo-nome">([^<]*)</span>', corpo)

    assert "Acompanhar" not in grupos
    assert "Resultados da empresa" in grupos
    assert "Gestão" in grupos


def test_nenhum_grupo_passa_de_oito_itens(client, diretor):
    """O limite não é estético: é o tamanho em que uma lista deixa de ser lida
    de relance e passa a ser varrida item a item."""
    client.force_login(diretor)

    corpo = _trilho(client, "/workspace/meu-dia/")
    # `au-rail-secao` e não `<details>` solto: o sino da topbar também é um
    # `<details>`, e ele não tem grupo nenhum dentro.
    for grupo in re.findall(
        r'<details class="au-rail-secao".*?</details>', corpo, re.S
    ):
        nome = re.search(r'au-rail-grupo">([^<]*)<', grupo).group(1)
        itens = len(re.findall(r'class="au-rail-item', grupo))
        assert itens <= 8, f"{nome} tem {itens} itens"


# ── Sem JavaScript ──────────────────────────────────────────────────


def test_o_trilho_nao_depende_de_javascript(client, diretor):
    """`<details>` é nativo. Se alguém trocar por um botão com `onclick`, a CSP
    o bloqueia em silêncio e o trilho para de abrir — sem erro na tela."""
    client.force_login(diretor)

    corpo = _trilho(client, "/workspace/meu-dia/")

    assert "<details" in corpo
    assert "onclick" not in corpo
    assert "data-abre-grupo" not in corpo


def test_toda_rota_do_trilho_esta_no_mapa_de_grupos():
    """Uma rota fora do mapa não quebra — ela abre grupo nenhum, e a pessoa
    perde a única pista de onde está. Este teste é o que impede isso de virar o
    normal sem ninguém decidir."""
    from pathlib import Path

    trilho = (
        Path(__file__).resolve().parent.parent
        / "templates/workspace/_rail_servicos.html"
    ).read_text(encoding="utf-8")

    rotas = set(re.findall(r"workspace:([a-z_]+)", trilho))
    faltando = sorted(rotas - set(navegacao.GRUPO_POR_ROTA))

    assert not faltando, f"rotas do trilho sem grupo: {faltando}"
