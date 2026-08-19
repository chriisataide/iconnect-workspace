"""§17 — quem está com o quê, e o que falta devolver.

O buraco que este módulo fecha: o notebook saía do estoque para uma pessoa e a
partir daí sumia do sistema. O saldo baixava, o razão registrava uma saída, e a
pergunta que o RH faz no desligamento — *o que esta pessoa tem para devolver?* —
não tinha onde ser respondida. Na prática ela era respondida pela memória de
quem entregou.

O que estes testes guardam:

1. **Entregar BAIXA o estoque.** Custódia não é cadastro paralelo: o capacete
   que está com alguém não está mais na prateleira.
2. **Ninguém entrega para si mesmo.** Segregação de função — quem opera o
   estoque também recebe equipamento, e nesse dia quem assina é outra pessoa.
3. **O aceite é da pessoa, e só dela.** `entregue_em` é Suprimentos dizendo
   "entreguei"; `aceito_em` é a pessoa dizendo "recebi".
4. **Devolver volta ao razão PELA CONDIÇÃO** — e sucata não volta ao saldo, pela
   mesma regra do §15.
5. **Saldo insuficiente não deixa termo órfão.** A saída vem antes da custódia, e
   é ela que dá o "ou nada" da transação.
"""

from __future__ import annotations

import pytest

from identidade.tests import fabricas as f
from workspace.models.custodia import Custodia
from workspace.models.estoque import (
    CondicaoMaterial,
    Material,
    MovimentoEstoque,
    TipoMovimento,
)
from workspace.models.notificacao import Notificacao, TipoNotificacao
from workspace.services import custodia as cst
from workspace.services import estoque as est
from workspace.services.custodia import CustodiaError
from workspace.services.estoque import EstoqueError

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    unidade = f.unidade()
    almox, ana = f.pessoa("almoxarife"), f.pessoa("ana")
    f.lotar(almox, uni=unidade)
    f.lotar(ana, uni=unidade)
    f.atribuir(
        almox,
        f.papel(
            "sup",
            ["log.custodia.ler.global", "log.custodia.atribuir.global"],
            escopo="global",
        ),
    )
    notebook = Material.objects.create(
        codigo="notebook", nome="Notebook Dell", controla_patrimonio=True
    )
    est.movimentar(notebook, unidade, TipoMovimento.ENTRADA, 5)
    return {"unidade": unidade, "almox": almox, "ana": ana, "material": notebook}


def entregar(cenario, **extras):
    dados = {"quantidade": 1, "patrimonio": "PAT-1042"}
    dados.update(extras)
    return cst.entregar(
        cenario["material"], cenario["ana"], cenario["almox"], **dados
    )


# ── Entregar ────────────────────────────────────────────────────────


def test_entregar_baixa_o_estoque(cenario):
    """Custódia não é cadastro paralelo: o que está com alguém não está na
    prateleira, e registrar sem baixar faria o sistema mentir nas duas pontas."""
    entregar(cenario)

    assert est.saldo_de(cenario["material"], cenario["unidade"]) == 4


def test_a_baixa_fica_amarrada_a_custodia_no_razao(cenario):
    entregar(cenario)

    saida = MovimentoEstoque.objects.get(tipo=TipoMovimento.SAIDA)
    assert saida.dominio == "log.custodia"
    assert "Ana" in saida.observacao or cenario["ana"].get_full_name() in saida.observacao


def test_ninguem_entrega_para_si_mesmo(cenario):
    """Segregação de função: quem opera o estoque também recebe equipamento, e
    nesse dia quem assina a entrega é outra pessoa."""
    with pytest.raises(CustodiaError, match="si mesmo"):
        cst.entregar(
            cenario["material"], cenario["almox"], cenario["almox"], quantidade=1
        )


def test_quem_nao_atribui_nao_entrega(cenario):
    outra = f.pessoa("bruno")
    f.lotar(outra, uni=cenario["unidade"])

    with pytest.raises(CustodiaError, match="não pode entregar"):
        cst.entregar(cenario["material"], cenario["ana"], outra, quantidade=1)


def test_saldo_insuficiente_nao_deixa_termo_orfao(cenario):
    """A saída vem ANTES da custódia, e é ela que dá o "ou nada" da transação.

    Registrar a custódia primeiro deixaria um termo de responsabilidade por um
    material que não existe.
    """
    with pytest.raises(EstoqueError):
        entregar(cenario, quantidade=99)

    assert not Custodia.objects.exists()
    assert est.saldo_de(cenario["material"], cenario["unidade"]) == 5


