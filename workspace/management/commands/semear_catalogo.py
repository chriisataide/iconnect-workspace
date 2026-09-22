"""Cria — e, quando pedido, atualiza — os itens iniciais do catálogo.

    python manage.py semear_catalogo                        # relatório
    python manage.py semear_catalogo --aplicar              # cria o que falta
    python manage.py semear_catalogo --atualizar --aplicar  # e sincroniza o resto

Reexecutável sem duplicar: casa por `chave`. Item criado à mão, fora da semente,
fica em paz sempre.

## Por que `--atualizar` existe, e por que NÃO é o padrão

Este docstring prometia, desde a primeira versão, que os campos divergentes eram
sincronizados. **Não eram**: o laço fazia `continue` em todo item existente. O
efeito é que toda mudança de formulário do produto — pergunta nova, opção nova,
prazo revisado — só chegava a instalação limpa. Banco que já roda, que é o que
está em produção, ficava no formulário do dia em que nasceu.

Não é o padrão porque `opcoes` é editável no admin de propósito: a lista de
sistemas do item de acesso muda sem deploy, e um `semear_catalogo --aplicar` de
rotina que sobrescrevesse isso apagaria o trabalho de quem mantém a lista. Com a
flag, quem roda está dizendo "quero o que a semente diz" — e o relatório mostra
campo a campo o que vai mudar antes de gravar.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from workspace.catalogo_inicial import CATALOGO_INICIAL
from workspace.models.catalogo import ItemCatalogo


class Command(BaseCommand):
    help = "Semeia o catálogo de serviços."

    #: O que a semente considera seu. Fora desta lista nada é tocado — `ativo`
    #: em especial, que é como uma remoção de produto é registrada: ressuscitar
    #: item desativado a cada semeadura desfaria a decisão em silêncio.
    CAMPOS_SINCRONIZADOS = (
        "nome", "descricao_curta", "termos", "grupo", "icone", "dominio",
        "prazo_prometido_dias", "exige_valor", "exige_centro_custo",
        "limite_auto_aprovacao", "campos", "rota_interna", "url_externa",
    )

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Grava.")
        parser.add_argument(
            "--atualizar",
            action="store_true",
            help="Sincroniza itens que já existem com o que a semente diz.",
        )

    def handle(self, *args, **opcoes):
        aplicar = opcoes["aplicar"]
        atualizar = opcoes["atualizar"]
        if not aplicar:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --aplicar.\n")
            )

        with transaction.atomic():
            criados, existentes, invalidos, mudados = self._semear(aplicar, atualizar)
            if not aplicar:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Catálogo"))
        self.stdout.write(f"  criados      {criados}")
        self.stdout.write(f"  já existiam  {existentes}")
        if atualizar:
            self.stdout.write(f"  atualizados  {mudados}")
        elif mudados:
            self.stdout.write(
                self.style.WARNING(
                    f"  DIVERGENTES  {mudados} — use --atualizar para sincronizar"
                )
            )

        if invalidos:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR(f"  INVÁLIDOS · {len(invalidos)}"))
            for chave, motivo in invalidos:
                self.stdout.write(f"     {chave}: {motivo}")

        if aplicar and not invalidos:
            self.stdout.write(self.style.SUCCESS("\n✓ Aplicado."))

    def _semear(self, aplicar: bool, atualizar: bool = False):
        criados = existentes = mudados = 0
        invalidos: list[tuple[str, str]] = []

        for spec in CATALOGO_INICIAL:
            existente = ItemCatalogo.objects.filter(chave=spec["chave"]).first()
            if existente is not None:
                existentes += 1
                diferencas = self._diferencas(existente, spec)
                if diferencas:
                    mudados += 1
                    self._relatar_diferencas(spec["chave"], diferencas)
                    if aplicar and atualizar:
                        for campo, (_, novo) in diferencas.items():
                            setattr(existente, campo, novo)
                        existente.save(update_fields=list(diferencas))
                continue

            item = ItemCatalogo(**spec)
            try:
                # Valida ANTES de gravar: item com 5 campos obrigatórios entraria
                # e só seria descoberto quando alguém tentasse usar.
                item.full_clean(exclude=["id"])
            except Exception as erro:  # ValidationError
                mensagens = getattr(erro, "messages", [str(erro)])
                invalidos.append((spec["chave"], mensagens[0]))
                continue

            criados += 1
            grupo = spec["grupo"]
            self.stdout.write(f"  + {spec['chave']:24} {grupo}")
            if aplicar:
                item.save()

        return criados, existentes, invalidos, mudados

    def _diferencas(self, item: ItemCatalogo, spec: dict) -> dict:
        """`{campo: (atual, da_semente)}` para o que divergiu."""
        fora = {}
        for campo in self.CAMPOS_SINCRONIZADOS:
            if campo not in spec:
                continue
            atual, novo = getattr(item, campo), spec[campo]
            if atual != novo:
                fora[campo] = (atual, novo)
        return fora

    def _relatar_diferencas(self, chave: str, diferencas: dict) -> None:
        self.stdout.write(f"  ~ {chave}")
        for campo, (atual, novo) in diferencas.items():
            # `campos` é uma lista de dicionários e imprimi-la inteira enche a
            # tela; o que interessa é QUE ela mudou e de quantas perguntas para
            # quantas.
            if campo == "campos":
                self.stdout.write(
                    f"      campos: {len(atual)} → {len(novo)} perguntas"
                )
            else:
                self.stdout.write(f"      {campo}: {atual!r} → {novo!r}")
