"""Serviços de IDN.

A superfície pública do app é esta. Views e outros apps importam daqui:

    from identidade.services import pode, escopo_de, subjects_de
"""

from .autorizacao import (
    cadeia_de_gestores,
    escopo_de,
    liderados_recursivos,
    pode,
    situacao_de,
    subjects_de,
)

__all__ = [
    "cadeia_de_gestores",
    "escopo_de",
    "liderados_recursivos",
    "pode",
    "situacao_de",
    "subjects_de",
]
