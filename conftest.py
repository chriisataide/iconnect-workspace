"""
conftest.py — Fixtures reutilizáveis para pytest no projeto iConnect
"""

import pytest
from django.contrib.auth.models import User

from dashboard.models import (
    CategoriaTicket,
    Cliente,
    PrioridadeTicket,
    StatusTicket,
    Ticket,
)


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
