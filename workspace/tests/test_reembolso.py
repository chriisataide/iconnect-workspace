"""RMB — reembolso item a item e o acerto do adiantamento.

O que estes testes protegem, em uma frase cada:

1. **Quem soma é o sistema.** O total do pedido é a soma das linhas, e o que
   vier no campo `valor` do POST é ignorado — era o total digitado que divergia
   dos comprovantes.
2. **Um comprovante por compra.** Cada `DespesaReembolso` tem o seu anexo; o
   vínculo é o que faz a conferência deixar de ser adivinhação.
3. **O adiantamento fecha.** Sobrou, devolve com comprovante; faltou, a empresa
   paga na conta informada. Sem lado nenhum ficar em aberto por omissão.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.models import (
    AcertoAdiantamento,
    DespesaReembolso,
    GrupoCatalogo,
    ItemCatalogo,
    SentidoAcerto,
    SituacaoServico,
    SolicitacaoServico,
    TipoCampo,
)
from workspace.services import catalogo as svc
from workspace.services import reembolso as rmb
from workspace.services.catalogo import SolicitacaoError
from workspace.services.reembolso import ReembolsoError


def cupom(nome: str = "cupom.jpg") -> SimpleUploadedFile:
    """JPEG com os magic bytes de verdade — é o que o validador confere."""
    return SimpleUploadedFile(
        nome, b"\xff\xd8\xff\xe0" + b"0" * 32, content_type="image/jpeg"
    )


def linha(valor="100", motivo="Almoço com cliente", arquivo=None) -> rmb.Linha:
    return rmb.Linha(
        valor=Decimal(valor),
        motivo=motivo,
        arquivo=arquivo if arquivo is not None else cupom(),
    )


@pytest.fixture
def item_reembolso():
    return ItemCatalogo.objects.create(
        chave="reembolso",
        nome="Reembolso",
        grupo=GrupoCatalogo.DINHEIRO,
        dominio="fin.reembolso",
        exige_valor=True,
        campos=[
            {"chave": "despesas", "rotulo": "Compras",
             "tipo": TipoCampo.DESPESAS, "obrigatorio": True},
            {"chave": "adiantamento", "rotulo": "Adiantamento",
             "tipo": TipoCampo.ADIANTAMENTO, "obrigatorio": False},
        ],
        limite_auto_aprovacao=Decimal("100000"),
    )


@pytest.fixture
def item_adiantamento():
    return ItemCatalogo.objects.create(
        chave="adiantamento",
        nome="Adiantamento",
        grupo=GrupoCatalogo.DINHEIRO,
        dominio="fin.adiantamento",
        exige_valor=True,
        campos=[{"chave": "motivo", "rotulo": "Motivo", "obrigatorio": True}],
        limite_auto_aprovacao=Decimal("100000"),
    )


@pytest.fixture
def ana():
    pessoa = f.pessoa("ana")
    f.lotar(pessoa)
    return pessoa


def adiantar(item, pessoa, valor="1000", situacao=SituacaoServico.APROVADA, **dados):
    """Um adiantamento já liberado — o dinheiro saiu, e ele deve prestação."""
    return SolicitacaoServico.objects.create(
        item=item,
        solicitante=pessoa,
        valor=Decimal(valor),
        situacao=situacao,
        dados={"motivo": "Viagem a Campinas", **dados},
    )


# ── Leitura do que a pessoa digitou ─────────────────────────────────


@pytest.mark.parametrize(
    "bruto,esperado",
    [
        ("1.234,56", Decimal("1234.56")),
        ("1234.56", Decimal("1234.56")),
        ("80", Decimal("80.00")),
        ("", None),
        (None, None),
        ("abc", None),
    ],
)
def test_valor_aceita_o_jeito_que_a_pessoa_digita(bruto, esperado):
    """Vírgula decimal é como se escreve dinheiro em português. Recusar
    `1.234,56` seria recusar o formato que o próprio sistema imprime."""
    assert rmb.valor_de(bruto) == esperado


def test_total_soma_as_linhas():
    assert rmb.total([linha(valor="10.50"), linha(valor="4.50")]) == Decimal("15.00")


def test_total_de_lista_vazia_e_zero():
    assert rmb.total([]) == Decimal("0")


# ── O que barra uma linha ───────────────────────────────────────────


def test_sem_nenhuma_compra_nao_ha_o_que_reembolsar():
    assert rmb.verificar_linhas([]) == [
        "Adicione ao menos uma compra, com comprovante e valor."
    ]


def test_linha_incompleta_diz_o_que_falta_em_cada_uma():
    """Todos os motivos de uma vez, e numerados: corrigir um erro por envio é o
    que faz a pessoa desistir no terceiro."""
    motivos = rmb.verificar_linhas([
        rmb.Linha(valor=None, motivo="", arquivo=None),
        linha(),
    ])
    assert "Compra 1: informe o valor." in motivos
    assert "Compra 1: informe o motivo." in motivos
    assert "Compra 1: anexe o comprovante." in motivos
    assert not [m for m in motivos if m.startswith("Compra 2")]


def test_valor_negativo_e_recusado():
    motivos = rmb.verificar_linhas([linha(valor="-5")])
    assert "Compra 1: o valor tem de ser positivo." in motivos


def test_teto_de_compras_por_reembolso():
    """Prestação de contas com dezenas de compras não é conferida, é carimbada."""
    motivos = rmb.verificar_linhas([linha() for _ in range(rmb.MAXIMO_DESPESAS + 1)])
    assert f"No máximo {rmb.MAXIMO_DESPESAS} compras por reembolso." in motivos


def test_arquivo_que_nao_e_o_que_diz_ser_e_recusado():
    """A validação por magic bytes é a mesma dos anexos — não há segundo
    caminho de upload com regra própria."""
    falso = SimpleUploadedFile("cupom.jpg", b"MZ\x90\x00 nao sou jpeg",
                               content_type="image/jpeg")
    motivos = rmb.verificar_linhas([linha(arquivo=falso)])
    assert any(m.startswith("Compra 1:") for m in motivos)


# ── Gravação ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_pedido_soma_as_linhas_e_ignora_o_valor_digitado(item_reembolso, ana):
    """O ponto do módulo: o total do pedido é a soma dos comprovantes."""
    pedido = svc.solicitar(
        item_reembolso,
        ana,
        valor=Decimal("9999"),  # mentira vinda da tela
        linhas=[linha(valor="30"), linha(valor="12.50")],
    )
    assert pedido.valor == Decimal("42.50")
    assert pedido.total_despesas == Decimal("42.50")


@pytest.mark.django_db
def test_cada_compra_guarda_o_seu_comprovante(item_reembolso, ana):
    svc.solicitar(
        item_reembolso,
        ana,
        linhas=[
            linha(valor="30", motivo="Táxi", arquivo=cupom("taxi.jpg")),
            linha(valor="12", motivo="Café", arquivo=cupom("cafe.jpg")),
        ],
    )
    despesas = list(DespesaReembolso.objects.order_by("ordem"))
    assert [(d.motivo, d.valor) for d in despesas] == [
        ("Táxi", Decimal("30.00")),
        ("Café", Decimal("12.00")),
    ]
    assert [d.anexo.nome_original for d in despesas] == ["taxi.jpg", "cafe.jpg"]


@pytest.mark.django_db
def test_reembolso_sem_compra_nenhuma_nao_e_criado(item_reembolso, ana):
    with pytest.raises(SolicitacaoError, match="ao menos uma compra"):
        svc.solicitar(item_reembolso, ana, linhas=[])
    assert not SolicitacaoServico.objects.exists()


@pytest.mark.django_db
def test_linha_ruim_nao_deixa_pedido_pela_metade(item_reembolso, ana):
    """Tudo-ou-nada: pedido criado com duas das três compras é um pedido que a
    pessoa não sabe que está errado."""
    with pytest.raises(SolicitacaoError):
        svc.solicitar(
            item_reembolso,
            ana,
            linhas=[linha(), rmb.Linha(valor=None, motivo="", arquivo=None)],
        )
    assert not SolicitacaoServico.objects.exists()
    assert not DespesaReembolso.objects.exists()


# ── Quais adiantamentos aparecem ────────────────────────────────────


@pytest.mark.django_db
def test_adiantamento_liberado_fica_pendente_de_prestacao(item_adiantamento, ana):
    adiantamento = adiantar(item_adiantamento, ana)
    assert list(rmb.adiantamentos_pendentes(ana)) == [adiantamento]


@pytest.mark.django_db
def test_adiantamento_ainda_em_aprovacao_nao_deve_prestacao(item_adiantamento, ana):
    """Não há o que prestar contas de dinheiro que não saiu."""
    adiantar(item_adiantamento, ana, situacao=SituacaoServico.AGUARDANDO_APROVACAO)
    assert not rmb.adiantamentos_pendentes(ana).exists()


@pytest.mark.django_db
def test_adiantamento_de_outra_pessoa_nao_aparece(item_adiantamento, ana):
    outra = f.pessoa("bruno")
    f.lotar(outra)
    adiantar(item_adiantamento, outra)
    assert not rmb.adiantamentos_pendentes(ana).exists()


@pytest.mark.django_db
def test_adiantamento_ja_prestado_sai_da_lista(item_reembolso, item_adiantamento, ana):
    adiantamento = adiantar(item_adiantamento, ana)
    svc.solicitar(item_reembolso, ana, linhas=[linha()], adiantamento=adiantamento)
    assert not rmb.adiantamentos_pendentes(ana).exists()


@pytest.mark.django_db
def test_prestacao_cancelada_devolve_o_adiantamento_a_lista(
    item_reembolso, item_adiantamento, ana
):
    """Cancelamento acidental não pode trancar a pessoa para sempre sem ter
    como prestar contas."""
    adiantamento = adiantar(item_adiantamento, ana)
    prestacao = svc.solicitar(
        item_reembolso, ana, linhas=[linha()], adiantamento=adiantamento
    )
    prestacao.situacao = SituacaoServico.CANCELADA
    prestacao.save(update_fields=["situacao"])

    assert list(rmb.adiantamentos_pendentes(ana)) == [adiantamento]


@pytest.mark.django_db
def test_atrelar_adiantamento_alheio_e_impossivel(item_adiantamento, ana):
    """A busca acontece dentro dos pendentes DA PESSOA — não é um id que se
    adivinha e o servidor confere depois."""
    outra = f.pessoa("bruno")
    f.lotar(outra)
    alheio = adiantar(item_adiantamento, outra)

    with pytest.raises(ReembolsoError, match="não está pendente"):
        rmb.adiantamento_escolhido(ana, str(alheio.pk))


@pytest.mark.django_db
def test_sem_escolha_nao_ha_adiantamento(ana):
    assert rmb.adiantamento_escolhido(ana, "") is None
    assert rmb.adiantamento_escolhido(ana, None) is None


@pytest.mark.django_db
def test_id_que_nao_e_numero_e_recusado(ana):
    with pytest.raises(ReembolsoError, match="inválido"):
        rmb.adiantamento_escolhido(ana, "dez")


# ── A conta ─────────────────────────────────────────────────────────


@pytest.mark.django_db
@pytest.mark.parametrize(
    "adiantado,gasto,sentido,diferenca",
    [
        ("10", "5", SentidoAcerto.DEVOLVER, "5.00"),
        ("10", "15", SentidoAcerto.RECEBER, "5.00"),
        ("10", "10", SentidoAcerto.QUITADO, "0.00"),
    ],
)
def test_o_lado_para_o_qual_a_diferenca_corre(
    item_reembolso, item_adiantamento, ana, adiantado, gasto, sentido, diferenca
):
    adiantamento = adiantar(item_adiantamento, ana, valor=adiantado)
    prestacao = svc.solicitar(
        item_reembolso, ana, linhas=[linha(valor=gasto)], adiantamento=adiantamento
    )

    conta = rmb.calcular_acerto(prestacao)
    assert conta.sentido == sentido
    # Sempre o módulo: "-5,00" numa tela de devolução faz a pessoa perguntar se
    # deve devolver ou receber.
    assert conta.diferenca == Decimal(diferenca)


@pytest.mark.django_db
def test_reembolso_sem_adiantamento_nao_tem_acerto(item_reembolso, ana):
    pedido = svc.solicitar(item_reembolso, ana, linhas=[linha()])
    assert rmb.calcular_acerto(pedido) is None


# ── Fechar a conta ──────────────────────────────────────────────────


@pytest.fixture
def sobrou(item_reembolso, item_adiantamento, ana):
    """Adiantou 100, gastou 40 — a pessoa devolve 60."""
    adiantamento = adiantar(item_adiantamento, ana, valor="100")
    return svc.solicitar(
        item_reembolso, ana, linhas=[linha(valor="40")], adiantamento=adiantamento
    )


@pytest.fixture
def faltou(item_reembolso, item_adiantamento, ana):
    """Adiantou 100, gastou 160 — a empresa paga 60."""
    adiantamento = adiantar(
        item_adiantamento, ana, valor="100", dados_bancarios="Banco 1 · ag 2 · cc 3"
    )
    return svc.solicitar(
        item_reembolso, ana, linhas=[linha(valor="160")], adiantamento=adiantamento
    )


@pytest.mark.django_db
def test_devolucao_exige_comprovante(sobrou, ana):
    """Sem o comprovante, o acerto seria a pessoa dizendo que devolveu — que é
    exatamente o que já acontecia por fora do sistema."""
    with pytest.raises(ReembolsoError, match="comprovante da devolução"):
        rmb.confirmar_acerto(sobrou, ana)


@pytest.mark.django_db
def test_devolucao_registrada_guarda_o_comprovante(sobrou, ana):
    acerto = rmb.confirmar_acerto(sobrou, ana, comprovante=cupom("deposito.jpg"))

    assert acerto.sentido == SentidoAcerto.DEVOLVER
    assert acerto.diferenca == Decimal("60.00")
    assert acerto.comprovante.nome_original == "deposito.jpg"
    assert acerto.confirmado_por == ana


@pytest.mark.django_db
def test_pagamento_a_pessoa_exige_a_conta(faltou, ana):
    with pytest.raises(ReembolsoError, match="onde a empresa deve depositar"):
        rmb.confirmar_acerto(faltou, ana)


@pytest.mark.django_db
def test_pagamento_a_pessoa_guarda_a_conta_informada(faltou, ana):
    acerto = rmb.confirmar_acerto(faltou, ana, dados_bancarios="Banco 9 · ag 1 · cc 7")

    assert acerto.sentido == SentidoAcerto.RECEBER
    assert acerto.diferenca == Decimal("60.00")
    assert acerto.dados_bancarios == "Banco 9 · ag 1 · cc 7"


@pytest.mark.django_db
def test_conta_do_adiantamento_e_sugerida(faltou):
    """Pré-preencher aqui é o oposto de adivinhar: é o dado que a própria
    pessoa digitou neste mesmo fluxo."""
    assert rmb.conta_sugerida(faltou) == "Banco 1 · ag 2 · cc 3"


@pytest.mark.django_db
def test_conta_certa_ainda_assim_vira_registro(item_reembolso, item_adiantamento, ana):
    """"Não houve diferença" e "ninguém conferiu" são estados diferentes."""
    adiantamento = adiantar(item_adiantamento, ana, valor="50")
    prestacao = svc.solicitar(
        item_reembolso, ana, linhas=[linha(valor="50")], adiantamento=adiantamento
    )

    acerto = rmb.confirmar_acerto(prestacao, ana)
    assert acerto.sentido == SentidoAcerto.QUITADO
    assert acerto.diferenca == Decimal("0.00")


@pytest.mark.django_db
def test_acerto_nao_e_confirmado_duas_vezes(sobrou, ana):
    rmb.confirmar_acerto(sobrou, ana, comprovante=cupom())
    with pytest.raises(ReembolsoError, match="já foi confirmado"):
        rmb.confirmar_acerto(sobrou, ana, comprovante=cupom())
    assert AcertoAdiantamento.objects.count() == 1


@pytest.mark.django_db
def test_so_quem_prestou_contas_fecha_a_conta(sobrou):
    outra = f.pessoa("bruno")
    f.lotar(outra)
    with pytest.raises(ReembolsoError, match="Só quem prestou contas"):
        rmb.confirmar_acerto(sobrou, outra, comprovante=cupom())


@pytest.mark.django_db
def test_pedido_sem_adiantamento_nao_tem_o_que_fechar(item_reembolso, ana):
    pedido = svc.solicitar(item_reembolso, ana, linhas=[linha()])
    with pytest.raises(ReembolsoError, match="não presta contas"):
        rmb.confirmar_acerto(pedido, ana)


# ── As telas ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_formulario_mostra_as_compras_e_esconde_o_valor(client, item_reembolso, ana):
    """Item a item, um campo de total editável seria a volta do problema que a
    lista veio resolver."""
    client.force_login(ana)
    html = client.get(
        reverse("workspace:pedir", args=["reembolso"])
    ).content.decode()

    assert 'name="despesa_valor_0"' in html
    assert 'name="despesa_anexo_0"' in html
    assert 'name="valor"' not in html


@pytest.mark.django_db
def test_formulario_lista_os_adiantamentos_pendentes(
    client, item_reembolso, item_adiantamento, ana
):
    adiantamento = adiantar(item_adiantamento, ana)
    client.force_login(ana)
    html = client.get(
        reverse("workspace:pedir", args=["reembolso"])
    ).content.decode()

    assert f'name="adiantamento" value="{adiantamento.pk}"' in html


@pytest.mark.django_db
def test_enviar_duas_compras_cria_as_duas_linhas(client, item_reembolso, ana):
    client.force_login(ana)
    resposta = client.post(
        reverse("workspace:pedir", args=["reembolso"]),
        {
            "despesa_indice": ["0", "1"],
            "despesa_valor_0": "30,00",
            "despesa_motivo_0": "Táxi",
            "despesa_anexo_0": cupom("taxi.jpg"),
            "despesa_valor_1": "12,50",
            "despesa_motivo_1": "Café",
            "despesa_anexo_1": cupom("cafe.jpg"),
        },
    )

    assert resposta.status_code == 302
    pedido = SolicitacaoServico.objects.get()
    assert pedido.valor == Decimal("42.50")
    assert pedido.despesas.count() == 2


@pytest.mark.django_db
def test_linha_em_branco_nao_impede_o_envio(client, item_reembolso, ana):
    """Uma linha aberta por engano é um clique a mais, não um erro."""
    client.force_login(ana)
    resposta = client.post(
        reverse("workspace:pedir", args=["reembolso"]),
        {
            "despesa_indice": ["0", "1"],
            "despesa_valor_0": "30,00",
            "despesa_motivo_0": "Táxi",
            "despesa_anexo_0": cupom(),
            "despesa_valor_1": "",
            "despesa_motivo_1": "",
        },
    )

    assert resposta.status_code == 302
    assert SolicitacaoServico.objects.get().despesas.count() == 1


@pytest.mark.django_db
def test_erro_nas_compras_volta_com_o_que_foi_digitado(client, item_reembolso, ana):
    """Formulário que se esvazia no erro é o que faz a pessoa mandar e-mail."""
    client.force_login(ana)
    html = client.post(
        reverse("workspace:pedir", args=["reembolso"]),
        {
            "despesa_indice": ["0"],
            "despesa_valor_0": "30,00",
            "despesa_motivo_0": "Táxi sem cupom",
        },
    ).content.decode()

    assert "anexe o comprovante" in html.lower()
    assert "Táxi sem cupom" in html
    assert not SolicitacaoServico.objects.exists()


@pytest.mark.django_db
def test_valor_que_nao_e_numero_volta_como_campo_vazio(client, item_reembolso, ana):
    """"abc" não vira zero: zero seria uma compra de graça entrando na soma.
    O campo volta em branco, com o motivo preservado e o erro à vista."""
    client.force_login(ana)
    html = client.post(
        reverse("workspace:pedir", args=["reembolso"]),
        {
            "despesa_indice": ["0"],
            "despesa_valor_0": "abc",
            "despesa_motivo_0": "Almoço",
            "despesa_anexo_0": cupom(),
        },
    ).content.decode()

    assert "informe o valor" in html.lower()
    assert 'value="Almoço"' in html
    assert not SolicitacaoServico.objects.exists()


@pytest.mark.django_db
def test_atrelar_adiantamento_leva_direto_ao_acerto(
    client, item_reembolso, item_adiantamento, ana
):
    """A conta não pode ficar aberta sem a pessoa saber que faltava um passo."""
    adiantamento = adiantar(item_adiantamento, ana, valor="100")
    client.force_login(ana)
    resposta = client.post(
        reverse("workspace:pedir", args=["reembolso"]),
        {
            "despesa_indice": ["0"],
            "despesa_valor_0": "40,00",
            "despesa_motivo_0": "Táxi",
            "despesa_anexo_0": cupom(),
            "adiantamento": str(adiantamento.pk),
        },
    )

    pedido = SolicitacaoServico.objects.get(adiantamento=adiantamento)
    assert resposta["Location"] == reverse("workspace:acerto", args=[pedido.pk])


@pytest.mark.django_db
def test_tela_de_acerto_mostra_a_conta(client, sobrou, ana):
    client.force_login(ana)
    html = client.get(reverse("workspace:acerto", args=[sobrou.pk])).content.decode()

    assert "60,00" in html
    assert 'name="comprovante"' in html


@pytest.mark.django_db
def test_acerto_recusado_explica_na_tela(client, sobrou, ana):
    client.force_login(ana)
    resposta = client.post(reverse("workspace:acerto", args=[sobrou.pk]), {})

    assert resposta.status_code == 200
    assert "comprovante da devolução" in resposta.content.decode()
    assert not AcertoAdiantamento.objects.exists()


@pytest.mark.django_db
def test_acerto_confirmado_pela_tela(client, faltou, ana):
    client.force_login(ana)
    resposta = client.post(
        reverse("workspace:acerto", args=[faltou.pk]),
        {"dados_bancarios": "Banco 9 · ag 1 · cc 7"},
    )

    assert resposta.status_code == 302
    assert AcertoAdiantamento.objects.get().sentido == SentidoAcerto.RECEBER


@pytest.mark.django_db
def test_acerto_de_pedido_alheio_nao_abre(client, sobrou):
    outra = f.pessoa("bruno")
    f.lotar(outra)
    client.force_login(outra)
    assert client.get(reverse("workspace:acerto", args=[sobrou.pk])).status_code == 404


@pytest.mark.django_db
def test_quem_aprova_ve_compra_por_compra(client, item_reembolso, ana):
    """Itemizar só para o lado de quem pede teria deixado a bandeja igual: um
    total e imagens soltas, com a soma refeita à mão."""
    from workspace.models import RegraAprovacao, TipoAprovador

    gestor = f.pessoa("gestor")
    f.lotar(gestor)
    ana.lotacao.gestor = gestor
    ana.lotacao.save(update_fields=["gestor"])
    RegraAprovacao.objects.create(
        dominio="*", tipo=TipoAprovador.GESTOR_DIRETO, ordem=10
    )
    item_reembolso.limite_auto_aprovacao = None  # sempre passa pela cadeia
    item_reembolso.save(update_fields=["limite_auto_aprovacao"])

    svc.solicitar(
        item_reembolso,
        ana,
        linhas=[
            linha(valor="30", motivo="Táxi até o cliente"),
            linha(valor="12", motivo="Estacionamento"),
        ],
    )

    client.force_login(gestor)
    html = client.get(reverse("workspace:aprovacoes")).content.decode()

    assert "Táxi até o cliente" in html
    assert "Estacionamento" in html
    assert "30,00" in html


@pytest.mark.django_db
def test_acerto_de_pedido_que_nao_presta_contas_nao_existe(
    client, item_reembolso, ana
):
    pedido = svc.solicitar(item_reembolso, ana, linhas=[linha()])
    client.force_login(ana)
    assert client.get(
        reverse("workspace:acerto", args=[pedido.pk])
    ).status_code == 404
