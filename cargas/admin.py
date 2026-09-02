"""As cargas no `/admin/`.

`FonteDados` e `RegraPrecedencia` são EDITÁVEIS — são configuração de operação,
e mudar a cadência ou a precedência não pode exigir deploy. `ExecucaoCarga` e
`Divergencia` são somente leitura: são registro do que aconteceu, e registro
editável não é registro.
"""

from __future__ import annotations

from django.contrib import admin

from .models import Divergencia, ExecucaoCarga, FonteDados, RegraPrecedencia


@admin.register(FonteDados)
class FonteAdmin(admin.ModelAdmin):
    list_display = ("nome", "chave", "ativa", "cadencia_esperada",
                    "idade_maxima_aceitavel", "responsavel_tecnico")
    list_filter = ("ativa",)


@admin.register(RegraPrecedencia)
class PrecedenciaAdmin(admin.ModelAdmin):
    list_display = ("entidade", "campo", "fonte_vencedora", "ordem", "ativa")
    list_filter = ("entidade", "fonte_vencedora", "ativa")


class SomenteLeitura(admin.ModelAdmin):
    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


@admin.register(ExecucaoCarga)
class ExecucaoAdmin(SomenteLeitura):
    list_display = ("fonte", "iniciada_em", "status", "lidos", "criados",
                    "atualizados", "ignorados", "rejeitados", "simulacao")
    list_filter = ("fonte", "status", "simulacao")
    date_hierarchy = "iniciada_em"


@admin.register(Divergencia)
class DivergenciaAdmin(SomenteLeitura):
    list_display = ("entidade", "campo", "chave_externa", "fonte_a", "valor_a",
                    "fonte_b", "valor_b", "fonte_vencedora", "resolvida_em")
    list_filter = ("entidade", "fonte_a", "fonte_b")
    # Marcar como resolvida É uma ação de gente — a única escrita permitida aqui.
    def has_change_permission(self, request, obj=None) -> bool:
        return True

    readonly_fields = ("entidade", "chave_externa", "campo", "fonte_a", "valor_a",
                       "fonte_b", "valor_b", "fonte_vencedora", "detectada_em", "carga")
