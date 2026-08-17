"""Contexto do rail — os contadores que aparecem em toda tela do módulo.

Context processor e não variável passada em cada view: o rail está em todas as
telas, e depender de cada view lembrar de preencher garante que uma esqueça.

Barato de propósito. Só roda em rota de `/workspace/` (ADR-009: curto-circuito
fora do Workspace).
"""

from __future__ import annotations

from django.http import HttpRequest

_ABERTAS = ["aguardando_aprovacao", "aprovada", "em_atendimento", "devolvida"]


def rail(request: HttpRequest) -> dict:
    if not request.path.startswith("/workspace/"):
        return {}

    from workspace.acesso import pessoa_da_requisicao
    from workspace.models.catalogo import SolicitacaoServico
    from workspace.services import aprovacao as apr
    from identidade.services import administracao as adm
    from workspace.services import atendimento as atd
    from workspace.services import notificacoes as nt

    pessoa = pessoa_da_requisicao(request)

    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}

    return {
        "abertas": SolicitacaoServico.objects.de(pessoa)
        .filter(situacao__in=_ABERTAS)
        .count(),
        "pendentes_aprovacao": apr.pendentes_para(
            pessoa, cache=request.perm_cache
        ).count(),
        "nao_lidas": nt.quantas_nao_lidas(pessoa),
        # `count()` numa consulta que já é filtrada por permissão: para quem
        # não atende nada dá 0, e o item do trilho nem aparece — trilho com
        # item vazio ensina o usuário a ignorar o trilho.
        "na_fila": atd.fila_de(pessoa, cache=request.perm_cache).count(),
        # Item de administração: aparece só para quem administra papéis, pela
        # mesma regra dos outros — trilho com item que não leva a nada ensina o
        # usuário a ignorar o trilho.
        "administra_papeis": adm.pode_administrar(pessoa, cache=request.perm_cache),
    }
