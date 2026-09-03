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
from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class CentroDeCusto:
    """O que o Workspace precisa saber de um centro de custo, e nada mais.

    Dataclass e não o model de `financas`: devolver o model faria a tela do
    R.H. depender do schema do app financeiro, que é exatamente o acoplamento
    que este contrato existe para impedir. `orcamento_mensal` continua podendo
    ser `None` — sem orçamento definido é diferente de zero, e a bandeja
    depende dessa diferença.
    """

    codigo: str
    nome: str
    orcamento_mensal: Decimal | None = None
    ativo: bool = True

    def __str__(self) -> str:
        return f"{self.codigo} · {self.nome}"


@dataclass(frozen=True)
class RevisaoDoOrcamento:
    """Uma revisão, como a tela a mostra. Dataclass e não o model de `financas`.

    O `delta` é o que mudou por mês, e não o valor final: "quanto mudou?" é a
    pergunta que se faz numa revisão orçamentária, e o final obrigaria a
    reconstruir a série por diferença.
    """

    numero: int
    motivo: str
    deltas: dict
    autor: str = ""
    criada_em: date | None = None

    @property
    def total(self) -> Decimal:
        return sum((Decimal(str(v)) for v in self.deltas.values()), Decimal("0"))


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

    def orcamento_do_mes(
        self, centro_custo_codigo: str, competencia: date
    ) -> Decimal | None:
        """O teto DAQUELE mês. `None` = não definido.

        Existe porque orçamento anual tem doze números, e `orcamento_mensal()`
        tem um só: sem competência, dezembro e janeiro teriam o mesmo teto — e
        dezembro nunca tem.

        A implementação padrão cai em `orcamento_mensal()`, e é de propósito:
        um domínio que ainda não faz orçamento anual continua respondendo o que
        sabe, e nada no Workspace precisa saber qual dos dois respondeu.
        """
        return self.orcamento_mensal(centro_custo_codigo)

    def orcamento_do_ano(self, centro_custo_codigo: str, ano: int) -> dict:
        """`{mes: valor}` do orçamento VIGENTE do ano. Vazio quando não há.

        Um dicionário e não uma lista de doze: mês sem linha é diferente de mês
        com teto zero, e uma lista obrigaria a inventar um valor para o buraco.
        """
        return {}

    def revisoes_do_ano(self, centro_custo_codigo: str, ano: int) -> list:
        """O histórico de revisões, para a tela mostrar o que mudou e por quê."""
        return []

    def realizado_no_mes(self, centro_custo_codigo: str, competencia: date) -> Decimal:
        """Soma do que de fato saiu no mês da competência."""
        return Decimal("0")

    def centro_custo_existe(self, centro_custo_codigo: str) -> bool:
        return False

    # ── Cadastro ─────────────────────────────────────────────────────
    #
    # Ler e ESCREVER pelo mesmo contrato. O R.H. lota alguém num centro de
    # custo que ainda não existe, o pedido dessa pessoa cai numa bandeja que
    # não sabe calcular impacto, e o aprovador vê "CC sem orçamento definido" —
    # sem nenhuma tela no produto onde resolver isso. A única porta era o
    # `/admin/`, que pede `is_staff`.
    #
    # A escrita continua sendo do domínio financeiro: o Workspace descreve o
    # que quer e não conhece o model. É a mesma fronteira da leitura, na outra
    # direção — e é por isso que ela mora aqui, e não num `import financas`
    # dentro de uma view.

    def centros(self) -> list["CentroDeCusto"]:
        """Todos os centros de custo, ativos primeiro. Lista vazia por padrão."""
        return []

    def salvar_centro(
        self,
        codigo: str,
        nome: str,
        orcamento_mensal: Decimal | None = None,
        ativo: bool = True,
    ) -> "CentroDeCusto | None":
        """Cria ou atualiza um centro de custo. `None` quando o domínio não
        aceita escrita — e aí a tela diz isso em vez de fingir que gravou."""
        return None

    # ── Orçamento anual ──────────────────────────────────────────────
    #
    # A escrita do orçamento vigente NÃO passa por aqui, e é a decisão da onda:
    # o teto vigente só muda por REVISÃO, e a revisão exige motivo e autor. Um
    # `salvar_orcamento(codigo, ano, valores)` genérico seria a porta por onde a
    # exigência se perde — bastaria alguém chamá-lo. Ver ADR-037.

    def montar_orcamento(
        self, centro_custo_codigo: str, ano: int, valores: dict
    ) -> bool:
        """Escreve as doze linhas de um orçamento em RASCUNHO. `False` se não dá."""
        return False

    def vigorar_orcamento(self, centro_custo_codigo: str, ano: int, quem) -> bool:
        """Rascunho → vigente. `False` quando não há rascunho para pôr em vigor."""
        return False

    def revisar_orcamento(
        self, centro_custo_codigo: str, ano: int, deltas: dict, motivo: str, quem
    ) -> "RevisaoDoOrcamento | None":
        """Aplica um delta por mês ao orçamento vigente, com motivo e autor.

        `None` quando o domínio não faz orçamento anual — e aí a tela diz isso,
        em vez de deixar a pessoa achar que revisou.
        """
        return None

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
