"""IDOR/BOLA — trocar um número na URL e ler o que é de outro.

## O que este arquivo prova

Que **autenticado não é autorizado**. Todo objeto do produto é endereçado por
um id sequencial na URL — `/workspace/solicitacao/12/cancelar/`,
`/workspace/anexo/40/`, `/workspace/relatorios/7/pdf/` —, e id sequencial é um
convite: quem tem o 12 tenta o 13.

O ataque não precisa de ferramenta. É uma pessoa da empresa, com conta legítima,
mudando um dígito na barra de endereços. E é a falha de controle de acesso mais
comum que existe justamente porque cada rota é escrita num dia diferente: basta
uma esquecer.

## As duas direções, e por que as duas

**Horizontal** — um colaborador contra o objeto de OUTRO colaborador. É o
atestado do colega, o comprovante de reembolso, o rascunho meio escrito.

**Vertical** — um colaborador contra o que exige papel. É a bandeja de
aprovação, a fila de atendimento, a concessão de papéis, o cadastro de centro
de custo.

## Por que a asserção é "o objeto não mudou", e não só o código HTTP

Um 302 pode significar "recusado e devolvido para a lista" ou "feito, redirecionando
para a lista" — e as duas telas são a mesma. Testar só o código deixaria passar
exatamente a falha que se quer pegar. Aqui cada teste vai ao banco depois.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.models import (
    GrupoCatalogo,
    ItemCatalogo,
    Recurso,
    Reserva,
    SituacaoReserva,
    SituacaoServico,
    SolicitacaoServico,
    TipoRecurso,
)
from workspace.services import catalogo as svc

pytestmark = pytest.mark.django_db


@pytest.fixture
def dois():
    """Dono e intruso: dois colaboradores comuns, nenhum com papel nenhum.

    O intruso é o pior caso realista — não é um invasor de fora, é alguém que a
    empresa deu conta e crachá e que decidiu tentar. Ele passa por toda a
    autenticação; o que tem de barrá-lo é só a autorização.
    """
    dono, intruso = f.pessoa("dono"), f.pessoa("intruso")
    f.lotar(dono)
    f.lotar(intruso)
    papel = f.papel("colab", ["rh.ler.proprio", "fin.solicitar.proprio",
                              "res.reservar.proprio", "ti.solicitar.proprio"])
    f.atribuir(dono, papel)
    f.atribuir(intruso, papel)
    return {"dono": dono, "intruso": intruso}


@pytest.fixture
def item():
    return ItemCatalogo.objects.create(
        chave="acesso", nome="Acesso a um sistema", grupo=GrupoCatalogo.EQUIPAMENTO,
        dominio="ti.acesso", prazo_prometido_dias=2,
        campos=[{"chave": "o_que", "rotulo": "O quê", "obrigatorio": True}],
    )


def _pedido_de(pessoa, item, **extras):
    pedido = svc.solicitar(item, pessoa, {"o_que": "VPN"})
    if extras:
        SolicitacaoServico.objects.filter(pk=pedido.pk).update(**extras)
        pedido.refresh_from_db()
    return pedido


# ── Horizontal: o objeto do colega ──────────────────────────────────


def test_nao_cancela_o_pedido_de_outra_pessoa(client, dois, item):
    pedido = _pedido_de(dois["dono"], item)
    client.force_login(dois["intruso"])

    client.post(reverse("workspace:cancelar_solicitacao", args=[pedido.pk]))

    pedido.refresh_from_db()
    assert pedido.situacao != SituacaoServico.CANCELADA


def test_nao_descarta_o_rascunho_de_outra_pessoa(client, dois, item):
    """Descartar é a ÚNICA exclusão do produto. Se ela não checar o dono, um
    dígito na URL apaga o que o colega estava escrevendo."""
    rascunho = svc.salvar_rascunho(item, dois["dono"], {"o_que": "VPN"})
    client.force_login(dois["intruso"])

    client.post(reverse("workspace:descartar_rascunho", args=[rascunho.pk]))

    assert SolicitacaoServico.objects.filter(pk=rascunho.pk).exists()


def test_nao_comenta_no_pedido_de_outra_pessoa(client, dois, item):
    """Comentário é parte do pedido, e o pedido é de duas partes: quem pediu e
    quem atende. Um terceiro não é nenhuma das duas."""
    from workspace.models.comentario import ComentarioSolicitacao

    pedido = _pedido_de(dois["dono"], item)
    client.force_login(dois["intruso"])

    client.post(
        reverse("workspace:comentar_solicitacao", args=[pedido.pk]),
        {"texto": "consigo escrever aqui?"},
    )

    assert not ComentarioSolicitacao.objects.filter(solicitacao=pedido).exists()


def test_nao_reabre_o_pedido_de_outra_pessoa(client, dois, item):
    pedido = _pedido_de(
        dois["dono"], item,
        situacao=SituacaoServico.CONCLUIDA, concluido_em=timezone.now(),
    )
    client.force_login(dois["intruso"])

    client.post(reverse("workspace:reabrir_solicitacao", args=[pedido.pk]))

    pedido.refresh_from_db()
    assert pedido.situacao == SituacaoServico.CONCLUIDA


def test_nao_baixa_o_anexo_de_outra_pessoa(client, dois, item):
    """O anexo é atestado, comprovante, contrato. É o objeto de maior valor
    endereçado por id no produto inteiro."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from workspace.models import Anexo

    pedido = _pedido_de(dois["dono"], item)
    anexo = Anexo.objects.create(
        solicitacao=pedido, campo="o_que", nome_original="atestado.pdf",
        arquivo=SimpleUploadedFile("a.pdf", b"%PDF-1.4 conteudo"),
        tamanho=17, criado_por=dois["dono"],
    )
    client.force_login(dois["intruso"])

    resposta = client.get(reverse("workspace:baixar_anexo", args=[anexo.pk]))

    assert resposta.status_code == 403


