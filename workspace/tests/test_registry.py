"""Registro de providers — ST-002 T4.

Aceite ③: o registry aceita e devolve provider.
"""

from __future__ import annotations

import pytest

from workspace.providers import WorkspaceProvider, registry
from workspace.providers.base import (
    ActionSpec,
    PendingItemDTO,
    SearchDocumentDTO,
    WidgetSpec,
)


class ProviderFalso(WorkspaceProvider):
    key = "falso"
    label = "Domínio Falso"


class OutroProvider(WorkspaceProvider):
    key = "outro"
    label = "Outro Domínio"


@pytest.fixture(autouse=True)
def _registro_limpo():
    """O registro é estado de processo. Sem isolar, um teste contamina o outro."""
    registry.limpar()
    yield
    registry.limpar()


def test_register_aceita_e_get_devolve():
    provider = registry.register(ProviderFalso())
    assert registry.get("falso") is provider


def test_all_devolve_em_ordem_estavel_de_chave():
    registry.register(OutroProvider())
    registry.register(ProviderFalso())
    assert [p.key for p in registry.all()] == ["falso", "outro"]


def test_all_vazio_quando_nada_registrado():
    assert registry.all() == []


def test_get_devolve_none_para_chave_desconhecida():
    assert registry.get("inexistente") is None


def test_chave_duplicada_levanta():
    registry.register(ProviderFalso())
    with pytest.raises(ValueError, match="Já existe provider"):
        registry.register(ProviderFalso())


def test_chave_duplicada_com_substituir_troca():
    primeiro = registry.register(ProviderFalso())
    segundo = registry.register(ProviderFalso(), substituir=True)
    assert registry.get("falso") is segundo
    assert registry.get("falso") is not primeiro


def test_recusa_objeto_que_nao_e_provider():
    class Impostor:
        key = "impostor"
        label = "Impostor"

    with pytest.raises(TypeError, match="não é um WorkspaceProvider"):
        registry.register(Impostor())


@pytest.mark.parametrize(
    ("chave", "rotulo", "trecho"),
    [
        ("", "Tem rótulo", "precisa declarar `key`"),
        ("tem_chave", "", "precisa declarar `label`"),
    ],
)
def test_recusa_provider_sem_identificacao(chave, rotulo, trecho):
    class Incompleto(WorkspaceProvider):
        key = chave
        label = rotulo

    with pytest.raises(ValueError, match=trecho):
        registry.register(Incompleto())


def test_unregister_remove_e_sinaliza():
    registry.register(ProviderFalso())
    assert registry.unregister("falso") is True
    assert registry.unregister("falso") is False
    assert registry.get("falso") is None


def test_metodos_padrao_devolvem_vazio():
    """Um domínio implementa só o que oferece — o resto não pode explodir."""
    provider = ProviderFalso()
    pessoa = object()
    assert provider.widgets(pessoa) == []
    assert provider.quick_actions(pessoa) == []
    assert provider.pending_items(pessoa) == []
    assert list(provider.search_documents()) == []


def test_dtos_sao_imutaveis():
    """Provider não pode mutar a spec depois de devolvê-la ao runtime."""
    spec = WidgetSpec(chave="aprovacoes", titulo="Aprovações", zona=2)
    with pytest.raises(Exception):  # FrozenInstanceError
        spec.zona = 3


def test_dtos_tem_defaults_utilizaveis():
    widget = WidgetSpec(chave="w", titulo="W", zona=1)
    assert widget.permissao is None and widget.ttl == 60 and widget.timeout == 3.0

    acao = ActionSpec(chave="a", rotulo="A", url_name="workspace:home")
    assert acao.ordem == 100

    item = PendingItemDTO(origem="svc", titulo="T", url="/x/")
    assert item.prazo is None and item.prioridade == 0

    doc = SearchDocumentDTO(
        origem="cnt", origem_id="1", titulo="T", url="/x/", acl_subjects=["*"]
    )
    assert doc.extra == {}


def test_acl_subjects_nao_compartilha_estado_entre_documentos():
    """`extra` com default mutável compartilhado seria vazamento entre docs."""
    a = SearchDocumentDTO(origem="cnt", origem_id="1", titulo="A", url="/a/", acl_subjects=[])
    b = SearchDocumentDTO(origem="cnt", origem_id="2", titulo="B", url="/b/", acl_subjects=[])
    a.extra["x"] = 1
    assert b.extra == {}
