"""Admin de IDN — onde a estrutura organizacional é mantida hoje.

O editor próprio de organograma é da Onda 1 (ST-017). O admin resolve agora e
continua de retaguarda depois.
"""

from __future__ import annotations

from django.contrib import admin

from .models import AtribuicaoPapel, Delegacao, Departamento, Lotacao, Papel, Unidade


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "sigla", "cidade", "estado", "ativa")
    list_filter = ("ativa", "estado")
    search_fields = ("codigo", "nome", "sigla")


@admin.register(Departamento)
class DepartamentoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "ativo")
    list_filter = ("ativo",)
    search_fields = ("codigo", "nome")


@admin.register(Lotacao)
class LotacaoAdmin(admin.ModelAdmin):
    list_display = ("user", "cargo", "unidade", "departamento", "gestor", "situacao")
    list_filter = ("situacao", "unidade", "departamento")
    search_fields = ("user__username", "user__nome", "user__email", "matricula", "cargo")
    autocomplete_fields = ("user", "gestor")
    list_select_related = ("user", "unidade", "departamento", "gestor")
    fieldsets = (
        (None, {"fields": ("user", "matricula", "cargo", "situacao", "data_admissao")}),
        (
            "Posição na empresa",
            {
                "fields": ("unidade", "departamento", "gestor", "centro_custo_codigo"),
                "description": (
                    "<b>gestor</b> define o escopo <code>equipe</code> — é o organograma. "
                    "Ciclo (A → B → A) é rejeitado."
                ),
            },
        ),
    )


@admin.register(Papel)
class PapelAdmin(admin.ModelAdmin):
    list_display = ("chave", "nome", "escopo_padrao", "qtd_permissoes", "ativo")
    list_filter = ("ativo", "escopo_padrao")
    search_fields = ("chave", "nome")
    prepopulated_fields = {"chave": ("nome",)}

    @admin.display(description="Permissões")
    def qtd_permissoes(self, obj: Papel) -> int:
        return len(obj.permissoes or [])


@admin.register(AtribuicaoPapel)
class AtribuicaoPapelAdmin(admin.ModelAdmin):
    list_display = (
        "user", "papel", "escopo", "unidade", "departamento",
        "vigencia_inicio", "vigencia_fim", "situacao",
    )
    list_filter = ("escopo", "papel", "unidade", "departamento")
    search_fields = ("user__username", "user__nome", "user__email")
    autocomplete_fields = ("user", "concedido_por")
    list_select_related = ("user", "papel", "unidade", "departamento")
    date_hierarchy = "vigencia_inicio"

    @admin.display(description="Vigente", boolean=True)
    def situacao(self, obj: AtribuicaoPapel) -> bool:
        return obj.vigente

    def save_model(self, request, obj, form, change):
        if obj.concedido_por_id is None:
            obj.concedido_por = request.user
        super().save_model(request, obj, form, change)


@admin.register(Delegacao)
class DelegacaoAdmin(admin.ModelAdmin):
    list_display = ("de_user", "para_user", "inicio", "fim", "ativa", "situacao")
    list_filter = ("ativa",)
    search_fields = ("de_user__username", "para_user__username")
    autocomplete_fields = ("de_user", "para_user")
    filter_horizontal = ("papeis",)
    fieldsets = (
        (None, {"fields": ("de_user", "para_user", "inicio", "fim", "motivo", "ativa")}),
        (
            "Papéis delegados",
            {
                "fields": ("papeis",),
                "description": (
                    "Vazio delega todos os papéis vigentes do delegante. "
                    "Delegação <b>nunca amplia</b>: o delegado recebe a interseção "
                    "com o que o delegante de fato tem hoje."
                ),
            },
        ),
    )

    @admin.display(description="Vigente", boolean=True)
    def situacao(self, obj: Delegacao) -> bool:
        return obj.vigente
