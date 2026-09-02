"""Onde os conectores se anunciam.

Registro em memória e não tabela: conector é código, não configuração. Uma
tabela permitiria "ativar" um conector que ninguém escreveu, e o erro apareceria
às três da manhã, no cron.
"""

from __future__ import annotations

import threading

_conectores: dict[str, object] = {}
_lock = threading.Lock()


def registrar(conector, *, substituir: bool = False):
    """Registra um conector pela sua chave. Colisão é erro, como em `providers`."""
    chave = getattr(conector, "chave", "")
    if not chave:
        raise ValueError(f"{type(conector).__name__} precisa declarar `chave`.")
    with _lock:
        if chave in _conectores and not substituir:
            raise ValueError(
                f"Já existe conector para {chave!r}: "
                f"{type(_conectores[chave]).__name__}."
            )
        _conectores[chave] = conector
    return conector


def conector_de(chave: str):
    """O conector desta fonte, ou None."""
    with _lock:
        return _conectores.get(chave)


def todos() -> dict[str, object]:
    with _lock:
        return dict(_conectores)


def limpar() -> None:
    """Só para teste."""
    with _lock:
        _conectores.clear()
