"""`@requer()` — o encaixe entre `pode()` e o Django."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse

from identidade.decorators import requer
from identidade.tests import fabricas as f


@requer("rh.ler")
def view_simples(request):
    return HttpResponse("ok")


@requer("rh.ler", alvo_de=lambda request, alvo_id: alvo_id)
def view_com_alvo(request, alvo_id):
    return HttpResponse("ok")


@pytest.mark.django_db
def test_permite_quem_tem_a_permissao(rf):
    u = f.pessoa("ana")
    f.atribuir(u, f.papel("p", ["rh.ler.global"], escopo="global"))
    req = rf.get("/")
    req.user = u

    assert view_simples(req).status_code == 200


@pytest.mark.django_db
def test_nega_quem_nao_tem(rf):
    req = rf.get("/")
    req.user = f.pessoa("ana")
    with pytest.raises(PermissionDenied, match="rh.ler"):
        view_simples(req)


@pytest.mark.django_db
def test_nega_anonimo_com_403_e_nao_redireciona(rf):
    """Usuário sem permissão não resolve nada fazendo login de novo."""
    req = rf.get("/")
    req.user = AnonymousUser()
    with pytest.raises(PermissionDenied):
        view_simples(req)


@pytest.mark.django_db
def test_cria_o_cache_no_request_quando_nao_existe(rf):
    u = f.pessoa("ana")
    f.atribuir(u, f.papel("p", ["rh.ler.global"], escopo="global"))
    req = rf.get("/")
    req.user = u

    view_simples(req)
    assert isinstance(req.perm_cache, dict)
    assert req.perm_cache, "o cache foi de fato usado"


@pytest.mark.django_db
def test_reusa_o_cache_que_o_middleware_criou(rf):
    u = f.pessoa("ana")
    f.atribuir(u, f.papel("p", ["rh.ler.global"], escopo="global"))
    req = rf.get("/")
    req.user = u
    marcado = {"marca": True}
    req.perm_cache = marcado

    view_simples(req)
    assert req.perm_cache is marcado, "não substitui o cache existente"


@pytest.mark.django_db
def test_alvo_de_resolve_o_objeto_da_url(rf):
    chefe, liderado, fora = (f.pessoa(n) for n in ("chefe", "lid", "fora"))
    f.lotar(chefe)
    f.lotar(liderado, gestor=chefe)
    f.lotar(fora)
    f.atribuir(chefe, f.papel("g", ["rh.ler.equipe"], escopo="equipe"))

    req = rf.get("/")
    req.user = chefe

    assert view_com_alvo(req, alvo_id=liderado.pk).status_code == 200
    with pytest.raises(PermissionDenied):
        view_com_alvo(req, alvo_id=fora.pk)


def test_preserva_metadados_da_view():
    assert view_simples.__name__ == "view_simples"
