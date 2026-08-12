"""Cria os papéis do Workspace.

    python manage.py semear_papeis            # relatório, sem gravar
    python manage.py semear_papeis --aplicar

Reexecutável sem duplicar: casa por `chave`. Papel cujas permissões mudaram em
`identidade/papeis.py` é atualizado; papel que alguém criou à mão e não está lá
é deixado em paz.

## O que este comando NÃO faz

Não migra `UserRole` do iConnect. Fazia, e estava errado: os 1432 registros de
`UserRole` são técnicos e clientes do **iConnect**, que é plataforma separada. O
Workspace é dos funcionários da icodev, algumas dezenas, e quem entra no organograma
é decidido no CSV do `importar_organograma` — não herdado de outra plataforma.

Atribuir papel a pessoa é ato deliberado: acontece no admin
(`/admin/identidade/atribuicaopapel/`) ou pelo CSV do organograma.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from identidade.models import Papel
from identidade.papeis import PAPEIS_V1


class Command(BaseCommand):
    help = "Semeia os papéis do Workspace em identidade.Papel."

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
            criados, atualizados, iguais = self._semear(aplicar)
            if not aplicar:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Papéis"))
        self.stdout.write(f"  criados      {criados}")
        self.stdout.write(f"  atualizados  {atualizados}")
        self.stdout.write(f"  sem mudança  {iguais}")

        if aplicar:
            self.stdout.write(self.style.SUCCESS("\n✓ Aplicado."))
            self.stdout.write(
                "  Atribua papéis em /admin/identidade/atribuicaopapel/ "
                "ou pelo CSV do organograma."
            )

    def _semear(self, aplicar: bool) -> tuple[int, int, int]:
        criados = atualizados = iguais = 0

        for spec in PAPEIS_V1:
            existente = Papel.objects.filter(chave=spec["chave"]).first()

            if existente is None:
                criados += 1
                self.stdout.write(f"  + {spec['chave']:16} {len(spec['permissoes'])} permissões")
                if aplicar:
                    Papel.objects.create(**spec)
                continue

            mudou = (
                existente.permissoes != spec["permissoes"]
                or existente.escopo_padrao != spec["escopo_padrao"]
                or existente.nome != spec["nome"]
            )
            if mudou:
                atualizados += 1
                self.stdout.write(f"  ~ {spec['chave']:16} permissões atualizadas")
                if aplicar:
                    for campo, valor in spec.items():
                        setattr(existente, campo, valor)
                    existente.save()
            else:
                iguais += 1

        return criados, atualizados, iguais
