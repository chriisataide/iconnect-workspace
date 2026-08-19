"""Reservar carro passa a ter UM caminho — a grade de Reservas. §18.

## A duplicação

Veículo existia duas vezes no produto, e as duas metades não se conheciam:

* `Recurso(tipo=VEICULO)` — a grade de Reservas, que garante por transação que
  duas pessoas não peguem a van no mesmo horário;
* o item de catálogo `veiculo` ("Reservar carro ou utilitário"), um formulário
  com "período" em TEXTO LIVRE que virava pedido numa fila de atendimento.

Marcar pelo primeiro não bloqueava o segundo. A van aparecia livre na grade
para quem tinha aberto o pedido, e livre no pedido para quem tinha marcado na
grade — Suprimentos atendia os dois de boa-fé, e no dia duas equipes chegavam
na porta esperando o mesmo veículo. O choque não era detectável em lugar
nenhum: um lado guardava `datetime`, o outro guardava a frase "de terça a
quinta".

## Por que o item sai, e não a grade

A grade tem a garantia; o item tem um campo de texto. Manter os dois e "avisar
para usar um só" é a versão do problema que sobrevive a qualquer documentação.

## `ativo=False` e não `delete()`

Mesma regra de `0026_desativa_trabalho_remoto`: `SolicitacaoServico.item` é
`PROTECT`, os pedidos de veículo já feitos continuam no histórico, os
indicadores do período continuam certos, e um `ativo=True` devolve o item se a
decisão mudar.

Pedidos EM ABERTO não são tocados: fechar a porta de entrada não é motivo para
cancelar quem já entrou.
"""

from django.db import migrations

CHAVE = "veiculo"


def desativar(apps, schema_editor):
    apps.get_model("workspace", "ItemCatalogo").objects.filter(chave=CHAVE).update(
        ativo=False
    )


def reativar(apps, schema_editor):
    apps.get_model("workspace", "ItemCatalogo").objects.filter(chave=CHAVE).update(
        ativo=True
    )


class Migration(migrations.Migration):
    dependencies = [
        ("workspace", "0043_alter_notificacao_tipo_veiculo_despesaveiculo_and_more")
    ]
    operations = [migrations.RunPython(desativar, reativar)]
