"""§55 — a auditoria de segurança, executável.

Auditoria em PDF envelhece na primeira semana; esta roda no CI. Cada teste
guarda uma propriedade que, se quebrar, quebra em silêncio — que é a
característica de todo defeito de segurança que chega a produção.

## O que ela cobre

1. **Arquivo**: extensão, MIME, magic bytes e tamanho, no MESMO validador para
   todo upload do produto.
2. **Armazenamento**: nada de arquivo em caminho que o servidor web sirva sem
   perguntar quem é.
3. **CSRF e método**: nenhuma ação que muda estado acontece por `GET`.
4. **Segredo**: nada de chave de desenvolvimento em produção.
5. **Cabeçalhos**: CSP estrita, sem `unsafe-inline`, em toda resposta.
6. **Anônimo**: o hub é aberto, e nenhuma tela pessoal está nele.
7. **SQL**: o único SQL cru do projeto é parametrizado.

## O que ela NÃO cobre, e por quê

Não testa a força da senha nem o freio de tentativas — isso mora em
`contas/entrada.py` e tem os testes dele. Não testa dependência vulnerável:
isso é trabalho de ferramenta (`pip-audit`), não de suíte, e uma imitação em
teste daria falsa segurança.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from identidade.tests import fabricas as f

pytestmark = pytest.mark.django_db

RAIZ = Path(__file__).resolve().parent.parent.parent
PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000a49444154789c6300010000050001" "0d0a2db4" "0000000049454e44ae426082"
)


def fontes(*pastas) -> list[Path]:
    arquivos = []
    for pasta in pastas:
        arquivos += [
            caminho
            for caminho in (RAIZ / pasta).rglob("*.py")
            if "migrations" not in caminho.parts and "tests" not in caminho.parts
        ]
    return arquivos


# ── Upload ──────────────────────────────────────────────────────────


def test_arquivo_com_extensao_permitida_e_conteudo_errado_e_recusado():
    """Magic bytes é a única checagem que pega `.pdf` que na verdade é
    executável. Extensão e `Content-Type` vêm do cliente e mentem de graça."""
    from workspace.services.anexos import validar

    falso = SimpleUploadedFile("nota.png", b"MZ\x90\x00 sou um executavel",
                               content_type="image/png")

    assert validar(falso)


def test_arquivo_legitimo_passa():
    from workspace.services.anexos import validar

    assert validar(SimpleUploadedFile("foto.png", PNG, content_type="image/png")) == ""


def test_ha_teto_de_tamanho():
    """Sem teto, um upload de 4 GB é uma negação de serviço com um clique."""
    from workspace.services import validacao_arquivo as val

    fonte = Path(val.__file__).read_text(encoding="utf-8")

    assert "max_size" in fonte
    assert re.search(r"uploaded_file\.size\s*>", fonte)


def test_todo_upload_do_produto_passa_pelo_mesmo_validador():
    """Um segundo validador é o que esquece os magic bytes — e é sempre o mais
    novo que esquece."""
    from workspace.services import anexos, conteudo

    assert "validate_file_upload" in Path(anexos.__file__).read_text(encoding="utf-8")
    # O acervo delega para `anexos.validar` em vez de reimplementar.
    assert "anx.validar" in Path(conteudo.__file__).read_text(encoding="utf-8")


# ── Armazenamento ───────────────────────────────────────────────────


def test_o_armazenamento_privado_nao_tem_url_publica():
    """`.url` levantar erro é o desenho, não um bug: se um dia alguém puser o
    caminho num template, a página quebra em desenvolvimento em vez de servir o
    atestado médico de alguém pelo nginx."""
    from workspace.storage import ArmazenamentoPrivado

    with pytest.raises(ValueError):
        ArmazenamentoPrivado().url("qualquer/arquivo.pdf")


def test_todo_campo_de_arquivo_usa_armazenamento_privado():
    """Um `FileField` sem `storage=` cai em `MEDIA_ROOT`, que o servidor web
    entrega sem perguntar quem é."""
    from django.apps import apps
    from django.db.models import FileField

    from workspace.storage import ArmazenamentoPrivado

    publicos = []
    for model in apps.get_app_config("workspace").get_models():
        for campo in model._meta.get_fields():
            if isinstance(campo, FileField) and not isinstance(
                campo.storage, ArmazenamentoPrivado
            ):
                publicos.append(f"{model.__name__}.{campo.name}")

    assert publicos == [], f"campos de arquivo em armazenamento público: {publicos}"


def test_baixar_anexo_de_outra_pessoa_e_negado():
    """A porta única até o arquivo, e ela pergunta quem é."""
    from workspace.services import anexos as anx

    assert "def pode_baixar" in Path(anx.__file__).read_text(encoding="utf-8")


# ── Método e CSRF ───────────────────────────────────────────────────


ACOES_QUE_MUDAM_ESTADO = (
    ("workspace:marcar_lidas", ()),
    ("workspace:registrar_correspondencia", ()),
    ("workspace:entregar_custodia", ()),
    ("workspace:registrar_movimento", ()),
    ("workspace:cadastrar_veiculo", ()),
    ("workspace:oportunidade_nova", ()),
    ("workspace:cancelar_solicitacao", (1,)),
    ("workspace:reabrir_solicitacao", (1,)),
    ("workspace:descartar_rascunho", (1,)),
    ("workspace:aceitar_custodia", (1,)),
    ("workspace:devolver_custodia", (1,)),
    ("workspace:documento_revogar", ("qualquer",)),
    ("workspace:oportunidade_decidir", (1,)),
    ("workspace:cancelar_reserva", (1,)),
    ("workspace:relatorio_acao", (1,)),
)


@pytest.mark.parametrize(
    "rota,args", ACOES_QUE_MUDAM_ESTADO, ids=[r for r, _ in ACOES_QUE_MUDAM_ESTADO]
)
def test_acao_que_muda_estado_nao_acontece_por_get(client, rota, args):
    """`GET` que muda estado é executável por uma tag `<img>` num e-mail — e o
    CSRF do Django não protege `GET`, por desenho."""
    pessoa = f.pessoa("ana")
    f.lotar(pessoa)
    client.force_login(pessoa)

    resposta = client.get(reverse(rota, args=args))

    assert resposta.status_code in (302, 403, 404), (
        f"{rota} respondeu {resposta.status_code} a um GET"
    )


def test_nenhum_formulario_de_post_esquece_o_csrf():
    """Varre os templates: `<form method="post">` sem `{% csrf_token %}`."""
    faltando = []
    for caminho in (RAIZ / "workspace" / "templates").rglob("*.html"):
        texto = caminho.read_text(encoding="utf-8")
        for bloco in re.findall(r"<form[^>]*method=[\"']post[\"'].*?</form>", texto,
                                re.DOTALL | re.IGNORECASE):
            if "csrf_token" not in bloco:
                faltando.append(caminho.name)
    assert faltando == [], f"formulário POST sem CSRF: {sorted(set(faltando))}"


def test_o_logout_nao_e_um_link():
    """`LogoutView` recusa `GET` desde o Django 4.1, e está certa: um link que
    desloga permite a um site de fora tirar você daqui com uma imagem
    escondida."""
    casca = (RAIZ / "workspace/templates/workspace/_shell.html").read_text(encoding="utf-8")

    assert 'action="{% url \'sair\' %}"' in casca
    assert 'href="{% url \'sair\' %}"' not in casca


# ── Cabeçalhos e CSP ────────────────────────────────────────────────


def test_a_csp_nao_tem_unsafe_inline(client):
    resposta = client.get(reverse("workspace:home"))
    csp = resposta["Content-Security-Policy"]

    assert "unsafe-inline" not in csp
    assert "unsafe-eval" not in csp
    assert "default-src 'self'" in csp


def test_os_cabecalhos_de_seguranca_vao_em_toda_resposta(client):
    resposta = client.get(reverse("workspace:home"))

    assert resposta["X-Content-Type-Options"] == "nosniff"
    assert resposta["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert resposta["Cross-Origin-Opener-Policy"] == "same-origin"


def test_nenhum_template_usa_estilo_ou_handler_inline():
    """A CSP é `style-src 'self'` sem `unsafe-inline`: navegador moderno
    DESCARTA `style=""` em silêncio, e o elemento simplesmente não recebe o
    estilo — sem nada no log do servidor."""
    ofensores = []
    for caminho in (RAIZ / "workspace" / "templates").rglob("*.html"):
        texto = caminho.read_text(encoding="utf-8")
        if re.search(r'\sstyle\s*=\s*["\']', texto):
            ofensores.append(f"{caminho.name} (style=)")
        if re.search(r'\son(click|load|error|submit|change)\s*=', texto):
            ofensores.append(f"{caminho.name} (handler inline)")
    assert ofensores == [], ofensores


def test_link_para_fora_leva_noopener():
    """`target="_blank"` sem `rel="noopener"` entrega `window.opener` à página
    de destino, que pode trocar a nossa por uma cópia pedindo senha."""
    faltando = []
    for caminho in (RAIZ / "workspace" / "templates").rglob("*.html"):
        texto = caminho.read_text(encoding="utf-8")
        for tag in re.findall(r"<a\s[^>]*>", texto):
            if '_blank' in tag and "noopener" not in tag:
                faltando.append(caminho.name)
    assert faltando == [], f"link _blank sem noopener: {sorted(set(faltando))}"


# ── Produção ────────────────────────────────────────────────────────


def _carregar_producao():
    """Recarrega `settings.prod` lendo o ambiente atual.

    `base` também é recarregado, e é obrigatório: `ALLOWED_HOSTS` é calculado no
    import dele, e recarregar só o `prod` traria a lista do primeiro import — o
    teste passaria por acidente, medindo a configuração de outro momento.
    """
    import importlib

    base = importlib.reload(importlib.import_module("iconnect_workspace.settings.base"))
    del base
    return importlib.reload(importlib.import_module("iconnect_workspace.settings.prod"))


def test_producao_recusa_a_chave_de_desenvolvimento(monkeypatch):
    """Chave de desenvolvimento em produção é o defeito que ninguém percebe até
    alguém forjar uma sessão."""
    from django.core.exceptions import ImproperlyConfigured

    monkeypatch.setenv("SECRET_KEY", "dev-only-nao-usar-em-producao")
    monkeypatch.setenv("ALLOWED_HOSTS", "exemplo.com.br")

    with pytest.raises(ImproperlyConfigured, match="SECRET_KEY"):
        _carregar_producao()


def test_producao_exige_allowed_hosts(monkeypatch):
    from django.core.exceptions import ImproperlyConfigured

    monkeypatch.setenv("SECRET_KEY", "uma-chave-longa-de-producao-de-verdade")
    monkeypatch.setenv("ALLOWED_HOSTS", "")

    with pytest.raises(ImproperlyConfigured, match="ALLOWED_HOSTS"):
        _carregar_producao()


def test_producao_exige_https_e_cookie_seguro(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "uma-chave-longa-de-producao-de-verdade")
    monkeypatch.setenv("ALLOWED_HOSTS", "exemplo.com.br")
    prod = _carregar_producao()

    assert prod.DEBUG is False
    assert prod.SESSION_COOKIE_SECURE
    assert prod.CSRF_COOKIE_SECURE
    assert prod.SECURE_HSTS_SECONDS >= 31_536_000
    assert prod.SESSION_COOKIE_HTTPONLY
    assert prod.X_FRAME_OPTIONS == "DENY"


def test_nenhum_segredo_escrito_no_codigo():
    """Senha, token ou chave literal no fonte vaza pelo git e não sai mais de lá."""
    suspeitos = []
    padrao = re.compile(
        r"""(SECRET_KEY|PASSWORD|TOKEN|API_KEY)\s*=\s*["'][^"']{12,}["']""",
        re.IGNORECASE,
    )
    for caminho in fontes("workspace", "identidade", "contas", "financas",
                          "iconnect_workspace"):
        for linha in padrao.findall(caminho.read_text(encoding="utf-8")):
            suspeitos.append(f"{caminho.name}: {linha}")
    # A única atribuição literal aceita é a chave de desenvolvimento, que o
    # `prod.py` recusa explicitamente.
    assert suspeitos == [], suspeitos


# ── SQL ─────────────────────────────────────────────────────────────


def test_o_unico_sql_cru_e_parametrizado():
    """A CTE recursiva do organograma é o único SQL escrito à mão do projeto."""
    com_sql = []
    for caminho in fontes("workspace", "identidade", "contas", "financas",
                          "iconnect_workspace"):
        texto = caminho.read_text(encoding="utf-8")
        if "cursor.execute" in texto:
            com_sql.append(caminho)

    assert {c.name for c in com_sql} == {"autorizacao.py", "saude.py"}

    for caminho in com_sql:
        texto = caminho.read_text(encoding="utf-8")
        # Nada de f-string nem `%` de formatação montando SQL.
        for chamada in re.findall(r"cursor\.execute\((.*?)\)", texto, re.DOTALL):
            assert 'f"' not in chamada and "f'" not in chamada, caminho.name
            assert ".format(" not in chamada, caminho.name


# ── O hub aberto ────────────────────────────────────────────────────


TELAS_PESSOAIS = (
    "workspace:meu_dia",
    "workspace:notificacoes",
    "workspace:minhas_solicitacoes",
    "workspace:minhas_reservas",
    "workspace:correspondencias",
    "workspace:custodia",
    "workspace:estoque",
    "workspace:frota",
    "workspace:marketing",
    "workspace:aprovacoes",
    "workspace:fila",
    "workspace:pessoas",
    "workspace:relatorios",
    "workspace:documentos",
    "workspace:indicadores",
    "workspace:universidade",
    "workspace:universidade_painel",
)


@pytest.mark.parametrize("rota", TELAS_PESSOAIS)
def test_tela_pessoal_nao_abre_para_anonimo(client, rota):
    """O hub é aberto — a vitrine, a agenda, o acervo público. Nada do que é de
    UMA pessoa está nele."""
    resposta = client.get(reverse(rota))

    assert resposta.status_code in (302, 403), f"{rota} respondeu {resposta.status_code}"
    if resposta.status_code == 302:
        assert "/entrar/" in resposta["Location"], rota


def test_o_anonimo_nao_recebe_contador_de_ninguem(client):
    """O defeito na forma mais direta: `pessoa_da_requisicao()` devolve uma
    pessoa de REFERÊNCIA para calcular alcance, e usá-la para contar mostraria
    os números dela a quem nunca entrou."""
    from workspace.services import painel

    resposta = client.get(reverse("workspace:home"))

    assert resposta.context["eu"] is None
    assert resposta.context["nao_lidas"] == 0
    assert resposta.context["cards"] == painel.cards(dict(painel.SEM_SESSAO), resposta.context["total_servicos"])


# ── Público-alvo da publicação ──────────────────────────────────────
#
# O vazamento tinha duas metades e as duas vinham do mesmo comentário
# desatualizado. `indexar_publicacao` dizia "publicação não tem público-alvo
# ainda" e gravava `["*"]`; o campo nasceu no §9 e o comentário ficou. A home
# filtrava certo, e a BUSCA devolvia a todo mundo o comunicado endereçado a um
# departamento — inclusive a quem nunca entrou. O detalhe, por número na URL,
# fazia o resto.


@pytest.fixture
def comunicado_do_financeiro():
    from workspace.models.comunicacao import Publicacao

    financeiro = f.departamento("FIN", "Financeiro")
    outra = f.departamento("OPS", "Operações")
    publicacao = Publicacao.objects.create(
        titulo="Nova política de adiantamento", resumo="Só para o Financeiro.",
        publicado=True,
    )
    publicacao.departamentos.add(financeiro)
    return {"publicacao": publicacao, "financeiro": financeiro, "outra": outra}


def test_o_comunicado_segmentado_nao_aparece_na_busca_de_quem_nao_alcanca(
    client, comunicado_do_financeiro
):
    de_fora = f.pessoa("bruno")
    f.lotar(de_fora, dep=comunicado_do_financeiro["outra"])
    client.force_login(de_fora)

    corpo = client.get(reverse("workspace:buscar"), {"q": "adiantamento"}).content.decode()

    assert "Nova política de adiantamento" not in corpo


def test_o_comunicado_segmentado_aparece_para_quem_alcanca(
    client, comunicado_do_financeiro
):
    """Fechar a porta errada não pode fechar a porta para quem devia entrar."""
    de_dentro = f.pessoa("ana")
    f.lotar(de_dentro, dep=comunicado_do_financeiro["financeiro"])
    client.force_login(de_dentro)

    corpo = client.get(reverse("workspace:buscar"), {"q": "adiantamento"}).content.decode()

    assert "Nova política de adiantamento" in corpo


def test_o_anonimo_nao_encontra_comunicado_segmentado(client, comunicado_do_financeiro):
    corpo = client.get(reverse("workspace:buscar"), {"q": "adiantamento"}).content.decode()

    assert "Nova política de adiantamento" not in corpo


def test_o_detalhe_do_comunicado_respeita_o_publico_alvo(
    client, comunicado_do_financeiro
):
    """404 e não 403: dizer "existe, mas não é para você" já conta que existe um
    comunicado dirigido a outra área — e o título costuma ser a informação."""
    de_fora = f.pessoa("bruno")
    f.lotar(de_fora, dep=comunicado_do_financeiro["outra"])
    client.force_login(de_fora)
    url = reverse(
        "workspace:publicacao_detalhe", args=[comunicado_do_financeiro["publicacao"].pk]
    )

    assert client.get(url).status_code == 404


def test_o_detalhe_abre_para_quem_alcanca(client, comunicado_do_financeiro):
    de_dentro = f.pessoa("ana")
    f.lotar(de_dentro, dep=comunicado_do_financeiro["financeiro"])
    client.force_login(de_dentro)
    url = reverse(
        "workspace:publicacao_detalhe", args=[comunicado_do_financeiro["publicacao"].pk]
    )

    assert client.get(url).status_code == 200


def test_comunicado_sem_alvo_continua_alcancando_todo_mundo(client):
    """VAZIO significa a empresa inteira, e não ninguém: o contrário faria o
    comunicado que todos precisam ler ser o primeiro a desaparecer."""
    from workspace.models.comunicacao import Publicacao

    Publicacao.objects.create(titulo="Recesso de fim de ano", publicado=True)

    corpo = client.get(reverse("workspace:buscar"), {"q": "recesso"}).content.decode()

    assert "Recesso de fim de ano" in corpo


def test_mudar_o_publico_alvo_reindexa(client, comunicado_do_financeiro):
    """`post_save` não basta: o M2M é gravado DEPOIS do `save()`, então o índice
    guardaria o alcance anterior — que na criação é "nenhum alvo", ou seja, a
    empresa inteira."""
    publicacao = comunicado_do_financeiro["publicacao"]
    publicacao.departamentos.clear()

    corpo = client.get(reverse("workspace:buscar"), {"q": "adiantamento"}).content.decode()

    assert "Nova política de adiantamento" in corpo
