"""A defesa de território — uma linha por contrato.

A pergunta é "este contrato se defende sozinho?", e ela precisa de três
respostas que moravam em três lugares: quanto ele rende, o que o cliente acha
dele, e quando ele vence.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.services import resultados as svc

pytestmark = pytest.mark.django_db


def _papel(sufixo, permissoes):
    return f.papel(f"terr_{sufixo}", permissoes, escopo="global")


@pytest.fixture
def com_satisfacao(db):
    pessoa = f.pessoa("terr_tudo", nome="Diretoria")
    f.lotar(pessoa, centro_custo_codigo="1042")
    f.atribuir(
        pessoa,
        _papel("tudo", ["eco.ler.global", "eco.satisfacao.global"]),
        escopo="global",
    )
    return pessoa


@pytest.fixture
def sem_satisfacao(db):
    """Lê resultado e NÃO lê pesquisa de cliente — o Financeiro."""
    pessoa = f.pessoa("terr_eco", nome="Financeiro")
    f.lotar(pessoa, centro_custo_codigo="1042")
    f.atribuir(pessoa, _papel("eco", ["eco.ler.global"]), escopo="global")
    return pessoa


@pytest.fixture
def espelho(db):
    """Dois contratos: um saudável e um com detrator e margem baixa."""
    from resultados.models import (
        AvaliacaoCliente, CompetenciaResultado, Contrato, Fonte, StatusContrato,
    )

    hoje = timezone.localdate()

    def contrato(codigo, cliente, margem, vence_em, escopo=""):
        c = Contrato.objects.create(
            fonte=Fonte.PLATFORM, chave_externa=f"p-{codigo}", codigo=codigo,
            nome_cliente=cliente, servico="monitoramento", centro_custo="1042",
            valor_mensal=Decimal("1000"), status=StatusContrato.ATIVO,
            escopo=escopo,
            fim_vigencia=hoje + timedelta(days=vence_em),
        )
        for atras in range(svc.MESES_DA_DEFESA):
            total = hoje.year * 12 + (hoje.month - 1) - atras
            ano, mes = total // 12, total % 12 + 1
            CompetenciaResultado.objects.create(
                fonte=Fonte.SANKHYA, chave_externa=f"s-{codigo}-{ano}{mes:02d}",
                contrato=c, centro_custo="1042", ano=ano, mes=mes,
                receita_bruta=Decimal("1000"),
                margem_contribuicao=Decimal(margem),
            )
        return c

    saudavel = contrato("C-BOM", "Cliente Bom", "300", 900, "800 câmeras")
    frio = contrato("C-RUIM", "Cliente Frio", "50", 900)

    AvaliacaoCliente.objects.create(
        fonte=Fonte.PLATFORM, chave_externa="a-1", contrato=saudavel,
        data=hoje - timedelta(days=30), nota=10, classificacao="promotor",
    )
    AvaliacaoCliente.objects.create(
        fonte=Fonte.PLATFORM, chave_externa="a-2", contrato=frio,
        data=hoje - timedelta(days=30), nota=3, classificacao="detrator",
    )
    return {"bom": saudavel, "ruim": frio}


def _faixa(client, query=""):
    resposta = client.get(reverse("workspace:resultados") + query)
    for faixa in resposta.context["faixas"]:
        if faixa.chave == "territorio":
            return resposta, faixa
    return resposta, None


def _linha(faixa, codigo):
    return next(linha for linha in faixa.conteudo["linhas"] if linha.codigo == codigo)


# ── As três leituras numa linha ─────────────────────────────────────


def test_a_linha_traz_financeiro_pesquisa_e_prazo(client, espelho, com_satisfacao):
    client.force_login(com_satisfacao)

    _, faixa = _faixa(client)
    linha = _linha(faixa, "C-BOM")

    assert linha.rob_medio == Decimal("1000.00")
    assert linha.mc_media == Decimal("300.00")
    assert linha.margem_pct == Decimal("30.0")
    assert linha.pesquisas == 1 and linha.promotores == 1
    assert linha.fim_vigencia is not None


def test_o_escopo_do_contrato_vem_junto(client, espelho, com_satisfacao):
    """"800 câmeras" responde "que contrato é este?" sem sair da tela."""
    client.force_login(com_satisfacao)

    _, faixa = _faixa(client)

    assert "800 câmeras" in _linha(faixa, "C-BOM").escopo


def test_as_duas_janelas_sao_diferentes():
    """Pesquisa de cliente é esparsa: sete meses deixariam contrato sem nenhuma
    resposta — "sem amostra" onde existe opinião, só que mais antiga."""
    assert svc.MESES_DA_DEFESA == 7
    assert svc.MESES_DA_SATISFACAO == 12


def test_a_media_diz_QUANTOS_meses_entraram(client, espelho, com_satisfacao):
    """Três meses e sete meses produzem o mesmo "médio" com confianças muito
    diferentes."""
    client.force_login(com_satisfacao)

    _, faixa = _faixa(client)

    assert _linha(faixa, "C-BOM").meses == svc.MESES_DA_DEFESA


# ── O risco ─────────────────────────────────────────────────────────


def test_detrator_poe_o_contrato_em_risco(client, espelho, com_satisfacao):
    """Um contrato rentável com cliente insatisfeito se perde na renovação."""
    client.force_login(com_satisfacao)

    _, faixa = _faixa(client)

    assert _linha(faixa, "C-RUIM").em_risco
    assert not _linha(faixa, "C-BOM").em_risco


def test_margem_abaixo_do_minimo_tambem(client, espelho, com_satisfacao):
    """Um contrato querido que dá prejuízo não se sustenta."""
    from resultados.models import CompetenciaResultado

    CompetenciaResultado.objects.filter(contrato=espelho["bom"]).update(
        margem_contribuicao=Decimal("50")
    )
    client.force_login(com_satisfacao)

    _, faixa = _faixa(client)

    assert _linha(faixa, "C-BOM").em_risco


def test_o_corte_do_prazo_e_o_MESMO_da_faixa_de_vencimentos():
    """O primeiro corte foi de 365 dias e acendeu para a carteira INTEIRA —
    dezoito de dezoito. Alerta que sempre acende ensina a ignorar a coluna, e
    uma tabela em que todas as linhas estão em risco não ordena nada."""
    assert svc.FAIXAS_DE_VENCIMENTO[-1] == 180


def test_vencimento_proximo_poe_em_risco(client, espelho, com_satisfacao):
    from resultados.models import Contrato

    Contrato.objects.filter(codigo="C-BOM").update(
        fim_vigencia=timezone.localdate() + timedelta(days=30)
    )
    client.force_login(com_satisfacao)

    _, faixa = _faixa(client)

    assert _linha(faixa, "C-BOM").em_risco


def test_em_risco_vem_PRIMEIRO_e_o_maior_na_frente(client, espelho, com_satisfacao):
    """A defesa começa pelo que dói mais perder."""
    client.force_login(com_satisfacao)

    _, faixa = _faixa(client)

    assert faixa.conteudo["linhas"][0].codigo == "C-RUIM"


# ── O NPS ───────────────────────────────────────────────────────────


def test_o_nps_e_promotores_menos_detratores(client, espelho, com_satisfacao):
    client.force_login(com_satisfacao)

    _, faixa = _faixa(client)

    assert _linha(faixa, "C-BOM").nps == Decimal("100.0")
    assert _linha(faixa, "C-RUIM").nps == Decimal("-100.0")


def test_SEM_pesquisa_o_nps_e_None_e_nao_zero(client, espelho, com_satisfacao):
    """Zero seria lido como "metade promotor, metade detrator". Ausência quer
    dizer que ninguém perguntou — e a ação é outra."""
    from resultados.models import AvaliacaoCliente

    AvaliacaoCliente.objects.all().delete()
    client.force_login(com_satisfacao)

    _, faixa = _faixa(client)
    linha = _linha(faixa, "C-BOM")

    assert linha.sem_pesquisa
    assert linha.nps is None
    assert linha.satisfacao_pct is None


def test_pesquisa_FORA_da_janela_nao_conta(client, espelho, com_satisfacao):
    from resultados.models import AvaliacaoCliente

    AvaliacaoCliente.objects.all().update(
        data=timezone.localdate() - timedelta(days=500)
    )
    client.force_login(com_satisfacao)

    _, faixa = _faixa(client)

    assert _linha(faixa, "C-BOM").sem_pesquisa


# ── A permissão ─────────────────────────────────────────────────────


def test_quem_NAO_le_satisfacao_ve_a_tabela_SEM_as_colunas_de_pesquisa(
    client, espelho, sem_satisfacao
):
    """Quadro e satisfação saíram para as telas 16 e 17 porque dar o turnover de
    um centro de custo significava dar junto a margem de todo contrato. Aqui o
    movimento é o inverso e o risco é o mesmo: sem a barreira, a defesa de
    território reabriria por uma porta lateral o acoplamento que a separação
    desfez."""
    client.force_login(sem_satisfacao)

    resposta, faixa = _faixa(client)

    assert faixa.disponivel, "a tabela financeira continua inteira"
    assert not faixa.conteudo["com_satisfacao"]
    assert all(linha.pesquisas == 0 for linha in faixa.conteudo["linhas"])
    # E o dado nem chega ao HTML — esconder por CSS o deixaria lá.
    assert "Cliente Frio" in resposta.content.decode()
    assert "NPS" not in resposta.content.decode()


def test_quem_le_satisfacao_ve_as_colunas(client, espelho, com_satisfacao):
    client.force_login(com_satisfacao)

    resposta, faixa = _faixa(client)

    assert faixa.conteudo["com_satisfacao"]
    assert "NPS" in resposta.content.decode()


# ── O recorte ───────────────────────────────────────────────────────


def test_a_tabela_respeita_o_filtro_da_tela(client, espelho, com_satisfacao):
    """Uma consulta com o escopo original traria contratos que a tela não lista,
    e a tabela mostraria linha a mais que o bloco logo acima."""
    client.force_login(com_satisfacao)

    _, faixa = _faixa(client, "?contrato=C-BOM")

    assert [linha.codigo for linha in faixa.conteudo["linhas"]] == ["C-BOM"]


def test_sem_contrato_a_faixa_diz_o_que_falta(client, com_satisfacao, db):
    client.force_login(com_satisfacao)

    _, faixa = _faixa(client)

    assert not faixa.disponivel
    assert "contrato na carteira" in faixa.motivo
