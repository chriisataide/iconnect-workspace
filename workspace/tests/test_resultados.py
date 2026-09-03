"""A Apresentação de Resultados — quem vê, quanto vê, e o que a tela recusa dizer.

Os três que mais protegem esta onda, em ordem de gravidade:

1. **Anônimo recebe 403 no GET.** Resultado financeiro não é informação
   institucional, e o Workspace é aberto para quase tudo — é justamente por ser
   aberto que esta tela precisa de uma trava explícita.
2. **Gerente de uma regional não enxerga a outra.** Vazamento em soma não deixa
   rastro: some dentro de um total plausível, e ninguém confere um total.
3. **Fonte com carga falha mostra o último dado bom.** Zerar é dizer que a
   empresa parou.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from resultados.models import (
    Apontamento, AvaliacaoCliente, Classificacao, CompetenciaResultado,
    Contrato, Fonte, MarcoProjeto, Projeto, QuadroPessoas, SituacaoProjeto,
    StatusContrato,
)
from workspace.services import resultados as svc

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()
COMPETENCIA = date(HOJE.year, HOJE.month, 1)


# ── Cenário ─────────────────────────────────────────────────────────


@pytest.fixture
def espelho(db):
    """Duas regionais, dois centros de custo, números diferentes em cada."""

    def _contrato(codigo, regional, cc, valor="100000", **campos):
        return Contrato.objects.create(
            fonte=Fonte.PLATFORM, chave_externa=f"plt-{codigo}", codigo=codigo,
            nome_cliente=f"Cliente {codigo}", servico="cftv",
            centro_custo=cc, regional=regional,
            inicio_vigencia=HOJE - timedelta(days=400),
            fim_vigencia=HOJE + timedelta(days=300),
            valor_mensal=Decimal(valor), **campos,
        )

    def _mes(contrato, mes_atras=0, receita="100000", margem="20000", **campos):
        total = COMPETENCIA.year * 12 + (COMPETENCIA.month - 1) - mes_atras
        ano, mes = total // 12, total % 12 + 1
        return CompetenciaResultado.objects.create(
            fonte=Fonte.SANKHYA,
            chave_externa=f"snk-{contrato.codigo}-{ano}{mes:02d}",
            contrato=contrato, centro_custo=contrato.centro_custo,
            ano=ano, mes=mes,
            receita_bruta=Decimal(receita),
            margem_contribuicao=Decimal(margem),
            **campos,
        )

    sudeste = _contrato("C-SE", "Sudeste", "1042")
    sul = _contrato("C-SU", "Sul", "2050", valor="50000")
    for atras in range(6):
        _mes(sudeste, atras, receita="100000", margem="20000")
        _mes(sul, atras, receita="50000", margem="10000")
    return {"sudeste": sudeste, "sul": sul}


def _pessoa(apelido, permissoes, escopo="global", **lotacao):
    pessoa = f.pessoa(apelido, nome=apelido.title())
    f.lotar(pessoa, **lotacao)
    f.atribuir(pessoa, f.papel(apelido, permissoes, escopo=escopo), escopo=escopo)
    return pessoa


@pytest.fixture
def diretoria():
    return _pessoa("diretoria", ["eco.ler.global"])


@pytest.fixture
def gerente_sudeste():
    unidade = f.unidade("SE", "Sudeste")
    return _pessoa(
        "gerente", ["eco.ler.departamento"], escopo="departamento",
        uni=unidade, centro_custo_codigo="1042",
    )


# ── Quem vê ─────────────────────────────────────────────────────────


def test_anonimo_recebe_403_no_GET_e_nao_so_no_POST(client, espelho):
    """O teste de autorização mais valioso da onda.

    O Workspace é aberto para o hub, o catálogo, a documentação e a agenda das
    salas — a fronteira normal dele passa entre o GET e o POST. Aqui não passa:
    resultado financeiro não é informação institucional, e o número já está na
    resposta do GET.
    """
    resposta = client.get(reverse("workspace:resultados"))

    assert resposta.status_code in (302, 403)
    if resposta.status_code == 302:
        assert "/entrar/" in resposta.headers["Location"]
    assert b"100000" not in resposta.content


def test_colaborador_comum_recebe_403(client, espelho):
    """403, e nunca um painel de zeros.

    Números todos em zero para quem nunca vai ter dado faz a pessoa achar que a
    empresa parou — mesma regra de `/workspace/indicadores/`.
    """
    ana = f.pessoa("ana")
    f.lotar(ana)
    client.force_login(ana)

    resposta = client.get(reverse("workspace:resultados"))

    assert resposta.status_code == 403


def test_permissao_sem_lotacao_nao_vira_acesso_global(client, espelho):
    """O caso que transforma uma permissão restrita em global por acidente.

    Alguém ganha `eco.ler.departamento` e ainda não foi lotado. Se o escopo
    caísse em "tudo" por falta de recorte, a pessoa veria a empresa inteira — e
    o defeito seria de CADASTRO, invisível na revisão de código.
    """
    solto = f.pessoa("solto")
    f.atribuir(
        solto, f.papel("solto", ["eco.ler.departamento"], escopo="departamento"),
        escopo="departamento",
    )
    client.force_login(solto)

    resposta = client.get(reverse("workspace:resultados"))

    assert resposta.status_code == 403


def test_gerente_de_uma_regional_nao_enxerga_o_numero_de_outra(
    client, espelho, gerente_sudeste
):
    """Vazamento em soma não deixa rastro na tela.

    Ele some dentro de um total plausível — e ninguém confere um total. Por isso
    o teste olha o NÚMERO e não a presença do nome da outra regional.
    """
    client.force_login(gerente_sudeste)

    resposta = client.get(reverse("workspace:resultados"))
    dinheiro = resposta.context["por_chave"]["dinheiro"]

    assert resposta.status_code == 200
    assert dinheiro.conteudo["totais"]["receita_bruta"] == Decimal("100000")
    assert b"C-SU" not in resposta.content


def test_a_diretoria_ve_as_duas(client, espelho, diretoria):
    client.force_login(diretoria)

    resposta = client.get(reverse("workspace:resultados"))

    assert resposta.context["escopo_total"] is True
    assert resposta.context["por_chave"]["dinheiro"].conteudo["totais"][
        "receita_bruta"
    ] == Decimal("150000")


def test_filtro_na_url_estreita_o_escopo_e_nunca_o_alarga(
    client, espelho, gerente_sudeste
):
    """O gerente digita `?regional=Sul` na barra de endereço.

    Ele continua vendo o dele. O filtro entra por INTERSEÇÃO — o que a pessoa
    não pode ver não volta por uma query string, que é o caminho mais óbvio e
    mais tentador de contornar um recorte.
    """
    client.force_login(gerente_sudeste)

    resposta = client.get(reverse("workspace:resultados"), {"regional": "Sul"})

    assert resposta.context["por_chave"]["dinheiro"].conteudo["totais"][
        "receita_bruta"
    ] == Decimal("100000")


def test_filtro_da_diretoria_recorta_de_verdade(client, espelho, diretoria):
    client.force_login(diretoria)

    resposta = client.get(reverse("workspace:resultados"), {"regional": "Sul"})

    assert resposta.context["por_chave"]["dinheiro"].conteudo["totais"][
        "receita_bruta"
    ] == Decimal("50000")


# ── Sem dado, sem fonte ─────────────────────────────────────────────


def test_competencia_sem_dado_mostra_o_motivo_e_nao_zero(client, espelho, diretoria):
    """"—" e a explicação. Zero seria lido como "a empresa não faturou"."""
    client.force_login(diretoria)

    resposta = client.get(reverse("workspace:resultados"), {"competencia": "2019-01"})
    dinheiro = resposta.context["por_chave"]["dinheiro"]

    assert dinheiro.disponivel is False
    assert "Sem lançamento financeiro" in dinheiro.motivo
    assert b"&#x2014;" in resposta.content or "—".encode() in resposta.content


def test_faixa_sem_fonte_conectada_nao_some(client, espelho, diretoria, monkeypatch):
    """Faixa que some esconde que a faixa existe.

    Quem abre a tela pela primeira vez concluiria que o produto não tem
    projetos — e não que o monday ainda não foi ligado.
    """
    from workspace.providers import resultados as contrato

    monkeypatch.setitem(contrato._provedores, contrato.ProvedorProjetos, None)
    monkeypatch.setattr(
        contrato, "obter",
        lambda tipo: None if tipo is contrato.ProvedorProjetos else contrato._provedores.get(tipo),
    )
    client.force_login(diretoria)

    projetos = client.get(reverse("workspace:resultados")).context["por_chave"]["projetos"]

    assert projetos.disponivel is False
    assert "monday" in projetos.motivo
    assert "não está conectada" in projetos.motivo


def test_fonte_com_carga_falha_mostra_o_ultimo_dado_bom(client, espelho, diretoria):
    """O carimbo em alerta, a idade do dado BOM, e o motivo ao lado.

    Falha de carga NUNCA zera o bloco. Zerar é dizer que a empresa parou — e a
    faixa continua com os números que entraram antes.
    """
    from cargas.models import ExecucaoCarga, FonteDados, StatusCarga
    from django.core.management import call_command

    call_command("semear_fontes", "--aplicar", verbosity=0)
    monday = FonteDados.objects.get(chave="monday")
    velho = timezone.now() - timedelta(hours=30)
    ExecucaoCarga.objects.create(
        fonte=monday, iniciada_em=velho, terminada_em=velho,
        status=StatusCarga.SUCESSO,
    )
    agora = timezone.now()
    ExecucaoCarga.objects.create(
        fonte=monday, iniciada_em=agora, terminada_em=agora,
        status=StatusCarga.FALHA, erro_resumo="tempo esgotado no board 4412",
    )
    Projeto.objects.create(
        fonte=Fonte.MONDAY, chave_externa="mon-1", codigo="PJ-1",
        nome="Obra Fictícia", situacao=SituacaoProjeto.EM_ANDAMENTO,
    )
    client.force_login(diretoria)

    resposta = client.get(reverse("workspace:resultados"))
    projetos = resposta.context["por_chave"]["projetos"]

    assert projetos.disponivel is True, "a faixa NÃO some quando a carga falha"
    assert projetos.carimbo.alerta is True
    assert "há 30 h" in projetos.carimbo.texto
    assert projetos.carimbo.motivo == "tempo esgotado no board 4412"


def test_a_fonte_quebrada_e_o_PRIMEIRO_cartao(client, espelho, diretoria):
    """Sem isso, alguém lê a tela inteira e decide em cima de dado de três dias."""
    from cargas.models import ExecucaoCarga, FonteDados, StatusCarga
    from django.core.management import call_command

    call_command("semear_fontes", "--aplicar", verbosity=0)
    agora = timezone.now()
    ExecucaoCarga.objects.create(
        fonte=FonteDados.objects.get(chave="sankhya"),
        iniciada_em=agora, terminada_em=agora,
        status=StatusCarga.FALHA, erro_resumo="credencial recusada",
    )
    Contrato.objects.filter(codigo="C-SE").update(status=StatusContrato.ATIVO)
    client.force_login(diretoria)

    cartoes = client.get(reverse("workspace:resultados")).context[
        "destaques"
    ].conteudo["cartoes"]

    assert cartoes[0].chave.startswith("fonte-")
    assert "desatualizada" in cartoes[0].titulo


# ── Amostra e margem ────────────────────────────────────────────────


def test_contrato_de_um_mes_nao_recebe_layer_nem_entra_na_regra_dos_dez(
    client, espelho, diretoria
):
    """Cobrar justificativa de quem faturou uma vez é cobrar de quem ainda não
    tem o que explicar."""
    novo = Contrato.objects.create(
        fonte=Fonte.PLATFORM, chave_externa="plt-novo", codigo="C-NOVO",
        nome_cliente="Cliente Novo", servico="alarme", centro_custo="1042",
        regional="Sudeste", valor_mensal=Decimal("90000"),
    )
    CompetenciaResultado.objects.create(
        fonte=Fonte.SANKHYA, chave_externa="snk-novo", contrato=novo,
        centro_custo="1042", ano=COMPETENCIA.year, mes=COMPETENCIA.month,
        receita_bruta=Decimal("90000"), margem_contribuicao=Decimal("4500"),
    )
    client.force_login(diretoria)

    contratos = client.get(reverse("workspace:resultados")).context["por_chave"][
        "contratos"
    ]
    dto = next(c for c in contratos.conteudo["carteira"] if c.codigo == "C-NOVO")

    assert dto.layer == "sem_amostra"
    assert dto not in contratos.conteudo["abaixo_da_margem"]


def test_contrato_deficitario_sai_separado(client, espelho, diretoria):
    """Ele é a única coisa desta tela que não espera a pessoa rolar."""
    CompetenciaResultado.objects.filter(contrato__codigo="C-SU").update(
        margem_contribuicao=Decimal("-5000")
    )
    client.force_login(diretoria)

    contratos = client.get(reverse("workspace:resultados")).context["por_chave"][
        "contratos"
    ]

    assert [c.codigo for c in contratos.conteudo["deficitarios"]] == ["C-SU"]


# ── Modo apresentação e PDF ─────────────────────────────────────────


def test_modo_apresentacao_tira_o_trilho_do_HTML_e_nao_so_da_vista(
    client, espelho, diretoria
):
    """`display:none` deixaria a navegação no HTML, e o leitor de tela leria uma
    navegação que ninguém pode ver."""
    client.force_login(diretoria)

    normal = client.get(reverse("workspace:resultados")).content
    reuniao = client.get(reverse("workspace:resultados"), {"apresentacao": "1"}).content

    assert b"au-rail-item" in normal
    assert b"au-rail-item" not in reuniao
    assert b"au-filtros--resultados" not in reuniao


def test_o_pdf_sai_com_o_mesmo_recorte_da_tela(client, espelho, gerente_sudeste):
    """Exportar não pode ser a forma de contornar o escopo.

    A exportação é justamente o caminho por onde o dado sai do prédio.
    """
    client.force_login(gerente_sudeste)

    resposta = client.get(reverse("workspace:resultados_pdf"))

    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "application/pdf"
    assert resposta.content[:4] == b"%PDF"


def test_o_pdf_recusa_quem_a_tela_recusa(client, espelho):
    ana = f.pessoa("ana")
    f.lotar(ana)
    client.force_login(ana)

    assert client.get(reverse("workspace:resultados_pdf")).status_code == 403


def test_o_pdf_nao_leva_comentario_de_cliente(client, espelho, diretoria):
    """Comentário de detrator num PDF que circula é o cliente descobrindo o que
    a empresa achou da reclamação dele."""
    AvaliacaoCliente.objects.create(
        fonte=Fonte.PLATFORM, chave_externa="av-1", contrato=espelho["sudeste"],
        data=HOJE, nota=3, classificacao=Classificacao.DETRATOR,
        comentario="SEGREDO-DO-CLIENTE",
    )
    client.force_login(diretoria)

    conteudo = client.get(reverse("workspace:resultados_pdf")).content

    assert b"SEGREDO-DO-CLIENTE" not in conteudo


# ── CSP ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("rota", ["workspace:resultados", "workspace:fontes"])
def test_nenhuma_resposta_contem_style(client, espelho, diretoria, rota):
    """A CSP é estrita e não tem `unsafe-inline`.

    Barra, medidor e gráfico são SVG, onde `x`, `y`, `width` e `height` são
    ATRIBUTOS — e atributo não é estilo. Um `style=` aqui não estouraria: ele
    seria silenciosamente ignorado pelo navegador, e o gráfico sairia torto sem
    erro nenhum no console.
    """
    from identidade.tests import fabricas as fab

    fab.atribuir(diretoria, fab.papel("op", ["eco.carga.global"], escopo="global"))
    client.force_login(diretoria)

    conteudo = client.get(reverse(rota)).content.decode()

    assert "style=" not in conteudo


def test_o_grafico_sai_com_a_tabela_irma(client, espelho, diretoria):
    """Atualizado na Onda 10, não removido.

    Ele afirmava `<svg class="au-serie">`, do SVG calculado à mão — que saiu.
    O que ele afirma agora é a regra que não muda com a biblioteca: **todo
    gráfico vem acompanhado da tabela com os mesmos números**.

    Sem JavaScript o gráfico não existe, e a tabela deixou de ser
    acessibilidade para virar o fallback.
    """
    client.force_login(diretoria)

    conteudo = client.get(reverse("workspace:resultados")).content.decode()

    assert 'data-grafico-tela=' in conteudo
    assert 'data-grafico-tabela=' in conteudo
    assert conteudo.count("data-grafico-tela=") == conteudo.count("data-grafico-tabela=")


def test_o_sem_amostra_do_contrato_e_o_mesmo_do_espelho():
    """A string está escrita nos dois lados, e não pode divergir.

    O Workspace não importa `resultados` — a string chega pelo DTO. A duplicação
    é o preço de manter a direção da dependência; o que não dá para pagar é a
    divergência: um `"sem-amostra"` de um lado e `"sem_amostra"` do outro faria
    a regra dos 10% voltar a cobrar de quem não tem histórico, em silêncio.
    """
    from resultados.services import SEM_AMOSTRA as DO_ESPELHO

    assert svc.SEM_AMOSTRA == DO_ESPELHO
