"""Contexto do rail — os contadores que aparecem em toda tela do módulo.

Context processor e não variável passada em cada view: o rail está em todas as
telas, e depender de cada view lembrar de preencher garante que uma esqueça.

Barato de propósito. Só roda em rota de `/workspace/` (ADR-009: curto-circuito
fora do Workspace).

## Onde a conta mora

Aqui não. O cálculo é de `workspace.services.painel`, que é a fonte única desde
o §50: o trilho e os cards da home leem os MESMOS números, e leem uma vez só por
requisição.

Antes eram dois lugares. A home não tem trilho — é a única tela do produto sem
ele —, então tudo o que o Workspace já sabia sobre a pessoa ficava invisível
exatamente na tela em que ela cai ao entrar. Dar os contadores à home
recalculando-os teria dobrado oito consultas por carregamento da tela mais
visitada do produto.

## Estes contadores são PESSOAIS, e por isso não usam a pessoa de referência

O Workspace é aberto, e `pessoa_da_requisicao()` devolve uma conta real do
organograma para o visitante anônimo — as telas do hub precisam de alguém para
calcular ALCANCE: quais tiles aparecem, quais itens do catálogo, quais
documentos.

Alcance é uma coisa. Contador pessoal é outra: "4 não lidas", "7 esperando sua
aprovação", "você administra papéis". Usando a pessoa de referência, o visitante
anônimo via os números DELA — no banco de demonstração, os do superusuário,
incluindo o item "Pessoas e papéis" no trilho.

Nada disso era exploração: era a tela contando, a quem passasse pelo endereço,
quantas notificações uma pessoa específica tinha para ler.
"""

from __future__ import annotations

from django.http import HttpRequest

#: Reexportado porque um teste de regressão e o `_shell.html` falam deste
#: número. Ver `painel.LIMITE_DO_SINO` para o porquê de cinco.
from workspace.services.painel import LIMITE_DO_SINO  # noqa: F401


def assistente(request: HttpRequest) -> dict:
    """As sugestões do painel do bot. Vale em TODA tela do portal.

    Fora do `rail()` de propósito: o trilho é de quem entrou e sai cedo para
    anônimo, e o assistente é aberto — pôr as duas coisas na mesma função faria
    o bot nascer mudo justamente para quem mais precisa dele, que é quem ainda
    não sabe onde ficam as coisas.
    """
    if not request.path.startswith("/workspace/"):
        return {}

    from workspace.services import assistente as asst

    return {"sugestoes_bot": asst.sugestoes_iniciais()}


def rail(request: HttpRequest) -> dict:
    if not request.path.startswith("/workspace/"):
        return {}

    from workspace.services import painel

    # Memoizado na requisição: quando a view já pediu os contadores — é o caso
    # da home —, aqui não custa consulta nenhuma.
    return painel.contadores(request)
