"""As quatro fontes e as regras de precedência entre elas.

Entra na sequência de semeadura ANTES de `semear_resultados`: sem `FonteDados`,
o carregador não tem onde registrar a execução e recusa começar — de propósito,
porque uma carga sem registro é dado sem procedência.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand

from cargas.models import Fonte, FonteDados, RegraPrecedencia

FONTES = (
    {
        "chave": Fonte.SANKHYA,
        "nome": "Sankhya",
        "cadencia_esperada": "diária, madrugada · competência em D-1",
        "idade_maxima_aceitavel": timedelta(hours=30),
        "observacao": "Financeiro, contábil, folha e ponto. Usuário de "
                      "integração somente leitura do lado de lá.",
    },
    {
        "chave": Fonte.MONDAY,
        "nome": "monday.com",
        "cadencia_esperada": "a cada 15 minutos",
        # Curta de propósito: o valor do monday é ser quase em tempo real, e
        # meia hora de atraso já muda a leitura de "projeto bloqueado hoje".
        "idade_maxima_aceitavel": timedelta(hours=2),
        "observacao": "Projetos, marcos e bloqueios. Ids de board em MONDAY_BOARDS.",
    },
    {
        "chave": Fonte.PLATFORM,
        "nome": "iConnect Platform",
        "cadencia_esperada": "de hora em hora",
        "idade_maxima_aceitavel": timedelta(hours=6),
        "observacao": "Contratos, vigência e satisfação. Consolidado, nunca detalhe.",
    },
    {
        "chave": Fonte.CSV,
        "nome": "Carga por arquivo",
        "cadencia_esperada": "sob demanda",
        # Sem idade máxima: uma carga manual não tem cadência a cumprir, e
        # alarmar por idade faria a tela piscar vermelho por dado que está
        # velho porque ninguém precisou atualizá-lo.
        "idade_maxima_aceitavel": None,
        "observacao": "O formato canônico. É por aqui que a massa de teste entra.",
    },
)

#: O que fazer quando duas fontes discordam. Cada regra tem justificativa: uma
#: regra sem o porquê é uma regra que ninguém ousa mudar.
PRECEDENCIAS = (
    {
        "entidade": "contrato",
        "campo": "fim_vigencia",
        "fonte_vencedora": Fonte.PLATFORM,
        "justificativa": "A vigência é renegociada no atendimento ao cliente, "
                         "que é onde o Platform vive. O Sankhya recebe a "
                         "alteração depois, quando ela vira faturamento.",
    },
    {
        "entidade": "contrato",
        "campo": "valor_mensal",
        "fonte_vencedora": Fonte.SANKHYA,
        "justificativa": "Valor é o que foi faturado. O Platform guarda o "
                         "combinado; o Sankhya guarda o cobrado, e é o cobrado "
                         "que fecha com a contabilidade.",
    },
    {
        "entidade": "contrato",
        "campo": "centro_custo",
        "fonte_vencedora": Fonte.SANKHYA,
        "justificativa": "O plano de centros de custo é do ERP. Deixar o "
                         "Platform mandar aqui produziria código que não existe "
                         "no orçamento — a divergência que a regra 19 vigia.",
    },
    {
        "entidade": "projeto",
        "campo": "percentual_concluido",
        "fonte_vencedora": Fonte.MONDAY,
        "justificativa": "Andamento é atualizado por quem toca o projeto, e "
                         "quem toca o projeto trabalha no monday.",
    },
)


class Command(BaseCommand):
    help = "Cadastra as fontes de dados e as regras de precedência entre elas."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--aplicar", action="store_true",
            help="Grava. Sem isto, só relata o que faria.",
        )

    def handle(self, *args, **opcoes) -> None:
        aplicar = opcoes["aplicar"]
        criadas = atualizadas = 0

        for dados in FONTES:
            existente = FonteDados.objects.filter(chave=dados["chave"]).first()
            if existente is None:
                criadas += 1
                self.stdout.write(f"  + fonte {dados['nome']}")
                if aplicar:
                    FonteDados.objects.create(**dados)
                continue
            # Atualiza o que é DESCRIÇÃO e nunca `ativa`: desativar uma fonte é
            # decisão de quem opera, e a semeadora não pode reativá-la ao rodar
            # de novo depois de um incidente.
            mudou = False
            for campo in ("nome", "cadencia_esperada", "idade_maxima_aceitavel",
                          "observacao"):
                if getattr(existente, campo) != dados[campo]:
                    setattr(existente, campo, dados[campo])
                    mudou = True
            if mudou:
                atualizadas += 1
                self.stdout.write(f"  ~ fonte {dados['nome']}")
                if aplicar:
                    existente.save()

        regras = 0
        for dados in PRECEDENCIAS:
            filtro = {k: dados[k] for k in ("entidade", "campo", "fonte_vencedora")}
            if RegraPrecedencia.objects.filter(**filtro).exists():
                continue
            regras += 1
            self.stdout.write(
                f"  + precedência {dados['entidade']}.{dados['campo']} "
                f"→ {dados['fonte_vencedora']}"
            )
            if aplicar:
                RegraPrecedencia.objects.create(**dados)

        resumo = (
            f"{criadas} fonte(s) nova(s), {atualizadas} atualizada(s), "
            f"{regras} regra(s) de precedência."
        )
        if aplicar:
            self.stdout.write(self.style.SUCCESS(resumo))
        else:
            self.stdout.write(self.style.WARNING(f"SIMULAÇÃO — {resumo}"))
            self.stdout.write("Rode de novo com --aplicar para gravar.")
