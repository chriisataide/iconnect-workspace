"""Cria os centros de custo que o organograma já usa.

    python manage.py semear_centros_custo            # relatório, sem gravar
    python manage.py semear_centros_custo --aplicar

## Por que existe

`Lotacao.centro_custo_codigo` era semeado; `CentroCusto` não era. O resultado é
um ambiente onde toda pessoa tem um código e nenhum código existe — e a
consequência aparece longe daqui, na bandeja de aprovação: "o CC 1042 não tem
orçamento mensal definido, não consigo calcular o impacto desta aprovação".
Quem estava testando o fluxo de aprovação lia isso e concluía que a barra de
orçamento estava quebrada. Não estava: não havia o que ler.

Os códigos saem das LOTAÇÕES que existem no banco, e não de uma lista escrita
aqui. Lista fixa divergiria do organograma no dia seguinte ao primeiro CSV
importado; assim, um código novo no organograma vira um centro no primeiro
`--aplicar`.

O orçamento fica em branco de propósito. Ele é decisão do Financeiro, não do
seeder — e "não definido" é o que a bandeja precisa dizer enquanto ninguém
decidiu. Definir um número aqui inventaria folga que a empresa não tem.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from financas.models import CentroCusto

#: Nome legível para os códigos que o `semear_organograma` planta. Código que
#: não estiver aqui entra com o próprio código como nome — feio e correto, e o
#: R.H. renomeia na tela de Pessoas.
NOMES = {
    "1000": "Diretoria",
    "1042": "Operações · Matriz",
    "1055": "Operações · Base Salvador",
}


class Command(BaseCommand):
    help = "Cria um CentroCusto para cada código usado nas lotações."

    def add_arguments(self, parser):
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Grava. Sem esta flag, só relata o que faria.",
        )

    def handle(self, *args, **opcoes):
        aplicar = opcoes["aplicar"]
        if not aplicar:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --aplicar.\n")
            )

        with transaction.atomic():
            criados, iguais = self._semear(aplicar)
            if not aplicar:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Centros de custo"))
        self.stdout.write(f"  criados      {criados}")
        self.stdout.write(f"  já existiam  {iguais}")
        if aplicar and criados:
            self.stdout.write(
                self.style.SUCCESS(
                    "\n✓ Aplicado. Defina o orçamento de cada um em "
                    "Workspace › Pessoas e papéis › Centros de custo."
                )
            )

    def _semear(self, aplicar: bool) -> tuple[int, int]:
        # Importado aqui e não no topo: este app não depende de `identidade`
        # em tempo de importação, e o comando é a única coisa que precisa.
        from identidade.models import Lotacao

        codigos = sorted(
            c
            for c in Lotacao.objects.exclude(centro_custo_codigo="")
            .values_list("centro_custo_codigo", flat=True)
            .distinct()
            if c
        )

        criados = iguais = 0
        for codigo in codigos:
            if CentroCusto.objects.filter(codigo=codigo).exists():
                iguais += 1
                self.stdout.write(f"  = {codigo}")
                continue
            criados += 1
            self.stdout.write(self.style.SUCCESS(f"  + {codigo} · {NOMES.get(codigo, codigo)}"))
            if aplicar:
                CentroCusto.objects.create(
                    codigo=codigo, nome=NOMES.get(codigo, codigo), orcamento_mensal=None
                )
        return criados, iguais
