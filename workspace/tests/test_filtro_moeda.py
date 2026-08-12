"""O filtro de moeda.

`R$ 13720,00` exige contar dígitos. Coluna de dinheiro sem separador de milhar é
o sinal mais rápido de que o produto não é sério.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from workspace.templatetags.wks import moeda


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        (Decimal("12400"), "12.400,00"),
        (Decimal("840.5"), "840,50"),
        (Decimal("1234567.89"), "1.234.567,89"),
        (Decimal("0"), "0,00"),
        (0, "0,00"),
        (None, "—"),
        ("", "—"),
        ("abc", "—"),
    ],
)
def test_moeda(entrada, esperado):
    assert moeda(entrada) == esperado
