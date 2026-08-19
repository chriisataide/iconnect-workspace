"""Contrato de IA — §56. O Workspace pergunta, o provedor responde.

## Por que uma camada, e não uma chamada

O prompt pede que as funcionalidades de IA — chatbot, análise de contrato,
geração de relatório, FAQ, classificação, busca inteligente — não deixem a
aplicação dependente de um provedor específico. Trocar de fornecedor não pode
ser uma varredura por `import openai` em oito arquivos.

Segue o padrão que o projeto já usa em `providers/orcamento.py`: um contrato
abstrato, um registro por processo, e a superfície perguntando ao contrato. A
diferença é o que acontece **quando não há ninguém registrado**.

## A regra que sustenta o resto: nenhuma tela DEPENDE de IA

Sem provedor registrado, todo método devolve `None` — e cada superfície tem um
caminho determinístico que continua funcionando:

| superfície | sem IA | com IA |
|---|---|---|
| Assistente (§3) | FAQ curada por palavra-chave e prioridade | reescrita e desambiguação |
| Análise de contrato (§25) | a tela diz que não está disponível | resumo, riscos, pontos críticos |
| Busca (§57) | índice com *security trimming* | reordenação por semântica |
| Relatório (§35–36) | questionário estruturado | redação do texto corrido |

Isso não é cautela decorativa. Um assistente que só responde quando o provedor
está de pé é um assistente que falha no dia do incidente — e é justamente no dia
do incidente que as pessoas perguntam onde fica alguma coisa.

## O que o contrato NÃO faz

Não define modelo, *prompt*, temperatura nem formato de mensagem. Isso é do
provedor, e pendurar aqui amarraria o contrato ao formato de conversa de um
fornecedor — que é exatamente a dependência que ele existe para evitar.

Não guarda o texto enviado. Contrato, relatório de ocorrência e pergunta de
colaborador saem da empresa quando um provedor externo é registrado; **é decisão
de negócio e de LGPD, não de código**, e por isso o padrão do produto é não ter
provedor nenhum.
"""

from __future__ import annotations

import logging
import threading
from abc import ABC
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Analise:
    """O resultado de uma análise de documento — §25.

    Campos separados e não um texto só: a tela apresenta *Resumo executivo +
    Riscos + Pontos críticos + Recomendações*, e um bloco único obrigaria o
    template a fatiar texto do modelo por marcador — que muda sem avisar.
    """

    resumo: str = ""
    riscos: list[str] = field(default_factory=list)
    pontos_criticos: list[str] = field(default_factory=list)
    recomendacoes: list[str] = field(default_factory=list)
    #: Dados objetivos que o provedor conseguiu extrair (partes, vigência,
    #: valores, multas, reajustes). Dicionário e não campos fixos: cada tipo de
    #: documento tem o seu conjunto, e campo fixo vira coluna vazia.
    campos: dict = field(default_factory=dict)

    #: Sempre presente na tela, e é obrigação profissional e não rodapé legal:
    #: a análise é apoio e NÃO substitui parecer jurídico. A frase mora no
    #: contrato para que nenhum provedor possa omiti-la.
    RESSALVA = (
        "Esta análise é gerada automaticamente e serve como apoio à leitura. "
        "Ela não substitui a análise jurídica profissional."
    )


class ProvedorIA(ABC):
    """Quem sabe responder com modelo de linguagem.

    Todos os métodos têm implementação padrão que devolve `None` — "não sei
    responder isto". Um provedor implementa só o que oferece, como no
    `WorkspaceProvider`: obrigar os seis faria quem só faz análise de contrato
    escrever cinco `return None`.

    `None` é resposta legítima e não erro. É o que permite a superfície ter
    caminho determinístico sem perguntar se há provedor.
    """

    key: str = ""
    label: str = ""

    def responder(self, pergunta: str, contexto: str = "") -> str | None:
        """Resposta em texto para o assistente — §3."""
        return None

    def analisar_documento(self, texto: str, tipo: str = "contrato") -> Analise | None:
        """Resumo, riscos e pontos críticos de um documento — §25."""
        return None

    def redigir(self, dados: dict, tipo: str = "relatorio") -> str | None:
        """Texto corrido a partir do questionário estruturado — §35–36."""
        return None

    def classificar(self, texto: str, opcoes: list[str]) -> str | None:
        """Escolhe uma das opções. `None` quando não tem confiança."""
        return None

    def ordenar_por_semantica(self, consulta: str, itens: list[str]) -> list[int] | None:
        """Índices de `itens` reordenados por relevância — §57."""
        return None


