"""URLs do Workspace, montadas sob `/workspace/`."""

from django.urls import path

from . import views

app_name = "workspace"

urlpatterns = [
    path("", views.home, name="home"),
    path("buscar/", views.buscar_view, name="buscar"),
    path("ajuda/", views.ajuda, name="ajuda"),
    path("assistente/", views.perguntar, name="assistente"),
    path("faq/", views.faq, name="faq"),
    path("faq/nova/", views.faq_editar, name="faq_nova"),
    path("faq/<int:pk>/editar/", views.faq_editar, name="faq_editar"),
    path("faq/<int:pk>/excluir/", views.faq_excluir, name="faq_excluir"),
    path("publicacao/<int:pk>/", views.publicacao_detalhe, name="publicacao_detalhe"),
    path("publicacoes/", views.publicacoes, name="publicacoes"),
    path("publicacoes/nova/", views.publicacao_editar, name="publicacao_nova"),
    path("publicacoes/<int:pk>/editar/", views.publicacao_editar, name="publicacao_editar"),
    path("publicacoes/<int:pk>/acao/", views.publicacao_acao, name="publicacao_acao"),
    # Módulos — o destino dos tiles da home. Públicos como o hub.
    #
    # Prefixo `m/` e não `<slug:chave>/` na raiz: sem ele, um módulo chamado
    # "buscar" ou "servicos" sequestraria uma rota existente, e o erro só
    # apareceria no dia em que alguém acrescentasse a chave errada.
    path("m/<slug:chave>/", views.modulo, name="modulo"),
    # Documentação.
    path("documentacao/", views.documentacao, name="documentacao"),
    # A REDAÇÃO do acervo — §37. Antes dela, criar um POP exigia o `/admin/`,
    # que pede `is_staff`: publicar norma significava pedir para outra pessoa.
    #
    # Estas três rotas vêm ANTES de `documentacao/<slug:slug>/`: sem isso, um
    # documento com slug "novo" sequestraria a tela de criação, e o erro só
    # apareceria no dia em que alguém escolhesse esse título.
    path("documentacao/acervo/", views.documentos, name="documentos"),
    path("documentacao/novo/", views.documento_editar, name="documento_novo"),
    path("documentacao/<slug:slug>/editar/", views.documento_editar,
         name="documento_editar"),
    path("documentacao/<slug:slug>/revogar/", views.documento_revogar,
         name="documento_revogar"),
    path("documentacao/<slug:slug>/", views.documento, name="documento"),
    path("documentacao/<slug:slug>/baixar/", views.baixar_documento,
         name="baixar_documento"),
    path("documentacao/<slug:slug>/anexar/", views.anexar_documento,
         name="anexar_documento"),
    path("documentacao/<slug:slug>/confirmar/", views.confirmar_leitura,
         name="confirmar_leitura"),
    # Reservas.
    path("reservas/", views.reservas, name="reservas"),
    path("reservas/minhas/", views.minhas_reservas, name="minhas_reservas"),
    path("reservas/<slug:codigo>/", views.reservar, name="reservar"),
    path("reserva/<int:pk>/cancelar/", views.cancelar_reserva,
         name="cancelar_reserva"),
    # Correspondências.
    path("correspondencias/", views.correspondencias, name="correspondencias"),
    path("correspondencias/registrar/", views.registrar_correspondencia,
         name="registrar_correspondencia"),
    path("correspondencia/<int:pk>/entregar/", views.entregar_correspondencia,
         name="entregar_correspondencia"),
    path("correspondencia/<int:pk>/confirmar/", views.confirmar_correspondencia,
         name="confirmar_correspondencia"),
    path("correspondencia/<int:pk>/identificar/",
         views.identificar_correspondencia, name="identificar_correspondencia"),
    # Estoque e custódia — o que a empresa tem, e quem está com o quê.
    #
    # O modelo e o serviço de estoque existiam desde a onda de Suprimentos e não
    # havia tela: dava para GASTAR estoque pela conclusão de um pedido e não
    # dava para repor, contar nem registrar o que voltou de campo.
    path("estoque/", views.estoque, name="estoque"),
    path("estoque/movimentar/", views.registrar_movimento, name="registrar_movimento"),
    path("custodia/", views.custodia, name="custodia"),
    path("custodia/entregar/", views.entregar_custodia, name="entregar_custodia"),
    path("custodia/<int:pk>/aceitar/", views.aceitar_custodia, name="aceitar_custodia"),
    path("custodia/<int:pk>/devolver/", views.devolver_custodia,
         name="devolver_custodia"),
    # Frota — §18 e §19.
    #
    # NÃO há rota de reserva de veículo aqui, e é a decisão que mais importa
    # deste módulo: o carro de uso comum é o mesmo `Recurso` da grade de
    # Reservas. Duas portas para marcar o mesmo veículo foi como o produto
    # passou a permitir duas equipes na porta esperando a mesma van.
    path("frota/", views.frota, name="frota"),
    path("frota/novo/", views.cadastrar_veiculo, name="cadastrar_veiculo"),
    path("frota/<int:pk>/", views.atualizar_veiculo, name="atualizar_veiculo"),
    path("frota/<int:pk>/gasto/", views.lancar_despesa_veiculo,
         name="lancar_despesa_veiculo"),
    # §10 — as candidaturas a vaga interna, vistas de quem recruta.
    #
    # NÃO há model novo: a inscrição já é um pedido do catálogo (`rh.vaga`), com
    # currículo e cadeia de aprovação. O que faltava era a pergunta invertida —
    # quem se candidatou a esta vaga, e a que vagas esta pessoa já se candidatou.
    path("candidaturas/", views.candidaturas, name="candidaturas"),
    # Marketing — §23. O radar de oportunidades.
    #
    # NÃO há rota de aprovação aqui: decidir ir a uma feira é gastar dinheiro da
    # empresa, e esse caminho já existe — o item `evento` do catálogo, que passa
    # por gestor e diretoria conforme a faixa.
    path("marketing/", views.marketing, name="marketing"),
    path("marketing/nova/", views.oportunidade_registrar,
         name="oportunidade_nova"),
    path("marketing/<int:pk>/", views.oportunidade_registrar,
         name="oportunidade_editar"),
    path("marketing/<int:pk>/decidir/", views.oportunidade_decidir,
         name="oportunidade_decidir"),
    # O que o Workspace LÊ do iConnect — §20, §21, §38 e §18.
    #
    # Nenhuma das duas escreve. Abrir chamado é no iConnect, que é onde ele é
    # atendido; o Workspace direciona, exibe status e exibe histórico.
    path("chamados/", views.chamados, name="chamados"),
    path("campo/", views.campo, name="campo"),
    # Meu dia e notificações.
    path("meu-dia/", views.meu_dia, name="meu_dia"),
    path("indicadores/", views.indicadores, name="indicadores"),
    path("relatorios/", views.relatorios, name="relatorios"),
    path("relatorios/novo/", views.relatorio_editar, name="relatorio_novo"),
    path("relatorios/<int:pk>/editar/", views.relatorio_editar, name="relatorio_editar"),
    path("relatorios/<int:pk>/", views.relatorio_ver, name="relatorio_ver"),
    path("relatorios/<int:pk>/acao/", views.relatorio_acao, name="relatorio_acao"),
    path("relatorios/<int:pk>/pdf/", views.relatorio_pdf, name="relatorio_pdf"),
    path("universidade/", views.universidade, name="universidade"),
    path("universidade/painel/", views.universidade_painel, name="universidade_painel"),
    path("notificacoes/", views.notificacoes, name="notificacoes"),
    path("notificacoes/lidas/", views.marcar_lidas, name="marcar_lidas"),
    # Serviços.
    path("servicos/", views.catalogo, name="servicos"),
    path("servicos/<slug:chave>/", views.pedir, name="pedir"),
    path("minhas-solicitacoes/", views.minhas_solicitacoes, name="minhas_solicitacoes"),
    path("solicitacao/<int:pk>/cancelar/", views.cancelar_solicitacao, name="cancelar_solicitacao"),
    path("solicitacao/<int:pk>/reabrir/", views.reabrir_solicitacao, name="reabrir_solicitacao"),
    path("solicitacao/<int:pk>/comentar/", views.comentar_solicitacao,
         name="comentar_solicitacao"),
    # §43 — o rascunho. Descartar APAGA, e é a única exclusão do produto: ver
    # `catalogo.descartar_rascunho` para o motivo de a regra da casa não valer
    # para um formulário que nunca foi enviado.
    path("solicitacao/<int:pk>/descartar/", views.descartar_rascunho,
         name="descartar_rascunho"),
    # O segundo passo do reembolso que presta contas de um adiantamento: para
    # onde corre a diferença. Rota própria porque a pessoa volta a ela — a
    # conta fica aberta até ser confirmada.
    path("solicitacao/<int:pk>/acerto/", views.acerto, name="acerto"),
    # Anexos — o único caminho até o arquivo. Não há URL pública: eles moram
    # fora de MEDIA_ROOT, que o nginx serve sem autenticação.
    path("anexo/<int:pk>/", views.baixar_anexo, name="baixar_anexo"),
    # A fila de quem ATENDE — o passo que faltava depois da aprovação. Sem ela,
    # o pedido parava em "aprovado" para sempre e o prazo REAL nunca era medido.
    path("fila/", views.fila, name="fila"),
    path("fila/<int:pk>/", views.atender, name="atender"),
    # Pessoas e papéis — quem aprova o quê. Administração de produto, para o
    # R.H. não precisar do /admin/ do Django.
    path("pessoas/", views.pessoas, name="pessoas"),
    path("pessoas/conceder/", views.conceder_papel, name="conceder_papel"),
    path("papel/<int:pk>/encerrar/", views.revogar_papel, name="revogar_papel"),
    # Aprovações
    path("aprovacoes/", views.bandeja, name="aprovacoes"),
    path("aprovacoes/<int:pk>/decidir/", views.decidir_aprovacao, name="decidir_aprovacao"),
    path("aprovacoes/lote/", views.aprovar_em_lote, name="aprovar_em_lote"),
]
