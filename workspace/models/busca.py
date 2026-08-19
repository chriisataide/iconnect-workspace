"""Índice unificado de busca — o `SearchDocument` da Etapa 5 §5.10.

## Por que existe um índice, se a base é pequena

Não é por desempenho. Com 19 itens de catálogo e cinco documentos, consulta
direta na origem seria mais rápida e nunca ficaria velha.

O índice existe pelo **recorte por permissão**. A Etapa 5 é categórica:

> Autorização de busca: *security trimming* no índice, **nunca** no
> pós-processamento. Filtrar depois de recuperar vaza contagem e snippet.

`Documento.publico_alvo` é um JSON, e filtrar JSON em Python é exatamente o
pós-processamento proibido: "8 resultados" viraria "3 resultados" depois do
filtro, e a diferença conta ao usuário que existem cinco documentos que ele não
pode ver — às vezes com o título no meio do caminho.

## Por que uma tabela de sujeitos, e não `ArrayField`

A Etapa 5 propõe `acl_subjects[]` com o operador `&&` do PostgreSQL. Isso
funcionaria em produção e **quebraria em desenvolvimento**, que roda SQLite —
`ArrayField` é exclusivo do Postgres.

`SujeitoIndice` normalizado dá o mesmo resultado (`WHERE sujeito IN (...)`) nos
dois bancos, com índice btree de verdade em vez de varredura de array. Custa um
`JOIN` e um `DISTINCT`. Quando o acervo justificar `tsvector` e `pgvector`, esta
tabela continua válida: ela é sobre QUEM vê, não sobre COMO se encontra.
"""

from __future__ import annotations

from django.db import models


class OrigemIndice(models.TextChoices):
    """De onde a entrada veio. Define o grupo na tela, na ordem daqui."""

    SERVICO = "servico", "Serviços"
    # §57 — o que se PEDE já estava; o que se PERGUNTA, se APRENDE, se MARCA e
    # o que é SEU não estava. A busca achava o item de catálogo "Reembolso" e
    # não achava o pedido de reembolso que a própria pessoa abriu — que é o que
    # ela procura quando digita "reembolso março".
    SOLICITACAO = "solicitacao", "Minhas solicitações"
    DOCUMENTO = "documento", "Documentação"
    FAQ = "faq", "Perguntas frequentes"
    CURSO = "curso", "Universidade"
    RECURSO = "recurso", "Reservas"
    CORRESPONDENCIA = "correspondencia", "Correspondências"
    COMUNICADO = "comunicado", "Comunicados"
    NOTICIA = "noticia", "Notícias"


class EntradaIndiceQuerySet(models.QuerySet):
    def para_sujeitos(self, sujeitos):
        """O *security trimming*, no `WHERE`.

        `DISTINCT` porque a mesma entrada casa por mais de um sujeito: um
        documento com público `["*", "papel:rh"]` casaria duas vezes para quem é
        do RH, e a contagem duplicaria.
        """
        return self.filter(sujeitos__sujeito__in=list(sujeitos)).distinct()


class EntradaIndice(models.Model):
    """Uma coisa encontrável, com seu texto de busca já normalizado."""

    # Acoplamento frouxo como no resto do Workspace: o índice sobrevive à origem.
    dominio = models.CharField(max_length=40, db_index=True)
    origem_id = models.CharField(max_length=64)
    origem = models.CharField(
        max_length=20, choices=OrigemIndice.choices, db_index=True
    )

    titulo = models.CharField(max_length=200)
    subtitulo = models.CharField(max_length=300, blank=True)
    # Título + subtítulo + corpo, tudo minúsculo e sem acento. Um campo só,
    # porque a consulta é `LIKE` sobre ele: casar em três campos separados
    # exigiria três `OR` e daria o mesmo resultado.
    texto = models.TextField(blank=True)

    url = models.CharField(max_length=300)
    icone = models.CharField(max_length=30, blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = EntradaIndiceQuerySet.as_manager()

    class Meta:
        ordering = ["origem", "titulo"]
        verbose_name = "entrada do índice"
        verbose_name_plural = "entradas do índice"
        constraints = [
            models.UniqueConstraint(
                fields=["dominio", "origem_id"], name="wks_indice_origem_unica"
            )
        ]
        indexes = [
            models.Index(fields=["origem", "titulo"], name="wks_indice_grupo_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_origem_display()} · {self.titulo}"


class SujeitoIndice(models.Model):
    """Quem pode ver esta entrada. Vocabulário de `subjects_de()`."""

    entrada = models.ForeignKey(
        EntradaIndice, on_delete=models.CASCADE, related_name="sujeitos"
    )
    sujeito = models.CharField(max_length=60, db_index=True)

    class Meta:
        verbose_name = "sujeito do índice"
        verbose_name_plural = "sujeitos do índice"
        constraints = [
            models.UniqueConstraint(
                fields=["entrada", "sujeito"], name="wks_indice_sujeito_unico"
            )
        ]

    def __str__(self) -> str:
        return self.sujeito
