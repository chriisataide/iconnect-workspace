"""Modelos do Workspace.

Já existe (Etapa 5 §5.2):

    comunicacao.py COM  Publicacao — alimenta Comunicados e Notícias no Portal

Entram nas ondas seguintes:

    aprovacao.py   APR  EtapaAprovacao, SolicitacaoAprovacao
    catalogo.py    SVC  ItemCatalogo, Solicitacao
    conteudo.py    CNT  Documento, VersaoDocumento, PendenciaLeitura
    comunicacao.py COM  + ConfirmacaoLeitura, público-alvo, classe crítica
    busca.py       SRC  SearchDocument (tsvector + acl_subjects; embedding no V1.1)
    widget.py      WKS  PreferenciaWidget, Preset
    plataforma.py  PLT  UsoApp, FeatureFlag
"""

from .comunicacao import Prioridade, Publicacao, TipoPublicacao

__all__ = ["Prioridade", "Publicacao", "TipoPublicacao"]
