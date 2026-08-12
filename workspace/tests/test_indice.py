"""O índice de busca — e o recorte por permissão, que é a razão dele existir.

O teste mais importante deste arquivo é `test_recorte_acontece_no_where`. Todo o
resto é consequência.

A Etapa 5 §5.10 é categórica: *security trimming* no índice, nunca no
pós-processamento. O motivo é concreto e não é desempenho — filtrar depois de
recuperar faz a **contagem vazar**. "8 resultados" que viram 3 na tela conta ao
usuário que existem cinco coisas que ele não pode ver, e às vezes o título passa
no caminho.
"""

from __future__ import annotations

from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.models.busca import EntradaIndice, OrigemIndice
from workspace.models.catalogo import GrupoCatalogo, ItemCatalogo
from workspace.models.comunicacao import Publicacao
from workspace.models.conteudo import Documento, SituacaoDocumento, TipoDocumento
from workspace.services import indice as idx
from workspace.services.busca import buscar

pytestmark = pytest.mark.django_db

HOJE = timezone.localdate()


@pytest.fixture
def pessoas():
    dono, ana, bruno = (f.pessoa(n) for n in ("dono", "ana", "bruno"))
    ti = f.departamento("TI", "Tecnologia")
    ops = f.departamento("OPS", "Operações")
    f.lotar(dono, dep=ti)
    f.lotar(ana, dep=ti)
    f.lotar(bruno, dep=ops)
    return {"dono": dono, "ana": ana, "bruno": bruno, "ti": ti, "ops": ops}


def documento(dono, **kwargs):
    padrao = {
        "slug": kwargs.get("slug", "pop-teste"),
        "tipo": TipoDocumento.POP,
        "titulo": "POP de instalação",
        "corpo": "Vistoria, instalação, teste.",
        "versao": "1.0",
        "publico_alvo": ["*"],
        "situacao": SituacaoDocumento.VIGENTE,
        "vigencia_inicio": HOJE - timedelta(days=1),
        "dono": dono,
    }
    return Documento.objects.create(**{**padrao, **kwargs})


# ── O recorte, no banco ─────────────────────────────────────────────


def test_recorte_acontece_no_where(pessoas):
    """A razão de o índice existir.

    Se o filtro fosse em Python, a consulta traria as duas entradas e o Python
    descartaria uma — e a contagem antes do descarte é a informação que vaza.
    """
    documento(pessoas["dono"], slug="geral", titulo="Politica geral")
    documento(
        pessoas["dono"], slug="so-ti", titulo="Politica de TI",
        publico_alvo=[f"depto:{pessoas['ti'].pk}"],
    )

    from identidade.services.autorizacao import subjects_de

    consulta = EntradaIndice.objects.para_sujeitos(subjects_de(pessoas["bruno"]))

    with CaptureQueriesContext(connection) as capturadas:
        assert consulta.count() == 1

    sql = " ".join(c["sql"] for c in capturadas).lower()
    assert "join" in sql and "in (" in sql, (
        "o recorte tem de estar no SQL — filtro em Python vaza contagem"
    )


def test_contagem_nao_vaza(pessoas):
    """O sintoma que o recorte no banco evita."""
    for i in range(5):
        documento(
            pessoas["dono"], slug=f"restrito-{i}", titulo=f"Norma restrita {i}",
            publico_alvo=[f"depto:{pessoas['ti'].pk}"],
        )
    documento(pessoas["dono"], slug="publico", titulo="Norma publica")

    grupos = buscar("norma", pessoas["bruno"])

    assert [r.titulo for r in grupos["Documentação"]] == ["Norma publica"]


def test_entrada_com_dois_sujeitos_nao_duplica(pessoas):
    """`["*", "depto:TI"]` casaria duas vezes para quem é de TI."""
    documento(
        pessoas["dono"], titulo="Norma dupla",
        publico_alvo=["*", f"depto:{pessoas['ti'].pk}"],
    )

    assert len(buscar("dupla", pessoas["ana"])["Documentação"]) == 1


def test_anonimo_ve_so_o_publico(pessoas):
    documento(pessoas["dono"], slug="geral", titulo="Politica geral")
    documento(
        pessoas["dono"], slug="restrito", titulo="Politica restrita",
        publico_alvo=[f"depto:{pessoas['ti'].pk}"],
    )

    grupos = buscar("politica", None)

    assert [r.titulo for r in grupos["Documentação"]] == ["Politica geral"]


# ── Manutenção por sinal ────────────────────────────────────────────


def test_publicar_documento_indexa_na_hora(pessoas):
    """Índice que atualiza de madrugada faz o autor publicar e não achar."""
    documento(pessoas["dono"], titulo="Norma nova")

    assert buscar("norma nova", pessoas["ana"])["Documentação"]


