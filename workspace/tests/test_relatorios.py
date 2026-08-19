"""§34–36 — relatório de entrega e relatório de ocorrência (CSI).

## O "assistente" do §35 é a ESTRUTURA, não IA

O que faz alguém desistir de um relatório de campo é a folha em branco: a pessoa
não sabe o que precisa ser dito, escreve pouco, e o relatório volta com pedido
de complemento três dias depois — quando ninguém lembra mais. Cinco perguntas
respondíveis são o que transforma "descreva a ocorrência" em algo que se faz.

## Emitido não muda, e é o ponto

Relatório de ocorrência é documento que alguém assina e que sai da empresa. Um
emitido editável é um documento que muda depois de entregue — e a única defesa
contra "não foi isso que eu recebi" é ele não poder ter mudado.

Correção de relatório errado é OUTRO relatório. Por isso cancelado continua
legível: a trilha entre os dois é o que permite explicar a divergência.

## Sobre o PDF

**Não há geração no servidor**, e isso é decisão declarada, não omissão. O
projeto não tem nenhuma dependência de terceiros em execução; `weasyprint` traz
Cairo e Pango, `reportlab` exige desenhar o layout em código. As duas são
escolhas de arquitetura, e não efeito colateral de uma tarefa.

A página emitida é desenhada para impressão e o navegador exporta em PDF. O que
os testes garantem é que ela sai SÓ com o documento — sem trilho, sem topbar,
sem botão.
"""

from __future__ import annotations

from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.models.relatorio import (
    EvidenciaRelatorio,
    Relatorio,
    SituacaoRelatorio,
    TipoRelatorio,
)
from workspace.services import relatorio as rel
from workspace.services.relatorio import RelatorioError

pytestmark = pytest.mark.django_db


OCORRENCIA = {
    "o_que_aconteceu": "Faltou energia às 14h30.",
    "acoes": "Acionamos o gerador em 4 minutos.",
    "resultado": "resolvido",
    "conclusao": "Sem perda de serviço. Recomenda-se revisar o nobreak.",
}
ENTREGA = {
    "responsavel_cliente": "João da Silva",
    "itens": "4 câmeras IP\n1 switch 24p",
    "conferido": "completo",
}


@pytest.fixture
def tecnico():
    pessoa = f.pessoa("tecnico")
    f.lotar(pessoa)
    return pessoa


def escrever(pessoa, tipo=TipoRelatorio.OCORRENCIA, dados=None, **extras):
    return rel.salvar(
        pessoa, tipo=tipo, titulo=extras.pop("titulo", "Queda de energia"),
        dados=dados if dados is not None else dict(OCORRENCIA), **extras,
    )


def _foto(nome="foto.jpg"):
    # JPEG mínimo — o validador confere magic bytes, então bytes aleatórios
    # seriam recusados por um motivo que não é o testado.
    return SimpleUploadedFile(nome, b"\xff\xd8\xff\xe0" + b"0" * 64, content_type="image/jpeg")


# ── O questionário (§35, §36) ───────────────────────────────────────


def test_cada_tipo_tem_o_seu_questionario():
    entrega = {c["chave"] for c in rel.questionario(TipoRelatorio.ENTREGA)}
    ocorrencia = {c["chave"] for c in rel.questionario(TipoRelatorio.OCORRENCIA)}

    assert {"responsavel_cliente", "itens", "conferido"} <= entrega
    assert {"o_que_aconteceu", "causa", "acoes", "resultado", "conclusao"} <= ocorrencia


def test_a_causa_da_ocorrencia_nao_e_obrigatoria():
    """Inventar causa é pior que assumir que não se sabe — e um campo
    obrigatório é exatamente o que faz alguém inventar."""
    causa = next(
        c for c in rel.questionario(TipoRelatorio.OCORRENCIA) if c["chave"] == "causa"
    )

    assert not causa.get("obrigatorio")
    assert "não se sabe" in causa["ajuda"]


def test_pendencias_so_aparece_quando_a_conferencia_nao_fechou():
    campo = next(
        c for c in rel.questionario(TipoRelatorio.ENTREGA) if c["chave"] == "pendencias"
    )

    assert rel.campo_ativo(campo, {"conferido": "parcial"})
    assert not rel.campo_ativo(campo, {"conferido": "completo"})
    assert not rel.campo_ativo(campo, {})


