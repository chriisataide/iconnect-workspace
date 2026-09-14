"""As telas 16 e 17 — o que saiu de dentro da 10, e por quê.

## O problema que a separação resolve

Quadro e jornada e Satisfação do cliente eram as faixas 6 e 7 da Apresentação de
Resultados. Enquanto moravam lá, elas exigiam `eco.ler` — a mesma permissão que
mostra a margem de cada contrato com o nome do cliente ao lado.

Consequência prática: dar o turnover de um centro de custo a quem responde por
gente significava dar junto o resultado financeiro da empresa. Ninguém fazia
isso, então as duas faixas existiam e eram lidas só pela diretoria.

## O que estes testes guardam

1. **Ninguém perdeu acesso.** Quem tinha `eco.ler` continua vendo as duas. Uma
   separação que retira algo em silêncio é pior do que não separar.
2. **Alguém ganhou.** `vendas` vê a 17 e **não** vê a 10 — é a linha que prova
   que a separação serviu para alguma coisa.
3. **As três recortam igual.** Elas compartilham `escopo_de`, e o gerente que vê
   só o centro de custo dele na 10 vê só o dele na 16.
4. **A 10 não mostra mais as duas faixas.** Senão a separação seria uma cópia.
"""

from __future__ import annotations

import re

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.services import resultados as svc

pytestmark = pytest.mark.django_db


def _papel(chave, permissoes):
    return f.papel(chave, permissoes, escopo="global")


@pytest.fixture
def so_gente(db):
    """Quem responde por gente e NÃO por dinheiro — o caso que não existia."""
    pessoa = f.pessoa("rh_puro", nome="Erre Agá")
    f.lotar(pessoa, uni=f.unidade())
    f.atribuir(pessoa, _papel("rh_puro", ["eco.pessoas.global"]), escopo="global")
    return pessoa


@pytest.fixture
def so_cliente(db):
    pessoa = f.pessoa("comercial", nome="Comercial")
    f.lotar(pessoa, uni=f.unidade())
    f.atribuir(
        pessoa, _papel("comercial", ["eco.satisfacao.global"]), escopo="global"
    )
    return pessoa


@pytest.fixture
def so_dinheiro(db):
    pessoa = f.pessoa("fin_puro", nome="Financeiro")
    f.lotar(pessoa, uni=f.unidade())
    f.atribuir(pessoa, _papel("fin_puro", ["eco.ler.global"]), escopo="global")
    return pessoa


# ── A separação serviu para alguma coisa ────────────────────────────


def test_quem_responde_por_gente_ve_o_quadro_e_nao_ve_o_dinheiro(client, so_gente):
    """A linha que justifica a onda inteira.

    Antes ela era impossível: a única permissão que abria o quadro abria junto a
    margem de todo contrato da empresa."""
    client.force_login(so_gente)

    assert client.get(reverse("workspace:quadro")).status_code == 200
    assert client.get(reverse("workspace:resultados")).status_code == 403
    assert client.get(reverse("workspace:satisfacao")).status_code == 403


def test_o_comercial_ve_a_avaliacao_e_so_ela(client, so_cliente):
    client.force_login(so_cliente)

    assert client.get(reverse("workspace:satisfacao")).status_code == 200
    assert client.get(reverse("workspace:resultados")).status_code == 403
    assert client.get(reverse("workspace:quadro")).status_code == 403


def test_quem_tem_so_o_dinheiro_nao_ganha_as_outras_de_brinde(client, so_dinheiro):
    """`eco.ler` sozinho abre a 10 e nada mais. Quem tem as três no produto
    real as tem porque `semear_papeis` concede as três, e não porque uma
    implica a outra."""
    client.force_login(so_dinheiro)

    assert client.get(reverse("workspace:resultados")).status_code == 200
    assert client.get(reverse("workspace:quadro")).status_code == 403
    assert client.get(reverse("workspace:satisfacao")).status_code == 403


# ── Ninguém perdeu acesso ───────────────────────────────────────────


@pytest.mark.parametrize("papel", ["diretoria", "socios", "rh", "financeiro"])
def test_quem_tinha_eco_ler_continua_vendo_as_duas(papel):
    """Contra o CATÁLOGO de papéis, e não contra a tela: é o catálogo que decide,
    e é ele que pode esquecer um papel numa próxima edição."""
    from identidade.papeis import PAPEIS_V1 as PAPEIS

    definicao = next(p for p in PAPEIS if p["chave"] == papel)
    permissoes = definicao["permissoes"]

    assert "eco.ler.global" in permissoes
    assert "eco.pessoas.global" in permissoes, f"{papel} perdeu o quadro"
    assert "eco.satisfacao.global" in permissoes, f"{papel} perdeu a avaliação"


def test_o_gestor_mantem_o_quadro_da_propria_equipe():
    """Ele via a faixa de pessoas dentro da tela 10, recortada ao centro de
    custo dele. Tirar isso seria uma regressão silenciosa."""
    from identidade.papeis import PAPEIS_V1 as PAPEIS

    gestor = next(p for p in PAPEIS if p["chave"] == "gestor")

    assert "eco.pessoas.departamento" in gestor["permissoes"]
    # Satisfação NÃO: ela é do comercial, e o gestor de operação nunca teve o
    # NPS recortado por contrato dele.
    assert not any(p.startswith("eco.satisfacao") for p in gestor["permissoes"])


def test_o_comercial_ganhou_a_avaliacao_no_catalogo():
    from identidade.papeis import PAPEIS_V1 as PAPEIS

    vendas = next(p for p in PAPEIS if p["chave"] == "vendas")

    assert "eco.satisfacao.global" in vendas["permissoes"]
    assert not any(p.startswith("eco.ler") for p in vendas["permissoes"])


