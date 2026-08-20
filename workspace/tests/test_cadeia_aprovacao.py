"""A cadeia de aprovação com o teto real da empresa.

Decidido em 12/08/2026, substituindo o chute de R$ 10.000 que estava nas telas:

    até R$  50.000        gestor direto
    R$ 50.000 …  300.000  + diretoria
    acima de R$ 300.000   + sócios

Em 20/08/2026 o degrau da ÁREA saiu da cadeia. Ele não sumiu: virou a FILA —
quem atende conclui ou devolve com o motivo. Ver
`semear_regras_aprovacao` para o porquê, e `test_reenvio.py` para a volta que
faltava para devolver ser a resposta certa.

O que estes testes protegem é a **cumulatividade**. As faixas somam etapas, não
as substituem: um pedido de R$ 400.000 passa pelos três degraus, na ordem. Se
alguém trocar isso por faixas excludentes, um pedido grande passaria a ser
aprovado só pelos sócios — sem o gestor da área ter visto que a despesa sai do
orçamento dele.
"""

from __future__ import annotations

from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command

from identidade.models import Papel
from identidade.tests import fabricas as f
from workspace.models.aprovacao import RegraAprovacao, TipoAprovador
from workspace.services import aprovacao as apr

pytestmark = pytest.mark.django_db


@pytest.fixture
def cadeia():
    """A cadeia real, semeada pelo comando — não montada à mão no teste.

    Montar as regras à mão aqui testaria o motor contra uma cadeia inventada, e
    a que vai para produção nunca seria exercitada.
    """
    call_command("semear_papeis", "--aplicar", stdout=StringIO())
    call_command("semear_regras_aprovacao", "--aplicar", stdout=StringIO())


@pytest.fixture
def hierarquia():
    """Sócio → diretor → gerente → analista, com os papéis atribuídos.

    Mais `comprador`, que não está na linha de comando de ninguém: ele responde
    pela ÁREA. Ele continua aqui depois de 20/08 justamente para provar que a
    área NÃO aparece mais na cadeia — quem some sem deixar teste é quem volta
    por engano na onda seguinte.
    """
    socio, diretor, gerente, analista = (
        f.pessoa(n) for n in ("socio", "diretor", "gerente", "analista")
    )
    comprador = f.pessoa("comprador")
    f.lotar(comprador, centro_custo_codigo="1042")
    f.atribuir(comprador, Papel.objects.get(chave="compras"))
    f.lotar(socio, centro_custo_codigo="1000")
    f.lotar(diretor, gestor=socio, centro_custo_codigo="1000")
    f.lotar(gerente, gestor=diretor, centro_custo_codigo="1042")
    f.lotar(analista, gestor=gerente, centro_custo_codigo="1042")

    for username, chave in (
        ("socio", "socios"),
        ("diretor", "diretoria"),
        ("gerente", "gestor"),
        ("analista", "colaborador"),
    ):
        user = {"socio": socio, "diretor": diretor, "gerente": gerente, "analista": analista}[username]
        f.atribuir(user, Papel.objects.get(chave=chave))

    return {
        "socio": socio, "diretor": diretor, "gerente": gerente,
        "analista": analista, "comprador": comprador,
    }


def _etapas(valor, solicitante):
    solicitacao = apr.criar(
        dominio="com.requisicao",
        titulo=f"Compra de R$ {valor}",
        solicitante=solicitante,
        origem_id=f"teste-{valor}",
        valor=Decimal(valor),
        centro_custo_codigo="1042",
    )
    return solicitacao, list(solicitacao.etapas.order_by("ordem"))


# ── A cadeia semeada ────────────────────────────────────────────────


def test_comando_cria_os_degraus_por_valor(cadeia):
    """As faixas valem para TODO domínio (`*`), e são cumulativas."""
    regras = list(
        RegraAprovacao.objects.filter(ativa=True, dominio="*").order_by("ordem")
    )

    assert [r.valor_minimo for r in regras] == [
        Decimal("0"),
        Decimal("50000"),
        Decimal("300000"),
    ]
    assert regras[0].tipo == TipoAprovador.GESTOR_DIRETO
    assert regras[1].papel.chave == "diretoria"
    assert regras[2].papel.chave == "socios"


