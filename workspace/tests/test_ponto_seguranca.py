"""As barreiras do modo de teste, e o que acontece quando o n8n falha.

Este é o arquivo que não pode passar por acidente. A regra que ele guarda é a
única do sistema cujo erro é irreversível: uma mensagem enviada ao colaborador
errado não volta atrás.
"""

from __future__ import annotations

import json
import urllib.error
from unittest import mock

import pytest
from django.utils import timezone

from workspace.models.ponto import (
    ColaboradorPonto,
    EnvioPonto,
    LotePonto,
    ModoEnvio,
    SituacaoEnvio,
    SituacaoLote,
)
from workspace.services import ponto_whatsapp as svc

pytestmark = pytest.mark.django_db

# Os números do §39, em formato de celular brasileiro válido.
JOAO = "5511911111111"
MARIA = "5522922222222"
TELEFONE_TESTE = "5533933333333"


def criar_lote(modo=ModoEnvio.TESTE, telefone_teste=TELEFONE_TESTE) -> LotePonto:
    return LotePonto.objects.create(
        arquivo_nome="ajuste.xlsx",
        modo=modo,
        telefone_teste=telefone_teste,
        situacao=SituacaoLote.VALIDADO,
    )


def criar_colaborador(lote, nome, telefone, pendencias=None):
    return ColaboradorPonto.objects.create(
        lote=lote,
        nome=nome,
        telefone_normalizado=telefone,
        pendencias=pendencias or [{"data": "15/09/2026", "motivo": "ausência de marcação de entrada"}],
        quantidade_pendencias=1,
        selecionado=True,
    )


# ── A regra central — §19 e §39 ─────────────────────────────────────


def test_em_teste_todos_os_destinos_viram_o_telefone_de_teste():
    """O teste exato que o §39 exige."""
    lote = criar_lote()
    joao = criar_colaborador(lote, "João", JOAO)
    maria = criar_colaborador(lote, "Maria", MARIA)

    destinos = dict(
        (c.nome, destino) for c, destino in svc.destinos_do_lote(lote, [joao, maria])
    )

    assert destinos == {"João": TELEFONE_TESTE, "Maria": TELEFONE_TESTE}
    assert JOAO not in destinos.values()
    assert MARIA not in destinos.values()


def test_nenhum_envio_gravado_em_teste_carrega_telefone_real():
    lote = criar_lote()
    criar_colaborador(lote, "João", JOAO)
    criar_colaborador(lote, "Maria", MARIA)

    envios = svc.preparar_envios(lote, lote.colaboradores.all())

    assert {e.destino for e in envios} == {TELEFONE_TESTE}
    gravados = set(EnvioPonto.objects.values_list("destino", flat=True))
    assert gravados == {TELEFONE_TESTE}


def test_o_payload_que_vai_ao_n8n_nao_contem_telefone_real_em_teste():
    """A última fronteira: o que sai pela rede."""
    lote = criar_lote()
    criar_colaborador(lote, "João", JOAO)
    criar_colaborador(lote, "Maria", MARIA)

    envios = svc.preparar_envios(lote, lote.colaboradores.all())
    bruto = json.dumps(svc.montar_payload(lote, envios))

    assert JOAO not in bruto
    assert MARIA not in bruto
    assert bruto.count(TELEFONE_TESTE) >= 2


def test_a_segunda_barreira_bloqueia_o_lote_inteiro_se_um_destino_divergir():
    """Protege contra o CÓDIGO errado, não contra o dado errado."""
    lote = criar_lote()
    joao = criar_colaborador(lote, "João", JOAO)

    # Simula uma montagem futura que escape da primeira barreira.
    with mock.patch.object(svc, "destinos_do_lote", return_value=[(joao, JOAO)]):
        with pytest.raises(svc.FalhaDeSeguranca, match="diferente do telefone de teste"):
            svc.preparar_envios(lote, [joao])

    assert EnvioPonto.objects.count() == 0, "nada pode ser gravado quando a barreira fecha"


