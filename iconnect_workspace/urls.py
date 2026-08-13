"""Rotas do iConnect Workspace.

`/` redireciona para `/workspace/`. O prefixo permanece por dois motivos: os
templates e os testes usam `workspace:` como namespace desde a primeira onda, e
manter o prefixo deixa a URL legível quando o produto ganhar um segundo módulo
que não seja o hub.

Não existe rota para o iConnect Platform aqui — ele é outro sistema, alcançado
pelo tile do launcher em `settings.ICONNECT_URL`.
"""

from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="workspace:home", permanent=False)),
    path("workspace/", include("workspace.urls")),
    # `entrar` e não `login`: o nome `login` era, no projeto anterior, a porta do
    # iConnect. Reaproveitá-lo aqui faria "ir para o login" significar duas
    # coisas dependendo de quem lê.
    path(
        "entrar/",
        auth.LoginView.as_view(template_name="contas/entrar.html"),
        name="entrar",
    ),
    path("sair/", auth.LogoutView.as_view(), name="sair"),
    path("admin/", admin.site.urls),
]
