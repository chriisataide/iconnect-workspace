"""Configuração comum do iConnect Workspace.

## Por que este projeto existe separado do iConnect Platform

São dois produtos. O Workspace organiza a vida corporativa da empresa; o
iConnect Platform organiza a operação de atendimento aos clientes. A ligação
entre eles é **um link** — o tile do launcher, em `ICONNECT_URL` — e nada mais:
não há banco compartilhado, sessão compartilhada nem tabela de usuários
compartilhada.

Essa separação não é estética. No projeto anterior os dois dividiam uma
`auth.User` e um cookie de sessão, e a consequência era concreta: uma conta
criada pelo Workspace passava a valer no iConnect, onde "usuário sem papel
definido" era tratado como analista. Aqui isso é impossível por construção, e
não por disciplina.

## O que a separação nos deu de imediato

CSP **estrita**. O iConnect precisa de `unsafe-inline` em `style-src` porque usa
`style=` em escala; o Workspace tem zero estilo inline, garantido por teste. Nos
dois no mesmo processo, o header era o do denominador comum e o Workspace pagava
a dívida do outro sem colher o benefício. Ver `SEGURANCA_CSP` abaixo.
"""

from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def _env(chave: str, default: str = "") -> str:
    return os.environ.get(chave, default)


def _env_bool(chave: str, default: bool = False) -> bool:
    bruto = os.environ.get(chave)
    if bruto is None:
        return default
    return bruto.strip().lower() in ("1", "true", "yes", "on", "sim")


# ── Identidade do projeto ───────────────────────────────────────────

SECRET_KEY = _env("SECRET_KEY", "dev-only-nao-usar-em-producao")
DEBUG = False
ALLOWED_HOSTS: list[str] = [
    h.strip() for h in _env("ALLOWED_HOSTS", "").split(",") if h.strip()
]

# ── Apps ────────────────────────────────────────────────────────────

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Conta da pessoa. App separado de `identidade` de propósito: o modelo de
    # usuário tem de existir ANTES da FK de `Lotacao`, e manter os dois no mesmo
    # app criaria um ciclo no grafo de migração daquele app.
    "contas",
    # IDN — organograma, papel com escopo e vigência. Raiz da dependência:
    # só conhece o modelo de usuário.
    "identidade",
    # WKS — a superfície e os motores do Workspace. Folha: ninguém importa dele.
    "workspace",
    # Domínio de orçamento. Implementa o contrato `workspace.providers.orcamento`
    # e se registra no `ready()` — é o que mantém a barra tripla da bandeja de
    # aprovação viva depois que `CentroCusto` deixou de morar no iConnect.
    "financas",
]

# A conta nasce do SSO (ADR-013). O identificador é o e-mail corporativo, e não
# um `username` digitado — ver `contas/models.py`.
AUTH_USER_MODEL = "contas.Pessoa"

# ── Middleware ──────────────────────────────────────────────────────

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Cabeçalhos de segurança, com a CSP estrita. Nosso, e não de biblioteca:
    # são 40 linhas cuja razão de existir é ser explícita e testada.
    "iconnect_workspace.seguranca.CabecalhosDeSeguranca",
]

ROOT_URLCONF = "iconnect_workspace.urls"
WSGI_APPLICATION = "iconnect_workspace.wsgi.application"
ASGI_APPLICATION = "iconnect_workspace.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.i18n",
                # Os contadores do rail e do sino. Context processor e não
                # variável por view: a casca está em todas as telas, e depender
                # de cada view lembrar garante que uma esqueça — foi exatamente
                # assim que a topbar já perdeu o sino uma vez.
                "workspace.context.rail",
            ],
        },
    },
]

# ── Banco ───────────────────────────────────────────────────────────

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Autenticação ────────────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── Internacionalização ─────────────────────────────────────────────

# pt-BR e não en-us: a home escreve "Sexta-feira, 7 de agosto" com
# `formats.date_format`, que depende do locale do Django. Trocar isto quebra a
# data da home e a pluralização dos contadores.
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# ── Arquivos ────────────────────────────────────────────────────────

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Anexos do Workspace moram FORA de `MEDIA_ROOT`, e isto é uma regra de
# segurança, não organização de pasta: servidor web serve `MEDIA_ROOT` como
# arquivo estático, sem passar por view nenhuma — foi assim que, no projeto
# anterior, o nginx expôs `/media/` sem autenticação. Aqui o único caminho até
# um anexo é `workspace:baixar_anexo`, que autoriza antes de entregar.
# Há teste que falha se este caminho cair dentro de `MEDIA_ROOT`.
ARQUIVOS_PRIVADOS_ROOT = Path(
    _env("ARQUIVOS_PRIVADOS_ROOT", str(BASE_DIR / "arquivos_privados"))
)

# ── Segurança ───────────────────────────────────────────────────────

# CSP sem `unsafe-inline` em nenhuma diretiva. O Workspace não tem um único
# `style=` nem `onclick=` — há teste que verifica —, então a política estrita
# não exige nonce e não tem exceção para manter.
SEGURANCA_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "object-src 'none'"
)

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
X_FRAME_OPTIONS = "DENY"

# Cookie com nome próprio. Se um dia os dois produtos servirem do mesmo domínio,
# é isto que impede a sessão de um valer no outro.
SESSION_COOKIE_NAME = "wks_sessao"
CSRF_COOKIE_NAME = "wks_csrf"

# ── A única ligação com o iConnect Platform ─────────────────────────

# Um link, e nada mais. É o destino do tile no launcher da home; não há API,
# banco ou sessão em comum. Mudou o endereço do iConnect? Muda esta variável.
ICONNECT_URL = _env("ICONNECT_URL", "https://app.icodev.com.br/login/")
