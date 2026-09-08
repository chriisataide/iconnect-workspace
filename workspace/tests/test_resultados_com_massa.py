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
        f.papel(
            "dir",
            [
                "eco.ler.global", "eco.carga.global",
                # As duas telas irmãs, desde que saíram de dentro da 10.
                "eco.pessoas.global", "eco.satisfacao.global",
            ],
            escopo="global",
        ),
        escopo="global",
    )
    return pessoa


@pytest.fixture
def tela(client, diretoria_com_massa):
    client.force_login(diretoria_com_massa)
    return client.get(reverse("workspace:resultados"))


@pytest.fixture
def tela_do_quadro(client, diretoria_com_massa):
    """A 16 — quadro e jornada. Era a faixa 6 da tela 10 até 04/09/2026."""
    client.force_login(diretoria_com_massa)
    return client.get(reverse("workspace:quadro"))


@pytest.fixture
def tela_da_satisfacao(client, diretoria_com_massa):
    """A 17 — avaliação do cliente. Era a faixa 7."""
    client.force_login(diretoria_com_massa)
    return client.get(reverse("workspace:satisfacao"))


def test_as_seis_faixas_abrem_com_dado(tela, tela_do_quadro, tela_da_satisfacao):
    """Nenhuma diz "sem fonte conectada" e nenhuma some.

    Continuam sendo SEIS — quatro na tela 10 e uma em cada irmã. O teste passou
    a somar as três telas de propósito: se ele olhasse só a 10, a separação teria
    "consertado" a cobertura fazendo duas faixas deixarem de ser conferidas.
    """
    indisponiveis = {
        faixa.chave: faixa.motivo
        for resposta in (tela, tela_do_quadro, tela_da_satisfacao)
        for faixa in resposta.context["faixas"]
        if not faixa.disponivel
    }

    assert indisponiveis == {}

    vistas = {
        faixa.chave
        for resposta in (tela, tela_do_quadro, tela_da_satisfacao)
        for faixa in resposta.context["faixas"]
    }
    assert vistas == {
        "dinheiro", "contratos", "vencimentos", "projetos", "pessoas", "satisfacao",
    }


def test_cada_faixa_carimba_a_SUA_fonte(tela, tela_da_satisfacao):
    """É a razão de o carimbo ser por bloco e não por tela.

    Na tela 10 o dinheiro vem do Sankhya e os projetos vêm do monday. Um carimbo
    único no topo estaria certo sobre metade do conteúdo.

    A satisfação saiu para a 17 e continua carimbando o Platform: a separação
    mudou a tela, não a procedência — e o carimbo é justamente o que não pode
    mudar de significado quando a faixa muda de endereço.
    """
    por_chave = {faixa.chave: faixa.carimbo.fonte for faixa in tela.context["faixas"]}

    assert por_chave["dinheiro"] == "sankhya"
    assert por_chave["projetos"] == "monday"
    assert por_chave["contratos"] == "iconnect_platform"
    # TRÊS, e continuam três mesmo sem a satisfação: carteira e vencimentos
    # também vêm do Platform. Escrevi "duas" ao mexer aqui e o teste me corrigiu
    # — que é exatamente para isso que ele conta as fontes em vez de nomeá-las.
    assert len(set(por_chave.values())) == 3, "três fontes distintas na tela 10"

    irma = {f.chave: f.carimbo.fonte for f in tela_da_satisfacao.context["faixas"]}
    assert irma["satisfacao"] == "iconnect_platform"


def test_o_monday_aparece_em_alerta_e_as_outras_nao(tela):
    """O defeito 14 da massa, visto da tela.

    A faixa 5 continua com os números — ela mostra dado velho com a idade em
    destaque, e não some.
    """
    por_chave = {faixa.chave: faixa for faixa in tela.context["faixas"]}

    assert por_chave["projetos"].carimbo.alerta is True
    assert por_chave["projetos"].disponivel is True
    assert por_chave["dinheiro"].carimbo.alerta is False


def test_os_cartoes_saem_das_regras_e_nao_de_uma_lista(
    tela, tela_do_quadro, tela_da_satisfacao
):
    """Cada cartão corresponde a um defeito plantado.

    Se a massa deixar de ter deficitário, o cartão some — que é o comportamento
    certo. Painel que sempre mostra oito cartões ensina a ignorar os oito.
    """
    def chaves_de(resposta):
        return {c.chave for c in resposta.context["destaques"].conteudo["cartoes"]}

    chaves = chaves_de(tela)
    assert "fonte-monday" in chaves, "a fonte quebrada vem primeiro"
    assert "deficitarios" in chaves
    assert "abaixo-da-margem" in chaves
    assert "layer3-vencendo" in chaves
    assert "projetos-bloqueados" in chaves
    assert "marcos-vencidos" in chaves
    assert "sem-orcado" in chaves

    # OS CARTÕES SEGUIRAM AS FAIXAS. Um cartão de detrator numa tela que não
    # mostra a avaliação levaria a uma âncora que não existe — e o cartão é um
    # link para a faixa logo abaixo.
    assert "detrator-sem-tratativa" in chaves_de(tela_da_satisfacao)
    assert "turnover" in chaves_de(tela_do_quadro)
    assert "detrator-sem-tratativa" not in chaves
    assert "turnover" not in chaves


def test_a_fonte_quebrada_e_o_primeiro_cartao_da_lista(tela):
    cartoes = tela.context["destaques"].conteudo["cartoes"]

    assert cartoes[0].chave == "fonte-monday"


def test_a_faixa_de_pessoas_mostra_o_centro_que_destoa(tela_do_quadro):
    """A média esconderia: 8,4% num centro contra 2,1% nos outros vira 2,6%.

    O recorte por centro de custo é o único que mostra o número que pede ação.
    """
    pessoas = tela_do_quadro.context["por_chave"]["pessoas"]
    pior = pessoas.conteudo["por_centro"][0]

    assert pior.turnover_pct > 5
    assert pessoas.conteudo["quadro"].turnover_pct < 5, "o agregado é tranquilo"


def test_a_conformidade_do_ponto_tem_bloco_proprio(tela_do_quadro):
    """Folha pendente e contrato sem assinatura viram autuação — no meio da
    tabela de horas elas passam como mais uma linha."""
    conformidade = tela_do_quadro.context["por_chave"]["pessoas"].conteudo["conformidade"]

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


def test_a_tela_de_fontes_lista_todas_e_a_divergencia(client, diretoria_com_massa):
    """CINCO desde 08/09/2026 — o PNCP entrou.

    O número sai de `FonteDados`, e não de uma constante: a tela 99 existe para
    responder "de onde vem cada número", e uma fonte cadastrada que não
    aparecesse ali seria justamente a que ninguém audita.
    """
    from cargas.models import FonteDados

    client.force_login(diretoria_com_massa)

    resposta = client.get(reverse("workspace:fontes"))

    assert len(resposta.context["fontes"]) == FonteDados.objects.count()
    assert len(resposta.context["fontes"]) == 5
    assert resposta.context["divergencias"], "a massa planta uma"
    assert resposta.context["historico"], "as três cargas ficaram registradas"
