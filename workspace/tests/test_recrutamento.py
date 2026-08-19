"""§10 — as candidaturas, e a busca que ninguém constrói.

## Por que não existe um model `Candidatura`

A inscrição em vaga interna já é um pedido do catálogo (`rh.vaga`), com currículo
anexado, cadeia de aprovação, histórico e estado. Uma tabela paralela seria a
duplicação que o §1 proíbe — duas verdades sobre a mesma inscrição, e a que
diverge é sempre a que alguém esqueceu de atualizar.

O que faltava não era um modelo: era a **pergunta invertida**. O produto sabia
responder "quais pedidos a Ana fez" e não sabia responder "quem se candidatou a
esta vaga".

## A busca negativa

O §10 pede as duas. "Quem já se candidatou" é a fácil; **"quem NUNCA se
candidatou"** é a que responde pergunta real — quem da equipe nunca se moveu — e
sem ela a resposta vem de alguém varrendo a lista à mão e concluindo pela
ausência.
"""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.models.catalogo import (
    GrupoCatalogo,
    ItemCatalogo,
    SituacaoServico,
    TipoCampo,
)
from workspace.services import catalogo as svc
from workspace.services import recrutamento as rec
from workspace.services.recrutamento import RecrutamentoError

pytestmark = pytest.mark.django_db

PDF = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


@pytest.fixture
def cenario():
    rh, ana, bruno, carla = (f.pessoa(n) for n in ("rh", "ana", "bruno", "carla"))
    for pessoa in (rh, ana, bruno, carla):
        f.lotar(pessoa)
    f.atribuir(rh, f.papel("rh", ["rh.recrutar.global"], escopo="global"))
    item = ItemCatalogo.objects.create(
        chave="vaga-interna",
        nome="Inscrição em vaga interna",
        grupo=GrupoCatalogo.DESENVOLVIMENTO,
        dominio="rh.vaga",
        campos=[
            {"chave": "vaga", "rotulo": "Qual vaga", "tipo": TipoCampo.TEXTO,
             "obrigatorio": True},
            {"chave": "motivo", "rotulo": "Por que", "tipo": TipoCampo.TEXTO_LONGO},
            {"chave": "curriculo", "rotulo": "Currículo", "tipo": TipoCampo.ARQUIVO},
        ],
    )
    return {"rh": rh, "ana": ana, "bruno": bruno, "carla": carla, "item": item}


def inscrever(cenario, pessoa, vaga="Analista de Suporte", com_curriculo=False):
    arquivos = (
        {"curriculo": [SimpleUploadedFile("cv.pdf", PDF, content_type="application/pdf")]}
        if com_curriculo
        else None
    )
    return svc.solicitar(
        cenario["item"], pessoa, {"vaga": vaga, "motivo": "Quero crescer."},
        arquivos=arquivos,
    )


# ── A pergunta invertida ────────────────────────────────────────────


def test_quem_se_candidatou_a_esta_vaga(cenario):
    inscrever(cenario, cenario["ana"], vaga="Analista de Suporte")
    inscrever(cenario, cenario["bruno"], vaga="Técnico de Campo")

    linhas = rec.candidaturas(cenario["rh"], vaga="suporte")

    assert len(linhas) == 1
    assert linhas[0]["candidato"] == cenario["ana"]


def test_o_filtro_de_vaga_ignora_maiuscula_e_acento_do_digitado(cenario):
    """A vaga é texto livre no formulário. Gravar normalizado faria a tela
    mostrar "analista de suporte" onde a pessoa escreveu com maiúsculas."""
    inscrever(cenario, cenario["ana"], vaga="Analista de Suporte")

    assert len(rec.candidaturas(cenario["rh"], vaga="ANALISTA")) == 1
    assert rec.candidaturas(cenario["rh"], vaga="Analista de Suporte")[0]["vaga"] == (
        "Analista de Suporte"
    )


def test_a_que_vagas_esta_pessoa_ja_se_candidatou(cenario):
    inscrever(cenario, cenario["ana"], vaga="Analista")
    inscrever(cenario, cenario["ana"], vaga="Coordenador")
    inscrever(cenario, cenario["bruno"], vaga="Analista")

    linhas = rec.candidaturas(cenario["rh"], pessoa=cenario["ana"])

    assert {l["vaga"] for l in linhas} == {"Analista", "Coordenador"}


def test_o_curriculo_vem_junto(cenario):
    inscrever(cenario, cenario["ana"], com_curriculo=True)

    assert len(rec.candidaturas(cenario["rh"])[0]["curriculos"]) == 1


# ── O resultado sai da máquina de estados ───────────────────────────


