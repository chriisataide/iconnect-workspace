"""As telas que LEEM o iConnect — §20, §21, §38 e §18.

Nenhuma delas escreve. Abrir chamado é no iConnect, que é onde ele é atendido; o
§38 pede exatamente isso, e o Workspace faz o que sobra e ninguém fazia:
direcionar, exibir status e exibir histórico.

Todas degradam. Sem `ICONNECT_API_URL`, sem token na sessão, ou com o outro lado
fora do ar, a tela **diz o que houve em português** e continua desenhada — o
§53 pede isso, e é o que separa uma integração de uma dependência.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from workspace.integracoes import cliente, iconnect as ic, sessao


def _cache(request: HttpRequest) -> dict:
    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    return request.perm_cache


def _ler(funcao, request, *args, **kwargs) -> tuple[list, str]:
    """`(dados, aviso)`. Nunca levanta — a tela sempre desenha.

    O aviso é a mensagem em português; vazio quando deu certo. Uma tupla e não
    uma exceção capturada em cada view porque são quatro leituras com o mesmo
    tratamento, e repetir `try/except` quatro vezes é como uma delas fica sem.
    """
    try:
        return list(funcao(request, *args, **kwargs)), ""
    except cliente.IntegracaoIndisponivel as erro:
        return [], str(erro)
    except cliente.IntegracaoError as erro:
        return [], str(erro)


@login_required
def chamados(request: HttpRequest) -> HttpResponse:
    """Os chamados desta pessoa no iConnect — §21 e §38.

    A tabela que o §21 pede: número, assunto, categoria, status, responsável,
    abertura, última atualização. O botão de abrir chamado leva **para fora** —
    o Workspace não recria a abertura.
    """
    lista, aviso = _ler(ic.chamados_de, request)

    return render(
        request,
        "workspace/chamados.html",
        {
            "chamados": lista,
            "aviso": aviso,
            "conectado": sessao.conectado(request),
            "configurado": cliente.disponivel(),
            "iconnect_url": settings.ICONNECT_URL,
            "abertos": len([c for c in lista if c["aberto"]]),
        },
    )


@login_required
def campo(request: HttpRequest) -> HttpResponse:
    """Onde a equipe está, e o que ela vai atender — §18.

    **Nada aqui é coletado pelo Workspace.** O GPS vem do app do técnico, que
    alimenta o FSM do iConnect; a otimização de rota e a auditoria de
    quilometragem também são de lá. Esta tela lê e mostra.

    Exige quem opera a frota: a posição de uma pessoa em tempo real é dado
    sensível sobre ela, não informação institucional.
    """
    from workspace.services import frota as frt

    if not frt.pode_ler(request.user, cache=_cache(request)):
        raise PermissionDenied("Esta tela é de quem opera a frota.")

    posicoes, aviso_posicoes = _ler(ic.posicoes_dos_tecnicos, request)
    ordens, aviso_ordens = _ler(ic.ordens_do_dia, request)
    rotas, aviso_rotas = _ler(ic.rotas_auditadas, request)

    return render(
        request,
        "workspace/campo.html",
        {
            "posicoes": posicoes,
            "ordens": ordens,
            "rotas": rotas,
            # Um aviso só: os três vêm do mesmo lado, e três mensagens iguais
            # empilhadas fazem a tela parecer mais quebrada do que está.
            "aviso": aviso_posicoes or aviso_ordens or aviso_rotas,
            "conectado": sessao.conectado(request),
            "configurado": cliente.disponivel(),
            "iconnect_url": settings.ICONNECT_URL,
        },
    )
