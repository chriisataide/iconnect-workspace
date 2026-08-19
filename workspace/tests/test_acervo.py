"""§37 — o acervo podia ser lido e não podia ser mantido.

## A auditoria

Documentos já tinham mais do que eu esperava: versão, vigência, público-alvo com
o vocabulário do recorte da busca, confirmação de leitura POR VERSÃO, cobertura
para auditoria, upload em armazenamento privado, bloco no Meu dia e badge de
vencimento na vitrine. Isso tudo ficou como estava.

Faltavam duas coisas, e as duas são silenciosas:

1. **Criar um documento exigia o `/admin/` do Django**, que pede `is_staff` — e
   quem escreve procedimento é a área que o executa, não quem administra o
   banco. Na prática, publicar norma significava pedir para outra pessoa. É o
   mesmo defeito que a redação de comunicados corrigiu, no módulo ao lado.

2. **Ninguém era cobrado, e ninguém era avisado.** A leitura obrigatória só
   acontecia para quem abria o Meu dia por conta própria — e é a confirmação,
   não a publicação, que se leva para auditoria. E `publicados()` tira o vencido
   da vitrine, então um POP que passa da vigência simplesmente SOME do acervo:
   as pessoas continuam precisando do procedimento, ele deixou de existir na
   tela, e ninguém foi informado.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.models.conteudo import (
    ConfirmacaoLeitura,
    Documento,
    SituacaoDocumento,
    TipoDocumento,
)
from workspace.models.notificacao import Notificacao, TipoNotificacao
from workspace.services import conteudo as cnt
from workspace.services.conteudo import DocumentoError

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


@pytest.fixture
def cenario():
    unidade, financeiro = f.unidade(), f.departamento("FIN", "Financeiro")
    dono, ana = f.pessoa("dono"), f.pessoa("ana")
    f.lotar(dono, uni=unidade, dep=financeiro)
    f.lotar(ana, uni=unidade, dep=financeiro)
    f.atribuir(dono, f.papel("qsms", ["doc.publicar.global"], escopo="global"))
    return {"unidade": unidade, "dep": financeiro, "dono": dono, "ana": ana}


def salvar(cenario, **extras):
    dados = {
        "slug": "",
        "titulo": "POP de compras",
        "tipo": TipoDocumento.POP,
        "publicar": True,
    }
    dados.update(extras)
    return cnt.salvar(cenario["dono"], None, **dados)


# ── Escrever ────────────────────────────────────────────────────────


def test_quem_nao_publica_nao_escreve(cenario):
    with pytest.raises(DocumentoError, match="não pode publicar"):
        cnt.salvar(
            cenario["ana"], None, slug="", titulo="x", tipo=TipoDocumento.POP
        )


def test_documento_sem_titulo_recusa(cenario):
    with pytest.raises(DocumentoError, match="título"):
        salvar(cenario, titulo="   ")


def test_tipo_invalido_recusa(cenario):
    with pytest.raises(DocumentoError, match="Tipo"):
        salvar(cenario, tipo="bilhete")


def test_vigencia_invertida_recusa(cenario):
    """Vigência invertida produz documento que nasce vencido: some da vitrine no
    mesmo instante em que é publicado, e ninguém entende por quê."""
    hoje = timezone.localdate()

    with pytest.raises(DocumentoError, match="termina antes"):
        salvar(
            cenario,
            vigencia_inicio=hoje,
            vigencia_fim=hoje - timedelta(days=1),
        )


def test_publicar_deixa_vigente_e_rascunho_nao(cenario):
    vigente = salvar(cenario, publicar=True)
    rascunho = salvar(cenario, titulo="Política de viagem", publicar=False)

    assert vigente.situacao == SituacaoDocumento.VIGENTE
    assert rascunho.situacao == SituacaoDocumento.RASCUNHO


def test_o_slug_nasce_do_titulo(cenario):
    assert salvar(cenario).slug == "pop-de-compras"


def test_titulo_repetido_ganha_endereco_proprio(cenario):
    """Recusar porque já existe outro com título parecido faria quem escreve
    inventar um título pior para caber na regra."""
    primeiro = salvar(cenario)
    segundo = salvar(cenario)

    assert primeiro.slug != segundo.slug
    assert segundo.slug.startswith("pop-de-compras")


def test_editar_nao_troca_o_endereco(cenario):
    """O slug vai na URL, e trocá-lo quebraria todo link já colado num chat."""
    doc = salvar(cenario)

    cnt.salvar(
        cenario["dono"], doc, slug="", titulo="POP de compras — revisado",
        tipo=TipoDocumento.POP, publicar=True,
    )
    doc.refresh_from_db()

    assert doc.slug == "pop-de-compras"
    assert doc.titulo == "POP de compras — revisado"


def test_publico_alvo_vazio_alcanca_a_empresa_inteira(cenario):
    """VAZIO significa "todo mundo", e não "ninguém": o contrário faria o POP que
    a empresa inteira precisa ler ser o primeiro a desaparecer."""
    assert salvar(cenario).publico_alvo == ["*"]


def test_publico_alvo_usa_o_vocabulario_da_busca(cenario):
    """Um segundo vocabulário para dizer "quem vê" divergiria do primeiro na
    terceira semana — e aí o documento aparece na busca de quem não pode
    abri-lo."""
    doc = salvar(
        cenario,
        unidades=[str(cenario["unidade"].pk)],
        departamentos=[str(cenario["dep"].pk)],
    )

    assert set(doc.publico_alvo) == {
        f"unidade:{cenario['unidade'].pk}",
        f"depto:{cenario['dep'].pk}",
    }


def test_o_alvo_volta_para_a_tela_marcado(cenario):
    doc = salvar(cenario, unidades=[str(cenario["unidade"].pk)])

    unidades, departamentos = cnt.alvo_para_tela(doc)

    assert unidades == {cenario["unidade"].pk}
    assert departamentos == set()


def test_alvo_para_tela_de_documento_novo_e_vazio():
    assert cnt.alvo_para_tela(None) == (set(), set())


def test_alvo_ignora_sujeito_que_nao_e_numero(cenario):
    """`*` e `papel:qsms` são sujeitos legítimos e não são caixinha de tela."""
    doc = salvar(cenario)
    doc.publico_alvo = ["*", "papel:qsms", "unidade:abc"]

    assert cnt.alvo_para_tela(doc) == (set(), set())


def test_a_versao_e_do_autor_e_nao_um_contador(cenario):
    """Um número que sobe sozinho a cada salvamento invalidaria toda confirmação
    de leitura por causa de uma vírgula corrigida — e é a confirmação que vai
    para a auditoria."""
    doc = salvar(cenario, versao="2.1")
    cnt.salvar(
        cenario["dono"], doc, slug="", titulo="POP de compras",
        tipo=TipoDocumento.POP, publicar=True,
    )
    doc.refresh_from_db()

    assert doc.versao == "2.1"


def test_o_arquivo_e_validado_ao_salvar(cenario):
    with pytest.raises(DocumentoError):
        salvar(
            cenario,
            arquivo=SimpleUploadedFile("pop.pdf", b"nao sou pdf", content_type="application/pdf"),
        )


def test_o_arquivo_entra_quando_valido(cenario):
    doc = salvar(
        cenario,
        arquivo=SimpleUploadedFile("pop.pdf", PDF, content_type="application/pdf"),
    )

    assert doc.tem_arquivo
    assert doc.arquivo_nome == "pop.pdf"


# ── Revogar ─────────────────────────────────────────────────────────


def test_revogar_tira_da_vitrine_sem_apagar(cenario):
    """Quem investiga uma ocorrência precisa poder abrir o POP que valia na
    época."""
    doc = salvar(cenario)

    cnt.revogar(doc, cenario["dono"])

    assert Documento.objects.filter(pk=doc.pk).exists()
    assert doc not in cnt.visiveis_para(cenario["ana"])
    assert cnt.pode_ver(doc, cenario["ana"])


def test_quem_nao_publica_nao_revoga(cenario):
    doc = salvar(cenario)

    with pytest.raises(DocumentoError, match="não pode revogar"):
        cnt.revogar(doc, cenario["ana"])


# ── A redação ───────────────────────────────────────────────────────


def test_a_redacao_mostra_o_que_a_vitrine_esconde(cenario):
    """Quem escreve precisa ver justamente o rascunho, o vencido e o revogado —
    é isso que dá trabalho a ele."""
    salvar(cenario, titulo="Vigente", publicar=True)
    salvar(cenario, titulo="Rascunho", publicar=False)

    assert cnt.redacao(cenario["dono"]).count() == 2
    assert cnt.visiveis_para(cenario["ana"]).count() == 1


def test_a_redacao_e_vazia_para_quem_nao_publica(cenario):
    salvar(cenario)

    assert not cnt.redacao(cenario["ana"]).exists()


# ── Cobrar a leitura ────────────────────────────────────────────────


def test_avisa_quem_deve_leitura_obrigatoria(cenario):
    """É a diferença entre "a empresa publicou" e "a empresa informou"."""
    salvar(cenario, leitura_obrigatoria=True)

    enviados = cnt.avisar_leituras_obrigatorias()

    assert enviados == 2  # o dono também lê a norma que ele escreveu
    aviso = Notificacao.objects.de(cenario["ana"]).get()
    assert aviso.tipo == TipoNotificacao.LEITURA_OBRIGATORIA
    assert "POP de compras" in aviso.titulo


def test_documento_sem_leitura_obrigatoria_nao_cobra_ninguem(cenario):
    salvar(cenario, leitura_obrigatoria=False)

    assert cnt.avisar_leituras_obrigatorias() == 0
    assert not Notificacao.objects.exists()


def test_quem_ja_confirmou_nao_e_cobrado(cenario):
    doc = salvar(cenario, leitura_obrigatoria=True)
    cnt.confirmar(doc, cenario["ana"])

    cnt.avisar_leituras_obrigatorias()

    assert not Notificacao.objects.de(cenario["ana"]).exists()


def test_a_nova_versao_cobra_de_novo_quem_ja_tinha_lido(cenario):
    """É exatamente o comportamento que a confirmação por versão existe para
    garantir."""
    doc = salvar(cenario, leitura_obrigatoria=True)
    cnt.confirmar(doc, cenario["ana"])
    cnt.avisar_leituras_obrigatorias()

    cnt.salvar(
        cenario["dono"], doc, slug="", titulo=doc.titulo, tipo=doc.tipo,
        versao="2", leitura_obrigatoria=True, publicar=True,
    )

    assert cnt.avisar_leituras_obrigatorias() >= 1
    assert Notificacao.objects.de(cenario["ana"]).count() == 1


def test_rodar_duas_vezes_nao_duplica_a_cobranca(cenario):
    salvar(cenario, leitura_obrigatoria=True)

    cnt.avisar_leituras_obrigatorias()
    cnt.avisar_leituras_obrigatorias()

    assert Notificacao.objects.de(cenario["ana"]).count() == 1


def test_a_cobranca_respeita_o_publico_alvo(cenario):
    """Cobrar de quem o documento nem alcança treina a pessoa a ignorar o sino."""
    outra = f.unidade(codigo="RJ", nome="Base RJ")
    bruno = f.pessoa("bruno")
    f.lotar(bruno, uni=outra)
    salvar(
        cenario, leitura_obrigatoria=True, unidades=[str(cenario["unidade"].pk)]
    )

    cnt.avisar_leituras_obrigatorias()

    assert Notificacao.objects.de(cenario["ana"]).exists()
    assert not Notificacao.objects.de(bruno).exists()


def test_rascunho_obrigatorio_nao_cobra_ninguem(cenario):
    """Rascunho é meio-documento; cobrar leitura dele faria alguém seguir uma
    norma que ainda não vale."""
    salvar(cenario, leitura_obrigatoria=True, publicar=False)

    assert cnt.avisar_leituras_obrigatorias() == 0


# ── Avisar a vigência ───────────────────────────────────────────────


def test_avisa_o_dono_do_documento_vencido(cenario):
    """`publicados()` tira o vencido da vitrine: o POP some do acervo e ninguém
    é avisado."""
    hoje = timezone.localdate()
    doc = salvar(cenario)
    Documento.objects.filter(pk=doc.pk).update(
        vigencia_inicio=hoje - timedelta(days=400), vigencia_fim=hoje - timedelta(days=2)
    )

    assert cnt.avisar_vencimentos() == 1

    aviso = Notificacao.objects.de(cenario["dono"]).get()
    assert aviso.tipo == TipoNotificacao.DOCUMENTO_A_VENCER
    assert "venceu" in aviso.titulo


def test_avisa_antes_de_vencer_com_os_dias_que_faltam(cenario):
    doc = salvar(cenario)
    Documento.objects.filter(pk=doc.pk).update(
        vigencia_fim=timezone.localdate() + timedelta(days=10)
    )

    cnt.avisar_vencimentos()

    assert "10 dias" in Notificacao.objects.de(cenario["dono"]).get().titulo


def test_documento_sem_vigencia_fim_nao_avisa(cenario):
    salvar(cenario)

    assert cnt.avisar_vencimentos() == 0


def test_o_aviso_de_vigencia_nao_duplica(cenario):
    doc = salvar(cenario)
    Documento.objects.filter(pk=doc.pk).update(
        vigencia_fim=timezone.localdate() + timedelta(days=5)
    )

    cnt.avisar_vencimentos()
    cnt.avisar_vencimentos()

    assert Notificacao.objects.de(cenario["dono"]).count() == 1


# ── O comando ───────────────────────────────────────────────────────


def test_avisar_documentos_sem_aplicar_nao_grava(cenario):
    from io import StringIO

    from django.core.management import call_command

    salvar(cenario, leitura_obrigatoria=True)
    call_command("avisar_documentos", stdout=StringIO())

    assert not Notificacao.objects.exists()


def test_avisar_documentos_aplica(cenario):
    from io import StringIO

    from django.core.management import call_command

    doc = salvar(cenario, leitura_obrigatoria=True)
    Documento.objects.filter(pk=doc.pk).update(
        vigencia_fim=timezone.localdate() - timedelta(days=1)
    )

    saida = StringIO()
    call_command("avisar_documentos", "--aplicar", stdout=saida)

    assert "VENCIDO" in saida.getvalue()
    assert Notificacao.objects.filter(
        tipo=TipoNotificacao.DOCUMENTO_A_VENCER
    ).exists()


def test_avisar_documentos_aceita_outra_antecedencia(cenario):
    from io import StringIO

    from django.core.management import call_command

    doc = salvar(cenario)
    Documento.objects.filter(pk=doc.pk).update(
        vigencia_fim=timezone.localdate() + timedelta(days=50)
    )

    call_command("avisar_documentos", "--dias", "90", "--aplicar", stdout=StringIO())

    assert Notificacao.objects.count() == 1


# ── As telas ────────────────────────────────────────────────────────


def test_quem_nao_publica_leva_403_no_acervo(cenario, client):
    client.force_login(cenario["ana"])

    assert client.get(reverse("workspace:documentos")).status_code == 403
    assert client.get(reverse("workspace:documento_novo")).status_code == 403


def test_criar_pela_tela(cenario, client):
    client.force_login(cenario["dono"])

    client.post(
        reverse("workspace:documento_novo"),
        {
            "titulo": "Política de viagem",
            "tipo": TipoDocumento.POLITICA,
            "resumo": "Como viajar a trabalho.",
            "versao": "1",
            "acao": "publicar",
        },
    )

    doc = Documento.objects.get(slug="politica-de-viagem")
    assert doc.situacao == SituacaoDocumento.VIGENTE


def test_salvar_rascunho_pela_tela(cenario, client):
    client.force_login(cenario["dono"])

    client.post(
        reverse("workspace:documento_novo"),
        {"titulo": "Rascunho", "tipo": TipoDocumento.NORMA, "acao": "rascunho"},
    )

    assert Documento.objects.get().situacao == SituacaoDocumento.RASCUNHO


def test_erro_no_formulario_nao_perde_a_tela(cenario, client):
    client.force_login(cenario["dono"])

    resposta = client.post(
        reverse("workspace:documento_novo"),
        {"titulo": "", "tipo": TipoDocumento.POP, "acao": "publicar"},
    )

    assert resposta.status_code == 200
    assert not Documento.objects.exists()


def test_editar_pela_tela_reabre_com_o_alvo_marcado(cenario, client):
    doc = salvar(cenario, unidades=[str(cenario["unidade"].pk)])
    client.force_login(cenario["dono"])

    resposta = client.get(reverse("workspace:documento_editar", args=[doc.slug]))

    assert resposta.context["alvo_unidades"] == {cenario["unidade"].pk}


def test_revogar_pela_tela(cenario, client):
    doc = salvar(cenario)
    client.force_login(cenario["dono"])

    client.post(reverse("workspace:documento_revogar", args=[doc.slug]))
    doc.refresh_from_db()

    assert doc.situacao == SituacaoDocumento.REVOGADO


def test_get_no_revogar_volta_para_o_acervo(cenario, client):
    doc = salvar(cenario)
    client.force_login(cenario["dono"])

    resposta = client.get(reverse("workspace:documento_revogar", args=[doc.slug]))

    assert resposta["Location"] == reverse("workspace:documentos")


def test_quem_nao_publica_nao_revoga_pela_tela(cenario, client):
    doc = salvar(cenario)
    client.force_login(cenario["ana"])

    client.post(reverse("workspace:documento_revogar", args=[doc.slug]))
    doc.refresh_from_db()

    assert doc.situacao == SituacaoDocumento.VIGENTE


def test_o_acervo_mostra_o_que_venceu(cenario, client):
    doc = salvar(cenario)
    Documento.objects.filter(pk=doc.pk).update(
        vigencia_fim=timezone.localdate() - timedelta(days=1)
    )
    client.force_login(cenario["dono"])

    resposta = client.get(reverse("workspace:documentos"))

    assert len(resposta.context["vencidos"]) == 1
    assert "sumiu da vitrine" in resposta.content.decode()


def test_a_rota_do_acervo_nao_e_sequestrada_por_um_slug(cenario, client):
    """Um documento chamado "acervo" derrubaria a tela de manutenção, e o erro
    só apareceria no dia em que alguém escolhesse esse título."""
    Documento.objects.create(
        slug="acervo", titulo="Acervo", tipo=TipoDocumento.POP,
        situacao=SituacaoDocumento.VIGENTE, dono=cenario["dono"],
    )
    client.force_login(cenario["dono"])

    resposta = client.get(reverse("workspace:documentos"))

    assert "documentos" in resposta.context


def test_o_trilho_conta_a_leitura_que_a_pessoa_deve(cenario, client):
    salvar(cenario, leitura_obrigatoria=True)
    client.force_login(cenario["ana"])

    resposta = client.get(reverse("workspace:meu_dia"))

    assert resposta.context["leituras_pendentes"] == 1
    assert resposta.context["ve_documentos"] is False


def test_o_trilho_so_oferece_o_acervo_a_quem_mantem(cenario, client):
    client.force_login(cenario["ana"])
    assert reverse("workspace:documentos") not in client.get(
        reverse("workspace:meu_dia")
    ).content.decode()

    client.force_login(cenario["dono"])
    assert reverse("workspace:documentos") in client.get(
        reverse("workspace:meu_dia")
    ).content.decode()


def test_a_leitura_obrigatoria_vira_card_urgente_na_home(cenario, client):
    salvar(cenario, leitura_obrigatoria=True)
    client.force_login(cenario["ana"])

    cards = client.get(reverse("workspace:home")).context["cards"]
    leitura = next(c for c in cards if c.chave == "leituras")

    assert leitura.urgente
    assert leitura.contagem == 1


def test_confirmar_a_leitura_tira_o_card(cenario, client):
    doc = salvar(cenario, leitura_obrigatoria=True)
    cnt.confirmar(doc, cenario["ana"])
    client.force_login(cenario["ana"])

    cards = client.get(reverse("workspace:home")).context["cards"]

    assert "leituras" not in [c.chave for c in cards]
    assert ConfirmacaoLeitura.objects.count() == 1
