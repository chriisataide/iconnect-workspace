"""Orçamento anual e revisão — a onda que começou decidindo a posse.

Os três que mais protegem esta onda:

1. **O teto vigente não muda sem revisão.** Antes desta onda, alguém com
   `is_staff` editava `CentroCusto.orcamento_mensal` e ninguém ficava sabendo.
   Agora mudar exige motivo, autor e delta — e tudo fica no histórico.
2. **Os dois orçados não se fundem.** O teto de operação é nosso; o orçado
   contábil é do Sankhya. Nenhum código escolhe vencedor: os dois aparecem, a
   diferença aparece, e a divergência vira ocorrência.
3. **A grade é de quem responde pelo centro de custo.** 403 e nunca uma grade de
   zeros — uma grade zerada faz a pessoa achar que a empresa não gastou nada.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.urls import reverse

from financas.models import (
    CentroCusto,
    Lancamento,
    LinhaOrcamento,
    OrcamentoAnual,
    RevisaoOrcamento,
    SituacaoOrcamento,
)
from identidade.tests import fabricas as f
from workspace.models.orcamento import Compromisso, SituacaoCompromisso
from workspace.providers import orcamento as contrato
from workspace.services import orcamento as svc

pytestmark = pytest.mark.django_db

ANO = 2026


# ── Cenário ─────────────────────────────────────────────────────────


@pytest.fixture
def centro(db):
    return CentroCusto.objects.create(
        codigo="1042", nome="Operação SP", orcamento_mensal=Decimal("10000")
    )


@pytest.fixture
def vigente(centro):
    """Um orçamento anual em vigor, doze meses de R$ 10.000."""
    call_command("semear_orcamento", "--aplicar", "--ano", str(ANO), verbosity=0)
    return OrcamentoAnual.objects.get(centro_custo=centro, ano=ANO)


def _pessoa_com(apelido, chave_do_papel, permissoes, cc="1042"):
    pessoa = f.pessoa(apelido, nome=apelido.title())
    f.lotar(pessoa, centro_custo_codigo=cc)
    f.atribuir(
        pessoa,
        f.papel(chave_do_papel, list(permissoes), escopo="global"),
        escopo="global",
    )
    return pessoa


@pytest.fixture
def financeiro(db):
    return _pessoa_com(
        "financeiro", "financeiro",
        ["fin.orcamento.ler.global", "fin.orcamento.revisar.global"],
    )


@pytest.fixture
def gestor(db):
    """Lê o próprio centro de custo e NÃO revisa."""
    return _pessoa_com("gestora", "gestor", ["fin.orcamento.ler.departamento"])


# ── 1. O teto vigente não muda sem revisão ──────────────────────────


def test_o_teto_vigente_nao_muda_sem_revisao(vigente, financeiro):
    """O teste que justifica a onda.

    O contrato não oferece atalho: `montar_orcamento` recusa em vigente, e a
    única porta é a revisão — que exige motivo e grava o delta.
    """
    provider = contrato.obter()

    montou = provider.montar_orcamento("1042", ANO, {7: Decimal("99999")})

    assert montou is False
    assert vigente.do_mes(7) == Decimal("10000")


def test_a_revisao_muda_o_teto_e_deixa_motivo_autor_e_delta(vigente, financeiro):
    revisao = svc.revisar(
        "1042", ANO, {7: Decimal("15000"), 9: Decimal("-8000")},
        motivo="Reajuste do contrato entrou em julho; obra escorregou de setembro.",
        quem=financeiro,
    )

    vigente.refresh_from_db()
    assert revisao.numero == 1
    assert revisao.total == Decimal("7000")
    assert vigente.do_mes(7) == Decimal("25000")
    assert vigente.do_mes(9) == Decimal("2000")
    assert vigente.do_mes(8) == Decimal("10000"), "mês não citado fica como está"

    registro = RevisaoOrcamento.objects.get()
    assert registro.autor_id == financeiro.pk
    assert "Reajuste do contrato" in registro.motivo
    assert registro.deltas == {"7": "15000", "9": "-8000"}


def test_a_revisao_sem_motivo_e_recusada(vigente, financeiro):
    """Sem motivo, a revisão vira uma edição com data — e o motivo é a metade
    que sobrevive a quem a fez."""
    with pytest.raises(svc.OrcamentoError, match="exige o motivo"):
        svc.revisar("1042", ANO, {7: Decimal("1")}, motivo="   ", quem=financeiro)

    assert RevisaoOrcamento.objects.count() == 0


def test_as_revisoes_sao_numeradas_e_acumulam(vigente, financeiro):
    """É por este número que a empresa conversa — "a segunda revisão do 1042"."""
    svc.revisar("1042", ANO, {7: Decimal("5000")}, motivo="primeira", quem=financeiro)
    segunda = svc.revisar(
        "1042", ANO, {7: Decimal("2000")}, motivo="segunda", quem=financeiro
    )

    vigente.refresh_from_db()
    assert segunda.numero == 2
    assert vigente.do_mes(7) == Decimal("17000"), "os deltas somam"
    assert [r.numero for r in svc.revisoes("1042", ANO)] == [1, 2]


def test_revisao_sem_delta_nenhum_nao_grava(vigente, financeiro):
    """Revisão vazia seria uma linha no histórico dizendo que nada mudou."""
    assert svc.revisar("1042", ANO, {}, motivo="mudei de ideia", quem=financeiro) is None
    assert svc.revisar(
        "1042", ANO, {7: Decimal("0")}, motivo="zero é nada", quem=financeiro
    ) is None
    assert RevisaoOrcamento.objects.count() == 0


def test_revisao_em_ano_sem_orcamento_vigente_nao_grava(centro, financeiro):
    assert svc.revisar(
        "1042", ANO, {7: Decimal("1000")}, motivo="não há o que revisar",
        quem=financeiro,
    ) is None


def test_montar_e_vigorar_e_o_caminho_do_rascunho(centro, financeiro):
    """Rascunho é onde se monta o ano; vigente é onde se para de escrever."""
    provider = contrato.obter()

    assert provider.montar_orcamento("1042", ANO, {m: 1000 for m in range(1, 13)})
    orcamento = OrcamentoAnual.objects.get(centro_custo=centro, ano=ANO)
    assert orcamento.situacao == SituacaoOrcamento.RASCUNHO
    assert orcamento.editavel is True

    assert svc.vigorar("1042", ANO, financeiro) is True
    orcamento.refresh_from_db()
    assert orcamento.vigente is True
    assert orcamento.vigorou_por_id == financeiro.pk
    assert orcamento.editavel is False


def test_rascunho_sem_linha_nao_vigora(centro, financeiro):
    """Orçamento vigente sem linha é um teto de zero disfarçado de teto ausente:
    a bandeja mostraria 0% de folga o ano todo."""
    OrcamentoAnual.objects.create(centro_custo=centro, ano=ANO)

    assert svc.vigorar("1042", ANO, financeiro) is False


def test_vigorar_o_que_ja_esta_em_vigor_nao_faz_nada(vigente, financeiro):
    assert svc.vigorar("1042", ANO, financeiro) is False


# ── 2. Os dois orçados não se fundem ────────────────────────────────


class EspelhoDeMentira:
    """O orçado CONTÁBIL, do Sankhya. Diferente do nosso de propósito."""

    def __init__(self, custo_orcado=Decimal("12000")):
        self.custo_orcado = custo_orcado

    def serie_competencia(self, escopo, de, ate):
        from workspace.providers import resultados as res

        return [
            res.CompetenciaDTO(
                procedencia=res.Procedencia(fonte="sankhya", chave_externa="cc-1042"),
                centro_custo="1042",
                ano=ANO,
                mes=mes,
                custo_orcado=self.custo_orcado,
            )
            for mes in range(1, 13)
        ]


@pytest.fixture
def espelho():
    from workspace.providers import resultados as res

    guardados = dict(res._provedores)
    res.limpar()
    falso = EspelhoDeMentira()
    res._provedores[res.ProvedorResultadoFinanceiro] = falso
    yield falso
    res.limpar()
    res._provedores.update(guardados)


def test_os_dois_orcados_aparecem_lado_a_lado_e_nao_se_fundem(vigente, espelho):
    """Nenhum código escolhe vencedor. Escolher dentro de um `if` teria razão até
    o dia em que não tivesse, e ninguém saberia dizer quando esse dia foi."""
    confronto = svc.confronto_com_o_espelho("1042", ANO)

    assert len(confronto) == 12
    julho = next(c for c in confronto if c["mes"] == 7)
    assert julho["operacao"] == Decimal("10000"), "o nosso teto de operação"
    assert julho["contabil"] == Decimal("12000"), "o orçado contábil do Sankhya"
    assert julho["diferenca"] == Decimal("-2000")


def test_a_grade_usa_o_nosso_teto_e_nao_o_do_espelho(vigente, espelho):
    """A grade é do teto de OPERAÇÃO — é ele que a bandeja usa para dizer se um
    pedido cabe. Misturar o contábil aqui faria as duas telas discordarem sobre
    o mesmo mês."""
    grade = svc.grade_anual("1042", ANO)

    assert all(linha.orcado == Decimal("10000") for linha in grade)


@pytest.fixture
def sem_espelho():
    """O registro de resultados vazio — a instalação sem integração.

    O app `resultados` se registra no `ready()`, então "sem espelho" não é o
    estado natural do processo de teste: ele precisa ser montado, e devolvido —
    senão o teste seguinte encontra o contrato vazio e culpa o app errado.
    """
    from workspace.providers import resultados as res

    guardados = dict(res._provedores)
    res.limpar()
    yield
    res.limpar()
    res._provedores.update(guardados)


def test_sem_espelho_conectado_o_confronto_e_vazio_e_nao_erro(vigente, sem_espelho):
    """Estado normal, e não falha: a instalação sem integração continua sendo uma
    instalação válida."""
    assert svc.confronto_com_o_espelho("1042", ANO) == []


def test_a_regra_de_conciliacao_ligou_nesta_onda(db):
    """Ela nasceu na Onda 4 registrada e DESLIGADA, com o texto "só passa a valer
    quando o orçamento existir aqui dentro". Agora ele existe."""
    from workspace import excecoes as reg
    from workspace.models.excecao import RegraExcecao

    call_command("semear_regras_excecao", "--aplicar", verbosity=0)
    regra = RegraExcecao.objects.get(chave="cc-sem-orcado-e-o-inverso")

    assert regra.exige_plano is True, "conciliação de código cobra plano"
    assert reg.regra_de("cc-sem-orcado-e-o-inverso") is not None, "tem avaliador"


