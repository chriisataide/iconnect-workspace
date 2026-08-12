"""Preenche `termos` nos itens que já existiam.

`semear_catalogo` não sobrescreve item existente, de propósito — item ajustado no
admin não pode ser desfeito por um comando. Isso é certo, e cria um problema
quando um CAMPO NOVO nasce: os itens já criados ficam com o campo vazio, e
`--aplicar` diz "criados 0" sem avisar que 19 itens estão sem sinônimo.

Sem sinônimo o assistente de ação só acha quem já sabe o nome do item — e quem
sabe o nome não precisa de assistente.

Só preenche o que está VAZIO. Quem editou os termos no admin fica em paz, e a
migração pode rodar de novo sem desfazer trabalho de ninguém.
"""

from django.db import migrations


def preencher(apps, schema_editor):
    from workspace.catalogo_inicial import CATALOGO_INICIAL

    ItemCatalogo = apps.get_model("workspace", "ItemCatalogo")
    por_chave = {
        spec["chave"]: spec.get("termos", []) for spec in CATALOGO_INICIAL
    }

    for item in ItemCatalogo.objects.all():
        termos = por_chave.get(item.chave)
        if termos and not item.termos:
            item.termos = list(termos)
            item.save(update_fields=["termos"])


def desfazer(apps, schema_editor):
    """Nada. Apagar os termos na volta destruiria o que alguém editou depois."""


class Migration(migrations.Migration):
    dependencies = [
        ("workspace", "0010_termos_do_catalogo"),
    ]

    operations = [
        migrations.RunPython(preencher, desfazer),
    ]