def test_rascunho_nao_entra_no_indice(pessoas):
    documento(pessoas["dono"], titulo="Segredo", situacao=SituacaoDocumento.RASCUNHO)

    assert buscar("segredo", pessoas["dono"]) == {}
    assert not EntradaIndice.objects.filter(dominio="cnt.documento").exists()


def test_vencer_tira_do_indice(pessoas):
    """A busca é onde o POP errado é encontrado por acidente."""
    d = documento(pessoas["dono"], titulo="Norma antiga")
    assert buscar("antiga", pessoas["ana"])

    d.vigencia_fim = HOJE - timedelta(days=1)
    d.save()

    assert buscar("antiga", pessoas["ana"]) == {}


def test_revogar_tira_do_indice(pessoas):
    d = documento(pessoas["dono"], titulo="Norma revogada")
    d.situacao = SituacaoDocumento.REVOGADO
    d.save()

    assert buscar("revogada", pessoas["ana"]) == {}


def test_apagar_documento_tira_do_indice(pessoas):
    d = documento(pessoas["dono"], titulo="Norma efemera")
    d.delete()

    assert not EntradaIndice.objects.exists()


def test_mudar_publico_alvo_SUBSTITUI_o_sujeito(pessoas):
    """O furo que `indexar()` evita: acrescentar em vez de substituir deixaria o
    `*` antigo, e a mudança de público não teria efeito na busca — a tela do
    documento diria uma coisa e a busca outra.
    """
    d = documento(pessoas["dono"], titulo="Norma que fecha")
    assert buscar("fecha", pessoas["bruno"])["Documentação"]

    d.publico_alvo = [f"depto:{pessoas['ti'].pk}"]
    d.save()

    assert buscar("fecha", pessoas["bruno"]) == {}
    assert buscar("fecha", pessoas["ana"])["Documentação"]


def test_publicacao_entra_e_sai(pessoas):
    pub = Publicacao.objects.create(
        titulo="Aviso de manutencao", resumo="Sabado", publicado=True
    )
    assert buscar("manutencao", pessoas["ana"])["Comunicados"]

    pub.publicado = False
    pub.save()

    assert buscar("manutencao", pessoas["ana"]) == {}


def test_publicacao_agendada_nao_entra(pessoas):
    Publicacao.objects.create(
        titulo="Anuncio de amanha",
        publicado=True,
        publicar_em=timezone.now() + timedelta(days=1),
    )

    assert buscar("anuncio", pessoas["ana"]) == {}


def test_item_de_catalogo_entra(pessoas):
    ItemCatalogo.objects.create(
        chave="reembolso", nome="Reembolso", descricao_curta="Despesa que voce pagou",
        grupo=GrupoCatalogo.DINHEIRO, dominio="fin.reembolso", icone="wallet",
        prazo_prometido_dias=5,
    )

    resultados = buscar("reembolso", pessoas["ana"])["Serviços"]
    assert resultados[0].url == "/workspace/servicos/reembolso/"


def test_item_inativo_sai(pessoas):
    item = ItemCatalogo.objects.create(
        chave="antigo", nome="Servico antigo", grupo=GrupoCatalogo.DINHEIRO,
        dominio="fin.x", prazo_prometido_dias=1,
    )
    item.ativo = False
    item.save()

    assert buscar("antigo", pessoas["ana"]) == {}


def test_item_com_permissao_continua_encontravel(pessoas):
    """O catálogo MOSTRA o item fora do alcance e o marca "Sem acesso".
    Esconder na busca contradiria a tela."""
    ItemCatalogo.objects.create(
        chave="restrito", nome="Servico restrito", grupo=GrupoCatalogo.DINHEIRO,
        dominio="fin.x", prazo_prometido_dias=1, permissao="fin.admin.global",
    )

    assert buscar("restrito", pessoas["ana"])["Serviços"]


# ── Reindexação ─────────────────────────────────────────────────────


def test_reindexar_recupera_indice_apagado(pessoas):
    documento(pessoas["dono"], titulo="Norma preservada")
    ItemCatalogo.objects.create(
        chave="x", nome="Servico x", grupo=GrupoCatalogo.DINHEIRO,
        dominio="fin.x", prazo_prometido_dias=1,
    )
    EntradaIndice.objects.all().delete()

    contagem = idx.reindexar()

    assert contagem["documentos"] == 1
    assert contagem["servicos"] == 1
    assert buscar("preservada", pessoas["ana"])["Documentação"]


