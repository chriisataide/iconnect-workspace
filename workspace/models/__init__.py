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
    reserva.py     RES  Recurso, Reserva — sem choque de horário
    reembolso.py   RMB  DespesaReembolso, AcertoAdiantamento — uma linha por
                        compra, e a conta do adiantamento fechada
    evento.py      HST  EventoSolicitacao — o que aconteceu com um pedido, e quem fez
    comentario.py  WKF  ComentarioSolicitacao — a conversa dentro do pedido, sem
                        precisar devolvê-lo para perguntar
    correspondencia.py COR  Correspondencia — o que chega na recepção
    estoque.py     EST  Material, SaldoEstoque, MovimentoEstoque — o razão do
                        que a empresa tem, e o saldo por unidade
    custodia.py    EST  Custodia — quem está com o quê, e o que falta devolver
    marketing.py   MKT  Oportunidade — a feira que existe e o dia em que é
                        preciso responder; NÃO aprova nada, o catálogo aprova
    frota.py       FRT  Veiculo, DespesaVeiculo — a frota, seus prazos e o que
                        ela consome; o veículo reservável é o MESMO recurso
    faq.py         FAQ  PerguntaFrequente — a base que o assistente consulta
                        antes de encaminhar alguém para um setor

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
from .comentario import ComentarioSolicitacao
from .faq import AreaFAQ, PerguntaFrequente
from .habilitacao import Curso, Matricula, SituacaoMatricula, TipoCurso
from .relatorio import (
    EvidenciaRelatorio,
    Relatorio,
    SituacaoRelatorio,
    TipoRelatorio,
)
from .custodia import Custodia
from .marketing import Oportunidade, SituacaoOportunidade, TipoOportunidade
from .frota import (
    DespesaVeiculo,
    SituacaoVeiculo,
    TipoDespesaVeiculo,
    TipoVeiculo,
    Veiculo,
)
from .estoque import (
    CondicaoMaterial,
    Material,
    MovimentoEstoque,
    SaldoEstoque,
    TipoMovimento,
    UnidadeMedida,
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
from .correspondencia import (
    Correspondencia,
    SituacaoCorrespondencia,
    TipoCorrespondencia,
)
from .reserva import Recurso, Reserva, SituacaoReserva, TipoRecurso
from .reembolso import AcertoAdiantamento, DespesaReembolso, SentidoAcerto
from .excecao import (
    LIMITE_DE_CHAVES,
    RegraExcecao,
    ResultadoExcecao,
    Severidade,
)
from .ciclo import (
    AnotacaoEtapa,
    Cadencia,
    CicloPlanejamento,
    EtapaCiclo,
    OcorrenciaCiclo,
    SituacaoOcorrencia,
)
from .evento import AcaoSolicitacao, EventoSolicitacao
from .conteudo import (
    ConfirmacaoLeitura,
    Documento,
    SituacaoDocumento,
    TipoDocumento,
)
from .comunicacao import Prioridade, Publicacao, TipoPublicacao
from .orcamento import Compromisso, SituacaoCompromisso, competencia_de

__all__ = [
    "AnotacaoEtapa",
    "AreaFAQ",
    "Cadencia",
    "CicloPlanejamento",
    "EtapaCiclo",
    "OcorrenciaCiclo",
    "SituacaoOcorrencia",
    "ComentarioSolicitacao",
    "Curso",
    "EvidenciaRelatorio",
    "Relatorio",
    "SituacaoRelatorio",
    "TipoRelatorio",
    "Matricula",
    "SituacaoMatricula",
    "TipoCurso",
    "PerguntaFrequente",
    "CondicaoMaterial",
    "Custodia",
    "Oportunidade",
    "SituacaoOportunidade",
    "TipoOportunidade",
    "DespesaVeiculo",
    "SituacaoVeiculo",
    "TipoDespesaVeiculo",
    "TipoVeiculo",
    "Veiculo",
    "Material",
    "MovimentoEstoque",
    "SaldoEstoque",
    "TipoMovimento",
    "UnidadeMedida",
    "AcaoSolicitacao",
    "EventoSolicitacao",
    "AcertoAdiantamento",
    "DespesaReembolso",
    "SentidoAcerto",
    "TipoRecurso",
    "TipoCorrespondencia",
    "SituacaoReserva",
    "SituacaoCorrespondencia",
    "Reserva",
    "Recurso",
    "Correspondencia",
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
    "LIMITE_DE_CHAVES",
    "RegraExcecao",
    "ResultadoExcecao",
    "Severidade",
]
