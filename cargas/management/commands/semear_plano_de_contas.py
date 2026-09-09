"""O plano de contas da ADB.

Comando próprio, e não parte de `semear_resultados`, pela mesma razão de
`semear_areas`: o plano é **cadastro de produção**, e a massa é demonstração.
Limpar a massa não pode apagar a estrutura contábil — e rodar o seeder de massa
em produção não deve nem parecer razoável.

Idempotente por CÓDIGO: rodar de novo atualiza nome, natureza e degrau, e nunca
duplica. Recriar mudaria o `pk` e soltaria todo lançamento apontado para a
conta — `PROTECT` impediria, e o comando falharia no meio.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from resultados.models import ContaContabil
from resultados.plano_de_contas import PLANO, codigo_analitico


class Command(BaseCommand):
    help = "Cria ou atualiza o plano de contas."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Grava. Sem isto, apenas mostra o que faria.",
        )

    def handle(self, *args, **opcoes) -> None:
        aplicar = opcoes["aplicar"]
        criadas = atualizadas = iguais = 0

        with transaction.atomic():
            ordem_grupo = 0
            for codigo, nome, natureza, degrau, analiticas in PLANO:
                ordem_grupo += 1
                grupo, estado = self._gravar(
                    codigo, nome, natureza, degrau, None, ordem_grupo, aplicar
                )
                criadas += estado == "criada"
                atualizadas += estado == "atualizada"
                iguais += estado == "igual"

                for i, nome_analitica in enumerate(analiticas):
                    _, estado = self._gravar(
                        codigo_analitico(codigo, i),
                        nome_analitica,
                        natureza,
                        # O DEGRAU FICA VAZIO na analítica: ela herda do grupo,
                        # via `ContaContabil.degrau`. Copiar seria vinte lugares
                        # para divergir, e o vigésimo primeiro nasceria sem.
                        "",
                        grupo,
                        i + 1,
                        aplicar,
                    )
                    criadas += estado == "criada"
                    atualizadas += estado == "atualizada"
                    iguais += estado == "igual"

            if not aplicar:
                transaction.set_rollback(True)

        self.stdout.write(
            f"{criadas} criada(s) · {atualizadas} atualizada(s) · "
            f"{iguais} sem mudança"
        )
        if not aplicar:
            self.stdout.write(self.style.WARNING("SIMULAÇÃO — nada foi gravado."))

    def _gravar(self, codigo, nome, natureza, degrau, pai, ordem, aplicar):
        """Devolve `(conta, "criada" | "atualizada" | "igual")`.

        `conta` é `None` em simulação de conta nova — e por isso o laço acima
        passa esse `None` como pai das analíticas. Não é problema: em simulação
        nada é gravado, e um pai nulo numa gravação que não acontece não deixa
        rastro. Gravar de verdade para poder simular seria pior.
        """
        existente = ContaContabil.objects.filter(codigo=codigo).first()
        if existente is None:
            self.stdout.write(f"  + {codigo}  {nome}")
            if not aplicar:
                return None, "criada"
            return (
                ContaContabil.objects.create(
                    codigo=codigo, nome=nome, natureza=natureza,
                    degrau_dre=degrau, pai=pai, ordem=ordem,
                ),
                "criada",
            )

        mudou = (
            existente.nome != nome
            or existente.natureza != natureza
            or existente.degrau_dre != degrau
            or existente.pai_id != (pai.pk if pai else None)
            or existente.ordem != ordem
        )
        if not mudou:
            return existente, "igual"

        self.stdout.write(f"  ~ {codigo}  {nome}")
        if aplicar:
            existente.nome = nome
            existente.natureza = natureza
            existente.degrau_dre = degrau
            existente.pai = pai
            existente.ordem = ordem
            existente.save(
                update_fields=["nome", "natureza", "degrau_dre", "pai", "ordem"]
            )
        return existente, "atualizada"
