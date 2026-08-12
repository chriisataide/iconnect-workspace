"""Contrato de orçamento — o Workspace pergunta, o domínio responde.

Separado do `WorkspaceProvider` de propósito. Aquele é sobre **superfície**
(widget, busca, ação rápida); este é sobre **um número específico** que só o
domínio financeiro sabe calcular. Pendurar `realizado_no_mes()` no contrato
genérico obrigaria todo provider de todo domínio a implementar um método que não
tem nada a ver com ele.

## Por que o Workspace não consulta direto

`CentroCusto` e `MovimentacaoFinanceira` moram em `dashboard`. O Workspace é
folha (Etapa 5 §5.3) e não consulta model de outro domínio — se consultasse,
mudar o cálculo de realizado exigiria mexer em dois apps, e o Workspace viraria um
segundo lugar onde o dado financeiro mora e diverge.

O `Compromisso` — aprovado e não pago — é a **única** parte que o Workspace
possui, porque nasce da aprovação, que é do Workspace.
"""

from __future__ import annotations

import threading
from abc import ABC
from datetime import date
from decimal import Decimal


class OrcamentoProvider(ABC):
    """Quem sabe responder sobre orçamento e gasto realizado."""

    key: str = ""

    def orcamento_mensal(self, centro_custo_codigo: str) -> Decimal | None:
        """Teto do mês para este centro de custo. `None` = não definido.

        `None` e `Decimal("0")` são coisas diferentes: sem orçamento definido, o
        resumo não tem denominador e a tela precisa dizer isso em vez de mostrar
        0%.
        """
        return None

    def realizado_no_mes(self, centro_custo_codigo: str, competencia: date) -> Decimal:
        """Soma do que de fato saiu no mês da competência."""
        return Decimal("0")

    def centro_custo_existe(self, centro_custo_codigo: str) -> bool:
        return False

    def __repr__(self) -> str:  # pragma: no cover - conveniência de depuração
        return f"<{type(self).__name__} key={self.key!r}>"


_provider: OrcamentoProvider | None = None
_lock = threading.Lock()


def registrar(provider: OrcamentoProvider) -> OrcamentoProvider:
    """Registra o provider de orçamento.

    Um só, não uma lista: "quanto sobrou no CC 1042" tem uma resposta. Dois
    providers respondendo produziriam dois números, e aí o Workspace não tem o que
    mostrar.
    """
    if not isinstance(provider, OrcamentoProvider):
        raise TypeError(
            f"{provider!r} não é um OrcamentoProvider. "
            "Herde de workspace.providers.orcamento.OrcamentoProvider."
        )
    if not getattr(provider, "key", ""):
        raise ValueError(f"{type(provider).__name__} precisa declarar `key`.")

    global _provider
    with _lock:
        _provider = provider
    return provider


def obter() -> OrcamentoProvider | None:
    """O provider registrado, ou None quando nenhum domínio se registrou."""
    with _lock:
        return _provider


def limpar() -> None:
    """Só para teste."""
    global _provider
    with _lock:
        _provider = None
