"""A tela de pendências de ponto: permissão, upload e o caminho completo.

O teste que importa é `test_sem_permissao_producao_da_403`: ele chama a rota
direto, sem passar pela tela, que é o que alguém faria com `curl`. Esconder o
botão não é autorização — §32.
"""

from __future__ import annotations

import io
from unittest import mock

import openpyxl
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from workspace.models.ponto import (
    AcaoPonto,
    ColaboradorPonto,
    EnvioPonto,
    EventoPonto,
    LotePonto,
    ModoEnvio,
    SituacaoLote,
)
from workspace.services import ponto_lote as lot

pytestmark = pytest.mark.django_db

TELEFONE_TESTE = "(19) 99555-0001"


def planilha_bytes(linhas=None) -> bytes:
    colunas = ["Data", "Código", "CPF", "Senha", "Funcionário", "Entrada",
               "Pausa", "Retorno", "Saída", "Observação", "Telefone"]
    linhas = linhas or [
        ["15/09/2026", "1511", "11122233344", "3789", "JOAO SILVA", None,
         "12:00", "13:00", "18:00", "", "(019) 98888-7777"],
        ["16/09/2026", "1511", "11122233344", "3789", "JOAO SILVA", "08:00",
         "12:00", "13:00", None, "", "(019) 98888-7777"],
        ["15/09/2026", "1275", "55566677788", "2241", "MARIA LIMA", None,
         "12:00", "13:00", "18:00", "", "=VLOOKUP(A1;B:C;2;0)"],
    ]
    livro = openpyxl.Workbook()
    aba = livro.active
    aba.append(colunas)
    for linha in linhas:
        aba.append(linha)
    buffer = io.BytesIO()
    livro.save(buffer)
    return buffer.getvalue()


