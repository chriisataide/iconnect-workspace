"""Admin do Workspace.

    /admin/workspace/publicacao/   Comunicados e Notícias
    /admin/workspace/documento/    POP, políticas e normas — com trilha de leitura
    /admin/workspace/recurso/      salas, veículos e equipamentos reserváveis
    /admin/workspace/correspondencia/  o que chega na recepção
    /admin/workspace/regraaprovacao/   os tetos da cadeia de aprovação
    /admin/workspace/solicitacaoaprovacao/   auditoria das decisões
"""

from __future__ import annotations

from django.contrib import admin, messages
from django.utils import timezone

from .models import (
    AcaoDesenvolvimento,
    AnotacaoEtapa,
    CicloMetas,
    Meta,
    PlanoDesenvolvimento,
    QuadroMetas,
    PlanoAcao,
    VerificacaoPlano,
    CicloPlanejamento,
    EtapaCiclo,
    OcorrenciaCiclo,
    RegraExcecao,
    ResultadoExcecao,
    Anexo,
    Compromisso,
    Curso,
    Material,
    Correspondencia,
    ConfirmacaoLeitura,
    Documento,
    SituacaoDocumento,
    ItemCatalogo,
    EtapaAprovacao,
    Publicacao,
    Recurso,
    RegraAprovacao,
    Reserva,
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
                    "O card do Workspace só mostra o que está <b>publicado</b>, com "
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


class AnexoInline(admin.TabularInline):
    """Anexos em leitura. Sem link para o arquivo, de propósito.

    O admin roda sob autenticação de staff, mas a autorização do anexo é a do
    Workspace — solicitante, aprovador da cadeia, ou quem aprova sobre a pessoa.
    Um staff qualquer não está nessa lista, e um link aqui abriria uma segunda
    porta que não passa por `pode_baixar()`. Quem precisa auditar o conteúdo
    entra pela tela do Workspace.
    """

    model = Anexo
    extra = 0
    can_delete = False
    fields = ("campo", "nome_original", "tamanho_legivel", "tipo_mime", "criado_por", "criado_em")
    readonly_fields = fields

    def has_add_permission(self, request, obj) -> bool:
        # Anexo nasce do formulário do Workspace, que valida magic bytes. Upload
        # pelo admin driblaria essa validação.
        return False


@admin.register(SolicitacaoServico)
class SolicitacaoServicoAdmin(admin.ModelAdmin):
    list_display = ("item", "solicitante", "valor", "situacao", "auto_aprovada", "criado_em")
    list_filter = ("situacao", "auto_aprovada", "item__grupo")
    search_fields = ("solicitante__username", "item__nome", "centro_custo_codigo")
    date_hierarchy = "criado_em"
    list_select_related = ("item", "solicitante")
    readonly_fields = ("criado_em", "concluido_em", "dados", "aprovacao", "auto_aprovada")
    inlines = (AnexoInline,)


class ConfirmacaoInline(admin.TabularInline):
    """A trilha de leitura, em leitura. É a peça que vai para a auditoria."""

    model = ConfirmacaoLeitura
    extra = 0
    can_delete = False
    fields = ("pessoa", "versao", "confirmado_em")
    readonly_fields = fields

    def has_add_permission(self, request, obj) -> bool:
        # Confirmação lançada à mão no admin é declaração falsa de conformidade.
        # Quem leu confirma na tela do documento, autenticado.
        return False


@admin.register(Documento)
class DocumentoAdmin(admin.ModelAdmin):
    list_display = (
        "titulo", "tipo", "versao", "situacao", "vigencia_fim",
        "leitura_obrigatoria", "dono", "situacao_real",
    )
    list_filter = ("tipo", "situacao", "leitura_obrigatoria")
    search_fields = ("titulo", "resumo", "corpo", "slug")
    prepopulated_fields = {"slug": ("titulo",)}
    autocomplete_fields = ("dono",)
    date_hierarchy = "vigencia_inicio"
    list_select_related = ("dono",)
    inlines = (ConfirmacaoInline,)

    fieldsets = (
        (None, {"fields": ("tipo", "titulo", "slug", "resumo", "corpo")}),
        (
            "Responsabilidade",
            {
                "fields": ("dono", "versao"),
                "description": (
                    "<b>Dono</b> é quem responde pelo conteúdo, não quem digitou. "
                    "Documento normativo sem dono é documento que ninguém atualiza."
                ),
            },
        ),
        (
            "Quem vê",
            {
                "fields": ("publico_alvo", "leitura_obrigatoria"),
                "description": (
                    'Público-alvo em JSON. <code>["*"]</code> = toda a empresa. '
                    "Também aceita <code>papel:sesmt</code>, <code>depto:3</code>, "
                    "<code>unidade:1</code>, <code>pessoa:42</code> — o mesmo "
                    "vocabulário do recorte da busca. Lista vazia é tratada como "
                    "<code>[&quot;*&quot;]</code>."
                ),
            },
        ),
        (
            "Vigência",
            {
                "fields": ("situacao", "vigencia_inicio", "vigencia_fim", "revoga"),
                "description": (
                    "<b>Vencido não é uma situação</b> — sai de <i>vigência até</i> "
                    "ter passado. Estado gravado que depende da data mente no dia "
                    "seguinte. Documento vencido some da vitrine e da busca, mas "
                    "continua abrindo por link, com aviso."
                ),
            },
        ),
    )

    @admin.display(description="Estado real")
    def situacao_real(self, obj) -> str:
        if obj.situacao == SituacaoDocumento.REVOGADO:
            return "revogado"
        if obj.vencido:
            return "VENCIDO"
        if obj.vigente:
            return "em vigor"
        return obj.get_situacao_display().lower()


@admin.register(Recurso)
class RecursoAdmin(admin.ModelAdmin):
    list_display = ("nome", "tipo", "unidade", "capacidade", "duracao_maxima_horas", "ativo")
    list_filter = ("tipo", "ativo", "unidade")
    search_fields = ("nome", "codigo", "descricao")
    prepopulated_fields = {"codigo": ("nome",)}
    list_select_related = ("unidade",)

    fieldsets = (
        (None, {"fields": ("tipo", "nome", "codigo", "descricao", "ativo")}),
        (
            "Onde e para quantos",
            {
                "fields": ("unidade", "capacidade"),
                "description": (
                    "<b>Unidade vazia</b> = o recurso aparece para toda a empresa. "
                    "A unidade é informação na tela, não barreira: quem está em "
                    "outra base pode precisar da sala da matriz."
                ),
            },
        ),
        (
            "Limite",
            {
                "fields": ("duracao_maxima_horas",),
                "description": (
                    "Recurso preso por três meses bloqueia todo mundo. Pedido de "
                    "bloqueio longo tem de passar por alguém, não por um "
                    "formulário de reserva."
                ),
            },
        ),
    )


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ("recurso", "solicitante", "inicio", "fim", "situacao", "motivo")
    list_filter = ("situacao", "recurso__tipo", "recurso")
    search_fields = ("recurso__nome", "solicitante__username", "motivo")
    date_hierarchy = "inicio"
    list_select_related = ("recurso", "solicitante")
    autocomplete_fields = ("solicitante",)
    readonly_fields = ("criado_em", "cancelado_em", "cancelado_por")


@admin.register(Correspondencia)
class CorrespondenciaAdmin(admin.ModelAdmin):
    list_display = (
        "tipo", "destinatario", "nome_no_envelope", "remetente",
        "urgente", "situacao", "recebido_em",
    )
    list_filter = ("situacao", "tipo", "urgente", "unidade")
    search_fields = ("remetente", "descricao", "nome_no_envelope", "destinatario__username")
    date_hierarchy = "recebido_em"
    list_select_related = ("destinatario", "unidade")
    autocomplete_fields = ("destinatario", "recebido_por", "retirado_por")
    readonly_fields = ("urgente", "retirado_em")

    fieldsets = (
        (None, {"fields": ("tipo", "remetente", "descricao")}),
        (
            "Para quem",
            {
                "fields": ("destinatario", "nome_no_envelope", "unidade"),
                "description": (
                    "<b>Destinatário vazio é caso normal</b>: nome errado no "
                    "envelope, sem etiqueta, endereçada só à empresa. O nome no "
                    "envelope é o que permite alguém se reconhecer na fila."
                ),
            },
        ),
        (
            "Situação",
            {
                "fields": ("situacao", "urgente", "recebido_por", "recebido_em",
                           "retirado_por", "retirado_em", "observacao"),
                "description": (
                    "<b>Urgente é derivado do tipo</b> — intimação e multa têm "
                    "prazo legal, e quem registra não tem como saber isso."
                ),
            },
        ),
    )


# ── Cadastros de referência — §58 ───────────────────────────────────
#
# `Material` e `Curso` eram os dois únicos modelos do produto sem NENHUMA porta:
# não têm tela (a de estoque mostra saldo, não cadastra material; a Universidade
# mostra matrícula, não cadastra curso) e não estavam aqui. Na prática, incluir
# um material novo significava editar `semear_estoque.py` e rodar o comando, ou
# abrir um shell — que é como um cadastro para de acompanhar a operação.
#
# Admin e não tela própria, de propósito: são cadastros de referência, mexidos
# poucas vezes por ano por quem administra a área. Uma tela para cada seria
# superfície nova para manter em troca de dois formulários que ninguém abre no
# dia a dia. É exatamente o papel de retaguarda que o admin tem no resto do
# produto.
#
# O RAZÃO de estoque continua fora daqui, e é decisão: `MovimentoEstoque` é um
# livro que ninguém edita. Uma tela de admin sobre ele ofereceria justamente a
# operação que o modelo inteiro existe para impedir.


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = (
        "codigo",
        "nome",
        "categoria",
        "unidade_medida",
        "estoque_minimo",
        "controla_patrimonio",
        "ativo",
    )
    list_filter = ("ativo", "categoria", "controla_patrimonio")
    search_fields = ("codigo", "nome")
    ordering = ("nome",)


@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nome", "tipo", "validade_meses", "obrigatorio", "ativo")
    list_filter = ("ativo", "tipo", "obrigatorio")
    search_fields = ("codigo", "nome")
    ordering = ("nome",)


# ── Painel de exceções ──────────────────────────────────────────────


@admin.register(RegraExcecao)
class RegraExcecaoAdmin(admin.ModelAdmin):
    """A CONFIGURAÇÃO da regra — e só ela.

    Ligar, desligar, reordenar e mudar severidade são decisões de quem opera,
    tomadas no dia: exigir deploy para elas faria a primeira regra ruidosa ficar
    ruidosa por uma semana.

    A LÓGICA não está aqui e não pode estar. Ligar uma regra sem avaliador
    escrito é possível — e a tela responde "não avaliada" com o motivo, em vez
    de "sem ocorrências", que seria uma afirmação sobre uma verificação que não
    aconteceu.
    """

    # `chave` PRIMEIRO, e é uma restrição do Django com uma razão boa: o
    # primeiro campo de `list_display` vira o link para a página de edição, e
    # por isso não pode ser editável na lista.
    #
    # Deixar `ordem` ali obrigaria a escolher entre editar a ordem em massa —
    # que é o caso de uso real desta tela — e ter um link para abrir a regra.
    # `chave` é a identidade da regra e o melhor link possível.
    list_display = ("chave", "ordem", "titulo", "severidade", "escopo_papel",
                    "fonte_requerida", "ativa")
    list_filter = ("ativa", "severidade", "fonte_requerida", "escopo_papel")
    list_editable = ("ativa", "ordem")
    search_fields = ("chave", "titulo", "descricao_curta")
    ordering = ("ordem", "chave")
    readonly_fields = ("chave",)


@admin.register(ResultadoExcecao)
class ResultadoExcecaoAdmin(admin.ModelAdmin):
    """O retrato de uma avaliação. Registro, e por isso somente leitura.

    Registro editável não é registro — e é dele que sai a tendência que a tela
    mostra. Corrigir um número aqui faria a seta mentir sobre um movimento que
    não houve.
    """

    list_display = ("regra", "executada_em", "total", "avaliada")
    list_filter = ("avaliada", "regra")
    date_hierarchy = "executada_em"

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


# ── Ciclo de planejamento ───────────────────────────────────────────


class EtapaCicloInline(admin.TabularInline):
    """A pauta se edita DENTRO do ciclo.

    Etapa numa tela própria produziria a lista de 16 itens de três ciclos
    misturada, ordenada por id — e a ordem é justamente o que esta pauta é.
    """

    model = EtapaCiclo
    extra = 1
    fields = ("ordem", "codigo", "titulo", "tela", "pergunta", "obrigatoria")


@admin.register(CicloPlanejamento)
class CicloPlanejamentoAdmin(admin.ModelAdmin):
    """A pauta e a plateia. Quem conduz e quem lê são DADO, não código.

    O campo `tela` de cada etapa guarda o CÓDIGO do endereçamento — `10`, `02.3`
    —, e nunca uma URL: endereço é estável por decisão (ADR-015) e URL não é.
    Ver ADR-029.
    """

    list_display = ("chave", "nome", "cadencia", "papel_condutor", "ordem", "ativo")
    list_filter = ("cadencia", "ativo")
    list_editable = ("ordem", "ativo")
    search_fields = ("chave", "nome", "publico")
    inlines = (EtapaCicloInline,)


@admin.register(OcorrenciaCiclo)
class OcorrenciaCicloAdmin(admin.ModelAdmin):
    """A reunião. Registro histórico, e por isso somente leitura.

    Nem criação: abrir a reunião roda a conferência de frescor e congela os
    impedimentos. Uma ocorrência criada aqui nasceria sem essa lista — e a ATA
    dela diria que não havia fonte atrasada quando ninguém chegou a olhar.
    """

    list_display = ("ciclo", "ano", "mes", "situacao", "conduzida_por", "fechada_em")
    list_filter = ("situacao", "ciclo")
    readonly_fields = (
        "ciclo", "ano", "mes", "situacao", "conduzida_por", "aberta_em",
        "fechada_em", "impedimentos", "ata",
    )

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


@admin.register(AnotacaoEtapa)
class AnotacaoEtapaAdmin(admin.ModelAdmin):
    """O que se disse, e o carimbo que a tela tinha na hora.

    Somente leitura pelo mesmo motivo do `ResultadoExcecao`: editar o carimbo
    congelado reescreveria o que a sala viu, que é exatamente a informação que
    uma auditoria procura numa ATA. ADR-030.
    """

    list_display = ("ocorrencia", "etapa", "autor", "criado_em", "carimbo_texto")
    list_filter = ("ocorrencia__ciclo", "carimbo_alerta")
    search_fields = ("texto", "encaminhamento")

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


# ── Planos de ação ──────────────────────────────────────────────────


class VerificacaoPlanoInline(admin.TabularInline):
    """As conferências. Somente leitura: elas são o que a REGRA respondeu.

    Editável, a conferência viraria o jeito de declarar sucesso pela porta dos
    fundos — e é exatamente contra isso que ela existe (ADR-033).
    """

    model = VerificacaoPlano
    extra = 0
    can_delete = False
    fields = ("verificado_em", "ainda_ocorre", "avaliada", "observacao")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None) -> bool:
        return False


