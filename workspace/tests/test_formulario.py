"""FRM — ramo, passo e escolha no formulário dinâmico.

O que estes testes protegem:

1. **A tela esconde, o servidor decide.** Sem JS todos os ramos aparecem; quem
   descarta o que não é do ramo escolhido é o servidor.
2. **Lista fechada é fechada dos dois lados.** O `<select>` guia; um valor
   forjado no POST não passa.
3. **O passo que acontece depois do envio aparece na trilha.** Esconder que
   ainda falta uma etapa é o que faz a pessoa achar que terminou.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.models import (
    GrupoCatalogo,
    ItemCatalogo,
    SolicitacaoServico,
    TipoCampo,
)
from workspace.services import catalogo as svc
from workspace.services import formulario as frm
from workspace.services.catalogo import SolicitacaoError

RAMO = [
    {"chave": "origem", "rotulo": "Tipo", "tipo": TipoCampo.ESCOLHA,
     "obrigatorio": True, "passo": 1,
     "opcoes": [
         {"valor": "interno", "rotulo": "Interno"},
         {"valor": "externo", "rotulo": "Externo"},
     ]},
    {"chave": "instituicao", "rotulo": "Instituição", "obrigatorio": True, "passo": 2,
     "quando": {"campo": "origem", "igual": "externo"}},
    {"chave": "aplicacao", "rotulo": "Aplicação", "tipo": TipoCampo.TEXTO_LONGO,
     "obrigatorio": True, "passo": 3},
]


@pytest.fixture
def curso():
    return ItemCatalogo.objects.create(
        chave="curso", nome="Treinamento", grupo=GrupoCatalogo.DESENVOLVIMENTO,
        dominio="hab.treinamento", campos=RAMO,
        passos=[{"titulo": "Tipo"}, {"titulo": "O curso"}, {"titulo": "Aplicação"}],
        exige_valor=True,
        valor_quando={"campo": "origem", "igual": "externo"},
        limite_auto_aprovacao=Decimal("100000"),
    )


@pytest.fixture
def ana():
    pessoa = f.pessoa("ana")
    f.lotar(pessoa)
    return pessoa


# ── Ramo ────────────────────────────────────────────────────────────


def test_campo_sem_condicao_existe_sempre():
    assert frm.condicao_satisfeita({"chave": "x"}, {}) is True


def test_campo_do_outro_ramo_nao_existe():
    campo = {"chave": "instituicao", "quando": {"campo": "origem", "igual": "externo"}}
    assert frm.condicao_satisfeita(campo, {"origem": "interno"}) is False
    assert frm.condicao_satisfeita(campo, {"origem": "externo"}) is True


def test_condicao_aceita_lista_de_valores():
    campo = {"quando": {"campo": "tipo", "igual": ["a", "b"]}}
    assert frm.condicao_satisfeita(campo, {"tipo": "b"}) is True
    assert frm.condicao_satisfeita(campo, {"tipo": "c"}) is False


@pytest.mark.django_db
def test_o_que_e_de_outro_ramo_nao_e_exigido(curso, ana):
    """Pedir "qual a instituição" a quem escolheu curso interno é pedir para
    inventar uma resposta."""
    impedimentos = svc.verificar(
        curso, ana, {"origem": "interno", "aplicacao": "vou aplicar assim"}
    )
    assert [i.campo for i in impedimentos] == []


@pytest.mark.django_db
def test_o_que_e_do_ramo_escolhido_continua_obrigatorio(curso, ana):
    impedimentos = svc.verificar(
        curso, ana, {"origem": "externo", "aplicacao": "x"}, valor=Decimal("10")
    )
    assert "instituicao" in [i.campo for i in impedimentos]


@pytest.mark.django_db
def test_resposta_do_ramo_abandonado_nao_e_gravada(curso, ana):
    """Sem JS a tela mostra os dois ramos. Gravar os dois deixaria o pedido
    dizendo que o curso é interno E que a instituição é a Fulana — e seria o
    aprovador a descobrir a contradição."""
    pedido = svc.solicitar(
        curso, ana,
        {"origem": "interno", "instituicao": "Fulana Cursos", "aplicacao": "x"},
    )
    assert "instituicao" not in pedido.dados
    assert pedido.dados["origem"] == "interno"


# ── O valor que só existe em um ramo ────────────────────────────────


@pytest.mark.django_db
def test_ramo_sem_valor_nao_exige_valor(curso, ana):
    """Curso interno da empresa não tem preço a informar."""
    pedido = svc.solicitar(curso, ana, {"origem": "interno", "aplicacao": "x"})
    assert pedido.valor is None


@pytest.mark.django_db
def test_ramo_com_valor_continua_exigindo(curso, ana):
    impedimentos = svc.verificar(
        curso, ana, {"origem": "externo", "instituicao": "X", "aplicacao": "y"}
    )
    assert "valor" in [i.campo for i in impedimentos]


@pytest.mark.django_db
def test_valor_digitado_no_ramo_errado_e_descartado(curso, ana):
    """Guardar o que sobrou de um ramo abandonado faria o pedido comprometer
    orçamento por um número que a tela nem mostrava."""
    pedido = svc.solicitar(
        curso, ana, {"origem": "interno", "aplicacao": "x"}, valor=Decimal("900")
    )
    assert pedido.valor is None


# ── Escolha ─────────────────────────────────────────────────────────


def test_opcoes_aceitam_a_forma_curta():
    assert frm.opcoes_de({"opcoes": ["a", "b"]}) == [
        {"valor": "a", "rotulo": "a"},
        {"valor": "b", "rotulo": "b"},
    ]


@pytest.mark.django_db
def test_valor_fora_da_lista_e_recusado(curso, ana):
    """A lista fechada é fechada dos dois lados: o `<select>` guia, e aqui é
    onde um valor forjado no POST para de valer."""
    impedimentos = svc.verificar(curso, ana, {"origem": "hibrido", "aplicacao": "x"})
    assert "origem" in [i.campo for i in impedimentos]


@pytest.mark.django_db
def test_escolha_valida_passa(curso, ana):
    impedimentos = svc.verificar(curso, ana, {"origem": "interno", "aplicacao": "x"})
    assert "origem" not in [i.campo for i in impedimentos]


# ── Passos ──────────────────────────────────────────────────────────


def test_item_sem_passos_nao_tem_trilha():
    """Stepper em formulário de dois campos é cerimônia."""
    assert frm.passos_de(ItemCatalogo(passos=[])) == []


def test_passo_apos_envio_entra_na_trilha():
    item = ItemCatalogo(passos=[{"titulo": "Compras"},
                                {"titulo": "Acerto", "apos_envio": True}])
    trilha = frm.passos_de(item)
    assert [p["numero"] for p in trilha] == [1, 2]
    assert trilha[1]["apos_envio"] is True


def test_campo_sem_passo_mora_no_primeiro():
    """Assim um item ganha passos sem que todos os campos sejam reescritos."""
    assert frm.passo_do_campo({"chave": "x"}) == 1
    assert frm.passo_do_campo({"chave": "x", "passo": "2"}) == 2


# ── As telas ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_a_tela_desenha_select_e_trilha(client, curso, ana):
    client.force_login(ana)
    html = client.get(reverse("workspace:pedir", args=["curso"])).content.decode()

    assert "<select" in html
    assert 'value="interno"' in html
    assert 'data-quando-campo="origem"' in html
    assert 'data-passo="2"' in html
    assert "au-trilha" in html


@pytest.mark.django_db
def test_a_tela_manda_os_dois_ramos_e_o_servidor_escolhe(client, curso, ana):
    """Sem JS os dois ramos aparecem preenchíveis — e é isso que faz a página
    continuar funcionando sem JS. O servidor é quem separa."""
    client.force_login(ana)
    resposta = client.post(
        reverse("workspace:pedir", args=["curso"]),
        {
            "origem": "interno",
            "instituicao": "Fulana Cursos",
            "aplicacao": "vou treinar a equipe",
        },
    )

    assert resposta.status_code == 302
    assert SolicitacaoServico.objects.get().dados == {
        "origem": "interno",
        "aplicacao": "vou treinar a equipe",
    }


@pytest.mark.django_db
def test_erro_de_ramo_volta_com_a_mensagem_do_campo_certo(client, curso, ana):
    client.force_login(ana)
    html = client.post(
        reverse("workspace:pedir", args=["curso"]),
        {"origem": "externo", "aplicacao": "x", "valor": "100,00"},
    ).content.decode()

    assert "Instituição é obrigatório" in html
    assert not SolicitacaoServico.objects.exists()


# ── Os itens que os apontamentos pediram ────────────────────────────


def test_acesso_a_sistema_deixou_de_ser_texto_livre():
    """À mão, o mesmo sistema chegava como `iconnect`, `IConnect` e `aquele
    portal` — impossível de rotear e impossível de medir."""
    from workspace.catalogo_inicial import CATALOGO_INICIAL

    campos = {
        c["chave"]: c
        for s in CATALOGO_INICIAL if s["chave"] == "acesso-sistema"
        for c in s["campos"]
    }
    assert campos["sistema"]["tipo"] == TipoCampo.ESCOLHA
    assert len(frm.opcoes_de(campos["sistema"])) >= 3
    assert campos["motivo"]["obrigatorio"] is True


def test_vpn_pergunta_ate_quando_so_no_temporario():
    """Sem a pergunta, todo acesso vira definitivo por omissão — e é assim que
    se acumula gente com VPN de um projeto que acabou."""
    from workspace.catalogo_inicial import CATALOGO_INICIAL

    campos = {
        c["chave"]: c
        for s in CATALOGO_INICIAL if s["chave"] == "acesso-vpn"
        for c in s["campos"]
    }
    assert campos["periodo"]["tipo"] == TipoCampo.ESCOLHA
    assert campos["ate_quando"]["quando"] == {
        "campo": "periodo", "igual": "temporario"
    }


def test_reciclagem_pergunta_o_vencimento_e_o_responsavel_pelo_terceiro():
    """O técnico terceiro não acessa o Workspace: sem o responsável, o pedido
    chega sem ninguém do outro lado."""
    from workspace.catalogo_inicial import CATALOGO_INICIAL

    campos = {
        c["chave"]: c
        for s in CATALOGO_INICIAL if s["chave"] == "reciclagem-nr"
        for c in s["campos"]
    }
    assert campos["vencimento"]["tipo"] == TipoCampo.DATA
    for chave in ("tecnico_nome", "tecnico_documento", "tecnico_empresa",
                  "tecnico_responsavel"):
        assert campos[chave]["quando"]["igual"] == "terceiro", chave
        assert campos[chave]["obrigatorio"] is True, chave


def test_treinamento_tem_dois_cenarios():
    from workspace.catalogo_inicial import CATALOGO_INICIAL

    spec = next(s for s in CATALOGO_INICIAL if s["chave"] == "treinamento")
    campos = {c["chave"]: c for c in spec["campos"]}

    assert len(spec["passos"]) == 3
    assert campos["curso_interno"]["quando"]["igual"] == "interno"
    for chave in ("instituicao", "curso", "inicio", "periodo"):
        assert campos[chave]["quando"]["igual"] == "externo", chave
    # Curso interno não tem preço a informar.
    assert spec["valor_quando"] == {"campo": "origem", "igual": "externo"}


def test_rh_tem_vaga_interna_e_abertura_de_vaga():
    from workspace.catalogo_inicial import CATALOGO_INICIAL

    por_chave = {s["chave"]: s for s in CATALOGO_INICIAL}
    assert por_chave["vaga-interna"]["dominio"] == "rh.vaga"
    # Candidatura não passa pelo gestor: a cadeia normal faria o pedido de
    # mudar de área ser avaliado por quem perde a pessoa.
    assert por_chave["vaga-interna"]["limite_auto_aprovacao"] == Decimal("0")

    abertura = {c["chave"]: c for c in por_chave["abertura-vaga"]["campos"]}
    assert abertura["substituido"]["quando"]["igual"] == "reposicao"


def test_reembolso_virou_prestacao_de_contas_sem_perder_a_busca():
    """A tela também fecha adiantamento, e aí pode ser a PESSOA que devolve.
    Mas ninguém digita "prestação de contas": quem gastou escreve "reembolso"."""
    from workspace.catalogo_inicial import CATALOGO_INICIAL

    spec = next(s for s in CATALOGO_INICIAL if s["chave"] == "prestacao-contas")
    assert spec["nome"] == "Prestação de contas"
    assert "reembolso" in spec["termos"]
    assert [p.get("apos_envio", False) for p in spec["passos"]] == [False, False, True]
