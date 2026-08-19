"""O endpoint que responde "posso mandar tráfego para este processo?".

## Por que existe

Sem ele, o balanceador e o orquestrador só sabem que o processo *subiu* — e
processo que subiu com o banco inacessível continua aceitando requisição e
devolvendo 500 para todo mundo. A diferença entre "vivo" e "pronto" é
exatamente essa, e ela só existe se alguém a medir.

## O que ele checa, e por que só isso

Uma consulta trivial ao banco. É a única dependência externa do Workspace:
não há cache compartilhado, fila, nem serviço de terceiro no caminho de uma
requisição. Checar mais coisas do que existe produz o pior tipo de health
check — o que fica vermelho por algo que não derruba o produto, e é desligado
na primeira madrugada.

## O que ele NÃO responde

Versão, host, número de migrações pendentes, nome do banco. O endpoint é
anônimo por necessidade — sonda de balanceador não faz login —, e tudo o que
ele imprime é público. `{"status": "ok"}` é o suficiente para decidir roteamento
e não diz nada a quem não deveria estar perguntando.

## Duas armadilhas de operação

**`ALLOWED_HOSTS`.** A sonda do orquestrador chega pelo IP do contêiner, não
pelo domínio. Django recusa Host desconhecido com 400 **antes** de qualquer
view rodar — inclusive esta. Se a sonda voltar 400 e não 200, o problema não
está aqui: o IP do pod precisa entrar em `ALLOWED_HOSTS`.

**Cache.** A resposta vai com `no-store`. Health check cacheado por um proxy
responde "ok" durante toda a indisponibilidade, que é o único momento em que
ele importa.
"""

from __future__ import annotations

import json

from django.db import DatabaseError, connections
from django.http import HttpRequest, HttpResponse


def _banco_responde() -> bool:
    """`SELECT 1`. Não usa `connection.ensure_connection()` de propósito.

    Aquele devolve verdadeiro para uma conexão que existe mas está morta —
    banco reiniciado do outro lado, socket ainda aberto deste. O que responde a
    pergunta é uma ida e volta de verdade.
    """
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except DatabaseError:
        return False
    return True


def saude(request: HttpRequest) -> HttpResponse:
    """200 quando dá para atender, 503 quando não dá.

    503 e não 200 com corpo dizendo "erro": o balanceador lê o código, não o
    JSON. Um health check que devolve 200 para tudo é um health check que não
    tira do ar o processo quebrado — que é a sua única função.
    """
    ok = _banco_responde()
    corpo = json.dumps(
        {"status": "ok" if ok else "indisponivel", "banco": "ok" if ok else "erro"}
    )
    resposta = HttpResponse(
        corpo, content_type="application/json", status=200 if ok else 503
    )
    # `no-store` e não `no-cache`: o segundo permite guardar e revalidar, e o
    # proxy que revalida com o processo caído devolve a cópia velha — "ok"
    # durante toda a indisponibilidade.
    resposta["Cache-Control"] = "no-store"
    return resposta
