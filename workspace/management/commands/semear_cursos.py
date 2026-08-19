"""Cria o catálogo de cursos da Universidade e matrícula de demonstração.

    python manage.py semear_cursos --aplicar
    python manage.py semear_cursos --aplicar --matricular

As NRs e as validades são as usuais do setor — e devem ser conferidas contra a
norma vigente antes de valer para valer. O que NÃO é chute é a forma: NR-35 e
NR-10 reciclam a cada 2 anos, NR-33 anualmente, e integração não vence.

`--matricular` gera matrículas espalhadas no tempo — uma vencida, uma vencendo
em poucos dias, uma em dia — para que o painel e os alertas possam ser vistos
funcionando. Sem isso, a tela nasce vazia e ninguém descobre se ela funciona.
"""

from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from contas.models import Pessoa
from workspace.models.habilitacao import (
    Curso,
    Matricula,
    SituacaoMatricula,
    TipoCurso,
)
from workspace.services import habilitacao as hab

CURSOS = [
    ("nr-35", "NR-35 — Trabalho em altura", TipoCurso.NR, 24, 8, True,
     "Obrigatória para atividade acima de 2 metros."),
    ("nr-10", "NR-10 — Segurança em instalações elétricas", TipoCurso.NR, 24, 40, True,
     "Obrigatória para quem intervém em instalação elétrica."),
    ("nr-33", "NR-33 — Espaço confinado", TipoCurso.NR, 12, 16, True,
     "Reciclagem anual."),
    ("nr-12", "NR-12 — Segurança em máquinas", TipoCurso.NR, 24, 8, False, ""),
    ("integracao", "Integração de novos colaboradores", TipoCurso.INTEGRACAO, 0, 4, True,
     "Uma vez, na entrada. Não vence."),
    ("lgpd", "LGPD e tratamento de dados", TipoCurso.INSTITUCIONAL, 12, 2, True,
     "Reciclagem anual — a política muda."),
    ("primeiros-socorros", "Primeiros socorros", TipoCurso.TECNICO, 24, 8, False, ""),
    ("direcao-defensiva", "Direção defensiva", TipoCurso.TECNICO, 24, 8, False,
     "Para quem dirige veículo da empresa."),
]

#: `(curso, dias até vencer)` — negativo já venceu. Espalhados de propósito para
#: exercitar os quatro degraus de alerta e o estado "em dia".
DEMONSTRACAO = [("nr-35", -12), ("nr-10", 5), ("nr-33", 22), ("lgpd", 200)]


class Command(BaseCommand):
    help = "Semeia cursos da Universidade Corporativa."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Grava.")
        parser.add_argument(
            "--matricular", action="store_true",
            help="Cria matrículas de demonstração espalhadas no tempo.",
        )

    def handle(self, *args, **opcoes):
        aplicar = opcoes["aplicar"]
        if not aplicar:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --aplicar.\n")
            )

        with transaction.atomic():
            criados, existentes = self._cursos(aplicar)
            matriculas = self._matriculas(aplicar) if opcoes["matricular"] else 0
            if not aplicar:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Universidade"))
        self.stdout.write(f"  criados      {criados}")
        self.stdout.write(f"  já existiam  {existentes}")
        if opcoes["matricular"]:
            self.stdout.write(f"  matrículas   {matriculas}")
        if aplicar:
            self.stdout.write(self.style.SUCCESS("\n✓ Aplicado."))

    def _cursos(self, aplicar: bool):
        criados = existentes = 0
        for codigo, nome, tipo, validade, carga, obrigatorio, descricao in CURSOS:
            if Curso.objects.filter(codigo=codigo).exists():
                existentes += 1
                continue
            criados += 1
            validade_txt = f"{validade}m" if validade else "não vence"
            self.stdout.write(f"  + {codigo:20} {nome:46} {validade_txt}")
            if aplicar:
                Curso.objects.create(
                    codigo=codigo, nome=nome, tipo=tipo, validade_meses=validade,
                    carga_horaria=carga, obrigatorio=obrigatorio, descricao=descricao,
                )
        return criados, existentes

    def _matriculas(self, aplicar: bool) -> int:
        pessoas = list(Pessoa.objects.filter(is_active=True, lotacao__isnull=False)[:4])
        if not pessoas:
            self.stdout.write(
                self.style.WARNING("  Ninguém lotado — rode `semear_perfis` antes.")
            )
            return 0

        hoje = timezone.localdate()
        total = 0
        for posicao, (codigo, dias) in enumerate(DEMONSTRACAO):
            curso = Curso.objects.filter(codigo=codigo).first()
            pessoa = pessoas[posicao % len(pessoas)]
            if curso is None or Matricula.objects.filter(pessoa=pessoa, curso=curso).exists():
                continue

            total += 1
            self.stdout.write(f"  ~ {pessoa} · {curso.nome} · vence em {dias}d")
            if not aplicar:
                continue

            # A conclusão é calculada DE TRÁS para a frente a partir do
            # vencimento desejado — assim a demonstração exercita o mesmo
            # `_vencimento()` que a conclusão real usa, em vez de gravar a data
            # à mão e esconder um erro de cálculo.
            vence = hoje + timedelta(days=dias)
            matricula = Matricula.objects.create(
                pessoa=pessoa, curso=curso, situacao=SituacaoMatricula.PENDENTE
            )
            concluido = vence - timedelta(days=curso.validade_meses * 30)
            hab.concluir(matricula, em=concluido, certificado=f"DEMO-{curso.codigo}")
            Matricula.objects.filter(pk=matricula.pk).update(vence_em=vence)
        return total
