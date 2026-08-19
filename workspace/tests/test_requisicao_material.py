"""§16 — pedir do estoque, com o saldo mandando.

O fluxo inteiro num arquivo, porque é nas juntas que ele quebra:

    escolhe da lista → o envio confere o saldo → a entrega dá baixa

## As três decisões que estes testes protegem

1. **A conferência é no ENVIO, não no atendimento.** Deixar o pedido entrar e
   recusá-lo três dias depois na fila é o pior dos dois mundos: a pessoa
   esperou, Suprimentos gastou o atendimento, e a informação que faltava estava
   disponível no primeiro segundo.

2. **Enviar não RESERVA.** Reservar criaria saldo preso por pedido que ninguém
   aprovou — o material some do estoque de quem precisa hoje por causa de um
   pedido de daqui a duas semanas.

3. **A baixa acontece ANTES de marcar concluído**, dentro da mesma transação.
   Concluir primeiro e baixar depois deixaria pedido entregue com estoque
   intacto, e a diferença só apareceria na contagem física.

A corrida por concorrência é resolvida na baixa, onde `movimentar()` trava a
linha de saldo — e não no envio, onde travar não adiantaria nada.
"""

from __future__ import annotations

import pytest

from identidade.tests import fabricas as f
from workspace.models.catalogo import ItemCatalogo, SituacaoServico
from workspace.models.estoque import Material, MovimentoEstoque, TipoMovimento
from workspace.services import atendimento as atd
from workspace.services import catalogo as svc
from workspace.services import estoque as est
from workspace.services.atendimento import AtendimentoError
from workspace.services.catalogo import SolicitacaoError

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    unidade = f.unidade()
    ana, almox = f.pessoa("ana"), f.pessoa("almoxarife")
    f.lotar(ana, uni=unidade)
    f.lotar(almox, uni=unidade)
    f.atribuir(almox, f.papel("sup", ["log.atender.global"], escopo="global"))

    capacete = Material.objects.create(
        codigo="capacete", nome="Capacete", categoria="epi"
    )
    est.movimentar(capacete, unidade, TipoMovimento.ENTRADA, 10)

    item = ItemCatalogo.objects.create(
        chave="requisicao-material", nome="Requisição de material",
        grupo="espaco", dominio="log.requisicao", prazo_prometido_dias=2,
        limite_auto_aprovacao=0,
        campos=[
            {"chave": "material", "rotulo": "Material", "tipo": "escolha",
             "obrigatorio": True, "opcoes": [], "dinamico": True},
            {"chave": "quantidade", "rotulo": "Quantidade", "tipo": "numero",
             "obrigatorio": True},
            {"chave": "finalidade", "rotulo": "Para que vai usar", "tipo": "texto",
             "obrigatorio": True},
        ],
    )
    return {
        "unidade": unidade, "ana": ana, "almox": almox,
        "material": capacete, "item": item,
    }


def pedir(cenario, quantidade=3, codigo="capacete"):
    return svc.solicitar(
        cenario["item"], cenario["ana"],
        {"material": codigo, "quantidade": str(quantidade), "finalidade": "Obra Alfa"},
    )


# ── A lista vem do estoque ──────────────────────────────────────────


def test_a_lista_de_materiais_vem_do_saldo_da_unidade(cenario):
    campos = svc.campos_do_item(cenario["item"], cenario["ana"])
    material = next(c for c in campos if c["chave"] == "material")

    assert [o["valor"] for o in material["opcoes"]] == ["capacete"]
    assert "10" in material["opcoes"][0]["rotulo"], "o saldo tem de estar no rótulo"


def test_material_zerado_sai_da_lista(cenario):
    """Mostrá-lo produziria um pedido recusado no envio; mostrá-lo desabilitado
    ensinaria que existe, o que não ajuda quem precisa dele hoje."""
    est.movimentar(cenario["material"], cenario["unidade"], TipoMovimento.SAIDA, 10)

    campos = svc.campos_do_item(cenario["item"], cenario["ana"])
    assert next(c for c in campos if c["chave"] == "material")["opcoes"] == []


def test_quem_nao_tem_unidade_recebe_lista_vazia(cenario):
    """Sem lotação não há de onde tirar material — e a tela diz isso em vez de
    oferecer o estoque de outra unidade."""
    sem_lotacao = f.pessoa("visitante")

    campos = svc.campos_do_item(cenario["item"], sem_lotacao)
    assert next(c for c in campos if c["chave"] == "material")["opcoes"] == []


# ── O envio confere o saldo ─────────────────────────────────────────


def test_pedido_dentro_do_saldo_passa(cenario):
    pedido = pedir(cenario, 3)

    assert pedido.situacao == SituacaoServico.APROVADA


def test_pedido_acima_do_saldo_e_recusado_no_envio(cenario):
    with pytest.raises(SolicitacaoError, match="Há 10"):
        pedir(cenario, 11)