def test_pessoa_sem_lotacao_nao_recebe(cenario):
    """Sem unidade não há de qual prateleira baixar — e a devolução não teria
    para onde voltar."""
    sem_lotacao = f.pessoa("avulso")

    with pytest.raises(CustodiaError, match="unidade de lotação"):
        cst.entregar(cenario["material"], sem_lotacao, cenario["almox"])


def test_entrega_avisa_quem_recebeu(cenario):
    """O aviso é o que transforma o registro em termo: sem ele a pessoa passa a
    responder por um equipamento sem nunca ter sido informada."""
    entregar(cenario)

    aviso = Notificacao.objects.de(cenario["ana"]).get()
    assert aviso.tipo == TipoNotificacao.EQUIPAMENTO_SOB_CUSTODIA
    assert "PAT-1042" in aviso.titulo


def test_quantidade_zero_nao_entrega(cenario):
    with pytest.raises(CustodiaError, match="maior que zero"):
        entregar(cenario, quantidade=0)


def test_entrega_sem_pessoa_recusa(cenario):
    with pytest.raises(CustodiaError, match="para quem"):
        cst.entregar(cenario["material"], None, cenario["almox"])


# ── Aceite ──────────────────────────────────────────────────────────


def test_so_quem_esta_com_o_material_confirma(cenario):
    guarda = entregar(cenario)

    with pytest.raises(CustodiaError, match="Só quem está"):
        cst.aceitar(guarda, cenario["almox"])


def test_aceite_registra_a_palavra_de_quem_recebeu(cenario):
    guarda = entregar(cenario)
    assert guarda.espera_aceite

    cst.aceitar(guarda, cenario["ana"])
    guarda.refresh_from_db()

    assert guarda.aceita
    assert guarda.situacao == "em_uso"


def test_aceitar_duas_vezes_nao_reescreve_a_data(cenario):
    guarda = entregar(cenario)
    cst.aceitar(guarda, cenario["ana"])
    primeiro = guarda.aceito_em

    cst.aceitar(guarda, cenario["ana"])
    guarda.refresh_from_db()

    assert guarda.aceito_em == primeiro


def test_nao_se_aceita_custodia_encerrada(cenario):
    guarda = entregar(cenario)
    cst.devolver(guarda, cenario["almox"], CondicaoMaterial.USADO_BOM)

    with pytest.raises(CustodiaError, match="já foi encerrada"):
        cst.aceitar(guarda, cenario["ana"])


# ── Devolver ────────────────────────────────────────────────────────


def test_devolver_em_bom_estado_volta_ao_saldo(cenario):
    guarda = entregar(cenario)
    assert est.saldo_de(cenario["material"], cenario["unidade"]) == 4

    cst.devolver(guarda, cenario["almox"], CondicaoMaterial.USADO_BOM)

    assert est.saldo_de(cenario["material"], cenario["unidade"]) == 5


def test_sucata_entra_no_razao_e_nao_no_saldo(cenario):
    """A mesma regra do §15, e a mesma função: contar sucata no disponível faria
    alguém programar a entrega de um equipamento imprestável."""
    guarda = entregar(cenario)

    cst.devolver(guarda, cenario["almox"], CondicaoMaterial.SUCATA)

    assert est.saldo_de(cenario["material"], cenario["unidade"]) == 4
    assert MovimentoEstoque.objects.filter(
        tipo=TipoMovimento.REVERSA, condicao=CondicaoMaterial.SUCATA
    ).exists()


def test_devolucao_entra_como_reversa(cenario):
    """Material devolvido É material que voltou de campo — a pergunta "o que dá
    para reaproveitar" não pode ter duas respostas conforme o caminho de volta."""
    guarda = entregar(cenario)
    cst.devolver(guarda, cenario["almox"], CondicaoMaterial.USADO_REPARO)

    reversa = est.reversas(unidade=cenario["unidade"]).get()
    assert reversa.condicao == CondicaoMaterial.USADO_REPARO
    assert reversa.patrimonio == "PAT-1042"


def test_devolver_exige_a_condicao(cenario):
    guarda = entregar(cenario)

    with pytest.raises(CustodiaError, match="em que condição"):
        cst.devolver(guarda, cenario["almox"], "")


def test_quem_nao_atribui_nao_da_baixa(cenario):
    guarda = entregar(cenario)

    with pytest.raises(CustodiaError, match="não pode dar baixa"):
        cst.devolver(guarda, cenario["ana"], CondicaoMaterial.USADO_BOM)


