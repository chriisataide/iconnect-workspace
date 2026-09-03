"""Admin de finanças — onde o orçamento do mês é definido."""

from __future__ import annotations

from django.contrib import admin

from .models import (
    CentroCusto,
    Lancamento,
    LinhaOrcamento,
    OrcamentoAnual,
    RevisaoOrcamento,
)


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


# ── Orçamento anual ─────────────────────────────────────────────────


class LinhaOrcamentoInline(admin.TabularInline):
    """As doze linhas se editam DENTRO do ano.

    Numa tela própria, as linhas de trinta centros de custo apareceriam
    misturadas — e o orçamento anual é justamente o agrupamento.
    """

    model = LinhaOrcamento
    extra = 0
    fields = ("mes", "valor")


class RevisaoOrcamentoInline(admin.TabularInline):
    """As revisões. Somente leitura: revisar é um ATO, e o ato mora na tela.

    Editável aqui, a revisão viraria o jeito de mudar o teto sem motivo nem
    autor — que é exatamente o que o ADR-037 existe para impedir.
    """

    model = RevisaoOrcamento
    extra = 0
    can_delete = False
    fields = ("numero", "criada_em", "autor", "motivo", "deltas")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(OrcamentoAnual)
class OrcamentoAnualAdmin(admin.ModelAdmin):
    """O teto de um centro de custo num ano.

    `situacao`, `vigorou_por` e `vigorou_em` são somente leitura: pôr em vigor é
    um ato, e ele acontece na tela. Mudar a situação aqui permitiria devolver um
    orçamento vigente ao rascunho e reescrever o ano sem revisão nenhuma — o
    caminho exato que esta onda fechou.

    As LINHAS continuam editáveis: montar o rascunho pelo `/admin/` é legítimo,
    e o `save` do inline não passa a valer sozinho — enquanto a situação for
    rascunho, a bandeja usa o teto avulso do centro de custo.
    """

    list_display = ("centro_custo", "ano", "situacao", "total", "vigorou_em")
    list_filter = ("situacao", "ano")
    search_fields = ("centro_custo__codigo", "centro_custo__nome")
    readonly_fields = ("situacao", "vigorou_por", "vigorou_em", "criado_em")
    inlines = (LinhaOrcamentoInline, RevisaoOrcamentoInline)

    @admin.display(description="total do ano")
    def total(self, obj) -> str:
        return f"R$ {obj.total}"
