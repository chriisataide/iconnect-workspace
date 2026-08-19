"""O PDF gerado no servidor — §35 e §36.

## A dependência, e por que ela

Este é o único pacote de terceiros que o código do Workspace importa em
execução. Entrou por decisão pedida, e a escolha entre as duas opções foi de
DEPLOY, não de estética:

* `weasyprint` converteria a página HTML que já existe e daria um documento
  idêntico à tela — mas exige Cairo, Pango e GDK-PixBuf instalados no sistema
  operacional. Bibliotecas C que entram na imagem, versionam junto e quebram
  quando a base muda.
* `reportlab` é Python puro: instala por wheel, e a mesma imagem que roda o
  Django roda o PDF. O preço é desenhar o layout em código.

## O que estes testes garantem

1. **A numeração "página X de Y" está certa em documento de várias páginas.** É
   a garantia que a numeração existe para dar: uma folha extraviada denuncia a
   falta. Custou um erro — ver `_CanvasNumerado`.
2. **Acentuação do português sai legível.** Helvetica com WinAnsi cobre; isso é
   testado, não suposto.
3. **Rascunho sai marcado.** Impresso sem marca, ele vira documento definitivo
   na mesa de quem recebeu.
4. **Texto com `<` não quebra a geração** — "switch <porta 3> queimou" é frase
   normal num relatório de campo.
"""

from __future__ import annotations

import re

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.models.relatorio import TipoRelatorio
from workspace.services import pdf as pdf_service
from workspace.services import relatorio as rel

pytestmark = pytest.mark.django_db


OCORRENCIA = {
    "o_que_aconteceu": "Faltou energia às 14h30.",
    "acoes": "Acionamos o gerador.",
    "resultado": "resolvido",
    "conclusao": "Sem perda de serviço.",
}


@pytest.fixture(autouse=True)
def sem_compressao():
    """Sem compressão de página, o texto do PDF é legível em bytes.

    É a forma de afirmar sobre o CONTEÚDO em vez de só sobre o tamanho do
    arquivo — um teste que só confere "gerou alguma coisa" passa com um PDF em
    branco.
    """
    from reportlab import rl_config

    antes = rl_config.pageCompression
    rl_config.pageCompression = 0
    yield
    rl_config.pageCompression = antes


@pytest.fixture
def tecnico():
    pessoa = f.pessoa("tecnico", nome="Técnico de Campo")
    f.lotar(pessoa)
    return pessoa


def escrever(pessoa, dados=None, **extras):
    return rel.salvar(
        pessoa,
        tipo=extras.pop("tipo", TipoRelatorio.OCORRENCIA),
        titulo=extras.pop("titulo", "Queda de energia"),
        dados=dados if dados is not None else dict(OCORRENCIA),
        **extras,
    )


def texto_de(relatorio) -> str:
    return pdf_service.gerar(relatorio).decode("latin-1")


def trechos(pdf_texto: str) -> list[str]:
    return re.findall(r"\((?:[^()\\]|\\.)*\)", pdf_texto)


# ── O arquivo ───────────────────────────────────────────────────────


def test_gera_um_pdf_de_verdade(tecnico):
    conteudo = pdf_service.gerar(escrever(tecnico))

    assert conteudo.startswith(b"%PDF-")
    assert conteudo.rstrip().endswith(b"%%EOF")


def test_o_titulo_esta_no_documento(tecnico):
    assert "Queda de energia" in texto_de(escrever(tecnico))


def test_as_respostas_estao_no_documento(tecnico):
    conteudo = texto_de(escrever(tecnico))

    assert "gerador" in conteudo
    assert "Sem perda de servi" in conteudo


def test_a_ficha_traz_cliente_local_e_responsavel(tecnico):
    conteudo = texto_de(
        escrever(tecnico, cliente="Cliente Alfa", local="Base Salvador")
    )

    assert "Cliente Alfa" in conteudo
    assert "Base Salvador" in conteudo
    assert "cnico de Campo" in conteudo


# ── Acentuação ──────────────────────────────────────────────────────