def test_o_degrau_da_area_saiu_da_cadeia(cadeia):
    """Ele existiu entre 17 e 20/08, e a razão de sair está no seeder.

    Resumo: com ele, a área tocava o mesmo pedido DUAS vezes — aprovava na
    bandeja e depois executava na fila. Quem pedia via "aguardando aprovação"
    depois de o gestor já ter aprovado, sem nada ter mudado de mãos.

    A revisão da área não desapareceu: virou a fila, onde quem atende conclui
    ou devolve com o motivo. O que tornou isso possível foi o reenvio —
    enquanto devolver era um beco, reprovar na bandeja era a única forma de
    dizer não sem prender o pedido para sempre.
    """
    assert not RegraAprovacao.objects.filter(ativa=True, ordem=15).exists()


def test_a_regra_retirada_e_desativada_e_nao_apagada(cadeia):
    """§60. O caminho de quem JÁ tinha o degrau no banco.

    Numa instalação nova a regra nem chega a existir. Numa que rodou o seeder
    entre 17 e 20/08, ela existe e é referenciada por `EtapaAprovacao` de todo
    pedido que passou por ela — apagá-la levaria junto a explicação de por que
    aquele pedido teve um degrau a mais em setembro.
    """
    antiga = RegraAprovacao.objects.create(
        dominio="com.",
        valor_minimo=Decimal("0"),
        tipo=TipoAprovador.PAPEL,
        papel=Papel.objects.get(chave="compras"),
        ordem=15,
    )

    call_command("semear_regras_aprovacao", "--aplicar", stdout=StringIO())

    antiga.refresh_from_db()
    assert antiga.ativa is False, "foi desativada"
    assert RegraAprovacao.objects.filter(pk=antiga.pk).exists(), "e continua no banco"


def test_semear_de_novo_nao_ressuscita_o_degrau(cadeia):
    """Reexecutável sem desfazer a decisão: rodar o seeder duas vezes não pode
    trazer de volta o que ele acabou de retirar."""
    call_command("semear_regras_aprovacao", "--aplicar", stdout=StringIO())

    assert not RegraAprovacao.objects.filter(ativa=True, ordem=15).exists()


# ── As faixas, cumulativas ──────────────────────────────────────────


def test_ate_50k_para_no_gestor(cadeia, hierarquia):
    """Abaixo do teto, um degrau só. A área revisa DEPOIS, na fila."""
    _, etapas = _etapas("49999.99", hierarquia["analista"])

    assert len(etapas) == 1
    assert etapas[0].aprovador == hierarquia["gerente"]


def test_no_limite_de_50k_a_diretoria_entra(cadeia, hierarquia):
    """`valor_minimo` é "alcança este mínimo" — R$ 50.000 exatos já sobem.

    Fronteira testada de propósito: é onde erro de `>` versus `>=` mora, e o
    caso de valor redondo é o mais comum na vida real.
    """
    _, etapas = _etapas("50000", hierarquia["analista"])

    assert len(etapas) == 2
    assert etapas[0].aprovador == hierarquia["gerente"]
    assert etapas[1].papel.chave == "diretoria"


def test_acima_de_300k_os_socios_entram_sem_tirar_ninguem(cadeia, hierarquia):
    """A regra central: faixas somam, não substituem."""
    _, etapas = _etapas("400000", hierarquia["analista"])

    assert len(etapas) == 3
    assert etapas[0].aprovador == hierarquia["gerente"]
    assert etapas[1].papel.chave == "diretoria"
    assert etapas[2].papel.chave == "socios"


