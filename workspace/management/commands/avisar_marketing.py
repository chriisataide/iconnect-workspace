"""Avisa marketing sobre prazo de decisão perto ou vencido. §23.

    python manage.py avisar_marketing --aplicar
    python manage.py avisar_marketing --dias 30 --aplicar

Comando e não sinal, pelo mesmo motivo dos outros três: o prazo não vence
porque alguém salvou um formulário — vence porque o dia passou.

O aviso é sobre o PRAZO DE DECISÃO e não sobre a data do evento, e essa é a
razão de o módulo existir: a feira de outubro tem inscrição antecipada até
junho, e avisar em setembro é avisar depois que o stand acabou.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from workspace.services import marketing as mkt


class Command(BaseCommand):
    help = "Avisa marketing sobre prazos de decisão."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Grava os avisos.")
        parser.add_argument(
            "--dias",
            type=int,
            default=mkt.DIAS_DE_ALERTA,
            help="Antecedência do alerta, em dias.",
        )

    def handle(self, *args, **opcoes):
        aplicar, dias = opcoes["aplicar"], opcoes["dias"]
        if not aplicar:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --aplicar.\n")
            )

        achados = mkt.com_prazo_estourando(dias=dias)
        for oportunidade in achados:
            estado = (
                "VENCIDO"
                if oportunidade.prazo_perdido
                else f"{oportunidade.dias_para_decidir}d"
            )
            self.stdout.write(
                f"  {estado:>8}  {oportunidade.titulo[:40]:40} "
                f"{oportunidade.prazo_decisao.strftime('%d/%m/%Y')}"
            )

        with transaction.atomic():
            enviados = mkt.avisar_prazos(dias=dias)
            if not aplicar:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Marketing · prazos"))
        self.stdout.write(f"  prazos apertados  {len(achados)}")
        self.stdout.write(f"  avisos            {enviados}")
        if aplicar:
            self.stdout.write(self.style.SUCCESS("\n✓ Aplicado."))
