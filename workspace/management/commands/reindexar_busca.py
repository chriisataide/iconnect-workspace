"""Reconstrói o índice de busca a partir das origens.

    python manage.py reindexar_busca

O índice é mantido por sinal, então em operação normal este comando não é
necessário. Ele existe para três casos que o sinal não cobre:

- **Migração de dado.** Conteúdo que já existia antes do índice.
- **Alteração em massa por `queryset.update()`**, que não dispara `post_save`.
  É o jeito mais comum de o índice ficar velho sem ninguém notar.
- **Órfã**, quando a origem foi apagada direto no banco.

Sem `--aplicar`: reindexar é idempotente e não destrói conteúdo, então exigir
confirmação aqui seria cerimônia sem risco a evitar.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand

from workspace.services.indice import reindexar


class Command(BaseCommand):
    help = "Reconstrói o índice de busca do Workspace."

    def handle(self, *args, **opcoes):
        contagem = reindexar()

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Índice de busca"))
        self.stdout.write(f"  serviços      {contagem['servicos']}")
        self.stdout.write(f"  documentos    {contagem['documentos']}")
        self.stdout.write(f"  publicações   {contagem['publicacoes']}")
        if contagem["removidas"]:
            self.stdout.write(
                self.style.WARNING(f"  órfãs removidas {contagem['removidas']}")
            )
        self.stdout.write(self.style.SUCCESS("\n✓ Índice reconstruído."))
