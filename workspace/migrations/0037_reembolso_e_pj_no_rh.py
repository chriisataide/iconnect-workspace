"""O R.H. passa a TRATAR reembolso e pagamento de PJ, e o chamado predial sai.

## Reembolso e PJ mudam de dono, não só de lugar

`fin.reembolso` → `rh.reembolso` e `fin.pj` → `rh.pj`.

Isto NÃO é troca de rótulo: `dominio` decide de quem é a fila que executa. O
R.H. passa a receber esses pedidos — que é o que a empresa faz na prática, e foi
a decisão tomada depois de a pergunta ser feita: quem confere o comprovante e
libera o pagamento é o R.H.

A cadeia de aprovação sai de graça das regras que já existem: `*` ordem 10 é o
gestor direto, `rh.` ordem 15 é a área. Fica **gestor → R.H.**, sem regra nova.

Os pedidos JÁ FEITOS se movem junto, inclusive os em aberto — é o que "mover
para o R.H." quer dizer. Um reembolso parado na fila do Financeiro não deveria
continuar lá depois de a empresa decidir que quem trata é o R.H.

O ADIANTAMENTO fica em `fin.`: dinheiro que sai ANTES da despesa é do
Financeiro. A prestação de contas de um adiantamento passa a cruzar os dois
domínios de propósito — o R.H. confere os recibos, o Financeiro adiantou.

## Manutenção predial é aposentada

O chamado predial vive no iConnect Platform, que tem ordem de serviço, despacho,
SLA e o histórico junto do cliente. Manter os dois criaria duas filas para o
mesmo trabalho — e a segunda seria a que ninguém olha.

`ativo=False` e não `delete()`, como todas as outras: os chamados prediais já
abertos continuam no histórico e nos indicadores.
"""

from django.db import migrations

MUDAM = {"fin.reembolso": "rh.reembolso", "fin.pj": "rh.pj"}


def aplicar(apps, schema_editor):
    Item = apps.get_model("workspace", "ItemCatalogo")
    for de, para in MUDAM.items():
        Item.objects.filter(dominio=de).update(dominio=para)
    Item.objects.filter(chave="manutencao-predial").update(ativo=False)


def desfazer(apps, schema_editor):
    Item = apps.get_model("workspace", "ItemCatalogo")
    for de, para in MUDAM.items():
        Item.objects.filter(dominio=para).update(dominio=de)
    Item.objects.filter(chave="manutencao-predial").update(ativo=True)


class Migration(migrations.Migration):
    dependencies = [("workspace", "0036_remove_itemcatalogo_modulos_extras")]
    operations = [migrations.RunPython(aplicar, desfazer)]
