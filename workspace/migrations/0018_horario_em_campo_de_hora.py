"""Horário do atestado vira dois campos de hora, e a data da VPN fica cinza.

Mesma razão das 0013, 0015 e 0017: `semear_catalogo` não sobrescreve item
existente, então mudar `catalogo_inicial.py` não muda banco já semeado.

**Atestado.** `horario` era texto livre e chegava como "das 14 as 16",
"14h-16h" e "2 da tarde" para a mesma ausência — e o R.H. lança hora, não
frase. Vira `horario_inicio` + `horario_fim`, os dois `type="time"`, que trazem
os dois-pontos e o teclado certo do próprio navegador.

O texto já respondido NÃO é convertido: "2 da tarde" pode ser 14:00 e pode ser
outra coisa, e adivinhar produziria um horário errado com cara de horário
conferido. Pedido antigo mantém o texto em `dados["horario"]`, e o resumo o
mostra com o rótulo antigo.

**VPN.** `ate_quando` ganha `quando_modo: cinza`: em vez de sumir quando o
período é definitivo, fica na tela apagado. O campo é a consequência da escolha
ao lado, e vê-lo desabilitado ensina o que "definitivo" significa.
"""

from django.db import migrations

ANTIGO_HORARIO = "horario"

HORARIOS = [
    {"chave": "horario_inicio", "rotulo": "Saiu às", "tipo": "hora",
     "obrigatorio": False,
     "ajuda": "Em branco quando a ausência foi o dia todo."},
    {"chave": "horario_fim", "rotulo": "Voltou às", "tipo": "hora",
     "obrigatorio": False},
]


def _posicao(campos, chave, padrao):
    for indice, campo in enumerate(campos):
        if isinstance(campo, dict) and campo.get("chave") == chave:
            return indice
    return padrao


def aplicar(apps, schema_editor):
    ItemCatalogo = apps.get_model("workspace", "ItemCatalogo")

    atestado = ItemCatalogo.objects.filter(chave="atestado").first()
    if atestado is not None:
        campos = list(atestado.campos or [])
        onde = _posicao(campos, ANTIGO_HORARIO, len(campos))
        campos = [
            c for c in campos
            if not (isinstance(c, dict) and c.get("chave") == ANTIGO_HORARIO)
        ]
        existentes = {c.get("chave") for c in campos if isinstance(c, dict)}
        novos = [dict(h) for h in HORARIOS if h["chave"] not in existentes]
        campos[onde:onde] = novos
        atestado.campos = campos
        atestado.save(update_fields=["campos"])

    vpn = ItemCatalogo.objects.filter(chave="acesso-vpn").first()
    if vpn is not None:
        campos = list(vpn.campos or [])
        for campo in campos:
            if isinstance(campo, dict) and campo.get("chave") == "ate_quando":
                campo["quando_modo"] = "cinza"
        vpn.campos = campos
        vpn.save(update_fields=["campos"])


def desfazer(apps, schema_editor):
    ItemCatalogo = apps.get_model("workspace", "ItemCatalogo")

    atestado = ItemCatalogo.objects.filter(chave="atestado").first()
    if atestado is not None:
        chaves_novas = {h["chave"] for h in HORARIOS}
        campos = list(atestado.campos or [])
        onde = _posicao(campos, "horario_inicio", len(campos))
        campos = [
            c for c in campos
            if not (isinstance(c, dict) and c.get("chave") in chaves_novas)
        ]
        campos.insert(onde, {
            "chave": ANTIGO_HORARIO, "rotulo": "Horário", "tipo": "texto",
            "obrigatorio": True, "ajuda": "Das 14h às 16h, ou o dia todo.",
        })
        atestado.campos = campos
        atestado.save(update_fields=["campos"])

    vpn = ItemCatalogo.objects.filter(chave="acesso-vpn").first()
    if vpn is not None:
        campos = list(vpn.campos or [])
        for campo in campos:
            if isinstance(campo, dict):
                campo.pop("quando_modo", None)
        vpn.campos = campos
        vpn.save(update_fields=["campos"])


class Migration(migrations.Migration):
    dependencies = [
        ("workspace", "0017_stepper_e_campos_por_ramo"),
    ]

    operations = [
        migrations.RunPython(aplicar, desfazer),
    ]
