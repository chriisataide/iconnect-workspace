"""Documento — POP, política, norma, manual.

## Três decisões que definem se o acervo serve para algo

**1 · "Vencido" é derivado, nunca armazenado.** A situação guardada no banco tem
`rascunho`, `vigente` e `revogado`; vencimento sai de `vigencia_fim < hoje`.
Estado armazenado que depende do relógio mente no dia seguinte, a menos que
alguém mantenha um cron — e no dia em que o cron falhar, um POP vencido continua
sendo apresentado como vigente. Derivar é mais barato e não pode ficar defasado.

**2 · A confirmação de leitura guarda a VERSÃO lida.** Se o documento vai para a
v2, a confirmação da v1 deixa de valer. Sem isso, "todo mundo confirmou" é uma
frase sobre um texto que já não existe — e é justamente essa frase que se leva
para auditoria de ISO ou para defesa trabalhista.

**3 · Público-alvo usa o vocabulário de `subjects_de()`**, o mesmo do *security
trimming* da busca: `*`, `pessoa:N`, `unidade:N`, `depto:N`, `papel:chave`. Um
segundo vocabulário para dizer "quem vê" divergiria do primeiro na terceira
semana, e aí o documento aparece na busca de quem não pode abri-lo.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from workspace.storage import ArmazenamentoPrivado, caminho_do_documento


class TipoDocumento(models.TextChoices):
    """Na ordem em que a empresa procura, não alfabética."""

    POP = "pop", "POP — procedimento operacional"
    POLITICA = "politica", "Política"
    NORMA = "norma", "Norma"
    INSTRUCAO = "instrucao", "Instrução de trabalho"
    MANUAL = "manual", "Manual"


class SituacaoDocumento(models.TextChoices):
    RASCUNHO = "rascunho", "Rascunho"
    VIGENTE = "vigente", "Vigente"
    REVOGADO = "revogado", "Revogado"


class DocumentoQuerySet(models.QuerySet):
    def publicados(self, hoje=None):
        """Vigentes hoje: publicado, dentro da vigência, não revogado."""
        hoje = hoje or timezone.localdate()
        return self.filter(
            situacao=SituacaoDocumento.VIGENTE,
            vigencia_inicio__lte=hoje,
        ).filter(models.Q(vigencia_fim__isnull=True) | models.Q(vigencia_fim__gte=hoje))

    def vencidos(self, hoje=None):
        hoje = hoje or timezone.localdate()
        return self.filter(
            situacao=SituacaoDocumento.VIGENTE, vigencia_fim__lt=hoje
        )

    def para_subjects(self, subjects):
        """Documentos cujo público-alvo intersecta os sujeitos da pessoa.

        Feito em Python sobre `publico_alvo` (JSON) porque SQLite não tem
        operador de interseção de array. Com dezenas de documentos o custo é
        irrelevante; quando o acervo crescer, o índice unificado da onda D
        assume — e lá o recorte acontece no `WHERE`, como manda a Etapa 5.
        """
        alvo = set(subjects)
        ids = [d.pk for d in self if alvo & set(d.publico_alvo or ["*"])]
        return self.filter(pk__in=ids)

    def obrigatorios(self):
        return self.filter(leitura_obrigatoria=True)


class Documento(models.Model):
    """Um documento normativo da empresa."""

    slug = models.SlugField(max_length=80, unique=True)
    tipo = models.CharField(
        max_length=20, choices=TipoDocumento.choices, default=TipoDocumento.POP,
        db_index=True,
    )
    titulo = models.CharField(max_length=200)
    resumo = models.CharField(
        max_length=300, blank=True, help_text="Uma linha. Aparece na lista."
    )
    corpo = models.TextField(blank=True)

    # O ARQUIVO — §33.
    #
    # `corpo` (texto) e `arquivo` coexistem de propósito, e não são
    # alternativas: o texto é o que a BUSCA indexa e o que a tela mostra sem
    # download; o arquivo é o PDF assinado, a planilha, o desenho. Um documento
    # com os dois é o caso normal — resumo legível na tela, original anexado.
    #
    # Armazenamento privado. Um POP com o desenho da instalação, um contrato
    # modelo, uma política de acesso: nenhum deles deve ficar num caminho que o
    # nginx serve sem perguntar quem é.
    arquivo = models.FileField(
        upload_to=caminho_do_documento,
        storage=ArmazenamentoPrivado(),
        max_length=255,
        blank=True,
    )
    arquivo_nome = models.CharField(
        max_length=255, blank=True,
        help_text="Nome original, para quem baixa reconhecer.",
    )
    arquivo_tamanho = models.PositiveBigIntegerField(null=True, blank=True)

    # Quem RESPONDE pelo conteúdo, não quem digitou. Documento normativo sem dono
    # é documento que ninguém atualiza — e o primeiro sinal de acervo morto é uma
    # lista de POP sem responsável.
    dono = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="documentos_workspace",
    )
    versao = models.CharField(
        max_length=12, default="1.0",
        help_text="Texto livre — é o formato que a norma ISO usa (1.0, 1.2, 2026-A).",
    )

    publico_alvo = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            'Sujeitos que podem ver. `["*"]` = todos. Também aceita '
            '`papel:sesmt`, `depto:3`, `unidade:1`, `pessoa:42`.'
        ),
    )
    leitura_obrigatoria = models.BooleanField(
        default=False,
        help_text="Exige confirmação de leitura, com trilha para auditoria.",
    )

    vigencia_inicio = models.DateField(default=timezone.localdate, db_index=True)
    vigencia_fim = models.DateField(
        null=True, blank=True, help_text="Vazio = sem prazo de validade.", db_index=True
    )
    situacao = models.CharField(
        max_length=20, choices=SituacaoDocumento.choices,
        default=SituacaoDocumento.RASCUNHO, db_index=True,
    )
    revoga = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="revogado_por",
        help_text="O documento que este substitui.",
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = DocumentoQuerySet.as_manager()

    class Meta:
        # Tipo primeiro, na ordem de declaração do enum (frequência de busca),
        # depois título. `ordering` por `-atualizado_em` faria a lista mudar de
        # ordem a cada correção de vírgula.
        ordering = ["tipo", "titulo"]
        verbose_name = "documento"
        verbose_name_plural = "documentos"
        indexes = [
            models.Index(
                fields=["situacao", "tipo", "titulo"], name="wks_doc_vitrine_idx"
            ),
            models.Index(
                fields=["leitura_obrigatoria", "situacao"], name="wks_doc_obrig_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.titulo} v{self.versao}"

    @property
    def tem_arquivo(self) -> bool:
        return bool(self.arquivo)

    @property
    def tamanho_legivel(self) -> str:
        """"1,4 MB" em vez de 1468006.

        A tela mostra o tamanho para que a pessoa decida se baixa agora ou
        espera o wi-fi — e o número cru não responde essa pergunta.
        """
        bytes_ = self.arquivo_tamanho or 0
        if not bytes_:
            return ""
        for unidade in ("B", "KB", "MB", "GB"):
            if bytes_ < 1024 or unidade == "GB":
                return f"{bytes_:.0f} {unidade}".replace(".", ",")
            bytes_ /= 1024
        return ""

    @property
    def vencido(self) -> bool:
        """Derivado, não armazenado — ver docstring do módulo."""
        return bool(self.vigencia_fim and self.vigencia_fim < timezone.localdate())

    @property
    def vigente(self) -> bool:
        if self.situacao != SituacaoDocumento.VIGENTE:
            return False
        hoje = timezone.localdate()
        return self.vigencia_inicio <= hoje and not self.vencido

    @property
    def dias_para_vencer(self) -> int | None:
        if not self.vigencia_fim:
            return None
        return (self.vigencia_fim - timezone.localdate()).days

    @property
    def para_todos(self) -> bool:
        return "*" in (self.publico_alvo or ["*"])


class ConfirmacaoLeitura(models.Model):
    """Registro de que uma pessoa leu uma VERSÃO do documento."""

    documento = models.ForeignKey(
        Documento, on_delete=models.CASCADE, related_name="confirmacoes"
    )
    pessoa = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leituras_workspace",
    )
    # A versão no momento da confirmação. Documento que muda invalida a
    # confirmação antiga — é o que faz a trilha valer em auditoria.
    versao = models.CharField(max_length=12)
    confirmado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-confirmado_em"]
        verbose_name = "confirmação de leitura"
        verbose_name_plural = "confirmações de leitura"
        constraints = [
            # Uma confirmação por pessoa POR VERSÃO. Aqui a constraint é certa —
            # ao contrário da notificação, o modo de falha é "não grava duplicata",
            # e duplicata de confirmação não acrescenta informação nenhuma.
            models.UniqueConstraint(
                fields=["documento", "pessoa", "versao"],
                name="wks_leitura_unica_por_versao",
            )
        ]
        indexes = [
            models.Index(fields=["pessoa", "documento"], name="wks_leitura_pessoa_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.pessoa} leu {self.documento.titulo} v{self.versao}"