def test_nao_cancela_a_reserva_de_outra_pessoa(client, dois):
    recurso = Recurso.objects.create(
        codigo="sala-1", nome="Sala 1", tipo=TipoRecurso.SALA, ativo=True
    )
    inicio = timezone.now() + timedelta(days=1)
    reserva = Reserva.objects.create(
        recurso=recurso, solicitante=dois["dono"],
        inicio=inicio, fim=inicio + timedelta(hours=1),
    )
    client.force_login(dois["intruso"])

    client.post(reverse("workspace:cancelar_reserva", args=[reserva.pk]))

    reserva.refresh_from_db()
    assert reserva.situacao != SituacaoReserva.CANCELADA


def test_nao_abre_o_rascunho_de_outra_pessoa_pelo_formulario(client, dois, item):
    """O rascunho volta preenchido com o que a pessoa digitou. Abrir o do
    colega mostraria o conteúdo dele dentro do formulário."""
    rascunho = svc.salvar_rascunho(item, dois["dono"], {"o_que": "senha do cofre"})
    client.force_login(dois["intruso"])

    corpo = client.get(
        reverse("workspace:pedir", args=[item.chave]), {"rascunho": rascunho.pk}
    ).content.decode()

    assert "senha do cofre" not in corpo


def test_nao_confirma_a_correspondencia_de_outra_pessoa(client, dois):
    """"Recebi" dito por outro não confirma nada — e é essa linha que a empresa
    apresenta quando a intimação some."""
    from workspace.models import Correspondencia, SituacaoCorrespondencia

    registro = Correspondencia.objects.create(
        tipo="encomenda", destinatario=dois["dono"],
        situacao=SituacaoCorrespondencia.ENTREGUE, retirado_em=timezone.now(),
        recebido_por=dois["dono"],
    )
    client.force_login(dois["intruso"])

    client.post(reverse("workspace:confirmar_correspondencia", args=[registro.pk]))

    registro.refresh_from_db()
    assert registro.confirmado_em is None


