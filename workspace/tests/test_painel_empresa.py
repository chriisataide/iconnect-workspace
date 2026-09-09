"""O painel da empresa — §I1 e §I2.

A camada acima de `/resultados/`: só entra o que responde pergunta de empresa, e
todo bloco leva ao detalhe com o filtro aplicado.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.services import painel_empresa as svc

pytestmark = pytest.mark.django_db


@pytest.fixture
def diretoria(db):
    pessoa = f.pessoa("dir_painel", nome="Diretoria")
    f.lotar(pessoa, centro_custo_codigo="1042")
    f.atribuir(
        pessoa,
        f.papel(
            "dir_painel_papel",
            ["eco.ler.global", "eco.pessoas.global", "eco.satisfacao.global"],
            escopo="global",
        ),
        escopo="global",
    )
    return pessoa


@pytest.fixture
def sem_escopo(db):
    return f.pessoa("sem_escopo_painel", nome="Estagiário")


@pytest.fixture
def espelho(db):
    """Dois contratos em duas áreas, dois meses e o mesmo mês do ano anterior."""
    from resultados.models import (
        Area, CompetenciaResultado, Contrato, Fonte, StatusContrato,
    )

    areas = {
        codigo: Area.objects.create(codigo=codigo, nome=nome, ordem=i)
        for i, (codigo, nome) in enumerate(
            (("area-01", "Área 01"), ("area-03", "Área 03")), start=1
        )
    }
    hoje = timezone.localdate()

    def contrato(codigo, area, valor, cliente):
        c = Contrato.objects.create(
            fonte=Fonte.PLATFORM, chave_externa=f"p-{codigo}", codigo=codigo,
            nome_cliente=cliente, servico="monitoramento", centro_custo="1042",
            area=areas[area], valor_mensal=Decimal(valor),
            status=StatusContrato.ATIVO,
            fim_vigencia=hoje + timedelta(days=20) if codigo == "C-1" else None,
        )
        for atras, mc in ((0, "300"), (1, "250"), (12, "200")):
            total = hoje.year * 12 + (hoje.month - 1) - atras
            ano, mes = total // 12, total % 12 + 1
            CompetenciaResultado.objects.create(
                fonte=Fonte.SANKHYA, chave_externa=f"s-{codigo}-{ano}{mes:02d}",
                contrato=c, centro_custo="1042", ano=ano, mes=mes,
                receita_bruta=Decimal("1000"), impostos=Decimal("150"),
                custo_direto=Decimal("550"), margem_contribuicao=Decimal(mc),
                ebitda=Decimal("100"),
            )
        return c

    contrato("C-1", "area-01", "800", "Banco Meridional")
    contrato("C-2", "area-03", "200", "Rede Aurora")


# ── Permissão ───────────────────────────────────────────────────────


def test_anonimo_cai_no_login(client):
    resposta = client.get(reverse("workspace:painel"))

    assert resposta.status_code == 302
    assert "/entrar" in resposta["Location"] or "login" in resposta["Location"]


def test_quem_nao_tem_escopo_recebe_403_e_nao_tela_zerada(client, sem_escopo):
    """Números todos em zero para quem nunca vai ter dado faz a pessoa achar que
    a empresa parou."""
    client.force_login(sem_escopo)

    assert client.get(reverse("workspace:painel")).status_code == 403


def test_a_diretoria_abre(client, diretoria, espelho):
    client.force_login(diretoria)

    assert client.get(reverse("workspace:painel")).status_code == 200


# ── 1 · Os cinco números, com DUAS comparações ──────────────────────


def test_todo_numero_tem_as_duas_comparacoes(diretoria, espelho):
    """Uma só induz a erro num negócio com sazonalidade: dezembro contra
    novembro diz uma coisa, dezembro contra dezembro diz outra."""
    painel = svc.montar(diretoria)
    por_chave = {n.chave: n for n in painel.numeros}

    for chave in ("receita", "margem", "ebitda"):
        assert por_chave[chave].contra_mes is not None, chave
        assert por_chave[chave].contra_ano is not None, chave


def test_a_margem_varia_em_PONTOS_e_nao_em_percentual(diretoria, espelho):
    """A margem já é percentual, e "caiu 12%" sobre 19% é ambíguo entre 7 e
    16,7 — duas leituras que levam a decisões diferentes."""
    painel = svc.montar(diretoria)
    margem = next(n for n in painel.numeros if n.chave == "margem")

    # 30% agora contra 25% no mês anterior → 5 pontos, e não 20%.
    assert margem.contra_mes == Decimal("5.0")


def test_sem_base_a_variacao_e_None_e_nao_zero(diretoria, db):
    """`0%` seria lido como "não mudou", que é outra coisa."""
    painel = svc.montar(diretoria)

    assert all(n.contra_mes is None for n in painel.numeros)


def test_todo_numero_LEVA_ao_detalhe(diretoria, espelho):
    """Indicador que não leva a lugar nenhum é decoração."""
    painel = svc.montar(diretoria)

    assert all(n.url for n in painel.numeros)
    assert all("/workspace/resultados/" in n.url for n in painel.numeros)


# ── 2 · O semáforo por área ─────────────────────────────────────────


def test_uma_linha_por_area_e_o_clique_leva_ao_filtro(diretoria, espelho):
    painel = svc.montar(diretoria)

    assert [a.nome for a in painel.areas] == ["Área 01", "Área 03"]
    assert "area=area-01" in painel.areas[0].url


def test_a_margem_da_area_e_MEDIANA_e_nao_media():
    """Uma área com um contrato muito grande e vários pequenos teria a média
    puxada pelo maior, e o farol diria que ela está bem quando a maioria dos
    contratos dela não está."""
    assert svc._mediana([Decimal("1"), Decimal("2"), Decimal("99")]) == Decimal("2")
    assert svc._mediana([]) is None


def test_o_farol_traz_a_PALAVRA_junto(diretoria, espelho):
    """Num farol a cor é a única coisa que existe — sem o rótulo ele não
    comunica para quem não a distingue."""
    painel = svc.montar(diretoria)

    assert all(a.farol.rotulo for a in painel.areas)


# ── 4 · Dependência de cliente ──────────────────────────────────────


def test_a_dependencia_soma_os_maiores_e_traz_o_farol(diretoria, espelho):
    painel = svc.montar(diretoria)

    # Dois clientes, ambos entram nos cinco maiores → 100%.
    assert painel.dependencia["percentual"] == Decimal("100.0")
    assert painel.dependencia["farol"].situacao == "critico"
    assert len(painel.dependencia["clientes"]) == 2


def test_depender_MENOS_e_estar_melhor(diretoria, espelho):
    """`maior_melhor=False`: aqui o farol inverte, e 20% é bom enquanto 80% é
    crítico. Sem isso a tela diria que depender de um cliente só é ótimo."""
    from workspace.graficos import series as g

    bom = g.farol(
        Decimal("20"), critico=svc.DEPENDENCIA_CRITICA,
        atencao=svc.DEPENDENCIA_ATENCAO, maior_melhor=False,
    )
    ruim = g.farol(
        Decimal("80"), critico=svc.DEPENDENCIA_CRITICA,
        atencao=svc.DEPENDENCIA_ATENCAO, maior_melhor=False,
    )

    assert bom.situacao == "bom" and ruim.situacao == "critico"


def test_carteira_vazia_nao_produz_dependencia(diretoria, db):
    assert svc.montar(diretoria).dependencia == {}


# ── 5 a 8 · Os blocos por permissão ─────────────────────────────────


def test_as_faixas_de_vencimento_nao_contam_o_mesmo_contrato_duas_vezes(
    diretoria, espelho
):
    """Um contrato que vence em 20 dias está dentro de 30, de 60 e de 90.
    Somando as faixas sem descontar, ele apareceria três vezes e o valor em
    risco seria o triplo do real."""
    painel = svc.montar(diretoria)

    assert sum(f["quantos"] for f in painel.vencimentos) == 1


def test_sem_permissao_de_pessoas_o_bloco_NAO_aparece(client, db, espelho):
    """O painel é da empresa, mas quadro e jornada são de outra gente — a
    permissão que separa as telas 16 e 17 vale aqui também."""
    pessoa = f.pessoa("so_eco", nome="Financeiro")
    f.lotar(pessoa, centro_custo_codigo="1042")
    f.atribuir(
        pessoa,
        f.papel("so_eco_papel", ["eco.ler.global"], escopo="global"),
        escopo="global",
    )

    painel = svc.montar(pessoa)

    assert painel.pessoas == {}
    assert painel.satisfacao == {}
    assert painel.numeros, "o resto do painel continua"


def test_projeto_CONCLUIDO_nao_conta_como_atrasado(diretoria, db):
    """Contá-lo poria no painel um projeto que terminou em março."""
    from resultados.models import Fonte, Projeto

    ontem = timezone.localdate() - timedelta(days=10)
    Projeto.objects.create(
        fonte=Fonte.MONDAY, chave_externa="m-1", codigo="P-1", nome="Feito",
        situacao="concluido", prazo=ontem,
    )
    Projeto.objects.create(
        fonte=Fonte.MONDAY, chave_externa="m-2", codigo="P-2", nome="Atrasado",
        situacao="em_andamento", prazo=ontem,
    )

    painel = svc.montar(diretoria)

    assert painel.projetos["total"] == 1
    assert painel.projetos["atrasados"] == 1


# ── §I2 · As regras da tela ─────────────────────────────────────────


def test_a_tela_tem_NO_MAXIMO_nove_blocos():
    """A décima informação sempre parece necessária, e é ela que faz o CEO
    parar de abrir a tela."""
    campos = [c for c in svc.Painel.__dataclass_fields__ if c != "competencia"]

    assert len(campos) <= 9, campos


def test_o_modo_apresentacao_existe_aqui_tambem(client, diretoria, espelho):
    client.force_login(diretoria)

    corpo = client.get(
        reverse("workspace:painel") + "?apresentacao=1"
    ).content.decode()

    assert "au-rail" not in corpo, "o trilho some em apresentação"


def test_o_rodape_leva_a_tela_de_fontes(client, diretoria, espelho):
    """Quem abre o painel quer o número; quem duvida do número quer a
    procedência — nesta ordem."""
    client.force_login(diretoria)

    corpo = client.get(reverse("workspace:painel")).content.decode()

    assert reverse("workspace:fontes") in corpo


def test_indicadores_continua_sendo_o_SLA(client, diretoria):
    """Trocar a rota da tela existente para dar o nome bonito a esta quebraria
    link, favorito e teste para ganhar uma palavra."""
    client.force_login(diretoria)

    assert client.get(reverse("workspace:indicadores")).status_code in (200, 403)
    assert reverse("workspace:indicadores") != reverse("workspace:painel")


def test_o_trilho_separa_as_duas_pelo_ROTULO(client, diretoria, espelho):
    client.force_login(diretoria)

    corpo = client.get(reverse("workspace:painel")).content.decode()

    assert "Painel da empresa" in corpo
