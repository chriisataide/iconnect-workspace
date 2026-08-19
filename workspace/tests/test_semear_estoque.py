"""Os dois comandos de semente que este lote criou ou mudou.

`semear_estoque` existe porque sem material cadastrado a requisição do §16
mostra um `<select>` vazio: não há como testar o fluxo de ponta a ponta nem
descobrir que ele funciona.

`semear_catalogo --atualizar` existe porque o docstring do comando prometia,
desde a primeira versão, que campos divergentes eram sincronizados — e **não
eram**: o laço fazia `continue` em todo item existente. O efeito é que toda
mudança de formulário do produto só chegava a instalação limpa, e o banco que já
roda ficava no formulário do dia em que nasceu.
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command

from identidade.models import Unidade
from identidade.tests import fabricas as f
from workspace.models.catalogo import GrupoCatalogo, ItemCatalogo
from workspace.models.estoque import Material, MovimentoEstoque, TipoMovimento
from workspace.services import estoque as est

pytestmark = pytest.mark.django_db


def semear_estoque(*args):
    saida = StringIO()
    call_command("semear_estoque", *args, stdout=saida)
    return saida.getvalue()


# ── semear_estoque ──────────────────────────────────────────────────


def test_sem_unidade_o_comando_recusa_e_explica():
    """O saldo é POR UNIDADE — sem nenhuma cadastrada ele não teria onde morar,
    e criar material sem saldo deixaria o cadastro pela metade."""
    assert not Unidade.objects.exists()

    saida = semear_estoque("--aplicar")

    assert "Nenhuma unidade cadastrada" in saida
    assert "semear_perfis" in saida, "a mensagem tem de dizer o que fazer"
    assert not Material.objects.exists()


def test_semeia_materiais_com_saldo_inicial():
    unidade = f.unidade()

    semear_estoque("--aplicar")

    assert Material.objects.count() >= 10
    capacete = Material.objects.get(codigo="capacete")
    assert est.saldo_de(capacete, unidade) == 20


def test_o_saldo_inicial_nasce_do_razao_e_nao_solto():
    """Saldo sem linha de razão nasceria já sem explicação, e a conferência
    acusaria divergência no primeiro dia."""
    unidade = f.unidade()
    semear_estoque("--aplicar")
    capacete = Material.objects.get(codigo="capacete")

    entrada = MovimentoEstoque.objects.get(
        material=capacete, tipo=TipoMovimento.ENTRADA
    )
    assert entrada.saldo_anterior == 0
    assert est.conferir_razao(capacete, unidade) == (20, 20)


def test_simulacao_nao_grava():
    f.unidade()

    saida = semear_estoque()

    assert "SIMULAÇÃO" in saida
    assert not Material.objects.exists()


def test_e_reexecutavel_sem_duplicar():
    f.unidade()
    semear_estoque("--aplicar")
    antes = Material.objects.count()

    saida = semear_estoque("--aplicar")

    assert Material.objects.count() == antes
    assert f"já existiam  {antes}" in saida


def test_reexecutar_nao_soma_saldo_de_novo():
    """O erro clássico do comando idempotente: pular o cadastro e repetir a
    entrada. O saldo dobraria a cada semeadura."""
    unidade = f.unidade()
    semear_estoque("--aplicar")
    semear_estoque("--aplicar")

    capacete = Material.objects.get(codigo="capacete")
    assert est.saldo_de(capacete, unidade) == 20


# ── semear_catalogo --atualizar ─────────────────────────────────────


def _item_torto():
    return ItemCatalogo.objects.create(
        # `viagem` e não `ferias`: o item de férias saiu do catálogo no §10, e
        # amarrar o teste do COMANDO a um item de negócio faz uma decisão de
        # produto quebrar a suíte de infraestrutura.
        chave="viagem", nome="Nome antigo", grupo=GrupoCatalogo.VIAGEM,
        dominio="log.viagem", prazo_prometido_dias=99, campos=[],
    )


def test_sem_a_flag_o_divergente_e_so_relatado():
    """Não é o padrão porque `opcoes` é editável no admin de propósito: a lista
    de sistemas muda sem deploy, e um `--aplicar` de rotina que sobrescrevesse
    isso apagaria o trabalho de quem mantém a lista."""
    _item_torto()

    saida = StringIO()
    call_command("semear_catalogo", "--aplicar", stdout=saida)

    assert "DIVERGENTES" in saida.getvalue()
    assert "--atualizar" in saida.getvalue(), "tem de dizer como sincronizar"
    assert ItemCatalogo.objects.get(chave="viagem").nome == "Nome antigo"


def test_com_a_flag_o_item_e_sincronizado():
    _item_torto()

    call_command("semear_catalogo", "--atualizar", "--aplicar", stdout=StringIO())

    item = ItemCatalogo.objects.get(chave="viagem")
    assert item.nome == "Viagem"
    assert item.prazo_prometido_dias != 99
    assert item.campos, "o formulário tinha de voltar"


def test_o_relatorio_mostra_campo_a_campo_antes_de_gravar():
    _item_torto()

    saida = StringIO()
    call_command("semear_catalogo", stdout=saida)
    texto = saida.getvalue()

    assert "~ viagem" in texto
    assert "nome:" in texto
    assert "perguntas" in texto, "mudança de formulário tem de aparecer resumida"


def test_atualizar_nao_ressuscita_item_desativado():
    """`ativo` fica FORA dos campos sincronizados: é como uma remoção de produto
    é registrada, e ressuscitá-la a cada semeadura desfaria a decisão em
    silêncio — que é exatamente o modo de falha que o §60 do pedido proíbe."""
    call_command("semear_catalogo", "--aplicar", stdout=StringIO())
    ItemCatalogo.objects.filter(chave="viagem").update(ativo=False)

    call_command("semear_catalogo", "--atualizar", "--aplicar", stdout=StringIO())

    assert ItemCatalogo.objects.get(chave="viagem").ativo is False


def test_item_criado_a_mao_fica_em_paz():
    """Fora da semente, fora do alcance — inclusive de `--atualizar`."""
    proprio = ItemCatalogo.objects.create(
        chave="so-nosso", nome="Item da casa", grupo=GrupoCatalogo.ESPACO,
        dominio="ops.facilities", prazo_prometido_dias=3, campos=[],
    )

    call_command("semear_catalogo", "--atualizar", "--aplicar", stdout=StringIO())

    proprio.refresh_from_db()
    assert proprio.nome == "Item da casa"


def test_semeia_todas_as_unidades_e_com_saldos_diferentes():
    """Semear só a primeira unidade parecia suficiente e não era.

    O saldo é POR UNIDADE, e a requisição só oferece o que existe na unidade de
    quem pede. Com a Matriz semeada e as pessoas lotadas na base, o `<select>`
    de material aparecia vazio: o comando "funcionou" e o fluxo continuou
    intestável — foi assim, abrindo a tela, que isto foi descoberto.

    Os saldos são DIFERENTES entre unidades de propósito: iguais esconderiam o
    bug clássico deste módulo, que é a conta somar a empresa inteira em vez de
    olhar a unidade certa.
    """
    matriz = f.unidade(codigo="MTZ", nome="Matriz")
    base = f.unidade(codigo="BA1", nome="Base Salvador")

    semear_estoque("--aplicar")

    capacete = Material.objects.get(codigo="capacete")
    assert est.saldo_de(capacete, matriz) == 20
    assert est.saldo_de(capacete, base) == 6


# ── A base de conhecimento do assistente ────────────────────────────


def test_semear_faq_cria_a_base_por_area():
    from workspace.models.faq import PerguntaFrequente

    call_command("semear_faq", "--aplicar", stdout=StringIO())

    areas = set(PerguntaFrequente.objects.values_list("area", flat=True))
    assert {"rh", "fin", "log", "ops", "ti"} <= areas
    assert PerguntaFrequente.objects.count() >= 20


def test_toda_pergunta_da_semente_tem_palavras_chave():
    """O defeito mais comum de uma base é a pergunta boa que ninguém acha
    porque a lista de termos ficou vazia."""
    from workspace.faq_inicial import FAQ_INICIAL

    sem = [f_["pergunta"] for f_ in FAQ_INICIAL if not f_.get("palavras_chave")]
    assert not sem, sem


def test_todo_link_da_semente_e_interno():
    """Link para fora daqui envelhece sem ninguém perceber. O interno, quando
    quebra, dá 404 na cara de quem mantém a FAQ."""
    from workspace.faq_inicial import FAQ_INICIAL

    fora = [
        f_["pergunta"] for f_ in FAQ_INICIAL
        if f_.get("url_acao") and not f_["url_acao"].startswith("/workspace/")
    ]
    assert not fora, fora


def test_semear_faq_e_reexecutavel():
    from workspace.models.faq import PerguntaFrequente

    call_command("semear_faq", "--aplicar", stdout=StringIO())
    antes = PerguntaFrequente.objects.count()
    saida = StringIO()

    call_command("semear_faq", "--aplicar", stdout=saida)

    assert PerguntaFrequente.objects.count() == antes
    assert f"já existiam  {antes}" in saida.getvalue()


def test_semear_faq_atualiza_resposta_corrigida():
    """Resposta errada num portal é pior que resposta ausente, porque a pessoa
    age sobre ela — a correção precisa alcançar banco que já roda."""
    from workspace.models.faq import PerguntaFrequente

    call_command("semear_faq", "--aplicar", stdout=StringIO())
    alvo = PerguntaFrequente.objects.filter(area="rh").first()
    PerguntaFrequente.objects.filter(pk=alvo.pk).update(resposta="errado")

    call_command("semear_faq", "--atualizar", "--aplicar", stdout=StringIO())

    alvo.refresh_from_db()
    assert alvo.resposta != "errado"


def test_semear_faq_simula_sem_gravar():
    from workspace.models.faq import PerguntaFrequente

    saida = StringIO()
    call_command("semear_faq", stdout=saida)

    assert "SIMULAÇÃO" in saida.getvalue()
    assert not PerguntaFrequente.objects.exists()
