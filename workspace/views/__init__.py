"""Views do Workspace.

As demais entram nas ondas seguintes: `widget`, `aprovacao`, `servico`,
`conteudo`, `perfil`.
"""

from .busca import buscar_view
from .home import home
from .publicacao import detalhe as publicacao_detalhe

__all__ = ["buscar_view", "home", "publicacao_detalhe"]
