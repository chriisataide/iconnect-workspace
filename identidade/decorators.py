"""Decorador de view — o encaixe entre `pode()` e o Django.

    @requer("apr.aprovar")
    def bandeja(request): ...

Deliberadamente fino. A decisão fica em `pode()`; aqui só se traduz um `False`
em resposta HTTP. Regra de negócio em decorador é regra que não se testa sem
subir o ciclo de request.
"""

from __future__ import annotations

from functools import wraps

from django.core.exceptions import PermissionDenied

from identidade.services.autorizacao import pode


def requer(permissao: str, alvo_de=None):
    """Exige `permissao` para acessar a view.

    `alvo_de` — função opcional `(request, *args, **kwargs) -> alvo`, para
    quando a permissão depende do objeto acessado (ex.: ver o perfil de outra
    pessoa). Sem ela, a checagem é "posso em geral?".

    Levanta `PermissionDenied` (403), nunca redireciona para login: usuário
    autenticado sem permissão não resolve nada fazendo login de novo.
    """

    def decorador(view):
        @wraps(view)
        def envelope(request, *args, **kwargs):
            # Reusa o cache do request se o middleware já o criou; senão cria
            # aqui, para que várias checagens na mesma requisição não repitam
            # query.
            if not hasattr(request, "perm_cache"):
                request.perm_cache = {}

            alvo = alvo_de(request, *args, **kwargs) if alvo_de else None
            if not pode(request.user, permissao, alvo=alvo, cache=request.perm_cache):
                raise PermissionDenied(f"Sem permissão: {permissao}")
            return view(request, *args, **kwargs)

        return envelope

    return decorador
