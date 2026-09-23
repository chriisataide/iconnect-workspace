"""Um comando só, para levar a demonstração inteira a outro servidor.

    python manage.py semear_tudo --aplicar

## O que este comando é

Um ORQUESTRADOR. Ele não semeia nada sozinho — chama, na ordem que cada uma
exige, as semeadoras que já existem em `workspace`, `financas` e `cargas`, e
para no primeiro erro em vez de seguir com o banco pela metade.

A ordem importa e está documentada onde cada dependência nasce:
`semear_resultados` recusa começar sem `FonteDados` (`semear_fontes` antes);
`semear_lancamentos` lê `CentroCusto` (`semear_centros_custo` antes);
`semear_demonstracao` lê catálogo, recursos, estoque, frota e cursos — as
cinco de cima na lista abaixo. `EXEC_13_OPERACAO.md` §13.1 é a mesma ordem,
para quem quiser conferir contra o runbook.

## O que este comando NÃO faz — e por quê

**Não cria pessoa, papel nem organograma.** `semear_papeis`,
`importar_organograma` e `semear_acessos` continuam de fora de propósito: eles
fabricam gente e cargo, e um servidor que já tem gente de verdade não pode
ganhar "Gerente de Campo" e "Analista de Suporte" por cima. Este comando
assume que a IDENTIDADE do servidor — pessoas, papéis, ao menos um
superusuário — já existe. Se não existir, cada seeder abaixo vai dizer
exatamente o que falta (ex.: "nenhum superusuário no banco") e este comando
para ali, sem adivinhar.

**Não é dado real, em nenhuma das vinte chamadas.** Cliente, contrato, placa,
edital, valor: tudo inventado e plausível, para as telas terem o que mostrar.
Rodar isto num banco com movimento de verdade não acrescenta nada e suja o
histórico — é a mesma advertência que `semear_demonstracao` já faz sozinho,
só que agora vale para a pilha inteira de uma vez.

## Sobre rodar de novo

Todo passo é idempotente por construção (o seu próprio, não este arquivo): a
segunda vez atualiza ou não faz nada, nunca duplica. Isto faz deste comando
algo seguro de repetir sempre que uma semeadora ganhar uma linha nova — não é
preciso lembrar quais das vinte mudaram.

## Sem `--aplicar`

Cada seeder roda em simulação e desfaz a própria transação — o relatório
mostra o que aconteceria, e nada grava. É o mesmo contrato de sempre, só que
para os vinte passos de uma vez.
"""

from __future__ import annotations

import time

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

#: (nome do comando, o que ele prepara). A ordem É a dependência — mexer nela
#: sem entender por que cada uma está onde está é o jeito mais rápido de um
#: passo do meio falhar por falta do que o de cima deveria ter deixado pronto.
PASSOS: tuple[tuple[str, str], ...] = (
    ("semear_regras_aprovacao", "a cadeia de aprovação por faixa de valor"),
    ("semear_catalogo", "os itens de serviço"),
    ("semear_recursos", "salas, veículos e equipamentos reserváveis"),
    ("semear_estoque", "materiais e saldo inicial"),
    ("semear_frota", "os veículos, ligados aos recursos"),
    ("semear_cursos", "NRs e treinamentos"),
    ("semear_faq", "a base do assistente"),
    ("semear_centros_custo", "um CentroCusto por código já usado na lotação"),
    ("semear_orcamento", "o orçamento anual de cada centro de custo"),
    ("semear_areas", "as cinco áreas comerciais"),
    ("semear_plano_de_contas", "o plano de contas"),
    ("semear_fontes", "as quatro fontes e a precedência entre elas"),
    ("semear_resultados", "a massa fictícia do espelho, pelo carregador"),
    ("semear_regras_excecao", "as regras do painel de exceções"),
    ("semear_ciclos", "a pauta mensal e o recorte trimestral"),
    ("semear_ciclo_metas", "o ciclo de metas do ano corrente"),
    ("semear_demonstracao", "reserva, correspondência, matrícula, ATA, plano…"),
    ("semear_lancamentos", "os lançamentos financeiros, para orçado × realizado"),
    ("semear_editais", "editais públicos, como se vindos do PNCP"),
    ("reindexar_busca", "o índice da busca, por cima de tudo que entrou"),
)


class Command(BaseCommand):
    help = "Orquestra as vinte semeadoras de demonstração, na ordem que elas exigem."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--aplicar", action="store_true",
            help="Grava. Sem isto, cada passo só simula e relata.",
        )

    def handle(self, *args, **opcoes) -> None:
        aplicar = opcoes["aplicar"]

        self.stdout.write(self.style.WARNING(
            "\nDados de DEMONSTRAÇÃO — inventados e plausíveis, não dados "
            "reais. Não rode num banco com movimento de verdade.\n"
        ))
        if not aplicar:
            self.stdout.write(self.style.WARNING(
                "SIMULAÇÃO — nenhum dos vinte passos vai gravar. Rode de novo "
                "com --aplicar quando estiver pronto.\n"
            ))

        inicio = time.monotonic()
        for numero, (nome, descricao) in enumerate(PASSOS, start=1):
            self.stdout.write(
                self.style.MIGRATE_HEADING(f"[{numero:2d}/{len(PASSOS)}] {nome}")
                + f"  — {descricao}"
            )
            try:
                # `reindexar_busca` não é semeadora — não simula, não tem
                # `--aplicar`, e só faz sentido rodar quando os passos antes
                # dele gravaram de verdade.
                if nome == "reindexar_busca":
                    if aplicar:
                        call_command(nome)
                    else:
                        self.stdout.write("  (pulado na simulação — não há índice para atualizar)")
                else:
                    call_command(nome, aplicar=aplicar)
            except CommandError as erro:
                self.stdout.write(self.style.ERROR(f"\nParou em `{nome}`: {erro}"))
                self.stdout.write(self.style.ERROR(
                    "Os passos anteriores já gravaram — rodar `semear_tudo "
                    "--aplicar` de novo depois de resolver retoma sem duplicar "
                    "nada, porque cada seeder é idempotente."
                ))
                raise CommandError(f"semear_tudo interrompido em `{nome}`") from erro

        duracao = time.monotonic() - inicio
        if aplicar:
            self.stdout.write(self.style.SUCCESS(
                f"\n✓ Os {len(PASSOS)} passos rodaram e gravaram em {duracao:.1f}s."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\n✓ Simulação dos {len(PASSOS)} passos em {duracao:.1f}s — "
                "rode com --aplicar para gravar de verdade."
            ))
