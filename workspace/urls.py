"""URLs do Workspace, montadas sob `/workspace/`.

Convenção da Etapa 3 §3.1.2: `workspace:<modulo>_<recurso>_<acao>`.
A home é a exceção — é o destino padrão, e `workspace:home` lê melhor.
"""

from django.urls import path

from . import views

app_name = "workspace"

urlpatterns = [
    path("", views.home, name="home"),
]
