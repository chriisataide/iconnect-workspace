"""Gera o CSV esqueleto do organograma, para preencher no Excel.

    python manage.py exportar_organograma > organograma.csv
    python manage.py exportar_organograma --ativos --com-lotacao > atual.csv

Sai com uma linha por usuário e as colunas que `importar_organograma` lê de
volta. Quem já tem `Lotacao` sai com os valores atuais — então o mesmo arquivo
serve para conferir e para corrigir.

Por que CSV e não formulário: preencher hierarquia de 200 pessoas é trabalho de
planilha. Quem faz isso é RH, no Excel, ordenando por gestor e copiando célula.
Obrigar o mesmo trabalho no admin, um registro por vez, garante que não seja
feito.
"""

from __future__ import annotations

import csv
import sys

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

COLUNAS = [
    "username",
    "nome",
    "email",
    "matricula",
    "cargo",
    "unidade_codigo",
    "unidade_nome",
    "departamento_codigo",
    "departamento_nome",
    "gestor_username",
    "centro_custo_codigo",
    "situacao",
]


class Command(BaseCommand):
    help = "Exporta o CSV esqueleto do organograma para preenchimento."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ativos",
            action="store_true",
            help="Só usuários com is_active=True. Recomendado.",
        )
        parser.add_argument(
            "--com-lotacao",
            action="store_true",
            help="Só quem já tem lotação — para conferir o que está cadastrado.",
        )
        parser.add_argument(
            "--sem-lotacao",
            action="store_true",
            help="Só quem ainda NÃO tem lotação — a fila de trabalho.",
        )

    def handle(self, *args, **opcoes):
        usuarios = User.objects.all().order_by("username")
        if opcoes["ativos"]:
            usuarios = usuarios.filter(is_active=True)
        if opcoes["com_lotacao"]:
            usuarios = usuarios.filter(lotacao__isnull=False)
        if opcoes["sem_lotacao"]:
            usuarios = usuarios.filter(lotacao__isnull=True)

        usuarios = usuarios.select_related(
            "lotacao", "lotacao__unidade", "lotacao__departamento", "lotacao__gestor"
        )

        escritor = csv.DictWriter(self.stdout, fieldnames=COLUNAS, lineterminator="\n")
        escritor.writeheader()

        total = 0
        for user in usuarios:
            lot = getattr(user, "lotacao", None)
            escritor.writerow(
                {
                    "username": user.get_username(),
                    "nome": user.get_full_name(),
                    "email": user.email,
                    "matricula": lot.matricula if lot else "",
                    "cargo": (lot.cargo if lot else "") or self._cargo_legado(user),
                    "unidade_codigo": lot.unidade.codigo if lot and lot.unidade else "",
                    "unidade_nome": lot.unidade.nome if lot and lot.unidade else "",
                    "departamento_codigo": (
                        lot.departamento.codigo if lot and lot.departamento else ""
                    ),
                    "departamento_nome": (
                        lot.departamento.nome
                        if lot and lot.departamento
                        else self._departamento_legado(user)
                    ),
                    "gestor_username": (
                        lot.gestor.get_username() if lot and lot.gestor else ""
                    ),
                    "centro_custo_codigo": lot.centro_custo_codigo if lot else "",
                    "situacao": lot.situacao if lot else "ativo",
                }
            )
            total += 1

        # No stderr para não sujar o CSV quando redirecionado.
        print(f"{total} linha(s) exportada(s).", file=sys.stderr)

    def _cargo_legado(self, user) -> str:
        """`PerfilUsuario.cargo` como sugestão inicial, se houver."""
        perfil = getattr(user, "perfil", None)
        return (perfil.cargo or "") if perfil else ""

    def _departamento_legado(self, user) -> str:
        """`PerfilUsuario.departamento` é texto livre. Vira sugestão de nome."""
        perfil = getattr(user, "perfil", None)
        return (perfil.departamento or "") if perfil else ""
