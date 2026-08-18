"""Views do Workspace.

    home, buscar, publicacao   porta de entrada
    meu_dia, notificacoes      o que exige você, e o que aconteceu
    documentacao, documento    acervo normativo da empresa
    reservas                   agenda dos recursos
    correspondencias           a minha, e a fila da recepção
    modulo                     vitrine de cada departamento
    servicos, aprovacoes       pedidos e decisões

O Workspace é aberto; views que precisam de pessoa usam `workspace.acesso`.
"""

from .atendimento import atender, fila
from .pessoas import conceder_papel, pessoas, revogar_papel
from .aprovacoes import bandeja, decidir as decidir_aprovacao, decidir_em_lote as aprovar_em_lote
from .busca import buscar_view
from .conteudo import confirmar_leitura, documentacao, documento
from .correspondencia import (
    correspondencias,
    entregar_correspondencia,
    identificar_correspondencia,
    registrar_correspondencia,
)
from .home import home
from .meu_dia import marcar_lidas, meu_dia, notificacoes
from .modulo import modulo
from .reserva import (
    cancelar_reserva,
    minhas_reservas,
    reservar,
    reservas,
)
from .indicadores import indicadores
from .publicacao import detalhe as publicacao_detalhe
from .servicos import (
    acerto,
    baixar_anexo,
    cancelar as cancelar_solicitacao,
    catalogo,
    minhas_solicitacoes,
    pedir,
    reabrir as reabrir_solicitacao,
)

__all__ = [
    "acerto",
    "atender",
    "fila",
    "pessoas",
    "conceder_papel",
    "revogar_papel",
    "reservas",
    "reservar",
    "registrar_correspondencia",
    "minhas_reservas",
    "identificar_correspondencia",
    "entregar_correspondencia",
    "correspondencias",
    "cancelar_reserva",
    "aprovar_em_lote",
    "baixar_anexo",
    "bandeja",
    "buscar_view",
    "confirmar_leitura",
    "cancelar_solicitacao",
    "reabrir_solicitacao",
    "catalogo",
    "decidir_aprovacao",
    "documentacao",
    "documento",
    "home",
    "indicadores",
    "marcar_lidas",
    "meu_dia",
    "minhas_solicitacoes",
    "modulo",
    "notificacoes",
    "pedir",
    "publicacao_detalhe",
]
