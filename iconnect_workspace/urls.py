"""Rotas do iConnect Workspace.

`/` redireciona para `/workspace/`. O prefixo permanece por dois motivos: os
templates e os testes usam `workspace:` como namespace desde a primeira onda, e
manter o prefixo deixa a URL legível quando o produto ganhar um segundo módulo
que não seja o hub.
"""

from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="workspace:home", permanent=False)),
    path("workspace/", include("workspace.urls")),
    # `entrar` e não `login`: o nome `login` era, no projeto anterior, a porta
    # do iConnect. Reaproveitá-lo aqui faria "ir para o login" significar duas
    # coisas dependendo de quem lê.
    #
    # A rota existe de novo porque sem ela NÃO HAVIA como se identificar: o
    # `/admin/login/` recusa quem não é staff, e o Workspace não tinha outra
    # porta. Exigir identidade para decidir só é possível se houver onde provar
    # quem se é. Isto não reabre o login na frente do hub — nenhum link leva
    # aqui; só se chega por um ato que precisa de assinatura.
    path(
        "entrar/",
        auth.LoginView.as_view(template_name="contas/entrar.html"),
        name="entrar",
    ),
    path("sair/", auth.LogoutView.as_view(), name="sair"),
    path("admin/", admin.site.urls),
]
