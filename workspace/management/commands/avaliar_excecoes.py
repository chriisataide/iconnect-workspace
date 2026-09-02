"""`avaliar_excecoes [--aplicar] [--avisar]`

Roda todas as regras ativas e grava o retrato. É daqui que sai a **tendência**
que a tela mostra ao lado da contagem — uma regra que foi de 3 para 40 importa
mais que uma que está em 40 há um ano, e a contagem sozinha não conta isso.

A tela avalia ao vivo e **não escreve**. Quem escreve é este comando, e é ele
que precisa de cron. Sem cron, a tendência simplesmente não aparece: a tela
mostra a contagem de agora e omite a seta, em vez de inventar uma.

`--avisar` manda a notificação para quem responde por cada regra que achou algo.
Separado de `--aplicar` de propósito: gravar o retrato é barato e silencioso;
avisar gente é caro e acorda o sino de todo mundo. Quem agenda decide a cadência
de cada um.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from workspace.models.excecao import RegraExcecao
from workspace.services import excecoes as svc


class Command(BaseCommand):
    help = "Avalia as regras de exceção e grava o retrato."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--aplicar", action="store_true",
            help="Grava o resultado. Sem isto, só relata.",
        )
        parser.add_argument(
            "--avisar", action="store_true",
            help="Notifica quem responde pelas regras que acharam algo. "
                 "Exige --aplicar.",
        )
        parser.add_argument(
            "--regra", help="Só esta chave. Útil para depurar uma regra sozinha."
        )

    def handle(self, *args, **opcoes) -> None:
        aplicar = opcoes["aplicar"]
        regras = RegraExcecao.objects.ativas()
        if opcoes.get("regra"):
            regras = regras.filter(chave=opcoes["regra"])
            if not regras.exists():
                self.stdout.write(
                    self.style.ERROR(f"Regra {opcoes['regra']!r} não existe ou está desligada.")
                )
                return

        com_ocorrencia = nao_avaliadas = avisados = 0

        for regra in regras:
            avaliacao = svc.avaliar(regra)
            if not avaliacao.avaliada:
                nao_avaliadas += 1
                self.stdout.write(
                    self.style.WARNING(f"  ? {regra.chave:<32} {avaliacao.motivo}")
                )
            elif avaliacao.total:
                com_ocorrencia += 1
                seta = ""
                if avaliacao.variacao:
                    seta = f"  ({avaliacao.variacao:+d} desde a última)"
                self.stdout.write(f"  ! {regra.chave:<32} {avaliacao.total}{seta}")
            else:
                self.stdout.write(f"    {regra.chave:<32} sem ocorrências")

            if aplicar:
                # O retrato é gravado inclusive para a regra NÃO avaliada, com
                # a marca. Sem ele, o histórico teria um buraco onde deveria
                # ter "neste dia a fonte estava fora do ar" — e a tendência da
                # próxima avaliação compararia com um número de três dias atrás
                # como se fosse de ontem.
                svc.registrar_resultado(avaliacao)

            if aplicar and opcoes["avisar"] and avaliacao.avaliada and avaliacao.total:
                avisados += svc.notificar(avaliacao)

        resumo = (
            f"{regras.count()} regra(s) · {com_ocorrencia} com ocorrência · "
            f"{nao_avaliadas} não avaliada(s)"
            + (f" · {avisados} aviso(s)" if opcoes["avisar"] else "")
        )
        if aplicar:
            self.stdout.write(self.style.SUCCESS(resumo))
        else:
            self.stdout.write(self.style.WARNING(f"SIMULAÇÃO — {resumo}"))
            self.stdout.write("Rode de novo com --aplicar para gravar o retrato.")
