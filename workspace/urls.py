"""URLs do Workspace, montadas sob `/workspace/`."""

from django.urls import path

from . import views

app_name = "workspace"

urlpatterns = [
    path("", views.home, name="home"),
    path("buscar/", views.buscar_view, name="buscar"),
    path("publicacao/<int:pk>/", views.publicacao_detalhe, name="publicacao_detalhe"),
    # Módulos — o destino dos tiles da home. Públicos como o hub.
    #
    # Prefixo `m/` e não `<slug:chave>/` na raiz: sem ele, um módulo chamado
    # "buscar" ou "servicos" sequestraria uma rota existente, e o erro só
    # apareceria no dia em que alguém acrescentasse a chave errada.
    path("m/<slug:chave>/", views.modulo, name="modulo"),
    # Documentação.
    path("documentacao/", views.documentacao, name="documentacao"),
    path("documentacao/<slug:slug>/", views.documento, name="documento"),
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
    path("correspondencia/<int:pk>/identificar/",
         views.identificar_correspondencia, name="identificar_correspondencia"),
    # Meu dia e notificações.
    path("meu-dia/", views.meu_dia, name="meu_dia"),
    path("indicadores/", views.indicadores, name="indicadores"),
    path("notificacoes/", views.notificacoes, name="notificacoes"),
    path("notificacoes/lidas/", views.marcar_lidas, name="marcar_lidas"),
    # Serviços.
    path("servicos/", views.catalogo, name="servicos"),
    path("servicos/<slug:chave>/", views.pedir, name="pedir"),
    path("minhas-solicitacoes/", views.minhas_solicitacoes, name="minhas_solicitacoes"),
    path("solicitacao/<int:pk>/cancelar/", views.cancelar_solicitacao, name="cancelar_solicitacao"),
    path("solicitacao/<int:pk>/reabrir/", views.reabrir_solicitacao, name="reabrir_solicitacao"),
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