@admin.register(PlanoAcao)
class PlanoAcaoAdmin(admin.ModelAdmin):
    """A resposta a uma ocorrência. Consulta e correção de rumo, não de desfecho.

    `situacao` e `desfecho` são somente leitura: quem decide se o plano resolveu
    é a regra rodando de novo, e não quem tem acesso ao `/admin/`. Prazo e
    responsável se corrigem — trocar o dono de um plano é decisão legítima de
    quem opera, e negá-la faria a correção acontecer por fora, num plano novo
    que perderia o histórico.
    """

    list_display = ("titulo", "regra_chave", "responsavel", "prazo", "situacao")
    list_filter = ("situacao", "regra_chave")
    search_fields = ("titulo", "ocorrencia_chave", "justificativa", "acao")
    date_hierarchy = "criado_em"
    readonly_fields = (
        "regra_chave", "ocorrencia_chave", "titulo", "detalhe", "situacao",
        "desfecho", "aberto_por", "criado_em", "fechado_em",
    )
    inlines = (VerificacaoPlanoInline,)

    def has_add_permission(self, request) -> bool:
        # Plano nasce de uma OCORRÊNCIA, e o serviço confere que a regra ainda a
        # encontra. Criado aqui, ele nasceria sobre um problema que talvez já não
        # exista — e fecharia como resolvido sem ninguém ter feito nada.
        return False


