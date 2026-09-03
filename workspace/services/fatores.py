"""O catálogo de fatores — o que uma meta pode apontar.

## Por que um catálogo, e não texto livre

No Portal GPS a meta traz `Fator 1` e `Fator 2` — `EBITDA RE` ÷ `EBITDA OR` — e
é isso que a torna auditável: a fórmula está na tela.

Se o fator fosse texto livre, ele seria auditável só para quem escreveu. Duas
pessoas escreveriam "EBITDA" e "Ebitda realizado" para a mesma coisa, uma
terceira escreveria "resultado" querendo dizer outra, e a comparação entre
quadros — que é a razão de existir de um ciclo de metas — pararia de funcionar
no segundo ano.

Catálogo em CÓDIGO e não em tabela, pela mesma razão do registro de regras de
exceção: cada fator é uma função que consulta o espelho. Um fator "cadastrado"
sem função atrás dele seria uma meta que nunca pode ser apurada — e o erro
apareceria no dia da nota.

## Todo fator declara a FONTE

É o que faz a meta carregar o carimbo de frescor do número que a pontua. Uma
nota calculada sobre um espelho de três dias atrás continua sendo uma nota, mas
quem lê precisa saber disso — e é a mesma disciplina da Onda 1.

## `None` NÃO é zero

Fator que o espelho não sabe responder devolve `None`, e a meta fica **não
apurada**, com o motivo. Zero seria uma afirmação de que a pessoa falhou, e a
diferença entre "não bateu" e "não deu para medir" é a diferença entre uma
conversa e uma injustiça.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Callable

from workspace.providers import frescor as frescor_contrato
from workspace.providers import orcamento as orcamento_contrato
from workspace.providers import resultados as contrato

#: A unidade muda como o número é escrito na tela — e como ele é lido.
MOEDA = "moeda"
PERCENTUAL = "percentual"
QUANTIDADE = "quantidade"
DIAS = "dias"


@dataclass(frozen=True)
class Fator:
    """Uma grandeza que uma meta pode apontar."""

    chave: str
    rotulo: str
    unidade: str
    #: A fonte, para o carimbo. `workspace` = nativo, sem carga.
    fonte: str
    #: `(escopo, competencia) -> Decimal | None`. `None` = o espelho não sabe.
    valor: Callable
    #: O que o número quer dizer, em uma frase. Vai para a tela ao lado do
    #: seletor: sem isto, "margem" e "margem de contribuição" viram a mesma
    #: escolha para quem está montando o quadro às pressas.
    descricao: str = ""

    def __str__(self) -> str:
        return self.rotulo


_fatores: dict[str, Fator] = {}
_lock = threading.Lock()


def registrar(fator: Fator) -> Fator:
    """Registra um fator. Chave duplicada é erro, como em `providers`.

    Dois fatores com a mesma chave significa que um some em silêncio — e uma
    meta apontando para o que sumiu passaria a ser apurada pela conta errada,
    sem nada na tela mudando.
    """
    if not isinstance(fator, Fator):
        raise TypeError(f"{fator!r} não é um Fator.")
    with _lock:
        existente = _fatores.get(fator.chave)
        if existente is not None and existente is not fator:
            raise ValueError(
                f"Já existe fator {fator.chave!r}: {existente.rotulo!r}."
            )
        _fatores[fator.chave] = fator
    return fator


def de(chave: str) -> Fator | None:
    with _lock:
        return _fatores.get(chave)


def todos() -> list[Fator]:
    with _lock:
        return sorted(_fatores.values(), key=lambda f: (f.fonte, f.rotulo))


def limpar() -> None:
    """Só para teste."""
    with _lock:
        _fatores.clear()


def carimbo_de(chave: str, competencia: date | None = None):
    """O carimbo de frescor da fonte deste fator.

    É o que faz a meta dizer de quando é o número que a pontua. Importado aqui
    e não no model porque carimbo é serviço, e o model não faz consulta.
    """
    from workspace.services import frescor as fr

    fator = de(chave)
    if fator is None:
        return None
    return fr.de(fator.fonte, competencia=competencia)


# ── Os fatores do espelho ───────────────────────────────────────────
#
# Só entram os que o produto SABE responder hoje. Um catálogo com fatores que
# ainda não têm dado atrás produziria quadros inteiros não apuráveis — e a
# descoberta aconteceria no fim do ciclo, quando já não dá para trocar a meta.


def _consolidado(escopo, competencia):
    provedor = contrato.obter(contrato.ProvedorResultadoFinanceiro)
    if provedor is None:
        return None
    return provedor.consolidado(escopo, competencia)


def _campo_do_consolidado(nome: str):
    def ler(escopo, competencia):
        dto = _consolidado(escopo, competencia)
        if dto is None or dto.linhas == 0:
            # Zero linhas e soma zero são a mesma aparência e coisas diferentes.
            # É o campo `linhas` do DTO existindo exatamente para isto.
            return None
        return getattr(dto, nome)

    return ler


def _quadro(escopo, competencia):
    provedor = contrato.obter(contrato.ProvedorPessoas)
    if provedor is None:
        return None
    return provedor.quadro(escopo, competencia)


def _campo_do_quadro(nome: str):
    def ler(escopo, competencia):
        dto = _quadro(escopo, competencia)
        if dto is None:
            return None
        return Decimal(str(getattr(dto, nome)))

    return ler


def _orcamento_do_escopo(escopo, competencia):
    """O teto do mês, somado sobre os centros de custo do escopo.

    Escopo global não responde: somar o orçamento da empresa inteira exigiria
    enumerar todo centro de custo, e um total que muda quando alguém cadastra um
    CC novo não é um denominador de meta.
    """
    provedor = orcamento_contrato.obter()
    if provedor is None or not escopo.centros_custo:
        return None
    total = Decimal("0")
    achou = False
    for codigo in escopo.centros_custo:
        teto = provedor.orcamento_mensal(codigo)
        if teto is not None:
            total += teto
            achou = True
    return total if achou else None


def _realizado_do_escopo(escopo, competencia):
    provedor = orcamento_contrato.obter()
    if provedor is None or not escopo.centros_custo:
        return None
    return sum(
        (provedor.realizado_no_mes(c, competencia) for c in escopo.centros_custo),
        Decimal("0"),
    )


CATALOGO: tuple[Fator, ...] = (
    # ── Do espelho financeiro ───────────────────────────────────────
    Fator(
        chave="receita_bruta",
        rotulo="Receita bruta",
        unidade=MOEDA,
        fonte="sankhya",
        valor=_campo_do_consolidado("receita_bruta"),
        descricao="A soma faturada no escopo, na competência do ciclo.",
    ),
    Fator(
        chave="margem_contribuicao",
        rotulo="Margem de contribuição",
        unidade=MOEDA,
        fonte="sankhya",
        valor=_campo_do_consolidado("margem_contribuicao"),
        descricao="Receita menos os custos diretos. Não é EBITDA.",
    ),
    Fator(
        chave="ebitda",
        rotulo="EBITDA",
        unidade=MOEDA,
        fonte="sankhya",
        valor=_campo_do_consolidado("ebitda"),
        descricao="O resultado antes de juros, impostos, depreciação e amortização.",
    ),
    # ── Do espelho de pessoas ───────────────────────────────────────
    Fator(
        chave="turnover_pct",
        rotulo="Turnover",
        unidade=PERCENTUAL,
        fonte="sankhya",
        valor=_campo_do_quadro("turnover_pct"),
        descricao="Rotatividade do quadro no mês. Menor é melhor — use cálculo inverso.",
    ),
    Fator(
        chave="absenteismo_pct",
        rotulo="Absenteísmo",
        unidade=PERCENTUAL,
        fonte="sankhya",
        valor=_campo_do_quadro("absenteismo_pct"),
        descricao="Ausências sobre o previsto. Menor é melhor — use cálculo inverso.",
    ),
    Fator(
        chave="efetivo_ativo",
        rotulo="Efetivo ativo",
        unidade=QUANTIDADE,
        fonte="sankhya",
        valor=_campo_do_quadro("efetivo_ativo"),
        descricao="Quantas pessoas o escopo tem na folha.",
    ),
    # ── Do orçamento, que é daqui ───────────────────────────────────
    Fator(
        chave="orcamento_mensal",
        rotulo="Orçamento do mês",
        unidade=MOEDA,
        fonte="workspace",
        valor=_orcamento_do_escopo,
        descricao="O teto do mês nos centros de custo do escopo. Denominador comum.",
    ),
    Fator(
        chave="realizado_no_mes",
        rotulo="Realizado no mês",
        unidade=MOEDA,
        fonte="workspace",
        valor=_realizado_do_escopo,
        descricao="O que de fato saiu. Contra o orçamento, menor é melhor.",
    ),
)


def semear() -> None:
    """Carrega o catálogo. Chamado no `ready()` do app `workspace`."""
    for fator in CATALOGO:
        registrar(fator)
