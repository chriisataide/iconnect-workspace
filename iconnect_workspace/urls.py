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

from contas.entrada import LoginComFreio, LoginDoAdminComFreio
from iconnect_workspace.saude import saude

urlpatterns = [
    # A sonda do balanceador. Fora de `/workspace/` de propósito: ela pergunta
    # sobre o PROCESSO, não sobre o produto — e o dia em que o hub deixar de
    # responder é justamente o dia em que a resposta importa.
    path("saude/", saude, name="saude"),
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
    # Com freio de tentativas: um formulário de senha sem limite, contra contas
    # reais, é o alvo mais óbvio que um produto interno oferece. Ver
    # `contas/entrada.py` para as duas contagens e por que não há uma terceira.
    path("entrar/", LoginComFreio.as_view(), name="entrar"),
    path("sair/", auth.LogoutView.as_view(), name="sair"),
    # O `/admin/login/` com o MESMO freio de `/entrar/` — auditoria de agosto.
    #
    # Ele aceitava vinte senhas erradas seguidas, todas com HTTP 200, enquanto a
    # porta do produto barrava na sexta. O produto tinha uma tranca e uma
    # fechadura solta, e a solta é a que abre o banco inteiro sem passar por
    # regra, histórico nem permissão de negócio.
    #
    # ANTES de `admin.site.urls`, e é o que faz funcionar: a resolução é por
    # ordem, o nome `admin:login` continua sendo o do Django, e continua
    # apontando para esta mesma URL — que agora é a nossa view.
    path("admin/login/", LoginDoAdminComFreio.as_view(), name="admin_login"),
    path("admin/", admin.site.urls),
]
