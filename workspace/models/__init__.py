"""Modelos do Workspace.

Já existe (Etapa 5 §5.2):

    comunicacao.py COM  Publicacao — alimenta Comunicados e Notícias no Workspace
    aprovacao.py   APR  RegraAprovacao, SolicitacaoAprovacao, EtapaAprovacao
                        Uma bandeja para férias, reembolso e compra
    orcamento.py   FIN  Compromisso — aprovado e não pago
    catalogo.py    SVC  ItemCatalogo, SolicitacaoServico — uma fila de pedido
    anexo.py       SVC  Anexo — arquivo em armazenamento privado, fora de MEDIA
    notificacao.py WKS  Notificacao — aviso com UM destinatário, nunca fan-out
    conteudo.py    CNT  Documento, ConfirmacaoLeitura — acervo normativo
    busca.py       SRC  EntradaIndice, SujeitoIndice — índice com ACL no WHERE

Entram nas ondas seguintes:
    conteudo.py    CNT  Documento, VersaoDocumento, PendenciaLeitura
    comunicacao.py COM  + ConfirmacaoLeitura, público-alvo, classe crítica
    busca.py       SRC  SearchDocument (tsvector + acl_subjects; embedding no V1.1)
    widget.py      WKS  PreferenciaWidget, Preset
    plataforma.py  PLT  UsoApp, FeatureFlag
"""

from .anexo import Anexo
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
from .notificacao import Notificacao, TipoNotificacao
from .busca import EntradaIndice, OrigemIndice, SujeitoIndice
from .conteudo import (
    ConfirmacaoLeitura,
    Documento,
    SituacaoDocumento,
    TipoDocumento,
)
from .comunicacao import Prioridade, Publicacao, TipoPublicacao
from .orcamento import Compromisso, SituacaoCompromisso, competencia_de

__all__ = [
    "Anexo",
    "ConfirmacaoLeitura",
    "Compromisso",
    "Documento",
    "EntradaIndice",
    "Notificacao",
    "OrigemIndice",
    "GrupoCatalogo",
    "ItemCatalogo",
    "EtapaAprovacao",
    "Prioridade",
    "Publicacao",
    "RegraAprovacao",
    "SituacaoEtapa",
    "SituacaoDocumento",
    "SituacaoServico",
    "SituacaoSolicitacao",
    "SituacaoCompromisso",
    "SolicitacaoAprovacao",
    "SolicitacaoServico",
    "SujeitoIndice",
    "TipoAprovador",
    "TipoCampo",
    "TipoDocumento",
    "TipoNotificacao",
    "TipoPublicacao",
    "competencia_de",
]