def test_a_acentuacao_do_portugues_sai_legivel(tecnico):
    """Helvetica com WinAnsi cobre o português. Testado, não suposto — fonte
    errada transforma "ação" em "aÃ§Ã£o" e só se descobre imprimindo."""
    relatorio = escrever(
        tecnico,
        titulo="Inspeção não conformidade",
        dados={**OCORRENCIA, "conclusao": "Ação corretiva à vista, ônus do cliente."},
    )

    conteudo = texto_de(relatorio)

    # `\341` é á, `\347` é ç, `\343` é ã em WinAnsi — o encoding que o leitor
    # de PDF sabe ler. Se saísse UTF-8 cru, apareceriam dois bytes por acento.
    assert "Inspe\\347\\343o" in conteudo
    assert "\\302nus" in conteudo or "nus do cliente" in conteudo


# ── Numeração ───────────────────────────────────────────────────────


def test_a_numeracao_de_uma_pagina(tecnico):
    assert "P\\341gina 1 de 1" in texto_de(escrever(tecnico))


def test_a_numeracao_de_documento_longo(tecnico):
    """A garantia que a numeração existe para dar: uma folha extraviada denuncia
    a falta. Custou um erro — `multiBuild` só repassa quando há *indexing
    flowables*, e sem eles o rodapé saía "Página 1" sem total."""
    relatorio = escrever(
        tecnico, dados={**OCORRENCIA, "o_que_aconteceu": "linha\n" * 220}
    )

    conteudo = texto_de(relatorio)
    numeros = sorted(set(re.findall(r"P\\341gina (\d+) de (\d+)", conteudo)))

    assert len(numeros) > 1, "documento longo tem de ter mais de uma página"
    total = numeros[0][1]
    assert all(t == total for _, t in numeros), "o total muda de página para página"
    assert {n for n, _ in numeros} == {str(i) for i in range(1, int(total) + 1)}


# ── Rascunho e emitido ──────────────────────────────────────────────


def test_rascunho_sai_marcado(tecnico):
    """Impresso sem marca, um rascunho vira documento definitivo na mesa de quem
    recebeu."""
    assert "RASCUNHO" in texto_de(escrever(tecnico))


def test_emitido_nao_tem_marca(tecnico):
    relatorio = rel.emitir(escrever(tecnico), tecnico)

    assert "RASCUNHO" not in texto_de(relatorio)


def test_a_assinatura_so_aparece_no_emitido(tecnico):
    """Assinar rascunho é assinar documento que ainda vai mudar. No PDF a linha
    de assinatura é desenhada, então o que se confere é o nome sob ela."""
    relatorio = escrever(tecnico)
    rascunho = texto_de(relatorio)

    rel.emitir(relatorio, tecnico)
    emitido = texto_de(relatorio)

    assert emitido.count("cnico de Campo") > rascunho.count("cnico de Campo")


# ── Robustez ────────────────────────────────────────────────────────


def test_texto_com_sinal_de_menor_nao_quebra(tecnico):
    """`Paragraph` interpreta um subconjunto de HTML. Sem escapar, "switch
    <porta 3> queimou" perde o trecho — e um `<` sem par levanta no meio da
    geração, transformando texto legítimo em erro 500."""
    relatorio = escrever(
        tecnico,
        dados={**OCORRENCIA, "o_que_aconteceu": "O switch <porta 3> queimou & parou"},
    )

    conteudo = texto_de(relatorio)

    assert conteudo.startswith("%PDF-")
    assert "porta 3" in conteudo


def test_quebra_de_linha_vira_quebra_no_pdf(tecnico):
    relatorio = escrever(
        tecnico, dados={**OCORRENCIA, "acoes": "Primeiro isto\nDepois aquilo"}
    )

    conteudo = texto_de(relatorio)

    assert "Primeiro isto" in conteudo
    assert "Depois aquilo" in conteudo


def test_campo_em_branco_nao_vira_secao_vazia(tecnico):
    """A causa fica em branco quando ainda não se sabe — e um rótulo "CAUSA"
    seguido de nada é pior que a ausência dele."""
    conteudo = texto_de(escrever(tecnico))

    assert "CAUSA" not in conteudo


