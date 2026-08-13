"""Admin da conta.

Enxuto de propósito: papel e escopo NÃO se editam aqui — quem decide "pode?" é
`identidade`, com vigência. Um formulário de usuário que mostra permissões de
negócio convida a conceder acesso pelo lugar errado, sem data de fim e sem
trilha.
"""

from __future__ import annotations

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Pessoa


@admin.register(Pessoa)
class PessoaAdmin(UserAdmin):
    list_display = ("email", "nome", "is_active", "is_staff", "criado_em")
    list_filter = ("is_active", "is_staff")
    search_fields = ("email", "nome", "upn", "entra_oid")
    ordering = ("nome", "email")
    readonly_fields = ("criado_em", "last_login")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Pessoa", {"fields": ("nome",)}),
        (
            "Diretório corporativo",
            {
                "fields": ("entra_oid", "upn"),
                "description": (
                    "Preenchidos pelo SSO. <code>entra_oid</code> é a chave de "
                    "reconciliação — e-mail muda, ele não."
                ),
            },
        ),
        (
            "Acesso",
            {
                "fields": ("is_active", "is_staff", "is_superuser"),
                "description": (
                    "<strong>is_staff</strong> e <strong>is_superuser</strong> nunca "
                    "são derivados de atributo do diretório: são concessão explícita."
                ),
            },
        ),
        ("Datas", {"fields": ("last_login", "criado_em")}),
    )

    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "nome", "password1", "password2")}),
    )
