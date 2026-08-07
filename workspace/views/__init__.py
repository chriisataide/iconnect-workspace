"""Views do Workspace.

No ST-002 existe só `home`. As demais entram nas ondas seguintes:
`widget`, `aprovacao`, `servico`, `conteudo`, `comunicado`, `busca`, `perfil`.
"""

from .home import home

__all__ = ["home"]