def test_faltando_lista_so_o_que_esta_ativo_e_em_branco():
    faltam = rel.faltando(TipoRelatorio.ENTREGA, {"conferido": "parcial"})

    assert "Quem recebeu" in faltam
    assert "Observações" not in faltam, "opcional não entra"
    assert "O que ficou pendente" in faltam, "condicional ativo entra"


def test_condicional_inativo_nao_e_cobrado():
    faltam = rel.faltando(TipoRelatorio.ENTREGA, dict(ENTREGA))

    assert faltam == []


# ── Rascunho e emissão ──────────────────────────────────────────────


def test_rascunho_nasce_editavel(tecnico):
    r = escrever(tecnico)

    assert r.situacao == SituacaoRelatorio.RASCUNHO
    assert r.editavel
    assert not r.emitido


def test_rascunho_aceita_campo_em_branco(tecnico):
    """Campo em branco no meio da redação é normal — a pessoa está escrevendo.
    A conferência é na emissão."""
    r = escrever(tecnico, dados={"o_que_aconteceu": "Ainda escrevendo"})

    assert r.pk is not None


def test_emitir_confere_os_obrigatorios(tecnico):
    """O que não pode é SAIR DA EMPRESA incompleto."""
    r = escrever(tecnico, dados={"o_que_aconteceu": "Só isso"})

    with pytest.raises(RelatorioError, match="Falta preencher"):
        rel.emitir(r, tecnico)


def test_a_recusa_diz_o_que_falta(tecnico):
    """"Formulário incompleto" manda a pessoa procurar. O nome dos campos
    resolve na primeira leitura."""
    r = escrever(tecnico, dados={"o_que_aconteceu": "Só isso"})

    with pytest.raises(RelatorioError, match="Ações executadas"):
        rel.emitir(r, tecnico)


def test_emitir_fecha_o_relatorio(tecnico):
    r = rel.emitir(escrever(tecnico), tecnico)

    assert r.emitido
    assert r.emitido_em is not None
    assert not r.editavel


def test_emitido_nao_se_edita(tecnico):
    """A única defesa contra "não foi isso que eu recebi" é o documento não
    poder ter mudado."""
    r = rel.emitir(escrever(tecnico), tecnico)

    with pytest.raises(RelatorioError, match="não pode ser alterado"):
        rel.salvar(tecnico, r, tipo=r.tipo, titulo="Outro", dados=dict(OCORRENCIA))


def test_emitido_nao_recebe_evidencia_nova(tecnico):
    r = rel.emitir(escrever(tecnico), tecnico)

    with pytest.raises(RelatorioError, match="não recebe evidência"):
        rel.anexar(r, _foto())


def test_emitir_duas_vezes_e_silencioso(tecnico):
    r = rel.emitir(escrever(tecnico), tecnico)
    quando = r.emitido_em

    rel.emitir(r, tecnico)

    r.refresh_from_db()
    assert r.emitido_em == quando


def test_so_quem_escreveu_emite(tecnico):
    outro = f.pessoa("outro")
    f.lotar(outro)
    r = escrever(tecnico)

    with pytest.raises(RelatorioError, match="Só quem escreveu"):
        rel.emitir(r, outro)


def test_cancelado_continua_legivel(tecnico):
    """A correção de um relatório errado é OUTRO relatório, e a trilha entre os
    dois é o que permite explicar a divergência depois."""
    r = rel.emitir(escrever(tecnico), tecnico)

    rel.cancelar(r, tecnico)

    assert Relatorio.objects.filter(pk=r.pk).exists()
    assert r.situacao == SituacaoRelatorio.CANCELADO


def test_cancelado_nao_volta_a_ser_emitido(tecnico):
    r = escrever(tecnico)
    rel.cancelar(r, tecnico)

    with pytest.raises(RelatorioError, match="cancelado"):
        rel.emitir(r, tecnico)


def test_tipo_invalido_e_recusado(tecnico):
    with pytest.raises(RelatorioError, match="Tipo"):
        rel.salvar(tecnico, tipo="fofoca", titulo="x")


def test_titulo_vazio_e_recusado(tecnico):
    with pytest.raises(RelatorioError, match="título"):
        escrever(tecnico, titulo="   ")


# ── Evidências ──────────────────────────────────────────────────────


