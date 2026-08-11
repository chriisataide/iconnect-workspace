"""Modelos do Workspace.

Já existe (Etapa 5 §5.2):

    comunicacao.py COM  Publicacao — alimenta Comunicados e Notícias no Portal
    aprovacao.py   APR  RegraAprovacao, SolicitacaoAprovacao, EtapaAprovacao
                        Uma bandeja para férias, reembolso e compra

Entram nas ondas seguintes:
    catalogo.py    SVC  ItemCatalogo, Solicitacao
    conteudo.py    CNT  Documento, VersaoDocumento, PendenciaLeitura
    comunicacao.py COM  + ConfirmacaoLeitura, público-alvo, classe crítica
    busca.py       SRC  SearchDocument (tsvector + acl_subjects; embedding no V1.1)
    widget.py      WKS  PreferenciaWidget, Preset
    plataforma.py  PLT  UsoApp, FeatureFlag
"""

from .aprovacao import (
    EtapaAprovacao,
    RegraAprovacao,
    SituacaoEtapa,
    SituacaoSolicitacao,
    SolicitacaoAprovacao,
    TipoAprovador,
)
from .comunicacao import Prioridade, Publicacao, TipoPublicacao

__all__ = [
    "EtapaAprovacao",
    "Prioridade",
    "Publicacao",
    "RegraAprovacao",
    "SituacaoEtapa",
    "SituacaoSolicitacao",
    "SolicitacaoAprovacao",
    "TipoAprovador",
    "TipoPublicacao",
]
