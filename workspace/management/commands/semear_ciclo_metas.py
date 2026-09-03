"""O ciclo de metas do ano corrente, e um quadro de exemplo por papel de gestão.

## O que ele semeia

O **ciclo** — que é a única parte desta onda que precisa existir antes de
alguém abrir a tela — e, opcionalmente, um quadro de exemplo por gestor, para
que a primeira pessoa a chegar veja como uma meta com fórmula se parece.

## Por que os quadros de exemplo são OPCIONAIS

Porque eles são de mentira, e meta de mentira no quadro de uma pessoa real é
pior do que quadro vazio: ela aparece no painel do R.H. como aprovada, e alguém
vai perguntar por que a meta de EBITDA do gerente de TI está lá.

Por padrão o comando semeia **só o ciclo**. `--com-exemplos` acrescenta os
quadros, e ele existe para o ambiente de demonstração.

## O ciclo não é reaberto

Como toda semeadora deste repositório, ela não desfaz decisão de quem opera: um
ciclo fechado à mão continua fechado no deploy seguinte.
"""

from __future__ import annotations

from datetime import date

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from workspace.models.meta import (
    CicloMetas,
    GrupoMeta,
    Meta,
    QuadroMetas,
    SituacaoCiclo,
    TipoCalculo,
)

#: As metas de exemplo. Uma por grupo, e as três com FÓRMULA — é isso que
#: precisa ser visto: a meta aponta para o espelho, e não para um número
#: digitado.
EXEMPLOS = (
    {
        "grupo": GrupoMeta.FINANCEIRA,
        "descricao": "EBITDA realizado sobre o orçado",
        "fator_1": "ebitda",
        "fator_2": "orcamento_mensal",
        "tipo_calculo": TipoCalculo.DIRETO,
        "peso": 4,
        "detalhamento": "A razão entre o EBITDA do escopo e o teto orçado do mês.",
    },
    {
        "grupo": GrupoMeta.PESSOAS,
        "descricao": "Turnover abaixo de 3%",
        "fator_1": "turnover_pct",
        "fator_2": "",
        "alvo": "3",
        # Menor é melhor. Sem esta direção, quem perdeu metade da equipe
        # apareceria com 140% de desempenho.
        "tipo_calculo": TipoCalculo.INVERSO,
        "peso": 3,
        "detalhamento": "Rotatividade do quadro na competência de apuração.",
    },
    {
        "grupo": GrupoMeta.OPERACIONAL,
        "descricao": "Gasto dentro do orçamento",
        "fator_1": "realizado_no_mes",
        "fator_2": "orcamento_mensal",
        "tipo_calculo": TipoCalculo.INVERSO,
        "peso": 2,
        "detalhamento": "Quanto do teto foi consumido. Menos é melhor.",
    },
)


class Command(BaseCommand):
    help = "Cadastra o ciclo de metas do ano corrente."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--aplicar", action="store_true")
        parser.add_argument("--ano", type=int, default=0)
        parser.add_argument(
            "--com-exemplos",
            action="store_true",
            help="Cria também um quadro de exemplo para cada gestor. Só para "
                 "ambiente de demonstração: meta de mentira em quadro de pessoa "
                 "real aparece no painel do R.H. como se fosse verdade.",
        )

    def handle(self, *args, **opcoes) -> None:
        aplicar = opcoes["aplicar"]
        ano = opcoes["ano"] or timezone.localdate().year
        chave = f"metas-{ano}"

        with transaction.atomic():
            ciclo = CicloMetas.objects.filter(chave=chave).first()
            if ciclo is None:
                self.stdout.write(f"  + ciclo {chave}")
                if aplicar:
                    ciclo = CicloMetas.objects.create(
                        chave=chave,
                        nome=f"Ciclo de metas {ano}",
                        inicio=date(ano, 1, 1),
                        fim=date(ano, 12, 31),
                        situacao=SituacaoCiclo.ABERTO,
                    )
            else:
                # `situacao` fica de fora: fechar um ciclo é decisão de quem
                # opera, e a semeadora roda no deploy seguinte.
                self.stdout.write(f"  = ciclo {chave} já existe")

            quadros = metas = 0
            if opcoes["com_exemplos"] and ciclo is not None:
                quadros, metas = self._exemplos(ciclo, aplicar)

            if not aplicar:
                transaction.set_rollback(True)

        resumo = (
            f"ciclo {chave}"
            + (f", {quadros} quadro(s) de exemplo com {metas} meta(s)" if quadros else "")
            + "."
        )
        if aplicar:
            self.stdout.write(self.style.SUCCESS(f"Aplicado: {resumo}"))
        else:
            self.stdout.write(self.style.WARNING(f"SIMULAÇÃO — {resumo}"))
            self.stdout.write("Rode de novo com --aplicar para gravar.")

    def _exemplos(self, ciclo, aplicar: bool) -> tuple[int, int]:
        """Um quadro em RASCUNHO por gestor. Nunca aprovado.

        Rascunho de propósito: um quadro de exemplo aprovado entraria na
        contagem do R.H. como cobertura real, e a primeira pergunta da primeira
        reunião seria sobre um número que não existe.
        """
        from identidade.models import Lotacao

        gestores = (
            Lotacao.objects.exclude(gestor=None)
            .values_list("gestor_id", flat=True)
            .distinct()
        )
        quadros = metas = 0
        for gestor_id in gestores:
            if QuadroMetas.objects.filter(ciclo=ciclo, pessoa_id=gestor_id).exists():
                continue
            quadros += 1
            self.stdout.write(f"    + quadro de exemplo para a pessoa {gestor_id}")
            if not aplicar:
                metas += len(EXEMPLOS)
                continue
            quadro = QuadroMetas.objects.create(
                ciclo=ciclo,
                pessoa_id=gestor_id,
                resumo=(
                    "Quadro de EXEMPLO, semeado para demonstração. Substitua "
                    "as metas antes de aprovar."
                ),
            )
            for ordem, dados in enumerate(EXEMPLOS, 1):
                Meta.objects.create(quadro=quadro, ordem=ordem * 10, **dados)
                metas += 1
        return quadros, metas
