"""Home do Workspace.

No ST-002 é uma casca: prova que a rota, o template e a autenticação funcionam.
As três zonas e os widgets chegam na Onda 3 (ST-0xx), montados sobre o runtime
de widget da Etapa 5 §5.8.
"""

from __future__ import annotations

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from workspace.providers import registry


@login_required
def home(request: HttpRequest) -> HttpResponse:
    """Renderiza a casca do Workspace."""
    return render(
        request,
        "workspace/home.html",
        {
            "titulo": "Meu Espaço",
            # Ainda não há provider registrado — a lista existe para que a
            # casca já leia do registro, e não de uma lista fixa no template.
            "providers": registry.all(),
        },
    )
