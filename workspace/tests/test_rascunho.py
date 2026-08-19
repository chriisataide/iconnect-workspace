"""§43 — o rascunho, a outra metade do estado que faltava.

## O problema

O formulário longo era tudo-ou-nada. Prestação de contas com dez linhas, compra
com anexo, requisição com dez campos: quem não tinha o comprovante à mão perdia
o que já tinha digitado ao sair da tela. Na prática as pessoas resolviam isso
digitando tudo no bloco de notas primeiro, e o produto virava a segunda etapa
de um processo que começava fora dele.

## O que estes testes guardam

1. **Rascunho não valida nada.** Validar recriaria o problema, porque rascunho
   é por definição o formulário incompleto.
2. **Rascunho não é "em aberto".** Nada foi enviado, ninguém foi avisado, nenhum
   prazo corre. Somá-lo faria o painel da área contar como trabalho atrasado um
   formulário que nunca chegou a ela.
3. **Enviar promove a MESMA linha.** Criar outra deixaria o rascunho para trás
   com os anexos dentro — dois registros do mesmo pedido, um enviado sem
   comprovante e outro com o comprovante e nunca enviado.
4. **O relógio do prazo começa no envio**, e não no dia em que a pessoa abriu o
   formulário.
5. **Rascunho é de quem o escreveu**, e de mais ninguém.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.models.anexo import Anexo
from workspace.models.aprovacao import SolicitacaoAprovacao
from workspace.models.catalogo import (
    GrupoCatalogo,
    ItemCatalogo,
    SituacaoServico,
    SolicitacaoServico,
    TipoCampo,
)
from workspace.models.evento import AcaoSolicitacao, EventoSolicitacao
from workspace.models.notificacao import Notificacao
from workspace.services import catalogo as svc
from workspace.services import listagem as lst
from workspace.services.catalogo import SolicitacaoError

pytestmark = pytest.mark.django_db


#: Um PNG de 1×1 de verdade — o validador confere magic bytes, e um `b"x"`
#: qualquer seria recusado por motivo que não é o do teste.
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000050001" "0d0a2db4" "0000000049454e44ae426082"
)


@pytest.fixture
def cenario():
    ana, gestor = f.pessoa("ana"), f.pessoa("gestor")
    f.lotar(gestor)
    f.lotar(ana, gestor=gestor)
    item = ItemCatalogo.objects.create(
        chave="compra-teste",
        nome="Compra de teste",
        grupo=GrupoCatalogo.EQUIPAMENTO,
        dominio="log.compra",
        prazo_prometido_dias=3,
        campos=[
            {"chave": "o_que", "rotulo": "O que", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True},
            {"chave": "nota", "rotulo": "Nota fiscal", "tipo": TipoCampo.ARQUIVO,
             "obrigatorio": True},
        ],
    )
    return {"ana": ana, "gestor": gestor, "item": item}


def guardar(cenario, **extras):
    dados = {"dados": {"o_que": "Um monitor"}}
    dados.update(extras)
    return svc.salvar_rascunho(cenario["item"], cenario["ana"], **dados)


# ── Guardar ─────────────────────────────────────────────────────────


def test_rascunho_guarda_o_formulario_incompleto(cenario):
    """Sem anexo e sem campo obrigatório preenchido — é esse o ponto."""
    rascunho = svc.salvar_rascunho(cenario["item"], cenario["ana"], {"o_que": ""})

    assert rascunho.situacao == SituacaoServico.RASCUNHO
    assert rascunho.pk is not None


def test_rascunho_nao_cria_aprovacao(cenario):
    """Ninguém foi avisado, nenhuma bandeja recebeu nada."""
    guardar(cenario)

    assert not SolicitacaoAprovacao.objects.exists()
    assert not Notificacao.objects.exists()


def test_rascunho_nao_compromete_orcamento(cenario):
    from workspace.models.orcamento import Compromisso

    guardar(cenario, valor=Decimal("900"))

    assert not Compromisso.objects.exists()


def test_guardar_de_novo_atualiza_a_mesma_linha(cenario):
    """Um "salvar" por linha nova encheria a lista da pessoa de cópias do mesmo
    formulário."""
    primeiro = guardar(cenario)
    segundo = svc.salvar_rascunho(
        cenario["item"], cenario["ana"], {"o_que": "Dois monitores"},
        rascunho=primeiro,
    )

    assert segundo.pk == primeiro.pk
    assert SolicitacaoServico.objects.count() == 1
    assert segundo.dados["o_que"] == "Dois monitores"


def test_so_o_primeiro_salvar_entra_no_historico(cenario):
    """Cada "salvar" seguinte é a mesma pessoa mexendo no próprio texto —
    registrar todos encheria a linha do tempo de eventos que não contam nada."""
    rascunho = guardar(cenario)
    svc.salvar_rascunho(cenario["item"], cenario["ana"], {"o_que": "x"}, rascunho=rascunho)

    eventos = EventoSolicitacao.objects.filter(solicitacao=rascunho)
    assert eventos.count() == 1
    assert eventos.get().acao == AcaoSolicitacao.RASCUNHO_GUARDADO


def test_anonimo_nao_guarda_rascunho(cenario):
    """Rascunho é da pessoa, e sem sessão não há de quem ele seja."""
    from django.contrib.auth.models import AnonymousUser

    with pytest.raises(SolicitacaoError, match="identificado"):
        svc.salvar_rascunho(cenario["item"], AnonymousUser(), {})


def test_o_anexo_e_validado_mesmo_no_rascunho(cenario):
    """Arquivo com magic byte errado não entra em disco nem como rascunho: a
    validação existe contra o conteúdo, e o conteúdo não fica menos perigoso por
    o formulário estar pela metade."""
    from workspace.services.anexos import AnexoError

    falso = SimpleUploadedFile("nota.png", b"nao sou um png", content_type="image/png")

    with pytest.raises(AnexoError):
        svc.salvar_rascunho(
            cenario["item"], cenario["ana"], {}, arquivos={"nota": [falso]}
        )


def test_o_anexo_do_rascunho_e_guardado(cenario):
    rascunho = svc.salvar_rascunho(
        cenario["item"],
        cenario["ana"],
        {"o_que": "Um monitor"},
        arquivos={"nota": [SimpleUploadedFile("nota.png", PNG, content_type="image/png")]},
    )

    assert rascunho.anexos.count() == 1


# ── Rascunho não é trabalho ─────────────────────────────────────────


def test_rascunho_fica_fora_de_em_aberto(cenario):
    """"Em aberto" quer dizer que o pedido está vivo na esteira. Um formulário
    que ninguém enviou não tem prazo correndo nem dono."""
    guardar(cenario)

    assert SituacaoServico.RASCUNHO not in lst.ABERTAS
    assert not SolicitacaoServico.objects.abertas().exists()


def test_rascunho_fica_fora_do_painel_de_indicadores(cenario):
    """Sem esta exclusão o rascunho apareceria como pedido aberto e, passado o
    prazo do item, como ATRASADO — no painel de uma área que nunca soube dele."""
    from workspace.services import indicadores as ind

    rascunho = guardar(cenario)
    # Envelhecido além do prazo prometido: é quando o defeito apareceria.
    SolicitacaoServico.objects.filter(pk=rascunho.pk).update(
        criado_em=timezone.now() - timedelta(days=30)
    )

    olheiro = f.pessoa("diretor")
    f.lotar(olheiro)
    f.atribuir(olheiro, f.papel("ind", ["ind.ler.global"], escopo="global"))

    painel = ind.panorama(olheiro)
    total = sum(a["abertos"] + a["atrasados"] for a in painel["areas"])

    assert total == 0


def test_pedido_reprovado_tambem_saiu_do_aberto(cenario):
    """Achado no caminho do §43: `em_aberto` era uma lista escrita à mão com
    `(CONCLUIDA, CANCELADA)`, então um pedido REPROVADO continuava "em aberto"
    meses depois de o gestor ter dito não."""
    pedido = svc.solicitar(
        cenario["item"],
        cenario["ana"],
        {"o_que": "x"},
        arquivos={"nota": [SimpleUploadedFile("n.png", PNG, content_type="image/png")]},
    )
    pedido.situacao = SituacaoServico.REJEITADA
    pedido.save()

    assert not pedido.em_aberto


def test_rascunho_nao_conta_no_contador_do_trilho(cenario, client):
    guardar(cenario)
    client.force_login(cenario["ana"])

    assert client.get(reverse("workspace:meu_dia")).context["abertas"] == 0


def test_a_fase_diz_que_nada_foi_enviado(cenario):
    """"Rascunho" sozinho deixa a dúvida que importa: já mandei ou não?"""
    assert guardar(cenario).fase == "Rascunho · não enviado"


# ── Enviar ──────────────────────────────────────────────────────────


def enviar(cenario, rascunho, **extras):
    dados = {
        "dados": {"o_que": "Um monitor"},
        "arquivos": {},
        "rascunho": rascunho,
    }
    dados.update(extras)
    return svc.solicitar(cenario["item"], cenario["ana"], **dados)


def test_enviar_promove_a_mesma_linha(cenario):
    """Criar outra deixaria o rascunho para trás com os anexos dentro."""
    rascunho = svc.salvar_rascunho(
        cenario["item"],
        cenario["ana"],
        {"o_que": "Um monitor"},
        arquivos={"nota": [SimpleUploadedFile("n.png", PNG, content_type="image/png")]},
    )

    pedido = enviar(cenario, rascunho)

    assert pedido.pk == rascunho.pk
    assert SolicitacaoServico.objects.count() == 1
    assert pedido.situacao == SituacaoServico.AGUARDANDO_APROVACAO


def test_o_anexo_guardado_ontem_conta_na_validacao(cenario):
    """Sem isto, quem retomasse o rascunho seria mandado anexar de novo um
    arquivo que já está no pedido."""
    rascunho = svc.salvar_rascunho(
        cenario["item"],
        cenario["ana"],
        {"o_que": "Um monitor"},
        arquivos={"nota": [SimpleUploadedFile("n.png", PNG, content_type="image/png")]},
    )

    # Envio SEM mandar arquivo nenhum: o do rascunho tem de bastar.
    pedido = enviar(cenario, rascunho, arquivos={})

    assert pedido.situacao == SituacaoServico.AGUARDANDO_APROVACAO
    assert Anexo.objects.count() == 1


def test_enviar_incompleto_continua_recusando(cenario):
    """Guardar não valida; enviar valida. São dois atos diferentes."""
    rascunho = guardar(cenario)

    with pytest.raises(SolicitacaoError, match="Anexe"):
        enviar(cenario, rascunho, dados={"o_que": "Um monitor"})

    rascunho.refresh_from_db()
    assert rascunho.situacao == SituacaoServico.RASCUNHO


def test_o_relogio_do_prazo_comeca_no_envio(cenario):
    """`criado_em` é `auto_now_add` e só grava na inserção: sem mexer nele, o
    pedido nasceria com a data do rascunho e já atrasado."""
    rascunho = svc.salvar_rascunho(
        cenario["item"],
        cenario["ana"],
        {"o_que": "Um monitor"},
        arquivos={"nota": [SimpleUploadedFile("n.png", PNG, content_type="image/png")]},
    )
    SolicitacaoServico.objects.filter(pk=rascunho.pk).update(
        criado_em=timezone.now() - timedelta(days=30)
    )
    rascunho.refresh_from_db()

    pedido = enviar(cenario, rascunho, arquivos={})

    assert (timezone.now() - pedido.criado_em).days == 0


def test_enviar_cria_a_aprovacao_normalmente(cenario):
    rascunho = svc.salvar_rascunho(
        cenario["item"],
        cenario["ana"],
        {"o_que": "Um monitor"},
        arquivos={"nota": [SimpleUploadedFile("n.png", PNG, content_type="image/png")]},
    )

    pedido = enviar(cenario, rascunho, arquivos={})

    assert pedido.aprovacao is not None


# ── Dono ────────────────────────────────────────────────────────────


def test_rascunho_de_outra_pessoa_nao_e_encontrado(cenario):
    """Sem esta conferência, trocar um dígito na URL abriria o formulário meio
    preenchido de um colega, com o que ele digitou dentro."""
    rascunho = guardar(cenario)
    bruno = f.pessoa("bruno")
    f.lotar(bruno)

    assert svc.rascunho_de(bruno, rascunho.pk) is None
    assert svc.rascunho_de(cenario["ana"], rascunho.pk) == rascunho


def test_rascunho_de_recusa_pk_invalida(cenario):
    assert svc.rascunho_de(cenario["ana"], "abacaxi") is None
    assert svc.rascunho_de(cenario["ana"], None) is None


def test_rascunho_de_e_none_para_anonimo(cenario):
    from django.contrib.auth.models import AnonymousUser

    rascunho = guardar(cenario)

    assert svc.rascunho_de(AnonymousUser(), rascunho.pk) is None


def test_ninguem_guarda_por_cima_do_rascunho_alheio(cenario):
    rascunho = guardar(cenario)
    bruno = f.pessoa("bruno")
    f.lotar(bruno)

    with pytest.raises(SolicitacaoError, match="não é seu"):
        svc.salvar_rascunho(cenario["item"], bruno, {"o_que": "x"}, rascunho=rascunho)


def test_pedido_ja_enviado_nao_volta_a_ser_rascunho(cenario):
    pedido = svc.solicitar(
        cenario["item"],
        cenario["ana"],
        {"o_que": "x"},
        arquivos={"nota": [SimpleUploadedFile("n.png", PNG, content_type="image/png")]},
    )

    with pytest.raises(SolicitacaoError, match="já foi enviada"):
        svc.salvar_rascunho(cenario["item"], cenario["ana"], {}, rascunho=pedido)


# ── Descartar ───────────────────────────────────────────────────────


def test_descartar_apaga_de_verdade(cenario):
    """A única exclusão do produto, e ela se justifica: nada foi enviado,
    ninguém foi avisado, e guardá-lo como "cancelada" faria a taxa de
    cancelamento contar pedidos que nunca foram feitos."""
    rascunho = guardar(cenario)

    svc.descartar_rascunho(rascunho, cenario["ana"])

    assert not SolicitacaoServico.objects.exists()


def test_descartar_leva_os_anexos_junto(cenario):
    rascunho = svc.salvar_rascunho(
        cenario["item"],
        cenario["ana"],
        {},
        arquivos={"nota": [SimpleUploadedFile("n.png", PNG, content_type="image/png")]},
    )

    svc.descartar_rascunho(rascunho, cenario["ana"])

    assert not Anexo.objects.exists()


def test_ninguem_descarta_o_rascunho_alheio(cenario):
    rascunho = guardar(cenario)
    bruno = f.pessoa("bruno")
    f.lotar(bruno)

    with pytest.raises(SolicitacaoError, match="não é seu"):
        svc.descartar_rascunho(rascunho, bruno)

    assert SolicitacaoServico.objects.exists()


def test_pedido_enviado_nao_se_descarta(cenario):
    """A regra da casa volta a valer no instante do envio."""
    pedido = svc.solicitar(
        cenario["item"],
        cenario["ana"],
        {"o_que": "x"},
        arquivos={"nota": [SimpleUploadedFile("n.png", PNG, content_type="image/png")]},
    )

    with pytest.raises(SolicitacaoError, match="já foi enviada"):
        svc.descartar_rascunho(pedido, cenario["ana"])


# ── A tela ──────────────────────────────────────────────────────────


def png(nome="nota.png"):
    return SimpleUploadedFile(nome, PNG, content_type="image/png")


def test_o_botao_de_rascunho_so_aparece_para_quem_entrou(cenario, client):
    """Rascunho é da pessoa, e sem sessão não há de quem ele seja."""
    url = reverse("workspace:pedir", args=["compra-teste"])

    assert "Guardar rascunho" not in client.get(url).content.decode()

    client.force_login(cenario["ana"])
    assert "Guardar rascunho" in client.get(url).content.decode()


def test_guardar_pela_tela_sem_preencher_nada(cenario, client):
    client.force_login(cenario["ana"])

    resposta = client.post(
        reverse("workspace:pedir", args=["compra-teste"]),
        {"acao": "rascunho", "o_que": ""},
    )

    rascunho = SolicitacaoServico.objects.get()
    assert rascunho.situacao == SituacaoServico.RASCUNHO
    assert resposta["Location"].endswith(f"?rascunho={rascunho.pk}")


def test_retomar_devolve_o_que_estava_escrito(cenario, client):
    rascunho = guardar(cenario)
    client.force_login(cenario["ana"])

    resposta = client.get(
        reverse("workspace:pedir", args=["compra-teste"]), {"rascunho": rascunho.pk}
    )

    assert resposta.context["rascunho"] == rascunho
    campo = next(c for c in resposta.context["campos"] if c["chave"] == "o_que")
    assert campo["valor"] == "Um monitor"


def test_retomar_lista_os_anexos_ja_guardados(cenario, client):
    """Sem esta lista a pessoa volta ao formulário, não vê o comprovante que
    mandou ontem, e anexa de novo — e o pedido chega com dois."""
    rascunho = svc.salvar_rascunho(
        cenario["item"], cenario["ana"], {}, arquivos={"nota": [png()]}
    )
    client.force_login(cenario["ana"])

    resposta = client.get(
        reverse("workspace:pedir", args=["compra-teste"]), {"rascunho": rascunho.pk}
    )

    assert len(resposta.context["anexos_do_rascunho"]) == 1
    assert "nota.png" in resposta.content.decode()


def test_o_rascunho_de_outra_pessoa_nao_abre(cenario, client):
    rascunho = guardar(cenario)
    bruno = f.pessoa("bruno")
    f.lotar(bruno)
    client.force_login(bruno)

    resposta = client.get(
        reverse("workspace:pedir", args=["compra-teste"]), {"rascunho": rascunho.pk}
    )

    assert resposta.context["rascunho"] is None
    campo = next(c for c in resposta.context["campos"] if c["chave"] == "o_que")
    assert campo["valor"] == ""


def test_o_post_nao_sobrescreve_o_que_a_pessoa_acabou_de_digitar(cenario, client):
    """Reescrever com o valor guardado apagaria a edição no instante do envio."""
    rascunho = guardar(cenario)
    client.force_login(cenario["ana"])

    client.post(
        reverse("workspace:pedir", args=["compra-teste"]),
        {"acao": "rascunho", "rascunho": rascunho.pk, "o_que": "Dois monitores"},
    )
    rascunho.refresh_from_db()

    assert rascunho.dados["o_que"] == "Dois monitores"


def test_enviar_pela_tela_promove_o_rascunho(cenario, client):
    rascunho = svc.salvar_rascunho(
        cenario["item"], cenario["ana"], {"o_que": "Um monitor"},
        arquivos={"nota": [png()]},
    )
    client.force_login(cenario["ana"])

    client.post(
        reverse("workspace:pedir", args=["compra-teste"]),
        {"rascunho": rascunho.pk, "o_que": "Um monitor"},
    )
    rascunho.refresh_from_db()

    assert SolicitacaoServico.objects.count() == 1
    assert rascunho.situacao == SituacaoServico.AGUARDANDO_APROVACAO


def test_descartar_pela_tela(cenario, client):
    rascunho = guardar(cenario)
    client.force_login(cenario["ana"])

    client.post(reverse("workspace:descartar_rascunho", args=[rascunho.pk]))

    assert not SolicitacaoServico.objects.exists()


def test_descartar_o_alheio_pela_tela_nao_apaga(cenario, client):
    rascunho = guardar(cenario)
    bruno = f.pessoa("bruno")
    f.lotar(bruno)
    client.force_login(bruno)

    client.post(reverse("workspace:descartar_rascunho", args=[rascunho.pk]))

    assert SolicitacaoServico.objects.exists()


def test_get_no_descartar_volta_para_a_lista(cenario, client):
    rascunho = guardar(cenario)
    client.force_login(cenario["ana"])

    resposta = client.get(reverse("workspace:descartar_rascunho", args=[rascunho.pk]))

    assert resposta["Location"].endswith("?situacao=rascunho")
    assert SolicitacaoServico.objects.exists()


def test_a_lista_tem_aba_de_rascunhos(cenario, client):
    guardar(cenario)
    client.force_login(cenario["ana"])

    resposta = client.get(reverse("workspace:minhas_solicitacoes"), {"situacao": "rascunho"})

    assert resposta.context["encontradas"] == 1
    corpo = resposta.content.decode()
    assert "Continuar" in corpo
    assert "Descartar" in corpo


def test_a_aba_de_em_aberto_nao_mostra_rascunho(cenario, client):
    guardar(cenario)
    client.force_login(cenario["ana"])

    resposta = client.get(reverse("workspace:minhas_solicitacoes"), {"situacao": "abertas"})

    assert resposta.context["encontradas"] == 0


def test_todas_mostra_o_rascunho(cenario, client):
    """Esconder o rascunho justamente de quem o escreveu seria a única forma de
    perdê-lo de vez."""
    guardar(cenario)
    client.force_login(cenario["ana"])

    resposta = client.get(reverse("workspace:minhas_solicitacoes"))

    assert resposta.context["encontradas"] == 1


def test_o_rascunho_nao_oferece_cancelar(cenario, client):
    """"Cancelar" marcaria como CANCELADA um pedido que nunca foi enviado — e a
    taxa de cancelamento do painel passaria a contar pedidos que nunca
    existiram."""
    rascunho = guardar(cenario)
    client.force_login(cenario["ana"])

    corpo = client.get(
        reverse("workspace:minhas_solicitacoes"), {"situacao": "rascunho"}
    ).content.decode()

    assert reverse("workspace:cancelar_solicitacao", args=[rascunho.pk]) not in corpo


def test_cancelar_continua_recusando_rascunho_pela_porta_dos_fundos(cenario, client):
    rascunho = guardar(cenario)
    client.force_login(cenario["ana"])

    client.post(reverse("workspace:cancelar_solicitacao", args=[rascunho.pk]))
    rascunho.refresh_from_db()

    assert rascunho.situacao == SituacaoServico.RASCUNHO


def test_cancelar_no_formulario_do_rascunho_volta_para_a_lista(cenario, client):
    """§8 — quem está continuando um rascunho veio da lista de rascunhos, e
    mandá-lo para a vitrine faz o rascunho sumir de vista no exato clique em que
    ele decidiu não mexer nele agora."""
    rascunho = guardar(cenario)
    client.force_login(cenario["ana"])

    corpo = client.get(
        reverse("workspace:pedir", args=["compra-teste"]), {"rascunho": rascunho.pk}
    ).content.decode()

    assert f"{reverse('workspace:minhas_solicitacoes')}?situacao=rascunho" in corpo


def test_anexo_recusado_no_rascunho_vira_recado_e_nao_500(cenario, client):
    """Guardar não valida o formulário — valida o ARQUIVO. Um `.png` que não é
    png não entra em disco nem como rascunho, e o recado explica em vez de
    quebrar a tela."""
    client.force_login(cenario["ana"])

    resposta = client.post(
        reverse("workspace:pedir", args=["compra-teste"]),
        {
            "acao": "rascunho",
            "o_que": "Um monitor",
            "nota": SimpleUploadedFile("nota.png", b"nao sou png", content_type="image/png"),
        },
    )

    assert resposta.status_code == 302
    assert resposta["Location"].endswith("?situacao=rascunho")
    assert not SolicitacaoServico.objects.exists()
