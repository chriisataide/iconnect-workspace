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


@dataclass(frozen=True)
class FonteDTO:
    """Uma fonte, como a tela 99 a mostra."""

    chave: str
    nome: str
    ativa: bool = True
    cadencia: str = ""
    idade_maxima: timedelta | None = None
    responsavel: str = ""
    observacao: str = ""
    #: `False` quando falta credencial NESTE ambiente. Diferente de `ativa`:
    #: desativada é decisão de quem opera; não configurada é estado do deploy, e
    #: a tela precisa dizer coisas diferentes.
    configurada: bool = True


@dataclass(frozen=True)
class ExecucaoDTO:
    """Uma rodada de carga, para o histórico da tela 99."""

    fonte: str
    iniciada_em: datetime | None = None
    terminada_em: datetime | None = None
    status: str = SUCESSO
    lidos: int = 0
    criados: int = 0
    atualizados: int = 0
    #: Chegou e não mudou nada. É o número que prova a idempotência ao operador
    #: que rodou a carga duas vezes por precaução.
    ignorados: int = 0
    rejeitados: int = 0
    erro_resumo: str = ""
    simulacao: bool = False


@dataclass(frozen=True)
class DivergenciaDTO:
    """Duas fontes discordaram, com os dois valores lado a lado.

    Os DOIS, e não só o vencedor: a tela existe para alguém ir descobrir por que
    os sistemas discordam, e para isso é preciso ver o que cada um disse.
    """

    entidade: str
    chave: str
    campo: str
    fonte_a: str
    valor_a: str
    fonte_b: str
    valor_b: str
    vencedora: str = ""
    detectada_em: datetime | None = None
    resolvida: bool = False


class ProvedorFrescor(ABC):
    """Quem sabe quando cada fonte foi carregada pela última vez.

    ## O contrato cresceu na Onda 3, e de forma compatível

    Ele nasceu com um método só — `carimbo()` —, que é o que a tela precisava
    quando o carimbo era a única coisa que existia. A tela de fontes pede mais:
    o histórico, as contagens e as divergências abertas.

    Os métodos novos têm implementação padrão vazia, então quem implementava
    só `carimbo()` continua válido — e a tela 99 diz "esta fonte não reporta
    histórico" em vez de quebrar.
    """

    key: str = ""

    def carimbo(self, fonte: str, competencia=None) -> CarimboDTO | None:
        """O carimbo desta fonte, ou `None` quando ela é desconhecida."""
        return None

    def fontes(self) -> list["FonteDTO"]:
        """Todas as fontes cadastradas, para a tela 99."""
        return []

    def historico(self, fonte: str = "", limite: int = 10) -> list["ExecucaoDTO"]:
        """As últimas execuções, mais recente primeiro. Sem `fonte`, de todas."""
        return []

    def divergencias(self, *, abertas: bool = True) -> list["DivergenciaDTO"]:
        """Os conflitos entre fontes. Abertas por padrão — resolvidas viram
        histórico, não some do banco."""
        return []

    def recarregar(self, fonte: str, quem=None) -> bool:
        """Dispara uma carga sob demanda. `False` quando não é possível.

        ## Um contrato de LEITURA com um método que escreve

        É a mesma exceção — e a mesma justificativa — de
        `orcamento.salvar_centro`. A alternativa seria a view importar `cargas`
        para disparar a carga, e aí o Workspace passaria a conhecer o app de
        ingestão só por causa de um botão.

        O que atravessa aqui é uma ORDEM, não um dado: a view diz "recarregue
        esta fonte" e o domínio decide se pode, como e quando. A fronteira é a
        mesma da leitura, na outra direção.
        """
        return False

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
