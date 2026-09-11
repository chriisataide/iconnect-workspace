"""O registro das cargas — quem trouxe o quê, quando, e o que deu errado.

## Por que este app não se chama `integracoes`

Porque `workspace/integracoes/` já existe e faz outra coisa: é o **link** com o
iConnect Platform — cliente HTTP curto, sessão, middleware, tudo rodando dentro
de uma requisição do usuário. Dois pacotes com o mesmo nome fazendo trabalhos
diferentes é como um `import` errado passa despercebido numa revisão.

`cargas` diz o que este app faz: ele executa cargas. `ExecucaoCarga` mora aqui
sem precisar de explicação.

## O que este app garante, e o que ele não garante

Garante que **nenhuma carga apaga dado bom**. O carregador escreve por upsert
sobre `(fonte, chave_externa)`; falha no meio deixa a execução marcada
`parcial` e o espelho íntegro até onde chegou. Não existe caminho que trunque
uma tabela.

Não garante que o dado esteja certo — isso é do outro lado. O que ele registra é
de onde veio e quando, para que a pergunta "esse número está velho?" tenha
resposta sem ninguém abrir código.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import models
from django.utils import timezone


class Fonte(models.TextChoices):
    """As fontes conhecidas.

    Espelhada em `resultados.models.Fonte` de propósito — `resultados` não
    importa este app, e a duplicação de seis linhas é o preço de manter a
    direção. `test_as_duas_listas_de_fonte_batem` reprova a divergência.
    """

    SANKHYA = "sankhya", "Sankhya"
    MONDAY = "monday", "monday.com"
    PLATFORM = "iconnect_platform", "iConnect Platform"
    CSV = "csv", "Carga por arquivo"
    MANUAL = "manual", "Lançamento manual"
    #: A única PÚBLICA da lista, e a única sem credencial.
    PNCP = "pncp", "PNCP · contratações públicas"


class FonteDados(models.Model):
    """Uma origem de dado, com a cadência que ela promete cumprir."""

    chave = models.CharField(max_length=30, choices=Fonte.choices, unique=True)
    nome = models.CharField(max_length=80)
    ativa = models.BooleanField(default=True, db_index=True)

    #: O que se espera dela: "diária às 6h", "a cada 15 min". Texto e não cron:
    #: quem lê a tela de fontes é gente, e o agendamento de verdade mora no cron
    #: do servidor. Duas fontes de verdade sobre a cadência seria pior que uma
    #: frase.
    cadencia_esperada = models.CharField(max_length=80, blank=True)

    #: Acima disto o carimbo do bloco vira alerta. Declarado pela FONTE porque
    #: seis horas é velho para o monday e é novo para a folha do Sankhya — uma
    #: constante única alarmaria a metade errada da tela.
    idade_maxima_aceitavel = models.DurationField(
        null=True, blank=True, default=timedelta(hours=26)
    )

    responsavel_tecnico = models.CharField(max_length=120, blank=True)
    observacao = models.TextField(blank=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "fonte de dados"
        verbose_name_plural = "fontes de dados"

    def __str__(self) -> str:
        return self.nome or self.chave

    @property
    def ultima_boa(self) -> "ExecucaoCarga | None":
        """A última carga BEM-SUCEDIDA. É ela que data o dado que está na tela.

        Carga que falhou não avança este relógio. Se avançasse, uma fonte
        quebrada há três dias pareceria fresca — que é exatamente o carimbo
        mentiroso que a Onda 1 existe para impedir.
        """
        return (
            self.execucoes.filter(status=StatusCarga.SUCESSO)
            .order_by("-terminada_em")
            .first()
        )

    @property
    def ultima_tentativa(self) -> "ExecucaoCarga | None":
        return self.execucoes.order_by("-iniciada_em").first()


class StatusCarga(models.TextChoices):
    EM_ANDAMENTO = "em_andamento", "Em andamento"
    SUCESSO = "sucesso", "Sucesso"
    #: Trouxe parte e parou. **Não é falha**: o que entrou é bom e fica. A tela
    #: mostra o dado com a idade em destaque, e não um espaço vazio.
    PARCIAL = "parcial", "Parcial"
    FALHA = "falha", "Falha"


class ExecucaoCarga(models.Model):
    """Uma rodada de carga. É daqui que sai o carimbo de frescor."""

    fonte = models.ForeignKey(
        FonteDados, on_delete=models.CASCADE, related_name="execucoes"
    )
    iniciada_em = models.DateTimeField(default=timezone.now, db_index=True)
    terminada_em = models.DateTimeField(null=True, blank=True, db_index=True)
    status = models.CharField(
        max_length=20, choices=StatusCarga.choices,
        default=StatusCarga.EM_ANDAMENTO, db_index=True,
    )

    #: A janela pedida. Nula quando a carga é "tudo o que houver".
    janela_de = models.DateField(null=True, blank=True)
    janela_ate = models.DateField(null=True, blank=True)

    lidos = models.PositiveIntegerField(default=0)
    criados = models.PositiveIntegerField(default=0)
    atualizados = models.PositiveIntegerField(default=0)
    #: Chegou e não mudou nada — `hash_conteudo` igual. É o número que prova que
    #: reprocessar a mesma janela não fez nada, e é o que o operador olha depois
    #: de rodar de novo por precaução.
    ignorados = models.PositiveIntegerField(default=0)
    #: Chegou e foi recusado: centro de custo inexistente, campo obrigatório
    #: vazio, data impossível. Recusado NÃO é ignorado, e somá-los esconderia a
    #: única das duas contagens que pede ação.
    rejeitados = models.PositiveIntegerField(default=0)

    #: Uma linha, para a tela. Nunca contém credencial nem URL com token — a
    #: tela de fontes é visível a quem opera e à diretoria.
    erro_resumo = models.CharField(max_length=300, blank=True)
    log = models.TextField(blank=True)

    #: `True` quando a execução foi simulação. O comando roda em simulação por
    #: padrão, e uma simulação que virasse carimbo faria a tela dizer que o dado
    #: chegou quando nada foi gravado.
    simulacao = models.BooleanField(default=False, db_index=True)

    class Meta:
        ordering = ["-iniciada_em"]
        verbose_name = "execução de carga"
        verbose_name_plural = "execuções de carga"
        indexes = [
            models.Index(fields=["fonte", "status", "-terminada_em"],
                         name="crg_execucao_frescor_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.fonte.chave} · {self.iniciada_em:%d/%m %H:%M} · {self.status}"

    @property
    def duracao(self) -> timedelta | None:
        if self.terminada_em is None:
            return None
        return self.terminada_em - self.iniciada_em


class RegraPrecedencia(models.Model):
    """Quem vence quando duas fontes discordam — declarado, não decidido em `if`.

    Sankhya e monday vão discordar sobre valor de projeto; Sankhya e Platform
    sobre vigência de contrato. Resolver isso dentro do carregador esconderia a
    decisão de negócio num arquivo que só quem programa lê — e a próxima pessoa
    resolveria de outro jeito, no outro conector.

    `justificativa` é obrigatória na prática: uma regra sem o porquê é uma regra
    que ninguém ousa mudar.
    """

    entidade = models.CharField(max_length=40, db_index=True)
    campo = models.CharField(max_length=40)
    fonte_vencedora = models.CharField(max_length=30, choices=Fonte.choices)
    ordem = models.PositiveSmallIntegerField(default=100)
    justificativa = models.TextField(blank=True)
    ativa = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["entidade", "campo", "ordem"]
        verbose_name = "regra de precedência"
        verbose_name_plural = "regras de precedência"
        constraints = [
            models.UniqueConstraint(
                fields=["entidade", "campo", "fonte_vencedora"],
                name="crg_precedencia_unica",
            )
        ]

    def __str__(self) -> str:
        return f"{self.entidade}.{self.campo} → {self.fonte_vencedora}"


class Divergencia(models.Model):
    """Duas fontes discordaram, e a diferença passou do limiar.

    Registrada mesmo quando a `RegraPrecedencia` resolveu o valor. Resolver não
    é a mesma coisa que concordar: o número entra na tela pela regra, e a
    divergência aparece na tela de fontes com os dois valores lado a lado, para
    alguém ir descobrir por que os sistemas discordam.

    Silenciar aqui seria trocar um problema visível por um invisível.
    """

    entidade = models.CharField(max_length=40, db_index=True)
    chave_externa = models.CharField(max_length=120, db_index=True)
    campo = models.CharField(max_length=40)

    fonte_a = models.CharField(max_length=30)
    valor_a = models.CharField(max_length=200)
    fonte_b = models.CharField(max_length=30)
    valor_b = models.CharField(max_length=200)

    fonte_vencedora = models.CharField(max_length=30, blank=True)
    detectada_em = models.DateTimeField(default=timezone.now, db_index=True)
    carga = models.ForeignKey(
        ExecucaoCarga, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="divergencias",
    )
    #: Marcada por gente, na tela de fontes. Divergência resolvida não some do
    #: histórico: some da lista de abertas.
    resolvida_em = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-detectada_em"]
        verbose_name = "divergência entre fontes"
        verbose_name_plural = "divergências entre fontes"
        indexes = [
            models.Index(fields=["resolvida_em", "-detectada_em"],
                         name="crg_divergencia_abertas_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.entidade}.{self.campo} · {self.fonte_a} ≠ {self.fonte_b}"