def arquivo(nome="ajuste-de-ponto.xlsx", conteudo=None):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(
        nome,
        planilha_bytes() if conteudo is None else conteudo,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@pytest.fixture
def rh(db):
    """Quem opera: lê, importa e testa — mas NÃO dispara em produção.

    O e-mail é o identificador desta base; não há `username`.
    """
    return get_user_model().objects.create_user(
        "rh@icodev.com.br", password="senha-de-teste-123", nome="Rita RH"
    )


@pytest.fixture
def chefe(db):
    """Superusuário — passa em tudo, inclusive produção."""
    return get_user_model().objects.create_superuser(
        "chefe@icodev.com.br", password="senha-de-teste-123", nome="Chefe"
    )


def liberar(pessoa, *permissoes):
    """Troca `pode()` por uma lista fixa, sem montar organograma no teste."""
    return mock.patch(
        "workspace.services.ponto_lote.pode",
        side_effect=lambda p, perm, **kw: perm in permissoes,
    )


# ── Permissão — §32 e §39 ───────────────────────────────────────────


def test_sem_permissao_nenhuma_a_tela_e_negada(client, rh):
    client.force_login(rh)
    with liberar(rh):
        resposta = client.get(reverse("workspace:pendencias_ponto"))
    assert resposta.status_code == 403


def test_com_permissao_de_leitura_a_tela_abre(client, rh):
    client.force_login(rh)
    with liberar(rh, lot.PERM_LER):
        resposta = client.get(reverse("workspace:pendencias_ponto"))
    assert resposta.status_code == 200
    assert b"Nenhuma planilha processada" in resposta.content


def test_sem_permissao_producao_da_403_mesmo_chamando_a_rota_direto(client, rh):
    """O teste do §39: `curl` não passa por cima da autorização."""
    lote = LotePonto.objects.create(arquivo_nome="a.xlsx", situacao=SituacaoLote.VALIDADO)
    client.force_login(rh)

    with liberar(rh, lot.PERM_LER, lot.PERM_IMPORTAR, lot.PERM_TESTAR):
        resposta = client.post(
            reverse("workspace:ponto_enviar", args=[lote.pk]),
            {"modo": ModoEnvio.PRODUCAO, "confirmacao": "ENVIAR"},
        )

    assert resposta.status_code == 403
    assert EnvioPonto.objects.count() == 0


def test_quem_so_le_nao_importa(client, rh):
    client.force_login(rh)
    with liberar(rh, lot.PERM_LER):
        resposta = client.post(
            reverse("workspace:ponto_importar"), {"planilha": arquivo()}
        )
    assert resposta.status_code == 403
    assert LotePonto.objects.count() == 0


def test_producao_sem_a_palavra_digitada_nao_envia(client, chefe):
    """§21 — a confirmação é conferida no servidor."""
    lote = LotePonto.objects.create(arquivo_nome="a.xlsx", situacao=SituacaoLote.VALIDADO)
    ColaboradorPonto.objects.create(
        lote=lote, nome="João", telefone_normalizado="5519995550001", selecionado=True
    )
    client.force_login(chefe)

    resposta = client.post(
        reverse("workspace:ponto_enviar", args=[lote.pk]),
        {"modo": ModoEnvio.PRODUCAO, "confirmacao": "sim"},
        follow=True,
    )

    assert EnvioPonto.objects.count() == 0
    assert b"Digite ENVIAR" in resposta.content


# ── Upload — §9 e §39 ───────────────────────────────────────────────


def test_upload_valido_cria_lote_agrupado(client, rh):
    client.force_login(rh)
    with liberar(rh, lot.PERM_LER, lot.PERM_IMPORTAR):
        client.post(reverse("workspace:ponto_importar"), {"planilha": arquivo()})

    lote = LotePonto.objects.get()
    assert lote.situacao == SituacaoLote.VALIDADO
    # Três linhas, duas pessoas — uma delas com duas pendências.
    assert lote.colaboradores.count() == 2
    joao = lote.colaboradores.get(nome="JOAO SILVA")
    assert joao.quantidade_pendencias == 2
    assert joao.telefone_normalizado == "5519988887777"


def test_o_cpf_e_a_senha_nao_sao_gravados(client, rh):
    """A planilha traz os dois; nada do fluxo precisa deles."""
    client.force_login(rh)
    with liberar(rh, lot.PERM_LER, lot.PERM_IMPORTAR):
        client.post(reverse("workspace:ponto_importar"), {"planilha": arquivo()})

    tudo = str(list(ColaboradorPonto.objects.values()))
    assert "11122233344" not in tudo
    assert "55566677788" not in tudo


def test_a_planilha_nao_fica_guardada(client, rh):
    """Fica o digest, não o arquivo — §30."""
    client.force_login(rh)
    with liberar(rh, lot.PERM_LER, lot.PERM_IMPORTAR):
        client.post(reverse("workspace:ponto_importar"), {"planilha": arquivo()})

    lote = LotePonto.objects.get()
    assert len(lote.arquivo_digest) == 64
    assert not hasattr(lote, "arquivo")


def test_quem_tem_formula_no_telefone_nasce_desmarcado(client, rh):
    """§15 e §35 — inválido nunca entra no disparo por padrão."""
    client.force_login(rh)
    with liberar(rh, lot.PERM_LER, lot.PERM_IMPORTAR):
        client.post(reverse("workspace:ponto_importar"), {"planilha": arquivo()})

    maria = ColaboradorPonto.objects.get(nome="MARIA LIMA")
    assert maria.selecionado is False
    assert maria.pode_produzir is False
    assert maria.motivo_sem_telefone == "Telefone não disponível"


@pytest.mark.parametrize(
    "nome,conteudo,trecho",
    [
        ("ajuste.txt", b"qualquer coisa", "Formato não aceito"),
        ("ajuste.xlsx", b"", "vazio"),
        ("ajuste.xlsx", b"nao sou um zip", "não é uma planilha"),
    ],
)
def test_upload_ruim_e_recusado_com_mensagem(client, rh, nome, conteudo, trecho):
    client.force_login(rh)
    with liberar(rh, lot.PERM_LER, lot.PERM_IMPORTAR):
        resposta = client.post(
            reverse("workspace:ponto_importar"),
            {"planilha": arquivo(nome, conteudo)},
            follow=True,
        )
    assert trecho.encode() in resposta.content
    assert not LotePonto.objects.filter(situacao=SituacaoLote.VALIDADO).exists()


def test_planilha_sem_coluna_obrigatoria_diz_quais_faltam(client, rh):
    """§10 — nunca continuar em silêncio."""
    livro = openpyxl.Workbook()
    livro.active.append(["Data", "Pausa", "Retorno", "Saída"])
    livro.active.append(["15/09/2026", "12:00", "13:00", "18:00"])
    buffer = io.BytesIO()
    livro.save(buffer)

    client.force_login(rh)
    with liberar(rh, lot.PERM_LER, lot.PERM_IMPORTAR):
        resposta = client.post(
            reverse("workspace:ponto_importar"),
            {"planilha": arquivo("ruim.xlsx", buffer.getvalue())},
            follow=True,
        )

    assert b"Funcion\xc3\xa1rio" in resposta.content
    assert b"Entrada" in resposta.content


# ── Correção de telefone — §14 ──────────────────────────────────────


def test_corrigir_telefone_vale_so_no_lote_e_deixa_auditoria(client, rh):
    client.force_login(rh)
    with liberar(rh, lot.PERM_LER, lot.PERM_IMPORTAR):
        client.post(reverse("workspace:ponto_importar"), {"planilha": arquivo()})
        maria = ColaboradorPonto.objects.get(nome="MARIA LIMA")
        client.post(
            reverse("workspace:ponto_corrigir", args=[maria.pk]),
            {"telefone": "(19) 99555-0002"},
        )

    maria.refresh_from_db()
    assert maria.telefone_corrigido == "5519995550002"
    assert maria.pode_produzir is True

    evento = EventoPonto.objects.get(acao=AcaoPonto.ALTERACAO_TELEFONE)
    assert evento.quem == rh
    # O número inteiro não é repetido na auditoria — §33.
    assert "5519995550002" not in evento.detalhe
    assert "****" in evento.detalhe


# ── O caminho inteiro — §41 ─────────────────────────────────────────


def test_do_upload_ao_envio_de_teste(client, rh, settings):
    """O fluxo do §41, com o n8n simulado."""
    settings.PONTO_N8N_WEBHOOK_URL = "http://n8n.local/webhook/ponto"
    client.force_login(rh)

    with liberar(rh, lot.PERM_LER, lot.PERM_IMPORTAR, lot.PERM_TESTAR):
        client.post(reverse("workspace:ponto_importar"), {"planilha": arquivo()})
        lote = LotePonto.objects.get()

        contexto = mock.MagicMock()
        contexto.__enter__.return_value.read.return_value = b'{"resultados": []}'
        contexto.__exit__.return_value = False

        with mock.patch("urllib.request.urlopen", return_value=contexto) as chamada:
            resposta = client.post(
                reverse("workspace:ponto_enviar", args=[lote.pk]),
                {"modo": ModoEnvio.TESTE, "telefone_teste": TELEFONE_TESTE},
                follow=True,
            )

    lote.refresh_from_db()
    assert lote.situacao == SituacaoLote.CONCLUIDO
    assert b"Envio conclu\xc3\xaddo" in resposta.content

    # Só João foi: Maria tem fórmula no telefone e nasceu desmarcada.
    envio = EnvioPonto.objects.get()
    assert envio.colaborador.nome == "JOAO SILVA"
    # E o destino é o telefone de teste, não o dele.
    assert envio.destino == "5519995550001"
    assert envio.destino != "5519988887777"

    # O que saiu pela rede não leva o telefone do colaborador.
    corpo = chamada.call_args[0][0].data.decode("utf-8")
    assert "5519988887777" not in corpo
    assert '"loteId"' in corpo

    # E a auditoria registrou o caminho inteiro.
    acoes = set(EventoPonto.objects.values_list("acao", flat=True))
    assert {AcaoPonto.UPLOAD, AcaoPonto.VALIDACAO, AcaoPonto.TESTE_SOLICITADO,
            AcaoPonto.TESTE_EXECUTADO, AcaoPonto.ENVIO_CONCLUIDO} <= acoes


def test_historico_lista_o_lote(client, rh):
    client.force_login(rh)
    with liberar(rh, lot.PERM_LER, lot.PERM_IMPORTAR):
        client.post(reverse("workspace:ponto_importar"), {"planilha": arquivo()})
        resposta = client.get(reverse("workspace:ponto_historico"))

    assert resposta.status_code == 200
    assert b"ajuste-de-ponto.xlsx" in resposta.content
    assert b"TESTE" in resposta.content


def test_a_previa_mostra_a_mensagem_e_nao_tem_botao_de_enviar(client, rh):
    """§17 — conferir e disparar não podem ser a mesma tela."""
    client.force_login(rh)
    with liberar(rh, lot.PERM_LER, lot.PERM_IMPORTAR):
        client.post(reverse("workspace:ponto_importar"), {"planilha": arquivo()})
        joao = ColaboradorPonto.objects.get(nome="JOAO SILVA")
        resposta = client.get(reverse("workspace:ponto_mensagem", args=[joao.pk]))

    corpo = resposta.content.decode()
    assert "Prezado(a) colaborador(a)" in corpo
    assert "PontoTel" in corpo
    assert "ausência de marcação de entrada" in corpo
    assert 'name="modo"' not in corpo


def test_progresso_responde_json(client, rh):
    lote = LotePonto.objects.create(arquivo_nome="a.xlsx")
    client.force_login(rh)
    with liberar(rh, lot.PERM_LER):
        resposta = client.get(reverse("workspace:ponto_progresso", args=[lote.pk]))

    assert resposta.status_code == 200
    assert resposta.json()["total"] == 0


# ── A recarga em laço ───────────────────────────────────────────────


def _lote_concluido(rh):
    """Um lote que já terminou, com envios registrados."""
    lote = LotePonto.objects.create(
        arquivo_nome="a.xlsx",
        quem_importou=rh,
        situacao=SituacaoLote.CONCLUIDO_COM_ERROS,
        telefone_teste="11955550001",
    )
    colaborador = ColaboradorPonto.objects.create(
        lote=lote, nome="João", telefone_normalizado="5519995550001", selecionado=True
    )
    EnvioPonto.objects.create(
        lote=lote, colaborador=colaborador, modo=ModoEnvio.TESTE,
        destino="5511955550001", situacao="erro", erro="falhou",
    )
    return lote


def test_lote_concluido_nao_pede_polling(client, rh):
    """A recarga infinita: o gancho num lote pronto fazia o script perguntar,
    ver `terminou`, recarregar — e a página recarregada pedia de novo. A cada
    três segundos, apagando o que a pessoa digitava no telefone de teste."""
    lote = _lote_concluido(rh)
    client.force_login(rh)

    with liberar(rh, lot.PERM_LER):
        resposta = client.get(f"{reverse('workspace:pendencias_ponto')}?lote={lote.pk}")

    corpo = resposta.content.decode()
    assert "data-ponto-progresso" not in corpo, "lote pronto não pode pedir polling"
    assert 'data-ponto-terminou="1"' in corpo, "e o JS precisa saber que já estava pronto"


def test_lote_em_andamento_pede_polling(client, rh):
    """O outro lado: enquanto roda, a tela precisa acompanhar."""
    lote = _lote_concluido(rh)
    lote.situacao = SituacaoLote.PROCESSANDO
    lote.save(update_fields=["situacao"])
    client.force_login(rh)

    with liberar(rh, lot.PERM_LER):
        corpo = client.get(
            f"{reverse('workspace:pendencias_ponto')}?lote={lote.pk}"
        ).content.decode()

    assert "data-ponto-progresso" in corpo
    assert 'data-ponto-terminou="0"' in corpo


def test_sem_webhook_os_envios_nao_ficam_pendentes(client, rh, settings):
    """O lote fechava como "concluído com erros" e cada linha dizia `pendente`:
    a tela afirmava que terminou e a pessoa afirmava que ainda ia sair."""
    settings.PONTO_N8N_WEBHOOK_URL = ""
    client.force_login(rh)

    with liberar(rh, lot.PERM_LER, lot.PERM_IMPORTAR, lot.PERM_TESTAR):
        client.post(reverse("workspace:ponto_importar"), {"planilha": arquivo()})
        lote = LotePonto.objects.get()
        resposta = client.post(
            reverse("workspace:ponto_enviar", args=[lote.pk]),
            {"modo": ModoEnvio.TESTE, "telefone_teste": TELEFONE_TESTE},
            follow=True,
        )

    assert b"n8n n\xc3\xa3o est\xc3\xa1 configurada" in resposta.content
    situacoes = set(EnvioPonto.objects.values_list("situacao", flat=True))
    assert situacoes == {"erro"}, f"nenhum envio pode ficar pendente: {situacoes}"


def test_salvar_uma_pagina_nao_desmarca_as_outras(client, rh):
    """Com a tabela paginada de 10 em 10, o POST só traz as linhas da tela.
    Desmarcar quem não veio apagaria a seleção das outras páginas."""
    lote = _lote_concluido(rh)
    for i in range(11):
        ColaboradorPonto.objects.create(
            lote=lote, nome=f"Pessoa {i:02d}", telefone_normalizado="5519995550001",
            selecionado=True,
        )
    client.force_login(rh)

    with liberar(rh, lot.PERM_LER, lot.PERM_IMPORTAR):
        corpo = client.get(
            f"{reverse('workspace:pendencias_ponto')}?lote={lote.pk}"
        ).content.decode()
        assert "Página 1 de 2" in corpo
        assert corpo.count('name="na_pagina"') == 10
        assert "p=2#colaboradores" in corpo, "trocar de página não pode voltar ao topo"
        assert 'href="#passo-revisar"' in corpo, "o passo leva à seção dele"
        assert "Validar" not in corpo, "validar roda na importação, não é passo"

        primeira = ColaboradorPonto.objects.filter(lote=lote)[:10]
        client.post(
            reverse("workspace:ponto_selecionar", args=[lote.pk]),
            {"na_pagina": [c.pk for c in primeira], "colaborador": []},
        )

    assert ColaboradorPonto.objects.filter(lote=lote, selecionado=False).count() == 10
    assert ColaboradorPonto.objects.filter(lote=lote, selecionado=True).count() == 2