def test_anexar_evidencia(tecnico):
    r = escrever(tecnico)

    rel.anexar(r, _foto("lacre.jpg"), legenda="Lacre intacto")

    evidencia = EvidenciaRelatorio.objects.get()
    assert evidencia.nome_original.endswith("lacre.jpg")
    assert evidencia.legenda == "Lacre intacto"


def test_arquivo_recusado_pelo_validador(tecnico):
    """Reusa o validador dos anexos — extensão, MIME e magic bytes. Um segundo
    validador aqui produziria dois caminhos de upload com regras diferentes, e
    é sempre o mais novo que esquece os magic bytes."""
    r = escrever(tecnico)
    ruim = SimpleUploadedFile("script.exe", b"MZ\x90\x00", content_type="application/x-msdownload")

    with pytest.raises(RelatorioError):
        rel.anexar(r, ruim)


def test_a_evidencia_nao_tem_url_publica(tecnico):
    """O modo normal de vazar arquivo sensível não é ataque: é um
    `{{ obj.arquivo.url }}` escrito por distração num template."""
    r = escrever(tecnico)
    rel.anexar(r, _foto())

    with pytest.raises(ValueError):
        EvidenciaRelatorio.objects.get().arquivo.url


# ── Quem vê o quê ───────────────────────────────────────────────────


def test_o_autor_ve_o_proprio(tecnico):
    r = escrever(tecnico)

    assert rel.pode_ver(r, tecnico)
    assert r in rel.visiveis_para(tecnico)


def test_outro_nao_ve(tecnico):
    outro = f.pessoa("outro")
    f.lotar(outro)
    r = escrever(tecnico)

    assert not rel.pode_ver(r, outro)
    assert r not in rel.visiveis_para(outro)


def test_quem_responde_pela_operacao_ve_todos(tecnico):
    """Relatório de ocorrência é documento de operação: quem responde por ela
    precisa ler os de todo mundo, senão a informação que justifica o relatório
    fica presa em quem já sabe do episódio."""
    supervisor = f.pessoa("supervisor")
    f.lotar(supervisor)
    f.atribuir(supervisor, f.papel("ops", ["ops.ler.global"], escopo="global"))
    r = escrever(tecnico)

    assert rel.pode_ver(r, supervisor)
    assert r in rel.visiveis_para(supervisor)


# ── A folha impressa ────────────────────────────────────────────────


def test_a_impressao_segue_a_ordem_do_questionario(tecnico):
    """Dicionário não tem ordem garantida entre versões de Python, e um
    relatório impresso com as perguntas embaralhadas é um documento que ninguém
    assina."""
    r = escrever(tecnico)

    rotulos = [linha["rotulo"] for linha in rel.para_impressao(r)]

    assert rotulos.index("O que aconteceu") < rotulos.index("Ações executadas")
    assert rotulos.index("Ações executadas") < rotulos.index("Conclusão")


def test_a_impressao_traduz_a_escolha(tecnico):
    """"resolvido" é chave de banco. O documento mostra a frase."""
    r = escrever(tecnico)

    valores = {linha["rotulo"]: linha["valor"] for linha in rel.para_impressao(r)}
    assert valores["Resultado"] == "Resolvido no local"


def test_a_impressao_omite_o_que_ficou_em_branco(tecnico):
    r = escrever(tecnico)

    rotulos = [linha["rotulo"] for linha in rel.para_impressao(r)]
    assert "Causa" not in rotulos


def test_a_folha_esconde_a_navegacao_na_impressao():
    """A exportação em PDF É isto — sem trilho, sem topbar, sem botão."""
    from pathlib import Path

    css = Path("workspace/static/workspace/src/workspace.css").read_text()
    bloco = css[css.index("@media print"):]

    for classe in (".au-topbar", ".au-rail", ".au-rodape", ".au-bot", ".au-nao-imprime"):
        assert classe in bloco, classe


def test_a_assinatura_so_aparece_no_emitido(client, tecnico):
    """Assinar rascunho é assinar documento que ainda vai mudar."""
    r = escrever(tecnico)
    client.force_login(tecnico)

    rascunho = client.get(reverse("workspace:relatorio_ver", args=[r.pk])).content.decode()
    assert "au-folha-assinatura" not in rascunho

    rel.emitir(r, tecnico)
    emitido = client.get(reverse("workspace:relatorio_ver", args=[r.pk])).content.decode()
    assert "au-folha-assinatura" in emitido