# ── Registro ────────────────────────────────────────────────────────
#
# Um provedor por processo, e não vários com escolha por chamada. Escolher
# provedor a cada chamada espalharia a decisão pelo código e faria duas telas
# responderem com modelos diferentes sobre o mesmo assunto.

_provedor: ProvedorIA | None = None
_lock = threading.Lock()


def registrar(provedor: ProvedorIA, *, substituir: bool = False) -> ProvedorIA:
    """Registra o provedor de IA do processo. Chamado no `ready()` do app dono."""
    if not isinstance(provedor, ProvedorIA):
        raise TypeError(
            f"{provedor!r} não é um ProvedorIA. "
            "Herde de workspace.providers.ia.ProvedorIA."
        )
    if not getattr(provedor, "key", ""):
        raise ValueError(f"{type(provedor).__name__} precisa declarar `key`.")

    global _provedor
    with _lock:
        if _provedor is not None and not substituir:
            raise ValueError(
                f"Já existe provedor de IA registrado: {type(_provedor).__name__}. "
                "Use registrar(..., substituir=True) para trocar."
            )
        _provedor = provedor
    return provedor


def obter() -> ProvedorIA | None:
    return _provedor


def limpar() -> None:
    """Só para teste — devolve o processo ao estado sem IA."""
    global _provedor
    with _lock:
        _provedor = None


def disponivel() -> bool:
    """Há IA neste processo? A tela pergunta isto ANTES de oferecer o botão.

    Oferecer "Analisar com IA" e responder "indisponível" no clique é pior que
    não oferecer: a pessoa já subiu o arquivo.
    """
    return _provedor is not None


# ── A porta única ───────────────────────────────────────────────────
#
# As superfícies chamam estas funções, e não `obter()`. É o que garante que
# provedor que estoura NUNCA derruba a tela — a mesma regra 3 do
# `WorkspaceProvider`: provider que levanta exceção degrada o recurso, nunca a
# página. Sem isto, o dia em que a API do fornecedor ficar lenta seria o dia em
# que o portal inteiro fica lento.


def _seguro(metodo: str, *args, **kwargs):
    """Chama o método do provedor pelo NOME, e engole a falha.

    Pelo nome e não por `ProvedorIA.metodo(provedor, ...)`: a segunda forma
    chama a implementação da CLASSE BASE — a que devolve `None` — e nunca a
    sobrescrita do provedor. O provedor ficava registrado, `disponivel()` dizia
    que sim, e toda resposta vinha vazia.
    """
    provedor = _provedor
    if provedor is None:
        return None
    try:
        return getattr(provedor, metodo)(*args, **kwargs)
    except Exception:  # noqa: BLE001 — degradar é o comportamento desejado
        logger.warning(
            "provedor de IA %r falhou em %s", provedor.key, metodo, exc_info=True
        )
        return None


def responder(pergunta: str, contexto: str = "") -> str | None:
    return _seguro("responder", pergunta, contexto)


def analisar_documento(texto: str, tipo: str = "contrato") -> Analise | None:
    return _seguro("analisar_documento", texto, tipo)


def redigir(dados: dict, tipo: str = "relatorio") -> str | None:
    return _seguro("redigir", dados, tipo)


def classificar(texto: str, opcoes: list[str]) -> str | None:
    return _seguro("classificar", texto, opcoes)


def ordenar_por_semantica(consulta: str, itens: list[str]) -> list[int] | None:
    return _seguro("ordenar_por_semantica", consulta, itens)
