"""Modelos do Workspace.

Vazio no ST-002. Os módulos entram nas ondas seguintes (Etapa 5 §5.2):

    aprovacao.py   APR  EtapaAprovacao, SolicitacaoAprovacao
    catalogo.py    SVC  ItemCatalogo, Solicitacao
    conteudo.py    CNT  Documento, VersaoDocumento, PendenciaLeitura
    comunicacao.py COM  Comunicado, ConfirmacaoLeitura
    busca.py       SRC  SearchDocument (tsvector + acl_subjects; embedding no V1.1)
    widget.py      WKS  PreferenciaWidget, Preset
    plataforma.py  PLT  UsoApp, FeatureFlag
"""
