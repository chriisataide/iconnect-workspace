"""Desenvolvimento e teste. SQLite, DEBUG ligado, sem HTTPS."""

from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", "testserver"]

# LocMemCache: o `rail` faz COUNT por requisição e não precisa de Redis para
# desenvolver. Produção usa o cache real.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# E-mail no console — nada sai da máquina durante desenvolvimento.
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# O tile do iConnect em desenvolvimento aponta para o ambiente de homologação,
# não para produção: clicar num tile de teste e cair no sistema real dos
# clientes é o tipo de acidente que não avisa antes.
ICONNECT_URL = "http://127.0.0.1:8000/login/"

# A trilha de segurança também aparece em desenvolvimento. Sem isto ela só
# existiria em produção — e uma trilha que ninguém vê durante o desenvolvimento
# é uma trilha que ninguém percebe quando para de funcionar.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {
        "seguranca": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
