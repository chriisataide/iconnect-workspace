"""O contrato entre a superfície do Workspace e os domínios.

Este módulo é a fronteira de PLT (Plataforma). É a *única* parte do app
`workspace` que um domínio pode importar — ver `workspace/tests/test_isolamento.py`.

Regras (Etapa 3 §3.1.1):

1. O provider é **somente leitura**. Escrita passa pelos serviços do domínio.
2. Todo método recebe `pessoa` e devolve **já filtrado por permissão**. O
   Workspace não filtra depois — filtrar na superfície vaza contagem.
3. Provider que levanta exceção degrada o *widget*, nunca a página.
4. O Workspace não consulta model de outro domínio diretamente.

Os quatro métodos têm implementação padrão vazia de propósito: um domínio
implementa só o que oferece. Se fossem todos abstratos, um domínio que só
expõe busca seria obrigado a escrever três `return []`.
"""

from __future__ import annotations

from abc import ABC
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class WidgetSpec:
    """Declaração de um widget. Campos conforme a Etapa 5 §5.8."""

    chave: str
    titulo: str
    zona: int  # 1 = briefing · 2 = ação · 3 = contexto
    permissao: str | None = None  # None = visível para todos
    ttl: int = 60  # segundos de cache
    timeout: float = 3.0  # limite de execução do provider
    template: str = ""
    dominio: str = ""  # qual geração de cache observar (ADR-004)


@dataclass(frozen=True)
class ActionSpec:
    """Ação rápida oferecida por um domínio ao ⌘K e ao widget de acesso rápido."""

    chave: str
    rotulo: str
    url_name: str
    icone: str = ""
    permissao: str | None = None
    ordem: int = 100


@dataclass(frozen=True)
class PendingItemDTO:
    """Item pendente da pessoa, agregado pelo widget `meu_dia`."""

    origem: str  # chave do provider que devolveu
    titulo: str
    url: str
    subtitulo: str = ""
    icone: str = ""
    prazo: datetime | None = None
    prioridade: int = 0  # maior = mais urgente


@dataclass(frozen=True)
class SearchDocumentDTO:
    """Documento para o índice unificado de busca (Etapa 5 §5.10).

    `acl_subjects` é o que faz o *security trimming* acontecer no `WHERE`, e
    não no pós-processamento. Devolver a lista errada aqui é vazamento de dado,
    não bug de ordenação.
    """

    origem: str
    origem_id: str
    titulo: str
    url: str
    acl_subjects: list[str]
    subtitulo: str = ""
    corpo: str = ""
    icone: str = ""
    atualizado_em: datetime | None = None
    extra: dict = field(default_factory=dict)


class WorkspaceProvider(ABC):
    """Contrato somente-leitura entre o Workspace e um domínio.

    Subclasses declaram `key` e `label` como atributos de classe; o registro
    (`workspace.providers.registry`) recusa quem não declarar.
    """

    key: str = ""
    label: str = ""

    def widgets(self, pessoa) -> list[WidgetSpec]:
        """Widgets que este domínio oferece a `pessoa`, já filtrados."""
        return []

    def quick_actions(self, pessoa) -> list[ActionSpec]:
        """Ações rápidas disponíveis para `pessoa`, já filtradas."""
        return []

    def pending_items(self, pessoa) -> list[PendingItemDTO]:
        """O que está pendente para `pessoa` neste domínio."""
        return []

    def search_documents(self, since: datetime | None = None) -> Iterator[SearchDocumentDTO]:
        """Documentos para indexação — todos se `since` for None, senão o delta.

        É o único método sem `pessoa`: a indexação roda em Celery, fora de
        requisição. O recorte por permissão acontece na consulta, via
        `acl_subjects`.
        """
        return iter(())

    def __repr__(self) -> str:  # pragma: no cover - conveniência de depuração
        return f"<{type(self).__name__} key={self.key!r}>"
