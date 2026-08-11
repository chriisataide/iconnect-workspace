"""Cria os papéis do V1.0 e migra `UserRole.role` para `AtribuicaoPapel`.

    python manage.py semear_papeis            # relatório, sem gravar
    python manage.py semear_papeis --aplicar

Reexecutável sem duplicar: papel casa por `chave`, atribuição por
`(user, papel, escopo, vigencia_inicio)`. Rodar duas vezes não cria nada a mais.

`UserRole` continua intacto — nada é apagado. Durante a transição os dois
coexistem, e `pode()` lê apenas IDN.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from identidade.models import AtribuicaoPapel, Papel
from identidade.papeis import MAPA_PAPEL_LEGADO, PAPEIS_V1


class Command(BaseCommand):
    help = "Semeia os papéis do V1.0 e migra UserRole → AtribuicaoPapel."

    def add_arguments(self, parser):
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Grava. Sem esta flag, só relata o que faria.",
        )

    def handle(self, *args, **opcoes):
        aplicar = opcoes["aplicar"]
        if not aplicar:
            self.stdout.write(self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --aplicar.\n"))

        with transaction.atomic():
            criados_papel, atualizados_papel = self._semear_papeis(aplicar)
            migrados, ja_tinham, sem_mapa = self._migrar_atribuicoes(aplicar)
            if not aplicar:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Papéis"))
        self.stdout.write(f"  criados      {criados_papel}")
        self.stdout.write(f"  atualizados  {atualizados_papel}")
        self.stdout.write(self.style.MIGRATE_HEADING("Atribuições a partir de UserRole"))
        self.stdout.write(f"  migradas     {migrados}")
        self.stdout.write(f"  já existiam  {ja_tinham}")
        if sem_mapa:
            self.stdout.write(self.style.ERROR(f"  SEM MAPA     {len(sem_mapa)}"))
            for username, role in sem_mapa:
                self.stdout.write(f"     {username} · role={role!r}")
            self.stdout.write(
                self.style.ERROR(
                    "  ⚠ Estes usuários NÃO receberam atribuição. Acrescente o papel "
                    "em identidade/papeis.py:MAPA_PAPEL_LEGADO e rode de novo."
                )
            )

        if aplicar:
            self.stdout.write(self.style.SUCCESS("\n✓ Aplicado."))

    def _semear_papeis(self, aplicar: bool) -> tuple[int, int]:
        criados = atualizados = 0
        for spec in PAPEIS_V1:
            existente = Papel.objects.filter(chave=spec["chave"]).first()
            if existente is None:
                criados += 1
                if aplicar:
                    Papel.objects.create(**spec)
            else:
                mudou = (
                    existente.permissoes != spec["permissoes"]
                    or existente.escopo_padrao != spec["escopo_padrao"]
                )
                if mudou:
                    atualizados += 1
                    if aplicar:
                        for campo, valor in spec.items():
                            setattr(existente, campo, valor)
                        existente.save()
        return criados, atualizados

    def _migrar_atribuicoes(self, aplicar: bool):
        # Import tardio: `UserRole` mora em dashboard/utils/rbac.py, e este
        # comando é o ÚNICO ponto de IDN que conhece o legado. Manter o import
        # aqui evita que o app inteiro passe a depender de dashboard.
        from dashboard.utils.rbac import UserRole

        papeis = {p.chave: p for p in Papel.objects.all()} if aplicar else {}
        hoje = timezone.localdate()
        migrados = ja_tinham = 0
        sem_mapa: list[tuple[str, str]] = []

        for perfil in UserRole.objects.select_related("user").all():
            chave = MAPA_PAPEL_LEGADO.get(perfil.role)
            if chave is None:
                sem_mapa.append((perfil.user.get_username(), perfil.role))
                continue

            if not aplicar:
                migrados += 1
                continue

            papel = papeis.get(chave)
            if papel is None:  # pragma: no cover
                # Inalcançável enquanto `test_todos_os_papeis_do_mapa_existem_no_v1`
                # passar: só acontece se MAPA_PAPEL_LEGADO apontar para uma chave
                # ausente de PAPEIS_V1. Fica como rede porque a alternativa é
                # KeyError no meio de uma migração de acesso.
                sem_mapa.append((perfil.user.get_username(), perfil.role))
                continue

            _, criado = AtribuicaoPapel.objects.get_or_create(
                user=perfil.user,
                papel=papel,
                escopo=papel.escopo_padrao,
                unidade=None,
                departamento=None,
                # Vigência aberta: o papel migrado não expira sozinho.
                vigencia_inicio=hoje,
                defaults={
                    "vigencia_fim": None,
                    "justificativa": f"Migrado de UserRole.role={perfil.role!r}",
                },
            )
            if criado:
                migrados += 1
            else:
                ja_tinham += 1

        return migrados, ja_tinham, sem_mapa
