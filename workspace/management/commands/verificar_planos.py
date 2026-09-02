"""A conferência do vencimento — o que faz o plano medir resultado, e não esforço.

## O que ele faz

Para cada plano aberto cujo prazo já passou (mais a carência), roda **a mesma
regra** e procura **a mesma chave de ocorrência**. Se ela ainda está lá, o plano
fecha como *não resolvido*. Se sumiu, *resolvido*.

Ninguém opina. É a única forma de o número da tela significar alguma coisa: um
painel em que o próprio interessado declara o sucesso mede quem preenche
formulário.

## Fonte fora do ar NÃO fecha plano

A verificação fica registrada como **não avaliada** e o plano continua aberto,
esperando a próxima rodada. Sem isso, um conector caído fecharia como resolvido
todo plano que dependesse dele — um mês inteiro de metas batidas por causa de
uma credencial vencida.

## Por que existe carência

O cron pode ter ficado fora do ar. Fechar um plano no primeiro dia em que a
máquina voltou, com a fonte ainda subindo, produziria um desfecho aleatório —
e desfecho aleatório num registro que ninguém revisa é pior que desfecho
nenhum.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from workspace.services import planos as svc


class Command(BaseCommand):
    help = "Confere os planos de ação vencidos e grava o desfecho."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--aplicar", action="store_true")

    def handle(self, *args, **opcoes) -> None:
        aplicar = opcoes["aplicar"]
        vencidos = svc.vencidos_para_verificar()
        resolvidos = nao_resolvidos = adiados = 0

        for plano in vencidos:
            if not aplicar:
                # A simulação NÃO chama `verificar()`: ela grava uma linha de
                # `VerificacaoPlano`, e uma simulação que escreve no banco não é
                # simulação. O que ela mostra é o que seria conferido.
                self.stdout.write(
                    f"  ? {plano.regra_chave} · {plano.titulo} "
                    f"(venceu em {plano.prazo:%d/%m/%Y})"
                )
                continue

            antes = plano.situacao
            svc.concluir_pelo_prazo(plano)
            if plano.situacao == antes:
                adiados += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  ~ {plano.titulo}: fonte indisponível — continua aberto."
                    )
                )
            elif plano.situacao == "resolvido":
                resolvidos += 1
                self.stdout.write(self.style.SUCCESS(f"  ✓ {plano.titulo}"))
            else:
                nao_resolvidos += 1
                self.stdout.write(f"  ✗ {plano.titulo}: a regra ainda encontra.")

        if aplicar:
            self.stdout.write(
                self.style.SUCCESS(
                    f"{resolvidos} resolvido(s), {nao_resolvidos} não resolvido(s), "
                    f"{adiados} adiado(s) por fonte indisponível."
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"SIMULAÇÃO — {len(vencidos)} plano(s) venceram e seriam "
                    "conferidos."
                )
            )
            self.stdout.write("Rode de novo com --aplicar para gravar o desfecho.")