def test_a_conciliacao_acha_as_duas_direcoes(vigente, espelho, financeiro):
    """As duas na mesma regra porque são o MESMO defeito — um cadastro que não
    bate — e separá-las faria alguém corrigir metade."""
    from workspace import excecoes as reg

    CentroCusto.objects.create(codigo="9999", nome="Só no orçamento")
    contrato.obter().montar_orcamento("9999", ANO, {m: 500 for m in range(1, 13)})
    contrato.obter().vigorar_orcamento("9999", ANO, financeiro)

    avaliador = reg.regra_de("cc-sem-orcado-e-o-inverso")
    chaves = {o.chave for o in avaliador.avaliar(0)}

    assert "cc-orcamento:9999" in chaves, "orçado aqui e desconhecido no ERP"


def test_a_conciliacao_nao_avalia_sem_as_duas_pontas(vigente, sem_espelho):
    """Uma ponta só produziria uma lista em que tudo é divergente."""
    from workspace import excecoes as reg

    avaliador = reg.regra_de("cc-sem-orcado-e-o-inverso")

    assert avaliador.disponivel() is False, "sem espelho, não avalia"


def test_a_conciliacao_nao_avalia_sem_o_dominio_financeiro(vigente, espelho):
    """A outra ponta: sem `financas`, não há o lado do orçamento."""
    from workspace import excecoes as reg

    guardado = contrato.obter()
    contrato.limpar()
    try:
        avaliador = reg.regra_de("cc-sem-orcado-e-o-inverso")
        assert avaliador.disponivel() is False
    finally:
        if guardado is not None:
            contrato.registrar(guardado)