# ── As três recortam igual ──────────────────────────────────────────


def test_as_tres_telas_usam_o_mesmo_recorte(so_gente):
    """`escopo_de` é uma função só, com a permissão por parâmetro.

    Três cópias dela seriam três lugares onde "o gerente vê só o centro de custo
    dele" está escrito — e no dia em que discordassem, uma delas vazaria sem
    deixar rastro."""
    import inspect

    fonte = inspect.getsource(svc._painel)

    assert "escopo_de(pessoa, permissao" in fonte
    for nome in ("painel", "painel_de_pessoas", "painel_de_satisfacao"):
        assert "_painel(" in inspect.getsource(getattr(svc, nome))


def test_o_gerente_ve_so_o_centro_de_custo_dele_no_quadro(client):
    unidade = f.unidade()
    pessoa = f.pessoa("gerente_quadro")
    f.lotar(pessoa, uni=unidade, centro_custo_codigo="1042")
    f.atribuir(
        pessoa,
        f.papel("ger_quadro", ["eco.pessoas.departamento"], escopo="departamento"),
        escopo="departamento",
    )
    client.force_login(pessoa)

    escopo = client.get(reverse("workspace:quadro")).context["escopo"]

    assert escopo.centros_custo == ("1042",)
    assert not escopo.tudo


# ── A 10 não mostra mais as duas ────────────────────────────────────


def test_a_tela_dez_perdeu_as_duas_faixas(client, so_dinheiro):
    """Se elas continuassem lá, a separação seria uma cópia — e o número
    apareceria em dois lugares que podem divergir."""
    client.force_login(so_dinheiro)

    # A carteira contextualiza o resultado antes do detalhamento contábil.
    chaves = [c for c, _ in svc.MONTADORES]
    assert chaves == ["contratos", "dinheiro", "contabil", "vencimentos", "projetos"]

    corpo = client.get(reverse("workspace:resultados")).content.decode()
    faixas = re.findall(r'aria-labelledby="([a-z]+)"', corpo)
    assert "pessoas" not in faixas
    assert "satisfacao" not in faixas


def test_a_tela_de_fontes_continua_listando_as_seis():
    """A pergunta da 99 é "de onde vem cada número do produto", e ela não mudou
    porque duas faixas passaram a morar em telas próprias."""
    chaves = {linha["chave"] for linha in svc.mapa_das_faixas()}

    assert {"dinheiro", "contratos", "vencimentos", "projetos",
            "pessoas", "satisfacao"} <= chaves


# ── Os filtros que não se aplicam não aparecem ──────────────────────


@pytest.mark.parametrize(
    "rota,fixture", [("workspace:quadro", "so_gente"), ("workspace:satisfacao", "so_cliente")]
)
def test_as_telas_irmas_nao_oferecem_filtro_de_contrato(client, rota, fixture, request):
    """Serviço, layer e "só deficitários" são atributos de CONTRATO. Aqui não há
    contrato por trás do número — e um filtro que a pessoa escolhe e que não muda
    nada faz ela concluir que a tela quebrou."""
    client.force_login(request.getfixturevalue(fixture))

    corpo = client.get(reverse(rota)).content.decode()

    # `name="mes"` desde 08/09/2026 — A1. "Competência" é palavra de
    # contabilidade, e esta barra é lida por quem não é do financeiro. O
    # `?competencia=` antigo continua sendo LIDO, e há teste disso em
    # `test_filtros_resultados.py`; o que a tela GERA usa o nome novo.
    assert 'name="mes"' in corpo, "o seletor de mês precisa continuar"
    # `name="area"` no lugar de `name="regional"` — A3. `regional` é o nome da
    # UNIDADE do organograma e serve à PERMISSÃO; ele saiu da barra porque
    # ninguém filtra digitando o nome de uma unidade, e porque oferecê-lo ali
    # convida a trocá-lo pela área comercial e quebrar o acesso do gerente.
    assert 'name="area"' in corpo, "o recorte por área precisa continuar"
    assert 'name="servico"' not in corpo
    assert 'name="layer"' not in corpo
    assert 'name="deficitario"' not in corpo


def test_a_avaliacao_nao_tem_botao_de_pdf(client, so_cliente):
    """O comentário do cliente não sai desta tela — e o PDF sai do prédio."""
    client.force_login(so_cliente)

    corpo = client.get(reverse("workspace:satisfacao")).content.decode()

    assert reverse("workspace:resultados_pdf") not in corpo


# ── O trilho e o endereçamento ──────────────────────────────────────


def test_as_duas_tem_codigo_de_tela(client, so_gente):
    from workspace import enderecamento as end

    codigos = {t.codigo: t.url for t in end.todas()}
    assert codigos["16"] == reverse("workspace:quadro")
    assert codigos["17"] == reverse("workspace:satisfacao")

    client.force_login(so_gente)
    ida = client.get("/workspace/ir/16/")
    assert ida.status_code == 302
    assert ida.headers["Location"] == reverse("workspace:quadro")


def test_o_trilho_mostra_a_tela_de_quem_so_tem_ela(client, so_cliente):
    """O grupo "Resultados da empresa" precisa aparecer para quem tem SÓ a 17 —
    senão o comercial ganha a permissão e não acha a porta."""
    client.force_login(so_cliente)

    corpo = client.get(reverse("workspace:satisfacao")).content.decode()

    assert "Satisfação do cliente" in corpo
    assert reverse("workspace:quadro") not in corpo
    assert reverse("workspace:resultados") not in corpo
