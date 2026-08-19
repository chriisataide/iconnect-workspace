"""Cria uma frota mínima, amarrada aos recursos que já existem.

    python manage.py semear_frota --aplicar

Existe pela mesma razão de `semear_estoque` e `semear_recursos`: sem veículo
nenhum a tela da frota mostra o estado vazio, e não há como testar o consumo
nem descobrir que ele funciona.

**O ponto do comando não é criar carros — é amarrá-los.** Cada veículo de uso
comum aponta para o `Recurso` da grade de Reservas que já existe (`van-1`,
`utilitario-1`). Sem esse elo, o banco de demonstração nasceria com duas listas
de veículos, que é exatamente a duplicação que o §18 encontrou e desfez.

Placa, ano e prazos são **inventados** e plausíveis. Os prazos nascem
espalhados de propósito: um vencido, um vencendo e um longe, para que a tela e
o aviso tenham o que mostrar nos três estados.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from identidade.models import Unidade
from workspace.models.frota import TipoVeiculo, Veiculo
from workspace.models.reserva import Recurso, TipoRecurso

#: `(placa, modelo, marca, ano, tipo, codigo_do_recurso, km, dias_do_licenciamento)`
#:
#: `dias` negativo = já vencido. Os três estados aparecem de propósito.
VEICULOS = [
    ("RTA1B23", "Ducato", "Fiat", 2021, TipoVeiculo.VAN, "van-1", 84210, -12),
    ("RTB2C34", "Saveiro", "Volkswagen", 2022, TipoVeiculo.UTILITARIO,
     "utilitario-1", 41880, 18),
    ("RTC3D45", "Onix", "Chevrolet", 2023, TipoVeiculo.CARRO, "", 22140, 210),
]


class Command(BaseCommand):
    help = "Semeia veículos da frota, ligados aos recursos reserváveis."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Grava.")

    def handle(self, *args, **opcoes):
        aplicar = opcoes["aplicar"]
        if not aplicar:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --aplicar.\n")
            )

        unidade = Unidade.objects.order_by("pk").first()
        hoje = timezone.localdate()

        with transaction.atomic():
            criados, existentes, ligados = self._semear(unidade, hoje, aplicar)
            if not aplicar:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Frota"))
        self.stdout.write(f"  criados            {criados}")
        self.stdout.write(f"  já existiam        {existentes}")
        self.stdout.write(f"  ligados à reserva  {ligados}")
        if aplicar:
            self.stdout.write(self.style.SUCCESS("\n✓ Aplicado."))

    def _semear(self, unidade, hoje, aplicar: bool):
        criados = existentes = ligados = 0
        for placa, modelo, marca, ano, tipo, codigo, km, dias in VEICULOS:
            if Veiculo.objects.filter(placa=placa).exists():
                existentes += 1
                continue

            recurso = (
                Recurso.objects.filter(codigo=codigo, tipo=TipoRecurso.VEICULO).first()
                if codigo
                else None
            )
            # Recurso já amarrado a outra placa não é reusado: o `OneToOne`
            # recusaria, e reusar seria justamente criar a segunda ficha.
            if recurso is not None and Veiculo.objects.filter(recurso=recurso).exists():
                recurso = None

            criados += 1
            ligados += 1 if recurso is not None else 0
            elo = recurso.nome if recurso is not None else "fora da grade"
            self.stdout.write(f"  + {placa:9} {modelo:12} {km:>7} km   {elo}")
            if not aplicar:
                continue

            Veiculo.objects.create(
                placa=placa,
                modelo=modelo,
                marca=marca,
                ano=ano,
                tipo=tipo,
                unidade=unidade,
                recurso=recurso,
                km_atual=km,
                licenciamento_ate=hoje + timedelta(days=dias),
                seguro_ate=hoje + timedelta(days=dias + 120),
                ipva_ate=hoje + timedelta(days=dias + 200),
            )
        return criados, existentes, ligados
