"""`Contrato.servico` deixa de nomear equipamento e passa a nomear contratação.

## O mapeamento, e por que ele pode ser feito sem consultar ninguém

`cftv` e `alarme` diziam O QUE está instalado; `instalacao` dizia uma etapa. Os
três respondiam a uma pergunta diferente da que o campo faz agora — COMO o
contrato foi vendido —, e por isso não existe tradução exata: um contrato de
CFTV pode ter sido vendido como projeto, como locação ou como manutenção.

Traduzir sem saber seria inventar dado. O que autoriza esta migration é uma
resposta do dono do produto em 09/09/2026: **não há contrato real ainda**. As
linhas afetadas são todas de massa de demonstração, e `semear_resultados` as
regenera com os valores novos.

Se um dia esta migration rodar sobre dado real — não deve, mas migrations
sobrevivem a suposições —, o mapeamento abaixo é o menos errado e não o certo:
`instalacao` vira `projeto` porque instalar é entregar uma obra, e os dois de
equipamento viram `monitoramento` porque é a forma recorrente mais comum. Um
`RunPython` não tem como perguntar, e recusar a carga deixaria o banco inválido.

## A volta

`reverse` existe e não é decorativo: sem ele, `migrate resultados 0003` falharia
e o banco de desenvolvimento ficaria preso nesta versão. Ela é uma APROXIMAÇÃO
declarada — `projeto`, `locacao` e `projeto_turnkey` não existiam antes, e todos
voltam como `instalacao`. Descer e subir de novo não devolve o estado original,
e é por isso que o comentário está aqui em vez de a função fingir simetria.
"""

from django.db import migrations, models

#: `antigo → novo`. Ver o cabeçalho para o que autoriza cada linha.
PARA_NOVO = {
    "instalacao": "projeto",
    "cftv": "monitoramento",
    "alarme": "monitoramento",
}

#: A volta, aproximada e declarada como tal.
PARA_ANTIGO = {
    "projeto": "instalacao",
    "projeto_turnkey": "instalacao",
    "locacao": "instalacao",
}


def _traduzir(apps, mapa):
    Contrato = apps.get_model("resultados", "Contrato")
    for antigo, novo in mapa.items():
        Contrato.objects.filter(servico=antigo).update(servico=novo)


def para_frente(apps, schema_editor):
    _traduzir(apps, PARA_NOVO)


def para_tras(apps, schema_editor):
    _traduzir(apps, PARA_ANTIGO)


class Migration(migrations.Migration):

    dependencies = [
        ("resultados", "0003_area_contrato_area"),
    ]

    operations = [
        # A TRADUÇÃO VEM ANTES do `AlterField`, e a ordem não é indiferente:
        # `choices` não é restrição de banco no Django, mas rodar depois deixaria
        # uma janela em que o campo declara cinco valores e a tabela guarda oito
        # — e qualquer `full_clean` no meio reprovaria linhas que a própria
        # migration ia consertar.
        migrations.RunPython(para_frente, para_tras),
        migrations.AlterField(
            model_name="contrato",
            name="servico",
            field=models.CharField(
                choices=[
                    ("projeto", "Projeto"),
                    ("monitoramento", "Monitoramento"),
                    ("manutencao", "Manutenção"),
                    ("locacao", "Locação"),
                    ("projeto_turnkey", "Projeto turnkey"),
                ],
                max_length=20,
            ),
        ),
    ]