def test_ordem_dos_degraus_e_de_baixo_para_cima(cadeia, hierarquia):
    """Gestor primeiro. Sócio aprovando antes do gestor da área é como a
    despesa some do orçamento de quem responde por ela."""
    _, etapas = _etapas("400000", hierarquia["analista"])

    assert [e.ordem for e in etapas] == sorted(e.ordem for e in etapas)
    assert etapas[0].aprovador == hierarquia["gerente"]


# ── Quem decide cada degrau ─────────────────────────────────────────


def test_gerente_nao_decide_a_etapa_por_papel_acima_dele(cadeia, hierarquia):
    """Etapa por PAPEL só é decidida por quem tem o papel — sem exceção.

    É a proteção que faz a faixa de valor significar algo: um gerente com
    `apr.aprovar.equipe` não pode assinar o degrau da diretoria.
    """
    solicitacao, _ = _etapas("400000", hierarquia["analista"])
    apr.decidir(solicitacao, hierarquia["gerente"], apr.Decisao.APROVAR)

    solicitacao.refresh_from_db()
    assert solicitacao.etapa_atual.papel.chave == "diretoria"
    with pytest.raises(apr.AprovacaoError):
        apr.decidir(solicitacao, hierarquia["gerente"], apr.Decisao.APROVAR)


def test_escopo_global_destrava_etapa_nominal_e_fica_auditado(cadeia, hierarquia):
    """O comportamento real do motor, documentado aqui porque surpreende.

    Etapa NOMINAL (gestor direto) pode ser decidida por quem tem `apr.aprovar`
    com escopo sobre o titular — sócio e diretoria têm escopo global. É o
    destravamento previsto para quando o titular desaparece sem delegação
    registrada, e o motor grava quem de fato assinou.

    A consequência a pesar: com escopo global, o degrau do gestor da área é
    contornável. Em empresa de seis pessoas isso é necessário; conforme cresce,
    vira questão de segregação de função. A trilha em `decidido_por` é o que
    torna a exceção auditável em vez de invisível.
    """
    solicitacao, _ = _etapas("400000", hierarquia["analista"])
    etapa_do_gerente = solicitacao.etapa_atual
    assert etapa_do_gerente.aprovador == hierarquia["gerente"]

    apr.decidir(solicitacao, hierarquia["socio"], apr.Decisao.APROVAR)

    etapa_do_gerente.refresh_from_db()
    assert etapa_do_gerente.aprovador == hierarquia["gerente"], "a etapa segue do titular"
    assert etapa_do_gerente.decidido_por == hierarquia["socio"], "e quem assinou fica registrado"


def test_a_cadeia_completa_de_400k(cadeia, hierarquia):
    solicitacao, _ = _etapas("400000", hierarquia["analista"])

    apr.decidir(solicitacao, hierarquia["gerente"], apr.Decisao.APROVAR)
    apr.decidir(solicitacao, hierarquia["diretor"], apr.Decisao.APROVAR)
    apr.decidir(solicitacao, hierarquia["socio"], apr.Decisao.APROVAR)

    solicitacao.refresh_from_db()
    assert solicitacao.situacao == "aprovada"


def test_gerente_nao_conclui_sozinho_acima_do_teto(cadeia, hierarquia):
    """Aprovar o próprio degrau não encerra o pedido — o valor exige mais."""
    solicitacao, _ = _etapas("60000", hierarquia["analista"])
    apr.decidir(solicitacao, hierarquia["gerente"], apr.Decisao.APROVAR)

    solicitacao.refresh_from_db()
    assert solicitacao.situacao == "aguardando"
    assert solicitacao.etapa_atual.papel.chave == "diretoria"


# ── A bandeja mostra só a etapa da vez ──────────────────────────────
#
# O bug que estes testes travam: todas as etapas nascem `pendente` de uma vez.
# Filtrar a bandeja por "pendente e minha" trazia degraus FUTUROS — a diretoria
# via um pedido de R$ 420.000 cuja etapa 1 ainda era do gerente, rotulado
# "Etapa 1 de 3 · você", com o botão Aprovar funcionando pela válvula de escopo
# global. A bandeja convidava ao atalho que a cadeia existe para impedir.
#
# Com um degrau só, isso nunca apareceu.