# ── 3. Quem vê o quê ────────────────────────────────────────────────


def test_a_grade_e_de_quem_responde_pelo_centro_de_custo(vigente, gestor, client):
    client.force_login(gestor)

    resposta = client.get(reverse("workspace:orcamento"))

    assert resposta.status_code == 200
    assert b"1042" in resposta.content


def test_o_gestor_ve_so_o_proprio_centro_de_custo(vigente, gestor):
    CentroCusto.objects.create(codigo="2000", nome="Outra operação")

    codigos = [c.codigo for c in svc.centros_visiveis(gestor)]

    assert codigos == ["1042"]


def test_o_financeiro_ve_todos(vigente, financeiro):
    CentroCusto.objects.create(codigo="2000", nome="Outra operação")

    codigos = {c.codigo for c in svc.centros_visiveis(financeiro)}

    assert codigos == {"1042", "2000"}


def test_quem_nao_responde_por_centro_de_custo_recebe_403(vigente, client):
    """403, e nunca uma grade de zeros: uma grade zerada faz a pessoa achar que a
    empresa não gastou nada."""
    de_fora = _pessoa_com("almoxarife", "estoque", ["est.ler.global"])
    client.force_login(de_fora)

    assert client.get(reverse("workspace:orcamento")).status_code == 403


