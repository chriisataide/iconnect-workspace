"""Avisa quem está com habilitação vencendo ou vencida — §28 e §31.

    python manage.py avisar_habilitacoes            # relatório
    python manage.py avisar_habilitacoes --aplicar

Feito para rodar TODO DIA, por cron. É o desenho: um alerta semanal deixaria o
degrau de 7 dias virar 7-a-13, e o de 7 existe justamente para ser o último
aviso antes de a pessoa perder a habilitação.

## Rodar diariamente sem virar spam

A repetição é resolvida na Central de Notificações, que deduplica o NÃO LIDO. Um
aviso que a pessoa ainda não leu não é recriado no dia seguinte; se ela leu e o
vencimento avançou para o degrau seguinte, o novo aviso É evento novo e chega —
que é exatamente o comportamento desejado.

O degrau entra em `origem_id` para isso funcionar: 30, 15, 7 e vencido são
quatro eventos distintos do mesmo vencimento.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from workspace.services import habilitacao as hab


class Command(BaseCommand):
    help = "Avisa sobre habilitações vencendo ou vencidas."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Envia os avisos.")

    def handle(self, *args, **opcoes):
        aplicar = opcoes["aplicar"]
        if not aplicar:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada será enviado. Use --aplicar.\n")
            )

        avisos = hab.avisos_a_enviar()
        for aviso in avisos:
            marca = "!" if aviso.critico else " "
            quando = (
                f"venceu há {abs(aviso.dias)}d" if aviso.critico else f"vence em {aviso.dias}d"
            )
            self.stdout.write(
                f"  {marca} {aviso.matricula.pessoa} · {aviso.matricula.curso} · {quando}"
            )

        pessoas = gestores = 0
        if aplicar:
            with transaction.atomic():
                pessoas, gestores = hab.enviar_avisos()

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Habilitações"))
        self.stdout.write(f"  a avisar     {len(avisos)}")
        self.stdout.write(f"  vencidas     {sum(1 for a in avisos if a.critico)}")
        if aplicar:
            self.stdout.write(f"  avisos à pessoa       {pessoas}")
            self.stdout.write(f"  avisos a quem responde {gestores}")
            self.stdout.write(self.style.SUCCESS("\n✓ Enviado."))
