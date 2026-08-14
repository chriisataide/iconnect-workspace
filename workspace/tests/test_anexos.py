"""Anexos — upload de verdade, armazenamento privado e autorização.

O que estes testes protegem, em ordem de gravidade se quebrar:

1. **Não existe URL pública.** O arquivo mora fora de MEDIA_ROOT, que o nginx
   serve sem autenticação (`docker/nginx.conf`, `location /media/`). Se alguém
   trocar o storage por um com `base_url`, um `.url` no template passa a vazar
   atestado médico. O teste falha antes.
2. **Terceiro não baixa.** Nem colega, nem gestor de outra equipe.
3. **Campo obrigatório de arquivo exige arquivo**, não texto — era o bug que
   este módulo nasceu para corrigir.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.conf import settings

from identidade.tests import fabricas as f
from workspace.models import (
    Anexo,
    GrupoCatalogo,
    ItemCatalogo,
    RegraAprovacao,
    SolicitacaoServico,
    TipoAprovador,
    TipoCampo,
)
from workspace.services import anexos as anx
from workspace.services import catalogo as svc
from workspace.storage import ArmazenamentoPrivado, caminho_do_anexo

# JPEG mínimo válido: os magic bytes são o que o validador confere.
JPEG = b"\xff\xd8\xff\xe0" + b"0" * 64
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
PDF = b"%PDF-1.4\n" + b"0" * 64


def upload(nome="cupom.jpg", conteudo=JPEG, tipo="image/jpeg"):
    return SimpleUploadedFile(nome, conteudo, content_type=tipo)


@pytest.fixture
def privado(settings):
    """O diretório privado desta execução.

    Quem redireciona para temporário é o autouse `_anexos_em_diretorio_
    temporario`, no conftest da raiz — vale para a suíte inteira, não só para
    este arquivo.
    """
    return settings.ARQUIVOS_PRIVADOS_ROOT


@pytest.fixture
def cenario(privado):
    diretor, gestor, ana, bruno = (
        f.pessoa(n) for n in ("diretor", "gestor", "ana", "bruno")
    )
    f.lotar(diretor, centro_custo_codigo="1000")
    f.lotar(gestor, gestor=diretor, centro_custo_codigo="1008")
    f.lotar(ana, gestor=gestor, centro_custo_codigo="1008")
    # Bruno é de outra equipe: o terceiro que não deve ver nada.
    f.lotar(bruno, centro_custo_codigo="2000")
    RegraAprovacao.objects.create(dominio="*", tipo=TipoAprovador.GESTOR_DIRETO, ordem=10)

    item = ItemCatalogo.objects.create(
        chave="reembolso",
        nome="Reembolso",
        descricao_curta="Despesa que você pagou",
        grupo=GrupoCatalogo.DINHEIRO,
        dominio="fin.reembolso",
        icone="wallet",
        exige_valor=True,
        prazo_prometido_dias=5,
        campos=[
            {
                "chave": "comprovantes",
                "rotulo": "Comprovantes",
                "tipo": TipoCampo.ARQUIVO,
                "obrigatorio": True,
            }
        ],
    )
    return {
        "ana": ana, "gestor": gestor, "diretor": diretor, "bruno": bruno, "item": item
    }


def pedir(cenario, quem=None, arquivos=None, valor="184.50"):
    return svc.solicitar(
        cenario["item"],
        quem or cenario["ana"],
        dados={},
        valor=Decimal(valor),
        arquivos=arquivos if arquivos is not None else {"comprovantes": [upload()]},
    )


# ── 1. Não existe URL pública ───────────────────────────────────────


@pytest.mark.django_db
def test_arquivo_nao_tem_url_publica(cenario):
    """A trava central: `.url` levanta em vez de devolver endereço.

    Storage sem `base_url` transforma um `{{ anexo.arquivo.url }}` escrito por
    distração em erro de desenvolvimento, e não em vazamento silencioso.
    """
    solicitacao = pedir(cenario)
    anexo = solicitacao.anexos.get()

    with pytest.raises(ValueError):
        anexo.arquivo.url


@pytest.mark.django_db
def test_arquivo_fica_fora_de_media_root(cenario, privado, settings):
    solicitacao = pedir(cenario)
    caminho = Path(solicitacao.anexos.get().arquivo.path).resolve()

    assert Path(privado).resolve() in caminho.parents
    assert Path(settings.MEDIA_ROOT).resolve() not in caminho.parents, (
        "anexo em MEDIA_ROOT é servido pelo nginx sem autenticação"
    )


@pytest.mark.django_db
def test_nome_no_disco_nao_e_o_nome_do_usuario(cenario):
    """Nome de arquivo conta sobre a pessoa antes de alguém abrir o arquivo."""
    solicitacao = pedir(
        cenario, arquivos={"comprovantes": [upload("atestado-depressao.pdf", PDF, "application/pdf")]}
    )
    anexo = solicitacao.anexos.get()

    assert anexo.nome_original == "atestado-depressao.pdf"
    assert "depressao" not in anexo.arquivo.name
    assert anexo.arquivo.name.endswith(".pdf"), "a extensão é preservada"


def test_caminho_recusa_escapar_do_diretorio(privado):
    """Guarda o comportamento: `safe_join` do Django recusa o escape.

    O teste existe para que alguém que sobrescreva `path()` no futuro descubra
    na hora que desligou a proteção.
    """
    with pytest.raises(SuspiciousFileOperation):
        ArmazenamentoPrivado().path("../../etc/passwd")


def test_caminho_do_anexo_sem_solicitacao_nao_estoura():
    """Chamado antes do save em alguns fluxos do Django — não pode explodir."""

    class Fake:
        solicitacao_id = None

    assert caminho_do_anexo(Fake(), "x.jpg").startswith("anexos/orfao/")


# ── 2. Quem pode baixar ─────────────────────────────────────────────


@pytest.mark.django_db
def test_solicitante_baixa_o_proprio_anexo(client, cenario):
    solicitacao = pedir(cenario)
    anexo = solicitacao.anexos.get()

    client.force_login(cenario["ana"])
    resposta = client.get(reverse("workspace:baixar_anexo", args=(anexo.pk,)))

    assert resposta.status_code == 200
    assert b"".join(resposta.streaming_content) == JPEG


@pytest.mark.django_db
def test_aprovador_da_cadeia_baixa(client, cenario):
    """Aprovar reembolso sem abrir o comprovante é carimbar."""
    solicitacao = pedir(cenario)
    anexo = solicitacao.anexos.get()

    client.force_login(cenario["gestor"])
    assert client.get(reverse("workspace:baixar_anexo", args=(anexo.pk,))).status_code == 200


@pytest.mark.django_db
def test_terceiro_nao_baixa(client, cenario):
    solicitacao = pedir(cenario)
    anexo = solicitacao.anexos.get()

    client.force_login(cenario["bruno"])
    assert client.get(reverse("workspace:baixar_anexo", args=(anexo.pk,))).status_code == 403


@pytest.mark.django_db
def test_anonimo_nao_baixa_anexo_de_ninguem(client, cenario):
    """O Workspace é aberto para LER as telas; anexo não é tela.

    Este teste substitui um que exigia o contrário. O acesso aberto fazia
    `pode_baixar()` responder pela primeira pessoa do organograma, e o
    atestado médico dela saía por esta URL para qualquer visitante — o mesmo
    furo que o projeto fechou ao tirar os anexos de `MEDIA_ROOT`, reaberto por
    outro caminho.
    """
    anexo = pedir(cenario).anexos.get()
    resposta = client.get(reverse("workspace:baixar_anexo", args=(anexo.pk,)))

    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/entrar/")


@pytest.mark.django_db
def test_pode_baixar_recusa_anonimo_direto(cenario):
    from django.contrib.auth.models import AnonymousUser

    anexo = pedir(cenario).anexos.get()
    assert not anx.pode_baixar(AnonymousUser(), anexo)
    assert not anx.pode_baixar(None, anexo)


@pytest.mark.django_db
def test_quem_ja_decidiu_continua_vendo(client, cenario):
    """Auditoria: a etapa decidida não apaga o acesso de quem decidiu."""
    from workspace.services import aprovacao as apr

    solicitacao = pedir(cenario)
    anexo = solicitacao.anexos.get()
    apr.decidir(solicitacao.aprovacao, cenario["gestor"], apr.Decisao.APROVAR)

    client.force_login(cenario["gestor"])
    assert client.get(reverse("workspace:baixar_anexo", args=(anexo.pk,))).status_code == 200


@pytest.mark.django_db
def test_quem_decidiu_por_delegacao_continua_vendo(cenario):
    """O caso que `decidido_por` existe para cobrir.

    Na delegação, a etapa continua sendo do titular (`aprovador` = gestor) e
    quem assinou é o substituto. Se a autorização olhasse só `aprovador`, o
    substituto perderia o acesso ao comprovante do pedido que ele mesmo
    aprovou — e é justamente ele quem precisa responder por essa decisão numa
    auditoria.
    """
    from datetime import date, timedelta

    from workspace.services import aprovacao as apr

    substituto = f.pessoa("carlos")
    f.lotar(substituto, centro_custo_codigo="1008")
    f.delegar(
        cenario["gestor"],
        substituto,
        date.today() - timedelta(days=1),
        date.today() + timedelta(days=7),
    )

    solicitacao = pedir(cenario)
    anexo = solicitacao.anexos.get()

    assert not anx.pode_baixar(substituto, anexo), "antes de decidir, não vê"

    apr.decidir(solicitacao.aprovacao, substituto, apr.Decisao.APROVAR)
    etapa = solicitacao.aprovacao.etapas.first()
    assert etapa.aprovador == cenario["gestor"], "a etapa segue do titular"
    assert etapa.decidido_por == substituto

    assert anx.pode_baixar(substituto, anexo)


@pytest.mark.django_db
def test_falha_ao_gravar_aparece_na_tela(client, cenario, monkeypatch):
    """Formulário que recusa sem dizer nada é pior que a mensagem crua.

    Simula o que a revalidação não reproduz — disco cheio, permissão de escrita
    — para garantir que a tela não volta silenciosamente limpa.
    """
    from workspace.services import anexos as servico_anexos

    def explode(*_a, **_k):
        raise servico_anexos.AnexoError("Sem espaço em disco.")

    monkeypatch.setattr(servico_anexos, "guardar", explode)

    client.force_login(cenario["ana"])
    corpo = client.post(
        reverse("workspace:pedir", args=(cenario["item"].chave,)),
        {"valor": "184,50", "comprovantes": upload()},
    ).content.decode()

    assert "Sem espaço em disco." in corpo
    assert not SolicitacaoServico.objects.exists()


@pytest.mark.django_db
def test_pedido_auto_aprovado_sem_aprovacao_nao_quebra_autorizacao(cenario):
    """Auto-aprovado não tem cadeia — `pode_baixar` não pode assumir que tem."""
    cenario["item"].limite_auto_aprovacao = Decimal("1000")
    cenario["item"].save()

    solicitacao = pedir(cenario)
    assert solicitacao.auto_aprovada
    assert solicitacao.aprovacao is None

    anexo = solicitacao.anexos.get()
    assert anx.pode_baixar(cenario["ana"], anexo)
    assert not anx.pode_baixar(cenario["bruno"], anexo)


@pytest.mark.django_db
def test_arquivo_ausente_no_disco_da_404(client, cenario):
    """Metadado sem arquivo é erro de operação, não 500."""
    solicitacao = pedir(cenario)
    anexo = solicitacao.anexos.get()
    Path(anexo.arquivo.path).unlink()

    client.force_login(cenario["ana"])
    assert client.get(reverse("workspace:baixar_anexo", args=(anexo.pk,))).status_code == 404


@pytest.mark.django_db
def test_download_e_sempre_anexo_nunca_inline(client, cenario):
    """SVG ou HTML renderizado inline abriria XSS na nossa origem."""
    anexo = pedir(cenario).anexos.get()
    client.force_login(cenario["ana"])
    resposta = client.get(reverse("workspace:baixar_anexo", args=(anexo.pk,)))

    assert resposta["Content-Disposition"].startswith("attachment")
    assert "cupom.jpg" in resposta["Content-Disposition"]


# ── 3. Validação ────────────────────────────────────────────────────


@pytest.mark.django_db
def test_campo_de_arquivo_obrigatorio_exige_arquivo(cenario):
    """O bug de origem: digitar o nome do arquivo passava a validação."""
    impedimentos = svc.verificar(
        cenario["item"],
        cenario["ana"],
        dados={"comprovantes": "cupom.jpg"},  # texto, não arquivo
        valor=Decimal("184.50"),
        arquivos={},
    )

    assert [i.campo for i in impedimentos] == ["comprovantes"]
    assert "Anexe comprovantes" in impedimentos[0].motivo


@pytest.mark.django_db
def test_pedido_sem_anexo_nao_e_criado(cenario):
    with pytest.raises(svc.SolicitacaoError):
        pedir(cenario, arquivos={})

    assert not SolicitacaoServico.objects.exists(), "nada meio-criado"
    assert not Anexo.objects.exists()


@pytest.mark.django_db
def test_extensao_que_mente_sobre_o_conteudo_e_recusada(cenario):
    """`.jpg` que na verdade é outra coisa — a checagem de magic bytes."""
    falso = SimpleUploadedFile("foto.jpg", b"MZ\x90\x00 executavel", content_type="image/jpeg")

    with pytest.raises(svc.SolicitacaoError):
        pedir(cenario, arquivos={"comprovantes": [falso]})

    assert not Anexo.objects.exists()


@pytest.mark.django_db
def test_tipo_nao_permitido_e_recusado(cenario):
    with pytest.raises(svc.SolicitacaoError):
        pedir(
            cenario,
            arquivos={"comprovantes": [upload("script.sh", b"#!/bin/sh\n", "text/x-sh")]},
        )


@pytest.mark.django_db
def test_arquivo_grande_e_recusado(cenario):
    grande = SimpleUploadedFile(
        "enorme.png", PNG + b"0" * (11 * 1024 * 1024), content_type="image/png"
    )
    recusas = anx.verificar_lote({"comprovantes": [grande]})

    assert recusas and "10MB" in recusas[0].motivo


@pytest.mark.django_db
def test_limite_de_arquivos_por_campo(cenario):
    demais = [upload(f"c{i}.jpg") for i in range(anx.MAXIMO_POR_CAMPO + 1)]
    recusas = anx.verificar_lote({"comprovantes": demais})

    assert recusas and str(anx.MAXIMO_POR_CAMPO) in recusas[0].motivo


@pytest.mark.django_db
def test_tudo_ou_nada_quando_um_do_lote_falha(cenario):
    """Gravar dois e recusar o terceiro deixa a pessoa reenviando os três."""
    bom, ruim = upload("ok.jpg"), upload("mentira.jpg", b"MZ executavel")

    with pytest.raises(svc.SolicitacaoError):
        pedir(cenario, arquivos={"comprovantes": [bom, ruim]})

    assert not Anexo.objects.exists(), "o arquivo válido também não entrou"


@pytest.mark.django_db
def test_guardar_levanta_quando_chamado_direto_com_invalido(cenario):
    """`guardar()` revalida: quem chama não é a autoridade."""
    solicitacao = pedir(cenario)
    with pytest.raises(anx.AnexoError):
        anx.guardar(
            solicitacao, {"comprovantes": [upload("x.jpg", b"MZ")]}, cenario["ana"]
        )


@pytest.mark.django_db
def test_multiplos_arquivos_no_mesmo_campo(cenario):
    """Ida e volta são dois cupons."""
    solicitacao = pedir(
        cenario, arquivos={"comprovantes": [upload("ida.jpg"), upload("volta.jpg")]}
    )

    assert solicitacao.anexos.count() == 2
    assert {a.nome_original for a in solicitacao.anexos.all()} == {"ida.jpg", "volta.jpg"}


@pytest.mark.django_db
def test_campo_de_arquivo_opcional_aceita_vazio(cenario):
    cenario["item"].campos = [
        {"chave": "comprovantes", "rotulo": "Comprovantes",
         "tipo": TipoCampo.ARQUIVO, "obrigatorio": False}
    ]
    cenario["item"].save()

    solicitacao = pedir(cenario, arquivos={"comprovantes": []})
    assert solicitacao.anexos.count() == 0


# ── A tela ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_formulario_tem_enctype_e_input_de_arquivo(client, cenario):
    """Sem `enctype`, `request.FILES` chega vazio e o anexo é descartado."""
    client.force_login(cenario["ana"])
    corpo = client.get(
        reverse("workspace:pedir", args=(cenario["item"].chave,))
    ).content.decode()

    assert 'enctype="multipart/form-data"' in corpo
    assert 'type="file"' in corpo
    assert "nome do arquivo" not in corpo, "o placeholder da maquete ficou para trás"


@pytest.mark.django_db
def test_envio_pela_tela_cria_o_anexo(client, cenario):
    client.force_login(cenario["ana"])
    resposta = client.post(
        reverse("workspace:pedir", args=(cenario["item"].chave,)),
        {"valor": "184,50", "comprovantes": upload()},
    )

    assert resposta.status_code == 302
    anexo = Anexo.objects.get()
    assert anexo.nome_original == "cupom.jpg"
    assert anexo.criado_por == cenario["ana"]
    assert anexo.tipo_mime == "image/jpeg"


@pytest.mark.django_db
def test_tela_mostra_o_motivo_quando_o_arquivo_e_recusado(client, cenario):
    client.force_login(cenario["ana"])
    corpo = client.post(
        reverse("workspace:pedir", args=(cenario["item"].chave,)),
        {"valor": "184,50", "comprovantes": upload("falso.jpg", b"MZ executavel")},
    ).content.decode()

    assert "não corresponde" in corpo or "não permitido" in corpo
    assert not Anexo.objects.exists()


@pytest.mark.django_db
def test_minhas_solicitacoes_lista_o_anexo(client, cenario):
    pedir(cenario)
    client.force_login(cenario["ana"])
    corpo = client.get(reverse("workspace:minhas_solicitacoes")).content.decode()

    assert "cupom.jpg" in corpo
    assert reverse("workspace:baixar_anexo", args=(Anexo.objects.get().pk,)) in corpo


@pytest.mark.django_db
def test_dossie_da_bandeja_mostra_a_comprovacao(client, cenario):
    pedir(cenario)
    client.force_login(cenario["gestor"])
    corpo = client.get(reverse("workspace:aprovacoes")).content.decode()

    assert "Comprovação" in corpo
    assert "cupom.jpg" in corpo


@pytest.mark.django_db
def test_nenhuma_tela_expoe_caminho_do_disco(client, cenario):
    """`anexo.arquivo.name` num template entregaria a estrutura do storage."""
    pedir(cenario)
    client.force_login(cenario["ana"])
    corpo = client.get(reverse("workspace:minhas_solicitacoes")).content.decode()

    assert "anexos/" not in corpo


@pytest.mark.django_db
def test_bandeja_sem_servico_ligado_nao_quebra(client, cenario):
    """Aprovação criada fora do catálogo — férias lançadas direto, por exemplo."""
    from workspace.services import aprovacao as apr

    apr.criar(
        dominio="rh.ferias",
        titulo="Férias de Ana",
        solicitante=cenario["ana"],
        origem_id="avulso-1",
    )
    client.force_login(cenario["gestor"])
    assert client.get(reverse("workspace:aprovacoes")).status_code == 200


# ── Apresentação ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "bytes_, esperado",
    [(512, "512 B"), (184320, "180 KB"), (2 * 1024 * 1024, "2 MB")],
)
def test_tamanho_legivel(bytes_, esperado):
    assert Anexo(tamanho=bytes_).tamanho_legivel == esperado


def test_str_e_o_nome_que_o_usuario_reconhece():
    """No admin e em log, o uuid do disco não diz nada a ninguém."""
    assert str(Anexo(nome_original="cupom-taxi.jpg")) == "cupom-taxi.jpg"