def test_o_anonimo_nao_ve_orcamento(vigente, client):
    resposta = client.get(reverse("workspace:orcamento"))

    assert resposta.status_code == 302
    assert "/entrar/" in resposta["Location"]


def test_o_gestor_le_e_nao_revisa(vigente, gestor, client):
    client.force_login(gestor)
    url = reverse("workspace:orcamento_centro", kwargs={"codigo": "1042", "ano": ANO})

    conteudo = client.get(url).content.decode()
    assert "Aplicar revisão" not in conteudo

    resposta = client.post(
        reverse("workspace:revisar_orcamento", kwargs={"codigo": "1042", "ano": ANO}),
        {"delta_7": "1000", "motivo": "sem permissão"},
    )
    assert resposta.status_code == 403
    assert RevisaoOrcamento.objects.count() == 0


def test_centro_de_custo_alheio_da_403_e_nao_404(vigente, gestor, client):
    """Dizer "não existe" a quem apenas não alcança o centro de custo
    transformaria a tela num verificador de códigos."""
    CentroCusto.objects.create(codigo="2000", nome="Outra operação")
    client.force_login(gestor)

    resposta = client.get(
        reverse("workspace:orcamento_centro", kwargs={"codigo": "2000", "ano": ANO})
    )

    assert resposta.status_code == 403


# ── As seis colunas ─────────────────────────────────────────────────


def test_o_consumido_soma_realizado_e_comprometido(vigente, financeiro, centro):
    """Decidir por realizado é como se estoura um orçamento sem ninguém
    perceber: o que foi aprovado e ainda não pagou já é dinheiro gasto."""
    Lancamento.objects.create(
        centro_custo=centro, valor=Decimal("3000"), competencia=date(ANO, 7, 1)
    )
    Compromisso.objects.create(
        dominio="com", descricao="compra aprovada", centro_custo_codigo="1042",
        valor=Decimal("4000"), competencia=date(ANO, 7, 1),
        situacao=SituacaoCompromisso.ATIVO,
    )

    julho = next(linha for linha in svc.grade_anual("1042", ANO) if linha.mes == 7)

    assert julho.realizado == Decimal("3000")
    assert julho.comprometido == Decimal("4000")
    assert julho.consumido == Decimal("7000")
    assert julho.saldo == Decimal("3000")
    assert julho.percentual == Decimal("70.0")
    assert julho.estourado is False


