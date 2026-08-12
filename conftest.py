"""
conftest.py — Fixtures reutilizáveis para pytest no projeto iConnect
"""

import django
from django.conf import settings

# Desabilita Axes durante testes para evitar AxesBackendRequestParameterRequired
settings.AXES_ENABLED = False
settings.AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
]

# Desabilita o enforcement de MFA nos testes (o comportamento é verificado
# separadamente). Sem isto, views autenticadas como admin/gerente redirecionam
# para o cadastro de 2FA e retornam 302 em vez de 200.
settings.MFA_ENFORCE = False

# Chave Fernet dedicada para testes. Sem ela, com DEBUG=False, TODO teste que
# cifra PII/segredos (Fornecedor, PontoDeVenda, Webhook, SSO, AIConfiguration...)
# falha com ImproperlyConfigured. Só define se o ambiente não trouxe a sua
# (CI injeta via env); assim `pytest` roda em qualquer máquina sem setup manual.
if not getattr(settings, "FIELD_ENCRYPTION_KEY", None):
    settings.FIELD_ENCRYPTION_KEY = "wOCJ81ziK2GZoSdzQogPIT_sB5Q-IAZdOYxe23_1R2U="

import pytest
from django.contrib.auth.models import User

from dashboard.models import (
    CategoriaTicket,
    Cliente,
    PrioridadeTicket,
    StatusTicket,
    Ticket,
)


@pytest.fixture(autouse=True)
def _clear_cache_between_tests():
    """Limpa o cache antes de cada teste.

    O throttling do DRF guarda o histórico de requisições no cache; sem limpar,
    o contador acumula entre testes e endpoints como /health/ e /auth/jwt/
    passam a retornar 429 dependendo da ordem/volume de testes (flaky).
    """
    from django.core.cache import cache

    cache.clear()
    yield


@pytest.fixture(autouse=True)
def _anexos_em_diretorio_temporario(tmp_path, settings):
    """Anexos do Portal nunca escrevem no repositório.

    `ARQUIVOS_PRIVADOS_ROOT` aponta para `BASE_DIR/arquivos_privados` em
    produção. Sem este autouse, qualquer teste que crie um `Anexo` — inclusive
    um teste de outro app, que nem sabe que anexo existe — deixa comprovantes de
    mentira dentro do projeto. Aconteceu na primeira execução: 34 JPEGs.

    Autouse e não fixture opt-in de propósito: quem esquece de pedir a fixture é
    exatamente quem não sabia que precisava dela.
    """
    settings.ARQUIVOS_PRIVADOS_ROOT = tmp_path / "arquivos_privados"
    return settings.ARQUIVOS_PRIVADOS_ROOT


@pytest.fixture
def user(db):
    """Cria um usuário padrão para testes."""
    return User.objects.create_user(
        username="testuser",
        password="testpass123",
        email="testuser@test.com",
    )


@pytest.fixture
def admin_user(db):
    """Cria um superusuário para testes."""
    return User.objects.create_superuser(
        username="admin",
        password="admin123",
        email="admin@test.com",
    )


@pytest.fixture
def staff_user(db):
    """Cria um usuário staff (supervisor) para testes."""
    return User.objects.create_user(
        username="staffuser",
        password="testpass123",
        email="staff@test.com",
        is_staff=True,
    )


@pytest.fixture
def cliente(db):
    """Cria um cliente padrão para testes."""
    return Cliente.objects.create(
        nome="Cliente Teste",
        email="cliente@test.com",
    )


@pytest.fixture
def categoria(db):
    """Cria uma categoria de ticket para testes."""
    return CategoriaTicket.objects.create(
        nome="Suporte Técnico",
        descricao="Categoria de suporte técnico geral",
        cor="#007bff",
    )


@pytest.fixture
def ticket(db, cliente, user, categoria):
    """Cria um ticket básico para testes."""
    return Ticket.objects.create(
        titulo="Ticket de Teste",
        descricao="Descrição do ticket de teste",
        cliente=cliente,
        agente=user,
        categoria=categoria,
        status=StatusTicket.ABERTO,
        prioridade=PrioridadeTicket.MEDIA,
    )


@pytest.fixture
def ticket_resolvido(db, cliente, user, categoria):
    """Cria um ticket já resolvido para testes."""
    return Ticket.objects.create(
        titulo="Ticket Resolvido",
        descricao="Ticket já resolvido",
        cliente=cliente,
        agente=user,
        categoria=categoria,
        status=StatusTicket.RESOLVIDO,
        prioridade=PrioridadeTicket.BAIXA,
    )


@pytest.fixture
def api_client():
    """Cria um APIClient do DRF."""
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def authenticated_api_client(api_client, user):
    """Cria um APIClient já autenticado."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def admin_api_client(api_client, admin_user):
    """Cria um APIClient autenticado como admin."""
    api_client.force_authenticate(user=admin_user)
    return api_client