def test_teste_sem_telefone_de_teste_nao_cai_para_o_numero_real():
    """Nunca há retorno ao telefone verdadeiro — a falha fecha o lote."""
    lote = criar_lote(telefone_teste="")
    criar_colaborador(lote, "João", JOAO)

    with pytest.raises(svc.FalhaDeSeguranca):
        svc.preparar_envios(lote, lote.colaboradores.all())

    assert EnvioPonto.objects.count() == 0


def test_telefone_de_teste_invalido_e_recusado():
    lote = criar_lote(telefone_teste="(19) 3456-7890")  # fixo
    criar_colaborador(lote, "João", JOAO)

    with pytest.raises(svc.FalhaDeSeguranca, match="celular válido"):
        svc.preparar_envios(lote, lote.colaboradores.all())


def test_o_lote_nasce_em_teste_por_omissao():
    """§18: nenhum caminho pode criar um lote que já sai disparando."""
    lote = LotePonto.objects.create(arquivo_nome="x.xlsx")
    assert lote.modo == ModoEnvio.TESTE
    assert lote.em_teste is True


# ── Produção ────────────────────────────────────────────────────────


def test_em_producao_cada_um_recebe_no_proprio_numero():
    lote = criar_lote(modo=ModoEnvio.PRODUCAO)
    joao = criar_colaborador(lote, "João", JOAO)
    maria = criar_colaborador(lote, "Maria", MARIA)

    destinos = dict((c.nome, d) for c, d in svc.destinos_do_lote(lote, [joao, maria]))
    assert destinos == {"João": JOAO, "Maria": MARIA}


def test_em_producao_quem_nao_tem_telefone_fica_de_fora():
    """§35: sem telefone bom não vai para produção, e não derruba o lote."""
    lote = criar_lote(modo=ModoEnvio.PRODUCAO)
    joao = criar_colaborador(lote, "João", JOAO)
    sem = criar_colaborador(lote, "Sem Telefone", "")

    pares = svc.destinos_do_lote(lote, [joao, sem])
    assert [c.nome for c, _ in pares] == ["João"]


def test_o_telefone_corrigido_manda_em_producao():
    """§14: a correção vale para este lote."""
    lote = criar_lote(modo=ModoEnvio.PRODUCAO)
    colaborador = criar_colaborador(lote, "João", "")
    colaborador.telefone_corrigido = JOAO
    colaborador.save()

    pares = svc.destinos_do_lote(lote, [colaborador])
    assert pares[0][1] == JOAO


def test_producao_acima_do_teto_e_recusada(settings):
    settings.PONTO_MAXIMO_POR_LOTE = 2
    lote = criar_lote(modo=ModoEnvio.PRODUCAO)
    for i in range(3):
        criar_colaborador(lote, f"Pessoa {i}", f"551191111111{i}")

    with pytest.raises(svc.FalhaDeSeguranca, match="teto por disparo"):
        svc.preparar_envios(lote, lote.colaboradores.all())


# ── Integração com o n8n — §39 ──────────────────────────────────────


def preparado(modo=ModoEnvio.TESTE):
    lote = criar_lote(modo=modo)
    criar_colaborador(lote, "João", JOAO)
    criar_colaborador(lote, "Maria", MARIA)
    return lote, svc.preparar_envios(lote, lote.colaboradores.all())


def resposta_falsa(corpo: str):
    contexto = mock.MagicMock()
    contexto.__enter__.return_value.read.return_value = corpo.encode("utf-8")
    contexto.__exit__.return_value = False
    return contexto


def test_sem_webhook_configurado_a_falha_e_clara(settings):
    settings.PONTO_N8N_WEBHOOK_URL = ""
    lote, envios = preparado()
    with pytest.raises(svc.FalhaDeIntegracao, match="N8N_PONTO_WEBHOOK_URL"):
        svc.despachar(lote, envios)