def test_nao_aceita_a_custodia_de_outra_pessoa(client, dois):
    """O aceite é assinatura de termo de responsabilidade. Se outro puder dar,
    o termo não vale contra ninguém."""
    from workspace.models import Custodia, Material

    material = Material.objects.create(codigo="cap", nome="Capacete")
    unidade = f.unidade()
    registro = Custodia.objects.create(
        material=material, pessoa=dois["dono"], unidade=unidade, quantidade=1,
    )
    client.force_login(dois["intruso"])

    client.post(reverse("workspace:aceitar_custodia", args=[registro.pk]))

    registro.refresh_from_db()
    assert registro.aceito_em is None


# ── Vertical: o que exige papel ─────────────────────────────────────


ROTAS_QUE_EXIGEM_PAPEL = [
    # `aprovacoes` e `custodia` NÃO estão aqui, e não é esquecimento: as duas
    # respondem 200 para todo mundo de propósito. A bandeja mostra o que espera
    # VOCÊ (vazia para quem não decide nada) e Equipamentos responde "o que eu
    # tenho da empresa", que é pergunta de qualquer colaborador. Para elas a
    # pergunta certa não é "entra?" e sim "o que aparece?" — logo abaixo.
    ("workspace:fila", ()),
    ("workspace:pessoas", ()),
    ("workspace:estoque", ()),
    ("workspace:frota", ()),
    ("workspace:marketing", ()),
    ("workspace:candidaturas", ()),
    ("workspace:documentos", ()),
    ("workspace:publicacoes", ()),
    ("workspace:indicadores", ()),
]


@pytest.mark.parametrize("rota,args", ROTAS_QUE_EXIGEM_PAPEL)
def test_colaborador_comum_nao_entra_em_tela_de_papel(client, dois, rota, args):
    """Autenticado não é autorizado. Cada uma destas telas é trabalho de uma
    área, e nenhuma é informação institucional."""
    client.force_login(dois["intruso"])

    resposta = client.get(reverse(rota, args=args))

    assert resposta.status_code == 403, rota


def test_colaborador_comum_nao_concede_papel_a_si_mesmo(client, dois):
    """A escalada de privilégio mais direta que existe: se a rota de conceder
    não checar, qualquer pessoa se dá o papel que quiser."""
    from identidade.models import AtribuicaoPapel

    papel = f.papel("diretoria", ["apr.aprovar.global"], escopo="global")
    client.force_login(dois["intruso"])

    client.post(
        reverse("workspace:conceder_papel"),
        {"pessoa": dois["intruso"].pk, "papel": papel.pk,
         "escopo": "global", "justificativa": "quero"},
    )

    assert not AtribuicaoPapel.objects.filter(
        user=dois["intruso"], papel=papel
    ).exists()


def test_colaborador_comum_nao_muda_o_proprio_centro_de_custo(client, dois):
    """Centro de custo decide de qual orçamento o gasto sai. Escolher o próprio
    é escolher de quem é o dinheiro."""
    from identidade.models import Lotacao

    client.force_login(dois["intruso"])

    client.post(
        reverse("workspace:definir_centro_custo"),
        {"pessoa": dois["intruso"].pk, "centro_custo_codigo": "9999"},
    )

    assert Lotacao.objects.get(user=dois["intruso"]).centro_custo_codigo != "9999"


def test_colaborador_comum_nao_decide_aprovacao(client, dois, item):
    """Aprovar o próprio pedido é a escalada mais lucrativa do produto."""
    from workspace.models import SituacaoSolicitacao

    ItemCatalogo.objects.filter(pk=item.pk).update(limite_auto_aprovacao=Decimal("0"))
    chefe = f.pessoa("chefe")
    f.lotar(chefe)
    from identidade.models import Lotacao

    Lotacao.objects.filter(user=dois["dono"]).update(gestor=chefe)
    from workspace.models import RegraAprovacao, TipoAprovador

    RegraAprovacao.objects.create(
        dominio="ti.", tipo=TipoAprovador.GESTOR_DIRETO, ordem=10
    )
    pedido = _pedido_de(dois["dono"], item)
    assert pedido.aprovacao is not None

    client.force_login(dois["intruso"])
    client.post(
        reverse("workspace:decidir_aprovacao", args=[pedido.aprovacao.pk]),
        {"decisao": "aprovar"},
    )

    pedido.aprovacao.refresh_from_db()
    assert pedido.aprovacao.situacao == SituacaoSolicitacao.AGUARDANDO


