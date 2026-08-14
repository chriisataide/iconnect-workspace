"""Acrescenta aos itens já criados os campos novos de R.H. e adiantamento.

Mesma razão da 0011: `semear_catalogo` casa por `chave` e não sobrescreve item
existente, então mudar `catalogo_inicial.py` não muda nada em banco que já foi
semeado — `--aplicar` diria "criados 0" e o formulário continuaria com os campos
antigos.

Só ACRESCENTA campo cuja `chave` ainda não existe no item. Campo que alguém
editou no admin fica como está, e a migração pode rodar de novo sem desfazer
trabalho de ninguém.

Não valida o teto de 3 obrigatórios de propósito: `full_clean` não roda em
modelo histórico, e um item que alguém customizou não pode ser recusado por uma
migração — o teto continua valendo onde ele é aplicado, que é no admin e no
semeador.
"""

from django.db import migrations

# Escrito à mão, e não lido de `catalogo_inicial.py`, porque migração é um
# retrato do que mudou NESTE ponto da história: se a semente mudar de novo, esta
# migração precisa continuar aplicando o que ela aplicava hoje.
CAMPOS_NOVOS = {
    "atestado": [
        {"chave": "horario", "rotulo": "Horário", "tipo": "texto",
         "obrigatorio": True, "ajuda": "Das 14h às 16h, ou o dia todo."},
        {"chave": "motivo", "rotulo": "Motivo", "tipo": "texto_longo",
         "obrigatorio": False,
         "ajuda": "Consulta, exame, acompanhamento de familiar."},
        {"chave": "chefe_ciente", "rotulo": "Qual chefe estava ciente",
         "tipo": "texto", "obrigatorio": False,
         "ajuda": "Quem você avisou. Em branco, entende-se o gestor da sua lotação."},
    ],
    "home-office": [
        {"chave": "dias", "rotulo": "Dias", "tipo": "numero",
         "obrigatorio": True, "ajuda": "Quantos dias de trabalho remoto."},
        {"chave": "motivo", "rotulo": "Motivo", "tipo": "texto_longo",
         "obrigatorio": True},
    ],
    "declaracao": [
        {"chave": "anexo", "rotulo": "Anexo", "tipo": "arquivo",
         "obrigatorio": False,
         "ajuda": "Modelo exigido por quem pediu a declaração, se houver."},
    ],
    "adiantamento": [
        {"chave": "data_pagamento", "rotulo": "Data de pagamento",
         "tipo": "data", "obrigatorio": True,
         "ajuda": "Quando você precisa do dinheiro na conta."},
        {"chave": "dados_bancarios", "rotulo": "Conta do beneficiário",
         "tipo": "texto_longo", "obrigatorio": True,
         "ajuda": "Banco, agência, conta e chave PIX, se houver."},
        {"chave": "supervisor_ciente", "rotulo": "Supervisor ciente",
         "tipo": "texto", "obrigatorio": False,
         "ajuda": "Quem você combinou o adiantamento."},
        {"chave": "orcamento", "rotulo": "Orçamento", "tipo": "arquivo",
         "obrigatorio": False,
         "ajuda": "Anexe se já houver orçamento ou proposta."},
    ],
}

# Onde o campo novo entra. Sem isto, "Horário" apareceria depois do anexo do
# atestado — a ordem da lista é a ordem da tela.
POSICAO = {("atestado", "horario"): 1}


def acrescentar(apps, schema_editor):
    ItemCatalogo = apps.get_model("workspace", "ItemCatalogo")

    for item in ItemCatalogo.objects.filter(chave__in=CAMPOS_NOVOS):
        campos = list(item.campos or [])
        existentes = {c.get("chave") for c in campos if isinstance(c, dict)}
        mudou = False

        for novo in CAMPOS_NOVOS[item.chave]:
            if novo["chave"] in existentes:
                continue
            posicao = POSICAO.get((item.chave, novo["chave"]))
            if posicao is None:
                campos.append(dict(novo))
            else:
                campos.insert(posicao, dict(novo))
            mudou = True

        if mudou:
            item.campos = campos
            item.save(update_fields=["campos"])


def desfazer(apps, schema_editor):
    """Remove só os campos que esta migração acrescentou.

    Vale a pena escrever a volta: sem ela, descer uma versão deixaria o
    formulário pedindo dado que a versão anterior não sabe ler.
    """
    ItemCatalogo = apps.get_model("workspace", "ItemCatalogo")

    for item in ItemCatalogo.objects.filter(chave__in=CAMPOS_NOVOS):
        remover = {c["chave"] for c in CAMPOS_NOVOS[item.chave]}
        campos = [
            c for c in (item.campos or [])
            if not (isinstance(c, dict) and c.get("chave") in remover)
        ]
        if len(campos) != len(item.campos or []):
            item.campos = campos
            item.save(update_fields=["campos"])


class Migration(migrations.Migration):
    dependencies = [
        ("workspace", "0012_reserva_e_correspondencia"),
    ]

    operations = [
        migrations.RunPython(acrescentar, desfazer),
    ]
