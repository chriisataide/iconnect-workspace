"""Importa o organograma de um CSV. Simulação por padrão.

    python manage.py importar_organograma organograma.csv            # simula
    python manage.py importar_organograma organograma.csv --aplicar

Colunas lidas (`username` é a única obrigatória):

    username  nome  email  matricula  cargo
    unidade_codigo  unidade_nome
    departamento_codigo  departamento_nome
    gestor_username  centro_custo_codigo  situacao

## Duas passadas, de propósito

A primeira cria as lotações **sem gestor**; a segunda amarra os gestores. Assim
a ordem das linhas no arquivo não importa — e não importar é o que se espera de
uma planilha que RH vai ordenar por departamento, não por hierarquia.

## Ciclo é rejeitado no fim, não na linha

Validar A→B na linha de A e B→A na linha de B só pega o ciclo na segunda linha,
com metade do arquivo já gravado. A validação roda ao final, sobre o grafo
inteiro, e reprova a importação toda.
"""

from __future__ import annotations

import csv
from pathlib import Path

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from identidade.models import Departamento, Lotacao, Situacao, Unidade

SITUACOES = {s.value for s in Situacao}


class Command(BaseCommand):
    help = "Importa o organograma de um CSV (username, gestor_username, unidade…)."

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
            raise CommandError("CSV vazio ou sem coluna `username`.")

        try:
            with transaction.atomic():
                relatorio = self._importar(linhas, aplicar, opcoes["criar_estrutura"])
                if not aplicar:
                    transaction.set_rollback(True)
        except ValidationError as erro:
            raise CommandError(f"Importação reprovada: {erro.messages[0]}") from erro

        self._relatar(relatorio, aplicar)

    # ── Leitura ─────────────────────────────────────────────────────

    def _ler(self, caminho: Path) -> list[dict]:
        with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
            leitor = csv.DictReader(arquivo)
            if not leitor.fieldnames or "username" not in leitor.fieldnames:
                return []
            return [
                {k: (v or "").strip() for k, v in linha.items() if k}
                for linha in leitor
                if (linha.get("username") or "").strip()
            ]

    # ── Importação ──────────────────────────────────────────────────

    def _importar(self, linhas: list[dict], aplicar: bool, criar_estrutura: bool) -> dict:
        usuarios = {u.get_username(): u for u in User.objects.all()}
        rel = {
            "criadas": 0,
            "atualizadas": 0,
            "unidades": set(),
            "departamentos": set(),
            "sem_usuario": [],
            "gestor_ausente": [],
            "situacao_invalida": [],
            "gestores_amarrados": 0,
        }

        # ── Passada 1 · lotação sem gestor ──
        for linha in linhas:
            username = linha["username"]
            user = usuarios.get(username)
            if user is None:
                rel["sem_usuario"].append(username)
                continue

            situacao = linha.get("situacao") or Situacao.ATIVO
            if situacao not in SITUACOES:
                rel["situacao_invalida"].append((username, situacao))
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
            gestor_username = linha.get("gestor_username", "")
            if not gestor_username:
                continue
            user = usuarios.get(linha["username"])
            gestor = usuarios.get(gestor_username)
            if user is None:
                continue
            if gestor is None:
                rel["gestor_ausente"].append((linha["username"], gestor_username))
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
            ("sem_usuario", "USERNAME INEXISTENTE", "Confira a grafia ou crie o usuário."),
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
