"""Os públicos da marca — e por que só um deles entra aqui.

## O que o benchmark descreve

No site do GPS, o menu **"Extranet"** tem quatro destinos: *GPS 360 – Cliente*,
*GPS 360 – Fornecedor*, *Gerenciador Eletrônico* e *Portal GPS*. A anotação
equivalente para a ADB é um botão com **"ADB Cliente"**, **"ADB Fornecedor"** e
o portal do colaborador — três públicos, três produtos, uma marca. O nome do
terceiro sai de `settings.PRODUTO_NOME`: ele é este produto, e o nome dele não
pode ser escrito num segundo lugar.

## A decisão: este produto é o Portal ADB, e os outros dois não entram aqui

Não é preferência de escopo. O modelo de permissão inteiro assume que `Pessoa` é
**colaborador com `Lotacao` no organograma**: `escopo_de()` recorta por unidade,
departamento, centro de custo e gestor; `pode()` resolve `.equipe` percorrendo
`Lotacao.gestor`.

Cliente e fornecedor não têm nada disso. Deixá-los entrar exigiria um segundo
modelo de identidade — ou, pior, pessoas no organograma que não são funcionários,
que é literalmente o defeito das **881 lotações órfãs** que este repositório
cita desde a primeira etapa. Ver ADR-038.

## Destino não configurado NÃO aparece — e não aparece como "em breve"

`AppSpec` sem rota vira um tile *"em breve"*, e está certo para um módulo do
roadmap: alguém decidiu que ele vai existir.

Para o ADB Cliente, está errado. "Em breve" é uma **promessa**, e ninguém decidiu
que esse produto vai existir. ADR-012 já proíbe módulo "em breve" para preencher
taxonomia; aqui é o mesmo princípio aplicado a público. Vazio quer dizer
**ausente**. Ver ADR-039.

## O guard que vale mais que o resto deste módulo

**URL de público externo tem de ser absoluta e apontar para FORA deste host.**

Um `ADB_CLIENTE_URL=/workspace/` mal configurado mandaria clientes para dentro do
portal do funcionário — e a tela de entrar diria a eles que aquele é o lugar
certo. O registro recusa na subida do processo, que é onde um erro de
configuração ainda é barato.

É a mesma verificação que `cargas/conectores/platform.py` faz ao recusar um
`next` que aponta para fora, com o sinal trocado.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from urllib.parse import urlparse

from django.conf import settings

#: A chave do público deste produto. Existe como constante e não como string
#: solta porque três arquivos precisam da mesma resposta para "quem é o dono
#: desta porta".
INTERNO = "colaborador"


class PublicoInvalido(ValueError):
    """A configuração de um público não pode ser aceita, e a mensagem diz por quê."""


@dataclass(frozen=True)
class Publico:
    """Um público da marca, e onde ele entra."""

    chave: str
    nome: str
    descricao: str
    #: Absoluta e fora deste host, para os externos. Vazia para o interno — este
    #: produto não linka para si mesmo numa lista de "onde entrar".
    url: str = ""
    interno: bool = False

    @property
    def disponivel(self) -> bool:
        """O interno sempre; o externo só quando tem endereço configurado.

        É aqui que "vazio = ausente" vira comportamento. Um externo indisponível
        não é um tile apagado nem um "em breve": ele não existe na lista.
        """
        return self.interno or bool(self.url)

    def __str__(self) -> str:
        return self.nome


_publicos: dict[str, Publico] = {}
_lock = threading.Lock()


def _e_externo_de_verdade(url: str) -> bool:
    """A URL sai deste produto?

    Exige esquema e host. Um caminho relativo — `/workspace/` — não sai de lugar
    nenhum, e é o erro de configuração que este módulo existe para pegar.
    """
    partes = urlparse(url)
    return partes.scheme in ("http", "https") and bool(partes.netloc)


def _aponta_para_dentro(url: str) -> bool:
    """A URL aponta para um host que este produto atende?

    `ALLOWED_HOSTS` é a lista do que somos. Um público externo apontando para um
    deles manda cliente para o portal do funcionário — e a tela de entrar
    confirmaria a ele que é o lugar certo.

    `*` em `ALLOWED_HOSTS` é de desenvolvimento e não casa com nada aqui: ele
    diria que TODO endereço é interno, e nenhum público externo poderia ser
    configurado numa máquina de desenvolvimento.
    """
    host = (urlparse(url).hostname or "").lower()
    if not host:
        return False
    nossos = {
        h.lower().lstrip(".")
        for h in getattr(settings, "ALLOWED_HOSTS", [])
        if h and h != "*"
    }
    return host in nossos


def registrar(publico: Publico) -> Publico:
    """Registra um público. Recusa configuração que mandaria gente para o lugar
    errado — e recusa na subida do processo, não na hora do clique."""
    if not isinstance(publico, Publico):
        raise TypeError(f"{publico!r} não é um Publico.")
    if not publico.chave:
        raise PublicoInvalido("Público precisa de `chave`.")

    if publico.interno and publico.url:
        # O interno é este produto. Uma URL aqui criaria um link do produto para
        # si mesmo numa lista cujo propósito é dizer "sua entrada é outra".
        raise PublicoInvalido(
            f"{publico.chave!r} é o público deste produto e não tem URL própria."
        )

    if publico.url:
        if not _e_externo_de_verdade(publico.url):
            raise PublicoInvalido(
                f"{publico.chave!r}: {publico.url!r} não é um endereço absoluto. "
                "Público externo precisa de http(s) e host — um caminho relativo "
                "manda gente para dentro deste produto."
            )
        if _aponta_para_dentro(publico.url):
            raise PublicoInvalido(
                f"{publico.chave!r}: {publico.url!r} aponta para este próprio "
                "produto. Cliente e fornecedor não entram no portal do "
                "colaborador — ver ADR-038."
            )

    with _lock:
        _publicos[publico.chave] = publico
    return publico


def todos() -> list[Publico]:
    """Todos os registrados, inclusive os sem endereço. Para teste e diagnóstico."""
    with _lock:
        return sorted(_publicos.values(), key=lambda p: (not p.interno, p.nome))


def disponiveis() -> list[Publico]:
    """Os que a tela mostra. Sem endereço, o externo simplesmente não está aqui."""
    return [p for p in todos() if p.disponivel]


def externos() -> list[Publico]:
    """Os OUTROS públicos, configurados. É o que a tela de entrar oferece.

    Vazio é o estado normal enquanto os outros produtos não existirem — e uma
    lista vazia não vira uma seção vazia: a tela não desenha nada.
    """
    return [p for p in disponiveis() if not p.interno]


def de(chave: str) -> Publico | None:
    with _lock:
        return _publicos.get(chave)


def limpar() -> None:
    """Só para teste."""
    with _lock:
        _publicos.clear()


def semear() -> None:
    """Carrega os três públicos. Chamado no `ready()` do app `workspace`.

    Os externos leem a configuração do ambiente. Vazio é o padrão, e é o estado
    de hoje: nem o ADB Cliente nem o ADB Fornecedor existem, e o produto não
    promete que vão existir.
    """
    registrar(
        Publico(
            chave=INTERNO,
            # O nome vem do settings porque o público interno É este produto —
            # escrevê-lo aqui seria o segundo lugar onde o nome mora, e o
            # segundo é sempre o que fica para trás num rebatismo. Já quase
            # aconteceu: em 04/09/2026 este literal era "Portal ADB", o produto
            # virou "Portal ADB360", e um teste que procurava a substring passou
            # a reprovar por causa da colisão.
            nome=settings.PRODUTO_NOME,
            descricao="Este produto. A vida corporativa de quem trabalha aqui.",
            interno=True,
        )
    )
    registrar(
        Publico(
            chave="cliente",
            nome="ADB Cliente",
            descricao="Contratos, medições e ocorrências do seu contrato.",
            url=getattr(settings, "ADB_CLIENTE_URL", "") or "",
        )
    )
    registrar(
        Publico(
            chave="fornecedor",
            nome="ADB Fornecedor",
            descricao="Pedidos, notas e pagamentos de quem fornece para a ADB.",
            url=getattr(settings, "ADB_FORNECEDOR_URL", "") or "",
        )
    )
