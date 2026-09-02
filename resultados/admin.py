"""O espelho no `/admin/` — visível e **somente leitura**.

Editável, ele produziria duas verdades sobre a mesma linha: a do sistema de
origem e a de quem editou aqui. A segunda venceria até a próxima carga, ou não
venceria, dependendo da precedência — e as duas hipóteses são ruins.

Visível porque a pergunta "esse número está mesmo no espelho?" precisa de
resposta antes de a tela de fontes existir (Onda 3), e o caminho hoje é este.
"""

from __future__ import annotations

from django.contrib import admin

from .models import (
    Apontamento,
    AvaliacaoCliente,
    CompetenciaResultado,
    Contrato,
    MarcoProjeto,
    Projeto,
    QuadroPessoas,
)

PROCEDENCIA = ("fonte", "chave_externa", "carga_id", "importado_em", "hash_conteudo")


class SomenteLeitura(admin.ModelAdmin):
    """Nem criar, nem editar, nem apagar. O dado nasce onde é operado."""

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        # Apagar à mão deixaria o espelho e a origem em desacordo até alguém
        # reparar — e a próxima carga traria a linha de volta, o que faria a
        # exclusão parecer um bug do produto.
        return False


@admin.register(Contrato)
class ContratoAdmin(SomenteLeitura):
    list_display = ("codigo", "nome_cliente", "servico", "centro_custo",
                    "regional", "status", "fim_vigencia", "fonte")
    list_filter = ("fonte", "status", "servico", "regional")
    search_fields = ("codigo", "nome_cliente", "centro_custo")
    readonly_fields = PROCEDENCIA


@admin.register(CompetenciaResultado)
class CompetenciaAdmin(SomenteLeitura):
    list_display = ("__str__", "ano", "mes", "centro_custo", "receita_bruta",
                    "margem_contribuicao", "ebitda", "fonte")
    list_filter = ("fonte", "ano", "mes")
    search_fields = ("centro_custo", "contrato__codigo")
    readonly_fields = PROCEDENCIA


@admin.register(Projeto)
class ProjetoAdmin(SomenteLeitura):
    list_display = ("codigo", "nome", "situacao", "responsavel", "prazo",
                    "bloqueado", "fonte")
    list_filter = ("fonte", "situacao", "bloqueado")
    search_fields = ("codigo", "nome", "responsavel")
    readonly_fields = PROCEDENCIA


@admin.register(MarcoProjeto)
class MarcoAdmin(SomenteLeitura):
    list_display = ("titulo", "projeto", "prazo", "concluido_em", "fonte")
    list_filter = ("fonte",)
    readonly_fields = PROCEDENCIA


@admin.register(QuadroPessoas)
class QuadroAdmin(SomenteLeitura):
    list_display = ("centro_custo", "ano", "mes", "efetivo_ativo",
                    "turnover_pct", "absenteismo_pct", "fonte")
    list_filter = ("fonte", "ano", "mes")
    readonly_fields = PROCEDENCIA


@admin.register(Apontamento)
class ApontamentoAdmin(SomenteLeitura):
    list_display = ("centro_custo", "ano", "mes", "horas_normais", "he_total",
                    "he_ineficiencia", "fonte")
    list_filter = ("fonte", "ano", "mes")
    readonly_fields = PROCEDENCIA


@admin.register(AvaliacaoCliente)
class AvaliacaoAdmin(SomenteLeitura):
    """O comentário aparece; quem escreveu não existe no model.

    Quem respondeu é pessoa do cliente, e o Workspace não é dono desse cadastro.
    """

    list_display = ("contrato", "data", "nota", "classificacao",
                    "tratativa_aberta", "fonte")
    list_filter = ("fonte", "classificacao", "tratativa_aberta")
    readonly_fields = PROCEDENCIA
