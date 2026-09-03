"""Liga a regra que esperava o orçamento existir aqui dentro.

`cc-sem-orcado-e-o-inverso` nasceu na Onda 4 **registrada e desligada**, com o
texto: *"Só passa a valer quando o orçamento existir aqui dentro."* A Onda 8
criou `financas.OrcamentoAnual`, e a condição foi cumprida.

## Por que uma migração, e não a semeadora

`semear_regras_excecao` **nunca reativa** regra desligada — é uma decisão
deliberada, porque desligar quase sempre acontece no meio de um incidente e a
semeadora roda no deploy seguinte, que é exatamente quando desfazer isso seria
pior.

Esta regra é outro caso: ela não foi desligada por ninguém, ela **nasceu**
desligada, com a condição de religamento escrita. Uma migração liga uma chave,
uma vez, com o motivo versionado — e continua respeitando quem a desligar depois.

O `reverse` desliga de volta: uma migração que não sabe voltar é uma migração
que impede o `migrate` para trás no dia de um rollback.
"""

from __future__ import annotations

from django.db import migrations

CHAVE = "cc-sem-orcado-e-o-inverso"


def ligar(apps, schema_editor):
    RegraExcecao = apps.get_model("workspace", "RegraExcecao")
    RegraExcecao.objects.filter(chave=CHAVE).update(ativa=True)


def desligar(apps, schema_editor):
    RegraExcecao = apps.get_model("workspace", "RegraExcecao")
    RegraExcecao.objects.filter(chave=CHAVE).update(ativa=False)


class Migration(migrations.Migration):
    dependencies = [
        ("workspace", "0056_metas_avaliacao_e_pdi"),
    ]

    operations = [
        migrations.RunPython(ligar, desligar),
    ]
