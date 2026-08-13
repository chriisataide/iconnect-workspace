"""Produção. PostgreSQL, HTTPS obrigatório, segredo vindo do ambiente."""

from __future__ import annotations

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

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "padrao": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "padrao"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        # O agregador degrada em silêncio quando um provider falha; o warning é
        # o único rastro de que um bloco do Meu dia não foi desenhado.
        "workspace": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
