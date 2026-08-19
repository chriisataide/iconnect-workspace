"""Cria as salas, veículos e equipamentos reserváveis.

    python manage.py semear_recursos --aplicar

Existe pela mesma razão de `semear_estoque`: sem recurso nenhum, a tela de
reservas mostra o estado vazio e não há como testar a grade de disponibilidade
nem descobrir que ela funciona. Foi assim, abrindo a tela, que a falta disto
apareceu.

Os recursos são plausíveis e **inventados** — nome, capacidade e unidade devem
ser trocados pelos de verdade. O que não é inventado é a forma: sala pequena
tem duração máxima menor que auditório, porque sala de duas pessoas presa o dia
inteiro é o jeito mais rápido de a agenda perder a utilidade.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from identidade.models import Unidade
from workspace.models.reserva import Recurso, TipoRecurso

RECURSOS = [
    ("sala-reuniao-1", "Sala de reunião 1", TipoRecurso.SALA, 8, 4,
     "Projetor e videoconferência"),
    ("sala-reuniao-2", "Sala de reunião 2", TipoRecurso.SALA, 6, 4, "Quadro branco"),
    ("sala-rapida", "Sala rápida", TipoRecurso.SALA, 2, 1,
     "Para ligação — reserva curta"),
    ("auditorio", "Auditório", TipoRecurso.SALA, 40, 8, "Treinamento e apresentação"),
    ("sala-treinamento", "Sala de treinamento", TipoRecurso.SALA, 20, 8,
     "Bancadas e tomadas"),
    ("van-1", "Van 1", TipoRecurso.VEICULO, 12, 12, "Equipe de campo"),
    ("utilitario-1", "Utilitário 1", TipoRecurso.VEICULO, 3, 12, "Carga e ferramenta"),
    ("projetor-portatil", "Projetor portátil", TipoRecurso.EQUIPAMENTO, None, 8, ""),
    ("kit-videoconferencia", "Kit de videoconferência", TipoRecurso.EQUIPAMENTO,
     None, 8, "Câmera, microfone e tripé"),
]


class Command(BaseCommand):
    help = "Semeia salas, veículos e equipamentos reserváveis."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Grava.")

    def handle(self, *args, **opcoes):
        aplicar = opcoes["aplicar"]
        if not aplicar:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --aplicar.\n")
            )

        # A unidade é OPCIONAL no modelo: recurso sem unidade vale para a
        # empresa toda. Por isso o comando não recusa banco sem unidade — ao
        # contrário de `semear_estoque`, onde o saldo não teria onde morar.
        unidade = Unidade.objects.order_by("pk").first()

        with transaction.atomic():
            criados, existentes = self._semear(unidade, aplicar)
            if not aplicar:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Recursos"))
        self.stdout.write(f"  criados      {criados}")
        self.stdout.write(f"  já existiam  {existentes}")
        if aplicar:
            self.stdout.write(self.style.SUCCESS("\n✓ Aplicado."))

    def _semear(self, unidade, aplicar: bool):
        criados = existentes = 0
        for codigo, nome, tipo, capacidade, horas, descricao in RECURSOS:
            if Recurso.objects.filter(codigo=codigo).exists():
                existentes += 1
                continue

            criados += 1
            self.stdout.write(f"  + {codigo:22} {nome:28} {tipo}")
            if aplicar:
                Recurso.objects.create(
                    codigo=codigo, nome=nome, tipo=tipo, capacidade=capacidade,
                    duracao_maxima_horas=horas, descricao=descricao,
                    unidade=unidade,
                )
        return criados, existentes
