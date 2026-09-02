"""Contrato de frescor — de quando é este número.

## Por que isto nasce vazio

Nenhum domínio implementa este contrato hoje, e é de propósito. O Workspace é
dono do que ele mesmo mede, e dado próprio é lido no instante em que a tela
abre: não existe carga, não existe atraso, não existe o que carimbar além de
"agora". O carimbo que interessa é o do que vem **de fora** — e o que vem de
fora ainda não vem.

O contrato existe antes do primeiro conector porque a alternativa é pior. Sem
ele, a primeira tela com número de fora leria a hora no template, o carimbo
diria "atualizado agora" para um dado do Sankhya de ontem, e a correção
depois passaria por cada template já escrito. Um bloco que mente a idade é pior
do que um bloco sem carimbo: o segundo faz perguntar, o primeiro faz confiar.

## Por que separado do `WorkspaceProvider`

Mesma razão de `orcamento.py`: aquele contrato é sobre **superfície** — widget,
busca, ação rápida. Este é sobre **uma pergunta específica** que só quem carrega
o dado sabe responder. Pendurar `carimbo()` no contrato genérico obrigaria todo
provider de todo domínio a implementar um método que não tem a ver com ele.

## O que o implementador precisa garantir

1. `carregado_em` é o instante da última carga **bem-sucedida**. Carga que
   falhou não avança o relógio — se avançasse, uma fonte quebrada há três dias
   pareceria fresca.
2. `status` descreve a última TENTATIVA. Uma fonte pode ter `carregado_em` de
   seis horas atrás e `status="falha"` ao mesmo tempo: é exatamente o caso que
   a tela precisa mostrar, com o dado bom e o aviso junto.
3. Fonte indisponível devolve o carimbo com `status="falha"` e `motivo`, nunca
   `None`. `None` quer dizer "não sei nada sobre esta fonte", que é outra coisa.
"""

from __future__ import annotations

import threading
from abc import ABC
from dataclasses import dataclass
from datetime import datetime, timedelta

#: A "fonte" do que o Workspace mede sozinho. Não passa por conector nenhum, e
#: por isso não tem carga: o número é lido quando a tela abre.
NATIVO = "workspace"

SUCESSO = "sucesso"
PARCIAL = "parcial"
FALHA = "falha"


@dataclass(frozen=True)
class CarimboDTO:
    """O que se sabe sobre a última carga de uma fonte."""

    fonte: str
    rotulo: str
    #: A janela do dado, na língua de quem lê: "competência AGO/2026",
    #: "em tempo real", "D-1". Vazio quando a fonte não tem janela declarada.
    janela: str = ""
    carregado_em: datetime | None = None
    status: str = SUCESSO
    #: Acima disto o carimbo vira alerta. Declarado pela FONTE e não pela tela:
    #: seis horas é velho para o monday e é novo para a folha do Sankhya.
    idade_maxima: timedelta | None = None
    #: Por que a última tentativa falhou. Nunca contém credencial nem URL com
    #: token — o carimbo aparece em tela aberta.
    motivo: str = ""


class ProvedorFrescor(ABC):
    """Quem sabe quando cada fonte foi carregada pela última vez."""

    key: str = ""

    def carimbo(self, fonte: str, competencia=None) -> CarimboDTO | None:
        """O carimbo desta fonte, ou `None` quando ela é desconhecida."""
        return None

    def __repr__(self) -> str:  # pragma: no cover - conveniência de depuração
        return f"<{type(self).__name__} key={self.key!r}>"


_provider: ProvedorFrescor | None = None
_lock = threading.Lock()


def registrar(provider: ProvedorFrescor) -> ProvedorFrescor:
    """Registra o provedor de frescor. Um só, como o de orçamento.

    "Quando o Sankhya carregou pela última vez" tem uma resposta. Dois
    provedores respondendo produziriam dois carimbos, e aí a tela não tem o que
    mostrar — que é o problema que este contrato existe para evitar.
    """
    if not isinstance(provider, ProvedorFrescor):
        raise TypeError(
            f"{provider!r} não é um ProvedorFrescor. "
            "Herde de workspace.providers.frescor.ProvedorFrescor."
        )
    if not getattr(provider, "key", ""):
        raise ValueError(f"{type(provider).__name__} precisa declarar `key`.")

    global _provider
    with _lock:
        _provider = provider
    return provider


def obter() -> ProvedorFrescor | None:
    """O provedor registrado, ou None enquanto nenhum domínio se registrou."""
    with _lock:
        return _provider


def limpar() -> None:
    """Só para teste."""
    global _provider
    with _lock:
        _provider = None
