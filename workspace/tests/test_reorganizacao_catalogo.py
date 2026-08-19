"""O catálogo e a home depois da reorganização pedida.

Todas as remoções seguem a MESMA regra, e ela é o que estes testes guardam:
**some da tela, o dado fica**. `ativo=False` e nunca `delete()` —
`SolicitacaoServico.item` é `PROTECT`, e apagar o item exigiria apagar junto o
histórico de quem já pediu. É também o que torna cada uma reversível com um
clique no admin.

Duas metades por remoção, e as duas importam:

1. **Fora da SEMENTE** — senão `semear_catalogo` recria o item ativo em todo
   banco novo, e a decisão dura até o próximo `migrate` limpo.
2. **`ativo=False` por MIGRAÇÃO** — senão a decisão não alcança o banco que já
   existe, que é justamente o que está em produção.
"""

from __future__ import annotations

import pytest

from workspace.catalogo_inicial import CATALOGO_INICIAL
from workspace.modulos import MODULOS, modulo_por_chave

SAIRAM = ["epi", "material", "material-marketing", "parecer-juridico", "home-office"]


# ── §12 Logística → Suprimentos ─────────────────────────────────────


def test_o_modulo_agora_se_chama_suprimentos():
    nomes = {m.nome for m in MODULOS}
    assert "Suprimentos" in nomes
    assert "Logística" not in nomes


def test_o_prefixo_de_dominio_continua_log():
    """O rótulo mudou; a CHAVE não.

    `log.` está gravado em cada pedido já feito, na permissão `log.atender`, nos
    papéis concedidos e nas regras de aprovação. Renomear o prefixo junto com a
    palavra seria migração de dados travestida de troca de nome — e é assim que
    um rename vira incidente.
    """
    assert modulo_por_chave("suprimentos").dominios == ("log.",)


# ── §22 Compras sai da home ─────────────────────────────────────────


def test_compras_nao_tem_mais_tile_na_home():
    assert modulo_por_chave("compras") is None


def test_mas_o_dominio_de_compras_continua_vivo():
    """Saiu a PORTA, não o departamento. Os itens continuam pedíveis pela busca
    e pela navegação por intenção, e a fila de Compras continua recebendo."""
    assert any(s["dominio"].startswith("com.") for s in CATALOGO_INICIAL)


# ── §14, §24, §26 — os itens removidos ──────────────────────────────


@pytest.mark.parametrize("chave", SAIRAM)
def test_item_removido_saiu_da_semente(chave):
    assert not any(s["chave"] == chave for s in CATALOGO_INICIAL)


@pytest.mark.django_db
def test_a_migracao_desativa_e_nao_apaga():
    """A prova de que nada é apagado, exercitando a migração de verdade.

    Não basta olhar o banco de teste: ele nasce das migrações, sem semente, e
    os itens nem existem lá — o `update()` acertaria zero linhas e o teste
    passaria sem provar nada. Aqui os itens são criados ANTES, com um pedido
    pendurado em cada um, e a migração roda em cima disso.

    O pedido é o ponto. `SolicitacaoServico.item` é `PROTECT`: se algum dia
    alguém trocar o `update(ativo=False)` por um `delete()`, este teste explode
    com `ProtectedError` em vez de deixar o histórico ser apagado em produção.
    """
    from decimal import Decimal
    from importlib import import_module

    from django.apps import apps as registro

    from identidade.tests import fabricas as f
    from workspace.models.catalogo import (
        GrupoCatalogo,
        ItemCatalogo,
        SolicitacaoServico,
    )

    ana = f.pessoa("ana")
    f.lotar(ana)
    for chave in SAIRAM:
        item = ItemCatalogo.objects.create(
            chave=chave, nome=chave, grupo=GrupoCatalogo.ESPACO,
            dominio="log.requisicao", prazo_prometido_dias=2,
            limite_auto_aprovacao=Decimal("0"), campos=[],
        )
        SolicitacaoServico.objects.create(item=item, solicitante=ana, dados={})

    import_module("workspace.migrations.0026_desativa_trabalho_remoto").desativar(
        registro, None
    )
    import_module("workspace.migrations.0027_catalogo_suprimentos").aplicar(
        registro, None
    )

    for chave in SAIRAM:
        item = ItemCatalogo.objects.filter(chave=chave).first()
        assert item is not None, f"{chave} foi APAGADO — deveria só estar inativo"
        assert item.ativo is False, chave
    assert SolicitacaoServico.objects.count() == len(SAIRAM), "histórico perdido"


# ── §14 — o substituto ──────────────────────────────────────────────


def test_controle_de_materiais_substitui_os_tres():
    """Um item no lugar de três formulários com os mesmos campos.

    O tipo virou CAMPO: assim Suprimentos continua sabendo que foi EPI, e quem
    pede para de ter que classificar o próprio pedido — decisão que a pessoa
    não tem como tomar certo, e que não mudava o destino da fila de qualquer
    forma.
    """
    spec = next(s for s in CATALOGO_INICIAL if s["chave"] == "controle-materiais")
    tipo = next(c for c in spec["campos"] if c["chave"] == "tipo")

    valores = {o["valor"] for o in tipo["opcoes"]}
    assert {"epi", "uniforme", "trabalho"} <= valores
    assert spec["dominio"] == "log.requisicao", "tem de cair na fila de Suprimentos"


def test_quem_procura_epi_ainda_acha():
    """Os termos dos itens removidos migraram para o substituto. Sem isto, quem
    digita "epi" na busca não encontra nada — e a reorganização vira sumiço."""
    spec = next(s for s in CATALOGO_INICIAL if s["chave"] == "controle-materiais")

    for termo in ("epi", "uniforme", "material de trabalho"):
        assert termo in spec["termos"], termo