# ── Metas, avaliação e PDI ──────────────────────────────────────────


@admin.register(CicloMetas)
class CicloMetasAdmin(admin.ModelAdmin):
    """O período. É a única parte desta onda que se cadastra à mão."""

    list_display = ("chave", "nome", "inicio", "fim", "situacao")
    list_filter = ("situacao",)
    search_fields = ("chave", "nome")


class MetaInline(admin.TabularInline):
    """As metas se editam DENTRO do quadro.

    Numa tela própria, as metas de trinta pessoas apareceriam misturadas e
    ordenadas por id — e um quadro de metas é justamente o agrupamento.

    A APURAÇÃO é somente leitura aqui: `realizado` e `atingimento_pct` são
    congelados pela leitura do espelho, e editá-los seria escrever a nota à mão.
    """

    model = Meta
    extra = 0
    fields = (
        "ordem", "grupo", "descricao", "fator_1", "fator_2", "tipo_calculo",
        "alvo", "peso", "realizado", "atingimento_pct", "motivo_sem_apuracao",
    )
    readonly_fields = ("realizado", "atingimento_pct", "motivo_sem_apuracao")


@admin.register(QuadroMetas)
class QuadroMetasAdmin(admin.ModelAdmin):
    """O quadro de uma pessoa.

    `situacao`, `aprovado_por`, `aprovado_em` e `reaberturas` são somente
    leitura: aprovar, reabrir e apurar são ATOS, e cada um deixa registro. Mudar
    a situação aqui pularia o registro — que é exatamente o que o ADR-035
    existe para impedir.

    NÃO há `list_display` com nota. Uma coluna de nota ao lado de uma lista de
    nomes é uma planilha de desempenho, e o `/admin/` exporta.
    """

    list_display = ("pessoa", "ciclo", "situacao", "aprovado_em")
    list_filter = ("situacao", "ciclo")
    search_fields = ("pessoa__nome",)
    readonly_fields = (
        "situacao", "aprovado_por", "aprovado_em", "apurado_em", "reaberturas",
    )
    inlines = (MetaInline,)


class AcaoDesenvolvimentoInline(admin.TabularInline):
    model = AcaoDesenvolvimento
    extra = 0
    fields = ("ano", "mes", "descricao", "concluida_em")


@admin.register(PlanoDesenvolvimento)
class PlanoDesenvolvimentoAdmin(admin.ModelAdmin):
    """O PDI. Consulta, sobretudo.

    Ele é escrito pela própria pessoa na tela do produto; o `/admin/` existe
    aqui para o caso de precisar apagar um plano criado por engano, e não para
    redigir a carreira de alguém.
    """

    list_display = ("pessoa", "ciclo", "atualizado_em")
    list_filter = ("ciclo",)
    search_fields = ("pessoa__nome",)
    inlines = (AcaoDesenvolvimentoInline,)
