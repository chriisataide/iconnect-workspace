"""Troca o campo de comprovantes do reembolso pela lista de compras.

Mesma razão da 0011 e da 0013: `semear_catalogo` não mexe em item existente, e
sem esta migração o reembolso já semeado continuaria pedindo um campo
`comprovantes` que a tela nova não desenha mais — o formulário abriria sem
nenhuma forma de anexar nada.

Aqui a migração SUBSTITUI, e não só acrescenta, porque o campo antigo e o novo
resolvem a mesma coisa de jeitos incompatíveis: `comprovantes` é um punhado de
arquivos com um valor único somado à mão; `despesas` é uma linha por compra,
com o valor de cada uma. Manter os dois faria a tela pedir os comprovantes duas
vezes.

Os pedidos ANTIGOS não são convertidos, de propósito: o anexo deles continua no
lugar, ligado à solicitação, e ninguém sabe qual valor pertence a qual cupom —
essa informação nunca foi coletada. Inventar uma divisão para preencher a nova
tabela produziria uma prestação de contas falsa; a lista de compras fica vazia
para eles e a tela cai no valor total, que é o dado que de fato existe.
"""

from django.db import migrations

CHAVE = "reembolso"
ANTIGO = "comprovantes"

NOVOS = [
    {"chave": "despesas", "rotulo": "Compras", "tipo": "despesas",
     "obrigatorio": True,
     "ajuda": "Um comprovante por compra, com o valor e o motivo dela."},
    {"chave": "adiantamento", "rotulo": "Adiantamento a prestar contas",
     "tipo": "adiantamento", "obrigatorio": False,
     "ajuda": "Se este gasto saiu de um adiantamento, atrele aqui."},
]


def trocar(apps, schema_editor):
    ItemCatalogo = apps.get_model("workspace", "ItemCatalogo")

    item = ItemCatalogo.objects.filter(chave=CHAVE).first()
    if item is None:
        return

    campos = [
        c for c in (item.campos or [])
        if not (isinstance(c, dict) and c.get("chave") == ANTIGO)
    ]
    existentes = {c.get("chave") for c in campos if isinstance(c, dict)}
    campos.extend(dict(novo) for novo in NOVOS if novo["chave"] not in existentes)

    item.campos = campos
    item.save(update_fields=["campos"])


def desfazer(apps, schema_editor):
    ItemCatalogo = apps.get_model("workspace", "ItemCatalogo")

    item = ItemCatalogo.objects.filter(chave=CHAVE).first()
    if item is None:
        return

    novas = {novo["chave"] for novo in NOVOS}
    campos = [
        c for c in (item.campos or [])
        if not (isinstance(c, dict) and c.get("chave") in novas)
    ]
    campos.append({
        "chave": ANTIGO, "rotulo": "Comprovantes", "tipo": "arquivo",
        "obrigatorio": True,
        "ajuda": "Fotografe os cupons — nós lemos o resto.",
    })
    item.campos = campos
    item.save(update_fields=["campos"])


class Migration(migrations.Migration):
    dependencies = [
        ("workspace", "0014_solicitacaoservico_adiantamento_acertoadiantamento_and_more"),
    ]

    operations = [
        migrations.RunPython(trocar, desfazer),
    ]
