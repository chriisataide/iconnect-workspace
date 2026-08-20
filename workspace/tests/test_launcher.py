"""App Launcher — o catálogo de sistemas do Workspace (Etapa 5 §5.9)."""

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


def test_semente_traz_todo_modulo_mais_a_platform():
    """Derivado de `MODULOS` — ver o comentário em `test_home.py`."""
    from workspace.modulos import MODULOS

    chaves = {s.chave for s in launcher.catalogo_semente()}

    assert chaves == {m.chave for m in MODULOS} | {"iconnect"}


def test_iconnect_e_o_unico_destino_fora_do_portal():
    """Um caminho só para o sistema principal.

    Antes existiam três (topbar, tile, faixa), o que faz o usuário hesitar
    sobre se levam ao mesmo lugar. Os demais destinos são rotas internas.
    """
    externos = [s.chave for s in launcher.catalogo_semente() if s.url_direta]
    assert externos == ["iconnect"]


def test_o_helpdesk_saiu_da_faixa_de_aplicativos():
    """§38 — o tile levava para fora e não fazia mais nada.

    Desde o §21 existe `/workspace/chamados/`, que faz as quatro coisas que o
    §38 pede do Workspace: direciona, integra, exibe status e exibe histórico.
    Manter os dois deixaria na home um atalho que faz menos — e o atalho cego
    seria o mais clicado, porque estava na primeira tela.
    """
    chaves = {s.chave for s in launcher.catalogo_semente()}

    assert "helpdesk" not in chaves


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
    from workspace.modulos import MODULOS

    chaves = [s.chave for s in apps_disponiveis()]
    esperado = len(MODULOS) + 1  # + iConnect Platform (o HelpDesk saiu no §38)
    assert len(chaves) == len(set(chaves)) == esperado


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
