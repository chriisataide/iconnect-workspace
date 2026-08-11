"""Admin de IDN — é a única forma de manter o organograma hoje.

Testado pelo mesmo motivo do admin de Publicações: se ele quebra, a estrutura
organizacional fica sem manutenção e nada mais no sistema denuncia.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.admin.sites import AdminSite
from django.urls import reverse
from django.utils import timezone

from identidade.admin import AtribuicaoPapelAdmin, DelegacaoAdmin, PapelAdmin
from identidade.models import AtribuicaoPapel, Delegacao, Papel
from identidade.tests import fabricas as f


@pytest.fixture
def pedido(rf, admin_user):
    return type("R", (), {"user": admin_user})()


# ── Colunas calculadas ──────────────────────────────────────────────


@pytest.mark.django_db
def test_papel_admin_conta_permissoes():
    admin = PapelAdmin(Papel, AdminSite())
    assert admin.qtd_permissoes(f.papel("p", ["a", "b", "c"])) == 3
    assert admin.qtd_permissoes(f.papel("vazio", [])) == 0


@pytest.mark.django_db
def test_atribuicao_admin_mostra_vigencia():
    admin = AtribuicaoPapelAdmin(AtribuicaoPapel, AdminSite())
    hoje_ = timezone.localdate()
    u, p = f.pessoa("ana"), f.papel("p", [])

    assert admin.situacao(f.atribuir(u, p, inicio=hoje_)) is True
    assert admin.situacao(f.atribuir(u, p, inicio=hoje_ + timedelta(days=2))) is False


@pytest.mark.django_db
def test_delegacao_admin_mostra_vigencia():
    admin = DelegacaoAdmin(Delegacao, AdminSite())
    hoje_ = timezone.localdate()
    a, b = f.pessoa("a"), f.pessoa("b")

    assert admin.situacao(f.delegar(a, b, hoje_, hoje_ + timedelta(days=1))) is True
    assert admin.situacao(f.delegar(a, b, hoje_, hoje_, ativa=False)) is False


@pytest.mark.django_db
def test_atribuicao_admin_carimba_quem_concedeu(pedido, admin_user):
    """Concessão sem autor não sobrevive a auditoria."""
    admin = AtribuicaoPapelAdmin(AtribuicaoPapel, AdminSite())
    atrib = AtribuicaoPapel(
        user=f.pessoa("ana"), papel=f.papel("p", []), escopo="proprio",
        vigencia_inicio=timezone.localdate(),
    )
    admin.save_model(pedido, atrib, form=None, change=False)
    assert atrib.concedido_por == admin_user


@pytest.mark.django_db
def test_atribuicao_admin_nao_sobrescreve_quem_concedeu(pedido):
    admin = AtribuicaoPapelAdmin(AtribuicaoPapel, AdminSite())
    outro = f.pessoa("outro")
    atrib = AtribuicaoPapel(
        user=f.pessoa("ana"), papel=f.papel("p", []), escopo="proprio",
        vigencia_inicio=timezone.localdate(), concedido_por=outro,
    )
    admin.save_model(pedido, atrib, form=None, change=True)
    assert atrib.concedido_por == outro


# ── Telas ───────────────────────────────────────────────────────────


@pytest.mark.django_db
@pytest.mark.parametrize(
    "modelo", ["unidade", "departamento", "lotacao", "papel", "atribuicaopapel", "delegacao"]
)
def test_listagem_de_cada_modelo_abre(client, admin_user, modelo):
    client.force_login(admin_user)
    url = reverse(f"admin:identidade_{modelo}_changelist")
    assert client.get(url).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize(
    "modelo", ["unidade", "departamento", "lotacao", "papel", "atribuicaopapel", "delegacao"]
)
def test_formulario_de_criacao_de_cada_modelo_abre(client, admin_user, modelo):
    client.force_login(admin_user)
    url = reverse(f"admin:identidade_{modelo}_add")
    assert client.get(url).status_code == 200


@pytest.mark.django_db
def test_lotacao_tem_autocomplete_de_user(client, admin_user):
    """`autocomplete_fields` exige `search_fields` no admin do alvo. Sem isso o
    formulário quebra em runtime, não na checagem."""
    client.force_login(admin_user)
    assert client.get(reverse("admin:identidade_lotacao_add")).status_code == 200
