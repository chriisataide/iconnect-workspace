"""Anexo de uma solicitação de serviço.

Existe porque o campo de tipo `arquivo` do catálogo era um `<input type=text>`:
para pedir reembolso, a pessoa **digitava o nome** do comprovante. O fluxo
financeiro mais frequente da empresa estava fingindo.

Metadado na tabela, conteúdo no armazenamento privado. `nome_original` e
`tipo_mime` ficam aqui porque o nome no disco é um UUID — ver
`workspace/storage.py`.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models

from workspace.storage import ArmazenamentoPrivado, caminho_do_anexo


class Anexo(models.Model):
    """Um arquivo enviado em resposta a um campo `arquivo` do item."""

    solicitacao = models.ForeignKey(
        "workspace.SolicitacaoServico",
        on_delete=models.CASCADE,
        related_name="anexos",
    )
    # Qual campo do item este arquivo responde. Um item pode ter mais de um
    # campo de arquivo (contrato: minuta + procuração), e sem isso não se sabe
    # qual obrigatoriedade foi satisfeita.
    campo = models.CharField(max_length=50, db_index=True)

    arquivo = models.FileField(
        upload_to=caminho_do_anexo,
        storage=ArmazenamentoPrivado(),
        max_length=255,
    )
    nome_original = models.CharField(max_length=255)
    tamanho = models.PositiveBigIntegerField(help_text="Bytes.")
    tipo_mime = models.CharField(max_length=100, blank=True)

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="anexos_workspace",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["campo", "criado_em"]
        verbose_name = "anexo de solicitação"
        verbose_name_plural = "anexos de solicitação"
        indexes = [
            models.Index(fields=["solicitacao", "campo"], name="wks_anexo_sol_idx"),
        ]

    def __str__(self) -> str:
        return self.nome_original

    @property
    def tamanho_legivel(self) -> str:
        """`184320` → `180 KB`. Byte cru não diz nada a quem envia comprovante."""
        tamanho = float(self.tamanho)
        for unidade in ("B", "KB", "MB"):
            if tamanho < 1024 or unidade == "MB":
                if unidade == "B":
                    return f"{int(tamanho)} B"
                return f"{tamanho:.0f} {unidade}".replace(".", ",")
            tamanho /= 1024
        return f"{tamanho:.0f} MB"  # pragma: no cover - laço sempre retorna antes
