"""Acesso aberto do Workspace.

O produto não exige login. Algumas operações ainda precisam de uma pessoa no
banco por causa das FKs e das regras de permissão; em requisições anônimas,
usamos uma conta operacional existente do organograma.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.http import HttpRequest


def pessoa_da_requisicao(request: HttpRequest):
    """Pessoa efetiva para telas abertas.

    Se houver sessão autenticada, preserva a pessoa real. Sem sessão, usa a
    primeira conta ativa com lotação, que é criada pela massa inicial.
    """
    if getattr(request.user, "is_authenticated", False):
        return request.user

    User = get_user_model()
    pessoa = User.objects.filter(
        is_active=True, lotacao__isnull=False
    ).order_by("nome", "email").first()
    if pessoa is None:
        pessoa = User.objects.filter(is_active=True).order_by("email").first()
    if pessoa is None:
        pessoa = User.objects.create_user(
            "workspace-aberto@local",
            nome="Workspace Aberto",
        )
    return pessoa
