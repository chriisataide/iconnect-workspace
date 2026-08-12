"""Views do Workspace.

    home, buscar, publicacao   públicas — o Portal é a porta de entrada
    modulo                     pública — a vitrine de cada departamento
    servicos, aprovacoes       área pessoal, com @login_required

As demais entram nas ondas seguintes: `widget`, `conteudo`, `perfil`.
"""

from .aprovacoes import bandeja, decidir as decidir_aprovacao, decidir_em_lote as aprovar_em_lote
from .busca import buscar_view
from .home import home
from .modulo import modulo
from .publicacao import detalhe as publicacao_detalhe
from .servicos import (
    cancelar as cancelar_solicitacao,
    catalogo,
    minhas_solicitacoes,
    pedir,
)

__all__ = [
    "aprovar_em_lote",
    "bandeja",
    "buscar_view",
    "cancelar_solicitacao",
    "catalogo",
    "decidir_aprovacao",
    "home",
    "minhas_solicitacoes",
    "modulo",
    "pedir",
    "publicacao_detalhe",
]
