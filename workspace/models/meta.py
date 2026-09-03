"""Metas, avaliação e PDI — o quadro de uma pessoa num ciclo.

## A meta é auditável porque a FÓRMULA está na tela

No Portal GPS, cada meta traz *grupo*, *descrição*, *tipo de cálculo*, *lógica de
pontuação*, *detalhamento* e **Fator 1 / Fator 2** — `EBITDA RE` ÷ `EBITDA OR`.
Não é um número que alguém digitou no fim do ciclo: é uma conta que aponta para
o dado.

Aqui os fatores apontam para o **espelho**, pelo catálogo de
`workspace/services/fatores.py`. `Meta.fator_1` guarda uma chave — `"ebitda"` —,
e nunca um valor. Guardar o valor faria a meta virar uma planilha bonita: o
número entraria uma vez, ninguém saberia de onde veio, e a conferência exigiria
abrir o Sankhya ao lado. Ver ADR-034.

## Quadro aprovado não muda mais

Depois do `aprovado`, editar meta, peso ou alvo é recusado. Mover a trave no
meio do ciclo é exatamente o defeito que a palavra "meta" existe para impedir —
e é o defeito mais fácil de cometer sem má-fé, corrigindo um alvo que "estava
errado" em novembro.

Corrigir continua possível: reabrir é um ato, com autor e registro. Ver ADR-035.

## O realizado é CONGELADO na apuração

`Meta.realizado` e `apurado_em` são copiados quando o quadro é apurado, com o
carimbo da fonte. Recalcular na leitura faria a nota de 2026 mudar em 2027,
quando uma carga corrigisse um mês antigo — e a nota é o que foi para o comitê.

É a mesma decisão do carimbo da ATA (ADR-030), pelo mesmo motivo.

## Fator sem amostra NÃO vira zero

Meta cujo fator o espelho não sabe responder fica **não apurada**, com o motivo.
Zero seria uma afirmação de que a pessoa falhou — e a diferença entre "não bateu"
e "não deu para medir" é a diferença entre uma conversa e uma injustiça.

## Sobre o nome `Meta`

Sim, o model se chama `Meta` e tem um `class Meta:` dentro. É a palavra da
empresa, é a palavra do benchmark, e trocá-la por `MetaIndividual` faria o
código deixar de falar a língua de quem usa a tela.

Não há ambiguidade real: o `Meta` interno é atributo da classe, lido pelo Django
por nome, e o externo é um nome de módulo. O que pede atenção é o `__init__` dos
models, que exporta os dois vocabulários — e por isso este arquivo é o único
lugar onde a palavra aparece sozinha.

## O que este model NUNCA guarda

Dado pessoal sensível. O quadro é de uma pessoa e é lido pela pessoa e por quem
a lidera; ele não tem CPF, não tem documento, não tem dado de saúde, e **não
existe grade de pessoas com nota ao lado** — restrição 8, e ela vale aqui mais
que em qualquer outra tela do produto.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class SituacaoCiclo(models.TextChoices):
    ABERTO = "aberto", "Aberto — definindo metas"
    EM_CURSO = "em_curso", "Em curso"
    FECHADO = "fechado", "Fechado"


class SituacaoQuadro(models.TextChoices):
    """Três estados, e a ordem entre eles é o produto.

    `rascunho` é onde se escreve; `aprovado` é onde se para de escrever;
    `apurado` é onde o número entra. Sem o degrau do meio, a meta seria editável
    até o dia da nota.
    """

    RASCUNHO = "rascunho", "Rascunho"
    APROVADO = "aprovado", "Aprovado"
    APURADO = "apurado", "Apurado"


class TipoCalculo(models.TextChoices):
    """Como o realizado vira percentual do alvo.

    Duas direções, e não uma. Receita maior é melhor; turnover maior é pior — e
    uma tela que só sabe somar dá 140% de desempenho a quem perdeu metade da
    equipe.
    """

    DIRETO = "direto", "Diretamente proporcional"
    INVERSO = "inverso", "Inversamente proporcional"


class GrupoMeta(models.TextChoices):
    """Os grupos do benchmark. TextChoices e não tabela: são vocabulário, não
    cadastro — e um grupo novo por ano faria a comparação entre ciclos parar de
    funcionar."""

    FINANCEIRA = "financeira", "Metas financeiras"
    OPERACIONAL = "operacional", "Metas operacionais"
    PESSOAS = "pessoas", "Metas de pessoas"
    PROJETO = "projeto", "Metas de projeto"


class CicloMetas(models.Model):
    """O período de um quadro de metas.

    Nome distinto de `CicloPlanejamento` de propósito: aquele é a pauta de uma
    reunião, este é o período de uma avaliação. Reusar o model faria a pauta de
    outubro carregar as metas de todo mundo.
    """

    chave = models.SlugField(max_length=40, unique=True)
    nome = models.CharField(max_length=120)
    inicio = models.DateField()
    fim = models.DateField()
    situacao = models.CharField(
        max_length=10,
        choices=SituacaoCiclo.choices,
        default=SituacaoCiclo.ABERTO,
        db_index=True,
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-inicio"]
        verbose_name = "ciclo de metas"
        verbose_name_plural = "ciclos de metas"

    def __str__(self) -> str:
        return self.nome

    @property
    def competencia_de_apuracao(self):
        """O mês que os fatores consultam. É o ÚLTIMO do ciclo.

        Apurar pelo mês corrente daria notas diferentes a cada dia de acesso —
        e a nota é o que vai para o comitê.
        """
        return self.fim.replace(day=1)


class QuadroMetas(models.Model):
    """O quadro de UMA pessoa num ciclo."""

    ciclo = models.ForeignKey(
        CicloMetas, on_delete=models.CASCADE, related_name="quadros"
    )
    pessoa = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="quadros_metas"
    )
    situacao = models.CharField(
        max_length=10,
        choices=SituacaoQuadro.choices,
        default=SituacaoQuadro.RASCUNHO,
        db_index=True,
    )

    #: O texto da aba "Resumo" do benchmark: o negócio, as prioridades e a
    #: estratégia de condução. Livre de propósito — é a única parte do quadro
    #: que não vira número, e é a que explica os números.
    resumo = models.TextField(blank=True)

    aprovado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="quadros_aprovados",
    )
    aprovado_em = models.DateTimeField(null=True, blank=True)
    apurado_em = models.DateTimeField(null=True, blank=True)

    #: Quantas vezes o quadro foi reaberto depois de aprovado, e por quê.
    #:
    #: Lista de `{"quando", "quem", "motivo"}`. Reabrir é legítimo e precisa ser
    #: VISÍVEL: um quadro reaberto três vezes num ciclo é um achado sobre como as
    #: metas foram definidas, e ele desapareceria se a reabertura só apagasse a
    #: data de aprovação.
    reaberturas = models.JSONField(default=list, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-ciclo__inicio", "pessoa__nome"]
        verbose_name = "quadro de metas"
        verbose_name_plural = "quadros de metas"
        constraints = [
            models.UniqueConstraint(
                fields=["ciclo", "pessoa"], name="wks_quadro_um_por_ciclo"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.pessoa} · {self.ciclo.chave}"

    @property
    def editavel(self) -> bool:
        """Só em rascunho. É o ADR-035 em uma linha."""
        return self.situacao == SituacaoQuadro.RASCUNHO

    @property
    def peso_total(self) -> int:
        return sum(m.peso for m in self.metas.all())

    @property
    def nota(self) -> Decimal | None:
        """A média ponderada das metas APURADAS.

        `None` quando nenhuma foi apurada, e as não apuradas ficam **fora do
        denominador**: contá-las como zero transformaria uma fonte fora do ar na
        nota de uma pessoa.
        """
        apuradas = [m for m in self.metas.all() if m.atingimento_pct is not None]
        peso = sum(m.peso for m in apuradas)
        if not peso:
            return None
        soma = sum(m.atingimento_pct * m.peso for m in apuradas)
        return (Decimal(soma) / Decimal(peso)).quantize(Decimal("0.1"))

    @property
    def nao_apuradas(self) -> list:
        return [m for m in self.metas.all() if m.atingimento_pct is None]


class Meta(models.Model):
    """Uma meta: a fórmula, o alvo e — depois da apuração — o realizado."""

    quadro = models.ForeignKey(
        QuadroMetas, on_delete=models.CASCADE, related_name="metas"
    )
    grupo = models.CharField(
        max_length=15, choices=GrupoMeta.choices, default=GrupoMeta.FINANCEIRA
    )
    descricao = models.CharField(max_length=200)
    #: O detalhamento do benchmark: como ler a meta, em prosa. É o que responde
    #: "o que exatamente conta aqui?" sem exigir uma reunião.
    detalhamento = models.TextField(blank=True)

    #: Peso relativo dentro do quadro. Inteiro e não percentual: percentuais que
    #: precisam somar 100 produzem quadros que não fecham por um ponto, e a
    #: correção vira uma discussão sobre arredondamento.
    peso = models.PositiveSmallIntegerField(default=1)

    #: A FÓRMULA. Chaves do catálogo de `services/fatores.py`, nunca valores.
    #:
    #: `fator_2` vazio quer dizer que a meta é sobre o valor absoluto do
    #: `fator_1` — "receita de R$ 2 milhões" —, e não uma razão.
    fator_1 = models.CharField(max_length=40)
    fator_2 = models.CharField(max_length=40, blank=True)

    tipo_calculo = models.CharField(
        max_length=10, choices=TipoCalculo.choices, default=TipoCalculo.DIRETO
    )
    #: O alvo. `None` quando a meta é a própria razão entre os fatores — aí o
    #: alvo é 100%, e escrevê-lo seria repetição que alguém contradiz.
    alvo = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    ordem = models.PositiveSmallIntegerField(default=100)

    # ── Congelado na apuração ────────────────────────────────────────
    #
    # Recalcular na leitura faria a nota de 2026 mudar em 2027, quando uma carga
    # corrigisse um mês antigo. A nota é o que foi para o comitê.
    realizado = models.DecimalField(
        max_digits=14, decimal_places=2, null=True, blank=True
    )
    atingimento_pct = models.DecimalField(
        max_digits=6, decimal_places=1, null=True, blank=True
    )
    #: Por que não deu para apurar. Preenchido quando `atingimento_pct` é nulo
    #: depois de uma apuração — e é ele que separa "não bateu" de "não deu para
    #: medir".
    motivo_sem_apuracao = models.CharField(max_length=200, blank=True)
    #: O carimbo de frescor da fonte, congelado. Mesma decisão de
    #: `AnotacaoEtapa.carimbo_texto`.
    carimbo_texto = models.CharField(max_length=200, blank=True)
    apurado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["grupo", "ordem", "id"]
        verbose_name = "meta"
        verbose_name_plural = "metas"

    def __str__(self) -> str:
        return self.descricao

    @property
    def formula(self) -> str:
        """A fórmula em texto, para a tela. É o que torna a meta auditável."""
        if self.fator_2:
            return f"{self.fator_1} ÷ {self.fator_2}"
        return self.fator_1

    @property
    def apurada(self) -> bool:
        return self.apurado_em is not None

    @property
    def bateu(self) -> bool | None:
        if self.atingimento_pct is None:
            return None
        return self.atingimento_pct >= 100


class PlanoDesenvolvimento(models.Model):
    """O PDI — a terceira aba do benchmark.

    Separado de `QuadroMetas` e não um campo dele: o PDI sobrevive ao ciclo de
    metas e é conversa de carreira, não de nota. Junto, ele seria apagado com a
    reprovação de um quadro — e é justamente aí que ele importa mais.
    """

    ciclo = models.ForeignKey(
        CicloMetas, on_delete=models.CASCADE, related_name="planos_de_desenvolvimento"
    )
    pessoa = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pdis"
    )

    responsabilidades = models.TextField(blank=True)
    interesses = models.TextField(blank=True)
    #: 1 a 2 anos, e 3 a 5. Os horizontes são os do benchmark, e estão no rótulo
    #: da tela: "aspirações" sem prazo vira lista de desejos.
    aspiracao_curta = models.TextField(blank=True)
    aspiracao_longa = models.TextField(blank=True)

    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-ciclo__inicio"]
        verbose_name = "plano de desenvolvimento"
        verbose_name_plural = "planos de desenvolvimento"
        constraints = [
            models.UniqueConstraint(
                fields=["ciclo", "pessoa"], name="wks_pdi_um_por_ciclo"
            ),
        ]

    def __str__(self) -> str:
        return f"PDI · {self.pessoa} · {self.ciclo.chave}"


class AcaoDesenvolvimento(models.Model):
    """Uma ação do PDI, com mês e ano — como no benchmark.

    Mês e ano, e não data: "fazer o curso em março de 2027" é o grão em que essa
    conversa acontece, e um seletor de dia obrigaria a inventar um número.
    """

    plano = models.ForeignKey(
        PlanoDesenvolvimento, on_delete=models.CASCADE, related_name="acoes"
    )
    descricao = models.CharField(max_length=300)
    mes = models.PositiveSmallIntegerField()
    ano = models.PositiveSmallIntegerField()
    concluida_em = models.DateField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ano", "mes", "id"]
        verbose_name = "ação de desenvolvimento"
        verbose_name_plural = "ações de desenvolvimento"

    def __str__(self) -> str:
        return f"{self.mes:02d}/{self.ano} · {self.descricao}"

    @property
    def concluida(self) -> bool:
        return self.concluida_em is not None

    @property
    def atrasada(self) -> bool:
        """Passou do mês e não foi concluída. Derivado do relógio."""
        if self.concluida:
            return False
        hoje = timezone.localdate()
        return (self.ano, self.mes) < (hoje.year, hoje.month)
