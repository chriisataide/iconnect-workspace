"""Os módulos do Workspace — o que cada tile da home abre.

## O erro que este arquivo corrige

A home tinha dez tiles e nove deles não levavam a lugar nenhum. Ao mesmo tempo,
a única área real do Workspace (o catálogo de serviços) não tinha porta na home:
existia só se você digitasse a URL. Mapa sem destino de um lado, destino sem
porta do outro.

## O que é um módulo

Um módulo **não é um sistema novo**. É uma vista por departamento sobre o que já
existe: a fatia do catálogo que aquele departamento atende (`dominios`), mais os
pedidos da pessoa dentro dessa fatia.

Isso mantém a regra de ouro do SVC intacta. A navegação por **intenção**
(`/workspace/servicos/`) continua sendo o caminho principal, porque ela cobre
100% do catálogo; o mapa por departamento não cobre — hoje `jur.analise` não tem
tile nenhum. Departamento é onde a pessoa vai quando já sabe com quem quer
falar; intenção é onde ela vai quando só sabe do problema.

## Sem `dominios` = "em breve", honestamente

Um módulo que não atende nenhum domínio do catálogo não tem o que mostrar, e o
tile continua marcado "em breve" em vez de abrir uma página vazia. Isso é
decidido aqui, sem tocar o banco, porque o launcher é montado no `ready()`.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Modulo:
    """Um departamento do Workspace, com a fatia do catálogo que ele atende."""

    chave: str
    nome: str
    descricao: str
    icone: str
    # Prefixos de `ItemCatalogo.dominio`. Prefixo e não valor exato porque o
    # domínio é hierárquico: `rh.ferias`, `rh.ausencia` e `rh.documento` são
    # todos do RH, e listar um a um garante que o próximo item nasça órfão.
    dominios: tuple[str, ...] = field(default_factory=tuple)
    # Uma frase sobre o que o módulo faz além do catálogo. Aparece na página e
    # é onde fica registrado o que ainda NÃO existe.
    ordem: int = 100

    @property
    def tem_catalogo(self) -> bool:
        return bool(self.dominios)


MODULOS: tuple[Modulo, ...] = (
    Modulo(
        chave="rh",
        nome="RH",
        descricao="Holerite, férias, benefícios",
        icone="users",
        dominios=("rh.",),
        ordem=30,
    ),
    Modulo(
        chave="financeiro",
        nome="Financeiro",
        descricao="Reembolsos, notas, aprovações",
        icone="wallet",
        dominios=("fin.",),
        ordem=40,
    ),
    Modulo(
        chave="operacoes",
        nome="Operações",
        descricao="Ordens de serviço, escala, SLA",
        icone="activity",
        dominios=("ops.",),
        ordem=50,
    ),
    Modulo(
        chave="logistica",
        nome="Logística",
        descricao="Estoque, remessas e materiais",
        icone="truck",
        dominios=("log.",),
        ordem=60,
    ),
    Modulo(
        chave="redes",
        nome="Redes",
        descricao="Links, VPN e conectividade",
        icone="globe",
        # `ti.acesso` e não um domínio `rede.*` próprio: quem pede VPN pede
        # acesso, e inventar um domínio novo deixaria os itens que já existem
        # órfãos de tile.
        dominios=("ti.acesso",),
        ordem=70,
    ),
    Modulo(
        chave="compras",
        nome="Compras",
        descricao="Requisições e fornecedores",
        icone="cart",
        dominios=("com.",),
        ordem=80,
    ),
    Modulo(
        chave="universidade",
        nome="Universidade",
        descricao="Trilhas, cursos e certificações",
        icone="book",
        dominios=("hab.",),
        ordem=90,
    ),
    Modulo(
        chave="documentacao",
        nome="Documentação",
        descricao="POP, políticas, normas e manuais",
        icone="file",
        # Sem domínio de catálogo: documentação não é coisa que se "pede". O
        # tile fica "em breve" até existir o repositório de conteúdo (CNT).
        ordem=100,
    ),
)

_POR_CHAVE = {m.chave: m for m in MODULOS}


def modulo_por_chave(chave: str) -> Modulo | None:
    return _POR_CHAVE.get(chave)