def test_o_mes_estourado_e_marcado(vigente, centro):
    Lancamento.objects.create(
        centro_custo=centro, valor=Decimal("12000"), competencia=date(ANO, 8, 1)
    )

    agosto = next(linha for linha in svc.grade_anual("1042", ANO) if linha.mes == 8)

    assert agosto.saldo == Decimal("-2000")
    assert agosto.estourado is True


def test_mes_sem_teto_devolve_none_e_nao_zero(db, financeiro):
    """Sem teto não há denominador, e 0% seria lido como folga total —
    restrição 5, a mesma de `/workspace/indicadores/`."""
    CentroCusto.objects.create(codigo="3000", nome="Sem teto")

    linha = svc.grade_anual("3000", ANO)[0]

    assert linha.orcado is None
    assert linha.saldo is None
    assert linha.percentual is None
    assert linha.estourado is False, "sem teto não estoura — não há contra o quê"


def test_a_tela_escreve_travessao_e_nao_zero_sem_teto(db, financeiro, client):
    CentroCusto.objects.create(codigo="3000", nome="Sem teto")
    client.force_login(financeiro)

    conteudo = client.get(
        reverse("workspace:orcamento_centro", kwargs={"codigo": "3000", "ano": ANO})
    ).content.decode()

    assert "—" in conteudo
    assert "0,0%" not in conteudo


def test_o_rotulo_do_mes_e_o_do_calendario(vigente):
    grade = svc.grade_anual("1042", ANO)

    assert [linha.rotulo for linha in grade[:3]] == ["jan", "fev", "mar"]


# ── O contrato ──────────────────────────────────────────────────────


def test_o_teto_do_mes_vem_do_ano_vigente(vigente, financeiro):
    svc.revisar("1042", ANO, {7: Decimal("5000")}, motivo="ajuste", quem=financeiro)
    provider = contrato.obter()

    assert provider.orcamento_do_mes("1042", date(ANO, 7, 1)) == Decimal("15000")
    assert provider.orcamento_do_mes("1042", date(ANO, 8, 1)) == Decimal("10000")


def test_sem_ano_montado_o_teto_cai_no_campo_avulso(centro):
    """O campo antigo fica: arrancá-lo quebraria a bandeja no dia do deploy,
    para todo centro de custo que ainda não tiver o ano montado."""
    provider = contrato.obter()

    assert provider.orcamento_do_mes("1042", date(ANO, 7, 1)) == Decimal("10000")
    assert provider.orcamento_do_ano("1042", ANO) == {}


def test_mes_sem_linha_cai_no_campo_avulso(centro, financeiro):
    """Um orçamento montado só até junho não pode fazer julho virar "sem
    orçamento" para a bandeja."""
    provider = contrato.obter()
    provider.montar_orcamento("1042", ANO, {m: 20000 for m in range(1, 7)})
    provider.vigorar_orcamento("1042", ANO, financeiro)

    assert provider.orcamento_do_mes("1042", date(ANO, 3, 1)) == Decimal("20000")
    assert provider.orcamento_do_mes("1042", date(ANO, 7, 1)) == Decimal("10000")


def test_o_orcamento_do_ano_de_rascunho_nao_conta(centro, financeiro):
    """Rascunho não vale: enquanto ele não vigora, a bandeja usa o teto avulso."""
    contrato.obter().montar_orcamento("1042", ANO, {m: 20000 for m in range(1, 13)})

    assert contrato.obter().orcamento_do_ano("1042", ANO) == {}


def test_montar_centro_inexistente_devolve_false(db):
    assert contrato.obter().montar_orcamento("nao-existe", ANO, {1: 100}) is False


def test_mes_fora_do_calendario_e_ignorado_ao_montar(centro):
    contrato.obter().montar_orcamento("1042", ANO, {0: 100, 13: 100, 5: 700})

    orcamento = OrcamentoAnual.objects.get(centro_custo=centro, ano=ANO)
    assert [linha.mes for linha in orcamento.linhas.all()] == [5]


# ── A semeadora ─────────────────────────────────────────────────────