# ── As telas ────────────────────────────────────────────────────────


def test_a_lista_exige_sessao(client):
    resposta = client.get(reverse("workspace:relatorios"))

    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/entrar/")


def test_escrever_e_emitir_pela_tela(client, tecnico):
    client.force_login(tecnico)

    client.post(
        reverse("workspace:relatorio_novo"),
        {
            "tipo": TipoRelatorio.OCORRENCIA, "titulo": "Queda de energia",
            "cliente": "Cliente Alfa", "local": "Base Salvador",
            "ocorrido_em": "2026-08-18", "horario": "14:30",
            "acao": "emitir", **OCORRENCIA,
        },
    )

    r = Relatorio.objects.get()
    assert r.emitido
    assert r.ocorrido_em == date(2026, 8, 18)
    assert r.dados["conclusao"].startswith("Sem perda")


def test_emissao_incompleta_volta_ao_formulario_sem_perder_o_texto(client, tecnico):
    """O texto é o que custa caro num relatório de campo. Perdê-lo por um campo
    esquecido faria a pessoa parar de usar a tela."""
    client.force_login(tecnico)

    resposta = client.post(
        reverse("workspace:relatorio_novo"),
        {
            "tipo": TipoRelatorio.OCORRENCIA, "titulo": "Queda",
            "o_que_aconteceu": "Texto longo que não pode sumir", "acao": "emitir",
        },
        follow=True,
    )

    corpo = resposta.content.decode()
    assert "Falta preencher" in corpo
    assert "Texto longo que não pode sumir" in corpo
    assert Relatorio.objects.get().situacao == SituacaoRelatorio.RASCUNHO


def test_editar_emitido_redireciona_para_a_folha(client, tecnico):
    r = rel.emitir(escrever(tecnico), tecnico)
    client.force_login(tecnico)

    resposta = client.get(reverse("workspace:relatorio_editar", args=[r.pk]))

    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("workspace:relatorio_ver", args=[r.pk])


def test_ver_relatorio_de_outro_e_recusado(client, tecnico):
    outro = f.pessoa("outro")
    f.lotar(outro)
    r = escrever(tecnico)
    client.force_login(outro)

    assert client.get(reverse("workspace:relatorio_ver", args=[r.pk])).status_code == 403


def test_acao_desconhecida_nao_faz_nada(client, tecnico):
    r = escrever(tecnico)
    client.force_login(tecnico)

    client.post(reverse("workspace:relatorio_acao", args=[r.pk]), {"acao": "explodir"})

    r.refresh_from_db()
    assert r.situacao == SituacaoRelatorio.RASCUNHO


def test_acao_por_get_nao_faz_nada(client, tecnico):
    r = escrever(tecnico)
    client.force_login(tecnico)

    client.get(reverse("workspace:relatorio_acao", args=[r.pk]))

    r.refresh_from_db()
    assert r.situacao == SituacaoRelatorio.RASCUNHO


def test_o_trilho_leva_aos_relatorios(client, tecnico):
    client.force_login(tecnico)

    corpo = client.get(reverse("workspace:servicos")).content.decode()

    assert reverse("workspace:relatorios") in corpo


# ── §33 — o arquivo do documento ────────────────────────────────────


@pytest.fixture
def documento(tecnico):
    from workspace.models.conteudo import Documento, SituacaoDocumento, TipoDocumento

    # VIGENTE e não o padrão: `Documento` nasce rascunho, e rascunho é só do
    # dono — o que é a regra certa, e não o que se testa aqui.
    return Documento.objects.create(
        slug="pop-instalacao", titulo="POP de instalação",
        tipo=TipoDocumento.POP, dono=tecnico, versao="1.0",
        situacao=SituacaoDocumento.VIGENTE,
    )


@pytest.fixture
def publicador():
    pessoa = f.pessoa("editor")
    f.lotar(pessoa)
    f.atribuir(pessoa, f.papel("doc", ["doc.publicar.global"], escopo="global"))
    return pessoa


def _pdf():
    return SimpleUploadedFile("pop.pdf", b"%PDF-1.4\n" + b"0" * 64, content_type="application/pdf")


