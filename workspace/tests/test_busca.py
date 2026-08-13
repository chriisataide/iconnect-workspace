"""Busca do Workspace."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from django.conf import settings

from workspace.models import Publicacao, TipoPublicacao
from workspace.services.busca import buscar, normalizar


# ── Normalização ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("Férias", "ferias"),
        ("MANUTENÇÃO", "manutencao"),
        ("  Logística  ", "logistica"),
        ("São Paulo", "sao paulo"),
        ("", ""),
    ],
)
def test_normalizar_remove_acento_e_caixa(entrada, esperado):
    assert normalizar(entrada) == esperado


# ── Consulta ─────────────────────────────────────────────────────


@pytest.mark.django_db
def test_consulta_curta_devolve_vazio():
    """Uma letra casaria com quase tudo — ruído, não resultado."""
    assert buscar("a") == {}
    assert buscar("") == {}


@pytest.mark.django_db
def test_encontra_aplicativo_pelo_nome():
    grupos = buscar("financ")
    assert [r.titulo for r in grupos["Aplicativos"]] == ["Financeiro"]


@pytest.mark.django_db
def test_encontra_aplicativo_pela_descricao():
    """'holerite' está na descrição do RH, não no nome."""
    assert "RH" in [r.titulo for r in buscar("holerite")["Aplicativos"]]


@pytest.mark.django_db
def test_busca_sem_acento_encontra_com_acento():
    assert "Logística" in [r.titulo for r in buscar("logistica")["Aplicativos"]]


@pytest.mark.django_db
def test_app_em_breve_aparece_marcado_como_indisponivel():
    # HelpDesk é o único "em breve" PERMANENTE, por desenho: chamado abre no
    # iConnect Platform. RH e Documentação já ocuparam este lugar e ganharam
    # página — exemplo que muda a cada onda não serve de exemplo.
    helpdesk = next(
        r for r in buscar("chamado")["Aplicativos"] if r.titulo == "HelpDesk"
    )
    assert not helpdesk.disponivel


@pytest.mark.django_db
def test_encontra_publicacao():
    Publicacao.objects.create(titulo="Política de férias", publicado=True)
    assert [r.titulo for r in buscar("ferias")["Comunicados"]] == ["Política de férias"]


@pytest.mark.django_db
def test_encontra_no_corpo_da_publicacao():
    Publicacao.objects.create(
        titulo="Aviso", corpo="O refeitório estará fechado na sexta.", publicado=True
    )
    assert [r.titulo for r in buscar("refeitorio")["Comunicados"]] == ["Aviso"]


@pytest.mark.django_db
def test_separa_comunicado_de_noticia():
    Publicacao.objects.create(titulo="Zebra comunicado", tipo=TipoPublicacao.COMUNICADO, publicado=True)
    Publicacao.objects.create(titulo="Zebra notícia", tipo=TipoPublicacao.NOTICIA, publicado=True)

    grupos = buscar("zebra")
    assert len(grupos["Comunicados"]) == 1
    assert len(grupos["Notícias"]) == 1


@pytest.mark.django_db
def test_nao_encontra_rascunho():
    """Busca é a rota mais fácil de vazar conteúdo não publicado."""
    Publicacao.objects.create(titulo="Segredo corporativo", publicado=False)
    assert buscar("segredo") == {}


@pytest.mark.django_db
def test_nao_encontra_agendada():
    Publicacao.objects.create(
        titulo="Anúncio de amanhã", publicado=True, publicar_em=timezone.now() + timedelta(days=1)
    )
    assert buscar("anuncio") == {}


@pytest.mark.django_db
def test_sem_resultado_devolve_vazio():
    assert buscar("xyzabc123") == {}


@pytest.mark.django_db
def test_limita_resultados_por_grupo():
    for i in range(12):
        Publicacao.objects.create(titulo=f"Repetido {i}", publicado=True)
    assert len(buscar("repetido")["Comunicados"]) == 6


# ── Endpoint ─────────────────────────────────────────────────────


@pytest.mark.django_db
def test_endpoint_devolve_html_e_nao_json(client):
    """Etapa 3 §3.1.2: consumidor é o navegador, então devolve fragmento."""
    resposta = client.get(reverse("workspace:buscar"), {"q": "financ"})

    assert resposta.status_code == 200
    assert "text/html" in resposta["Content-Type"]
    assert "Financeiro" in resposta.content.decode()


@pytest.mark.django_db
def test_endpoint_e_publico(client):
    assert client.get(reverse("workspace:buscar"), {"q": "financ"}).status_code == 200


@pytest.mark.django_db
def test_endpoint_avisa_consulta_curta(client):
    resposta = client.get(reverse("workspace:buscar"), {"q": "a"})
    assert "ao menos 2 caracteres" in resposta.content.decode()


@pytest.mark.django_db
def test_endpoint_sem_parametro_nao_quebra(client):
    assert client.get(reverse("workspace:buscar")).status_code == 200


@pytest.mark.django_db
def test_endpoint_informa_quando_nada_encontrado(client):
    corpo = client.get(reverse("workspace:buscar"), {"q": "xyzabc"}).content.decode()
    assert "Nada encontrado" in corpo


@pytest.mark.django_db
def test_endpoint_escapa_a_consulta(client):
    """A consulta é ecoada no HTML. Sem escape, é XSS refletido."""
    corpo = client.get(reverse("workspace:buscar"), {"q": "<script>alert(1)</script>"}).content.decode()
    assert "<script>alert(1)</script>" not in corpo
    assert "&lt;script&gt;" in corpo


# ── Resolução de URL do app ──────────────────────────────────────


@pytest.mark.django_db
def test_resultado_de_app_com_url_direta_leva_ao_destino():
    iconnect = next(
        r for r in buscar("iconnect")["Aplicativos"] if r.titulo == "iConnect Platform"
    )
    assert iconnect.url == settings.ICONNECT_URL
    assert iconnect.disponivel


@pytest.mark.django_db
def test_resultado_de_app_com_url_name_e_resolvido():
    """Provador do outro ramo: app registrado por nome de rota, não URL crua."""
    from workspace import launcher
    from workspace.launcher import AppSpec, registrar_app

    anterior = dict(launcher._apps)
    try:
        registrar_app(AppSpec(chave="zzportal", nome="Zzportal", url_name="workspace:home"))
        achado = next(r for r in buscar("zzportal")["Aplicativos"] if r.titulo == "Zzportal")
        assert achado.url == reverse("workspace:home")
    finally:
        launcher._apps.clear()
        launcher._apps.update(anterior)


@pytest.mark.django_db
def test_resultado_de_app_em_breve_nao_tem_url():
    helpdesk = next(
        r for r in buscar("chamado")["Aplicativos"] if r.titulo == "HelpDesk"
    )
    assert helpdesk.url == ""


@pytest.mark.django_db
def test_resultado_de_modulo_pronto_leva_a_pagina():
    """A busca resolve a rota parametrizada. Sem `args` no `reverse`, buscar
    "RH" estourava NoReverseMatch e derrubava a busca inteira."""
    rh = next(r for r in buscar("holerite")["Aplicativos"] if r.titulo == "RH")
    assert rh.url == "/workspace/m/rh/"
