"""Fixtures do espelho."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from resultados.models import CompetenciaResultado, Contrato, Fonte


@pytest.fixture
def contrato(db):
    def _criar(codigo="C-100", **campos):
        return Contrato.objects.create(
            fonte=campos.pop("fonte", Fonte.PLATFORM),
            chave_externa=campos.pop("chave_externa", f"ext-{codigo}"),
            codigo=codigo,
            nome_cliente=campos.pop("nome_cliente", "Cliente Fictício"),
            servico=campos.pop("servico", "cftv"),
            centro_custo=campos.pop("centro_custo", "1042"),
            regional=campos.pop("regional", "Sudeste"),
            **campos,
        )

    return _criar


@pytest.fixture
def competencia(db):
    def _criar(contrato=None, ano=2026, mes=1, receita="100000", **campos):
        return CompetenciaResultado.objects.create(
            fonte=campos.pop("fonte", Fonte.SANKHYA),
            # A chave inclui o CONTRATO: sem ele, duas linhas de meses iguais
            # em contratos diferentes colidiriam na constraint de origem — que
            # foi exatamente o que aconteceu ao escrever estes testes.
            chave_externa=campos.pop(
                "chave_externa",
                f"k-{contrato.codigo if contrato else campos.get('centro_custo', 'cc')}-{ano}-{mes}",
            ),
            contrato=contrato,
            centro_custo=campos.pop("centro_custo", contrato.centro_custo if contrato else "1042"),
            ano=ano,
            mes=mes,
            receita_bruta=Decimal(receita),
            **campos,
        )

    return _criar
