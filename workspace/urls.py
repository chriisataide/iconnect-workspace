"""URLs do Portal, montadas sob `/workspace/`.

Convenção da Etapa 3 §3.1.2: `workspace:<modulo>_<recurso>_<acao>`.
`home` e `buscar` são exceções — são a casca, não um módulo.
"""

from django.urls import path

from . import views

app_name = "workspace"

urlpatterns = [
    path("", views.home, name="home"),
    path("buscar/", views.buscar_view, name="buscar"),
    path("publicacao/<int:pk>/", views.publicacao_detalhe, name="publicacao_detalhe"),
]
