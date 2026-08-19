"""EST — o estoque de materiais, e o que a empresa tem em campo.

## Por que existe

Os papéis de Suprimentos declaram `log.movimentar`, `log.custodia.ler`,
`log.custodia.atribuir` e `log.inventario.contar` desde a primeira onda. O
vocabulário foi desenhado; os modelos nunca foram construídos. Na prática o
saldo vive numa planilha, e a pergunta "temos capacete G?" é respondida por
mensagem para quem tem a planilha aberta.

## O razão é a verdade, o saldo é atalho

`MovimentoEstoque` é um razão: uma linha por entrada, saída ou ajuste, e nada
apaga linha. `SaldoEstoque.quantidade` é o mesmo número somado — denormalizado
porque "cabe no saldo?" é perguntado a cada requisição, e somar o razão inteiro
a cada pergunta é o tipo de conta que fica cara exatamente quando o estoque
começa a ser usado.

A mesma decisão de `SolicitacaoServico.reaberturas`: contador ao lado, razão
como fonte. Quando os dois discordam, o razão está certo — e é por isso que
`saldo_anterior` e `saldo_posterior` vão gravados em cada linha: sem eles, uma
divergência não tem como ser rastreada até o movimento que a criou.

## Reversa é entrada, não tabela separada

§15 pede controle do material recuperado de unidade desativada. Isso é uma
ENTRADA com procedência — de onde veio, em que condição, de qual cliente. Uma
tabela própria duplicaria o razão e criaria a pergunta "o saldo soma as duas?",
que é o tipo de pergunta que se responde errado uma vez e ninguém percebe.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class UnidadeMedida(models.TextChoices):
    UNIDADE = "un", "Unidade"
    PAR = "par", "Par"
    CAIXA = "cx", "Caixa"
    METRO = "m", "Metro"
    LITRO = "l", "Litro"
    QUILO = "kg", "Quilo"


class TipoMovimento(models.TextChoices):
    ENTRADA = "entrada", "Entrada"
    # Separada de ENTRADA porque a pergunta que ela responde é outra: "o que
    # temos para REUTILIZAR", que é o §15 inteiro. Somar as duas num tipo só
    # tornaria essa pergunta impossível sem adivinhar pela observação.
    REVERSA = "reversa", "Entrada de reversa"
    SAIDA = "saida", "Saída"
    # Ajuste de inventário: a contagem física discordou do sistema. Existe para
    # que corrigir saldo seja um FATO REGISTRADO com autor, e não um UPDATE que
    # ninguém consegue explicar seis meses depois.
    AJUSTE = "ajuste", "Ajuste de inventário"


class CondicaoMaterial(models.TextChoices):
    NOVO = "novo", "Novo"
    USADO_BOM = "usado_bom", "Usado — em boas condições"
    USADO_REPARO = "usado_reparo", "Usado — precisa de reparo"
    SUCATA = "sucata", "Sucata"


class Material(models.Model):
    """O que se controla. Um cadastro, não um item de catálogo.

    Separado de `ItemCatalogo` de propósito: catálogo é o que se PEDE, material
    é o que se TEM. Um material pode existir em estoque sem nunca ser pedido
    (peça de reposição de obra), e um item de catálogo pode não ter material
    nenhum atrás (acesso a sistema).
    """

    codigo = models.SlugField(max_length=40, unique=True)
    nome = models.CharField(max_length=120)
    categoria = models.CharField(max_length=40, blank=True, db_index=True)
    unidade_medida = models.CharField(
        max_length=5, choices=UnidadeMedida.choices, default=UnidadeMedida.UNIDADE
    )

    # Material com patrimônio é rastreado PEÇA A PEÇA — notebook, rádio,
    # ferramenta cara. O saldo continua contando, mas a custódia (§17) só faz
    # sentido para estes: ninguém assina termo de responsabilidade por parafuso.
    controla_patrimonio = models.BooleanField(default=False)

    # Abaixo disto o estoque avisa. Zero desliga o aviso, que é o padrão: aviso
    # que dispara para tudo é aviso que se aprende a ignorar.
    estoque_minimo = models.PositiveIntegerField(default=0)

    ativo = models.BooleanField(default=True, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "material"
        verbose_name_plural = "materiais"
        indexes = [models.Index(fields=["ativo", "categoria"], name="wks_material_idx")]

    def __str__(self) -> str:
        return self.nome


class SaldoEstoque(models.Model):
    """Quanto existe de um material EM UMA UNIDADE.

    Por unidade e não global: "temos 40 capacetes" é inútil para quem está em
    Campinas se os 40 estão em São Paulo. É também o que permite a requisição
    recusar por falta local sem mentir sobre o total da empresa.
    """

    material = models.ForeignKey(Material, on_delete=models.PROTECT, related_name="saldos")
    unidade = models.ForeignKey(
        "identidade.Unidade", on_delete=models.PROTECT, related_name="saldos_estoque"
    )
    quantidade = models.IntegerField(default=0)
    localizacao = models.CharField(
        max_length=80, blank=True, help_text="Prateleira, sala, contêiner."
    )
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["material__nome"]
        verbose_name = "saldo de estoque"
        verbose_name_plural = "saldos de estoque"
        constraints = [
            models.UniqueConstraint(
                fields=["material", "unidade"], name="wks_saldo_unico_por_unidade"
            ),
            # O saldo negativo é impossível por REGRA, e a regra fica no banco.
            # Em `movimentar()` ela também está — mas serviço se contorna com um
            # `update()` distraído, e constraint não.
            models.CheckConstraint(
                condition=models.Q(quantidade__gte=0), name="wks_saldo_nao_negativo"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.material} · {self.unidade} · {self.quantidade}"

    @property
    def abaixo_do_minimo(self) -> bool:
        minimo = self.material.estoque_minimo
        return bool(minimo) and self.quantidade < minimo


class MovimentoEstoque(models.Model):
    """Uma linha do razão. Nada aqui é editado nem apagado."""

    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name="movimentos"
    )
    unidade = models.ForeignKey(
        "identidade.Unidade", on_delete=models.PROTECT, related_name="movimentos_estoque"
    )
    tipo = models.CharField(max_length=10, choices=TipoMovimento.choices, db_index=True)

    # Sempre POSITIVA. O sinal é do `tipo`, e não do número: quantidade
    # negativa numa entrada é o tipo de dado que passa despercebido e vira
    # saldo errado sem nenhuma linha suspeita no razão.
    quantidade = models.PositiveIntegerField()
    saldo_anterior = models.IntegerField()
    saldo_posterior = models.IntegerField()

    quem = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="movimentos_estoque",
    )
    quando = models.DateTimeField(auto_now_add=True, db_index=True)
    observacao = models.CharField(max_length=300, blank=True)

    # De onde veio o movimento, no mesmo acoplamento frouxo do resto do
    # Workspace: `dominio` + `origem_id` em vez de FK. Um movimento sobrevive
    # ao pedido que o causou — o material saiu do estoque de qualquer forma.
    dominio = models.CharField(max_length=40, blank=True, db_index=True)
    origem_id = models.CharField(max_length=64, blank=True, db_index=True)

    # ── Só para REVERSA (§15) ────────────────────────────────────────
    condicao = models.CharField(
        max_length=15, choices=CondicaoMaterial.choices, blank=True
    )
    unidade_origem = models.ForeignKey(
        "identidade.Unidade",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reversas_enviadas",
        help_text="De qual unidade o material voltou.",
    )
    cliente = models.CharField(max_length=120, blank=True)
    patrimonio = models.CharField(max_length=40, blank=True, db_index=True)

    class Meta:
        ordering = ["-quando"]
        verbose_name = "movimento de estoque"
        verbose_name_plural = "movimentos de estoque"
        indexes = [
            models.Index(fields=["material", "unidade", "-quando"], name="wks_mov_razao_idx"),
            models.Index(fields=["tipo", "-quando"], name="wks_mov_tipo_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} · {self.material} · {self.quantidade}"

    def clean(self) -> None:
        if self.tipo != TipoMovimento.REVERSA and (self.condicao or self.cliente):
            raise ValidationError(
                {"condicao": "Condição e cliente só valem para entrada de reversa."}
            )
        if self.tipo == TipoMovimento.REVERSA and not self.condicao:
            # Reversa sem condição não serve para nada: a pergunta que o §15
            # existe para responder é "o que dá para reaproveitar", e ela é
            # respondida pela condição, não pela quantidade.
            raise ValidationError({"condicao": "Reversa exige a condição do material."})