def test_as_evidencias_entram_na_lista(tecnico):
    from django.core.files.uploadedfile import SimpleUploadedFile

    relatorio = escrever(tecnico)
    rel.anexar(
        relatorio,
        SimpleUploadedFile("lacre.jpg", b"\xff\xd8\xff\xe0" + b"0" * 64, content_type="image/jpeg"),
        legenda="Lacre intacto",
    )

    conteudo = texto_de(relatorio)

    assert "lacre.jpg" in conteudo
    assert "Lacre intacto" in conteudo


def test_relatorio_de_entrega_tambem_gera(tecnico):
    relatorio = escrever(
        tecnico, tipo=TipoRelatorio.ENTREGA, titulo="Entrega Farol",
        dados={
            "responsavel_cliente": "João da Silva",
            "itens": "4 câmeras IP\n1 switch 24p",
            "conferido": "completo",
        },
    )

    conteudo = texto_de(relatorio)

    assert "Entrega Farol" in conteudo
    assert "Jo\\343o da Silva" in conteudo
    assert "Conferido no local" in conteudo.upper() or "CONFERIDO" in conteudo.upper()


# ── O nome do arquivo ───────────────────────────────────────────────


def test_o_nome_do_arquivo_e_legivel(tecnico):
    """O arquivo vai para a pasta de downloads de alguém e para o e-mail de um
    cliente. `12.pdf` é o que ninguém acha depois."""
    from datetime import date

    relatorio = escrever(tecnico, titulo="Queda de energia na Base")
    relatorio.ocorrido_em = date(2026, 8, 18)

    nome = pdf_service.nome_do_arquivo(relatorio)

    assert nome == "ocorrencia-2026-08-18-queda-de-energia-na-base.pdf"


def test_titulo_estranho_nao_quebra_o_nome(tecnico):
    relatorio = escrever(tecnico, titulo="../../etc/passwd")

    nome = pdf_service.nome_do_arquivo(relatorio)

    assert "/" not in nome
    assert nome.endswith(".pdf")


# ── A rota ──────────────────────────────────────────────────────────


def test_baixar_o_pdf_pela_tela(client, tecnico):
    relatorio = rel.emitir(escrever(tecnico), tecnico)
    client.force_login(tecnico)

    resposta = client.get(reverse("workspace:relatorio_pdf", args=[relatorio.pk]))

    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "application/pdf"
    assert resposta.content.startswith(b"%PDF-")


def test_o_pdf_abre_na_aba_em_vez_de_baixar(client, tecnico):
    """Quem clica em "PDF" quer CONFERIR antes de mandar para o cliente. Forçar
    download obriga a abrir o gerenciador de arquivos para ver o que já poderia
    estar na tela — e o nome vai junto, então "salvar como" sai certo."""
    relatorio = rel.emitir(escrever(tecnico), tecnico)
    client.force_login(tecnico)

    resposta = client.get(reverse("workspace:relatorio_pdf", args=[relatorio.pk]))

    assert resposta["Content-Disposition"].startswith("inline;")
    assert ".pdf" in resposta["Content-Disposition"]


def test_o_pdf_de_outro_e_recusado(client, tecnico):
    outro = f.pessoa("outro")
    f.lotar(outro)
    relatorio = escrever(tecnico)
    client.force_login(outro)

    assert client.get(
        reverse("workspace:relatorio_pdf", args=[relatorio.pk])
    ).status_code == 403


def test_o_pdf_exige_sessao(client, tecnico):
    relatorio = escrever(tecnico)

    resposta = client.get(reverse("workspace:relatorio_pdf", args=[relatorio.pk]))

    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/entrar/")


def test_o_pdf_nao_e_guardado_em_disco(tecnico):
    """Gerado a cada pedido: o documento é derivado do banco e reflete o estado
    atual. Um PDF salvo na emissão seria uma segunda verdade que envelhece — e é
    a que alguém encontraria depois."""
    relatorio = escrever(tecnico)
    primeiro = texto_de(relatorio)

    rel.salvar(
        tecnico, relatorio, tipo=relatorio.tipo, titulo="Título corrigido",
        dados=relatorio.dados,
    )
    segundo = texto_de(relatorio)

    assert "Queda de energia" in primeiro
    assert "tulo corrigido" in segundo