def test_o_resultado_e_derivado_e_nao_um_campo_novo(cenario):
    """Um `status_candidatura` ao lado seria a segunda fonte de verdade sobre o
    mesmo fato, e a primeira a divergir."""
    pedido = inscrever(cenario, cenario["ana"])
    assert rec.candidaturas(cenario["rh"])[0]["resultado"] == "em_analise"

    pedido.situacao = SituacaoServico.CONCLUIDA
    pedido.save()
    assert rec.candidaturas(cenario["rh"])[0]["resultado"] == "aprovado"

    pedido.situacao = SituacaoServico.REJEITADA
    pedido.save()
    linha = rec.candidaturas(cenario["rh"])[0]
    assert linha["resultado"] == "reprovado"
    assert linha["rotulo"] == "Não seguiu"


def test_o_rascunho_nao_e_candidatura(cenario):
    """Formulário guardado pela metade não é inscrição — ninguém se candidatou."""
    svc.salvar_rascunho(cenario["item"], cenario["ana"], {"vaga": "Analista"})

    assert rec.candidaturas(cenario["rh"]) == []


# ── A busca negativa ────────────────────────────────────────────────


def test_quem_nunca_se_candidatou(cenario):
    """A metade que ninguém constrói, e a que responde pergunta real."""
    inscrever(cenario, cenario["ana"])

    nunca = list(rec.nunca_se_candidataram(cenario["rh"]))

    assert cenario["ana"] not in nunca
    assert cenario["bruno"] in nunca
    assert cenario["carla"] in nunca


def test_a_busca_negativa_so_olha_o_organograma(cenario):
    """A lista é o organograma, e não a tabela de contas: quem o R.H. ainda não
    lotou em lugar nenhum não é "quem nunca se candidatou", é quem ainda não
    entrou."""
    f.pessoa("avulso")

    nomes = {p.get_username() for p in rec.nunca_se_candidataram(cenario["rh"])}

    assert "avulso@icodev.com.br" not in nomes


def test_quem_se_candidatou_e_foi_reprovado_sai_da_lista_negativa(cenario):
    """Reprovado se candidatou — a pergunta é sobre movimento, não sobre
    sucesso."""
    pedido = inscrever(cenario, cenario["ana"])
    pedido.situacao = SituacaoServico.REJEITADA
    pedido.save()

    assert cenario["ana"] not in list(rec.nunca_se_candidataram(cenario["rh"]))


# ── Permissão ───────────────────────────────────────────────────────


def test_quem_nao_recruta_nao_ve_a_lista(cenario):
    """A lista diz quem se candidatou a quê e quem foi reprovado — informação
    que muda a relação de uma pessoa com o gestor dela."""
    with pytest.raises(RecrutamentoError, match="recrutamento"):
        rec.candidaturas(cenario["ana"])

    with pytest.raises(RecrutamentoError):
        rec.nunca_se_candidataram(cenario["ana"])


def test_a_permissao_nao_e_satisfeita_por_autoatendimento():
    """§48 — `rh.ler.proprio` está em AUTOATENDIMENTO, e usá-la aqui abriria a
    lista de candidaturas para a empresa inteira."""
    from identidade.papeis import AUTOATENDIMENTO

    proibidas = {p.rsplit(".", 1)[0] for p in AUTOATENDIMENTO if p.endswith(".proprio")}

    assert rec.PERMISSAO not in proibidas


# ── A tela ──────────────────────────────────────────────────────────


def test_quem_nao_recruta_leva_403(cenario, client):
    client.force_login(cenario["ana"])

    assert client.get(reverse("workspace:candidaturas")).status_code == 403


def test_a_tela_lista_e_conta(cenario, client):
    inscrever(cenario, cenario["ana"], vaga="Analista")
    inscrever(cenario, cenario["bruno"], vaga="Analista")
    client.force_login(cenario["rh"])

    resposta = client.get(reverse("workspace:candidaturas"))

    assert resposta.context["resumo"]["total"] == 2
    assert resposta.context["resumo"]["pessoas"] == 2
    assert "Analista" in resposta.content.decode()


def test_a_tela_filtra_por_pessoa(cenario, client):
    inscrever(cenario, cenario["ana"], vaga="Analista")
    inscrever(cenario, cenario["bruno"], vaga="Coordenador")
    client.force_login(cenario["rh"])

    resposta = client.get(
        reverse("workspace:candidaturas"), {"pessoa": cenario["ana"].pk}
    )

    assert len(resposta.context["linhas"]) == 1


def test_a_tela_ignora_pessoa_forjada(cenario, client):
    inscrever(cenario, cenario["ana"])
    client.force_login(cenario["rh"])

    resposta = client.get(reverse("workspace:candidaturas"), {"pessoa": "'; drop"})

    assert resposta.context["pessoa_atual"] is None
    assert len(resposta.context["linhas"]) == 1


def test_a_tela_mostra_quem_nunca_se_candidatou(cenario, client):
    inscrever(cenario, cenario["ana"])
    client.force_login(cenario["rh"])

    resposta = client.get(reverse("workspace:candidaturas"))

    assert cenario["bruno"] in resposta.context["nunca"]
    assert "nunca se candidataram a nada" in resposta.content.decode()
