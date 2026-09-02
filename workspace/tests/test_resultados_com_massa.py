"""A tela inteira, com a massa de verdade.

Os outros arquivos testam pedaço: um escopo, uma regra, um carimbo. Este monta o
banco pela semeadora — que entra pelo carregador, como qualquer carga — e abre a
tela como a diretoria abriria.

É o teste que responde à pergunta que a onda existe para responder: **a diretoria
abre a tela sozinha e encontra o que precisa?**
"""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.urls import reverse

from identidade.tests import fabricas as f

pytestmark = pytest.mark.django_db


@pytest.fixture
def diretoria_com_massa(db):
    call_command("semear_fontes", "--aplicar", verbosity=0)
    call_command("semear_resultados", "--aplicar", verbosity=0)
    pessoa = f.pessoa("diretoria", nome="Diretoria")
    f.lotar(pessoa)
    f.atribuir(
        pessoa,
        f.papel("dir", ["eco.ler.global", "eco.carga.global"], escopo="global"),
        escopo="global",
    )
    return pessoa


@pytest.fixture
def tela(client, diretoria_com_massa):
    client.force_login(diretoria_com_massa)
    return client.get(reverse("workspace:resultados"))


def test_as_seis_faixas_abrem_com_dado(tela):
    """Nenhuma diz "sem fonte conectada" e nenhuma some.

    Com a massa carregada pelas três fontes, todas têm o que mostrar — e se uma
    não tiver, o motivo dela vem no `assert`.
    """
    indisponiveis = {
        faixa.chave: faixa.motivo for faixa in tela.context["faixas"] if not faixa.disponivel
    }

    assert indisponiveis == {}


def test_cada_faixa_carimba_a_SUA_fonte(tela):
    """É a razão de o carimbo ser por bloco e não por tela.

    Nesta mesma página o dinheiro vem do Sankhya e os projetos vêm do monday. Um
    carimbo único no topo estaria certo sobre metade do conteúdo.
    """
    por_chave = {faixa.chave: faixa.carimbo.fonte for faixa in tela.context["faixas"]}

    assert por_chave["dinheiro"] == "sankhya"
    assert por_chave["projetos"] == "monday"
    assert por_chave["satisfacao"] == "iconnect_platform"
    assert len(set(por_chave.values())) == 3, "três fontes distintas na mesma tela"


def test_o_monday_aparece_em_alerta_e_as_outras_nao(tela):
    """O defeito 14 da massa, visto da tela.

    A faixa 5 continua com os números — ela mostra dado velho com a idade em
    destaque, e não some.
    """
    por_chave = {faixa.chave: faixa for faixa in tela.context["faixas"]}

    assert por_chave["projetos"].carimbo.alerta is True
    assert por_chave["projetos"].disponivel is True
    assert por_chave["dinheiro"].carimbo.alerta is False


def test_os_cartoes_saem_das_regras_e_nao_de_uma_lista(tela):
    """Cada cartão corresponde a um defeito plantado.

    Se a massa deixar de ter deficitário, o cartão some — que é o comportamento
    certo. Painel que sempre mostra oito cartões ensina a ignorar os oito.
    """
    chaves = {c.chave for c in tela.context["destaques"].conteudo["cartoes"]}

    assert "fonte-monday" in chaves, "a fonte quebrada vem primeiro"
    assert "deficitarios" in chaves
    assert "abaixo-da-margem" in chaves
    assert "layer3-vencendo" in chaves
    assert "projetos-bloqueados" in chaves
    assert "marcos-vencidos" in chaves
    assert "detrator-sem-tratativa" in chaves
    assert "sem-orcado" in chaves
    assert "turnover" in chaves


def test_a_fonte_quebrada_e_o_primeiro_cartao_da_lista(tela):
    cartoes = tela.context["destaques"].conteudo["cartoes"]

    assert cartoes[0].chave == "fonte-monday"


def test_a_faixa_de_pessoas_mostra_o_centro_que_destoa(tela):
    """A média esconderia: 8,4% num centro contra 2,1% nos outros vira 2,6%.

    O recorte por centro de custo é o único que mostra o número que pede ação.
    """
    pessoas = tela.context["por_chave"]["pessoas"]
    pior = pessoas.conteudo["por_centro"][0]

    assert pior.turnover_pct > 5
    assert pessoas.conteudo["quadro"].turnover_pct < 5, "o agregado é tranquilo"


def test_a_conformidade_do_ponto_tem_bloco_proprio(tela):
    """Folha pendente e contrato sem assinatura viram autuação — no meio da
    tabela de horas elas passam como mais uma linha."""
    conformidade = tela.context["por_chave"]["pessoas"].conteudo["conformidade"]

    assert conformidade["folhas_pendentes"] == 14
    assert conformidade["contratos_pendentes"] == 3


def test_as_faixas_de_vencimento_nao_repetem_contrato(tela):
    """Cumulativas: um contrato de 45 dias aparece em "60" e não em "30".

    Repeti-lo faria a soma das faixas não bater com a carteira, e alguém
    contaria duas vezes na reunião.
    """
    blocos = tela.context["por_chave"]["vencimentos"].conteudo["blocos"]
    codigos = [c.codigo for bloco in blocos for c in bloco["contratos"]]

    assert len(codigos) == len(set(codigos))


def test_a_linha_sem_orcado_aparece_como_traco_e_nao_como_estouro(tela):
    """Ela parece estouro de orçamento e não é: é código de centro de custo que
    existe de um lado e não do outro."""
    linhas = tela.context["por_chave"]["dinheiro"].conteudo["linhas"]
    orfas = [l for l in linhas if l["orcado"] is None]

    assert orfas, "a massa planta uma"
    assert all(l["percentual"] is None and l["diferenca"] is None for l in orfas)


def test_toda_linha_do_dinheiro_diz_de_onde_veio(tela):
    """Espelho sem procedência é boato com aparência de relatório."""
    linhas = tela.context["por_chave"]["dinheiro"].conteudo["linhas"]

    assert linhas
    assert all(l["procedencia"].chave_externa for l in linhas)


def test_o_pdf_da_competencia_sai_com_as_faixas(client, diretoria_com_massa):
    client.force_login(diretoria_com_massa)

    resposta = client.get(reverse("workspace:resultados_pdf"))

    assert resposta.status_code == 200
    assert resposta.content[:4] == b"%PDF"
    assert len(resposta.content) > 3000, "um PDF de uma página só seria a capa"


def test_o_modo_apresentacao_mostra_os_mesmos_numeros(client, diretoria_com_massa):
    """A MESMA tela, e não uma segunda.

    Duas telas divergiriam na terceira semana — e a que a diretoria vê na
    reunião é justamente a que não pode divergir.
    """
    client.force_login(diretoria_com_massa)

    normal = client.get(reverse("workspace:resultados"))
    reuniao = client.get(reverse("workspace:resultados"), {"apresentacao": "1"})

    def _totais(resposta):
        return resposta.context["por_chave"]["dinheiro"].conteudo["totais"]

    assert _totais(normal) == _totais(reuniao)


def test_a_tela_de_fontes_lista_as_quatro_e_a_divergencia(client, diretoria_com_massa):
    client.force_login(diretoria_com_massa)

    resposta = client.get(reverse("workspace:fontes"))

    assert len(resposta.context["fontes"]) == 4
    assert resposta.context["divergencias"], "a massa planta uma"
    assert resposta.context["historico"], "as três cargas ficaram registradas"
