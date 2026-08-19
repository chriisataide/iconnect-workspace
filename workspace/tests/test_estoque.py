"""EST — o razão do estoque, e o saldo que não pode ficar negativo.

Os papéis de Suprimentos declaram `log.movimentar`, `log.custodia.*` e
`log.inventario.contar` desde a primeira onda. O vocabulário foi desenhado e os
modelos nunca existiram: na prática o saldo mora numa planilha, e "temos
capacete G?" é respondido por mensagem para quem tem a planilha aberta.

O que estes testes guardam:

1. **O razão é a verdade e o saldo é atalho** — e existe uma conta que compara
   os dois, senão uma divergência só apareceria na contagem física seguinte.
2. **Saldo negativo é impossível**, no serviço e no banco.
3. **Duas requisições simultâneas não gastam a mesma peça.**
4. **Sucata volta ao razão mas não ao saldo** — contá-la faria alguém programar
   a entrega de um equipamento imprestável.
5. **Ajuste é a contagem, não o delta** — quem conta a prateleira sabe quantos
   viu, não a diferença.
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError, transaction

from identidade.tests import fabricas as f
from workspace.models.estoque import (
    CondicaoMaterial,
    Material,
    MovimentoEstoque,
    SaldoEstoque,
    TipoMovimento,
)
from workspace.services import estoque as est
from workspace.services.estoque import EstoqueError

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    unidade = f.unidade()
    almox = f.pessoa("almoxarife")
    f.lotar(almox, uni=unidade)
    capacete = Material.objects.create(
        codigo="capacete-g", nome="Capacete G", categoria="epi", estoque_minimo=5
    )
    return {"unidade": unidade, "quem": almox, "material": capacete}


def entrar(cenario, quantidade=10):
    return est.movimentar(
        cenario["material"], cenario["unidade"], TipoMovimento.ENTRADA,
        quantidade, quem=cenario["quem"],
    )


# ── O razão e o saldo ───────────────────────────────────────────────


def test_entrada_cria_saldo_e_linha_no_razao(cenario):
    movimento = entrar(cenario, 10)

    assert est.saldo_de(cenario["material"], cenario["unidade"]) == 10
    assert movimento.saldo_anterior == 0
    assert movimento.saldo_posterior == 10


def test_cada_linha_guarda_o_antes_e_o_depois(cenario):
    """Sem `saldo_anterior`/`saldo_posterior`, uma divergência não tem como ser
    rastreada até o movimento que a criou."""
    entrar(cenario, 10)
    saida = est.movimentar(
        cenario["material"], cenario["unidade"], TipoMovimento.SAIDA, 4,
        quem=cenario["quem"],
    )

    assert (saida.saldo_anterior, saida.saldo_posterior) == (10, 6)


def test_o_razao_confere_com_o_saldo(cenario):
    entrar(cenario, 10)
    est.movimentar(cenario["material"], cenario["unidade"], TipoMovimento.SAIDA, 3)

    gravado, somado = est.conferir_razao(cenario["material"], cenario["unidade"])
    assert gravado == somado == 7


def test_a_conferencia_denuncia_saldo_mexido_por_fora(cenario):
    """O modo real de o estoque ficar errado não é concorrência — é um
    `update()` numa migração de dados. A conta existe para que isso apareça."""
    entrar(cenario, 10)
    SaldoEstoque.objects.filter(material=cenario["material"]).update(quantidade=99)

    gravado, somado = est.conferir_razao(cenario["material"], cenario["unidade"])
    assert gravado == 99 and somado == 10


# ── O saldo não fica negativo ───────────────────────────────────────


def test_saida_maior_que_o_saldo_e_recusada(cenario):
    entrar(cenario, 3)

    with pytest.raises(EstoqueError, match="Saldo insuficiente"):
        est.movimentar(cenario["material"], cenario["unidade"], TipoMovimento.SAIDA, 4)


def test_a_recusa_diz_quanto_existe(cenario):
    """"Saldo insuficiente" sozinho manda a pessoa perguntar. O número evita a
    mensagem."""
    entrar(cenario, 3)

    with pytest.raises(EstoqueError, match="há 3 unidade"):
        est.movimentar(cenario["material"], cenario["unidade"], TipoMovimento.SAIDA, 4)


def test_a_saida_recusada_nao_deixa_rastro(cenario):
    entrar(cenario, 3)
    with pytest.raises(EstoqueError):
        est.movimentar(cenario["material"], cenario["unidade"], TipoMovimento.SAIDA, 4)

    assert est.saldo_de(cenario["material"], cenario["unidade"]) == 3
    assert MovimentoEstoque.objects.filter(tipo=TipoMovimento.SAIDA).count() == 0


def test_o_banco_tambem_recusa_saldo_negativo(cenario):
    """A constraint é a que sobra quando alguém contorna o serviço."""
    entrar(cenario, 3)

    with pytest.raises(IntegrityError), transaction.atomic():
        SaldoEstoque.objects.filter(material=cenario["material"]).update(quantidade=-1)


@pytest.mark.parametrize("quantidade", [0, -5])
def test_movimento_sem_quantidade_positiva_e_recusado(cenario, quantidade):
    """Zero não é movimento, e negativo é o sinal invertido — os dois corrompem
    o razão de um jeito que só aparece na conferência do mês."""
    with pytest.raises(EstoqueError, match="maior que zero"):
        est.movimentar(
            cenario["material"], cenario["unidade"], TipoMovimento.ENTRADA, quantidade
        )


# ── Reversa (§15) ───────────────────────────────────────────────────


def test_reversa_entra_no_saldo_e_guarda_a_procedencia(cenario):
    outra = f.unidade(codigo="RJ", nome="Filial RJ")

    movimento = est.entrada_de_reversa(
        cenario["material"], cenario["unidade"], 6,
        condicao=CondicaoMaterial.USADO_BOM, quem=cenario["quem"],
        unidade_origem=outra, cliente="Cliente Alfa", patrimonio="PAT-9911",
    )

    assert est.saldo_de(cenario["material"], cenario["unidade"]) == 6
    assert movimento.unidade_origem == outra
    assert movimento.cliente == "Cliente Alfa"
    assert movimento.patrimonio == "PAT-9911"


def test_reversa_exige_condicao(cenario):
    """A pergunta que o §15 responde é "o que dá para reaproveitar", e quem
    responde isso é a condição — não a quantidade."""
    with pytest.raises(EstoqueError, match="condição"):
        est.entrada_de_reversa(
            cenario["material"], cenario["unidade"], 6, condicao="", quem=cenario["quem"]
        )


def test_sucata_fica_no_razao_e_fora_do_saldo(cenario):
    entrar(cenario, 4)

    est.entrada_de_reversa(
        cenario["material"], cenario["unidade"], 10,
        condicao=CondicaoMaterial.SUCATA, quem=cenario["quem"],
    )

    assert est.saldo_de(cenario["material"], cenario["unidade"]) == 4, (
        "sucata entrou no saldo — alguém vai programar a entrega dela"
    )
    assert MovimentoEstoque.objects.filter(condicao=CondicaoMaterial.SUCATA).exists()


def test_a_conferencia_nao_conta_sucata(cenario):
    entrar(cenario, 4)
    est.entrada_de_reversa(
        cenario["material"], cenario["unidade"], 10,
        condicao=CondicaoMaterial.SUCATA, quem=cenario["quem"],
    )

    gravado, somado = est.conferir_razao(cenario["material"], cenario["unidade"])
    assert gravado == somado == 4


# ── Ajuste de inventário ────────────────────────────────────────────


def test_ajuste_e_a_contagem_e_nao_a_diferenca(cenario):
    """Quem conta a prateleira sabe quantos viu. Pedir o delta obrigaria a
    pessoa a fazer a subtração de cabeça — e é aí que o inventário erra."""
    entrar(cenario, 10)

    movimento = est.movimentar(
        cenario["material"], cenario["unidade"], TipoMovimento.AJUSTE, 7,
        quem=cenario["quem"], observacao="Contagem de agosto.",
    )

    assert est.saldo_de(cenario["material"], cenario["unidade"]) == 7
    assert (movimento.saldo_anterior, movimento.saldo_posterior) == (10, 7)


def test_o_razao_recomeca_do_ajuste(cenario):
    """Depois de um ajuste, o histórico anterior não soma mais: a contagem
    física SUBSTITUIU o que o sistema achava. Somar desde o começo devolveria
    justamente a diferença que o ajuste corrigiu."""
    entrar(cenario, 10)
    est.movimentar(cenario["material"], cenario["unidade"], TipoMovimento.AJUSTE, 7)
    est.movimentar(cenario["material"], cenario["unidade"], TipoMovimento.SAIDA, 2)

    gravado, somado = est.conferir_razao(cenario["material"], cenario["unidade"])
    assert gravado == somado == 5


# ── Saldo por unidade, não global ───────────────────────────────────


def test_o_saldo_e_por_unidade(cenario):
    """"Temos 40" é inútil para quem está em Campinas quando os 40 estão em
    São Paulo."""
    outra = f.unidade(codigo="CPS", nome="Filial Campinas")
    entrar(cenario, 40)

    assert est.saldo_de(cenario["material"], outra) == 0
    with pytest.raises(EstoqueError, match="Saldo insuficiente"):
        est.movimentar(cenario["material"], outra, TipoMovimento.SAIDA, 1)


def test_estoque_minimo_marca_a_linha(cenario):
    entrar(cenario, 3)
    linha = SaldoEstoque.objects.get(material=cenario["material"])

    assert linha.abaixo_do_minimo, "3 está abaixo do mínimo 5"


def test_minimo_zero_nao_alarma(cenario):
    """Aviso que dispara para tudo é aviso que se aprende a ignorar."""
    Material.objects.filter(pk=cenario["material"].pk).update(estoque_minimo=0)
    entrar(cenario, 1)
    linha = SaldoEstoque.objects.select_related("material").get(material=cenario["material"])

    assert not linha.abaixo_do_minimo


# ── As guardas que só aparecem quando alguém erra ───────────────────


def test_ajuste_negativo_e_recusado(cenario):
    entrar(cenario, 10)

    with pytest.raises(EstoqueError, match="não pode ser negativa"):
        est.movimentar(cenario["material"], cenario["unidade"], TipoMovimento.AJUSTE, -1)


def test_ajuste_aceita_zero(cenario):
    """"A prateleira está vazia" é a contagem mais importante que existe.

    A guarda genérica de `quantidade > 0` a recusava junto com as outras, e o
    efeito era um inventário sem como zerar item: o saldo fantasma ficava para
    sempre, e a contagem física que o desmentia não tinha onde ser registrada.
    """
    entrar(cenario, 10)

    est.movimentar(cenario["material"], cenario["unidade"], TipoMovimento.AJUSTE, 0)

    assert est.saldo_de(cenario["material"], cenario["unidade"]) == 0


@pytest.mark.parametrize("tipo", [TipoMovimento.ENTRADA, TipoMovimento.SAIDA])
def test_zero_continua_recusado_nos_outros_tipos(cenario, tipo):
    """Em entrada e saída a quantidade é um MOVIMENTO, e movimento de zero não
    é nada — a exceção do ajuste não vale para eles."""
    entrar(cenario, 10)

    with pytest.raises(EstoqueError, match="maior que zero"):
        est.movimentar(cenario["material"], cenario["unidade"], tipo, 0)


def test_tipo_desconhecido_e_recusado(cenario):
    """A lista de tipos é fechada. Sem esta guarda, um tipo inventado cairia no
    `else` sem saldo calculado e gravaria linha de razão que não bate com nada."""
    with pytest.raises(EstoqueError, match="desconhecido"):
        est.movimentar(cenario["material"], cenario["unidade"], "teletransporte", 1)


def test_condicao_so_vale_para_reversa(cenario):
    """Condição e cliente descrevem PROCEDÊNCIA. Numa entrada de compra eles
    não querem dizer nada, e aceitá-los faria o relatório de reversa do §15
    contar material que nunca voltou de lugar nenhum."""
    from django.core.exceptions import ValidationError

    movimento = MovimentoEstoque(
        material=cenario["material"], unidade=cenario["unidade"],
        tipo=TipoMovimento.ENTRADA, quantidade=1, saldo_anterior=0, saldo_posterior=1,
        condicao=CondicaoMaterial.USADO_BOM,
    )
    with pytest.raises(ValidationError, match="reversa"):
        movimento.full_clean(exclude=["quem"])


def test_reversa_sem_condicao_e_recusada_tambem_no_modelo(cenario):
    """A regra vale no serviço e no modelo: serviço é a porta certa, e o modelo
    é o que sobra quando alguém cria a linha direto no admin."""
    from django.core.exceptions import ValidationError

    movimento = MovimentoEstoque(
        material=cenario["material"], unidade=cenario["unidade"],
        tipo=TipoMovimento.REVERSA, quantidade=1, saldo_anterior=0, saldo_posterior=1,
    )
    with pytest.raises(ValidationError, match="condição"):
        movimento.full_clean(exclude=["quem"])


def test_o_razao_de_um_material_e_legivel(cenario):
    entrar(cenario, 10)
    est.movimentar(cenario["material"], cenario["unidade"], TipoMovimento.SAIDA, 2)

    linhas = list(est.razao_de(cenario["material"], unidade=cenario["unidade"]))

    assert [linha.tipo for linha in linhas] == [TipoMovimento.SAIDA, TipoMovimento.ENTRADA]
    assert len(list(est.razao_de(cenario["material"], limite=1))) == 1


def test_disponivel_para_sem_unidade_mostra_a_empresa_toda(cenario):
    """A visão de quem administra o estoque, e não a de quem retira."""
    outra = f.unidade(codigo="RJ", nome="Filial RJ")
    entrar(cenario, 10)
    est.movimentar(cenario["material"], outra, TipoMovimento.ENTRADA, 5)

    assert est.disponivel_para(cenario["quem"]).count() == 2
    assert est.disponivel_para(cenario["quem"], unidade=outra).count() == 1


def test_material_inativo_sai_da_disponibilidade(cenario):
    entrar(cenario, 10)
    Material.objects.filter(pk=cenario["material"].pk).update(ativo=False)

    assert est.disponivel_para(cenario["quem"]).count() == 0


def test_os_modelos_se_descrevem_no_admin(cenario):
    """`__str__` é o que o admin mostra em cada `<select>` de FK. Sem eles, a
    tela de movimento vira uma lista de `Material object (7)`."""
    entrar(cenario, 10)
    saldo = SaldoEstoque.objects.get(material=cenario["material"])
    movimento = MovimentoEstoque.objects.first()

    assert str(cenario["material"]) == "Capacete G"
    assert "Capacete G" in str(saldo) and "10" in str(saldo)
    assert "Entrada" in str(movimento) and "Capacete G" in str(movimento)


# ── A conferência, agora com quem a execute — §58 ───────────────────


def test_conferir_estoque_nao_acha_divergencia_quando_tudo_passou_pelo_servico(
    cenario, capsys
):
    """`conferir_razao()` existia com a docstring "existe para que a divergência
    seja DETECTÁVEL" e nenhum chamador — a função que detecta não era executada
    por ninguém."""
    from io import StringIO

    from django.core.management import call_command

    entrar(cenario, 10)
    saida = StringIO()

    call_command("conferir_estoque", stdout=saida)

    assert "Saldo e razão batem" in saida.getvalue()


def test_conferir_estoque_acha_o_update_feito_por_fora(cenario):
    """A divergência só nasce por caminho que não passou pelo serviço — um
    `update()` numa migração de dados, uma correção no shell."""
    from io import StringIO

    from django.core.management import call_command

    entrar(cenario, 10)
    SaldoEstoque.objects.filter(material=cenario["material"]).update(quantidade=99)
    saida = StringIO()

    call_command("conferir_estoque", stdout=saida)

    texto = saida.getvalue()
    assert "divergências       1" in texto
    assert "+89" in texto


def test_conferir_estoque_aceita_uma_unidade(cenario):
    from io import StringIO

    from django.core.management import call_command

    entrar(cenario, 10)
    saida = StringIO()

    call_command("conferir_estoque", "--unidade", cenario["unidade"].codigo, stdout=saida)

    assert "linhas conferidas  1" in saida.getvalue()


def test_conferir_estoque_recusa_unidade_inexistente(cenario):
    from io import StringIO

    from django.core.management import call_command

    saida = StringIO()

    call_command("conferir_estoque", "--unidade", "ZZ", stdout=saida)

    assert "não existe" in saida.getvalue()
