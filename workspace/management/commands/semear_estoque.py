"""Cria um cadastro mínimo de materiais e um saldo inicial.

    python manage.py semear_estoque --aplicar

Existe pela mesma razão de `semear_catalogo`: sem material nenhum cadastrado, a
requisição do §16 mostra um `<select>` vazio, e não há como testar o fluxo de
ponta a ponta — nem descobrir que ele funciona.

Os materiais são os que aparecem em toda operação de campo. **Não são dado
real**: quantidade, mínimo e localização são plausíveis e inventados, e a
empresa deve substituí-los pelo inventário de verdade.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from identidade.models import Unidade
from workspace.models.estoque import Material, TipoMovimento, UnidadeMedida
from workspace.services import estoque as est

MATERIAIS = [
    ("capacete", "Capacete de segurança", "epi", UnidadeMedida.UNIDADE, 5, 20),
    ("luva-nitrilica", "Luva nitrílica", "epi", UnidadeMedida.PAR, 20, 80),
    ("bota-seguranca", "Bota de segurança", "epi", UnidadeMedida.PAR, 6, 24),
    ("colete-refletivo", "Colete refletivo", "epi", UnidadeMedida.UNIDADE, 10, 35),
    ("camisa-uniforme", "Camisa do uniforme", "uniforme", UnidadeMedida.UNIDADE, 15, 60),
    ("cabo-utp", "Cabo UTP cat6 (caixa 305m)", "rede", UnidadeMedida.CAIXA, 2, 7),
    ("conector-rj45", "Conector RJ45", "rede", UnidadeMedida.UNIDADE, 100, 500),
    ("cadeado", "Cadeado", "obra", UnidadeMedida.UNIDADE, 5, 12),
    ("fita-isolante", "Fita isolante", "obra", UnidadeMedida.UNIDADE, 10, 40),
    ("papel-a4", "Papel A4 (resma)", "papelaria", UnidadeMedida.UNIDADE, 5, 25),
]


class Command(BaseCommand):
    help = "Semeia materiais e saldo inicial de estoque."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Grava.")

    def handle(self, *args, **opcoes):
        aplicar = opcoes["aplicar"]
        if not aplicar:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --aplicar.\n")
            )

        # TODAS as unidades, e não só a primeira.
        #
        # Semear uma só parecia suficiente e não é: o saldo é POR UNIDADE, e a
        # requisição só oferece o que existe na unidade de quem pede. Com uma
        # unidade semeada e as pessoas lotadas em outra, o `<select>` de material
        # aparece vazio — o comando "funcionou" e o fluxo continuou intestável.
        unidades = list(Unidade.objects.order_by("pk"))
        if not unidades:
            self.stdout.write(
                self.style.ERROR(
                    "Nenhuma unidade cadastrada — o saldo é POR UNIDADE e não teria onde "
                    "morar. Rode `semear_perfis --aplicar` antes."
                )
            )
            return

        with transaction.atomic():
            criados, existentes = self._semear(unidades, aplicar)
            if not aplicar:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"Estoque · {len(unidades)} unidade(s): "
                + ", ".join(u.nome for u in unidades)
            )
        )
        self.stdout.write(f"  criados      {criados}")
        self.stdout.write(f"  já existiam  {existentes}")
        if aplicar:
            self.stdout.write(self.style.SUCCESS("\n✓ Aplicado."))

    def _semear(self, unidades, aplicar: bool):
        criados = existentes = 0
        for codigo, nome, categoria, medida, minimo, inicial in MATERIAIS:
            if Material.objects.filter(codigo=codigo).exists():
                existentes += 1
                continue

            criados += 1
            self.stdout.write(f"  + {codigo:20} {nome:32} {inicial} {medida}")
            if not aplicar:
                continue

            material = Material.objects.create(
                codigo=codigo, nome=nome, categoria=categoria,
                unidade_medida=medida, estoque_minimo=minimo,
            )
            for posicao, unidade in enumerate(unidades):
                # A matriz recebe o lote cheio e as bases uma fração. Não é
                # capricho: saldo idêntico em toda unidade esconderia o bug
                # clássico deste módulo, que é a conta somar a empresa inteira
                # em vez de olhar a unidade de quem pede.
                quantidade = inicial if posicao == 0 else max(1, inicial // 3)
                # Entrada e não `SaldoEstoque` direto: o saldo é atalho, o razão
                # é a verdade. Saldo inicial sem linha de razão nasceria já sem
                # explicação, e a conferência acusaria divergência no dia um.
                est.movimentar(
                    material, unidade, TipoMovimento.ENTRADA, quantidade,
                    observacao="Saldo inicial da semente.",
                )
        return criados, existentes
