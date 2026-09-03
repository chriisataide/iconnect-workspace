"""A implementação local do contrato de orçamento.

Espelha o que `dashboard/workspace_provider.py` fazia no projeto anterior, com a
mesma assinatura — o Workspace não sabe (nem deve saber) que a resposta mudou de
casa. Trocar a fonte do realizado mexe só neste arquivo.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Sum

from workspace.providers.orcamento import (
    CentroDeCusto,
    OrcamentoProvider,
    RevisaoDoOrcamento,
)


class OrcamentoLocal(OrcamentoProvider):
    """Responde sobre orçamento e realizado a partir dos models deste app."""

    key = "financas"

    def orcamento_mensal(self, centro_custo_codigo: str) -> Decimal | None:
        from .models import CentroCusto

        # `values_list(...).first()` e não `.get()`: centro de custo inexistente
        # é caso normal — a lotação da pessoa pode apontar para um código que
        # ninguém cadastrou ainda —, e não merece exceção.
        return (
            CentroCusto.objects.ativos()
            .filter(codigo=centro_custo_codigo)
            .values_list("orcamento_mensal", flat=True)
            .first()
        )

    # ── Orçamento anual ──────────────────────────────────────────────

    def _vigente(self, centro_custo_codigo: str, ano: int):
        from .models import OrcamentoAnual

        return (
            OrcamentoAnual.objects.vigentes()
            .filter(centro_custo__codigo=centro_custo_codigo, ano=ano)
            .prefetch_related("linhas")
            .first()
        )

    def orcamento_do_mes(
        self, centro_custo_codigo: str, competencia: date
    ) -> Decimal | None:
        """O teto daquele mês, do orçamento VIGENTE.

        Sem orçamento anual, cai no campo antigo de `CentroCusto`. O campo fica
        de propósito: arrancá-lo quebraria a bandeja de aprovação no dia do
        deploy, para todo centro de custo que ainda não tiver o ano montado.
        """
        orcamento = self._vigente(centro_custo_codigo, competencia.year)
        if orcamento is None:
            return self.orcamento_mensal(centro_custo_codigo)
        do_mes = orcamento.do_mes(competencia.month)
        # Mês sem linha cai no campo antigo pelo mesmo motivo: um orçamento
        # montado só até junho não pode fazer julho virar "sem orçamento" para
        # a bandeja, que é onde a diferença vira uma barra que some.
        return do_mes if do_mes is not None else self.orcamento_mensal(
            centro_custo_codigo
        )

    def orcamento_do_ano(self, centro_custo_codigo: str, ano: int) -> dict:
        orcamento = self._vigente(centro_custo_codigo, ano)
        if orcamento is None:
            return {}
        return {linha.mes: linha.valor for linha in orcamento.linhas.all()}

    def revisoes_do_ano(self, centro_custo_codigo: str, ano: int) -> list:
        from .models import OrcamentoAnual

        orcamento = (
            OrcamentoAnual.objects.filter(
                centro_custo__codigo=centro_custo_codigo, ano=ano
            )
            .prefetch_related("revisoes__autor")
            .first()
        )
        if orcamento is None:
            return []
        return [
            RevisaoDoOrcamento(
                numero=r.numero,
                motivo=r.motivo,
                deltas={int(m): Decimal(str(v)) for m, v in (r.deltas or {}).items()},
                autor=getattr(r.autor, "nome", "") or "",
                criada_em=r.criada_em.date(),
            )
            for r in orcamento.revisoes.all()
        ]

    def montar_orcamento(
        self, centro_custo_codigo: str, ano: int, valores: dict
    ) -> bool:
        """Escreve as linhas de um orçamento em RASCUNHO.

        Recusa em orçamento vigente. É o ADR-037 do lado do domínio: o teto
        vigente muda por revisão, e o contrato não oferece atalho.
        """
        from django.db import transaction

        from .models import CentroCusto, LinhaOrcamento, OrcamentoAnual

        centro = CentroCusto.objects.filter(codigo=centro_custo_codigo).first()
        if centro is None:
            return False

        with transaction.atomic():
            orcamento, _ = OrcamentoAnual.objects.get_or_create(
                centro_custo=centro, ano=ano
            )
            if not orcamento.editavel:
                return False
            for mes, valor in valores.items():
                mes = int(mes)
                if not 1 <= mes <= 12:
                    continue
                LinhaOrcamento.objects.update_or_create(
                    orcamento=orcamento, mes=mes,
                    defaults={"valor": Decimal(str(valor))},
                )
        return True

    def vigorar_orcamento(self, centro_custo_codigo: str, ano: int, quem) -> bool:
        from django.utils import timezone

        from .models import OrcamentoAnual, SituacaoOrcamento

        orcamento = OrcamentoAnual.objects.filter(
            centro_custo__codigo=centro_custo_codigo,
            ano=ano,
            situacao=SituacaoOrcamento.RASCUNHO,
        ).first()
        if orcamento is None or not orcamento.linhas.exists():
            # Orçamento vigente sem linha nenhuma é um teto de zero disfarçado
            # de teto ausente: a bandeja mostraria 0% de folga para o ano todo.
            return False
        orcamento.situacao = SituacaoOrcamento.VIGENTE
        orcamento.vigorou_por = quem if getattr(quem, "pk", None) else None
        orcamento.vigorou_em = timezone.now()
        orcamento.save(update_fields=["situacao", "vigorou_por", "vigorou_em"])
        return True

    def revisar_orcamento(
        self, centro_custo_codigo: str, ano: int, deltas: dict, motivo: str, quem
    ):
        """Aplica o delta ao orçamento vigente e registra a revisão.

        Delta e não valor final: é o que responde "quanto mudou?" sem
        reconstruir a série por diferença — e é essa a pergunta de uma revisão.
        """
        from django.db import transaction
        from django.db.models import Max

        from .models import LinhaOrcamento, RevisaoOrcamento

        orcamento = self._vigente(centro_custo_codigo, ano)
        if orcamento is None:
            return None

        limpos = {}
        for mes, delta in (deltas or {}).items():
            mes = int(mes)
            valor = Decimal(str(delta))
            if 1 <= mes <= 12 and valor != 0:
                limpos[mes] = valor
        if not limpos:
            return None

        with transaction.atomic():
            for mes, delta in limpos.items():
                linha, _ = LinhaOrcamento.objects.get_or_create(
                    orcamento=orcamento, mes=mes, defaults={"valor": Decimal("0")}
                )
                linha.valor = linha.valor + delta
                linha.save(update_fields=["valor"])

            ultimo = orcamento.revisoes.aggregate(n=Max("numero")).get("n") or 0
            revisao = RevisaoOrcamento.objects.create(
                orcamento=orcamento,
                numero=ultimo + 1,
                motivo=motivo[:300],
                deltas={str(m): str(v) for m, v in limpos.items()},
                autor=quem if getattr(quem, "pk", None) else None,
            )

        return RevisaoDoOrcamento(
            numero=revisao.numero,
            motivo=revisao.motivo,
            deltas=limpos,
            autor=getattr(quem, "nome", "") or "",
            criada_em=revisao.criada_em.date(),
        )

    def realizado_no_mes(self, centro_custo_codigo: str, competencia: date) -> Decimal:
        from .models import Lancamento, competencia_de

        total = (
            Lancamento.objects.do_mes(centro_custo_codigo, competencia_de(competencia))
            .aggregate(total=Sum("valor"))
            .get("total")
        )
        # `Sum` devolve None quando não há linha, e None quebra a soma da barra.
        return total or Decimal("0")

    def centro_custo_existe(self, centro_custo_codigo: str) -> bool:
        from .models import CentroCusto

        return CentroCusto.objects.ativos().filter(codigo=centro_custo_codigo).exists()

    # ── Cadastro ─────────────────────────────────────────────────────

    def centros(self) -> list[CentroDeCusto]:
        from .models import CentroCusto

        # Inativo entra na lista, no fim. Ele precisa aparecer porque alguém
        # ainda pode estar lotado nele — esconder o código faria a tela do R.H.
        # mostrar uma pessoa com centro de custo em branco quando ela tem um.
        return [
            CentroDeCusto(
                codigo=c.codigo,
                nome=c.nome,
                orcamento_mensal=c.orcamento_mensal,
                ativo=c.ativo,
            )
            for c in CentroCusto.objects.order_by("-ativo", "codigo")
        ]

    def salvar_centro(
        self,
        codigo: str,
        nome: str,
        orcamento_mensal: Decimal | None = None,
        ativo: bool = True,
    ) -> CentroDeCusto:
        from .models import CentroCusto

        # `update_or_create` pela chave que o resto do sistema usa. O código é
        # o que está gravado na lotação de cada pessoa: trocá-lo seria migração
        # de dados, então ele é a identidade e não um campo editável.
        centro, _ = CentroCusto.objects.update_or_create(
            codigo=codigo,
            defaults={"nome": nome, "orcamento_mensal": orcamento_mensal, "ativo": ativo},
        )
        return CentroDeCusto(
            codigo=centro.codigo,
            nome=centro.nome,
            orcamento_mensal=centro.orcamento_mensal,
            ativo=centro.ativo,
        )
