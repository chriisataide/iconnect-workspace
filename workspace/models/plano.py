"""Plano de ação com limiar — a regra dos 10% do benchmark, generalizada.

## Limiar não é alerta: é obrigação

No Portal GPS, **margem abaixo de 10% exige justificativa e plano de ação**. O
mesmo desenho aparece no NPS: todo detrator gera plano com prazo acordado, e a
pesquisa é **refeita ao fim do prazo**.

Essa segunda metade é o que vale copiar, e é o que separa este model de uma
lista de tarefas. Um plano que fecha porque o responsável clicou "resolvido"
mede esforço. Um que fecha porque a regra **parou de disparar** mede resultado —
e é a diferença entre uma tela que a diretoria consulta e uma que ela aprende a
ignorar.

## O desfecho é reverificado, nunca declarado

`VerificacaoPlano` guarda o que a regra respondeu no vencimento, sobre a MESMA
chave de ocorrência. Se a ocorrência ainda está lá, o plano fecha como **não
resolvido** — mesmo que o responsável tenha escrito que resolveu. Ver ADR-033.

## Os quatro estados do benchmark

O painel de Tratativas mede efetividade em quatro: *em andamento no prazo*, *em
andamento fora do prazo*, *alterado para promotor*, *mantido como detrator*.
Generalizados aqui, dois são guardados e dois são derivados do relógio:

| Estado | De onde vem |
|---|---|
| em andamento no prazo | `situacao=aberto` e `prazo >= hoje` |
| em andamento fora do prazo | `situacao=aberto` e `prazo < hoje` |
| resolvido | a reverificação não achou mais a ocorrência |
| não resolvido | a reverificação achou de novo |

"Fora do prazo" derivado e não guardado: um campo `atrasado` precisaria de um
processo para mantê-lo, e um plano ficaria "no prazo" até o cron rodar.

## A chave da ocorrência é TEXTO, e nunca uma FK

`contrato:CT-100`, `lotacao:41`. O sujeito da exceção mora em outro app — às
vezes num espelho que a próxima carga reescreve —, e uma FK morreria junto com
ele. É a mesma decisão de `ResultadoExcecao.chaves`, pelo mesmo motivo: o plano
é registro histórico, e registro histórico não pode depender de a linha original
continuar existindo.

E, pelo mesmo motivo de lá: **a chave nunca identifica pessoa**.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

#: Quando a regra exige plano e não declara prazo. Trinta dias porque é o prazo
#: que o benchmark usa nas tratativas de NPS, e porque prazo ausente viraria um
#: plano que vence no dia em que nasce.
PRAZO_PADRAO_DO_PLANO = 30


class SituacaoPlano(models.TextChoices):
    ABERTO = "aberto", "Em andamento"
    RESOLVIDO = "resolvido", "Resolvido"
    NAO_RESOLVIDO = "nao_resolvido", "Não resolvido"


class PlanoAcaoQuerySet(models.QuerySet):
    def abertos(self):
        return self.filter(situacao=SituacaoPlano.ABERTO)

    def vencidos(self, ate=None):
        return self.abertos().filter(prazo__lt=ate or timezone.localdate())

    def no_prazo(self, ate=None):
        return self.abertos().filter(prazo__gte=ate or timezone.localdate())


class PlanoAcao(models.Model):
    """A resposta a UMA ocorrência de uma regra que gera obrigação."""

    #: A chave da regra, em texto. Não é FK por consistência com a chave da
    #: ocorrência: se a regra for retirada do catálogo, o plano que ela cobrou
    #: continua sendo o registro de uma decisão tomada.
    regra_chave = models.SlugField(max_length=60, db_index=True)
    ocorrencia_chave = models.CharField(max_length=120, db_index=True)

    #: O título congelado da ocorrência, do dia em que o plano foi aberto.
    #:
    #: Congelado pelo mesmo motivo do carimbo da ATA: reler a regra para
    #: reconstruir o título faria um plano de março mudar de assunto em setembro,
    #: quando o contrato mudasse de nome. O registro é do que se viu.
    titulo = models.CharField(max_length=200)
    #: O detalhe do dia — "margem de 4,2%". É o número que gerou a obrigação, e
    #: sem ele o plano diz o que fazer sem dizer por quê.
    detalhe = models.CharField(max_length=300, blank=True)

    #: Por que aconteceu. Obrigatória: é metade da exigência do benchmark, e a
    #: outra metade sem esta vira tarefa sem diagnóstico.
    justificativa = models.TextField()
    #: O que será feito. Também obrigatória.
    acao = models.TextField()

    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="planos_sob_responsabilidade",
    )
    prazo = models.DateField(db_index=True)

    situacao = models.CharField(
        max_length=15,
        choices=SituacaoPlano.choices,
        default=SituacaoPlano.ABERTO,
        db_index=True,
    )
    #: O que se disse ao fechar. Escrito por quem fechou, ou pela reverificação.
    desfecho = models.CharField(max_length=300, blank=True)

    aberto_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="planos_abertos",
    )
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    fechado_em = models.DateTimeField(null=True, blank=True)

    objects = PlanoAcaoQuerySet.as_manager()

    class Meta:
        ordering = ["prazo", "-criado_em"]
        verbose_name = "plano de ação"
        verbose_name_plural = "planos de ação"
        constraints = [
            # UM plano aberto por ocorrência. Dois planos abertos para o mesmo
            # contrato produzem duas versões do que a empresa vai fazer, e a
            # reverificação fecharia as duas com o mesmo desfecho — um deles
            # ganhando crédito por trabalho que não fez.
            #
            # `condition` e não `unique_together`: FECHADOS podem repetir, e
            # devem. A margem cair de novo em março depois de um plano cumprido
            # em janeiro é justamente o que o histórico precisa mostrar.
            models.UniqueConstraint(
                fields=["regra_chave", "ocorrencia_chave"],
                condition=models.Q(situacao="aberto"),
                name="wks_plano_um_aberto_por_ocorrencia",
            ),
        ]
        indexes = [
            models.Index(fields=["situacao", "prazo"], name="wks_plano_estado_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.regra_chave} · {self.ocorrencia_chave}"

    @property
    def aberto(self) -> bool:
        return self.situacao == SituacaoPlano.ABERTO

    @property
    def atrasado(self) -> bool:
        """Derivado do relógio, e não guardado.

        Um campo precisaria de um processo para mantê-lo, e o plano ficaria "no
        prazo" até o cron rodar — que é exatamente quando ninguém está olhando.
        """
        return self.aberto and self.prazo < timezone.localdate()

    @property
    def estado(self) -> str:
        """Um dos quatro do benchmark."""
        if not self.aberto:
            return self.situacao
        return "fora_do_prazo" if self.atrasado else "no_prazo"

    @property
    def dias_ate_o_prazo(self) -> int:
        return (self.prazo - timezone.localdate()).days


class VerificacaoPlano(models.Model):
    """O que a regra respondeu no vencimento, sobre a mesma ocorrência.

    Registro e não estado: um plano pode ser reconferido mais de uma vez — o
    comando roda todo dia —, e é a série que mostra se a ocorrência sumiu e
    voltou. Guardar só a última esconderia exatamente esse padrão, que é o mais
    caro de todos: o problema que se resolve e reaparece.
    """

    plano = models.ForeignKey(
        PlanoAcao, on_delete=models.CASCADE, related_name="verificacoes"
    )
    verificado_em = models.DateTimeField(default=timezone.now, db_index=True)
    #: `True` = a regra achou a ocorrência de novo. É o que decide o desfecho.
    ainda_ocorre = models.BooleanField()
    #: `False` quando a fonte da regra não estava no ar. NÃO é "resolvido": uma
    #: fonte caída faria todo plano que dependesse dela fechar como resolvido, e
    #: um conector fora do ar viraria um mês de metas batidas.
    avaliada = models.BooleanField(default=True)
    observacao = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-verificado_em"]
        verbose_name = "verificação de plano"
        verbose_name_plural = "verificações de plano"

    def __str__(self) -> str:
        estado = "ainda ocorre" if self.ainda_ocorre else "não ocorre mais"
        return f"{self.plano} · {estado}"