def test_anexar_arquivo_ao_documento(documento, publicador):
    from workspace.services import conteudo as cnt

    cnt.anexar_arquivo(documento, _pdf(), publicador)

    documento.refresh_from_db()
    assert documento.tem_arquivo
    assert documento.arquivo_nome.endswith("pop.pdf")
    assert documento.arquivo_tamanho > 0


def test_o_nome_original_e_guardado(documento, publicador):
    """O nome no disco é um UUID: sem `arquivo_nome`, quem baixa recebe
    `a3f9c1….pdf` e não reconhece o que pediu."""
    from workspace.services import conteudo as cnt

    cnt.anexar_arquivo(documento, _pdf(), publicador)

    assert "pop.pdf" in documento.arquivo_nome
    assert "pop.pdf" not in documento.arquivo.name


def test_quem_nao_publica_nao_anexa(documento, tecnico):
    from workspace.services import conteudo as cnt

    with pytest.raises(cnt.DocumentoError, match="não pode publicar"):
        cnt.anexar_arquivo(documento, _pdf(), tecnico)


def test_arquivo_invalido_e_recusado(documento, publicador):
    from workspace.services import conteudo as cnt

    ruim = SimpleUploadedFile("x.exe", b"MZ\x90\x00", content_type="application/x-msdownload")

    with pytest.raises(cnt.DocumentoError):
        cnt.anexar_arquivo(documento, ruim, publicador)


def test_o_documento_nao_tem_url_publica(documento, publicador):
    from workspace.services import conteudo as cnt

    cnt.anexar_arquivo(documento, _pdf(), publicador)

    with pytest.raises(ValueError):
        documento.arquivo.url


def test_baixar_pela_tela(client, documento, publicador):
    from workspace.services import conteudo as cnt

    cnt.anexar_arquivo(documento, _pdf(), publicador)
    client.force_login(publicador)

    resposta = client.get(reverse("workspace:baixar_documento", args=[documento.slug]))

    assert resposta.status_code == 200
    assert "pop.pdf" in resposta["Content-Disposition"]


def test_baixar_exige_sessao(client, documento, publicador):
    from workspace.services import conteudo as cnt

    cnt.anexar_arquivo(documento, _pdf(), publicador)

    resposta = client.get(reverse("workspace:baixar_documento", args=[documento.slug]))

    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/entrar/")


def test_baixar_documento_sem_arquivo_da_404(client, documento, publicador):
    client.force_login(publicador)

    assert client.get(
        reverse("workspace:baixar_documento", args=[documento.slug])
    ).status_code == 404


def test_o_tamanho_e_legivel(documento, publicador):
    """"1,4 MB" em vez de 1468006 — a tela mostra o tamanho para a pessoa
    decidir se baixa agora ou espera o wi-fi, e o número cru não responde
    isso."""
    from workspace.services import conteudo as cnt

    cnt.anexar_arquivo(documento, _pdf(), publicador)

    assert documento.tamanho_legivel.endswith(("B", "KB", "MB"))


def test_sem_arquivo_o_tamanho_e_vazio(documento):
    assert documento.tamanho_legivel == ""


def test_o_formulario_de_anexo_so_aparece_para_quem_publica(client, documento, publicador, tecnico):
    client.force_login(publicador)
    corpo = client.get(reverse("workspace:documento", args=[documento.slug])).content.decode()
    assert "Anexar arquivo" in corpo

    client.force_login(tecnico)
    corpo = client.get(reverse("workspace:documento", args=[documento.slug])).content.decode()
    assert "Anexar arquivo" not in corpo


def test_anexar_pela_tela(client, documento, publicador):
    client.force_login(publicador)

    client.post(
        reverse("workspace:anexar_documento", args=[documento.slug]),
        {"arquivo": _pdf()},
    )

    documento.refresh_from_db()
    assert documento.tem_arquivo


def test_anexar_sem_arquivo_avisa(client, documento, publicador):
    client.force_login(publicador)

    resposta = client.post(
        reverse("workspace:anexar_documento", args=[documento.slug]), {}, follow=True
    )

    assert "Escolha um arquivo" in resposta.content.decode()


# ── As bordas que faltavam ──────────────────────────────────────────


def test_a_lista_mostra_os_relatorios(client, tecnico):
    escrever(tecnico, titulo="Entrega Farol")
    client.force_login(tecnico)

    corpo = client.get(reverse("workspace:relatorios")).content.decode()

    assert "Entrega Farol" in corpo


