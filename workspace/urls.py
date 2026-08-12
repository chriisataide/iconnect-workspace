"""URLs do Portal, montadas sob `/workspace/`.

A home é pública. Tudo sob `servicos/` e `aprovacoes/` é área pessoal —
`@login_required` mora nas views, não aqui, para que a regra fique junto do
código que a aplica.
"""

from django.urls import path

from . import views

app_name = "workspace"

urlpatterns = [
    path("", views.home, name="home"),
    path("buscar/", views.buscar_view, name="buscar"),
    path("publicacao/<int:pk>/", views.publicacao_detalhe, name="publicacao_detalhe"),
    # Serviços — área pessoal
    path("servicos/", views.catalogo, name="servicos"),
    path("servicos/<slug:chave>/", views.pedir, name="pedir"),
    path("minhas-solicitacoes/", views.minhas_solicitacoes, name="minhas_solicitacoes"),
    path("solicitacao/<int:pk>/cancelar/", views.cancelar_solicitacao, name="cancelar_solicitacao"),
    # Aprovações
    path("aprovacoes/", views.bandeja, name="aprovacoes"),
    path("aprovacoes/<int:pk>/decidir/", views.decidir_aprovacao, name="decidir_aprovacao"),
    path("aprovacoes/lote/", views.aprovar_em_lote, name="aprovar_em_lote"),
]