def test_a_recusa_diz_o_saldo_a_unidade_e_o_pedido(cenario):
    """Três números, e os três importam: sem o saldo a pessoa tenta de novo às
    cegas; sem a unidade ela acha que a empresa inteira não tem."""
    impedimentos = svc.verificar(
        cenario["item"], cenario["ana"],
        {"material": "capacete", "quantidade": "11", "finalidade": "x"},
    )
    motivo = impedimentos[0].motivo

    assert "10" in motivo and cenario["unidade"].nome in motivo and "11" in motivo


def test_material_fora_do_cadastro_e_recusado(cenario):
    """A lista é fechada dos dois lados: o `<select>` guia, e aqui é onde um
    valor forjado no POST para de valer."""
    with pytest.raises(SolicitacaoError, match="não está no cadastro"):
        pedir(cenario, 1, codigo="foguete")


@pytest.mark.parametrize("quantidade", ["0", "-3"])
def test_quantidade_sem_sentido_e_recusada(cenario, quantidade):
    with pytest.raises(SolicitacaoError, match="maior que zero"):
        pedir(cenario, quantidade)


def test_quantidade_que_nao_e_numero_e_recusada(cenario):
    with pytest.raises(SolicitacaoError, match="número"):
        pedir(cenario, "muitos")


def test_enviar_nao_reserva_saldo(cenario):
    """Reservar no envio prenderia material por pedido que ninguém aprovou."""
    pedir(cenario, 3)

    assert est.saldo_de(cenario["material"], cenario["unidade"]) == 10


# ── A entrega dá baixa ──────────────────────────────────────────────


def test_concluir_da_baixa_no_saldo(cenario):
    pedido = pedir(cenario, 3)

    atd.concluir(pedido, cenario["almox"])

    assert est.saldo_de(cenario["material"], cenario["unidade"]) == 7


def test_a_baixa_diz_de_quem_foi_o_pedido(cenario):
    """Sem a amarração, a saída fica no razão sem dizer para quem foi — e "quem
    levou os dez capacetes de março" volta a ser respondido por memória."""
    pedido = pedir(cenario, 3)
    atd.concluir(pedido, cenario["almox"])

    saida = MovimentoEstoque.objects.get(tipo=TipoMovimento.SAIDA)
    assert saida.origem_id == str(pedido.pk)
    assert saida.quem == cenario["almox"]
    assert cenario["ana"].get_full_name() in saida.observacao


def test_a_baixa_e_na_unidade_de_quem_pediu(cenario):
    """Suprimentos de São Paulo despachando para Campinas dá baixa em Campinas,
    que é onde o capacete estava."""
    outra = f.unidade(codigo="SP2", nome="Outra")
    from identidade.models import Lotacao

    Lotacao.objects.filter(user=cenario["almox"]).update(unidade=outra)
    pedido = pedir(cenario, 3)

    atd.concluir(pedido, cenario["almox"])

    assert est.saldo_de(cenario["material"], cenario["unidade"]) == 7
    assert est.saldo_de(cenario["material"], outra) == 0


def test_saldo_que_acabou_entre_o_pedido_e_a_entrega_impede_concluir(cenario):
    """O caso que só a baixa pega: dois pedidos passam na validação porque
    naquele instante cabiam, e o segundo chega na entrega sem material."""
    primeiro = pedir(cenario, 6)
    segundo = pedir(cenario, 6)
    atd.concluir(primeiro, cenario["almox"])

    with pytest.raises(AtendimentoError, match="Saldo insuficiente"):
        atd.concluir(segundo, cenario["almox"])


def test_a_conclusao_recusada_nao_fecha_o_pedido(cenario):
    """A baixa vem ANTES de marcar concluído, e é isso que dá o "ou nada" da
    transação: pedido entregue com estoque intacto é a divergência que só
    aparece na contagem física, meses depois."""
    primeiro = pedir(cenario, 6)
    segundo = pedir(cenario, 6)
    atd.concluir(primeiro, cenario["almox"])

    with pytest.raises(AtendimentoError):
        atd.concluir(segundo, cenario["almox"])

    segundo.refresh_from_db()
    assert segundo.situacao != SituacaoServico.CONCLUIDA
    assert segundo.concluido_em is None


def test_pedido_que_nao_e_de_material_conclui_sem_tocar_estoque(cenario):
    """A baixa é silenciosa para item que não tem os campos — senão todo
    pedido do produto passaria a depender do cadastro de estoque."""
    outro = ItemCatalogo.objects.create(
        chave="acesso-x", nome="Acesso", grupo="equipamento", dominio="log.requisicao",
        prazo_prometido_dias=1, limite_auto_aprovacao=0,
        campos=[{"chave": "motivo", "rotulo": "Motivo", "obrigatorio": True}],
    )
    pedido = svc.solicitar(outro, cenario["ana"], {"motivo": "preciso"})

    atd.concluir(pedido, cenario["almox"])

    assert not MovimentoEstoque.objects.filter(tipo=TipoMovimento.SAIDA).exists()


def test_o_razao_continua_batendo_depois_do_ciclo(cenario):
    pedido = pedir(cenario, 4)
    atd.concluir(pedido, cenario["almox"])

    gravado, somado = est.conferir_razao(cenario["material"], cenario["unidade"])
    assert gravado == somado == 6