def test_editar_relatorio_de_outro_e_recusado(client, tecnico):
    outro = f.pessoa("outro")
    f.lotar(outro)
    r = escrever(tecnico)
    client.force_login(outro)

    assert client.get(
        reverse("workspace:relatorio_editar", args=[r.pk])
    ).status_code == 403


def test_salvar_rascunho_pela_tela_nao_emite(client, tecnico):
    client.force_login(tecnico)

    client.post(
        reverse("workspace:relatorio_novo"),
        {"tipo": TipoRelatorio.OCORRENCIA, "titulo": "Só o começo",
         "acao": "rascunho", "o_que_aconteceu": "Escrevendo ainda"},
    )

    r = Relatorio.objects.get()
    assert r.situacao == SituacaoRelatorio.RASCUNHO
    assert r.dados["o_que_aconteceu"] == "Escrevendo ainda"


def test_titulo_vazio_pela_tela_nao_perde_o_texto(client, tecnico):
    client.force_login(tecnico)

    resposta = client.post(
        reverse("workspace:relatorio_novo"),
        {"tipo": TipoRelatorio.OCORRENCIA, "titulo": "  ",
         "acao": "rascunho", "o_que_aconteceu": "Texto que não pode sumir"},
    )

    assert "Texto que não pode sumir" in resposta.content.decode()
    assert not Relatorio.objects.exists()


def test_anexar_evidencia_pela_tela(client, tecnico):
    client.force_login(tecnico)

    client.post(
        reverse("workspace:relatorio_novo"),
        {"tipo": TipoRelatorio.OCORRENCIA, "titulo": "Com foto",
         "acao": "rascunho", "evidencias": _foto()},
    )

    assert EvidenciaRelatorio.objects.count() == 1


def test_evidencia_recusada_nao_perde_o_texto(client, tecnico):
    client.force_login(tecnico)
    ruim = SimpleUploadedFile("x.exe", b"MZ\x90\x00", content_type="application/x-msdownload")

    resposta = client.post(
        reverse("workspace:relatorio_novo"),
        {"tipo": TipoRelatorio.OCORRENCIA, "titulo": "Com anexo ruim",
         "acao": "rascunho", "o_que_aconteceu": "Texto longo", "evidencias": ruim},
    )

    assert "Texto longo" in resposta.content.decode()


def test_cancelar_pela_tela(client, tecnico):
    r = escrever(tecnico)
    client.force_login(tecnico)

    client.post(reverse("workspace:relatorio_acao", args=[r.pk]), {"acao": "cancelar"})

    r.refresh_from_db()
    assert r.situacao == SituacaoRelatorio.CANCELADO


def test_emitir_incompleto_pela_acao_mostra_o_motivo(client, tecnico):
    r = escrever(tecnico, dados={"o_que_aconteceu": "Só isso"})
    client.force_login(tecnico)

    resposta = client.post(
        reverse("workspace:relatorio_acao", args=[r.pk]), {"acao": "emitir"}, follow=True
    )

    assert "Falta preencher" in resposta.content.decode()


def test_os_querysets_do_relatorio(tecnico):
    from django.contrib.auth.models import AnonymousUser

    rascunho = escrever(tecnico, titulo="Rascunho")
    emitido = rel.emitir(escrever(tecnico, titulo="Emitido"), tecnico)

    assert list(Relatorio.objects.emitidos()) == [emitido]
    assert list(Relatorio.objects.rascunhos()) == [rascunho]
    assert not Relatorio.objects.de(AnonymousUser()).exists()
    assert not Relatorio.objects.de(None).exists()


def test_os_modelos_se_descrevem_no_admin(tecnico):
    r = escrever(tecnico)
    rel.anexar(r, _foto("lacre.jpg"), legenda="Lacre intacto")

    assert "Queda de energia" in str(r)
    assert "ocorrência" in str(r).lower()
    assert str(EvidenciaRelatorio.objects.get()) == "Lacre intacto"


def test_evidencia_sem_legenda_mostra_o_nome(tecnico):
    r = escrever(tecnico)
    rel.anexar(r, _foto("lacre.jpg"))

    assert "lacre.jpg" in str(EvidenciaRelatorio.objects.get())
