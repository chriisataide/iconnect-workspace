"""App Launcher — o catálogo de sistemas do Portal (Etapa 5 §5.9)."""

from __future__ import annotations

import pytest

from workspace import launcher
from workspace.launcher import AppSpec, apps_disponiveis, registrar_app


@pytest.fixture
def catalogo_vazio():
    """O catálogo é estado de processo, semeado no ready(). Isolar e devolver."""
    anterior = dict(launcher._apps)
    launcher.limpar()
    yield
    launcher.limpar()
    launcher._apps.update(anterior)


def test_semente_traz_os_dez_destinos_do_diagrama():
    chaves = {s.chave for s in launcher.catalogo_semente()}
    assert chaves == {
        "iconnect", "helpdesk", "rh", "financeiro", "operacoes",
        "logistica", "redes", "compras", "universidade", "documentacao",
    }


def test_apenas_o_iconnect_tem_destino_hoje():
    disponiveis = [s.chave for s in launcher.catalogo_semente() if s.disponivel]
    assert disponiveis == ["iconnect"]


def test_disponivel_reflete_ter_destino():
    assert AppSpec(chave="a", nome="A", url_direta="/x/").disponivel
    assert AppSpec(chave="b", nome="B", url_name="workspace:home").disponivel
    assert not AppSpec(chave="c", nome="C").disponivel


def test_app_registrado_vence_a_semente(catalogo_vazio):
    """O caso que a semente existe para permitir: o sistema real nasce."""
    registrar_app(AppSpec(chave="rh", nome="RH de verdade", url_name="workspace:home"))
    launcher.semear()

    rh = next(s for s in apps_disponiveis() if s.chave == "rh")
    assert rh.nome == "RH de verdade"
    assert rh.disponivel


def test_semear_e_idempotente(catalogo_vazio):
    launcher.semear()
    launcher.semear()
    chaves = [s.chave for s in apps_disponiveis()]
    assert len(chaves) == len(set(chaves)) == 10


def test_ordenacao_poe_disponivel_antes_de_em_breve(catalogo_vazio):
    registrar_app(AppSpec(chave="tarde", nome="Z", ordem=999, url_direta="/z/"))
    registrar_app(AppSpec(chave="cedo", nome="A", ordem=1))

    assert [s.chave for s in apps_disponiveis()] == ["tarde", "cedo"]


def test_ordenacao_desempata_por_nome(catalogo_vazio):
    registrar_app(AppSpec(chave="b", nome="Beta", ordem=10))
    registrar_app(AppSpec(chave="a", nome="Alfa", ordem=10))
    assert [s.chave for s in apps_disponiveis()] == ["a", "b"]


def test_anonimo_nao_ve_app_que_exige_permissao(catalogo_vazio):
    """Negar por omissão. Liberar é como portal vaza tela de RH."""
    registrar_app(AppSpec(chave="publico", nome="Público"))
    registrar_app(AppSpec(chave="restrito", nome="Restrito", permissao="rh.ler.global"))

    assert [s.chave for s in apps_disponiveis(pessoa=None)] == ["publico"]


def test_autenticado_ainda_nao_ve_restrito_ate_o_st014(catalogo_vazio):
    """`pode()` não existe ainda; até lá o filtro nega. Documenta o estado."""
    registrar_app(AppSpec(chave="restrito", nome="Restrito", permissao="rh.ler.global"))
    assert apps_disponiveis(pessoa=object()) == []


def test_registrar_substitui_por_padrao(catalogo_vazio):
    registrar_app(AppSpec(chave="x", nome="Primeiro"))
    registrar_app(AppSpec(chave="x", nome="Segundo"))
    assert apps_disponiveis()[0].nome == "Segundo"


def test_registrar_sem_substituir_recusa_colisao(catalogo_vazio):
    registrar_app(AppSpec(chave="x", nome="Primeiro"))
    with pytest.raises(ValueError, match="Já existe app"):
        registrar_app(AppSpec(chave="x", nome="Segundo"), substituir=False)


def test_recusa_objeto_que_nao_e_appspec(catalogo_vazio):
    with pytest.raises(TypeError, match="não é um AppSpec"):
        registrar_app({"chave": "x", "nome": "X"})


def test_recusa_appspec_sem_chave(catalogo_vazio):
    with pytest.raises(ValueError, match="precisa de `chave`"):
        registrar_app(AppSpec(chave="", nome="Sem chave"))


def test_appspec_e_imutavel():
    spec = AppSpec(chave="x", nome="X")
    with pytest.raises(Exception):  # FrozenInstanceError
        spec.nome = "Outro"
