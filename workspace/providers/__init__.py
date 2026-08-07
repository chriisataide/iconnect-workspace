"""Contrato Workspace ↔ domínio (PLT).

Reexporta a superfície pública para que os domínios importem de um lugar só:

    from workspace.providers import WorkspaceProvider, WidgetSpec, register
"""

from . import registry
from .base import (
    ActionSpec,
    PendingItemDTO,
    SearchDocumentDTO,
    WidgetSpec,
    WorkspaceProvider,
)
from .registry import register

# `all`, `get`, `unregister` e `limpar` NÃO são reexportados de propósito:
# o contrato da Etapa 3 nomeia a função de listagem como `all()`, e trazê-la
# para o nível do pacote sombrearia o builtin `all` de quem importasse daqui.
# Use `registry.all()` — que também lê melhor no ponto de uso.
__all__ = [
    "ActionSpec",
    "PendingItemDTO",
    "SearchDocumentDTO",
    "WidgetSpec",
    "WorkspaceProvider",
    "register",
    "registry",
]
