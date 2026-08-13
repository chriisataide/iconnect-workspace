"""Admin de finanças — onde o orçamento do mês é definido."""

from __future__ import annotations

from django.contrib import admin

from .models import CentroCusto, Lancamento


@admin.register(CentroCusto)
class CentroCustoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "orcamento_mensal", "ativo")
    list_filter = ("ativo",)
    search_fields = ("codigo", "nome")
    ordering = ("codigo",)


@admin.register(Lancamento)
class LancamentoAdmin(admin.ModelAdmin):
    list_display = ("centro_custo", "valor", "competencia", "descricao")
    list_filter = ("competencia", "centro_custo")
    search_fields = ("centro_custo__codigo", "descricao")
    date_hierarchy = "competencia"
