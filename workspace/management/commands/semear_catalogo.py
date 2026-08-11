"""Cria os itens iniciais do catálogo de serviços.

    python manage.py semear_catalogo            # relatório
    python manage.py semear_catalogo --aplicar

Reexecutável sem duplicar: casa por `chave`. Item que alguém ajustou no admin
NÃO é sobrescrito — só os campos que a semente define e que estão diferentes do
que ela diz. Um item criado à mão fica em paz.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from workspace.catalogo_inicial import CATALOGO_INICIAL
from workspace.models.catalogo import ItemCatalogo


class Command(BaseCommand):
    help = "Semeia o catálogo de serviços."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Grava.")

    def handle(self, *args, **opcoes):
        aplicar = opcoes["aplicar"]
        if not aplicar:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --aplicar.\n")
            )

        with transaction.atomic():
            criados, existentes, invalidos = self._semear(aplicar)
            if not aplicar:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Catálogo"))
        self.stdout.write(f"  criados      {criados}")
        self.stdout.write(f"  já existiam  {existentes}")

        if invalidos:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR(f"  INVÁLIDOS · {len(invalidos)}"))
            for chave, motivo in invalidos:
                self.stdout.write(f"     {chave}: {motivo}")

        if aplicar and not invalidos:
            self.stdout.write(self.style.SUCCESS("\n✓ Aplicado."))

    def _semear(self, aplicar: bool):
        criados = existentes = 0
        invalidos: list[tuple[str, str]] = []

        for spec in CATALOGO_INICIAL:
            if ItemCatalogo.objects.filter(chave=spec["chave"]).exists():
                existentes += 1
                continue

            item = ItemCatalogo(**spec)
            try:
                # Valida ANTES de gravar: item com 5 campos obrigatórios entraria
                # e só seria descoberto quando alguém tentasse usar.
                item.full_clean(exclude=["id"])
            except Exception as erro:  # ValidationError
                mensagens = getattr(erro, "messages", [str(erro)])
                invalidos.append((spec["chave"], mensagens[0]))
                continue

            criados += 1
            grupo = spec["grupo"]
            self.stdout.write(f"  + {spec['chave']:24} {grupo}")
            if aplicar:
                item.save()

        return criados, existentes, invalidos
