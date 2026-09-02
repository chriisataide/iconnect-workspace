"""Os ciclos de planejamento da ADB — a pauta mensal e o recorte trimestral.

## Por que a pauta é semeada, e não deixada em branco

Um ciclo vazio é um ciclo que ninguém usa: a primeira reunião chegaria com a
tela pedindo que alguém montasse dezesseis itens ali, na hora. A semeadura
entrega a ordem de olhar que o benchmark ensina, já apontada para as telas que
este produto tem — e quem governa o ciclo ajusta no `/admin/` depois.

## O que ela NÃO faz

Não mexe em ciclo desligado, pelo mesmo motivo de `semear_regras_excecao`:
desligar é decisão de quem opera, e a semeadora roda no deploy seguinte.

Não apaga etapa que alguém acrescentou à mão. Ela garante que as etapas
DECLARADAS aqui existem com o texto certo; o que foi acrescentado depois é
decisão da empresa sobre a própria reunião, e uma semeadora que a desfaz ensina
a não usar a tela.

## O trimestral é um SUBCONJUNTO, e não outra pauta

É assim no benchmark: mesma biblioteca de telas, recorte diferente por público.
Duas pautas independentes divergiriam — e a diferença entre elas deixaria de ser
"o que a plateia sênior precisa ver" para virar "o que alguém esqueceu de
copiar".
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from workspace.models.ciclo import Cadencia, CicloPlanejamento, EtapaCiclo

#: A pauta mensal. Cada item aponta para um CÓDIGO do endereçamento.
#:
#: CP01 é a tela 10 — Apresentação de Resultados —, como no Portal GPS, onde o
#: ciclo abre por Destaques/Concentrações. A ordem não é alfabética nem por
#: departamento: é a ordem de olhar, que começa pelo resultado e termina no que
#: sustenta o resultado.
MENSAL = (
    ("CP01", "10", "Resultado do mês",
     "O mês fechou onde deveria? Que contrato puxou o número para baixo?"),
    ("CP02", "11", "O que saiu da linha",
     "Que regra disparou desde a última reunião, e quem responde por ela?"),
    ("CP03", "08", "O produto está sendo usado?",
     "Volume por área, tempo até resolver e onde a fila trava."),
    ("CP04", "02.3", "A fila das áreas",
     "O que está parado além do prazo que a pessoa viu ao pedir?"),
    ("CP05", "02.2", "O que espera aprovação",
     "Que pedido está parado em ALGUÉM, e não em alguma coisa?"),
    ("CP06", "30", "Pessoas e papéis",
     "Quem entrou, quem mudou de área, que papel vence no mês que vem?"),
    ("CP07", "03.1", "Normativos",
     "O que foi publicado, o que vence e o que ainda não foi confirmado."),
    ("CP08", "33", "Frota",
     "Prazos vencendo e o que a frota consumiu no mês."),
    ("CP09", "31", "Estoque e equipamentos",
     "O que a empresa tem, o que falta devolver."),
    ("CP10", "26.1", "Oportunidades",
     "O que precisa de resposta antes da próxima reunião."),
    ("CP11", "99", "De onde vieram os números",
     "Que fonte falhou no mês, e que divergência entre fontes ficou em aberto."),
    ("CP12", "", "Encaminhamentos e encerramento",
     "O que ficou de fazer, com dono e com prazo."),
)

#: O trimestral: o recorte para a plateia sênior. Os códigos são os MESMOS —
#: mesma biblioteca de telas, recorte diferente por público.
TRIMESTRAL = ("CP01", "CP02", "CP03", "CP06", "CP11", "CP12")

CICLOS = (
    {
        "chave": "mensal",
        "nome": "Ciclo de Planejamento Mensal",
        "cadencia": Cadencia.MENSAL,
        "publico": "Diretoria Executiva, Diretores, Gerentes e coordenadores",
        # A plateia como LISTA de papéis. A ATA sai com estes papéis no
        # `publico_alvo`, e é isso que faz vitrine, busca e leitura direta
        # concordarem sem exceção nenhuma no app de conteúdo.
        "papeis_leitores": ["diretoria", "socios", "gestor", "rh", "financeiro"],
        "papel_condutor": "diretoria",
        "ordem": 10,
        "etapas": MENSAL,
    },
    {
        "chave": "trimestral",
        "nome": "Ciclo de Planejamento Trimestral",
        "cadencia": Cadencia.TRIMESTRAL,
        "publico": "Presidência, Vice-presidência, Diretores e Gerentes",
        # Plateia MENOR, de propósito. É a diferença que o benchmark faz entre
        # os dois ciclos, e ela precisa aparecer na ATA: a do trimestral não é
        # leitura de rotina de quem executa.
        "papeis_leitores": ["diretoria", "socios"],
        "papel_condutor": "diretoria",
        "ordem": 20,
        "etapas": tuple(e for e in MENSAL if e[0] in TRIMESTRAL),
    },
)


class Command(BaseCommand):
    help = "Cadastra os ciclos de planejamento e as etapas de cada pauta."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--aplicar", action="store_true")

    def handle(self, *args, **opcoes) -> None:
        aplicar = opcoes["aplicar"]
        criados = etapas_novas = etapas_atualizadas = 0

        with transaction.atomic():
            for dados in CICLOS:
                etapas = dados.pop("etapas")
                ciclo = CicloPlanejamento.objects.filter(chave=dados["chave"]).first()
                if ciclo is None:
                    criados += 1
                    self.stdout.write(f"  + ciclo {dados['chave']}")
                    if aplicar:
                        ciclo = CicloPlanejamento.objects.create(**dados)
                else:
                    # `ativo` fica de fora: desligar um ciclo é decisão de quem
                    # opera, e a semeadora roda no deploy seguinte.
                    mudou = False
                    for campo, valor in dados.items():
                        if campo == "chave":
                            continue
                        if getattr(ciclo, campo) != valor:
                            setattr(ciclo, campo, valor)
                            mudou = True
                    if mudou and aplicar:
                        ciclo.save()
                dados["etapas"] = etapas

                if ciclo is None:
                    # Simulação de um ciclo que não existe: as etapas dele
                    # também não existem, e contá-las é o número honesto.
                    etapas_novas += len(etapas)
                    for codigo, _tela, titulo, _pergunta in etapas:
                        self.stdout.write(f"    + {codigo} · {titulo}")
                    continue

                for ordem, (codigo, tela, titulo, pergunta) in enumerate(etapas, 1):
                    campos = {
                        "ordem": ordem * 10,
                        "titulo": titulo,
                        "tela": tela,
                        "pergunta": pergunta,
                    }
                    etapa = EtapaCiclo.objects.filter(ciclo=ciclo, codigo=codigo).first()
                    if etapa is None:
                        etapas_novas += 1
                        self.stdout.write(f"    + {codigo} · {titulo}")
                        if aplicar:
                            EtapaCiclo.objects.create(
                                ciclo=ciclo, codigo=codigo, **campos
                            )
                        continue
                    mudou = [c for c, v in campos.items() if getattr(etapa, c) != v]
                    if mudou:
                        etapas_atualizadas += 1
                        self.stdout.write(f"    ~ {codigo} · {', '.join(mudou)}")
                        if aplicar:
                            for campo, valor in campos.items():
                                setattr(etapa, campo, valor)
                            etapa.save()

            if not aplicar:
                # A simulação escreve e desfaz: sem isto, o `--aplicar` de
                # amanhã não poderia usar o mesmo caminho de código, e a
                # simulação passaria a mentir sobre o que ele faz.
                transaction.set_rollback(True)

        resumo = (
            f"{criados} ciclo(s) novo(s), {etapas_novas} etapa(s) nova(s), "
            f"{etapas_atualizadas} etapa(s) atualizada(s)."
        )
        if aplicar:
            self.stdout.write(self.style.SUCCESS(resumo))
        else:
            self.stdout.write(self.style.WARNING(f"SIMULAÇÃO — {resumo}"))
            self.stdout.write("Rode de novo com --aplicar para gravar.")
