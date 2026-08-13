"""Importa o organograma de um CSV. Simulação por padrão.

    python manage.py importar_organograma organograma.csv            # simula
    python manage.py importar_organograma organograma.csv --aplicar

Colunas lidas (`email` é a única obrigatória):

    email  nome  matricula  cargo
    unidade_codigo  unidade_nome
    departamento_codigo  departamento_nome
    gestor_email  centro_custo_codigo  situacao

## Duas passadas, de propósito

A primeira cria as lotações **sem gestor**; a segunda amarra os gestores. Assim
a ordem das linhas no arquivo não importa — e não importar é o que se espera de
uma planilha que RH vai ordenar por departamento, não por hierarquia.

## Por que `--criar-usuarios` é desligado por padrão

Criar conta a partir de planilha é ação de segurança: um e-mail digitado
errado não gera erro, gera **conta fantasma** — que passa a existir, aparecer no
organograma e receber etapa de aprovação que ninguém decide.

A empresa usa Microsoft 365, então em produção a conta deve nascer do **SSO no
primeiro login** (`dashboard/utils/sso.py`), e o CSV apenas pendura a estrutura
organizacional em quem já entrou. A flag existe para semear ambiente de teste e
para o caso de quem ainda não fez o primeiro acesso.

Quando a flag é usada, a conta nasce com `set_unusable_password()`: ela não
autentica por senha, só por SSO. Conta semeada com senha conhecida é a porta que
fica aberta depois que todos esqueceram que ela existe.

## Ciclo é rejeitado no fim, não na linha

Validar A→B na linha de A e B→A na linha de B só pega o ciclo na segunda linha,
com metade do arquivo já gravado. A validação roda ao final, sobre o grafo
inteiro, e reprova a importação toda.
"""

from __future__ import annotations

import csv
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from identidade.models import Departamento, Lotacao, Situacao, Unidade

SITUACOES = {s.value for s in Situacao}