def test_reindexar_remove_orfa(pessoas):
    """Entrada cuja origem sumiu sem passar pelo sinal — `queryset.delete()`
    em massa, ou apagada direto no banco."""
    documento(pessoas["dono"], titulo="Norma qualquer")
    Documento.objects.all().delete()
    # Recria a entrada órfã à mão, simulando o que `update()` em massa deixaria.
    idx.indexar(
        dominio="cnt.documento", origem_id="9999", origem=OrigemIndice.DOCUMENTO,
        titulo="Fantasma", url="/x/",
    )

    contagem = idx.reindexar()

    assert contagem["removidas"] == 1
    assert not EntradaIndice.objects.filter(titulo="Fantasma").exists()


def test_reindexar_e_idempotente(pessoas):
    documento(pessoas["dono"])
    idx.reindexar()
    antes = EntradaIndice.objects.count()

    idx.reindexar()

    assert EntradaIndice.objects.count() == antes


def test_comando_de_reindexacao(pessoas):
    documento(pessoas["dono"], titulo="Norma do comando")
    saida = StringIO()

    call_command("reindexar_busca", stdout=saida)

    texto = saida.getvalue()
    assert "Índice reconstruído" in texto
    assert "documentos    1" in texto


def test_comando_relata_orfa(pessoas):
    idx.indexar(
        dominio="cnt.documento", origem_id="8888", origem=OrigemIndice.DOCUMENTO,
        titulo="Fantasma", url="/x/",
    )
    saida = StringIO()

    call_command("reindexar_busca", stdout=saida)

    assert "órfãs removidas 1" in saida.getvalue()


# ── A busca ─────────────────────────────────────────────────────────


def test_ordem_dos_grupos_poe_servico_antes_de_documento(pessoas):
    """Quem busca "reembolso" quer pedir um, não ler a política sobre ele."""
    ItemCatalogo.objects.create(
        chave="reembolso", nome="Reembolso", grupo=GrupoCatalogo.DINHEIRO,
        dominio="fin.reembolso", prazo_prometido_dias=5,
    )
    documento(pessoas["dono"], titulo="Politica de reembolso")
    Publicacao.objects.create(titulo="Reembolso mudou", publicado=True)

    grupos = list(buscar("reembolso", pessoas["ana"]))

    assert grupos.index("Serviços") < grupos.index("Documentação")
    assert grupos.index("Documentação") < grupos.index("Comunicados")


def test_aplicativos_vem_por_ultimo(pessoas):
    """Aplicativo é navegação — quem digita já sabe para onde vai. O que ele
    não sabe é que existe um serviço que resolve."""
    documento(pessoas["dono"], slug="doc-rh", titulo="Norma de RH")

    grupos = list(buscar("rh", pessoas["ana"]))

    assert grupos[-1] == "Aplicativos"


def test_encontra_pelo_corpo(pessoas):
    documento(pessoas["dono"], titulo="POP qualquer", corpo="Fixar o talabarte no ponto de ancoragem.")

    assert buscar("talabarte", pessoas["ana"])["Documentação"]


def test_busca_sem_acento_encontra_com_acento(pessoas):
    documento(pessoas["dono"], titulo="Política de manutenção")

    assert buscar("manutencao", pessoas["ana"])["Documentação"]


def test_consulta_curta_devolve_vazio(pessoas):
    documento(pessoas["dono"])
    assert buscar("a", pessoas["ana"]) == {}
    assert buscar("", pessoas["ana"]) == {}


def test_limita_por_grupo(pessoas):
    for i in range(10):
        documento(pessoas["dono"], slug=f"norma-{i}", titulo=f"Norma numero {i}")

    from workspace.services.busca import LIMITE_POR_GRUPO

    assert len(buscar("norma", pessoas["ana"])["Documentação"]) == LIMITE_POR_GRUPO


def test_uma_consulta_para_todos_os_grupos(pessoas):
    """Uma consulta por grupo multiplicaria por quatro o custo do JOIN de
    sujeitos a cada tecla digitada."""
    documento(pessoas["dono"], slug="d", titulo="Coisa documento")
    Publicacao.objects.create(titulo="Coisa comunicado", publicado=True)
    ItemCatalogo.objects.create(
        chave="c", nome="Coisa servico", grupo=GrupoCatalogo.DINHEIRO,
        dominio="fin.x", prazo_prometido_dias=1,
    )

    with CaptureQueriesContext(connection) as capturadas:
        grupos = buscar("coisa", pessoas["ana"])

    assert len(grupos) == 3
    do_indice = [
        c for c in capturadas if "wks_indice" in c["sql"] or "entradaindice" in c["sql"].lower()
    ]
    assert len(do_indice) == 1, f"{len(do_indice)} consultas ao índice"


# ── A paleta na casca ───────────────────────────────────────────────


