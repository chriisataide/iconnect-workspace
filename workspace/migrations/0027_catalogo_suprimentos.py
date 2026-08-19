"""Remoções e substituição do catálogo — §14, §24, §26 do pedido.

Todas seguem a mesma regra, que é a que você escolheu: **some da tela, o dado
fica**. `ativo=False` e nunca `delete()` — `SolicitacaoServico.item` é `PROTECT`,
e apagar o item exigiria apagar junto o histórico de quem já pediu.

## O que sai

- `epi` e `material` (§14) — três formulários com os mesmos quatro campos.
- `material-marketing` (§24)
- `parecer-juridico` (§26)

## O que entra, e por que NÃO é aqui

`controle-materiais` substitui os dois primeiros — o tipo de material vira CAMPO
em vez de item separado. Ele entra pela SEMENTE (`CATALOGO_INICIAL` +
`semear_catalogo`), que é de onde vem todo item deste produto, e não por esta
migração.

Criá-lo aqui parecia mais direto e estava errado: migração roda em todo banco de
TESTE também, e o item nasceria em cada um deles. Vinte e três testes que
assumem catálogo vazio quebraram de uma vez — foi assim que este comentário
ficou sabendo. `semear_catalogo` cria item por item o que ainda não existe, então
o banco que já roda recebe o novo com um comando, sem migração de dados.

Pedidos em aberto dos itens removidos não são tocados: fechar a porta de
entrada não cancela quem já entrou.
"""

from django.db import migrations

DESATIVAR = ["epi", "material", "material-marketing", "parecer-juridico"]

def aplicar(apps, schema_editor):
    apps.get_model("workspace", "ItemCatalogo").objects.filter(
        chave__in=DESATIVAR
    ).update(ativo=False)


def desfazer(apps, schema_editor):
    apps.get_model("workspace", "ItemCatalogo").objects.filter(
        chave__in=DESATIVAR
    ).update(ativo=True)


class Migration(migrations.Migration):
    dependencies = [("workspace", "0026_desativa_trabalho_remoto")]
    operations = [migrations.RunPython(aplicar, desfazer)]
