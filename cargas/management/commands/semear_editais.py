"""Editais públicos de demonstração, como se tivessem vindo do PNCP.

    python manage.py semear_editais --aplicar

## Por que ela mora aqui

`EditalPublico` é do app `resultados`, que é espelho do que vem de fora e não
tem view, form nem semeadora própria — quem escreve nele é `cargas`, como já
faz `semear_resultados`. E não pode morar em `semear_demonstracao`, no
`workspace`: aquele app é a FOLHA da árvore de dependências e não importa app
de domínio, regra que `test_workspace_nao_importa_app_de_dominio` cobra.

Os registros entram com `fonte=PNCP` e `carga_id=None` — não vieram de uma
execução de carga de verdade, e marcar uma seria inventar procedência para dado
inventado.

## O que ela NÃO é

Não é dado real. Órgão, número de controle, valor e link são plausíveis e
fictícios; nenhum deles deve sobreviver à primeira carga de verdade do PNCP.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from resultados.models import EditalPublico, Fonte

# (chave, número de controle, objeto, órgão, unidade, UF, município,
#  modalidade, valor, dias até a abertura, dias até o encerramento, termo, link)
#
# Os prazos são relativos a hoje e cobrem os dois lados de propósito: há edital
# encerrado, aberto agora e por abrir. Uma lista toda no futuro deixaria os
# filtros de "encerrado" e "vencendo" sem nada para mostrar.
EDITAIS = [
    ("pncp-2026-000112", "05.442.128/0001-10-1-000112/2026",
     "Contratação de serviços continuados de vigilância patrimonial armada "
     "e desarmada para as unidades administrativas.",
     "Tribunal Regional do Trabalho da 5ª Região", "Secretaria de Administração",
     "BA", "Salvador", "Pregão eletrônico", "4820000.00", -12, 6,
     "vigilância", "https://pncp.gov.br/app/editais/05442128000110/2026/112"),
    ("pncp-2026-000118", "14.112.907/0001-44-1-000118/2026",
     "Serviço de vigilância patrimonial desarmada para o campus sede e "
     "unidades avançadas.",
     "Instituto Federal da Bahia", "Pró-Reitoria de Administração",
     "BA", "Salvador", "Pregão eletrônico", "2310000.00", -5, 13,
     "vigilância", "https://pncp.gov.br/app/editais/14112907000144/2026/118"),
    ("pncp-2026-000203", "13.937.073/0001-09-1-000203/2026",
     "Registro de preços para serviços de portaria e controle de acesso.",
     "Prefeitura Municipal de Lauro de Freitas", "Secretaria de Administração",
     "BA", "Lauro de Freitas", "Pregão eletrônico", "1180000.00", -2, 20,
     "portaria", "https://pncp.gov.br/app/editais/13937073000109/2026/203"),
    ("pncp-2026-000225", "15.180.714/0001-04-1-000225/2026",
     "Instalação e manutenção de sistema de CFTV e controle de acesso nas "
     "unidades de saúde.",
     "Secretaria Municipal de Saúde de Camaçari", "Diretoria de Infraestrutura",
     "BA", "Camaçari", "Concorrência", "3640000.00", 3, 31,
     "cftv", "https://pncp.gov.br/app/editais/15180714000104/2026/225"),
    ("pncp-2026-000241", "00.394.460/0001-41-1-000241/2026",
     "Serviços de vigilância armada para agências e postos de atendimento.",
     "Banco do Nordeste do Brasil", "Superintendência de Logística",
     "CE", "Fortaleza", "Pregão eletrônico", "7950000.00", -20, 45,
     "vigilância", "https://pncp.gov.br/app/editais/00394460000141/2026/241"),
    ("pncp-2026-000258", "33.000.167/0001-01-1-000258/2026",
     "Monitoramento eletrônico e pronta resposta para unidades operacionais.",
     "Petrobras Distribuidora", "Gerência de Segurança Patrimonial",
     "RJ", "Rio de Janeiro", "Pregão eletrônico", "5210000.00", 10, 60,
     "monitoramento", "https://pncp.gov.br/app/editais/33000167000101/2026/258"),
    ("pncp-2026-000260", "07.954.605/0001-60-1-000260/2026",
     "Serviço de segurança patrimonial para o complexo hospitalar.",
     "Hospital Universitário Professor Edgard Santos", "Divisão Administrativa",
     "BA", "Salvador", "Pregão eletrônico", "2960000.00", -40, -8,
     "segurança patrimonial", "https://pncp.gov.br/app/editais/07954605000160/2026/260"),
    ("pncp-2026-000266", "16.236.849/0001-77-1-000266/2026",
     "Contratação de brigada de incêndio e socorrista para eventos públicos.",
     "Superintendência de Esportes do Estado", "Diretoria de Eventos",
     "BA", "Salvador", "Dispensa", "480000.00", -35, -15,
     "brigada", "https://pncp.gov.br/app/editais/16236849000177/2026/266"),
    ("pncp-2026-000271", "11.238.699/0001-59-1-000271/2026",
     "Serviços de vigilância desarmada para escolas da rede estadual.",
     "Secretaria de Educação do Estado da Bahia", "Coordenação de Infraestrutura",
     "BA", "Feira de Santana", "Pregão eletrônico", "6180000.00", 1, 27,
     "vigilância", "https://pncp.gov.br/app/editais/11238699000159/2026/271"),
    ("pncp-2026-000277", "29.979.036/0001-40-1-000277/2026",
     "Locação de equipamentos de raio-x e detector de metais com operadores.",
     "Assembleia Legislativa do Estado", "Diretoria de Segurança",
     "PE", "Recife", "Pregão eletrônico", "1420000.00", 8, 40,
     "controle de acesso", "https://pncp.gov.br/app/editais/29979036000140/2026/277"),
    ("pncp-2026-000284", "08.775.812/0001-06-1-000284/2026",
     "Serviço de escolta armada para transporte de valores e documentos.",
     "Companhia de Desenvolvimento Urbano", "Gerência de Suprimentos",
     "BA", "Salvador", "Pregão eletrônico", "890000.00", -1, 11,
     "escolta", "https://pncp.gov.br/app/editais/08775812000106/2026/284"),
    ("pncp-2026-000290", "02.341.467/0001-20-1-000290/2026",
     "Fornecimento de merenda escolar para a rede municipal.",
     "Prefeitura Municipal de Simões Filho", "Secretaria de Educação",
     "BA", "Simões Filho", "Pregão eletrônico", "2100000.00", 2, 22,
     "patrimonial", "https://pncp.gov.br/app/editais/02341467000120/2026/290"),
]


class Command(BaseCommand):
    help = "Semeia editais públicos de demonstração, com procedência PNCP."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--aplicar", action="store_true", help="Grava.")

    def handle(self, *args, **opcoes) -> None:
        aplicar = opcoes["aplicar"]
        if not aplicar:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --aplicar.\n")
            )

        hoje = timezone.localdate()

        def momento(dias: int, hora: int):
            return timezone.make_aware(
                datetime.combine(hoje + timedelta(days=dias), time(hora, 0))
            )

        criados = existiam = 0
        with transaction.atomic():
            for (chave, numero, objeto, orgao, unidade, uf, municipio, modalidade,
                 valor, abertura, encerramento, termo, link) in EDITAIS:
                _, criado = EditalPublico.objects.get_or_create(
                    fonte=Fonte.PNCP,
                    chave_externa=chave,
                    defaults={
                        "numero_controle": numero,
                        "objeto": objeto,
                        "orgao": orgao,
                        "unidade": unidade,
                        "uf": uf,
                        "municipio": municipio,
                        "modalidade": modalidade,
                        "valor_estimado": Decimal(valor),
                        "abertura_proposta": momento(abertura, 9),
                        "encerramento_proposta": momento(encerramento, 14),
                        "termo_casado": termo,
                        "link": link,
                        "carga_id": None,
                    },
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
