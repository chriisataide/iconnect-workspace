"""O acervo normativo — vigência, público-alvo e trilha de leitura.

Três coisas que, erradas, tornam o acervo pior que não ter acervo:

1. **POP vencido apresentado como vigente.** A pessoa segue o procedimento errado
   achando que seguiu o certo.
2. **Documento de departamento visível a quem não é do departamento.** Vaza dado
   que tem público-alvo justamente porque não é para todos.
3. **Confirmação de leitura que sobrevive à mudança do texto.** "Todo mundo
   confirmou" passa a ser uma frase sobre um texto que já não existe — e é essa
   frase que se leva para auditoria.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.models import Papel
from identidade.tests import fabricas as f
from workspace.models.conteudo import (
    ConfirmacaoLeitura,
    Documento,
    SituacaoDocumento,
    TipoDocumento,
)
from workspace.services import conteudo as cnt

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()


def doc(**kwargs):
    padrao = {
        "slug": kwargs.get("slug", "pop-teste"),
        "tipo": TipoDocumento.POP,
        "titulo": "POP de teste",
        "corpo": "Passo 1. Passo 2.",
        "versao": "1.0",
        "publico_alvo": ["*"],
        "situacao": SituacaoDocumento.VIGENTE,
        "vigencia_inicio": HOJE - timedelta(days=1),
    }
    return Documento.objects.create(**{**padrao, **kwargs})


@pytest.fixture
def pessoas():
    dono, ana, bruno = (f.pessoa(n) for n in ("dono", "ana", "bruno"))
    unidade = f.unidade("MTZ", "Matriz")
    ti = f.departamento("TI", "Tecnologia")
    ops = f.departamento("OPS", "Operações")
    f.lotar(dono, uni=unidade, dep=ti)
    f.lotar(ana, uni=unidade, dep=ti)
    f.lotar(bruno, uni=unidade, dep=ops)
    return {"dono": dono, "ana": ana, "bruno": bruno, "ti": ti, "ops": ops}


# ── 1 · Vigência ────────────────────────────────────────────────────


def test_vencido_e_derivado_nunca_armazenado(pessoas):
    """Estado gravado que depende do relógio mente no dia seguinte."""
    d = doc(dono=pessoas["dono"], vigencia_fim=HOJE - timedelta(days=1))

    assert d.situacao == SituacaoDocumento.VIGENTE, "a situação gravada não mudou"
    assert d.vencido, "e ainda assim está vencido"
    assert not d.vigente


def test_vencido_sai_da_vitrine(pessoas):
    doc(dono=pessoas["dono"], slug="atual")
    doc(dono=pessoas["dono"], slug="velho", vigencia_fim=HOJE - timedelta(days=1))

    visiveis = {d.slug for d in cnt.visiveis_para(pessoas["ana"])}
    assert visiveis == {"atual"}


def test_vencido_ainda_abre_por_link(client, pessoas):
    """Quem precisa saber o que dizia o POP anterior a uma ocorrência precisa
    poder abrir. O que muda é que a tela avisa."""
    d = doc(dono=pessoas["dono"], vigencia_fim=HOJE - timedelta(days=2))

    resposta = client.get(reverse("workspace:documento", args=(d.slug,)))

    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert "Vigência encerrada" in corpo
    assert "não é o procedimento em vigor" in corpo


def test_aviso_de_vencido_vem_antes_do_texto(client, pessoas):
    """POP vencido lido até o fim e só então desmentido no rodapé é o pior
    desenho possível: a pessoa já seguiu."""
    d = doc(dono=pessoas["dono"], corpo="MARCADOR-DO-CORPO", vigencia_fim=HOJE - timedelta(days=1))

    corpo = client.get(reverse("workspace:documento", args=(d.slug,))).content.decode()

    assert corpo.index("Vigência encerrada") < corpo.index("MARCADOR-DO-CORPO")


def test_sem_prazo_nunca_vence(pessoas):
    d = doc(dono=pessoas["dono"], vigencia_fim=None)

    assert not d.vencido
    assert d.vigente
    assert d.dias_para_vencer is None


def test_vigencia_futura_ainda_nao_vale(pessoas):
    d = doc(dono=pessoas["dono"], vigencia_inicio=HOJE + timedelta(days=5))

    assert not d.vigente
    assert not cnt.visiveis_para(pessoas["ana"]).exists()


def test_rascunho_e_so_do_dono(pessoas):
    d = doc(dono=pessoas["dono"], situacao=SituacaoDocumento.RASCUNHO)

    assert cnt.pode_ver(d, pessoas["dono"])
    assert not cnt.pode_ver(d, pessoas["ana"]), (
        "rascunho visível é meio-documento tratado como norma, e alguém vai seguir"
    )


def test_revogado_aponta_o_substituto(client, pessoas):
    velho = doc(dono=pessoas["dono"], slug="velho", situacao=SituacaoDocumento.REVOGADO)
    doc(dono=pessoas["dono"], slug="novo", titulo="POP novo", revoga=velho)

    corpo = client.get(reverse("workspace:documento", args=("velho",))).content.decode()

    assert "foi revogado" in corpo
    assert "POP novo" in corpo


def test_revogado_sem_substituto_nao_deixa_beco(client, pessoas):
    doc(dono=pessoas["dono"], slug="orfao", situacao=SituacaoDocumento.REVOGADO)

    corpo = client.get(reverse("workspace:documento", args=("orfao",))).content.decode()

    assert "procure o responsável" in corpo


# ── 2 · Público-alvo ────────────────────────────────────────────────


def test_publico_alvo_de_departamento(pessoas):
    doc(dono=pessoas["dono"], slug="so-ti", publico_alvo=[f"depto:{pessoas['ti'].pk}"])

    assert cnt.visiveis_para(pessoas["ana"]).count() == 1, "ana é de TI"
    assert cnt.visiveis_para(pessoas["bruno"]).count() == 0, "bruno é de Operações"


def test_publico_alvo_por_papel(pessoas):
    papel = f.papel("sesmt", ["rh.ler.global"], escopo="global")
    f.atribuir(pessoas["bruno"], papel)
    doc(dono=pessoas["dono"], slug="so-sesmt", publico_alvo=["papel:sesmt"])

    assert cnt.visiveis_para(pessoas["bruno"]).count() == 1
    assert cnt.visiveis_para(pessoas["ana"]).count() == 0


def test_anonimo_ve_so_o_que_e_de_todos(client, pessoas):
    """Política geral não é segredo; documento de área exige saber quem é."""
    doc(dono=pessoas["dono"], slug="geral", titulo="Política geral")
    doc(dono=pessoas["dono"], slug="so-ti", titulo="Norma de TI",
        publico_alvo=[f"depto:{pessoas['ti'].pk}"])

    corpo = client.get(reverse("workspace:documentacao")).content.decode()

    assert "Política geral" in corpo
    assert "Norma de TI" not in corpo


def test_anonimo_recebe_403_em_documento_restrito(client, pessoas):
    doc(dono=pessoas["dono"], slug="restrito", publico_alvo=[f"depto:{pessoas['ti'].pk}"])

    resposta = client.get(reverse("workspace:documento", args=("restrito",)))
    assert resposta.status_code == 403


def test_lista_vazia_de_publico_vale_como_todos(pessoas):
    """Campo JSON esquecido no admin não pode esconder o documento em silêncio."""
    doc(dono=pessoas["dono"], publico_alvo=[])

    assert cnt.visiveis_para(pessoas["bruno"]).count() == 1


def test_o_vocabulario_e_o_mesmo_da_busca(pessoas):
    """Um segundo vocabulário divergiria, e o documento apareceria na busca de
    quem não pode abrir."""
    from identidade.services.autorizacao import subjects_de

    subjects = subjects_de(pessoas["ana"])
    assert "*" in subjects
    assert f"depto:{pessoas['ti'].pk}" in subjects
    assert f"pessoa:{pessoas['ana'].pk}" in subjects


# ── 3 · Trilha de leitura ───────────────────────────────────────────


def test_confirmacao_guarda_a_versao(pessoas):
    d = doc(dono=pessoas["dono"], leitura_obrigatoria=True, versao="1.0")

    confirmacao = cnt.confirmar(d, pessoas["ana"])

    assert confirmacao.versao == "1.0"
    assert cnt.ja_confirmou(d, pessoas["ana"])


def test_nova_versao_invalida_a_confirmacao_anterior(pessoas):
    """O ponto central da trilha: "todo mundo confirmou" tem de ser sobre o
    texto que está no ar."""
    d = doc(dono=pessoas["dono"], leitura_obrigatoria=True, versao="1.0")
    cnt.confirmar(d, pessoas["ana"])

    d.versao = "2.0"
    d.save(update_fields=["versao"])

    assert not cnt.ja_confirmou(d, pessoas["ana"])
    assert d in cnt.pendentes_de_leitura(pessoas["ana"])
    assert ConfirmacaoLeitura.objects.count() == 1, "a confirmação da v1 é preservada"


def test_pendentes_ignora_o_que_nao_e_obrigatorio(pessoas):
    doc(dono=pessoas["dono"], slug="opcional", leitura_obrigatoria=False)
    doc(dono=pessoas["dono"], slug="obrigatorio", leitura_obrigatoria=True)

    pendentes = cnt.pendentes_de_leitura(pessoas["ana"])
    assert [d.slug for d in pendentes] == ["obrigatorio"]


def test_pendentes_respeita_publico_alvo(pessoas):
    doc(dono=pessoas["dono"], slug="ti", leitura_obrigatoria=True,
        publico_alvo=[f"depto:{pessoas['ti'].pk}"])

    assert cnt.pendentes_de_leitura(pessoas["ana"])
    assert not cnt.pendentes_de_leitura(pessoas["bruno"])


def test_pendentes_ignora_vencido(pessoas):
    doc(dono=pessoas["dono"], leitura_obrigatoria=True,
        vigencia_fim=HOJE - timedelta(days=1))

    assert not cnt.pendentes_de_leitura(pessoas["ana"])


def test_confirmar_vencido_e_recusado(pessoas):
    """Registraria conformidade com um texto que não vale mais."""
    d = doc(dono=pessoas["dono"], leitura_obrigatoria=True,
            vigencia_fim=HOJE - timedelta(days=1))

    with pytest.raises(cnt.ConteudoError):
        cnt.confirmar(d, pessoas["ana"])


def test_confirmar_e_idempotente(pessoas):
    """Duplo clique não pode estourar."""
    d = doc(dono=pessoas["dono"], leitura_obrigatoria=True)

    primeira = cnt.confirmar(d, pessoas["ana"])
    segunda = cnt.confirmar(d, pessoas["ana"])

    assert primeira.pk == segunda.pk
    assert ConfirmacaoLeitura.objects.count() == 1


def test_confirmar_exige_identidade(pessoas):
    from django.contrib.auth.models import AnonymousUser

    d = doc(dono=pessoas["dono"], leitura_obrigatoria=True)

    with pytest.raises(cnt.ConteudoError):
        cnt.confirmar(d, AnonymousUser())


def test_confirmacao_pela_tela(client, pessoas):
    d = doc(dono=pessoas["dono"], leitura_obrigatoria=True)
    client.force_login(pessoas["ana"])

    resposta = client.post(reverse("workspace:confirmar_leitura", args=(d.slug,)))

    assert resposta.status_code == 302
    assert cnt.ja_confirmou(d, pessoas["ana"])


def test_get_nao_confirma_leitura(client, pessoas):
    """Pré-carregamento de link do navegador registraria conformidade que a
    pessoa nunca declarou — e é esse registro que se leva a uma audiência."""
    d = doc(dono=pessoas["dono"], leitura_obrigatoria=True)
    client.force_login(pessoas["ana"])

    client.get(reverse("workspace:confirmar_leitura", args=(d.slug,)))

    assert not cnt.ja_confirmou(d, pessoas["ana"])


def test_confirmar_documento_restrito_e_recusado(client, pessoas):
    d = doc(dono=pessoas["dono"], leitura_obrigatoria=True,
            publico_alvo=[f"depto:{pessoas['ti'].pk}"])
    client.force_login(pessoas["bruno"])

    resposta = client.post(reverse("workspace:confirmar_leitura", args=(d.slug,)))

    assert resposta.status_code == 403
    assert not cnt.ja_confirmou(d, pessoas["bruno"])


def test_cobertura_conta_so_a_versao_atual(pessoas):
    d = doc(dono=pessoas["dono"], leitura_obrigatoria=True, versao="1.0")
    cnt.confirmar(d, pessoas["ana"])
    cnt.confirmar(d, pessoas["bruno"])
    assert cnt.cobertura_de_leitura(d)["confirmadas"] == 2

    d.versao = "2.0"
    d.save(update_fields=["versao"])

    assert cnt.cobertura_de_leitura(d) == {"versao": "2.0", "confirmadas": 0}


def test_dono_ve_a_cobertura_e_os_outros_nao(client, pessoas):
    d = doc(dono=pessoas["dono"], leitura_obrigatoria=True)
    cnt.confirmar(d, pessoas["ana"])

    # "esta versão" e não "confirmaram esta versão": com UMA confirmação o
    # `blocktrans` usa o singular ("1 pessoa confirmou"), e assertar o plural
    # reprovaria a tela certa.
    client.force_login(pessoas["dono"])
    assert "esta versão" in client.get(
        reverse("workspace:documento", args=(d.slug,))
    ).content.decode()

    client.force_login(pessoas["bruno"])
    assert "esta versão" not in client.get(
        reverse("workspace:documento", args=(d.slug,))
    ).content.decode()


# ── Para o dono ─────────────────────────────────────────────────────


def test_a_vencer_filtra_por_dono(pessoas):
    doc(dono=pessoas["dono"], slug="meu", vigencia_fim=HOJE + timedelta(days=10))
    doc(dono=pessoas["ana"], slug="dela", vigencia_fim=HOJE + timedelta(days=10))

    assert [d.slug for d in cnt.a_vencer(dono=pessoas["dono"])] == ["meu"]
    assert cnt.a_vencer().count() == 2


def test_a_vencer_ignora_o_que_esta_longe(pessoas):
    doc(dono=pessoas["dono"], vigencia_fim=HOJE + timedelta(days=200))

    assert not cnt.a_vencer(dono=pessoas["dono"]).exists()


def test_vencidos_e_a_fila_de_trabalho_do_dono(pessoas):
    doc(dono=pessoas["dono"], slug="passou", vigencia_fim=HOJE - timedelta(days=3))
    doc(dono=pessoas["dono"], slug="ok")

    assert [d.slug for d in cnt.vencidos(dono=pessoas["dono"])] == ["passou"]
    assert cnt.vencidos().count() == 1


# ── Meu dia ─────────────────────────────────────────────────────────


def test_leitura_obrigatoria_aparece_no_meu_dia(pessoas):
    from workspace.services import meu_dia as md

    doc(dono=pessoas["dono"], leitura_obrigatoria=True, titulo="Política de viagens")

    bloco = next(b for b in md.para(pessoas["ana"])["blocos"] if b.chave == "leituras")

    assert bloco.urgente
    assert bloco.itens[0].titulo == "Política de viagens"


def test_leitura_confirmada_sai_do_meu_dia(pessoas):
    from workspace.services import meu_dia as md

    d = doc(dono=pessoas["dono"], leitura_obrigatoria=True)
    cnt.confirmar(d, pessoas["ana"])

    assert "leituras" not in {b.chave for b in md.para(pessoas["ana"])["blocos"]}


def test_documento_a_vencer_aparece_so_para_o_dono(pessoas):
    from workspace.services import meu_dia as md

    doc(dono=pessoas["dono"], vigencia_fim=HOJE + timedelta(days=10))

    chaves_dono = {b.chave for b in md.para(pessoas["dono"])["blocos"]}
    chaves_ana = {b.chave for b in md.para(pessoas["ana"])["blocos"]}

    assert "documentos_do_dono" in chaves_dono
    assert "documentos_do_dono" not in chaves_ana


def test_vencido_do_dono_e_urgente_e_a_vencer_nao(pessoas):
    from workspace.services import meu_dia as md

    doc(dono=pessoas["dono"], slug="futuro", vigencia_fim=HOJE + timedelta(days=10))
    bloco = next(
        b for b in md.para(pessoas["dono"])["blocos"] if b.chave == "documentos_do_dono"
    )
    assert not bloco.urgente, "'vence em 10 dias' é planejamento"

    doc(dono=pessoas["dono"], slug="passou", vigencia_fim=HOJE - timedelta(days=1))
    bloco = next(
        b for b in md.para(pessoas["dono"])["blocos"] if b.chave == "documentos_do_dono"
    )
    assert bloco.urgente, "POP vencido em vigor é risco de conformidade"


# ── A vitrine e o tile ──────────────────────────────────────────────


def test_vitrine_agrupa_na_ordem_de_busca(client, pessoas):
    """POP antes de Instrução de trabalho — ordem do enum, não alfabética."""
    doc(dono=pessoas["dono"], slug="instr", tipo=TipoDocumento.INSTRUCAO, titulo="Instrução X")
    doc(dono=pessoas["dono"], slug="pop", tipo=TipoDocumento.POP, titulo="POP Y")

    corpo = client.get(reverse("workspace:documentacao")).content.decode()

    assert corpo.index("POP — procedimento") < corpo.index("Instrução de trabalho")


def test_tile_de_documentacao_deixou_de_ser_em_breve(client, pessoas):
    doc(dono=pessoas["dono"])
    resposta = client.get(reverse("workspace:home"))
    tile = next(a for a in resposta.context["apps"] if a.chave == "documentacao")

    assert tile.disponivel
    assert tile.destino == reverse("workspace:documentacao")


def test_modulo_com_rota_propria_nao_usa_a_pagina_de_catalogo(client, pessoas):
    """Acervo normativo não é fila de pedidos. Forçá-lo na tela de catálogo
    produziria uma vitrine de coisas que não se pedem."""
    assert client.get(reverse("workspace:modulo", args=("documentacao",))).status_code == 404


def test_vitrine_sem_documento_orienta_onde_publicar(client, pessoas):
    corpo = client.get(reverse("workspace:documentacao")).content.decode()

    assert "Nenhum documento em vigor." in corpo
    assert "Documentos" in corpo


def test_corpo_nao_e_renderizado_como_html(client, pessoas):
    """`|safe` no corpo transformaria o admin em vetor de XSS para a empresa."""
    doc(dono=pessoas["dono"], corpo="<script>alert(1)</script>")

    corpo = client.get(reverse("workspace:documento", args=("pop-teste",))).content.decode()

    assert "<script>alert(1)</script>" not in corpo
    assert "&lt;script&gt;" in corpo


def test_telas_sem_estilo_inline(client, pessoas):
    """A CSP de produção tem nonce em `style-src`, o que faz o navegador ignorar
    `unsafe-inline` — e nonce não se aplica a atributo `style`."""
    doc(dono=pessoas["dono"], leitura_obrigatoria=True)
    client.force_login(pessoas["ana"])

    for rota, args in [
        ("workspace:documentacao", ()),
        ("workspace:documento", ("pop-teste",)),
        ("workspace:meu_dia", ()),
    ]:
        corpo = client.get(reverse(rota, args=args)).content.decode()
        assert "style=" not in corpo, f"{rota} tem estilo inline"


def test_str_dos_models(pessoas):
    d = doc(dono=pessoas["dono"], leitura_obrigatoria=True)
    confirmacao = cnt.confirmar(d, pessoas["ana"])

    assert str(d) == "POP de teste v1.0"
    assert "leu POP de teste" in str(confirmacao)


def test_para_todos_e_dias_para_vencer(pessoas):
    aberto = doc(dono=pessoas["dono"], slug="a", vigencia_fim=HOJE + timedelta(days=7))
    restrito = doc(dono=pessoas["dono"], slug="b", publico_alvo=["papel:rh"])

    assert aberto.para_todos
    assert aberto.dias_para_vencer == 7
    assert not restrito.para_todos


def test_papel_precisa_existir_para_o_teste_fazer_sentido(pessoas):
    """Guarda contra teste que passa por acidente: se `Papel` não existisse,
    `publico_alvo=["papel:x"]` nunca casaria e o teste acima seria vazio."""
    assert Papel.objects.filter(chave="sesmt").exists() is False
    papel = f.papel("sesmt", ["rh.ler.global"], escopo="global")
    f.atribuir(pessoas["ana"], papel)
    doc(dono=pessoas["dono"], publico_alvo=["papel:sesmt"])

    assert cnt.visiveis_para(pessoas["ana"]).count() == 1


# ── Ramos que faltavam ──────────────────────────────────────────────


def test_vigente_e_falso_para_revogado(pessoas):
    """`vigente` tem de barrar por SITUAÇÃO, não só por data.

    Um revogado com vigência aberta passaria como em vigor se a checagem
    olhasse só o calendário.
    """
    d = doc(dono=pessoas["dono"], situacao=SituacaoDocumento.REVOGADO, vigencia_fim=None)

    assert not d.vigente
    assert not d.vencido, "não venceu — foi revogado, que é outra coisa"


def test_meu_dia_ignora_anonimo():
    from django.contrib.auth.models import AnonymousUser

    from workspace.services import meu_dia as md

    contexto = md.para(AnonymousUser())
    assert "documentos_do_dono" not in {b.chave for b in contexto["blocos"]}
    assert "leituras" not in {b.chave for b in contexto["blocos"]}


def test_tela_mostra_o_motivo_quando_a_confirmacao_e_recusada(client, pessoas):
    """Documento que vence entre carregar a página e clicar no botão.

    Sem a mensagem, o clique não faz nada visível e a pessoa clica de novo.
    """
    d = doc(dono=pessoas["dono"], leitura_obrigatoria=True)
    client.force_login(pessoas["ana"])

    Documento.objects.filter(pk=d.pk).update(vigencia_fim=HOJE - timedelta(days=1))
    resposta = client.post(
        reverse("workspace:confirmar_leitura", args=(d.slug,)), follow=True
    )

    assert "não está vigente" in resposta.content.decode()
    assert not ConfirmacaoLeitura.objects.exists()


def test_modulo_sem_catalogo_e_sem_rota_nao_esta_disponivel():
    from workspace.modulos import Modulo

    assert not Modulo(chave="x", nome="X", descricao="", icone="file").disponivel
    assert Modulo(chave="y", nome="Y", descricao="", icone="file", rota="workspace:home").disponivel
    assert Modulo(chave="z", nome="Z", descricao="", icone="file", dominios=("z.",)).disponivel


# ── Admin ───────────────────────────────────────────────────────────


def test_admin_nao_permite_lancar_confirmacao():
    """Confirmação lançada à mão é declaração falsa de conformidade — e é
    exatamente o registro que se leva a uma audiência."""
    from django.contrib.admin.sites import AdminSite

    from workspace.admin import ConfirmacaoInline

    inline = ConfirmacaoInline(ConfirmacaoLeitura, AdminSite())
    assert inline.has_add_permission(None, None) is False


@pytest.mark.parametrize(
    ("kwargs", "esperado"),
    [
        ({}, "em vigor"),
        ({"situacao": SituacaoDocumento.REVOGADO}, "revogado"),
        ({"vigencia_fim": HOJE - timedelta(days=1)}, "VENCIDO"),
        ({"situacao": SituacaoDocumento.RASCUNHO}, "rascunho"),
    ],
)
def test_admin_mostra_o_estado_real(pessoas, kwargs, esperado):
    """A coluna existe porque `situacao` sozinha mente: um documento marcado
    `vigente` com vigência encerrada aparece como vigente na lista."""
    from django.contrib.admin.sites import AdminSite

    from workspace.admin import DocumentoAdmin

    d = doc(dono=pessoas["dono"], **kwargs)
    admin = DocumentoAdmin(Documento, AdminSite())

    assert admin.situacao_real(d) == esperado
