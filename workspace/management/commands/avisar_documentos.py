"""Cobra a leitura obrigatória e avisa o dono do documento que vai vencer. §37.

    python manage.py avisar_documentos --aplicar
    python manage.py avisar_documentos --dias 60 --aplicar

Comando e não sinal, pelo mesmo motivo de `avisar_habilitacoes` e
`avisar_frota`: a vigência não acaba porque alguém salvou um formulário — acaba
porque o dia passou.

As duas metades resolvem silêncios diferentes:

**Leitura obrigatória.** Sem o aviso, a confirmação só acontece para quem abre
o Meu dia por conta própria. É a diferença entre "a empresa publicou" e "a
empresa informou" — e é a confirmação, não a publicação, que se leva para
auditoria de ISO ou para defesa trabalhista.

**Vigência.** `publicados()` tira o vencido da vitrine, então um POP que passa
da data simplesmente SOME do acervo. As pessoas continuam precisando do
procedimento; ele deixou de existir na tela, e só o dono pode republicá-lo.

Diário é o certo. O `criar()` deduplica por aviso NÃO LIDO, então rodar todo dia
não produz trinta cópias — e a chave inclui a VERSÃO do documento, para que
publicar a v2 volte a cobrar quem já tinha lido a v1.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from workspace.services import conteudo as cnt


class Command(BaseCommand):
    help = "Cobra leitura obrigatória e avisa vigência de documento."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Grava os avisos.")
        parser.add_argument(
            "--dias",
            type=int,
            default=cnt.DIAS_DE_AVISO,
            help="Antecedência do aviso de vigência, em dias.",
        )

    def handle(self, *args, **opcoes):
        aplicar, dias = opcoes["aplicar"], opcoes["dias"]
        if not aplicar:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --aplicar.\n")
            )

        for documento in cnt.vencidos():
            self.stdout.write(
                f"  VENCIDO   {documento.slug:32} "
                f"{documento.vigencia_fim.strftime('%d/%m/%Y')}"
            )
        for documento in cnt.a_vencer(dias=dias):
            if not documento.vencido:
                self.stdout.write(
                    f"  a vencer  {documento.slug:32} "
                    f"{documento.dias_para_vencer}d"
                )

        with transaction.atomic():
            leituras = cnt.avisar_leituras_obrigatorias()
            vigencias = cnt.avisar_vencimentos(dias=dias)
            if not aplicar:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Documentação"))
        self.stdout.write(f"  cobranças de leitura  {leituras}")
        self.stdout.write(f"  avisos de vigência    {vigencias}")
        if aplicar:
            self.stdout.write(self.style.SUCCESS("\n✓ Aplicado."))