def test_diretoria_nao_ve_pedido_antes_da_vez(cadeia, hierarquia):
    _etapas("400000", hierarquia["analista"])

    fila = apr.pendentes_para(hierarquia["diretor"])

    assert not fila.exists(), "a diretoria vê pedido cuja etapa é do gerente"


def test_socios_nao_veem_pedido_antes_da_vez(cadeia, hierarquia):
    _etapas("400000", hierarquia["analista"])

    assert not apr.pendentes_para(hierarquia["socio"]).exists()


def test_o_pedido_aparece_para_cada_um_na_sua_vez(cadeia, hierarquia):
    """A fila anda: cada degrau só vê quando é dele."""
    solicitacao, _ = _etapas("400000", hierarquia["analista"])

    assert list(apr.pendentes_para(hierarquia["gerente"])) == [solicitacao]
    assert not apr.pendentes_para(hierarquia["diretor"]).exists()

    apr.decidir(solicitacao, hierarquia["gerente"], apr.Decisao.APROVAR)

    assert not apr.pendentes_para(hierarquia["gerente"]).exists()
    # A área NÃO entra na cadeia: ela recebe o pedido na fila, depois de
    # aprovado. Ver `test_reenvio.py`.
    assert not apr.pendentes_para(hierarquia["comprador"]).exists()
    assert list(apr.pendentes_para(hierarquia["diretor"])) == [solicitacao]
    assert not apr.pendentes_para(hierarquia["socio"]).exists()

    apr.decidir(solicitacao, hierarquia["diretor"], apr.Decisao.APROVAR)

    assert not apr.pendentes_para(hierarquia["diretor"]).exists()
    assert list(apr.pendentes_para(hierarquia["socio"])) == [solicitacao]


def test_o_resumo_da_bandeja_nao_represa_valor_de_outro_degrau(cadeia, hierarquia):
    """"Valor represado" tem de ser o que ESTA pessoa destrava.

    Somar pedido de degrau futuro infla o número e faz o aprovador achar que a
    fila dele é maior do que é.
    """
    _etapas("400000", hierarquia["analista"])
    _etapas("30000", hierarquia["analista"])

    resumo_gerente = apr.resumo_da_bandeja(hierarquia["gerente"])
    resumo_diretor = apr.resumo_da_bandeja(hierarquia["diretor"])

    assert resumo_gerente["quantidade"] == 2
    assert resumo_gerente["valor_represado"] == Decimal("430000")
    assert resumo_diretor["quantidade"] == 0
    assert resumo_diretor["valor_represado"] == Decimal("0")


def test_pendentes_para_continua_sendo_uma_consulta(cadeia, hierarquia, django_assert_num_queries):
    """O contrato da função: sem N+1 de autorização.

    O `Subquery` que corrige a etapa da vez não pode ter virado laço.
    """
    for valor in ("10000", "60000", "400000"):
        _etapas(valor, hierarquia["analista"])

    # papéis + delegações + a consulta de solicitações = 3
    with django_assert_num_queries(3):
        list(apr.pendentes_para(hierarquia["gerente"]))


# ── O papel `socios` ────────────────────────────────────────────────


def test_socios_nao_herda_poder_administrativo(cadeia):
    """Sócio decide sobre dinheiro; não opera o sistema.

    Papel de última instância com permissão administrativa vira superusuário de
    fato — e o degrau que existe para conferir passa a poder alterar o que
    confere.
    """
    socios = Papel.objects.get(chave="socios")
    diretoria = Papel.objects.get(chave="diretoria")

    assert "apr.aprovar.global" in socios.permissoes
    assert "ops.excecao.certificacao" not in socios.permissoes
    assert "ops.excecao.certificacao" in diretoria.permissoes
    for permissao in socios.permissoes:
        assert not permissao.endswith(".admin.global"), permissao
