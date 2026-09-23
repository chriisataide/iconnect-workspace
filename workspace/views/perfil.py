"""A tela da própria conta.

## Por que ela existe

O menu da conta na topbar mostra nome, cargo, área e último acesso, e um menu
não é lugar para editar nada: ele fecha ao primeiro clique fora. A foto de
perfil, que passou a existir em `contas.Pessoa`, só podia ser definida pelo
admin do Django — ou seja, por quem tem `is_staff`, que é quase ninguém.

## O que se edita aqui, e o que não

**Só a foto.** Nome, cargo, área e unidade vêm do diretório corporativo — nome e
e-mail do SSO (`entra_oid` é a chave de reconciliação), cargo, área e unidade de
`identidade.Lotacao`. Deixar a pessoa digitar o próprio cargo aqui criaria uma
segunda verdade sobre quem faz o quê, e é a lotação que a bandeja de aprovação
consulta para decidir quem aprova o quê. Quem corrige isso é o R.H., na origem.

Por isso a tela mostra esses campos e diz de onde vêm, em vez de escondê-los: a
pergunta "por que meu cargo está errado?" precisa ter resposta na própria tela,
senão vira chamado.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _

#: Teto do arquivo de foto. 2 MiB é folgado para um retrato e barra o upload de
#: um PNG de câmera inteiro, que chegaria a dezenas de MiB e ficaria no disco
#: para sempre — `ImageField` não redimensiona nada sozinho.
LIMITE_AVATAR = 2 * 1024 * 1024

#: Formatos que o navegador exibe sem plugin e que o Pillow abre sem extra.
TIPOS_AVATAR = ("image/png", "image/jpeg", "image/webp")


@login_required
def perfil(request: HttpRequest) -> HttpResponse:
    pessoa = request.user

    if request.method == "POST":
        if request.POST.get("acao") == "remover":
            if pessoa.avatar:
                # `delete(save=False)` + `save()` numa transação implícita: o
                # primeiro tira o arquivo do disco, o segundo limpa a coluna.
                pessoa.avatar.delete(save=False)
                pessoa.avatar = ""
                pessoa.save(update_fields=["avatar"])
                messages.success(request, _("Foto removida."))
            return redirect(reverse("workspace:perfil"))

        arquivo = request.FILES.get("avatar")
        if not arquivo:
            messages.error(request, _("Escolha um arquivo de imagem."))
        elif arquivo.size > LIMITE_AVATAR:
            messages.error(
                request,
                _("A imagem tem %(tem)s MB e o limite é 2 MB.")
                % {"tem": f"{arquivo.size / 1024 / 1024:.1f}".replace(".", ",")},
            )
        elif arquivo.content_type not in TIPOS_AVATAR:
            # `content_type` vem do cliente e não é garantia; quem valida de
            # verdade é o `ImageField`, que abre o arquivo com o Pillow ao
            # salvar. Esta checagem existe para a mensagem de erro ser legível
            # em vez de um ValidationError cru sobre imagem inválida.
            messages.error(request, _("Use um arquivo PNG, JPEG ou WebP."))
        else:
            pessoa.avatar = arquivo
            pessoa.save(update_fields=["avatar"])
            messages.success(request, _("Foto atualizada."))
        return redirect(reverse("workspace:perfil"))

    # Sem contexto próprio: `eu` — nome, cargo, área, unidade, avatar e o
    # percentual — já chega em toda tela pelo processador `workspace.context.rail`.
    return render(request, "workspace/perfil.html", {})
