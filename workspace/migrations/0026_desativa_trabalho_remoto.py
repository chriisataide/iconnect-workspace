"""Trabalho remoto sai da tela do RH — e continua no banco.

Decisão de produto, não defeito: o item deixa de ser oferecido no catálogo.

`ativo=False` e não `delete()`, por três razões que valem para toda remoção
deste tipo:

1. **Os pedidos já feitos continuam existindo.** `SolicitacaoServico.item` é
   `PROTECT` — apagar o item seria impossível sem apagar o histórico junto, e
   o histórico é o que responde "quem pediu home office em março".
2. **Os indicadores continuam certos.** Um item apagado tira do passado
   pedidos que realmente aconteceram, e o painel passa a mentir sobre o volume
   do RH no período.
3. **É reversível com um clique.** `ativo=True` no admin devolve o item, com
   tudo que ele já tinha.

O item também saiu de `CATALOGO_INICIAL`: banco novo não recria o que foi
retirado do produto, e `semear_catalogo` pula o que já existe — sem essa
retirada, um banco novo nasceria com o item ativo de novo.

Pedidos EM ABERTO não são tocados. Quem tem um trabalho remoto aguardando
aprovação continua com ele: fechar a porta de entrada não é motivo para
cancelar o que já entrou.
"""

from django.db import migrations

CHAVE = "home-office"


def desativar(apps, schema_editor):
    apps.get_model("workspace", "ItemCatalogo").objects.filter(chave=CHAVE).update(
        ativo=False
    )


def reativar(apps, schema_editor):
    apps.get_model("workspace", "ItemCatalogo").objects.filter(chave=CHAVE).update(
        ativo=True
    )


class Migration(migrations.Migration):
    dependencies = [("workspace", "0025_alter_etapaaprovacao_situacao_and_more")]
    operations = [migrations.RunPython(desativar, reativar)]