def test_colaborador_comum_nao_assume_pedido_da_fila(client, dois, item):
    """Assumir o atendimento dá acesso ao conteúdo do pedido — inclusive aos
    anexos, pela regra de quem atende."""
    pedido = _pedido_de(dois["dono"], item, situacao=SituacaoServico.APROVADA)
    client.force_login(dois["intruso"])

    client.post(reverse("workspace:atender", args=[pedido.pk]), {"acao": "assumir"})

    pedido.refresh_from_db()
    assert pedido.atendente_id is None


# ── Anônimo: nem chega perto ────────────────────────────────────────


def test_anonimo_nao_baixa_anexo(client, dois, item):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from workspace.models import Anexo

    pedido = _pedido_de(dois["dono"], item)
    anexo = Anexo.objects.create(
        solicitacao=pedido, campo="o_que", nome_original="atestado.pdf",
        arquivo=SimpleUploadedFile("a.pdf", b"%PDF-1.4 x"),
        tamanho=10, criado_por=dois["dono"],
    )

    resposta = client.get(reverse("workspace:baixar_anexo", args=[anexo.pk]))

    assert resposta.status_code in (302, 403)
    assert b"%PDF" not in resposta.content


# ── As duas telas abertas: 200 é resposta certa, vazio é o requisito ──
#
# Nem toda tela precisa responder 403. A bandeja de aprovação e a de
# Equipamentos abrem para qualquer pessoa identificada — e é decisão de
# produto, não descuido: uma responde "o que espera VOCÊ" e a outra "o que eu
# tenho da empresa". O que não pode acontecer é aparecer coisa de terceiro.
#
# São as telas mais fáceis de quebrar por acidente numa onda futura: basta
# trocar um `de(pessoa)` por `all()` num dia apressado, e o 403 nunca vai
# denunciar isso porque ele nunca existiu aqui.


def test_a_bandeja_de_quem_nao_decide_nada_vem_vazia(client, dois, item):
    """Ela abre — e não mostra o pedido de ninguém."""
    from identidade.models import Lotacao
    from workspace.models import RegraAprovacao, TipoAprovador

    chefe = f.pessoa("chefe")
    f.lotar(chefe)
    Lotacao.objects.filter(user=dois["dono"]).update(gestor=chefe)
    RegraAprovacao.objects.create(
        dominio="ti.", tipo=TipoAprovador.GESTOR_DIRETO, ordem=10
    )
    ItemCatalogo.objects.filter(pk=item.pk).update(limite_auto_aprovacao=Decimal("0"))
    _pedido_de(dois["dono"], item)

    client.force_login(dois["intruso"])
    resposta = client.get(reverse("workspace:aprovacoes"))

    assert resposta.status_code == 200
    assert resposta.context["itens"] == []
    assert "Acesso a um sistema" not in resposta.content.decode()


def test_equipamentos_mostra_o_meu_e_nao_o_do_colega(client, dois):
    """Quem controla patrimônio vê a lista dos outros DENTRO desta tela. Quem
    não controla vê só a própria — e o nome do colega não pode escapar."""
    from workspace.models import Custodia, Material

    material = Material.objects.create(codigo="note", nome="Notebook Dell")
    unidade = f.unidade()
    Custodia.objects.create(
        material=material, pessoa=dois["dono"], unidade=unidade, quantidade=1
    )

    client.force_login(dois["intruso"])
    corpo = client.get(reverse("workspace:custodia")).content.decode()

    assert dois["dono"].get_short_name() not in corpo
    assert dois["dono"].email not in corpo
