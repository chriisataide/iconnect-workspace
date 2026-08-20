"""Configura a cadeia de aprovação com o teto real da empresa.

    python manage.py semear_regras_aprovacao            # relatório
    python manage.py semear_regras_aprovacao --aplicar

Comando e não cliques no admin porque o teto é **regra de negócio versionada**:
quando alguém perguntar em dezembro por que uma compra de R$ 80.000 foi para a
diretoria, a resposta tem de estar no git com data e autor — não na memória de
quem configurou a tela.

## A cadeia (12/08/2026 · área acrescentada em 17/08 · área RETIRADA em 20/08)

    sempre                 gestor direto
    R$ 50.000 …  300.000   + diretoria
    acima de R$ 300.000    + sócios

As faixas são **cumulativas**, não excludentes: um pedido de R$ 400.000 passa
pelos três degraus, na ordem. É o desenho do motor (`RegraAprovacao.valor_minimo`
é "a etapa entra quando o valor alcança este mínimo"), e é o comportamento certo
— sócio aprovando sem o gestor ter visto é como a nota some do orçamento da área.

## Por que o degrau da ÁREA saiu

Ele entrou em 17/08 respondendo a uma pergunta legítima: quem decide férias, o
gestor ou o R.H.? Os dois — o gestor sabe se a equipe aguenta a ausência, o
R.H. sabe se há saldo e se o período é legal.

A pergunta continua legítima. O que estava errado era o LUGAR da resposta.

Com o degrau, a área tocava o mesmo pedido **duas vezes**: aprovava na bandeja
e depois executava na fila. Do lado de quem pedia, o efeito era um pedido que
já tinha sido aprovado pelo gestor e continuava dizendo "aguardando aprovação",
sem que nada tivesse mudado de mãos. Do lado da área, eram duas telas para uma
decisão que ela toma uma vez só — porque para o Financeiro "aprovar o
adiantamento" e "pagar o adiantamento" são o mesmo ato.

A revisão da área não sumiu: ela é a fila. Quem atende olha o pedido, e ou
**conclui** (fez) ou **devolve** com o motivo — e devolver agora tem volta, que
é o que faltava para essa ser a resposta certa. O R.H. que vê férias sem saldo
devolve dizendo isso, a pessoa corrige e reenvia, e a cadeia recomeça do gestor.

Antes do reenvio existir, devolver era um beco — e é por isso que o degrau
extra parecia necessário: reprovar na bandeja era a única forma de dizer não
sem prender o pedido para sempre.
"""

from __future__ import annotations

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from identidade.models import Papel
from workspace.models.aprovacao import RegraAprovacao, TipoAprovador

# `dominio="*"` vale para todos. Faixa por VALOR, não por área: um reembolso de
# R$ 60.000 é tão relevante quanto uma compra de R$ 60.000, e criar tetos
# diferentes por domínio é o começo do labirinto de exceções.
# ── O degrau que foi retirado ───────────────────────────────────────
#
# Estas regras foram criadas em 17/08 e desativadas em 20/08 (ver a docstring).
# A lista fica aqui, e o comando as DESATIVA em vez de apagar: `RegraAprovacao`
# é referenciada por `EtapaAprovacao` de todo pedido que já passou por ela, e
# apagar a linha levaria junto a explicação de por que aquele pedido teve um
# degrau a mais em setembro.
#
# `ativa=False` tira da cadeia dos pedidos NOVOS e deixa a história inteira de
# pé — é a regra da casa (§60), e é a diferença entre mudar o processo e apagar
# o que aconteceu.
AREAS_RETIRADAS = ["rh.", "fin.", "com.", "hab.", "ven.", "log."]

#: A ordem que o degrau da área ocupava. Nenhuma regra nova usa esta posição.
ORDEM_DA_AREA = 15

CADEIA = [
    {
        "ordem": 10,
        "valor_minimo": Decimal("0"),
        "tipo": TipoAprovador.GESTOR_DIRETO,
        "papel": None,
        "rotulo": "sempre · gestor direto",
    },
    {
        "ordem": 20,
        "valor_minimo": Decimal("50000"),
        "tipo": TipoAprovador.PAPEL,
        "papel": "diretoria",
        "rotulo": "≥ R$ 50.000 · diretoria",
    },
    {
        "ordem": 30,
        "valor_minimo": Decimal("300000"),
        "tipo": TipoAprovador.PAPEL,
        "papel": "socios",
        "rotulo": "≥ R$ 300.000 · sócios",
    },
]


class Command(BaseCommand):
    help = "Semeia a cadeia de aprovação por faixa de valor."

    def add_arguments(self, parser):
        parser.add_argument("--aplicar", action="store_true", help="Grava.")

    def handle(self, *args, **opcoes):
        aplicar = opcoes["aplicar"]
        if not aplicar:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --aplicar.\n")
            )

        with transaction.atomic():
            criadas, existentes, faltando = self._semear()
            if not aplicar:
                transaction.set_rollback(True)

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Cadeia de aprovação"))
        for rotulo in criadas:
            self.stdout.write(self.style.SUCCESS(f"  + {rotulo}"))
        for rotulo in existentes:
            self.stdout.write(f"  = {rotulo} (já existia)")

        if faltando:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR("  PAPÉIS AUSENTES"))
            for chave in faltando:
                self.stdout.write(f"     {chave} — rode `semear_papeis --aplicar`")
            return

        if aplicar:
            self.stdout.write(self.style.SUCCESS("\n✓ Aplicado."))
            self.stdout.write(
                "  Confira em /admin/workspace/regraaprovacao/. Etapa de gestor "
                "direto é PULADA para quem não tem gestor na lotação."
            )

    def _semear(self):
        criadas: list[str] = []
        existentes: list[str] = []
        faltando: list[str] = []

        # O degrau da ÁREA sai da cadeia. Desativado e não apagado — as etapas
        # dos pedidos que já passaram por ele apontam para estas linhas.
        desativadas = RegraAprovacao.objects.filter(
            dominio__in=AREAS_RETIRADAS, ordem=ORDEM_DA_AREA, ativa=True
        )
        for regra in desativadas:
            criadas.append(f"− {regra.dominio} · revisão de área DESATIVADA")
        desativadas.update(ativa=False)

        for spec in CADEIA:
            papel = None
            if spec["papel"]:
                papel = Papel.objects.filter(chave=spec["papel"]).first()
                if papel is None:
                    faltando.append(spec["papel"])
                    continue

            ja_existe = RegraAprovacao.objects.filter(
                dominio="*",
                valor_minimo=spec["valor_minimo"],
                tipo=spec["tipo"],
                ordem=spec["ordem"],
            ).exists()

            if ja_existe:
                existentes.append(spec["rotulo"])
                continue

            # Cria sempre: a simulação é o `set_rollback` do chamador, e não um
            # segundo caminho de código. Caminho de simulação separado do
            # caminho real é como a simulação passa a mentir.
            RegraAprovacao.objects.create(
                dominio="*",
                valor_minimo=spec["valor_minimo"],
                tipo=spec["tipo"],
                papel=papel,
                ordem=spec["ordem"],
                ativa=True,
            )
            criadas.append(spec["rotulo"])

        return criadas, existentes, faltando
