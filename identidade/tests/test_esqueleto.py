"""Esqueleto do app IDN — ST-002 T1.

Aceite ①: o app carrega sem erro. Parece trivial, mas app registrado no
INSTALLED_APPS sem `migrations/__init__.py` quebra o `makemigrations` só quando
alguém adiciona o primeiro modelo — semanas depois, longe da causa.
"""

from __future__ import annotations

from pathlib import Path

from django.apps import apps


def test_app_registrado():
    config = apps.get_app_config("identidade")
    assert config.name == "identidade"
    assert config.verbose_name == "Identidade & Organização"


def test_pacote_de_migracoes_existe():
    raiz = Path(__file__).resolve().parent.parent
    assert (raiz / "migrations" / "__init__.py").exists()


def test_ainda_nao_ha_modelos():
    """IDN entra na Onda 1. Se este teste falhar, alguém adiantou ST-007+ —
    e aí precisa de migração, gate de cobertura e teste de isolamento de tenant.
    """
    assert list(apps.get_app_config("identidade").get_models()) == []