@pytest.mark.parametrize(
    "rota",
    ["workspace:home", "workspace:documentacao", "workspace:meu_dia", "workspace:servicos"],
)
def test_paleta_existe_em_toda_tela(client, pessoas, rota):
    """O bug que isto trava: o campo existia só na home, então ⌘K — que está no
    JS desde o começo — não funcionava em nenhuma outra tela."""
    client.force_login(pessoas["ana"])
    corpo = client.get(reverse(rota)).content.decode()

    assert 'id="paleta"' in corpo, f"{rota} sem a paleta"
    assert 'id="busca"' in corpo, f"{rota} sem o campo"
    assert "workspace/js/workspace.js" in corpo, f"{rota} sem o script"


def test_home_tem_gatilho_e_nao_um_segundo_campo(client, pessoas):
    """Dois campos com o mesmo id resolveriam o ⌘K criando problema pior."""
    corpo = client.get(reverse("workspace:home")).content.decode()

    assert corpo.count('id="busca"') == 1
    assert "data-abre-busca" in corpo


def test_paleta_e_dialog_nativo(client, pessoas):
    """`<dialog>` traz Esc, foco preso e fundo inerte do navegador. Um `div`
    exigiria reimplementar tudo isso, que é a origem mais comum de armadilha
    de foco em produto interno."""
    corpo = client.get(reverse("workspace:home")).content.decode()

    assert '<dialog class="au-paleta"' in corpo


def test_paleta_nao_tem_estilo_inline(client, pessoas):
    corpo = client.get(reverse("workspace:home")).content.decode()
    assert "style=" not in corpo


# ── Ramos que faltavam ──────────────────────────────────────────────


def test_apagar_publicacao_tira_do_indice(pessoas):
    pub = Publicacao.objects.create(titulo="Aviso efemero", publicado=True)
    assert buscar("efemero", pessoas["ana"])["Comunicados"]

    pub.delete()

    assert buscar("efemero", pessoas["ana"]) == {}
    assert not EntradaIndice.objects.filter(dominio="com.publicacao").exists()


def test_reindexar_cobre_publicacao(pessoas):
    """A reindexação varre as TRÊS origens. Faltar uma deixaria conteúdo fora
    do índice depois de uma migração de dado — e ninguém procura o que não sabe
    que existe."""
    Publicacao.objects.create(titulo="Comunicado antigo", publicado=True)
    Publicacao.objects.create(titulo="Rascunho", publicado=False)
    EntradaIndice.objects.all().delete()

    contagem = idx.reindexar()

    assert contagem["publicacoes"] == 1, "só o que está no ar"
    assert buscar("comunicado antigo", pessoas["ana"])["Comunicados"]


def test_str_das_entradas(pessoas):
    documento(pessoas["dono"], titulo="Norma com nome")
    entrada = EntradaIndice.objects.get(dominio="cnt.documento")

    assert str(entrada) == "Documentação · Norma com nome"
    assert str(entrada.sujeitos.first()) == "*"


def test_frase_com_palavra_de_pergunta_acha_o_documento(pessoas):
    """"qual a política de viagens" devolvia ZERO documentos.

    "qual" entrava na consulta como se fosse conteúdo, e o E exigia que algum
    texto contivesse "qual". A busca recusava a ação corretamente e não achava
    nada — a pior combinação, porque parece que nada funciona.
    """
    documento(pessoas["dono"], titulo="Politica de viagens e reembolso")

    grupos = buscar("qual a politica de viagens", pessoas["ana"])

    assert [r.titulo for r in grupos["Documentação"]] == ["Politica de viagens e reembolso"]


def test_e_com_queda_para_ou(pessoas):
    """Frase conversacional sempre traz palavra que não está em texto nenhum.

    "politica de viagem urgente" combinado por E devolve zero, porque nenhum
    documento diz "urgente". A queda para OU acha o documento — e só acontece
    quando o E falhou.
    """
    documento(pessoas["dono"], titulo="Politica de viagens")

    assert buscar("politica viagens", pessoas["ana"])["Documentação"], "o E resolve"
    assert buscar("politica viagens inexistentexyz", pessoas["ana"])["Documentação"], (
        "a queda para OU resolve"
    )


def test_e_tem_precedencia_sobre_ou(pessoas):
    """Quando o E acha, o OU não roda — senão o resultado preciso viria diluído
    no meio de tudo que fala de uma das palavras."""
    documento(pessoas["dono"], slug="a", titulo="Politica de viagens")
    documento(pessoas["dono"], slug="b", titulo="Politica de compras")

    achados = [r.titulo for r in buscar("politica viagens", pessoas["ana"])["Documentação"]]

    assert achados == ["Politica de viagens"]
