"""`carregar_fonte <chave> [--janela AAAA-MM] [--aplicar]`

Simulação por padrão, como todo comando deste repositório. Em simulação a
`ExecucaoCarga` é gravada marcada `simulacao=True` e o espelho não é tocado —
o registro existe para o operador poder comparar a simulação com a carga de
verdade, e a marca existe para a simulação nunca virar carimbo de frescor.
"""

from __future__ import annotations

import calendar
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from cargas.carregador import CargaError, carregar
from cargas.conectores import Janela
from cargas.models import Fonte, StatusCarga


class Command(BaseCommand):
    help = "Roda a carga de uma fonte externa para o espelho de resultados."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "chave",
            choices=[c for c, _ in Fonte.choices],
            help="Qual fonte carregar.",
        )
        parser.add_argument(
            "--janela",
            help="Competência AAAA-MM. Sem isto, a fonte devolve tudo o que "
                 "houver — o que só faz sentido na primeira carga.",
        )
        parser.add_argument(
            "--aplicar", action="store_true",
            help="Grava no espelho. Sem isto, só relata o que faria.",
        )

    def handle(self, *args, **opcoes) -> None:
        janela = _janela(opcoes.get("janela"))
        try:
            resultado = carregar(opcoes["chave"], janela, aplicar=opcoes["aplicar"])
        except CargaError as erro:
            raise CommandError(str(erro)) from erro

        self.stdout.write(f"fonte    {resultado.fonte}")
        self.stdout.write(f"janela   {resultado.janela}")
        self.stdout.write(f"lidos    {resultado.lidos}")
        self.stdout.write(f"criados  {resultado.criados}")
        self.stdout.write(f"atualiz. {resultado.atualizados}")
        # Destacado porque é o número que responde "rodei duas vezes, e daí?".
        self.stdout.write(f"ignorados {resultado.ignorados}  (conteúdo idêntico)")
        if resultado.rejeitados:
            self.stdout.write(self.style.WARNING(f"rejeitados {resultado.rejeitados}"))
        if resultado.divergencias:
            self.stdout.write(
                self.style.WARNING(
                    f"divergências {resultado.divergencias} — veja a tela de fontes"
                )
            )

        for linha in resultado.linhas_de_log[:20]:
            self.stdout.write(f"  {linha}")

        if resultado.status == StatusCarga.SUCESSO:
            estilo = self.style.SUCCESS
        elif resultado.status == StatusCarga.PARCIAL:
            estilo = self.style.WARNING
        else:
            estilo = self.style.ERROR
        self.stdout.write(estilo(f"status   {resultado.status}"))
        if resultado.erro_resumo:
            self.stdout.write(estilo(f"motivo   {resultado.erro_resumo}"))

        if not opcoes["aplicar"]:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada foi gravado no espelho.")
            )
            self.stdout.write("Rode de novo com --aplicar.")


def _janela(texto: str | None) -> Janela:
    """`AAAA-MM` vira o mês inteiro.

    Mês inteiro e não "do dia 1 até hoje": uma janela que termina hoje faria a
    carga do dia 30 trazer menos que a do dia 31, e o mesmo comando produziria
    números diferentes conforme a hora em que rodou.
    """
    if not texto:
        return Janela()
    try:
        ano, mes = (int(parte) for parte in texto.split("-", 1))
        primeiro = date(ano, mes, 1)
    except (ValueError, TypeError) as erro:
        raise CommandError(f"Janela {texto!r} não é AAAA-MM.") from erro
    ultimo = date(ano, mes, calendar.monthrange(ano, mes)[1])
    return Janela(de=primeiro, ate=ultimo)