def test_sucesso_marca_todos_como_enviados(settings):
    settings.PONTO_N8N_WEBHOOK_URL = "http://n8n.local/webhook/ponto"
    lote, envios = preparado()

    with mock.patch("urllib.request.urlopen", return_value=resposta_falsa('{"resultados": []}')):
        resultado = svc.despachar(lote, envios)

    assert resultado.enviados == 2
    assert resultado.falhas == 0
    assert set(EnvioPonto.objects.values_list("situacao", flat=True)) == {SituacaoEnvio.ENVIADO}


def test_retorno_parcial_marca_so_quem_falhou(settings):
    settings.PONTO_N8N_WEBHOOK_URL = "http://n8n.local/webhook/ponto"
    lote, envios = preparado()
    corpo = json.dumps(
        {"resultados": [{"envioId": envios[0].pk, "status": "erro_envio", "erro": "sem sessão"}]}
    )

    with mock.patch("urllib.request.urlopen", return_value=resposta_falsa(corpo)):
        resultado = svc.despachar(lote, envios)

    assert (resultado.enviados, resultado.falhas) == (1, 1)
    assert EnvioPonto.objects.get(pk=envios[0].pk).situacao == SituacaoEnvio.ERRO
    assert EnvioPonto.objects.get(pk=envios[1].pk).situacao == SituacaoEnvio.ENVIADO


@pytest.mark.parametrize(
    "erro,trecho",
    [
        (urllib.error.HTTPError("u", 401, "nao autorizado", {}, None), "recusou"),
        (urllib.error.HTTPError("u", 500, "erro interno", {}, None), "recusou"),
        (urllib.error.URLError("conexao recusada"), "possível falar"),
        (TimeoutError("demorou"), "não respondeu"),
    ],
)
def test_falha_do_n8n_nao_perde_o_lote(settings, erro, trecho):
    """§39: o sistema não pode perder o lote."""
    settings.PONTO_N8N_WEBHOOK_URL = "http://n8n.local/webhook/ponto"
    lote, envios = preparado()

    with mock.patch("urllib.request.urlopen", side_effect=erro):
        with pytest.raises(svc.FalhaDeIntegracao, match=trecho):
            svc.despachar(lote, envios)

    assert LotePonto.objects.filter(pk=lote.pk).exists()
    assert EnvioPonto.objects.filter(lote=lote).count() == 2
    assert set(EnvioPonto.objects.values_list("situacao", flat=True)) == {SituacaoEnvio.ERRO}


def test_o_token_vai_no_cabecalho_e_nunca_no_corpo(settings):
    settings.PONTO_N8N_WEBHOOK_URL = "http://n8n.local/webhook/ponto"
    settings.PONTO_N8N_TOKEN = "token-secreto-do-n8n"
    lote, envios = preparado()

    with mock.patch("urllib.request.urlopen", return_value=resposta_falsa("{}")) as chamada:
        svc.despachar(lote, envios)

    requisicao = chamada.call_args[0][0]
    assert requisicao.get_header("Authorization") == "Bearer token-secreto-do-n8n"
    assert "token-secreto" not in requisicao.data.decode("utf-8")


def test_fechar_lote_marca_erro_quando_houve_falha():
    lote = criar_lote()
    svc.fechar_lote(lote, svc.Resultado(enviados=1, falhas=1))
    lote.refresh_from_db()
    assert lote.situacao == SituacaoLote.CONCLUIDO_COM_ERROS
    assert lote.concluido_em is not None


def test_progresso_conta_o_que_a_tela_mostra():
    lote, envios = preparado()
    EnvioPonto.objects.filter(pk=envios[0].pk).update(
        situacao=SituacaoEnvio.ENVIADO, enviado_em=timezone.now()
    )

    estado = svc.progresso(lote)
    assert estado["total"] == 2
    assert estado["enviados"] == 1
    assert estado["restantes"] == 1
    assert estado["terminou"] is False
