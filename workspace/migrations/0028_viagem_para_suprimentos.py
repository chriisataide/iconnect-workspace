"""Viagem sai do Financeiro e vai para Suprimentos — §13.

## Por que é migração, e não só semente

`semear_catalogo` pula item que já existe, então a mudança de `dominio` no
`CATALOGO_INICIAL` não alcançaria nenhum banco que já roda. E a mudança precisa
alcançar: `dominio` decide de quem é a FILA que executa.

## O que muda de verdade

`fin.viagem` → `log.viagem`. Os pedidos de viagem já feitos apontam para o mesmo
`ItemCatalogo`, então eles se movem junto — **inclusive os que estão em aberto**.
Isso é intencional e é o que "mover para Suprimentos" quer dizer: um pedido de
passagem parado na fila do Financeiro não deveria continuar lá depois que a
empresa decidiu que quem reserva é Suprimentos.

O que NÃO se move: pedido já concluído continua concluído, e o histórico
continua registrando quem atendeu na época.

## A regra de aprovação que vem junto

Sem uma regra de ordem 15 para `log.`, a mudança removeria em silêncio a revisão
de área — o pedido iria do gestor direto para a fila, e a única pista seria um
degrau a menos. A regra é criada aqui pelo mesmo motivo da mudança de domínio.

As regras por FAIXA DE VALOR (diretoria acima de 50k, sócios acima de 300k) não
são tocadas: elas valem para todo domínio, e é por elas que o dinheiro da viagem
continua sendo olhado.
"""

from decimal import Decimal

from django.db import migrations

DE, PARA = "fin.viagem", "log.viagem"


def mover(apps, schema_editor):
    apps.get_model("workspace", "ItemCatalogo").objects.filter(dominio=DE).update(
        dominio=PARA
    )
    _regra_de_area(apps, "log.", "logistica")


def voltar(apps, schema_editor):
    apps.get_model("workspace", "ItemCatalogo").objects.filter(dominio=PARA).update(
        dominio=DE
    )
    apps.get_model("workspace", "RegraAprovacao").objects.filter(
        dominio="log.", ordem=15
    ).delete()


def _regra_de_area(apps, dominio: str, chave_papel: str) -> None:
    """A revisão da área, se o papel existir.

    Silencioso quando o papel não existe: banco recém-migrado ainda não passou
    por `semear_papeis`, e falhar aqui travaria o `migrate` de uma instalação
    limpa por causa de um dado que chega depois.
    """
    Papel = apps.get_model("identidade", "Papel")
    Regra = apps.get_model("workspace", "RegraAprovacao")

    papel = Papel.objects.filter(chave=chave_papel).first()
    if papel is None or Regra.objects.filter(dominio=dominio, ordem=15).exists():
        return

    Regra.objects.create(
        dominio=dominio,
        ordem=15,
        tipo="papel",
        papel=papel,
        valor_minimo=Decimal("0"),
    )


class Migration(migrations.Migration):
    dependencies = [
        ("workspace", "0027_catalogo_suprimentos"),
        ("identidade", "0001_initial"),
    ]
    operations = [migrations.RunPython(mover, voltar)]
