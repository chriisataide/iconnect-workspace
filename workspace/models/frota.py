"""FRT — a frota, e o que ela consome. §18 e §19.

## A duplicação que este módulo encontrou antes de escrever uma linha

Veículo já existia no produto **duas vezes**, e as duas não se conheciam:

* `Recurso(tipo=VEICULO)` — a grade de reservas, com garantia de que duas
  pessoas não pegam a van no mesmo horário;
* o item de catálogo `veiculo` ("Reservar carro ou utilitário"), um formulário
  de texto livre com "período" e "destino" que virava pedido numa fila.

Reservar pelo primeiro não bloqueava o segundo. Alguém marcava a van na grade,
outra pessoa abria o pedido, Suprimentos atendia os dois — e no dia, duas
equipes na porta esperando a mesma van. O item de catálogo foi aposentado
(`ativo=False`, os pedidos antigos continuam no histórico) e a reserva passou a
ser um caminho só.

`Veiculo.recurso` é o elo: o carro da frota **é** o recurso reservável, e não
uma segunda ficha com o mesmo nome. Sem esse `OneToOne`, a terceira lista de
veículos nasceria no primeiro mês.

## O que a frota controla que a reserva não controla

Quilometragem, documento com prazo e dinheiro. A grade responde "quem está com
a van hoje"; ela não responde "o licenciamento venceu?" nem "quanto essa van
custou este ano" — e é a primeira pergunta que faz o carro ser apreendido, não
a segunda.

## Documento vencido é DERIVADO da data, nunca um campo

Um `licenciamento_vencido = BooleanField` estaria errado no dia seguinte ao ser
gravado, e ninguém rodaria o comando que o corrige. A data é o fato; "vencido" é
uma conta sobre hoje.

## Consumo mora na despesa, não no veículo

`km/l` é a conta entre dois abastecimentos — precisa do anterior para existir.
Guardá-la no veículo daria um número só, do último tanque, que é exatamente o
número que não mostra a bomba quebrada nem o motorista abastecendo o carro
errado.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone


class TipoVeiculo(models.TextChoices):
    CARRO = "carro", "Carro"
    UTILITARIO = "utilitario", "Utilitário"
    VAN = "van", "Van"
    MOTO = "moto", "Moto"
    CAMINHAO = "caminhao", "Caminhão"


class SituacaoVeiculo(models.TextChoices):
    ATIVO = "ativo", "Em operação"
    MANUTENCAO = "manutencao", "Em manutenção"
    # Baixado e não apagado: multa, sinistro e imposto de um carro vendido
    # continuam chegando por anos, e a placa precisa achar o histórico.
    BAIXADO = "baixado", "Baixado"


class TipoDespesaVeiculo(models.TextChoices):
    """§19 na ordem de frequência. Combustível primeiro, e é o único que rende
    consumo — os outros não têm litro."""

    COMBUSTIVEL = "combustivel", "Combustível"
    PEDAGIO = "pedagio", "Pedágio"
    ESTACIONAMENTO = "estacionamento", "Estacionamento"
    LAVAGEM = "lavagem", "Lavagem"
    MANUTENCAO = "manutencao", "Manutenção"
    MULTA = "multa", "Multa"


#: Os documentos com prazo, na ordem em que a apreensão acontece. Em um lugar
#: só porque a lista aparece na tela, no aviso e no resumo — e a versão que
#: esquece um deles é a que deixa o carro ser apreendido.
DOCUMENTOS_COM_PRAZO = (
    ("licenciamento_ate", "Licenciamento"),
    ("seguro_ate", "Seguro"),
    ("ipva_ate", "IPVA"),
    ("revisao_em", "Revisão"),
)


class VeiculoQuerySet(models.QuerySet):
    def em_operacao(self):
        return self.filter(situacao=SituacaoVeiculo.ATIVO)

    def da_unidade(self, unidade):
        return self.filter(unidade=unidade) if unidade is not None else self


class Veiculo(models.Model):
    """Um carro da empresa. A placa é a identidade."""

    # A placa é o identificador que todo mundo usa — o guincho, a multa, o
    # frentista. `unique` porque duas fichas para a mesma placa é como a frota
    # passa a ter dois históricos de manutenção.
    placa = models.CharField(max_length=8, unique=True)
    marca = models.CharField(max_length=40, blank=True)
    modelo = models.CharField(max_length=60)
    ano = models.PositiveSmallIntegerField(null=True, blank=True)
    tipo = models.CharField(
        max_length=15, choices=TipoVeiculo.choices, default=TipoVeiculo.CARRO
    )

    renavam = models.CharField(max_length=20, blank=True)
    chassi = models.CharField(max_length=25, blank=True)

    unidade = models.ForeignKey(
        "identidade.Unidade",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="veiculos",
        help_text="Onde o veículo fica lotado.",
    )

    # O ELO COM A RESERVA — ver o cabeçalho do módulo.
    #
    # `SET_NULL` e não `CASCADE`: aposentar o recurso reservável (o carro saiu
    # do rodízio, mas continua da empresa) não pode apagar a ficha da frota,
    # onde moram a multa e o IPVA.
    recurso = models.OneToOneField(
        "workspace.Recurso",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="veiculo",
        help_text="O recurso reservável correspondente, quando o carro é de uso comum.",
    )

    km_atual = models.PositiveIntegerField(default=0)

    # ── Os prazos que fazem o carro parar ────────────────────────────
    licenciamento_ate = models.DateField(null=True, blank=True)
    seguro_ate = models.DateField(null=True, blank=True)
    ipva_ate = models.DateField(null=True, blank=True)
    revisao_em = models.DateField(null=True, blank=True)

    situacao = models.CharField(
        max_length=15,
        choices=SituacaoVeiculo.choices,
        default=SituacaoVeiculo.ATIVO,
        db_index=True,
    )
    observacao = models.CharField(max_length=300, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    objects = VeiculoQuerySet.as_manager()

    class Meta:
        ordering = ["placa"]
        verbose_name = "veículo"
        verbose_name_plural = "veículos"
        indexes = [
            models.Index(fields=["situacao", "unidade"], name="wks_veiculo_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.placa} · {self.modelo}"

    def save(self, *args, **kwargs):
        # A placa em maiúsculas, sempre. Sem isto "abc1d23" e "ABC1D23" são dois
        # veículos, e o `unique` não impede — o banco compara byte a byte.
        self.placa = self.placa.strip().upper()
        super().save(*args, **kwargs)

    # ── Prazos ───────────────────────────────────────────────────────

    def prazos(self, hoje: date | None = None) -> list[dict]:
        """Um item por documento COM data, com quantos dias faltam.

        Documento sem data preenchida fica de fora em vez de aparecer como
        "vencido": não saber a data do seguro é diferente de o seguro ter
        vencido, e tratar as duas coisas igual faria a tela gritar sobre a frota
        inteira no dia em que ela fosse cadastrada.
        """
        hoje = hoje or timezone.localdate()
        saida = []
        for campo, rotulo in DOCUMENTOS_COM_PRAZO:
            prazo = getattr(self, campo)
            if prazo is None:
                continue
            saida.append(
                {
                    "campo": campo,
                    "rotulo": rotulo,
                    "data": prazo,
                    "dias": (prazo - hoje).days,
                    "vencido": prazo < hoje,
                }
            )
        return sorted(saida, key=lambda p: p["data"])

    @property
    def vencidos(self) -> list[dict]:
        return [p for p in self.prazos() if p["vencido"]]

    @property
    def tem_pendencia(self) -> bool:
        return bool(self.vencidos)

    @property
    def reservavel(self) -> bool:
        """Só o que está em operação E tem recurso na grade.

        Carro em manutenção continua com recurso ligado — desligar e religar
        perderia o histórico de reservas —, e por isso a situação também conta.
        """
        return self.situacao == SituacaoVeiculo.ATIVO and self.recurso_id is not None


class DespesaVeiculo(models.Model):
    """Um gasto do veículo — §19. Combustível, pedágio e o resto."""

    veiculo = models.ForeignKey(
        Veiculo, on_delete=models.PROTECT, related_name="despesas"
    )
    tipo = models.CharField(
        max_length=15, choices=TipoDespesaVeiculo.choices, db_index=True
    )
    data = models.DateField(default=timezone.localdate, db_index=True)
    valor = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))]
    )

    # Odômetro no momento do gasto. Opcional porque pedágio e lavagem não pedem
    # — e exigir faria quem lança inventar um número, que é pior que o vazio: o
    # cálculo de consumo passaria a mentir com aparência de precisão.
    km = models.PositiveIntegerField(null=True, blank=True)
    litros = models.DecimalField(
        max_digits=7, decimal_places=3, null=True, blank=True
    )
    # Tanque cheio ou não. É a informação que decide se o consumo pode ser
    # calculado: o método tanque-a-tanque só vale entre dois enchimentos
    # completos, e sem essa marca a conta divide a distância pelo litro de um
    # tanque parcial — e devolve um número plausível e errado.
    tanque_cheio = models.BooleanField(default=True)

    fornecedor = models.CharField(max_length=120, blank=True)

    # ── Quem dirigia, para onde, e por quê — §19 ─────────────────────
    #
    # `motorista` é SEPARADO de `quem`, e a separação é o §19 inteiro: quem
    # lança a nota do posto é o administrativo; quem dirigia é o técnico. Com um
    # campo só, "custo por técnico" — que o §19 pede explicitamente — mediria o
    # custo do administrativo que digitou.
    motorista = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="despesas_dirigidas",
        help_text="Quem estava dirigindo. Vazio quando não se sabe.",
    )
    destino = models.CharField(max_length=160, blank=True)
    finalidade = models.CharField(
        max_length=200, blank=True, help_text="Cliente, obra, entrega, deslocamento."
    )

    quem = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="despesas_veiculo",
        help_text="Quem lançou — não necessariamente quem dirigia.",
    )
    observacao = models.CharField(max_length=300, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Mais recente primeiro na tela; `-pk` desempata para que dois
        # lançamentos do mesmo dia tenham ordem estável — sem isso a lista
        # embaralha entre dois carregamentos e parece que algo mudou.
        ordering = ["-data", "-pk"]
        verbose_name = "despesa de veículo"
        verbose_name_plural = "despesas de veículo"
        indexes = [
            models.Index(fields=["veiculo", "-data"], name="wks_desp_veic_idx"),
            models.Index(fields=["tipo", "-data"], name="wks_desp_tipo_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} · {self.veiculo.placa} · {self.valor}"

    @property
    def rende_consumo(self) -> bool:
        """Só abastecimento completo com litro e odômetro entra na conta."""
        return (
            self.tipo == TipoDespesaVeiculo.COMBUSTIVEL
            and self.tanque_cheio
            and self.km is not None
            and self.litros is not None
            and self.litros > 0
        )

    @property
    def preco_por_litro(self) -> Decimal | None:
        if not self.litros:
            return None
        return (self.valor / self.litros).quantize(Decimal("0.001"))
