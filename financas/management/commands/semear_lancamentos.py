"""Lançamentos de demonstração, para o orçado × realizado ter série.

    python manage.py semear_lancamentos --aplicar

## Por que ela mora aqui, e não junto com o resto da demonstração

`semear_demonstracao`, no app `workspace`, enche as telas que as outras
semeadoras deixam vazias — e `Lancamento` é uma delas. Mas `workspace` é a
FOLHA da árvore de dependências: ele não importa app de domínio, consome tudo
por provider. Um `from financas.models import Lancamento` lá dentro derruba
`test_workspace_nao_importa_app_de_dominio`, e com razão — a regra existe para
que a superfície não passe a conhecer o domínio pela porta dos fundos.

Então a parte que escreve em `financas` mora em `financas`. O mesmo vale para
os editais, que moram em `cargas` pelo mesmo motivo.

## O que ela NÃO é

Não é dado real. Descrição e valor são inventados e plausíveis, e nenhum deles
deve sobreviver ao primeiro dado de verdade.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from financas.models import CentroCusto, Lancamento


class Command(BaseCommand):
    help = "Semeia lançamentos de demonstração nos centros de custo existentes."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--aplicar", action="store_true", help="Grava.")

    def handle(self, *args, **opcoes) -> None:
        aplicar = opcoes["aplicar"]
        if not aplicar:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --aplicar.\n")
            )

        hoje = timezone.localdate()
        centros = {c.codigo: c for c in CentroCusto.objects.all()}
        if not centros:
            self.stdout.write(
                self.style.ERROR(
                    "Nenhum CentroCusto cadastrado — um lançamento precisa de onde "
                    "morar. Rode `semear_centros_custo --aplicar` antes."
                )
            )
            return

        # Por centro de custo: (descrição, valor base, variação por mês).
        #
        # A variação é determinística e não aleatória: o gráfico de orçado ×
        # realizado precisa da mesma série toda vez que alguém abrir a tela,
        # senão duas pessoas olhando o mesmo mês veem números diferentes.
        linhas = {
            "1000": [
                ("Assessoria jurídica e contábil", 28000, 900),
                ("Software de gestão e licenças", 14500, 350),
                ("Viagens e representação da diretoria", 9800, 1700),
                ("Serviços de auditoria externa", 12000, 600),
            ],
            "1042": [
                ("Folha do efetivo operacional — Matriz", 52000, 1400),
                ("Combustível e manutenção da frota", 9600, 850),
                ("Uniformes e EPI", 6200, 700),
                ("Locação de rádios e equipamentos", 4800, 300),
            ],
            "1055": [
                ("Folha do efetivo operacional — Base Salvador", 78000, 2100),
                ("Manutenção de CFTV e alarme", 15400, 1200),
                ("Combustível e pedágio da Base", 8300, 640),
                ("Aluguel e condomínio da Base", 11200, 180),
            ],
        }

        criados = existiam = 0
        with transaction.atomic():
            for codigo, itens in linhas.items():
                centro = centros.get(codigo)
                if centro is None:
                    continue
                # Só até o mês corrente: realizado de mês futuro é dinheiro que
                # ainda não saiu, e a série de orçado × realizado ficaria
                # mentindo exatamente onde ela é mais lida.
                for mes in range(1, hoje.month + 1):
                    for posicao, (descricao, base, passo) in enumerate(itens):
                        # Sobe ao longo do ano e oscila por item: uma série
                        # plana vira uma reta, e reta não mostra nada.
                        valor = base + passo * ((mes + posicao * 5) % 7) + passo * (mes // 3)
                        _, criado = Lancamento.objects.get_or_create(
                            centro_custo=centro,
                            competencia=date(hoje.year, mes, 1),
                            descricao=descricao,
                            defaults={"valor": Decimal(valor).quantize(Decimal("0.01"))},
                        )
                        criados += criado
                        existiam += not criado

            if not aplicar:
                transaction.set_rollback(True)

        self.stdout.write(f"  criados      {criados}")
        self.stdout.write(f"  já existiam  {existiam}")
        self.stdout.write(
            self.style.SUCCESS("\n✓ Aplicado.") if aplicar
            else self.style.WARNING("\nSIMULAÇÃO — rode de novo com --aplicar.")
        )
