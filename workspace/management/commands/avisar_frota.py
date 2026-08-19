"""Avisa quem opera a frota sobre documento vencido ou vencendo. §18.

    python manage.py avisar_frota --aplicar
    python manage.py avisar_frota --dias 45 --aplicar

Comando e não sinal, pelo mesmo motivo de `avisar_habilitacoes`: documento não
vence porque alguém salvou um formulário — vence porque o dia passou. Não há
evento no sistema no instante certo, então quem dispara é o relógio.

Diário é o certo. O `criar()` deduplica por aviso NÃO LIDO, então rodar todo dia
não produz trinta cópias do mesmo alerta: quem já viu e não leu continua com um.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from workspace.services import frota as frt


class Command(BaseCommand):
    help = "Avisa a frota sobre documentos vencidos ou vencendo."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Grava os avisos.")
        parser.add_argument(
            "--dias",
            type=int,
            default=frt.DIAS_DE_ALERTA,
            help="Antecedência do alerta, em dias.",
        )

    def handle(self, *args, **opcoes):
        aplicar, dias = opcoes["aplicar"], opcoes["dias"]
        if not aplicar:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --aplicar.\n")
            )

        achados = frt.com_prazo_estourando(dias=dias)
        for achado in achados:
            veiculo, prazo = achado["veiculo"], achado["prazo"]
            estado = "VENCIDO" if prazo["vencido"] else f"{prazo['dias']}d"
            self.stdout.write(
                f"  {veiculo.placa:9} {prazo['rotulo']:15} {estado:>8}  "
                f"{prazo['data'].strftime('%d/%m/%Y')}"
            )

        with transaction.atomic():
            enviados = frt.avisar_vencimentos(dias=dias)
            if not aplicar:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Frota · documentos"))
        self.stdout.write(f"  prazos estourando  {len(achados)}")
        self.stdout.write(f"  avisos             {enviados}")
        if aplicar:
            self.stdout.write(self.style.SUCCESS("\n✓ Aplicado."))
