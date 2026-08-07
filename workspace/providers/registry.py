"""Registro dos providers de domínio.

Cada domínio registra o seu no `ready()` do próprio `AppConfig`. O Workspace
não importa app de domínio — a direção da dependência é sempre
`domínio → contrato`, nunca `superfície → domínio` (Etapa 5 §5.3: WKS é folha).

    # fsm/apps.py
    def ready(self):
        from workspace.providers.registry import register
        from .workspace_provider import FsmProvider
        register(FsmProvider())

O registro é validado na hora: chave duplicada ou provider sem `key`/`label`
levanta erro na subida do processo, não em produção às 3h da manhã.
"""

from __future__ import annotations

import threading

from .base import WorkspaceProvider

_providers: dict[str, WorkspaceProvider] = {}
_lock = threading.Lock()


def register(provider: WorkspaceProvider, *, substituir: bool = False) -> WorkspaceProvider:
    """Registra um provider. Devolve o próprio, para encadear.

    `substituir=True` existe para teste e para o raro caso de um domínio
    especializar o provider de outro. Fora isso, colisão de chave é erro:
    dois providers com a mesma chave significam que um deles some em silêncio.
    """
    if not isinstance(provider, WorkspaceProvider):
        raise TypeError(
            f"{provider!r} não é um WorkspaceProvider. "
            "Herde de workspace.providers.base.WorkspaceProvider."
        )
    chave = getattr(provider, "key", "")
    if not chave or not isinstance(chave, str):
        raise ValueError(f"{type(provider).__name__} precisa declarar `key` (str não vazia).")
    if not getattr(provider, "label", ""):
        raise ValueError(f"{type(provider).__name__} precisa declarar `label`.")

    with _lock:
        existente = _providers.get(chave)
        if existente is not None and not substituir:
            raise ValueError(
                f"Já existe provider com a chave {chave!r}: {type(existente).__name__}. "
                "Use uma chave distinta ou register(..., substituir=True)."
            )
        _providers[chave] = provider
    return provider


def all() -> list[WorkspaceProvider]:  # noqa: A001 - nome definido pelo contrato da Etapa 3
    """Todos os providers registrados, em ordem estável de chave."""
    with _lock:
        return [_providers[k] for k in sorted(_providers)]


def get(chave: str) -> WorkspaceProvider | None:
    """O provider da chave, ou None."""
    with _lock:
        return _providers.get(chave)


def unregister(chave: str) -> bool:
    """Remove um provider. Devolve se havia algo para remover."""
    with _lock:
        return _providers.pop(chave, None) is not None


def limpar() -> None:
    """Esvazia o registro. Só para teste."""
    with _lock:
        _providers.clear()
