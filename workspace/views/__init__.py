"""Views do Workspace.

    home, buscar, publicacao   públicas — o Workspace é a porta de entrada
    meu_dia, notificacoes      área pessoal — o que exige você, e o que aconteceu
    documentacao, documento    públicas — o acervo normativo da empresa
    modulo                     pública — a vitrine de cada departamento
    servicos, aprovacoes       área pessoal, com @login_required

As demais entram nas ondas seguintes: `widget`, `conteudo`, `perfil`.
"""

from .aprovacoes import bandeja, decidir as decidir_aprovacao, decidir_em_lote as aprovar_em_lote
from .busca import buscar_view
from .conteudo import confirmar_leitura, documentacao, documento
from .home import home
from .meu_dia import marcar_lidas, meu_dia, notificacoes
from .modulo import modulo
from .publicacao import detalhe as publicacao_detalhe
from .servicos import (
    baixar_anexo,
    cancelar as cancelar_solicitacao,
    catalogo,
    minhas_solicitacoes,
    pedir,
)

__all__ = [
    "aprovar_em_lote",
    "baixar_anexo",
    "bandeja",
    "buscar_view",
    "confirmar_leitura",
    "cancelar_solicitacao",
    "catalogo",
    "decidir_aprovacao",
    "documentacao",
    "documento",
    "home",
    "marcar_lidas",
    "meu_dia",
    "minhas_solicitacoes",
    "modulo",
    "notificacoes",
    "pedir",
    "publicacao_detalhe",
]
