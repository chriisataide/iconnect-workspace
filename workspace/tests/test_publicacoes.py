"""Publicações — o que alimenta Comunicados e Notícias."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from workspace.models import Prioridade, Publicacao, TipoPublicacao


def cria(**kwargs) -> Publicacao:
    dados = {"titulo": "Título", "tipo": TipoPublicacao.COMUNICADO, "publicado": True}
    return Publicacao.objects.create(**{**dados, **kwargs})


# ── Regra de "estar no ar" ───────────────────────────────────────


@pytest.mark.django_db
def test_publicada_aparece():
    pub = cria(titulo="Política de viagens")
    assert pub.no_ar
    assert pub in Publicacao.objects.publicadas()


@pytest.mark.django_db
def test_rascunho_nao_aparece():
    pub = cria(publicado=False)
    assert not pub.no_ar
    assert pub not in Publicacao.objects.publicadas()


@pytest.mark.django_db
def test_agendada_para_o_futuro_nao_aparece():
    pub = cria(publicar_em=timezone.now() + timedelta(days=1))
    assert not pub.no_ar
    assert pub not in Publicacao.objects.publicadas()


@pytest.mark.django_db
def test_expirada_nao_aparece():
    pub = cria(
        publicar_em=timezone.now() - timedelta(days=10),
        expira_em=timezone.now() - timedelta(days=1),
    )
    assert not pub.no_ar
    assert pub not in Publicacao.objects.publicadas()


@pytest.mark.django_db
def test_sem_data_de_expiracao_nao_expira():
    assert cria(expira_em=None).no_ar


# ── Ordenação ────────────────────────────────────────────────────


@pytest.mark.django_db
def test_fixado_vem_antes_do_mais_recente():
    agora = timezone.now()
    cria(titulo="Recente", publicar_em=agora)
    cria(titulo="Fixado antigo", fixado=True, publicar_em=agora - timedelta(days=30))

    assert [p.titulo for p in Publicacao.objects.publicadas()] == ["Fixado antigo", "Recente"]


@pytest.mark.django_db
def test_ordena_por_data_de_publicacao_nao_de_criacao():
    """O que vale para o leitor é quando foi publicado."""
    agora = timezone.now()
    cria(titulo="Criado primeiro, publicado depois", publicar_em=agora)
    cria(titulo="Criado depois, publicado antes", publicar_em=agora - timedelta(days=5))

    assert Publicacao.objects.publicadas().first().titulo == "Criado primeiro, publicado depois"


# ── Home ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_home_separa_comunicados_de_noticias(client):
    cria(titulo="Comunicado A", tipo=TipoPublicacao.COMUNICADO)
    cria(titulo="Notícia B", tipo=TipoPublicacao.NOTICIA)

    ctx = client.get(reverse("workspace:home")).context
    assert [p.titulo for p in ctx["comunicados"]] == ["Comunicado A"]
    assert [p.titulo for p in ctx["noticias"]] == ["Notícia B"]


@pytest.mark.django_db
def test_home_limita_a_quatro_por_card(client):
    for i in range(7):
        cria(titulo=f"Comunicado {i}")
    assert len(client.get(reverse("workspace:home")).context["comunicados"]) == 4


@pytest.mark.django_db
def test_card_vazio_diz_onde_publicar(client):
    """Empty state precisa dar a próxima ação, não só constatar o vazio."""
    corpo = client.get(reverse("workspace:home")).content.decode()
    assert "Nenhum comunicado no ar." in corpo
    assert "Publicações" in corpo  # aponta para o admin


# ── Detalhe ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_detalhe_abre_publicacao_no_ar(client):
    pub = cria(titulo="Manutenção programada", resumo="Sábado, 8h às 12h")
    resposta = client.get(reverse("workspace:publicacao_detalhe", args=[pub.pk]))

    assert resposta.status_code == 200
    assert "Manutenção programada" in resposta.content.decode()


@pytest.mark.django_db
def test_detalhe_de_rascunho_da_404(client):
    """URL adivinhada não pode vazar rascunho nem comunicado agendado."""
    pub = cria(publicado=False)
    assert client.get(reverse("workspace:publicacao_detalhe", args=[pub.pk])).status_code == 404


@pytest.mark.django_db
def test_detalhe_de_agendada_da_404(client):
    pub = cria(publicar_em=timezone.now() + timedelta(days=2))
    assert client.get(reverse("workspace:publicacao_detalhe", args=[pub.pk])).status_code == 404


@pytest.mark.django_db
def test_detalhe_inexistente_da_404(client):
    assert client.get(reverse("workspace:publicacao_detalhe", args=[999999])).status_code == 404


# ── Prioridade ───────────────────────────────────────────────────


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("prioridade", "token"),
    [
        (Prioridade.URGENTE, "var(--au-danger)"),
        (Prioridade.ATENCAO, "var(--au-warning)"),
        (Prioridade.NORMAL, "var(--au-accent)"),
    ],
)
def test_cor_segue_a_prioridade(prioridade, token):
    assert cria(prioridade=prioridade).cor == token


# ── Formatação de data em português ──────────────────────────────


@pytest.mark.django_db
def test_data_do_artigo_tem_mes_em_minuscula(client):
    """O locale pt-BR do Django devolve "Agosto". Em português é "agosto"."""
    pub = cria(publicar_em=timezone.make_aware(timezone.datetime(2026, 8, 7, 10, 0)))
    corpo = client.get(reverse("workspace:publicacao_detalhe", args=[pub.pk])).content.decode()

    assert "7 de agosto de 2026" in corpo
    assert "Agosto" not in corpo


@pytest.mark.django_db
def test_data_da_home_capitaliza_so_a_primeira_letra(client):
    """`text-transform: capitalize` produziria "Sexta-Feira, 7 De Agosto"."""
    hoje = client.get(reverse("workspace:home")).context["hoje"]

    assert hoje[0].isupper()
    assert " De " not in hoje
    assert hoje.count(",") == 1
    # Fora a primeira, nenhuma palavra pode começar com maiúscula.
    assert all(not p[:1].isupper() for p in hoje.split()[1:]), hoje
