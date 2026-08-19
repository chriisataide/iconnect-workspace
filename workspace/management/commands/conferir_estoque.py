"""Compara o saldo gravado com a soma do razão. §58.

    python manage.py conferir_estoque
    python manage.py conferir_estoque --unidade SP

`estoque.conferir_razao()` existia desde a onda de Suprimentos com uma docstring
explícita — *"existe para que a divergência seja DETECTÁVEL"* — e **nenhum
chamador**. A função que detecta a divergência não era executada por ninguém, o
que é a mesma coisa que não detectar.

O saldo é atalho e o razão é a verdade. Quando os dois discordam, quem está
certo é o razão — e a diferença só nasce por caminho que não passou pelo
serviço: um `update()` numa migração de dados, uma correção feita no shell.
Sem esta conferência, ela apareceria na contagem física do ano seguinte, sem
nenhuma pista de quando começou.

Somente leitura, de propósito. Corrigir automaticamente esconderia o defeito de
origem, e a correção certa é uma CONTAGEM de inventário — que tem autor, fica no
razão e pode ser explicada depois.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from identidade.models import Unidade
from workspace.models.estoque import Material, SaldoEstoque
from workspace.services import estoque as est


class Command(BaseCommand):
    help = "Confere saldo contra razão e lista as divergências."

    def add_arguments(self, parser):
        parser.add_argument(
            "--unidade", default="", help="Código da unidade. Vazio confere todas."
        )

    def handle(self, *args, **opcoes):
        codigo = (opcoes["unidade"] or "").strip()
        linhas = SaldoEstoque.objects.select_related("material", "unidade")
        if codigo:
            unidade = Unidade.objects.filter(codigo__iexact=codigo).first()
            if unidade is None:
                self.stdout.write(self.style.ERROR(f"Unidade {codigo!r} não existe."))
                return
            linhas = linhas.filter(unidade=unidade)

        divergentes = 0
        conferidos = 0
        for linha in linhas:
            gravado, somado = est.conferir_razao(linha.material, linha.unidade)
            conferidos += 1
            if gravado == somado:
                continue
            divergentes += 1
            self.stdout.write(
                self.style.ERROR(
                    f"  {linha.unidade.codigo:6} {linha.material.codigo:22} "
                    f"saldo {gravado:>6}   razão {somado:>6}   "
                    f"diferença {gravado - somado:+}"
                )
            )

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Estoque · conferência"))
        self.stdout.write(f"  linhas conferidas  {conferidos}")
        self.stdout.write(f"  divergências       {divergentes}")
        if divergentes:
            self.stdout.write(
                self.style.WARNING(
                    "\nO razão é a verdade. Corrija por CONTAGEM DE INVENTÁRIO na tela "
                    "de estoque — ela grava a correção com autor e motivo, e um "
                    "`update()` no banco recria a divergência sem deixar rastro."
                )
            )
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ Saldo e razão batem."))
