"""Admin do Workspace.

    /admin/workspace/publicacao/   Comunicados e Notícias
    /admin/workspace/regraaprovacao/   os tetos da cadeia de aprovação
    /admin/workspace/solicitacaoaprovacao/   auditoria das decisões
"""

from __future__ import annotations

from django.contrib import admin, messages
from django.utils import timezone

from .models import (
    Compromisso,
    ItemCatalogo,
    EtapaAprovacao,
    Publicacao,
    RegraAprovacao,
    SolicitacaoAprovacao,
    SolicitacaoServico,
)


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


@admin.register(RegraAprovacao)
class RegraAprovacaoAdmin(admin.ModelAdmin):
    """Onde os tetos de aprovação são configurados.

    São dados, não código, porque a pergunta "qual o teto por nível?" ainda não
    foi respondida — e chutar em código significaria refatorar depois.
    """

    list_display = ("dominio", "valor_minimo", "tipo", "papel", "aprovador", "ordem", "ativa")
    list_filter = ("dominio", "tipo", "ativa")
    ordering = ("dominio", "ordem", "valor_minimo")
    autocomplete_fields = ("aprovador",)
    fieldsets = (
        (
            None,
            {
                "fields": ("dominio", "valor_minimo", "ordem", "ativa"),
                "description": (
                    "A cadeia de uma solicitação é a soma das regras cujo "
                    "<b>valor mínimo</b> ela alcança. Regra específica do domínio "
                    "substitui a genérica <code>*</code> na mesma ordem."
                ),
            },
        ),
        ("Quem aprova", {"fields": ("tipo", "papel", "aprovador")}),
    )


class EtapaInline(admin.TabularInline):
    model = EtapaAprovacao
    extra = 0
    can_delete = False
    fields = ("ordem", "aprovador", "papel", "situacao", "decidido_por", "decidido_em",
              "justificativa", "motivo_pulo")
    readonly_fields = fields
    ordering = ("ordem",)

    def has_add_permission(self, request, obj):
        # A cadeia é montada pelo serviço. Acrescentar etapa à mão produz
        # solicitação que ninguém consegue explicar depois.
        return False


@admin.register(SolicitacaoAprovacao)
class SolicitacaoAprovacaoAdmin(admin.ModelAdmin):
    list_display = ("titulo", "dominio", "solicitante", "valor", "situacao",
                    "etapa_pendente", "criado_em")
    list_filter = ("situacao", "dominio")
    search_fields = ("titulo", "resumo", "solicitante__username", "origem_id")
    date_hierarchy = "criado_em"
    list_select_related = ("solicitante",)
    inlines = (EtapaInline,)
    readonly_fields = ("criado_em", "decidido_em", "dados")

    @admin.display(description="Aguardando")
    def etapa_pendente(self, obj: SolicitacaoAprovacao) -> str:
        etapa = obj.etapa_atual
        if etapa is None:
            return "—"
        return str(etapa.aprovador or etapa.papel or "?")


@admin.register(Compromisso)
class CompromissoAdmin(admin.ModelAdmin):
    """Auditoria do comprometido — o que foi aprovado e ainda não pagou.

    Somente leitura de propósito: compromisso nasce da aprovação e morre na
    baixa. Editar valor à mão aqui produziria um orçamento que não bate com
    nenhuma decisão registrada.
    """

    list_display = ("centro_custo_codigo", "valor", "competencia", "situacao",
                    "dominio", "descricao", "criado_em")
    list_filter = ("situacao", "competencia", "dominio")
    search_fields = ("centro_custo_codigo", "descricao", "origem_id", "movimentacao_id")
    date_hierarchy = "competencia"
    list_select_related = ("solicitacao", "criado_por")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ItemCatalogo)
class ItemCatalogoAdmin(admin.ModelAdmin):
    """O catálogo. Onde os itens e os limites de auto-aprovação são mantidos."""

    list_display = ("nome", "grupo", "dominio", "prazo", "limite_auto_aprovacao",
                    "qtd_campos", "ativo", "ordem")
    list_filter = ("ativo", "grupo")
    search_fields = ("chave", "nome", "descricao_curta", "dominio")
    prepopulated_fields = {"chave": ("nome",)}
    ordering = ("grupo", "ordem", "nome")
    fieldsets = (
        (None, {"fields": ("chave", "nome", "descricao_curta", "grupo", "icone", "ordem", "ativo")}),
        (
            "Roteamento",
            {
                "fields": ("dominio", "permissao"),
                "description": (
                    "<b>Domínio</b> é para onde o pedido vai — é dado de roteamento, "
                    "não de navegação. O usuário navega por <b>grupo de intenção</b>."
                ),
            },
        ),
        (
            "Formulário",
            {
                "fields": ("campos", "exige_valor", "exige_centro_custo"),
                "description": (
                    "Máximo de <b>3 campos obrigatórios</b>. O resto vem da identidade "
                    "da pessoa — formulário longo é o que faz o usuário mandar e-mail."
                ),
            },
        ),
        (
            "Aprovação",
            {
                "fields": ("prazo_prometido_dias", "limite_auto_aprovacao"),
                "description": (
                    "Abaixo do limite <b>e</b> dentro do orçamento, o pedido não vai "
                    "para fila humana. Vazio = sempre exige aprovação."
                ),
            },
        ),
    )

    @admin.display(description="Prazo")
    def prazo(self, obj: ItemCatalogo) -> str:
        from workspace.services.catalogo import prazo_medido

        dias, medido = prazo_medido(obj)
        return f"{dias}d {'(medido)' if medido else '(prometido)'}"

    @admin.display(description="Campos")
    def qtd_campos(self, obj: ItemCatalogo) -> str:
        return f"{len(obj.campos or [])} ({len(obj.campos_obrigatorios)} obrig.)"


@admin.register(SolicitacaoServico)
class SolicitacaoServicoAdmin(admin.ModelAdmin):
    list_display = ("item", "solicitante", "valor", "situacao", "auto_aprovada", "criado_em")
    list_filter = ("situacao", "auto_aprovada", "item__grupo")
    search_fields = ("solicitante__username", "item__nome", "centro_custo_codigo")
    date_hierarchy = "criado_em"
    list_select_related = ("item", "solicitante")
    readonly_fields = ("criado_em", "concluido_em", "dados", "aprovacao", "auto_aprovada")
