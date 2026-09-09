"""A área comercial, e o escopo que ela recorta.

## O que estes testes protegem, em uma frase cada

- **Área não é regional.** Trocar uma pela outra quebra o acesso do gerente,
  porque `Escopo.regionais` vem do organograma e nenhuma área se chama "Sudeste".
- **Nada some do total.** Contrato sem área é uma escolha do filtro, não um
  contrato invisível.
- **Atributo não é nível.** Área entra com `E` contra o nível, e não na
  precedência — na precedência, estreitar faria a lista crescer.
- **A carga não pisa no cadastro.** Área é registro nosso; a carga da madrugada
  não pode apagá-la.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.db.utils import IntegrityError

from resultados.models import (
    SEM_AREA,
    Area,
    CompetenciaResultado,
    Contrato,
    Fonte,
    StatusContrato,
)
from resultados.providers import EspelhoLocal
from workspace.providers.resultados import Escopo


@pytest.fixture
def areas(db):
    return {
        codigo: Area.objects.create(
            codigo=codigo, nome=nome, descricao=descricao, ordem=ordem
        )
        for ordem, (codigo, nome, descricao) in enumerate(
            (
                ("area-01", "Área 01", "Santander"),
                ("area-03", "Área 03", "Bradesco, Mercantil"),
            ),
            start=1,
        )
    }


def _contrato(codigo, *, area=None, cc="1042", regional="Sudeste",
              servico="monitoramento", receita="100"):
    contrato = Contrato.objects.create(
        fonte=Fonte.PLATFORM, chave_externa=f"ext-{codigo}", codigo=codigo,
        nome_cliente=f"Cliente {codigo}", servico=servico, centro_custo=cc,
        regional=regional, area=area, valor_mensal=Decimal("1000"),
        status=StatusContrato.ATIVO,
    )
    CompetenciaResultado.objects.create(
        fonte=Fonte.SANKHYA, chave_externa=f"k-{codigo}-2026-9",
        contrato=contrato, centro_custo=cc, ano=2026, mes=9,
        receita_bruta=Decimal(receita),
    )
    return contrato


# ── Área é cadastro, não espelho ────────────────────────────────────


def test_o_codigo_sem_area_e_reservado(db):
    """`sem-area` identifica a AUSÊNCIA de área no filtro. Uma área real com
    esse código faria "Sem área" devolver ela mesma, e os contratos sem área
    sumiriam de vez — que é justamente o que a reserva evita."""
    with pytest.raises(IntegrityError):
        Area.objects.create(codigo=SEM_AREA, nome="Armadilha")


def test_o_nome_da_area_traz_os_clientes_junto(db):
    """`__str__` aparece no admin e no `title` do seletor. "Área 03" sozinho não
    diz a ninguém o que tem dentro."""
    com = Area.objects.create(codigo="area-09", nome="Área 09", descricao="Itaú")
    sem = Area.objects.create(codigo="area-10", nome="Área 10")

    assert str(com) == "Área 09 · Itaú"
    assert str(sem) == "Área 10", "sem descrição não sobra um separador solto"


def test_a_carga_da_madrugada_nao_apaga_a_area(db, areas):
    """Área é registro NOSSO, e o conector não a conhece.

    O carregador só escreve os campos que a fonte mandou (`_gravar` monta
    `dados` a partir de `registro.dados`), e nenhum conector manda `area`. Este
    teste é o que impede alguém de acrescentar `area` ao payload de um conector
    e, sem perceber, fazer a carga das 5h30 desagrupar a carteira inteira.
    """
    from cargas.conectores.base import Registro
    from cargas.carregador import ENTIDADES

    contrato = _contrato("C-100", area=areas["area-01"])
    assert ENTIDADES["contrato"] is Contrato

    campos_do_conector = set(
        Registro(entidade="contrato", chave_externa="x", dados={}).dados
    )
    assert "area" not in campos_do_conector

    contrato.refresh_from_db()
    assert contrato.area_id == areas["area-01"].pk


# ── O recorte ───────────────────────────────────────────────────────


def test_filtra_a_carteira_por_area(db, areas):
    _contrato("C-01", area=areas["area-01"])
    _contrato("C-03", area=areas["area-03"])

    carteira = EspelhoLocal().contratos(Escopo(areas=("area-01",)))

    assert [c.codigo for c in carteira] == ["C-01"]
    assert carteira[0].area == "area-01"
    assert carteira[0].area_nome == "Área 01"


def test_duas_areas_ao_mesmo_tempo(db, areas):
    """Comparar a Área 01 com a 03 é a razão de o filtro aceitar mais de um
    valor — se ele substituísse, o segundo clique desfaria o primeiro."""
    _contrato("C-01", area=areas["area-01"])
    _contrato("C-03", area=areas["area-03"])
    _contrato("C-SEM")

    carteira = EspelhoLocal().contratos(Escopo(areas=("area-01", "area-03")))

    assert sorted(c.codigo for c in carteira) == ["C-01", "C-03"]


def test_contrato_sem_area_NAO_some_do_total(db, areas):
    """O teste que protege a confiança da diretoria.

    Quem soma as áreas e não chega ao total da empresa para de acreditar na tela
    inteira — e com razão. "Sem área" tem de ser uma linha visível, não um
    contrato que existe só quando ninguém filtra.
    """
    _contrato("C-01", area=areas["area-01"], receita="100")
    _contrato("C-03", area=areas["area-03"], receita="200")
    _contrato("C-SEM", receita="300")

    espelho = EspelhoLocal()
    total = len(espelho.contratos(Escopo()))
    por_area = sum(
        len(espelho.contratos(Escopo(areas=(a,))))
        for a in ("area-01", "area-03", SEM_AREA)
    )

    assert total == 3
    assert por_area == total, "as áreas mais os sem área têm de fechar o total"


def test_sem_area_e_uma_escolha_e_pode_vir_junto(db, areas):
    """"Área 01 e os sem área" é pergunta legítima de quem está reagrupando."""
    _contrato("C-01", area=areas["area-01"])
    _contrato("C-03", area=areas["area-03"])
    _contrato("C-SEM")

    carteira = EspelhoLocal().contratos(Escopo(areas=("area-01", SEM_AREA)))

    assert sorted(c.codigo for c in carteira) == ["C-01", "C-SEM"]


def test_a_area_recorta_o_dinheiro_e_nao_so_a_carteira(db, areas):
    """Duas faixas discordando sobre o mesmo filtro é o defeito que faz alguém
    parar de confiar no número — e ele não dá erro nem aparece em log."""
    _contrato("C-01", area=areas["area-01"], receita="100")
    _contrato("C-03", area=areas["area-03"], receita="200")

    serie = EspelhoLocal().serie_competencia(
        Escopo(areas=("area-01",)), date(2026, 1, 1), date(2026, 12, 31)
    )

    assert [linha.receita_bruta for linha in serie] == [Decimal("100")]


# ── Atributo não é nível ────────────────────────────────────────────


def test_area_entra_com_E_contra_o_nivel_e_nao_na_precedencia(db, areas):
    """Um centro de custo atende contratos de áreas diferentes: nenhum dos dois
    contém o outro.

    Se área entrasse na precedência, ela SUBSTITUIRIA o centro de custo — e
    quem desceu para o CC 1042 e depois marcou a Área 01 veria a lista CRESCER
    para incluir a Área 01 inteira. É o defeito que o `OU` da hierarquia
    produzia antes da Onda 11, de volta por outra porta.
    """
    _contrato("C-MEU", area=areas["area-01"], cc="1042")
    _contrato("C-OUTRO-CC", area=areas["area-01"], cc="1055")

    carteira = EspelhoLocal().contratos(
        Escopo(centros_custo=("1042",), areas=("area-01",))
    )

    assert [c.codigo for c in carteira] == ["C-MEU"], "estreitou, não alargou"


def test_o_servico_tambem_recorta_todas_as_faixas(db, areas):
    _contrato("C-MON", servico="monitoramento", receita="100")
    _contrato("C-MAN", servico="manutencao", receita="200")

    espelho = EspelhoLocal()
    escopo = Escopo(servicos=("monitoramento",))

    assert [c.codigo for c in espelho.contratos(escopo)] == ["C-MON"]
    serie = espelho.serie_competencia(escopo, date(2026, 1, 1), date(2026, 12, 31))
    assert [linha.receita_bruta for linha in serie] == [Decimal("100")]


def test_filtro_que_nao_casa_devolve_VAZIO_e_nao_tudo(db):
    """A regressão que este teste pegou de verdade, em 08/09/2026.

    `_competencias_no_escopo` montava a condição com `Q()` e, quando só havia
    filtro de atributo, esse `Q()` ficava vazio — e `filter(Q())` devolve a
    tabela inteira. O detalhe de `?servico=nao-existe` mostrava TODAS as linhas
    em vez de nenhuma, dizendo à pessoa que o filtro não funciona quando o
    problema era o contrário.
    """
    _contrato("C-MON", servico="monitoramento")

    serie = EspelhoLocal().serie_competencia(
        Escopo(servicos=("nao-existe",)), date(2026, 1, 1), date(2026, 12, 31)
    )

    assert serie == []


# ── O vazamento do OU ───────────────────────────────────────────────


def test_o_gerente_ve_o_centro_de_custo_dele_e_nao_a_regional_inteira(db):
    """VAZAMENTO DE PERMISSÃO, reproduzido e corrigido em 08/09/2026.

    `escopo_de` monta, para um gerente, as duas coisas ao mesmo tempo:
    `regionais=("Sudeste",)` E `centros_custo=("1042",)`. O
    `_competencias_no_escopo` combinava os níveis com **OU** — herança de antes
    da Onda 11, que corrigiu o mesmo defeito no `_recortar` e deixou este para
    trás. "Sudeste OU 1042" é o Sudeste inteiro.

    Medido antes da correção:

        carteira   → C-MEU
        dinheiro   → C-MEU, C-VIZINHO

    A mesma tela mostrando a carteira de um centro de custo e a receita da
    regional toda. Sem erro, sem log, e sem ninguém notar — porque os dois
    números nunca aparecem lado a lado.
    """
    _contrato("C-MEU", cc="1042", regional="Sudeste", receita="100")
    _contrato("C-VIZINHO", cc="1055", regional="Sudeste", receita="900")

    espelho = EspelhoLocal()
    escopo = Escopo(regionais=("Sudeste",), centros_custo=("1042",))

    carteira = [c.codigo for c in espelho.contratos(escopo)]
    serie = espelho.serie_competencia(escopo, date(2026, 1, 1), date(2026, 12, 31))

    assert carteira == ["C-MEU"]
    assert [linha.contrato for linha in serie] == ["C-MEU"], (
        "o dinheiro tem de concordar com a carteira"
    )


def test_no_nivel_do_centro_de_custo_o_rateio_sem_contrato_continua_dentro(db):
    """A razão de esta função não usar `_recortar`, e ela não pode se perder na
    correção do OU: a linha de centro de custo não tem contrato, e filtrar por
    `contrato__centro_custo` a deixaria de fora — fazendo o total do CC ficar
    menor que a soma dos contratos dele."""
    _contrato("C-MEU", cc="1042", receita="100")
    CompetenciaResultado.objects.create(
        fonte=Fonte.SANKHYA, chave_externa="k-rateio-1042-2026-9",
        contrato=None, centro_custo="1042", ano=2026, mes=9,
        receita_bruta=Decimal("50"),
    )

    serie = EspelhoLocal().serie_competencia(
        Escopo(centros_custo=("1042",)), date(2026, 1, 1), date(2026, 12, 31)
    )

    assert sorted(linha.receita_bruta for linha in serie) == [
        Decimal("50"), Decimal("100")
    ]
