"""Views do Workspace.

    home, buscar, publicacao   porta de entrada
    meu_dia, notificacoes      o que exige você, e o que aconteceu
    documentacao, documento    acervo normativo da empresa
    reservas                   agenda dos recursos
    correspondencias           a minha, e a fila da recepção
    estoque, custodia, frota   o que a empresa tem, com quem está e o que consome
    modulo                     vitrine de cada departamento
    servicos, aprovacoes       pedidos e decisões

O Workspace é aberto; views que precisam de pessoa usam `workspace.acesso`.
"""

from .atendimento import atender, fila
from .pessoas import (
    conceder_papel,
    definir_centro_custo,
    pessoas,
    revogar_papel,
    salvar_centro_custo,
)
from .aprovacoes import bandeja, decidir as decidir_aprovacao, decidir_em_lote as aprovar_em_lote
from .busca import buscar_view
from .enderecamento import ir_para
from .excecoes import excecoes, notificar_excecao
from .resultados import fontes, recarregar_fonte, resultados, resultados_pdf
from .conteudo import (
    anexar_documento,
    baixar_documento,
    confirmar_leitura,
    documentacao,
    documento,
    documento_editar,
    documento_revogar,
    documentos,
)
from .correspondencia import (
    correspondencias,
    confirmar_correspondencia,
    entregar_correspondencia,
    identificar_correspondencia,
    registrar_correspondencia,
)
from .custodia import (
    aceitar_custodia,
    custodia,
    devolver_custodia,
    entregar_custodia,
)
from .estoque import estoque, registrar_movimento
from .frota import (
    atualizar_veiculo,
    cadastrar_veiculo,
    frota,
    lancar_despesa as lancar_despesa_veiculo,
)
from .iconnect import campo, chamados
from .home import home
from .marketing import marketing, oportunidade_decidir, oportunidade_registrar
from .recrutamento import candidaturas
from .meu_dia import marcar_lidas, meu_dia, notificacoes
from .modulo import modulo
from .reserva import (
    cancelar_reserva,
    minhas_reservas,
    reservar,
    reservas,
)
from .indicadores import indicadores
from .assistente import ajuda, perguntar
from .faq import faq, faq_editar, faq_excluir
from .relatorios import (
    relatorio_acao,
    relatorio_editar,
    relatorio_pdf,
    relatorio_ver,
    relatorios,
)
from .universidade import universidade, universidade_painel
from .publicacoes import (
    publicacao_acao,
    publicacao_editar,
    publicacoes,
)
from .publicacao import detalhe as publicacao_detalhe
from .servicos import (
    acerto,
    baixar_anexo,
    comentar_solicitacao,
    cancelar as cancelar_solicitacao,
    catalogo,
    descartar_rascunho,
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
    "definir_centro_custo",
    "salvar_centro_custo",
    "reservas",
    "reservar",
    "registrar_correspondencia",
    "minhas_reservas",
    "identificar_correspondencia",
    "entregar_correspondencia",
    "correspondencias",
    "custodia",
    "aceitar_custodia",
    "devolver_custodia",
    "entregar_custodia",
    "estoque",
    "registrar_movimento",
    "frota",
    "atualizar_veiculo",
    "cadastrar_veiculo",
    "lancar_despesa_veiculo",
    "cancelar_reserva",
    "aprovar_em_lote",
    "baixar_anexo",
    "bandeja",
    "buscar_view",
    "ir_para",
    "fontes",
    "recarregar_fonte",
    "excecoes",
    "notificar_excecao",
    "resultados",
    "resultados_pdf",
    "confirmar_leitura",
    "cancelar_solicitacao",
    "descartar_rascunho",
    "reabrir_solicitacao",
    "catalogo",
    "decidir_aprovacao",
    "documentacao",
    "documento",
    "documentos",
    "documento_editar",
    "documento_revogar",
    "campo",
    "chamados",
    "home",
    "candidaturas",
    "marketing",
    "oportunidade_decidir",
    "oportunidade_registrar",
    "indicadores",
    "marcar_lidas",
    "meu_dia",
    "minhas_solicitacoes",
    "modulo",
    "notificacoes",
    "pedir",
    "anexar_documento",
    "baixar_documento",
    "comentar_solicitacao",
    "ajuda",
    "relatorio_acao",
    "relatorio_editar",
    "relatorio_pdf",
    "relatorio_ver",
    "relatorios",
    "universidade",
    "universidade_painel",
    "faq",
    "faq_editar",
    "faq_excluir",
    "perguntar",
    "publicacao_detalhe",
    "publicacao_acao",
    "publicacao_editar",
    "publicacoes",
]
