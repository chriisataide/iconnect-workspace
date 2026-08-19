"""REL — relatórios de entrega e de ocorrência (§34–36).

## Um modelo com `tipo`, não dois

Relatório de entrega e relatório CSI compartilham tudo que é estrutura: quem
fez, quando, onde, para qual cliente, com que evidências, e um estado de
rascunho → emitido. O que muda é o QUESTIONÁRIO — e questionário é dado, não
schema.

Dois modelos custariam duas migrações, dois admins, duas telas e duas consultas
para sempre, e o terceiro tipo de relatório que a empresa pedir custaria a
mesma coisa de novo. É a mesma decisão de `Publicacao`, que tem comunicado e
notícia num modelo só.

## Os campos do tipo ficam em JSON, e o motivo não é preguiça

A lista de perguntas de um relatório de entrega muda quando o contrato com o
cliente muda. Colunas exigiriam migração para cada mudança — e, pior, exigiriam
que os relatórios ANTIGOS ganhassem a coluna nova vazia, como se a pergunta
tivesse sido feita e não respondida.

Em JSON, um relatório emitido guarda exatamente o que foi perguntado no dia. É
a mesma escolha de `SolicitacaoServico.dados`, e pelo mesmo motivo.

## Rascunho e emitido, e por que emitido não se edita

Relatório de ocorrência é documento que alguém assina e que sai da empresa. Um
emitido editável é um documento que muda depois de entregue — e a única defesa
contra "não foi isso que eu recebi" é ele não poder ter mudado.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from workspace.storage import ArmazenamentoPrivado, caminho_do_documento


class TipoRelatorio(models.TextChoices):
    ENTREGA = "entrega", "Relatório de entrega"
    OCORRENCIA = "ocorrencia", "Relatório de ocorrência (CSI)"


class SituacaoRelatorio(models.TextChoices):
    RASCUNHO = "rascunho", "Rascunho"
    EMITIDO = "emitido", "Emitido"
    CANCELADO = "cancelado", "Cancelado"


class RelatorioQuerySet(models.QuerySet):
    def de(self, pessoa):
        if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
            return self.none()
        return self.filter(autor=pessoa)

    def emitidos(self):
        return self.filter(situacao=SituacaoRelatorio.EMITIDO)

    def rascunhos(self):
        return self.filter(situacao=SituacaoRelatorio.RASCUNHO)


class Relatorio(models.Model):
    """Um relatório de campo — entrega ou ocorrência."""

    tipo = models.CharField(
        max_length=20, choices=TipoRelatorio.choices, db_index=True
    )
    titulo = models.CharField(max_length=200)

    # ── O que é comum aos dois tipos ─────────────────────────────────
    cliente = models.CharField(max_length=160, blank=True)
    local = models.CharField(max_length=200, blank=True)
    # Data do FATO, não do registro. São diferentes com frequência: a ocorrência
    # foi na sexta e o relatório foi escrito na segunda, e datar pelo registro
    # faria o prazo contratual contar a partir do dia errado.
    ocorrido_em = models.DateField(default=timezone.localdate, db_index=True)
    horario = models.TimeField(null=True, blank=True)

    #: As respostas do questionário do tipo. Ver o docstring do módulo.
    dados = models.JSONField(default=dict, blank=True)

    situacao = models.CharField(
        max_length=20, choices=SituacaoRelatorio.choices,
        default=SituacaoRelatorio.RASCUNHO, db_index=True,
    )
    emitido_em = models.DateTimeField(null=True, blank=True)

    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="relatorios"
    )
    unidade = models.ForeignKey(
        "identidade.Unidade", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="relatorios",
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = RelatorioQuerySet.as_manager()

    class Meta:
        ordering = ["-ocorrido_em", "-criado_em"]
        verbose_name = "relatório"
        verbose_name_plural = "relatórios"
        indexes = [
            models.Index(fields=["tipo", "situacao", "-ocorrido_em"], name="wks_rel_lista_idx"),
            models.Index(fields=["autor", "-criado_em"], name="wks_rel_autor_idx"),
        ]

    def __str__(self) -> str:
        return f"[{self.get_tipo_display()}] {self.titulo}"

    @property
    def emitido(self) -> bool:
        return self.situacao == SituacaoRelatorio.EMITIDO

    @property
    def editavel(self) -> bool:
        """Só rascunho se edita. Ver o docstring do módulo."""
        return self.situacao == SituacaoRelatorio.RASCUNHO


class EvidenciaRelatorio(models.Model):
    """Uma foto ou arquivo anexado ao relatório.

    Modelo próprio e não `FileField` no relatório: uma ocorrência tem várias
    fotos, e "foto1, foto2, foto3" como colunas é o desenho que trava na quarta.

    Armazenamento privado. Foto de ocorrência mostra o local, às vezes gente, e
    frequentemente o que deu errado — nada disso deve estar num caminho público.
    """

    relatorio = models.ForeignKey(
        Relatorio, on_delete=models.CASCADE, related_name="evidencias"
    )
    arquivo = models.FileField(
        upload_to=caminho_do_documento, storage=ArmazenamentoPrivado(), max_length=255
    )
    nome_original = models.CharField(max_length=255)
    legenda = models.CharField(max_length=200, blank=True)
    tamanho = models.PositiveBigIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["criado_em"]
        verbose_name = "evidência"
        verbose_name_plural = "evidências"

    def __str__(self) -> str:
        return self.legenda or self.nome_original
