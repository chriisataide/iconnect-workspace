"""§10 — o R.H. reorganizado.

## O que sai da tela

`declaracao`, `ferias` e `atestado`. Mesma regra das outras remoções, que é a
que você escolheu: **some da tela, o dado fica**. `ativo=False` e nunca
`delete()` — `SolicitacaoServico.item` é `PROTECT`, e apagar levaria junto o
histórico de quem já pediu.

`home-office` já saiu na migração 0026.

## O que esta migração NÃO faz mais

Ela chegou a preencher `modulos_extras` em `prestacao-contas`, para o item
aparecer no R.H. sem mudar de dono. A decisão de negócio veio depois e foi
outra: **o R.H. trata o reembolso mesmo** — confere o comprovante e libera o
pagamento. A mudança de domínio está em `0037`, e o campo foi removido em `0036`.

O trecho foi retirado daqui em vez de deixado como histórico porque ele
escrevia numa coluna que uma migração seguinte apaga: em banco novo, gravar e
apagar; em banco antigo, o mesmo. Zero efeito nos dois, e uma referência a um
campo inexistente para quem for ler.

## O que entra

`pagamento-pj` vem pela SEMENTE, como todo item deste produto — ver o comentário
da migração 0027 sobre por que criar item aqui pollui todo banco de teste.
"""

from django.db import migrations

SAEM = ["declaracao", "ferias", "atestado"]


def aplicar(apps, schema_editor):
    apps.get_model("workspace", "ItemCatalogo").objects.filter(
        chave__in=SAEM
    ).update(ativo=False)


def desfazer(apps, schema_editor):
    apps.get_model("workspace", "ItemCatalogo").objects.filter(
        chave__in=SAEM
    ).update(ativo=True)


class Migration(migrations.Migration):
    dependencies = [("workspace", "0033_itemcatalogo_modulos_extras")]
    operations = [migrations.RunPython(aplicar, desfazer)]
