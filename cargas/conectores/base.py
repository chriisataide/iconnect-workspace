"""O protocolo do conector, e o pouco que todos compartilham.

## Três métodos, e a razão de serem três

    coletar(janela)   -> o bruto, como veio do outro lado
    normalizar(bruto) -> Registro, no vocabulário do espelho

Separar coleta de normalização é o que torna o conector testável sem rede: a
fixture é a saída de `coletar`, e `normalizar` é função pura em cima dela. Um
método só faria todo teste precisar de um servidor falso.

## Onde foi parar `chave_externa()`

O protocolo desenhado tinha um terceiro método, `chave_externa(dto) -> str`. Ele
virou um CAMPO do `Registro`, e a razão é que um método que lê um campo que o
próprio `normalizar` acabou de preencher é um segundo lugar onde a identidade do
registro é decidida — e dois lugares divergem. A idempotência do carregador
inteiro pendura nessa chave; ela precisa nascer num lugar só.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Janela:
    """O recorte de tempo que a carga pede à fonte.

    Vazia quer dizer "tudo o que houver", e é o caso da primeira carga. Depois
    disso a janela existe para a carga não reler o histórico inteiro toda noite.
    """

    de: date | None = None
    ate: date | None = None

    @property
    def aberta(self) -> bool:
        return self.de is None and self.ate is None

    def __str__(self) -> str:
        if self.aberta:
            return "tudo"
        return f"{self.de or '…'} a {self.ate or '…'}"


@dataclass(frozen=True)
class Registro:
    """Um item normalizado, pronto para o upsert.

    `entidade` é o nome curto do model no espelho ("contrato", "competencia").
    String e não a classe: o conector não importa `resultados.models` — quem
    resolve o nome é o carregador, que é o único que conhece os dois lados.
    """

    entidade: str
    #: A identidade do registro NO SISTEMA DE ORIGEM. É a chave da idempotência:
    #: `(fonte, chave_externa)` tem constraint no banco, e reprocessar a mesma
    #: janela encontra a mesma linha em vez de criar outra.
    chave_externa: str
    dados: dict = field(default_factory=dict)
    #: Campos que este registro NÃO afirma. Usado quando uma fonte traz metade
    #: do objeto: o carregador atualiza o resto sem zerar o que a outra fonte
    #: gravou. Sem isto, duas fontes escrevendo no mesmo registro apagariam uma
    #: à outra a cada carga.
    omissos: tuple[str, ...] = ()

    def __str__(self) -> str:
        return f"{self.entidade}:{self.chave_externa}"


@runtime_checkable
class Conector(Protocol):
    """O que todo conector precisa saber fazer."""

    chave: str

    def disponivel(self) -> bool:
        """Há credencial e endereço para esta fonte neste ambiente?

        `False` não é falha: rodar sem Sankhya configurado é estado normal em
        desenvolvimento, e o comando diz isso em vez de estourar.
        """
        ...

    def coletar(self, janela: Janela) -> Iterable[dict]:
        """O bruto, como veio. Sem tradução, sem filtro, sem gravar nada."""
        ...

    def normalizar(self, bruto: Iterable[dict]) -> Iterable[Registro]:
        """O bruto no vocabulário do espelho. Função pura — não toca a rede."""
        ...


class ConectorBase:
    """Conveniências. Herdar é opcional — o protocolo é o que vale."""

    chave: str = ""

    def disponivel(self) -> bool:
        return True

    def coletar(self, janela: Janela) -> Iterable[dict]:
        return ()

    def normalizar(self, bruto: Iterable[dict]) -> Iterable[Registro]:
        return ()

    def __repr__(self) -> str:  # pragma: no cover - conveniência de depuração
        return f"<{type(self).__name__} chave={self.chave!r}>"
