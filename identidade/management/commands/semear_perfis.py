"""Um usuário POR PAPEL, com o nome do papel. Para testar sem decorar quem é quem.

    python manage.py semear_perfis            # relatório, sem gravar
    python manage.py semear_perfis --aplicar

## Por que este comando existe

O organograma de exemplo tem gente com nome de gente: `gerente.suporte`,
`tecnico.campo`. É realista, e é péssimo para testar — para saber quem vê a fila
de Compras é preciso lembrar que Compras caiu no gerente de suporte, e nada na
tela diz isso.

Aqui o e-mail **é** a resposta: quem entra como `compras@icodev.com.br` atende
Compras. `financeiro@` vê a fila do Financeiro. `colaborador@` não vê fila
nenhuma, e é esse o teste.

Os dois convivem de propósito: o organograma prova que o produto funciona com
gente de verdade, e estes perfis provam **o quê** cada papel alcança.

## A hierarquia, e por que ela importa

`colaborador@` → `gestor@` → `diretoria@` → `socios@`, e todo perfil de área
responde a `gestor@`. Sem isso a cadeia não teria o primeiro degrau: a regra de
ordem 10 é GESTOR_DIRETO, e ela sai da lotação, não de papel.

Com a hierarquia montada, o caminho inteiro dá para percorrer numa sessão:

    colaborador@ pede → gestor@ aprova → área aprova
    → acima de R$ 50 mil, diretoria@ → acima de R$ 300 mil, socios@

## Sobre a senha

Uma só, e igual para todos, porque o ponto aqui é trocar de perfil rápido. Isto
é ambiente de demonstração e o comando só roda com `DEBUG` ligado — a senha
única é justamente o que não se quer em lugar nenhum além deste.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from identidade.models import AtribuicaoPapel, Departamento, Lotacao, Papel, Unidade
from identidade.services import administracao as adm

SENHA_PADRAO = "workspace123"
DOMINIO = "icodev.com.br"

# Papel → (rótulo na tela, chefe). O chefe é a chave de outro perfil desta
# mesma lista, ou None para quem está no topo.
#
# A ordem importa: o chefe precisa existir antes de quem responde a ele.
PERFIS: list[tuple[str, str, str | None]] = [
    ("socios", "Sócios", None),
    ("diretoria", "Diretoria", "socios"),
    ("gestor", "Gestor", "diretoria"),
    # As áreas respondem ao gestor como qualquer pessoa: elas também PEDEM
    # coisas, e um pedido do R.H. sem primeiro degrau não exercita a cadeia.
    ("rh", "RH", "gestor"),
    ("financeiro", "Financeiro", "gestor"),
    ("compras", "Compras", "gestor"),
    ("vendas", "Vendas", "gestor"),
    ("marketing", "Marketing", "gestor"),
    ("juridico", "Jurídico", "gestor"),
    ("logistica", "Suprimentos", "gestor"),
    # A RECEPÇÃO tem perfil próprio desde a rodada de testes de agosto: quem foi
    # exercitar o aviso de encomenda não achou por onde entrar, porque a função
    # só existia dentro de Suprimentos.
    ("recepcao", "Recepção", "gestor"),
    ("operacao", "Operação", "gestor"),
    ("sesmt", "SESMT", "gestor"),
    ("ti", "TI", "gestor"),
    ("monitoramento", "Monitoramento", "gestor"),
    ("auditoria", "Auditoria", "gestor"),
    # Por último e sem papel de área: é a pessoa que só PEDE, e é contra ela
    # que se mede se o portal esconde alguma coisa que não deveria.
    ("colaborador", "Colaborador", "gestor"),
]

JUSTIFICATIVA = "Perfil de teste: um usuário por papel, para exercitar o acesso."


class Command(BaseCommand):
    help = "Cria um usuário por papel, com o nome do papel, senha única."

    def add_arguments(self, parser):
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Grava. Sem esta flag, só relata o que faria.",
        )
        parser.add_argument(
            "--senha",
            default=SENHA_PADRAO,
            help=f"A senha de todos os perfis. Padrão: {SENHA_PADRAO}",
        )
        parser.add_argument(
            "--forcar",
            action="store_true",
            help="Permite rodar com DEBUG=False. Pense duas vezes.",
        )

    def handle(self, *args, **opcoes):
        aplicar = opcoes["aplicar"]
        senha = opcoes["senha"]

        if not settings.DEBUG and not opcoes["forcar"]:
            raise CommandError(
                "DEBUG=False. Estes perfis têm senha única e conhecida, e não "
                "podem existir num ambiente real. Use --forcar se for mesmo isso."
            )

        if not aplicar:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --aplicar.\n")
            )

        with transaction.atomic():
            linhas = self._semear(aplicar, senha)
            if not aplicar:
                transaction.set_rollback(True)

        self._relatar(linhas, senha, aplicar)

    # ── O trabalho ──────────────────────────────────────────────────

    def _semear(self, aplicar, senha):
        quem = self._concedente()
        unidade, departamento = self._onde(aplicar)
        Pessoa = get_user_model()

        criados: dict[str, object] = {}
        linhas = []

        for indice, (chave, rotulo, chefe) in enumerate(PERFIS, start=1):
            email = f"{chave}@{DOMINIO}"
            pessoa = Pessoa.objects.filter(email__iexact=email).first()
            novo = pessoa is None

            if aplicar:
                if novo:
                    pessoa = Pessoa.objects.create_user(email=email, password=senha)
                else:
                    pessoa.set_password(senha)
                # O nome é o do PAPEL: a tela mostra "Compras aprovou", e é
                # exatamente isso que se quer ler ao conferir um teste.
                #
                # `nome`, e não `first_name`: este projeto tem UM campo de nome
                # (ver `contas.Pessoa`). A primeira versão escrevia
                # `first_name`, o `save()` ignorava sem reclamar, e a tela
                # mostrava "compras" — a parte local do e-mail, que é o que o
                # modelo usa quando não há nome.
                pessoa.nome = f"{rotulo} (perfil)"
                pessoa.save(update_fields=["nome"])

                Lotacao.objects.update_or_create(
                    user=pessoa,
                    defaults={
                        "matricula": f"PF{indice:04d}",
                        "cargo": rotulo,
                        "unidade": unidade,
                        "departamento": departamento,
                        "gestor": criados.get(chefe),
                        "centro_custo_codigo": "1000",
                    },
                )
                criados[chave] = pessoa

            papel = self._papel(chave)
            concedido = self._conceder(pessoa, papel, quem, aplicar)
            linhas.append(
                {
                    "email": email,
                    "papel": papel.nome if papel else f"{chave} · PAPEL NÃO EXISTE",
                    "escopo": papel.escopo_padrao if papel else "—",
                    "chefe": f"{chefe}@{DOMINIO}" if chefe else "—",
                    "estado": "novo" if novo else ("atualizado" if aplicar else "existe"),
                    "papel_novo": concedido,
                }
            )

        return linhas

    def _onde(self, aplicar):
        """Onde os perfis ficam lotados. Cria o mínimo se o banco estiver vazio.

        Metade dos papéis tem escopo `unidade` — Compras, Vendas, Suprimentos,
        Operação. Papel de escopo `unidade` numa lotação SEM unidade não alcança
        nada, e o perfil entraria no sistema parecendo certo e sem enxergar a
        própria fila. Num banco recém-criado é exatamente o que aconteceria.
        """
        unidade = Unidade.objects.order_by("codigo").first()
        departamento = Departamento.objects.order_by("codigo").first()

        if unidade is None and aplicar:
            unidade = Unidade.objects.create(codigo="MTZ", nome="Matriz")
        if departamento is None and aplicar:
            departamento = Departamento.objects.create(codigo="DIR", nome="Diretoria")

        return unidade, departamento

    def _papel(self, chave):
        return Papel.objects.filter(chave=chave, ativo=True).first()

    def _conceder(self, pessoa, papel, quem, aplicar) -> bool:
        """`True` se o papel foi concedido agora. Reexecutável: quem tem, tem."""
        if papel is None or pessoa is None or not aplicar:
            return papel is not None

        if AtribuicaoPapel.objects.vigentes().filter(
            user=pessoa, papel=papel, escopo=papel.escopo_padrao
        ).exists():
            return False

        adm.conceder(
            pessoa=pessoa,
            papel=papel,
            escopo=papel.escopo_padrao,
            quem=quem,
            justificativa=JUSTIFICATIVA,
        )
        return True

    def _concedente(self):
        quem = get_user_model().objects.filter(is_superuser=True).order_by("pk").first()
        if quem is None:
            raise CommandError(
                "Nenhum superusuário no banco. Toda concessão precisa de autor: "
                "crie um com `manage.py createsuperuser` e rode de novo."
            )
        return quem

    # ── O relatório ─────────────────────────────────────────────────

    def _relatar(self, linhas, senha, aplicar):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Perfis"))
        self.stdout.write(
            f"  {'entrar como':<32} {'papel':<24} {'escopo':<10} responde a"
        )
        self.stdout.write("  " + "─" * 88)
        for linha in linhas:
            self.stdout.write(
                f"  {linha['email']:<32} {linha['papel']:<24} "
                f"{linha['escopo']:<10} {linha['chefe']}"
            )

        self.stdout.write("")
        if aplicar:
            self.stdout.write(self.style.SUCCESS(f"✓ Aplicado. Senha de todos: {senha}"))
        else:
            self.stdout.write(
                self.style.WARNING(f"Nada gravado. Rode com --aplicar. Senha: {senha}")
            )
