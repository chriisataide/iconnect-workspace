"""Admin do Workspace — é aqui que Comunicados e Notícias são alimentados.

`/admin/workspace/publicacao/`
"""

from __future__ import annotations

from django.contrib import admin, messages
from django.utils import timezone

from .models import Publicacao


@admin.register(Publicacao)
class PublicacaoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "tipo", "prioridade", "fixado", "publicado", "publicar_em", "situacao")
    list_filter = ("tipo", "publicado", "prioridade", "fixado")
    search_fields = ("titulo", "resumo", "corpo")
    date_hierarchy = "publicar_em"
    list_per_page = 30
    actions = ("publicar_agora", "despublicar")

    fieldsets = (
        (None, {"fields": ("tipo", "titulo", "resumo", "corpo")}),
        ("Destaque", {"fields": ("prioridade", "fixado")}),
        (
            "Publicação",
            {
                "fields": ("publicado", "publicar_em", "expira_em"),
                "description": (
                    "O card do Portal só mostra o que está <b>publicado</b>, com "
                    "<b>publicar em</b> no passado e ainda dentro da validade."
                ),
            },
        ),
        ("Auditoria", {"fields": ("autor", "criado_em", "atualizado_em"), "classes": ("collapse",)}),
    )
    readonly_fields = ("criado_em", "atualizado_em")

    @admin.display(description="No ar")
    def situacao(self, obj: Publicacao) -> str:
        if obj.no_ar:
            return "✅ no ar"
        if not obj.publicado:
            return "— rascunho"
        if obj.publicar_em > timezone.now():
            return "🕒 agendado"
        return "⌛ expirado"

    def save_model(self, request, obj, form, change):
        if obj.autor_id is None:
            obj.autor = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="Publicar agora")
    def publicar_agora(self, request, queryset):
        n = queryset.update(publicado=True, publicar_em=timezone.now())
        self.message_user(request, f"{n} publicação(ões) no ar.", messages.SUCCESS)

    @admin.action(description="Despublicar")
    def despublicar(self, request, queryset):
        n = queryset.update(publicado=False)
        self.message_user(request, f"{n} publicação(ões) fora do ar.", messages.WARNING)
