"""Contexto do rail — os contadores que aparecem em toda tela do módulo.

Context processor e não variável passada em cada view: o rail está em todas as
telas, e depender de cada view lembrar de preencher garante que uma esqueça.

Barato de propósito. Só roda para usuário autenticado em rota de `/workspace/`
(ADR-009: curto-circuito fora do Workspace) — a home pública não paga nada por
isto, e é a tela mais acessada.
"""

from __future__ import annotations

from django.http import HttpRequest

_ABERTAS = ["aguardando_aprovacao", "aprovada", "em_atendimento", "devolvida"]


def rail(request: HttpRequest) -> dict:
    if not request.path.startswith("/workspace/"):
        return {}
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return {}

    from workspace.models.catalogo import SolicitacaoServico
    from workspace.services import aprovacao as apr
    from workspace.services import notificacoes as nt

    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}

    return {
        "abertas": SolicitacaoServico.objects.de(request.user)
        .filter(situacao__in=_ABERTAS)
        .count(),
        "pendentes_aprovacao": apr.pendentes_para(
            request.user, cache=request.perm_cache
        ).count(),
        # O sino está na casca, então o número tem de vir daqui. É um `COUNT`
        # sobre índice parcial (`wks_notif_sino_idx`), não uma listagem.
        "nao_lidas": nt.quantas_nao_lidas(request.user),
    }
