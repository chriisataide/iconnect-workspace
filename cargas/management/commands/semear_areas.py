"""As cinco áreas comerciais da ADB.

## Por que um comando próprio, e não parte de `semear_resultados`

Porque `Area` **não é massa de demonstração**: é cadastro de produção. O
agrupamento comercial da carteira existe na empresa real, e `semear_resultados`
é o que enche o banco de dado fictício para alguém conseguir olhar a tela.

Misturar os dois faria "limpar a massa de teste" apagar o cadastro comercial —
e faria rodar o seeder em produção parecer uma ideia razoável.

Este comando é **idempotente por código**: rodar de novo atualiza nome e
descrição e não duplica. É seguro chamar depois de cada mudança na lista.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from resultados.models import Area

#: As cinco áreas, na ordem em que a diretoria as lê.
#:
#: A `descricao` é o que aparece no seletor, e ela não é enfeite: "Área 03" não
#: diz nada a ninguém, e um filtro que exige conhecimento prévio é um filtro que
#: só o autor usa.
AREAS: tuple[tuple[str, str, str], ...] = (
    ("area-01", "Área 01", "Santander"),
    ("area-02", "Área 02", "Localiza, Magazine Luiza"),
    ("area-03", "Área 03", "Bradesco, Mercantil, Agibank, Caixa Econômica"),
    ("area-04", "Área 04", "Lojas Americanas"),
    ("area-05", "Área 05", "ROMU"),
)


class Command(BaseCommand):
    help = "Cria ou atualiza as cinco áreas comerciais."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Grava. Sem isto, apenas mostra o que faria.",
        )

    def handle(self, *args, **opcoes) -> None:
        aplicar = opcoes["aplicar"]
        criadas = atualizadas = iguais = 0

        with transaction.atomic():
            for ordem, (codigo, nome, descricao) in enumerate(AREAS, start=1):
                existente = Area.objects.filter(codigo=codigo).first()
                if existente is None:
                    criadas += 1
                    self.stdout.write(f"  + {codigo}  {nome} · {descricao}")
                    if aplicar:
                        Area.objects.create(
                            codigo=codigo, nome=nome,
                            descricao=descricao, ordem=ordem,
                        )
                    continue

                mudou = (
                    existente.nome != nome
                    or existente.descricao != descricao
                    or existente.ordem != ordem
                )
                if not mudou:
                    iguais += 1
                    continue

                atualizadas += 1
                self.stdout.write(f"  ~ {codigo}  {nome} · {descricao}")
                if aplicar:
                    existente.nome = nome
                    existente.descricao = descricao
                    existente.ordem = ordem
                    existente.save(update_fields=["nome", "descricao", "ordem"])

            if not aplicar:
                # `set_rollback` e não `raise`: o comando precisa terminar em
                # zero para poder entrar numa cadeia de `&&` sem derrubá-la.
                transaction.set_rollback(True)

        self.stdout.write(
            f"{criadas} criada(s) · {atualizadas} atualizada(s) · {iguais} sem mudança"
        )
        if not aplicar:
            self.stdout.write(self.style.WARNING("SIMULAÇÃO — nada foi gravado."))
