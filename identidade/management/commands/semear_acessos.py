"""Dá acesso e papel às pessoas do organograma de demonstração.

    python manage.py semear_acessos            # relatório, sem gravar
    python manage.py semear_acessos --aplicar

## Por que este comando existe

O `importar_organograma` traz quem é quem: cargo, departamento, gestor. Ele não
traz **credencial** — CSV de organograma não tem senha, e não deveria ter.

O resultado é um ambiente onde o organograma está certo e ninguém consegue
entrar: das sete pessoas do exemplo, duas tinham senha e cinco não. E, do outro
lado, cinco áreas de aprovação sem nenhum titular — o pedido chegava no degrau
de Compras e parava, porque Compras não era de ninguém.

Este comando fecha os dois buracos de uma vez, para que dê para percorrer o
fluxo inteiro — pedir, aprovar em cadeia, atender, reabrir — com pessoas
diferentes.

## O que ele NUNCA faz

**Não troca senha que já existe.** Quem já consegue entrar é deixado em paz, e
isso inclui você: rodar este comando por engano não pode ser o jeito de perder
o acesso ao próprio ambiente.

**Não toca em superusuário.** Conta de emergência não é conta de demonstração.
Isso vale inclusive com `--resortear`.

**Não roda fora do DEBUG sem `--forcar`.** Semear senha conhecida em produção é
exatamente o acidente que este guarda impede.

## Sobre a senha

Sorteada, uma por pessoa, impressa UMA vez no terminal de quem rodou. Não fica
em arquivo, não vai para o banco em claro, não é derivada do e-mail. Senha
previsível em ambiente de demonstração vira senha previsível em produção no dia
em que alguém copia o comando.

`--resortear` troca a de quem já tem — serve para quando a senha passou por um
lugar por onde não devia (o log de um CI, uma janela compartilhada) e você quer
uma nova sem mexer no banco à mão.

## Sobre os papéis

O mapa abaixo é por CARGO, e é de demonstração: numa empresa de verdade quem
aprova Compras é decisão de gente, não de código. Ele existe para que as áreas
que travam a cadeia tenham dono, e a escolha de cada uma está escrita ao lado.

A concessão passa pelo mesmo serviço que a tela de papéis usa. Assim este
comando não consegue criar um estado que a tela não conseguiria — inclusive a
justificativa escrita, que os escopos amplos exigem.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.crypto import get_random_string

from identidade.models import AtribuicaoPapel, Lotacao, Papel
from identidade.services import administracao as adm

# Alfabeto sem `l`, `1`, `O` e `0`: esta senha vai ser lida na tela e digitada à
# mão, e o par que se confunde na fonte do terminal produz um "senha inválida"
# que ninguém consegue explicar.
ALFABETO = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TAMANHO_SENHA = 16

# Cargo → papéis. Um dicionário e não heurística sobre o texto do cargo: a
# heurística acerta hoje e erra no primeiro cargo novo, em silêncio.
POR_CARGO: dict[str, list[str]] = {
    # Aprova tudo, no topo da cadeia.
    "Sócio": ["socios"],
    # Diretoria destrava o degrau de diretoria; vendas fica aqui porque no
    # organograma de exemplo não existe ninguém comercial, e a área precisa de
    # dono para o pedido não morrer no meio do caminho.
    "Diretor de Operações": ["diretoria", "vendas"],
    # Gestor é o degrau de equipe. Operação e SESMT vão para quem está no
    # campo — é de lá que saem o incidente e a exigência de habilitação.
    "Gerente de Campo": ["gestor", "operacao", "sesmt"],
    # Compras com quem já tem equipe: o degrau de compras é o que mais aparece
    # na cadeia, e sem titular ele engole a requisição inteira.
    "Gerente de Suporte": ["gestor", "compras"],
    # Sem papel de área: são justamente as pessoas que servem para testar o
    # lado de QUEM PEDE. Portal com todo mundo aprovador não prova nada.
    "Analista de Suporte": ["colaborador"],
    "Técnico de Campo": ["colaborador"],
}

JUSTIFICATIVA = (
    "Ambiente de demonstração: área sem titular trava a cadeia de aprovação."
)


class Command(BaseCommand):
    help = "Sorteia senha e concede papéis às pessoas do organograma de exemplo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--aplicar",
            action="store_true",
            help="Grava. Sem esta flag, só relata o que faria.",
        )
        parser.add_argument(
            "--forcar",
            action="store_true",
            help="Permite rodar com DEBUG=False. Pense duas vezes.",
        )
        parser.add_argument(
            "--resortear",
            action="store_true",
            help="Troca a senha de quem já tem. Superusuário continua intocado.",
        )

    def handle(self, *args, **opcoes):
        aplicar = opcoes["aplicar"]

        if not settings.DEBUG and not opcoes["forcar"]:
            raise CommandError(
                "DEBUG=False. Este comando semeia acesso de demonstração e não "
                "deve tocar um ambiente real. Use --forcar se for mesmo isso."
            )

        if not aplicar:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --aplicar.\n")
            )

        with transaction.atomic():
            senhas, papeis, pulados = self._semear(aplicar, opcoes["resortear"])
            if not aplicar:
                transaction.set_rollback(True)

        self._relatar(senhas, papeis, pulados, aplicar)

    # ── O trabalho ──────────────────────────────────────────────────

    def _semear(self, aplicar, resortear=False):
        quem = self._concedente()
        senhas: list[tuple[str, str]] = []
        papeis: list[str] = []
        pulados: list[str] = []

        for lotacao in Lotacao.objects.select_related("user").order_by("user__email"):
            pessoa = lotacao.user

            if pessoa.is_superuser:
                pulados.append(f"{pessoa.email} · superusuário")
                continue

            if pessoa.has_usable_password() and not resortear:
                pulados.append(f"{pessoa.email} · já tem senha")
            else:
                senha = get_random_string(TAMANHO_SENHA, ALFABETO)
                if aplicar:
                    pessoa.set_password(senha)
                    pessoa.save(update_fields=["password"])
                senhas.append((pessoa.email, senha))

            papeis.extend(self._conceder_do_cargo(pessoa, lotacao, quem, aplicar))

        return senhas, papeis, pulados

    def _conceder_do_cargo(self, pessoa, lotacao, quem, aplicar) -> list[str]:
        feitos = []
        for chave in POR_CARGO.get(lotacao.cargo, []):
            papel = Papel.objects.filter(chave=chave, ativo=True).first()
            if papel is None:
                # Papel que não existe é erro de configuração, não de dado:
                # `semear_papeis` roda antes deste comando.
                feitos.append(f"{pessoa.email} · {chave} · PAPEL NÃO EXISTE")
                continue

            escopo = papel.escopo_padrao
            if AtribuicaoPapel.objects.vigentes().filter(
                user=pessoa, papel=papel, escopo=escopo
            ).exists():
                continue  # reexecutável: quem já tem, tem

            if aplicar:
                adm.conceder(
                    pessoa=pessoa,
                    papel=papel,
                    escopo=escopo,
                    quem=quem,
                    justificativa=JUSTIFICATIVA,
                )
            feitos.append(f"{pessoa.email} · {papel.nome} ({escopo})")
        return feitos

    def _concedente(self):
        """Quem assina as concessões.

        `concedido_por` é obrigatório de propósito: concessão sem autor não
        responde à única pergunta que importa depois de um incidente. Aqui o
        autor é o superusuário — é ele quem rodou o comando.
        """
        quem = get_user_model().objects.filter(is_superuser=True).order_by("pk").first()
        if quem is None:
            raise CommandError(
                "Nenhum superusuário no banco. Toda concessão precisa de autor: "
                "crie um com `manage.py createsuperuser` e rode de novo."
            )
        return quem

    # ── O relatório ─────────────────────────────────────────────────

    def _relatar(self, senhas, papeis, pulados, aplicar):
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Papéis concedidos"))
        for linha in papeis or ["  (nenhum — todos já tinham)"]:
            self.stdout.write(f"  {linha}")

        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Intocados"))
        for linha in pulados or ["  (nenhum)"]:
            self.stdout.write(f"  {linha}")

        if senhas and not aplicar:
            # Na simulação a senha NÃO é impressa. A transação vai voltar, e
            # quem anotasse descobriria na hora de entrar que o que está no
            # papel não vale — pior que não ter mostrado nada.
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("Senhas que seriam sorteadas"))
            for email, _ in senhas:
                self.stdout.write(f"  {email:<45} (sorteada ao aplicar)")

        if senhas and aplicar:
            self.stdout.write("")
            self.stdout.write(self.style.MIGRATE_HEADING("Senhas — anote agora"))
            self.stdout.write(
                self.style.WARNING(
                    "  Elas não são guardadas em lugar nenhum e não dá para "
                    "mostrá-las de novo.\n"
                )
            )
            for email, senha in senhas:
                self.stdout.write(f"  {email:<45} {senha}")

        self.stdout.write("")
        if aplicar:
            self.stdout.write(self.style.SUCCESS("✓ Aplicado."))
        else:
            self.stdout.write(
                self.style.WARNING("Nada foi gravado. Rode com --aplicar.")
            )
