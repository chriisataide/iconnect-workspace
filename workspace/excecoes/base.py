"""O protocolo de uma regra de exceção, e o registro delas.

## Uma regra é código; se ela está LIGADA é dado

`RegraExcecao` no banco guarda `ativa`, `ordem`, `severidade` e `janela`. A
lógica mora aqui, num registro em memória.

Se a lógica fosse dado, daria para "ativar" pelo `/admin/` uma regra que ninguém
escreveu — e o erro apareceria às três da manhã, no cron. Se a configuração
fosse código, mudar a severidade exigiria deploy, e severidade é decisão de quem
opera, tomada no dia.

## `disponivel()` é o que separa "zero" de "não avaliada"

Regra cuja fonte não está no ar **não vale zero**. Zero é tranquilidade; não
avaliada é uma fonte para ligar. Somar as duas faria uma fonte caída parecer um
mês sem problema — que é o pior resultado possível num painel de exceções.

## A exceção nasce endereçada

Cada `Ocorrencia` traz o **responsável**: o papel que responde por ela e, quando
há uma pessoa só, o nome. É o que o benchmark faz ao pôr o e-mail do gestor em
cada linha da grade — sem isso, a lista vira um relatório que alguém precisa
distribuir à mão.

**Mas nunca o e-mail, e nunca o documento.** Nome e papel bastam para saber com
quem falar, e a grade é vista por quem tem o papel da regra — não por quem tem
o direito de ver dado pessoal de terceiro.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Ocorrencia:
    """Uma linha da grade — um registro que violou a regra."""

    #: A identidade do registro, para a avaliação seguinte saber o que é NOVO.
    #: `lotacao:41`, `contrato:CT-100`. Nunca identifica pessoa: o histórico é
    #: consultado sem passar por permissão nenhuma.
    chave: str
    titulo: str
    detalhe: str = ""
    #: Para onde ir para resolver. Vazio quando não há tela — e aí a grade
    #: mostra a linha sem link, em vez de um link que não leva a nada.
    url: str = ""
    #: Quem responde. NOME e papel; nunca e-mail, nunca documento.
    responsavel: str = ""
    papel: str = ""
    #: Desde quando. É o que separa "apareceu hoje" de "está aí há três meses".
    desde: date | None = None


@runtime_checkable
class Regra(Protocol):
    """O que toda regra sabe fazer."""

    chave: str

    def disponivel(self) -> bool:
        """A fonte desta regra está no ar neste ambiente?

        `False` faz a regra aparecer como **não avaliada**, e não como zero.
        """
        ...

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        """Os registros que violaram a regra. `janela` em dias, 0 = sem janela."""
        ...


class RegraBase:
    """Conveniências. Herdar é opcional — o protocolo é o que vale."""

    chave: str = ""
    #: A fonte de que a regra depende. Vazio = dado do próprio Workspace, que
    #: está sempre disponível.
    fonte: str = ""

    def disponivel(self) -> bool:
        return True

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        return []

    def __repr__(self) -> str:  # pragma: no cover - conveniência de depuração
        return f"<{type(self).__name__} chave={self.chave!r}>"


_regras: dict[str, Regra] = {}
_lock = threading.Lock()


def registrar(regra, *, substituir: bool = False):
    """Registra uma regra. Chave duplicada é erro, como em `providers`.

    Duas regras com a mesma chave significa que uma some em silêncio — e a que
    some é sempre a que alguém acabou de escrever.
    """
    chave = getattr(regra, "chave", "")
    if not chave:
        raise ValueError(f"{type(regra).__name__} precisa declarar `chave`.")
    with _lock:
        if chave in _regras and not substituir:
            raise ValueError(
                f"Já existe regra {chave!r}: {type(_regras[chave]).__name__}."
            )
        _regras[chave] = regra
    return regra


def regra_de(chave: str):
    with _lock:
        return _regras.get(chave)


def todas() -> dict[str, Regra]:
    with _lock:
        return dict(_regras)


def limpar() -> None:
    """Só para teste."""
    with _lock:
        _regras.clear()


# ── Responsáveis ────────────────────────────────────────────────────


def titulares(chave_do_papel: str) -> list:
    """Quem ocupa o papel hoje. Lista vazia quando ninguém ocupa.

    Papel sem dono é um achado por si só — e é a razão de a lista vazia não ser
    tratada como erro aqui: a regra 2 existe justamente para mostrá-la.
    """
    if not chave_do_papel:
        return []
    from django.contrib.auth import get_user_model
    from identidade.models import AtribuicaoPapel

    ids = (
        AtribuicaoPapel.objects.vigentes()
        .filter(papel__chave=chave_do_papel, papel__ativo=True)
        .values_list("user_id", flat=True)
    )
    return list(get_user_model().objects.filter(pk__in=ids, is_active=True))


def quem_responde(chave_do_papel: str) -> str:
    """O nome de quem responde, ou o que dizer quando não há ninguém.

    Uma pessoa: o nome. Várias: o nome da primeira e quantas mais. Nenhuma:
    **"ninguém"**, escrito assim — e não um espaço em branco. Exceção sem dono é
    exceção que ninguém resolve, e a tela precisa dizer isso em vez de deixar a
    coluna vazia e parecer um defeito de renderização.
    """
    pessoas = titulares(chave_do_papel)
    if not pessoas:
        return "ninguém"
    primeiro = pessoas[0].get_full_name() or pessoas[0].get_short_name()
    if len(pessoas) == 1:
        return primeiro
    return f"{primeiro} e mais {len(pessoas) - 1}"
