"""Admin de Publicações — é por aqui que Comunicados e Notícias são alimentados.

Testado porque é a *única* forma de publicar hoje. Admin quebrado significa
Portal permanentemente vazio, e nada mais no sistema denunciaria isso.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.admin.sites import AdminSite
from django.urls import reverse
from django.utils import timezone

from workspace.admin import PublicacaoAdmin
from workspace.models import Publicacao, TipoPublicacao
from workspace.templatetags.portal import data_extenso


@pytest.fixture
def admin_publicacao():
    return PublicacaoAdmin(Publicacao, AdminSite())


@pytest.fixture
def pedido(rf, admin_user):
    requisicao = rf.post("/admin/")
    requisicao.user = admin_user
    # As actions do admin usam django.contrib.messages, que exige middleware.
    from django.contrib.messages.storage.fallback import FallbackStorage

    requisicao.session = {}
    requisicao._messages = FallbackStorage(requisicao)
    return requisicao


# ── Coluna "No ar" ───────────────────────────────────────────────


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("kwargs", "esperado"),
    [
        ({"publicado": True}, "✅ no ar"),
        ({"publicado": False}, "— rascunho"),
        ({"publicado": True, "publicar_em": "futuro"}, "🕒 agendado"),
        ({"publicado": True, "expira_em": "passado"}, "⌛ expirado"),
    ],
)
def test_coluna_situacao(admin_publicacao, kwargs, esperado):
    agora = timezone.now()
    if kwargs.get("publicar_em") == "futuro":
        kwargs["publicar_em"] = agora + timedelta(days=1)
    if kwargs.get("expira_em") == "passado":
        kwargs["publicar_em"] = agora - timedelta(days=5)
        kwargs["expira_em"] = agora - timedelta(days=1)

    pub = Publicacao.objects.create(titulo="X", **kwargs)
    assert admin_publicacao.situacao(pub) == esperado


# ── Autoria ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_save_model_carimba_o_autor(admin_publicacao, pedido, admin_user):
    pub = Publicacao(titulo="Novo comunicado")
    admin_publicacao.save_model(pedido, pub, form=None, change=False)
    assert pub.autor == admin_user


@pytest.mark.django_db
def test_save_model_nao_sobrescreve_autor_existente(
    admin_publicacao, pedido, admin_user, django_user_model
):
    outro = django_user_model.objects.create_user(username="outro", password="x")
    pub = Publicacao(titulo="De outra pessoa", autor=outro)
    admin_publicacao.save_model(pedido, pub, form=None, change=True)
    assert pub.autor == outro


# ── Actions em lote ──────────────────────────────────────────────


@pytest.mark.django_db
def test_action_publicar_agora(admin_publicacao, pedido):
    Publicacao.objects.create(titulo="A", publicado=False)
    Publicacao.objects.create(titulo="B", publicado=False)

    admin_publicacao.publicar_agora(pedido, Publicacao.objects.all())
    assert Publicacao.objects.publicadas().count() == 2


@pytest.mark.django_db
def test_action_publicar_agora_corrige_agendamento_futuro(admin_publicacao, pedido):
    """Publicar agora precisa puxar `publicar_em` para o presente, senão o item
    fica 'publicado' e mesmo assim invisível."""
    Publicacao.objects.create(
        titulo="Agendada", publicado=False, publicar_em=timezone.now() + timedelta(days=30)
    )
    admin_publicacao.publicar_agora(pedido, Publicacao.objects.all())
    assert Publicacao.objects.publicadas().count() == 1


@pytest.mark.django_db
def test_action_despublicar(admin_publicacao, pedido):
    Publicacao.objects.create(titulo="A", publicado=True)
    admin_publicacao.despublicar(pedido, Publicacao.objects.all())
    assert Publicacao.objects.publicadas().count() == 0


# ── Telas do admin ───────────────────────────────────────────────


@pytest.mark.django_db
def test_listagem_do_admin_abre(client, admin_user):
    client.force_login(admin_user)
    assert client.get(reverse("admin:workspace_publicacao_changelist")).status_code == 200


@pytest.mark.django_db
def test_formulario_de_criacao_abre(client, admin_user):
    client.force_login(admin_user)
    assert client.get(reverse("admin:workspace_publicacao_add")).status_code == 200


@pytest.mark.django_db
def test_publicar_pelo_admin_aparece_no_portal(client, admin_user):
    """O caminho completo que o usuário vai percorrer."""
    client.force_login(admin_user)
    client.post(
        reverse("admin:workspace_publicacao_add"),
        {
            "tipo": TipoPublicacao.NOTICIA,
            "titulo": "Nova base em Campinas",
            "resumo": "Inauguração dia 22.",
            "corpo": "",
            "prioridade": 0,
            "publicado": "on",
            "publicar_em_0": timezone.localtime().strftime("%Y-%m-%d"),
            "publicar_em_1": "08:00:00",
            "_save": "Salvar",
        },
    )
    noticias = client.get(reverse("workspace:home")).context["noticias"]
    assert [p.titulo for p in noticias] == ["Nova base em Campinas"]


# ── Detalhes menores, mas que aparecem na tela ───────────────────


@pytest.mark.django_db
def test_str_identifica_tipo_e_titulo():
    pub = Publicacao.objects.create(titulo="Aviso geral", tipo=TipoPublicacao.COMUNICADO)
    assert str(pub) == "[Comunicado] Aviso geral"


def test_data_extenso_com_valor_vazio():
    assert data_extenso(None) == ""
    assert data_extenso("") == ""


def test_data_extenso_sem_ano():
    from datetime import date

    assert data_extenso(date(2026, 8, 7), com_ano=False) == "7 de agosto"
