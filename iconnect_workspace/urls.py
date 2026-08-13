"""Rotas do iConnect Workspace.

`/` redireciona para `/workspace/`. O prefixo permanece por dois motivos: os
templates e os testes usam `workspace:` como namespace desde a primeira onda, e
manter o prefixo deixa a URL legível quando o produto ganhar um segundo módulo
que não seja o hub.
"""

from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="workspace:home", permanent=False)),
    path("workspace/", include("workspace.urls")),
    path("admin/", admin.site.urls),
]