def test_nao_se_devolve_duas_vezes(cenario):
    guarda = entregar(cenario)
    cst.devolver(guarda, cenario["almox"], CondicaoMaterial.USADO_BOM)

    with pytest.raises(CustodiaError, match="já foi encerrada"):
        cst.devolver(guarda, cenario["almox"], CondicaoMaterial.USADO_BOM)


def test_observacao_da_devolucao_e_gravada(cenario):
    guarda = entregar(cenario)
    cst.devolver(
        guarda, cenario["almox"], CondicaoMaterial.USADO_REPARO,
        observacao="Tela trincada.",
    )
    guarda.refresh_from_db()

    assert guarda.observacao == "Tela trincada."


# ── Consulta ────────────────────────────────────────────────────────


def test_a_pessoa_ve_o_que_esta_no_proprio_nome_sem_permissao(cenario):
    """Negar isso à própria pessoa seria pedir que ela assine um termo que não
    pode ler."""
    entregar(cenario)

    assert list(cst.minhas(cenario["ana"])) == list(Custodia.objects.all())


def test_a_lista_dos_outros_exige_permissao(cenario):
    entregar(cenario)

    assert not cst.em_poder_de_terceiros(cenario["ana"]).exists()
    assert cst.em_poder_de_terceiros(cenario["almox"]).exists()


def test_pendencias_de_e_a_pergunta_do_desligamento(cenario):
    entregar(cenario)
    entregar(cenario, patrimonio="PAT-2000")

    assert len(cst.pendencias_de(cenario["ana"])) == 2


def test_devolvida_sai_das_pendencias(cenario):
    guarda = entregar(cenario)
    cst.devolver(guarda, cenario["almox"], CondicaoMaterial.NOVO)

    assert cst.pendencias_de(cenario["ana"]) == []


def test_a_aceitar_lista_so_o_que_falta_confirmar(cenario):
    primeira = entregar(cenario)
    entregar(cenario, patrimonio="PAT-2000")
    cst.aceitar(primeira, cenario["ana"])

    assert cst.a_aceitar(cenario["ana"]).count() == 1


def test_filtro_por_unidade_na_lista_de_terceiros(cenario):
    entregar(cenario)
    outra = f.unidade(codigo="RJ", nome="Base RJ")

    assert cst.em_poder_de_terceiros(cenario["almox"], unidade=outra).count() == 0
    assert (
        cst.em_poder_de_terceiros(cenario["almox"], unidade=cenario["unidade"]).count()
        == 1
    )


# ── O que a tela lê ─────────────────────────────────────────────────


def test_identificacao_prefere_patrimonio_depois_serie(cenario):
    com_patrimonio = entregar(cenario)
    com_serie = entregar(cenario, patrimonio="", numero_serie="SN-9")
    sem_nada = entregar(cenario, patrimonio="")

    assert com_patrimonio.identificacao == "pat. PAT-1042"
    assert com_serie.identificacao == "s/n SN-9"
    assert sem_nada.identificacao == ""


def test_situacao_e_derivada_e_nao_gravada(cenario):
    """Um campo `situacao` ao lado de `devolvido_em` seria uma segunda fonte de
    verdade sobre a mesma data, e a primeira a discordar dela."""
    guarda = entregar(cenario)
    assert guarda.situacao == "a_aceitar"

    cst.aceitar(guarda, cenario["ana"])
    assert guarda.situacao == "em_uso"

    cst.devolver(guarda, cenario["almox"], CondicaoMaterial.USADO_BOM)
    assert guarda.situacao == "devolvida"
    assert guarda.situacao_rotulo == "Devolvida"


def test_dias_em_uso_para_no_dia_da_devolucao(cenario):
    guarda = entregar(cenario)
    cst.devolver(guarda, cenario["almox"], CondicaoMaterial.USADO_BOM)

    assert guarda.dias_em_uso == 0


def test_queryset_de_nao_vaza_para_anonimo(cenario):
    from django.contrib.auth.models import AnonymousUser

    entregar(cenario)

    assert not Custodia.objects.de(AnonymousUser()).exists()
    assert not Custodia.objects.de(None).exists()


def test_quem_atribui_tambem_le(cenario):
    """Sem a soma, o papel que entrega equipamento não enxergaria o que acabou
    de entregar — e teria de declarar as duas permissões para uma coisa só."""
    so_atribui = f.pessoa("carlos")
    f.lotar(so_atribui, uni=cenario["unidade"])
    f.atribuir(
        so_atribui,
        f.papel("atrib", ["log.custodia.atribuir.global"], escopo="global"),
    )

    assert cst.pode_ler(so_atribui)