def test_a_semeadora_importa_doze_meses_iguais(centro):
    """Inventar sazonalidade seria inventar dado. Doze iguais é o que o produto
    sabe hoje — a primeira revisão de verdade corrige julho."""
    call_command("semear_orcamento", "--aplicar", "--ano", str(ANO), verbosity=0)

    orcamento = OrcamentoAnual.objects.get(centro_custo=centro, ano=ANO)
    assert orcamento.vigente is True
    assert orcamento.linhas.count() == 12
    assert orcamento.total == Decimal("120000")


def test_a_semeadora_nao_toca_no_que_ja_existe(vigente, financeiro):
    """Sobrescrever no deploy seguinte apagaria revisões."""
    svc.revisar("1042", ANO, {7: Decimal("5000")}, motivo="ajuste", quem=financeiro)

    call_command("semear_orcamento", "--aplicar", "--ano", str(ANO), verbosity=0)

    vigente.refresh_from_db()
    assert vigente.do_mes(7) == Decimal("15000")
    assert RevisaoOrcamento.objects.count() == 1


def test_a_semeadora_pula_centro_sem_teto(db):
    """Criar um ano de zeros seria pior: a bandeja diria "0% de folga" onde hoje
    ela diz, corretamente, "sem orçamento definido"."""
    CentroCusto.objects.create(codigo="3000", nome="Sem teto")

    call_command("semear_orcamento", "--aplicar", "--ano", str(ANO), verbosity=0)

    assert not OrcamentoAnual.objects.filter(centro_custo__codigo="3000").exists()


def test_a_simulacao_nao_grava(centro):
    call_command("semear_orcamento", "--ano", str(ANO), verbosity=0)

    assert OrcamentoAnual.objects.count() == 0


# ── Pela view ───────────────────────────────────────────────────────


def test_a_revisao_pela_tela_aplica_e_avisa_o_total(vigente, financeiro, client):
    client.force_login(financeiro)

    resposta = client.post(
        reverse("workspace:revisar_orcamento", kwargs={"codigo": "1042", "ano": ANO}),
        {"delta_7": "15000", "delta_9": "-8000", "motivo": "reajuste de julho"},
        follow=True,
    )

    vigente.refresh_from_db()
    assert "Revisão 1 aplicada" in resposta.content.decode()
    assert vigente.do_mes(7) == Decimal("25000")


def test_o_campo_em_branco_e_nao_mexi_e_nao_zerei(vigente, financeiro, client):
    """Tratar em branco como zero faria uma revisão de julho zerar os outros
    onze."""
    client.force_login(financeiro)

    client.post(
        reverse("workspace:revisar_orcamento", kwargs={"codigo": "1042", "ano": ANO}),
        {"delta_7": "1000", "motivo": "só julho"},
    )

    vigente.refresh_from_db()
    assert vigente.do_mes(7) == Decimal("11000")
    assert vigente.do_mes(1) == Decimal("10000")
    assert RevisaoOrcamento.objects.get().deltas == {"7": "1000"}


def test_valor_invalido_no_delta_avisa_e_ignora_o_mes(vigente, financeiro, client):
    """Perder a revisão inteira por causa de um campo seria o pior desfecho: o
    motivo e os outros meses são o que a pessoa acabou de escrever."""
    client.force_login(financeiro)

    resposta = client.post(
        reverse("workspace:revisar_orcamento", kwargs={"codigo": "1042", "ano": ANO}),
        {"delta_7": "mil reais", "delta_8": "2000", "motivo": "agosto"},
        follow=True,
    )

    vigente.refresh_from_db()
    assert "Valor inválido em jul" in resposta.content.decode()
    assert vigente.do_mes(7) == Decimal("10000")
    assert vigente.do_mes(8) == Decimal("12000")


def test_a_virgula_decimal_e_aceita(vigente, financeiro, client):
    """Quem digita orçamento no Brasil digita vírgula."""
    client.force_login(financeiro)

    client.post(
        reverse("workspace:revisar_orcamento", kwargs={"codigo": "1042", "ano": ANO}),
        {"delta_7": "1500,50", "motivo": "vírgula"},
    )

    vigente.refresh_from_db()
    assert vigente.do_mes(7) == Decimal("11500.50")


