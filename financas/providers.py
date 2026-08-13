"""A implementação local do contrato de orçamento.

Espelha o que `dashboard/workspace_provider.py` fazia no projeto anterior, com a
mesma assinatura — o Workspace não sabe (nem deve saber) que a resposta mudou de
casa. Trocar a fonte do realizado mexe só neste arquivo.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Sum

from workspace.providers.orcamento import OrcamentoProvider


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
