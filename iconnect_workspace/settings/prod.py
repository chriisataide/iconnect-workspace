"""Produção. PostgreSQL, HTTPS obrigatório, segredo vindo do ambiente."""

from __future__ import annotations

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import _env, _env_bool

DEBUG = False

# Falha ao subir, e não silenciosamente. Chave de desenvolvimento em produção é
# o defeito que ninguém percebe até alguém forjar uma sessão.
SECRET_KEY = _env("SECRET_KEY")
if not SECRET_KEY or SECRET_KEY.startswith("dev-only"):
    raise ImproperlyConfigured(
        "SECRET_KEY é obrigatória em produção e não pode ser a de desenvolvimento."
    )

if not ALLOWED_HOSTS:  # noqa: F405
    raise ImproperlyConfigured("ALLOWED_HOSTS é obrigatória em produção.")

if "*" in ALLOWED_HOSTS:  # noqa: F405
    # `*` desliga a checagem de Host. Com ela desligada, um atacante manda
    # `Host: servidor-dele.com` e o produto passa a gerar links absolutos
    # apontando para lá — é assim que um e-mail de recuperação legítimo entrega
    # o token para outra pessoa. E é o atalho que alguém aplica às três da
    # manhã, para o deploy parar de recusar a sonda do orquestrador.
    raise ImproperlyConfigured(
        "ALLOWED_HOSTS com `*` desliga a checagem de Host. Liste os domínios "
        "— e inclua o IP do contêiner se a sonda chegar por ele."
    )

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _env("POSTGRES_DB", "iconnect_workspace"),
        "USER": _env("POSTGRES_USER", "workspace"),
        "PASSWORD": _env("POSTGRES_PASSWORD"),
        "HOST": _env("POSTGRES_HOST", "localhost"),
        "PORT": _env("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": _env("REDIS_URL", "redis://127.0.0.1:6379/0"),
    }
}

# ── HTTPS ───────────────────────────────────────────────────────────

SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", True)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

SECURE_HSTS_SECONDS = 31_536_000  # um ano
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in _env("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()
]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
    },
}

# ── Logs em arquivo ─────────────────────────────────────────────────
#
# Só o terminal não guarda histórico: reiniciou o serviço, o erro de ontem
# sumiu. Os arquivos ficam em `/var/log/workspace`, ao lado dos logs do cron.
#
# `WatchedFileHandler` e não `TimedRotatingFileHandler`: são quatro workers do
# gunicorn, e cada um giraria o arquivo por conta própria, perdendo linhas. Aqui
# o Python só escreve; quem gira e apaga é o logrotate (`deploy/logrotate`), e o
# handler reabre o arquivo quando ele é trocado.
#
# Sem permissão de escrita na pasta, o portal sobe só com o terminal em vez de
# não subir: log é diagnóstico, e não pode ser a causa da queda.
LOG_DIR = Path(_env("LOG_DIR", "/var/log/workspace"))
try:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    _LOG_EM_ARQUIVO = os.access(LOG_DIR, os.W_OK)
except OSError:
    _LOG_EM_ARQUIVO = False


def _arquivo(nome: str, nivel: str) -> dict:
    return {
        "class": "logging.handlers.WatchedFileHandler",
        "filename": str(LOG_DIR / nome),
        "formatter": "padrao",
        "level": nivel,
        "encoding": "utf-8",
    }


_handlers = {"console": {"class": "logging.StreamHandler", "formatter": "padrao"}}
_geral, _seg = ["console"], ["console"]
if _LOG_EM_ARQUIVO:
    # `erros.log` pega WARNING para cima: os 500 com traceback (`django.request`)
    # e o aviso do agregador quando um bloco do Meu dia não foi desenhado.
    _handlers["erros"] = _arquivo("erros.log", "WARNING")
    # A trilha de segurança em arquivo próprio, com retenção própria.
    _handlers["seguranca"] = _arquivo("seguranca.log", "INFO")
    _geral, _seg = ["console", "erros"], ["console", "seguranca"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "padrao": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": _handlers,
    "root": {"handlers": _geral, "level": "INFO"},
    "loggers": {
        # O agregador degrada em silêncio quando um provider falha; o warning é
        # o único rastro de que um bloco do Meu dia não foi desenhado.
        "workspace": {"handlers": _geral, "level": "INFO", "propagate": False},
        # A TRILHA DE SEGURANÇA em fluxo próprio: entrada, saída, falha de
        # senha, bloqueio por tentativas, concessão e encerramento de papel.
        # Logger separado para que retenção e quem pode ler sejam outros.
        #
        # Ele nunca carrega senha, token nem segredo: ver `contas/auditoria.py`.
        "seguranca": {"handlers": _seg, "level": "INFO", "propagate": False},
    },
}