def test_revisao_sem_motivo_pela_tela_volta_com_a_mensagem(vigente, financeiro, client):
    client.force_login(financeiro)

    resposta = client.post(
        reverse("workspace:revisar_orcamento", kwargs={"codigo": "1042", "ano": ANO}),
        {"delta_7": "1000", "motivo": "  "},
        follow=True,
    )

    assert "exige o motivo" in resposta.content.decode()
    assert RevisaoOrcamento.objects.count() == 0


def test_revisao_sem_nada_para_mudar_diz_as_duas_causas(vigente, financeiro, client):
    """Sem orçamento vigente não há o que revisar; sem delta, não houve mudança.
    As duas pedem coisas diferentes de quem está na tela."""
    client.force_login(financeiro)

    resposta = client.post(
        reverse("workspace:revisar_orcamento", kwargs={"codigo": "1042", "ano": ANO}),
        {"motivo": "nada mudou"},
        follow=True,
    )

    assert "Nada foi revisado" in resposta.content.decode()


def test_vigorar_pela_tela(centro, financeiro, client):
    contrato.obter().montar_orcamento("1042", ANO, {m: 1000 for m in range(1, 13)})
    client.force_login(financeiro)

    resposta = client.post(
        reverse("workspace:vigorar_orcamento", kwargs={"codigo": "1042", "ano": ANO}),
        follow=True,
    )

    assert "muda por revisão" in resposta.content.decode()
    assert OrcamentoAnual.objects.get(centro_custo=centro, ano=ANO).vigente is True


def test_vigorar_sem_rascunho_avisa_e_nao_estoura(centro, financeiro, client):
    client.force_login(financeiro)

    resposta = client.post(
        reverse("workspace:vigorar_orcamento", kwargs={"codigo": "1042", "ano": ANO}),
        follow=True,
    )

    assert "Não havia rascunho" in resposta.content.decode()


def test_vigorar_sem_permissao_de_revisar_volta_com_o_motivo(
    vigente, gestor, client
):
    client.force_login(gestor)

    resposta = client.post(
        reverse("workspace:vigorar_orcamento", kwargs={"codigo": "1042", "ano": ANO}),
        follow=True,
    )

    assert "responde pelo dinheiro" in resposta.content.decode()


def test_ano_invalido_na_query_da_404(vigente, financeiro, client):
    client.force_login(financeiro)

    assert client.get(
        reverse("workspace:orcamento"), {"ano": "ano que vem"}
    ).status_code == 404
    assert client.get(
        reverse("workspace:orcamento"), {"ano": "1899"}
    ).status_code == 404


def test_ano_fora_do_calendario_na_url_da_404(vigente, financeiro, client):
    client.force_login(financeiro)

    resposta = client.get(
        reverse("workspace:orcamento_centro", kwargs={"codigo": "1042", "ano": 1500})
    )

    assert resposta.status_code == 404


def test_a_lista_marca_os_meses_estourados(vigente, centro, financeiro, client):
    Lancamento.objects.create(
        centro_custo=centro, valor=Decimal("12000"), competencia=date(ANO, 8, 1)
    )
    client.force_login(financeiro)

    conteudo = client.get(
        reverse("workspace:orcamento"), {"ano": ANO}
    ).content.decode()

    assert "1 mês" in conteudo


def test_a_lista_sem_centro_nenhum_explica_o_que_falta(db, client):
    """Estado vazio que EXPLICA — restrição 6."""
    financeiro = _pessoa_com(
        "fin", "financeiro_global",
        ["fin.orcamento.ler.global", "fin.orcamento.revisar.global"],
    )
    client.force_login(financeiro)

    conteudo = client.get(reverse("workspace:orcamento")).content.decode()

    assert "semear_orcamento" in conteudo


def test_o_confronto_aparece_na_tela_com_os_dois_numeros(vigente, espelho, financeiro,
                                                         client):
    client.force_login(financeiro)

    conteudo = client.get(
        reverse("workspace:orcamento_centro", kwargs={"codigo": "1042", "ano": ANO})
    ).content.decode()

    assert "o orçado do Sankhya" in conteudo
    assert "não se resolve aqui" in conteudo


