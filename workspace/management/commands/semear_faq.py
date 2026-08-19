"""Cria a base de conhecimento inicial do assistente.

    python manage.py semear_faq --aplicar
    python manage.py semear_faq --atualizar --aplicar

Mesma forma de `semear_catalogo`, e pelo mesmo motivo: sem `--atualizar`, toda
correção de resposta só chegaria a instalação limpa — e resposta errada num
portal é pior que resposta ausente, porque a pessoa age sobre ela.

Casa por `pergunta` dentro da área. Pergunta editada na tela do produto continua
existindo; o que a semente sincroniza é o texto DELA, quando pedido.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from workspace.faq_inicial import FAQ_INICIAL
from workspace.models.faq import PerguntaFrequente

CAMPOS = ("resposta", "palavras_chave", "url_acao", "rotulo_acao", "prioridade")


class Command(BaseCommand):
    help = "Semeia as perguntas frequentes do assistente."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Grava.")
        parser.add_argument(
            "--atualizar", action="store_true",
            help="Sincroniza o texto das que já existem.",
        )

    def handle(self, *args, **opcoes):
        aplicar, atualizar = opcoes["aplicar"], opcoes["atualizar"]
        if not aplicar:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --aplicar.\n")
            )

        with transaction.atomic():
            criadas, existentes, mudadas = self._semear(aplicar, atualizar)
            if not aplicar:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Perguntas frequentes"))
        self.stdout.write(f"  criadas      {criadas}")
        self.stdout.write(f"  já existiam  {existentes}")
        if atualizar:
            self.stdout.write(f"  atualizadas  {mudadas}")
        elif mudadas:
            self.stdout.write(
                self.style.WARNING(
                    f"  DIVERGENTES  {mudadas} — use --atualizar para sincronizar"
                )
            )
        if aplicar:
            self.stdout.write(self.style.SUCCESS("\n✓ Aplicado."))

    def _semear(self, aplicar: bool, atualizar: bool):
        criadas = existentes = mudadas = 0
        for spec in FAQ_INICIAL:
            existente = PerguntaFrequente.objects.filter(
                area=spec["area"], pergunta=spec["pergunta"]
            ).first()
            if existente is not None:
                existentes += 1
                fora = [c for c in CAMPOS if getattr(existente, c) != spec.get(c, "")]
                if fora:
                    mudadas += 1
                    self.stdout.write(f"  ~ [{spec['area']}] {spec['pergunta']}")
                    self.stdout.write(f"      {', '.join(fora)}")
                    if aplicar and atualizar:
                        for campo in fora:
                            setattr(existente, campo, spec.get(campo, ""))
                        existente.save(update_fields=fora)
                continue

            criadas += 1
            self.stdout.write(f"  + [{spec['area']}] {spec['pergunta']}")
            if aplicar:
                PerguntaFrequente.objects.create(**spec)
        return criadas, existentes, mudadas
