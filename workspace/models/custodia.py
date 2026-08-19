"""EST — quem está com o quê. O termo de responsabilidade que nunca existiu.

## O problema real

O notebook sai do estoque para uma pessoa, e a partir daí ele some do sistema: o
saldo baixou, o razão registrou uma saída, e a pergunta que o RH faz no
desligamento — *o que esta pessoa tem para devolver?* — não tem onde ser
respondida. Na prática ela é respondida por memória de quem entregou, e o
resultado é o rádio que ninguém cobra e o notebook que a pessoa leva embora sem
má-fé nenhuma.

## Custódia não é saída de estoque

A saída registra que o material deixou a prateleira. A custódia registra que ele
**continua sendo da empresa** e está sob responsabilidade de alguém. São fatos
diferentes com vidas diferentes: a saída acabou no instante em que aconteceu, a
custódia dura anos e termina numa devolução.

Por isso a custódia é um modelo próprio e o razão continua sendo o razão — a
entrega grava as duas coisas, cada uma respondendo a sua pergunta.

## Aceite separado da entrega

`entregue_em` é Suprimentos dizendo "entreguei"; `aceito_em` é a pessoa dizendo
"recebi". É a mesma distinção do §6 na correspondência, e pela mesma razão:
enquanto só existe o primeiro, a única versão registrada dos fatos é a de quem
entregou — e é justamente essa que não vale nada no dia em que o equipamento
sumir e alguém precisar cobrar.

## A devolução alimenta a reversa (§15)

Devolver com condição gera uma entrada de reversa no razão. Não é acoplamento
gratuito: material devolvido *é* material que voltou de campo, e a pergunta "o
que dá para reaproveitar" não pode ter duas respostas conforme o caminho de
volta.

## Situação é derivada

Não há campo `situacao`. Uma custódia está em uso enquanto `devolvido_em` for
nulo — um campo ao lado seria uma segunda fonte de verdade sobre a mesma data, e
a primeira a discordar dela.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from workspace.models.estoque import CondicaoMaterial, Material


class CustodiaQuerySet(models.QuerySet):
    def de(self, pessoa):
        if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
            return self.none()
        return self.filter(pessoa=pessoa)

    def em_uso(self):
        return self.filter(devolvido_em__isnull=True)

    def devolvidas(self):
        return self.filter(devolvido_em__isnull=False)

    def a_aceitar(self):
        """Entregue e ainda sem a palavra de quem recebeu."""
        return self.em_uso().filter(aceito_em__isnull=True)


class Custodia(models.Model):
    """Um material da empresa sob responsabilidade de uma pessoa."""

    material = models.ForeignKey(
        Material, on_delete=models.PROTECT, related_name="custodias"
    )
    pessoa = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="custodias"
    )
    # De qual prateleira saiu. Guardada porque a devolução volta para ELA, e não
    # para a unidade de quem estiver recebendo: o notebook que saiu de São Paulo
    # e voltou por Campinas não vira saldo de Campinas por acidente de logística.
    unidade = models.ForeignKey(
        "identidade.Unidade", on_delete=models.PROTECT, related_name="custodias"
    )

    quantidade = models.PositiveIntegerField(default=1)

    # Patrimônio e série ficam AQUI e não no material: o material é o modelo
    # ("Notebook Dell i5"), a custódia é a peça. Guardá-los no cadastro obrigaria
    # um material por peça, e o saldo perderia o sentido.
    patrimonio = models.CharField(max_length=40, blank=True, db_index=True)
    numero_serie = models.CharField(max_length=60, blank=True)

    entregue_em = models.DateTimeField(default=timezone.now, db_index=True)
    entregue_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="custodias_entregues",
    )
    # A palavra de quem recebeu. Ver o cabeçalho: sem ela, o único registro é o
    # de quem entregou.
    aceito_em = models.DateTimeField(null=True, blank=True)

    devolvido_em = models.DateTimeField(null=True, blank=True, db_index=True)
    devolvido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="custodias_recebidas",
        help_text="Quem recebeu de volta — Suprimentos, não a pessoa.",
    )
    condicao_devolucao = models.CharField(
        max_length=15, choices=CondicaoMaterial.choices, blank=True
    )

    observacao = models.CharField(max_length=300, blank=True)

    objects = CustodiaQuerySet.as_manager()

    class Meta:
        # Mais recente primeiro. Não ordenamos por "em uso" antes: a tela já
        # separa as duas listas, e ordenação que repete o que a tela faz é a que
        # discorda dela quando uma das duas mudar.
        ordering = ["-entregue_em"]
        verbose_name = "custódia"
        verbose_name_plural = "custódias"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantidade__gt=0), name="wks_custodia_quantidade"
            ),
        ]
        indexes = [
            models.Index(fields=["pessoa", "devolvido_em"], name="wks_custodia_pessoa_idx"),
            models.Index(fields=["unidade", "devolvido_em"], name="wks_custodia_unid_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.material} · {self.pessoa}"

    @property
    def em_uso(self) -> bool:
        return self.devolvido_em is None

    @property
    def aceita(self) -> bool:
        return self.aceito_em is not None

    @property
    def espera_aceite(self) -> bool:
        return self.em_uso and not self.aceita

    @property
    def dias_em_uso(self) -> int:
        fim = self.devolvido_em or timezone.now()
        return (fim - self.entregue_em).days

    @property
    def situacao(self) -> str:
        if not self.em_uso:
            return "devolvida"
        return "em_uso" if self.aceita else "a_aceitar"

    @property
    def situacao_rotulo(self) -> str:
        return {
            "devolvida": "Devolvida",
            "em_uso": "Em uso",
            "a_aceitar": "Aguardando o aceite",
        }[self.situacao]

    @property
    def identificacao(self) -> str:
        """Patrimônio, série, ou nada — a etiqueta que a tela mostra."""
        if self.patrimonio:
            return f"pat. {self.patrimonio}"
        if self.numero_serie:
            return f"s/n {self.numero_serie}"
        return ""