class Command(BaseCommand):
    help = "Importa o organograma de um CSV (email, gestor_email, unidade…)."

    def add_arguments(self, parser):
        parser.add_argument("arquivo", type=str)
        parser.add_argument(
            "--aplicar", action="store_true", help="Grava. Sem isto, só relata."
        )
        parser.add_argument(
            "--criar-estrutura",
            action="store_true",
            default=True,
            help="Cria Unidade/Departamento que não existirem (padrão).",
        )
        parser.add_argument(
            "--criar-usuarios",
            action="store_true",
            help=(
                "Cria conta para quem não tem, SEM senha utilizável. "
                "Desligado por padrão — ver docstring."
            ),
        )

    def handle(self, *args, **opcoes):
        caminho = Path(opcoes["arquivo"])
        if not caminho.exists():
            raise CommandError(f"Arquivo não encontrado: {caminho}")

        aplicar = opcoes["aplicar"]
        if not aplicar:
            self.stdout.write(
                self.style.WARNING("SIMULAÇÃO — nada será gravado. Use --aplicar.\n")
            )

        linhas = self._ler(caminho)
        if not linhas:
            raise CommandError("CSV vazio ou sem coluna `email`.")

        try:
            with transaction.atomic():
                relatorio = self._importar(
                    linhas,
                    aplicar,
                    opcoes["criar_estrutura"],
                    opcoes["criar_usuarios"],
                )
                if not aplicar:
                    transaction.set_rollback(True)
        except ValidationError as erro:
            raise CommandError(f"Importação reprovada: {erro.messages[0]}") from erro

        self._relatar(relatorio, aplicar)

    # ── Leitura ─────────────────────────────────────────────────────

    def _ler(self, caminho: Path) -> list[dict]:
        with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
            leitor = csv.DictReader(arquivo)
            if not leitor.fieldnames or "email" not in leitor.fieldnames:
                return []
            return [
                {k: (v or "").strip() for k, v in linha.items() if k}
                for linha in leitor
                if (linha.get("email") or "").strip()
            ]

    def _criar_usuario(self, linha: dict):
        """Conta sem senha utilizável — autentica só por SSO.

        `nome` vai inteiro para um campo só. Antes era partido no primeiro espaço
        entre `first_name` e `last_name`, porque o `User` do Django separa em
        dois — e aquela heurística existia só para servir ao modelo, não à
        realidade: em português "Maria Clara Souza Lima" não tem um "primeiro
        nome" e um "sobrenome" úteis de separar. Com `contas.Pessoa` o problema
        deixou de existir.
        """
        Pessoa = get_user_model()
        pessoa = Pessoa(
            email=(linha["email"] or "").strip().lower(),
            nome=(linha.get("nome") or "").strip()[:160],
        )
        pessoa.set_unusable_password()
        pessoa.save()
        return pessoa

    # ── Importação ──────────────────────────────────────────────────

    def _importar(
        self,
        linhas: list[dict],
        aplicar: bool,
        criar_estrutura: bool,
        criar_usuarios: bool = False,
    ) -> dict:
        usuarios = {u.get_username(): u for u in get_user_model().objects.all()}
        rel = {
            "criadas": 0,
            "atualizadas": 0,
            "unidades": set(),
            "departamentos": set(),
            "sem_usuario": [],
            "usuarios_criados": [],
            "gestor_ausente": [],
            "situacao_invalida": [],
            "gestores_amarrados": 0,
        }

        # ── Passada 1 · lotação sem gestor ──
        for linha in linhas:
            email = linha["email"]
            user = usuarios.get(email)
            if user is None and criar_usuarios:
                user = self._criar_usuario(linha)
                usuarios[email] = user
                rel["usuarios_criados"].append(email)
            if user is None:
                rel["sem_usuario"].append(email)
                continue

            situacao = linha.get("situacao") or Situacao.ATIVO
            if situacao not in SITUACOES:
                rel["situacao_invalida"].append((email, situacao))
                situacao = Situacao.ATIVO

            unidade = self._resolver_unidade(linha, aplicar, criar_estrutura, rel)
            departamento = self._resolver_departamento(linha, aplicar, criar_estrutura, rel)

            existente = Lotacao.objects.filter(user=user).first()
            campos = {
                "matricula": linha.get("matricula", ""),
                "cargo": linha.get("cargo", ""),
                "centro_custo_codigo": linha.get("centro_custo_codigo", ""),
                "situacao": situacao,
                "unidade": unidade,
                "departamento": departamento,
            }

            if existente is None:
                rel["criadas"] += 1
                if aplicar:
                    Lotacao.objects.create(user=user, **campos)
            else:
                rel["atualizadas"] += 1
                if aplicar:
                    for campo, valor in campos.items():
                        setattr(existente, campo, valor)
                    existente.save()

        # ── Passada 2 · gestores ──
        # Separada para que a ordem das linhas não importe.
        for linha in linhas:
            gestor_email = linha.get("gestor_email", "")
            if not gestor_email:
                continue
            user = usuarios.get(linha["email"])
            gestor = usuarios.get(gestor_email)
            if user is None:
                continue
            if gestor is None:
                rel["gestor_ausente"].append((linha["email"], gestor_email))
                continue

            rel["gestores_amarrados"] += 1
            if aplicar:
                Lotacao.objects.filter(user=user).update(gestor=gestor)

        if aplicar:
            self._validar_grafo()

        return rel

    def _resolver_unidade(self, linha, aplicar, criar, rel):
        codigo = linha.get("unidade_codigo", "")
        nome = linha.get("unidade_nome", "")
        if not codigo and not nome:
            return None
        codigo = codigo or nome[:20].upper()
        rel["unidades"].add(codigo)
        if not aplicar:
            return Unidade.objects.filter(codigo=codigo).first()
        if not criar:
            return Unidade.objects.filter(codigo=codigo).first()
        unidade, _ = Unidade.objects.get_or_create(
            codigo=codigo, defaults={"nome": nome or codigo}
        )
        return unidade

    def _resolver_departamento(self, linha, aplicar, criar, rel):
        codigo = linha.get("departamento_codigo", "")
        nome = linha.get("departamento_nome", "")
        if not codigo and not nome:
            return None
        codigo = codigo or nome[:20].upper()
        rel["departamentos"].add(codigo)
        if not aplicar:
            return Departamento.objects.filter(codigo=codigo).first()
        if not criar:
            return Departamento.objects.filter(codigo=codigo).first()
        departamento, _ = Departamento.objects.get_or_create(
            codigo=codigo, defaults={"nome": nome or codigo}
        )
        return departamento

    def _validar_grafo(self) -> None:
        """Valida o organograma inteiro depois de montado.

        Ciclo detectado aqui reprova a importação toda, pela transação — melhor
        que gravar metade e deixar o grafo inconsistente.
        """
        for lotacao in Lotacao.objects.exclude(gestor=None).select_related("gestor"):
            lotacao.clean()

    # ── Relatório ───────────────────────────────────────────────────

    def _relatar(self, rel: dict, aplicar: bool) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("Lotações"))
        self.stdout.write(f"  criadas            {rel['criadas']}")
        self.stdout.write(f"  atualizadas        {rel['atualizadas']}")
        self.stdout.write(f"  gestores amarrados {rel['gestores_amarrados']}")
        if rel["usuarios_criados"]:
            self.stdout.write(
                f"  contas criadas     {len(rel['usuarios_criados'])} "
                "(sem senha — entram por SSO)"
            )

        if rel["unidades"]:
            self.stdout.write(
                f"  unidades           {len(rel['unidades'])} "
                f"({', '.join(sorted(rel['unidades'])[:6])}…)"
            )
        if rel["departamentos"]:
            self.stdout.write(
                f"  departamentos      {len(rel['departamentos'])} "
                f"({', '.join(sorted(rel['departamentos'])[:6])}…)"
            )

        for chave, titulo, dica in [
            ("sem_usuario", "E-MAIL INEXISTENTE", "Confira a grafia ou crie o usuário."),
            ("gestor_ausente", "GESTOR INEXISTENTE", "A lotação foi criada SEM gestor."),
            ("situacao_invalida", "SITUAÇÃO INVÁLIDA", f"Use uma de: {sorted(SITUACOES)}"),
        ]:
            problemas = rel[chave]
            if not problemas:
                continue
            self.stdout.write("")
            self.stdout.write(self.style.ERROR(f"  {titulo} · {len(problemas)}"))
            for item in problemas[:10]:
                self.stdout.write(f"     {item}")
            if len(problemas) > 10:
                self.stdout.write(f"     … e {len(problemas) - 10} outros")
            self.stdout.write(f"     → {dica}")

        if aplicar:
            self.stdout.write(self.style.SUCCESS("\n✓ Aplicado."))
        else:
            self.stdout.write(
                self.style.WARNING("\nNada gravado. Rode com --aplicar quando estiver certo.")
            )