def test_o_trilho_so_mostra_orcamento_para_quem_responde(vigente, client):
    de_fora = _pessoa_com("almoxarife2", "estoque2", ["est.ler.global"])
    client.force_login(de_fora)

    conteudo = client.get(reverse("workspace:servicos")).content.decode()

    assert "/workspace/orcamento/" not in conteudo


def test_sem_provider_financeiro_a_tela_nao_estoura(vigente, financeiro):
    """O Workspace roda sem `financas` instalado — é a mesma degradação que
    `resumo()` já praticava."""
    guardado = contrato.obter()
    contrato.limpar()
    try:
        grade = svc.grade_anual("1042", ANO)
        assert all(linha.orcado is None for linha in grade)
        assert svc.revisoes("1042", ANO) == []
        assert svc.revisar("1042", ANO, {7: 1}, motivo="x", quem=financeiro) is None
        assert svc.vigorar("1042", ANO, financeiro) is False
        assert svc.montar("1042", ANO, {7: 1}, financeiro) is False
    finally:
        if guardado is not None:
            contrato.registrar(guardado)


def test_montar_sem_permissao_e_recusado(vigente, gestor):
    with pytest.raises(svc.OrcamentoError, match="responde pelo dinheiro"):
        svc.montar("1042", ANO, {7: 1}, gestor)


def test_o_str_de_cada_model_diz_o_que_e(vigente, financeiro):
    """`__str__` aparece no `/admin/` e em toda mensagem de erro."""
    revisao = svc.revisar(
        "1042", ANO, {7: Decimal("1000")}, motivo="ajuste", quem=financeiro
    )
    registro = RevisaoOrcamento.objects.get()
    linha = LinhaOrcamento.objects.filter(orcamento=vigente, mes=7).get()

    assert str(vigente) == f"1042 · {ANO}"
    assert str(linha).startswith(f"1042 · {ANO} · 07")
    assert str(registro) == f"1042 · {ANO} · revisão 1"
    assert revisao.numero == registro.numero


def test_lotacao_sem_centro_de_custo_recebe_403(vigente, client):
    """Permissão sem lotação não vira escopo global por acidente de cadastro —
    é a mesma proteção de `resultados.escopo_de`."""
    solto = f.pessoa("solto", nome="Solto")
    f.lotar(solto, centro_custo_codigo="")
    f.atribuir(
        solto,
        f.papel("papel_solto", ["fin.orcamento.ler.departamento"], escopo="global"),
        escopo="global",
    )
    client.force_login(solto)

    assert client.get(reverse("workspace:orcamento")).status_code == 403


def test_revisar_centro_alheio_pela_tela_e_403(vigente, gestor, client):
    """O `codigo` vem da URL: sem esta checagem, quem alcança um centro de custo
    revisaria o de qualquer outro."""
    CentroCusto.objects.create(codigo="2000", nome="Outra operação")
    client.force_login(gestor)

    assert client.post(
        reverse("workspace:revisar_orcamento", kwargs={"codigo": "2000", "ano": ANO}),
        {"delta_7": "1000", "motivo": "alheio"},
    ).status_code == 403
    assert client.post(
        reverse("workspace:vigorar_orcamento", kwargs={"codigo": "2000", "ano": ANO})
    ).status_code == 403


def test_revisar_sem_permissao_e_recusado_no_servico(vigente, gestor):
    """A view confere antes, e o serviço confere de novo — a segunda tranca é a
    que vale quando alguém escrever a terceira view."""
    with pytest.raises(svc.OrcamentoError, match="responde pelo dinheiro"):
        svc.revisar("1042", ANO, {7: Decimal("1")}, motivo="x", quem=gestor)


def test_montar_pelo_servico_escreve_o_rascunho(centro, financeiro):
    assert svc.montar("1042", ANO, {m: 500 for m in range(1, 13)}, financeiro) is True

    orcamento = OrcamentoAnual.objects.get(centro_custo=centro, ano=ANO)
    assert orcamento.total == Decimal("6000")
