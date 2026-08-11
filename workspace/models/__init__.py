"""Modelos do Workspace.

Já existe (Etapa 5 §5.2):

    comunicacao.py COM  Publicacao — alimenta Comunicados e Notícias no Portal
    aprovacao.py   APR  RegraAprovacao, SolicitacaoAprovacao, EtapaAprovacao
                        Uma bandeja para férias, reembolso e compra
    orcamento.py   FIN  Compromisso — aprovado e não pago
    catalogo.py    SVC  ItemCatalogo, SolicitacaoServico — uma fila de pedido

Entram nas ondas seguintes:
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
from .catalogo import (
    GrupoCatalogo,
    ItemCatalogo,
    SituacaoServico,
    SolicitacaoServico,
    TipoCampo,
)
from .comunicacao import Prioridade, Publicacao, TipoPublicacao
from .orcamento import Compromisso, SituacaoCompromisso, competencia_de

__all__ = [
    "Compromisso",
    "GrupoCatalogo",
    "ItemCatalogo",
    "EtapaAprovacao",
    "Prioridade",
    "Publicacao",
    "RegraAprovacao",
    "SituacaoEtapa",
    "SituacaoServico",
    "SituacaoSolicitacao",
    "SituacaoCompromisso",
    "SolicitacaoAprovacao",
    "SolicitacaoServico",
    "TipoAprovador",
    "TipoCampo",
    "TipoPublicacao",
    "competencia_de",
]
