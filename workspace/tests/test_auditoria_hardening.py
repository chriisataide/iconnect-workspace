"""Os controles que a auditoria de segurança de agosto de 2026 acrescentou.

Cada teste aqui corresponde a um achado. O nome do teste é o achado; a
docstring é o risco. Se um deles ficar vermelho, o buraco voltou.

O que este arquivo NÃO cobre: o que já tinha guarda própria. CSP, CSRF, upload,
armazenamento privado e público-alvo estão em `test_auditoria_seguranca.py`
desde antes; IDOR e escalada de privilégio, em `test_auditoria_idor.py`.
"""

from __future__ import annotations

import logging

import pytest
from django.core.cache import cache
from django.urls import reverse

from identidade.tests import fabricas as f

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _cache_limpo():
    """O freio conta em cache, e o cache é do processo. Sem limpar, um teste
    herda as tentativas do anterior e o resultado depende da ordem."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def trilha():
    """As linhas do logger `seguranca`, capturadas.

    Fixture própria e não `caplog`: o logger tem `propagate: False` de
    propósito — a trilha de segurança vai para um fluxo separado, com retenção
    e acesso próprios —, e `caplog` escuta na raiz. Sem isto o teste passaria a
    depender de a trilha estar misturada com o resto, que é exatamente o que
    ela não deve estar.
    """

    class Coletor(logging.Handler):
        def __init__(self):
            super().__init__()
            self.linhas: list[str] = []

        def emit(self, registro):
            self.linhas.append(registro.getMessage())

        def __contains__(self, trecho):
            return any(trecho in linha for linha in self.linhas)

        def tudo(self) -> str:
            return " | ".join(self.linhas)

    logger = logging.getLogger("seguranca")
    coletor = Coletor()
    nivel = logger.level
    logger.addHandler(coletor)
    logger.setLevel(logging.INFO)
    try:
        yield coletor
    finally:
        logger.removeHandler(coletor)
        logger.setLevel(nivel)


@pytest.fixture
def staff(django_user_model):
    return django_user_model.objects.create_superuser(
        "chefe@icodev.com.br", password="senha-longa-de-teste-2026"
    )


# ── ALTA · o /admin/login/ não tinha freio ──────────────────────────


def test_o_admin_tambem_para_depois_de_errar_demais(client, staff, settings):
    """Era a porta sem tranca do produto.

    `/entrar/` barrava na sexta tentativa; `/admin/login/` aceitava vinte, todas
    com HTTP 200. E o admin é o alvo que vale mais: ele edita a base sem passar
    por regra de negócio, sem histórico e sem as permissões do produto.
    """
    settings.LOGIN_LIMITE_POR_CONTA = 3
    for _ in range(3):
        resposta = client.post(
            "/admin/login/", {"username": staff.email, "password": "errada"}
        )
        assert resposta.status_code == 200

    barrado = client.post(
        "/admin/login/", {"username": staff.email, "password": "errada"}
    )
    assert barrado.status_code == 429


def test_o_admin_bloqueado_nem_testa_a_senha_certa(client, staff, settings):
    """Sem isto, cada tentativa a mais custaria uma verificação de hash — que é
    lenta de propósito — e o freio viraria um jeito de gastar CPU do servidor."""
    settings.LOGIN_LIMITE_POR_CONTA = 2
    for _ in range(2):
        client.post("/admin/login/", {"username": staff.email, "password": "errada"})

    resposta = client.post(
        "/admin/login/",
        {"username": staff.email, "password": "senha-longa-de-teste-2026"},
    )

    assert resposta.status_code == 429
    assert "_auth_user_id" not in client.session


def test_o_admin_continua_deixando_entrar_quem_acerta(client, staff):
    """O freio não pode ter fechado a porta para quem tem a chave."""
    resposta = client.post(
        "/admin/login/",
        {"username": staff.email, "password": "senha-longa-de-teste-2026",
         "next": "/admin/"},
    )

    assert resposta.status_code == 302
    assert client.session.get("_auth_user_id")


def test_a_tela_do_admin_continua_sendo_a_do_admin(client):
    """A view é nossa; o template e o contexto continuam sendo do Django. Sem o
    `each_context`, a tela renderiza sem cabeçalho e sem título."""
    corpo = client.get("/admin/login/").content.decode()

    assert 'name="username"' in corpo
    assert 'name="csrfmiddlewaretoken"' in corpo


def test_toda_porta_de_senha_do_produto_tem_freio():
    """O GUARDA. Uma terceira porta de autenticação não pode nascer sem freio —
    foi exatamente assim que a do admin ficou de fora por uma onda inteira."""
    from django.contrib.auth.views import LoginView
    from django.urls import get_resolver

    from contas.entrada import ComFreio

    sem_freio = []
    for padrao in get_resolver().url_patterns:
        vista = getattr(padrao, "callback", None)
        classe = getattr(vista, "view_class", None)
        if classe is None or not issubclass(classe, LoginView):
            continue
        if not issubclass(classe, ComFreio):
            sem_freio.append(str(padrao.pattern))

    assert not sem_freio, (
        f"porta de senha sem contagem de tentativas: {sem_freio}"
    )


# ── MÉDIA · nenhum evento de segurança era registrado ───────────────


def test_a_entrada_deixa_rastro(client, pessoa, trilha):
    client.post(
        reverse("entrar"),
        {"username": pessoa.email, "password": "senha-de-teste-123"},
    )

    assert "entrada ok" in trilha
    assert pessoa.email in trilha.tudo()


def test_a_falha_de_senha_deixa_rastro(client, pessoa, trilha):
    """É o evento que se procura depois — e o que o freio barra em silêncio se
    ninguém registrar."""
    client.post(reverse("entrar"), {"username": pessoa.email, "password": "x"})

    assert "entrada falhou" in trilha


def test_o_bloqueio_deixa_rastro(client, pessoa, trilha, settings):
    """Cinco falhas é gente esquecendo a senha. Bloqueio repetido é alguém
    insistindo — e é uma linha diferente por isso."""
    settings.LOGIN_LIMITE_POR_CONTA = 1
    client.post(reverse("entrar"), {"username": pessoa.email, "password": "x"})
    client.post(reverse("entrar"), {"username": pessoa.email, "password": "x"})

    assert "entrada bloqueada" in trilha
    assert "porta=/entrar/" in trilha.tudo()


def test_o_rastro_nunca_carrega_a_senha(client, pessoa, trilha):
    """A regra que não se quebra. Um log de segurança que vaza credencial é uma
    segunda cópia do problema que ele deveria ajudar a investigar."""
    senha = "uma-senha-muito-particular-987"

    client.post(reverse("entrar"), {"username": pessoa.email, "password": senha})
    client.post(
        reverse("entrar"),
        {"username": pessoa.email, "password": "senha-de-teste-123"},
    )

    assert senha not in trilha.tudo()
    assert "senha-de-teste-123" not in trilha.tudo()


def test_conceder_papel_deixa_rastro(trilha):
    """Mudar o alcance de alguém é a alteração que ninguém vê acontecer e que
    muda o que essa pessoa alcança no dia seguinte."""
    from identidade.services import administracao as adm

    rh, alvo = f.pessoa("rh"), f.pessoa("alvo")
    f.lotar(rh)
    f.lotar(alvo)
    f.atribuir(rh, f.papel("rh-admin", ["rh.admin.global"], escopo="global"))
    papel = f.papel("compras", ["com.aprovar.unidade"], escopo="unidade")

    adm.conceder(
        pessoa=alvo, papel=papel, escopo="unidade", quem=rh,
        justificativa="responde por compras da base",
    )

    assert "papel concedido" in trilha
    assert alvo.email in trilha.tudo()
    assert f"por={rh.email}" in trilha.tudo()


# ── MÉDIA · a sessão durava duas semanas ────────────────────────────


def test_a_sessao_nao_dura_duas_semanas():
    """O padrão do Django é catorze dias absolutos. Numa estação de obra ou
    numa recepção, é uma sessão viva por duas semanas depois de a pessoa ir
    embora — e o que ela abre é atestado, comprovante e bandeja."""
    from django.conf import settings

    assert settings.SESSION_COOKIE_AGE <= 24 * 60 * 60
    assert settings.SESSION_SAVE_EVERY_REQUEST is True, (
        "sem isto o prazo conta desde o login e expulsa quem está digitando"
    )


def test_os_limites_de_upload_sao_explicitos():
    """Padrão do framework muda entre versões. Upload sem teto é disco cheio —
    que derruba o produto sem precisar de falha de código nenhuma."""
    from django.conf import settings

    assert settings.DATA_UPLOAD_MAX_MEMORY_SIZE <= 10 * 1024 * 1024
    assert settings.DATA_UPLOAD_MAX_NUMBER_FIELDS <= 5_000
    assert settings.DATA_UPLOAD_MAX_NUMBER_FILES <= 100


# ── MÉDIA · o IP atrás de proxy trancava a empresa inteira ──────────


def test_sem_proxy_configurado_o_cabecalho_e_ignorado(rf, settings):
    """O padrão é ZERO, e é o comportamento seguro: `X-Forwarded-For` é escrito
    pelo cliente, e confiar nele zeraria a contagem por origem a cada tentativa.
    """
    from contas.entrada import ip_de

    settings.PROXIES_CONFIAVEIS = 0
    requisicao = rf.post("/entrar/", HTTP_X_FORWARDED_FOR="1.2.3.4", REMOTE_ADDR="10.0.0.1")

    assert ip_de(requisicao) == "10.0.0.1"


def test_com_um_proxy_le_o_endereco_que_o_proxy_escreveu(rf, settings):
    """Atrás de um balanceador toda a empresa chega com o mesmo `REMOTE_ADDR`,
    e vinte senhas erradas de vinte pessoas trancariam o produto para todos."""
    from contas.entrada import ip_de

    settings.PROXIES_CONFIAVEIS = 1
    requisicao = rf.post(
        "/entrar/", HTTP_X_FORWARDED_FOR="200.1.1.1", REMOTE_ADDR="10.0.0.1"
    )

    assert ip_de(requisicao) == "200.1.1.1"


def test_o_que_o_cliente_inventa_fica_a_esquerda_e_e_ignorado(rf, settings):
    """A prova de que a leitura por posição não é falsificável: o proxy
    ACRESCENTA à direita, então o que o atacante escreveu sobra atrás."""
    from contas.entrada import ip_de

    settings.PROXIES_CONFIAVEIS = 1
    requisicao = rf.post(
        "/entrar/",
        HTTP_X_FORWARDED_FOR="9.9.9.9, 200.1.1.1",
        REMOTE_ADDR="10.0.0.1",
    )

    assert ip_de(requisicao) == "200.1.1.1"


# ── MÉDIA · a ponte SSO guardava token sem rotacionar a sessão ──────


def test_a_ponte_sso_rotaciona_a_chave_da_sessao(rf, settings, monkeypatch):
    """É a única coisa do produto que põe credencial de terceiro numa sessão
    sem passar por `login()` — e é `login()` que normalmente rotaciona, contra
    fixação de sessão."""
    from django.contrib.sessions.middleware import SessionMiddleware

    from workspace.integracoes import sessao as pnt

    settings.ICONNECT_API_URL = "https://exemplo.invalido"
    monkeypatch.setattr(
        pnt, "_post_sem_token", lambda *a, **k: {"access": "jwt-de-teste"}
    )

    requisicao = rf.get("/workspace/")
    SessionMiddleware(lambda r: None).process_request(requisicao)
    requisicao.session.save()
    antes = requisicao.session.session_key

    assert pnt.trocar_codigo(requisicao, "codigo-valido") is True
    assert requisicao.session.session_key != antes
    assert requisicao.session[pnt.CHAVE_ACCESS] == "jwt-de-teste"


# ── BAIXA · escopo inválido entrava no banco ────────────────────────


def test_escopo_invalido_e_recusado_em_vez_de_gravado():
    """`choices` num `CharField` não é validado no `save()`. Um escopo digitado
    errado entrava, não alcançava ninguém (`abrangencia()` devolve -1) e o R.H.
    via "papel concedido" com a pessoa continuando sem acesso."""
    from identidade.services import administracao as adm
    from identidade.services.administracao import AdministracaoError

    rh, alvo = f.pessoa("rh"), f.pessoa("alvo")
    f.lotar(rh)
    f.lotar(alvo)
    f.atribuir(rh, f.papel("rh-admin", ["rh.admin.global"], escopo="global"))
    papel = f.papel("compras", ["com.aprovar.unidade"], escopo="unidade")

    with pytest.raises(AdministracaoError, match="Escopo inválido"):
        adm.conceder(pessoa=alvo, papel=papel, escopo="Global", quem=rh,
                     justificativa="tanto faz")


# ── BAIXA · faltava Cross-Origin-Resource-Policy ────────────────────


def test_o_cabecalho_isola_os_recursos_de_outra_origem(client):
    """`frame-ancestors` e `X-Frame-Options` cobrem o enquadramento da PÁGINA.
    Este cobre os recursos — é o que barra uma página de fora puxar um anexo no
    navegador de quem está com a sessão aberta."""
    resposta = client.get(reverse("workspace:home"))

    assert resposta["Cross-Origin-Resource-Policy"] == "same-origin"


# ── §2 e §20 · segredos e o que não pode ser versionado ─────────────


def test_o_gitignore_barra_env_e_chave_privada():
    """O modo normal de vazar chave não é ataque: é um `git add .` num
    diretório onde alguém deixou uma. O `.gitignore` é o que transforma esse
    descuido em nada."""
    from pathlib import Path

    regras = Path(".gitignore").read_text().splitlines()
    for obrigatoria in (".env", "*.pem", "*.key", "id_rsa"):
        assert obrigatoria in regras, f"{obrigatoria} não está no .gitignore"
    assert "!.env.example" in regras, (
        "o exemplo PRECISA ser versionado — é onde as variáveis são documentadas"
    )


def test_o_exemplo_de_ambiente_nao_tem_valor_real():
    """`.env.example` é versionado de propósito. Um valor real dentro dele é um
    segredo commitado com a bênção de todo mundo."""
    from pathlib import Path

    linhas = [
        linha.strip()
        for linha in Path(".env.example").read_text().splitlines()
        if linha.strip() and not linha.strip().startswith("#") and "=" in linha
    ]
    sensiveis = ("SECRET_KEY", "POSTGRES_PASSWORD", "WORKSPACE_SHARED_SECRET",
                 "CONTA_BANCARIA_EMPRESA")
    for linha in linhas:
        chave, _, valor = linha.partition("=")
        if chave in sensiveis:
            assert valor == "", f"{chave} tem valor no .env.example"


def test_toda_variavel_lida_pelo_settings_esta_documentada():
    """O GUARDA contra a variável que nasce sem ninguém saber.

    Uma configuração nova lida por `_env()` e ausente do exemplo é uma pergunta
    que só aparece no dia do deploy — e a resposta costuma ser o padrão, que
    para segurança é quase sempre o valor errado.
    """
    import re
    from pathlib import Path

    settings = "\n".join(
        Path(f"iconnect_workspace/settings/{nome}.py").read_text()
        for nome in ("base", "prod", "dev")
    )
    lidas = set(re.findall(r'_env(?:_bool)?\(\s*"([A-Z_]+)"', settings))
    documentadas = set(
        re.findall(r"(?m)^([A-Z_]+)=", Path(".env.example").read_text())
    )

    faltando = sorted(lidas - documentadas)
    assert not faltando, f"variável lida pelo settings e não documentada: {faltando}"


# ── Produção: o atalho das três da manhã ────────────────────────────


def test_producao_recusa_allowed_hosts_curinga(monkeypatch):
    """`*` desliga a checagem de Host, e o efeito aparece longe: o produto passa
    a gerar link absoluto para o domínio que o atacante mandou.

    É o atalho que alguém aplica quando o deploy recusa a sonda do orquestrador
    — e que ninguém desfaz depois.
    """
    import importlib

    from django.core.exceptions import ImproperlyConfigured

    monkeypatch.setenv("SECRET_KEY", "uma-chave-longa-de-producao-de-verdade")
    monkeypatch.setenv("ALLOWED_HOSTS", "*")
    importlib.reload(importlib.import_module("iconnect_workspace.settings.base"))

    with pytest.raises(ImproperlyConfigured, match=r"\*"):
        importlib.reload(importlib.import_module("iconnect_workspace.settings.prod"))
