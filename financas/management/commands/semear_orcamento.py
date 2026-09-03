"""A carga inicial do orçamento anual — do teto avulso para o ano montado.

## O que ele faz

Cada `CentroCusto` tem hoje um `orcamento_mensal`: um número, sem ano e sem
histórico. Este comando cria o `OrcamentoAnual` do ano pedido com **doze linhas
iguais a esse número** e o põe em vigor.

É a "carga inicial importada" que o benchmark prevê para o orçamento (§5), e é o
que faz a grade anual nascer com dado real em vez de doze traços.

## Por que doze linhas iguais, e não uma curva

Porque inventar sazonalidade seria inventar dado. Doze iguais é o que o produto
sabe hoje — e a primeira revisão de verdade é quem vai corrigir julho.

## O que ele NÃO faz

Não toca em orçamento que já existe, em nenhuma situação. Um ano já montado é
decisão de quem opera, e sobrescrevê-lo no deploy seguinte apagaria revisões.

Não apaga `CentroCusto.orcamento_mensal`. O campo continua sendo o fallback de
todo centro de custo que ainda não tiver o ano montado — arrancá-lo quebraria a
bandeja de aprovação no dia do deploy.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from financas.models import (
    CentroCusto,
    LinhaOrcamento,
    OrcamentoAnual,
    SituacaoOrcamento,
)


class Command(BaseCommand):
    help = "Importa o teto avulso de cada centro de custo para um orçamento anual."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--aplicar", action="store_true")
        parser.add_argument("--ano", type=int, default=0)

    def handle(self, *args, **opcoes) -> None:
        aplicar = opcoes["aplicar"]
        ano = opcoes["ano"] or timezone.localdate().year
        criados = pulados = sem_teto = 0

        with transaction.atomic():
            for centro in CentroCusto.objects.ativos().order_by("codigo"):
                if OrcamentoAnual.objects.filter(centro_custo=centro, ano=ano).exists():
                    pulados += 1
                    continue
                if centro.orcamento_mensal is None:
                    # Sem teto avulso não há o que importar — e criar um ano de
                    # zeros seria pior: a bandeja passaria a dizer "0% de folga"
                    # onde hoje ela diz, corretamente, "sem orçamento definido".
                    sem_teto += 1
                    self.stdout.write(f"  ~ {centro.codigo}: sem teto definido")
                    continue

                criados += 1
                self.stdout.write(
                    f"  + {centro.codigo}: 12 × R$ {centro.orcamento_mensal}"
                )
                if not aplicar:
                    continue

                orcamento = OrcamentoAnual.objects.create(
                    centro_custo=centro,
                    ano=ano,
                    situacao=SituacaoOrcamento.VIGENTE,
                    observacao=(
                        "Importado do teto mensal avulso. Doze meses iguais — "
                        "a sazonalidade entra na primeira revisão."
                    ),
                    vigorou_em=timezone.now(),
                )
                LinhaOrcamento.objects.bulk_create(
                    LinhaOrcamento(
                        orcamento=orcamento, mes=mes,
                        valor=centro.orcamento_mensal,
                    )
                    for mes in range(1, 13)
                )

            if not aplicar:
                transaction.set_rollback(True)

        resumo = (
            f"{criados} orçamento(s) de {ano} criado(s), {pulados} já existiam, "
            f"{sem_teto} centro(s) sem teto definido."
        )
        if aplicar:
            self.stdout.write(self.style.SUCCESS(resumo))
        else:
            self.stdout.write(self.style.WARNING(f"SIMULAÇÃO — {resumo}"))
            self.stdout.write("Rode de novo com --aplicar para gravar.")
