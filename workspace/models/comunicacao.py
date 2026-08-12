"""COM — Comunicação. O que alimenta os cards de Comunicados e Notícias.

Onde se publica: **Django admin**, em "iConnect Workspace › Publicações"
(`/admin/workspace/publicacao/`). O editor de conteúdo próprio é da Onda 3;
o admin resolve hoje e continua servindo de retaguarda depois.

Escolha de modelagem: **um** modelo com `tipo`, não dois. Comunicado e notícia
compartilham 100% dos campos e diferem só em intenção editorial. Dois modelos
custariam duas migrações, dois admins, duas queries e duas telas para sempre.

Fora do escopo aqui, de propósito (Onda 3, com o Mural): confirmação de
leitura, público-alvo segmentado e classe "crítico" que bloqueia navegação.
Esses exigem o modelo de identidade (IDN), que ainda não existe.
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone


class TipoPublicacao(models.TextChoices):
    COMUNICADO = "comunicado", "Comunicado"
    NOTICIA = "noticia", "Notícia"


class Prioridade(models.IntegerChoices):
    NORMAL = 0, "Normal"
    ATENCAO = 1, "Atenção"
    URGENTE = 2, "Urgente"


class PublicacaoQuerySet(models.QuerySet):
    def publicadas(self, agora=None):
        """Só o que está no ar agora: publicado, dentro da vigência.

        Feito como queryset e não como filtro na view para que a home, a busca
        e um futuro feed não divirjam sobre o que "estar no ar" significa.
        """
        agora = agora or timezone.now()
        return self.filter(publicado=True, publicar_em__lte=agora).filter(
            models.Q(expira_em__isnull=True) | models.Q(expira_em__gt=agora)
        )

    def do_tipo(self, tipo: str):
        return self.filter(tipo=tipo)


class Publicacao(models.Model):
    """Um comunicado ou uma notícia no Portal."""

    tipo = models.CharField(
        max_length=20, choices=TipoPublicacao.choices, default=TipoPublicacao.COMUNICADO, db_index=True
    )
    titulo = models.CharField(max_length=200)
    resumo = models.CharField(
        max_length=300, blank=True, help_text="Uma linha, exibida no card do Portal."
    )
    corpo = models.TextField(blank=True)

    prioridade = models.IntegerField(choices=Prioridade.choices, default=Prioridade.NORMAL)
    fixado = models.BooleanField(default=False, help_text="Fixa no topo da lista.")

    publicado = models.BooleanField(default=False, db_index=True)
    publicar_em = models.DateTimeField(
        default=timezone.now, help_text="Data futura agenda a publicação."
    )
    expira_em = models.DateTimeField(
        null=True, blank=True, help_text="Em branco, não expira."
    )

    autor = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="publicacoes_workspace"
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = PublicacaoQuerySet.as_manager()

    class Meta:
        verbose_name = "publicação"
        verbose_name_plural = "publicações"
        # Fixado primeiro, depois mais recente. `-publicar_em` e não
        # `-criado_em`: o que vale para o leitor é a data de publicação.
        ordering = ["-fixado", "-publicar_em"]
        indexes = [
            models.Index(fields=["tipo", "publicado", "-publicar_em"], name="wks_pub_listagem_idx"),
        ]

    def __str__(self) -> str:
        return f"[{self.get_tipo_display()}] {self.titulo}"

    @property
    def no_ar(self) -> bool:
        agora = timezone.now()
        if not self.publicado or self.publicar_em > agora:
            return False
        return self.expira_em is None or self.expira_em > agora

    @property
    def classe_prioridade(self) -> str:
        """Sufixo de classe CSS do ponto de prioridade.

        Classe e não token inline: a CSP de produção traz nonce em `style-src`,
        e navegador moderno ignora `unsafe-inline` quando há nonce — o que
        bloqueia atributo `style=""`. Cor via classe é a única forma segura.
        """
        return {
            Prioridade.URGENTE: "urgente",
            Prioridade.ATENCAO: "atencao",
        }.get(self.prioridade, "normal")
