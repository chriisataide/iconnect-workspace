"""O posicionamento, verificado onde ele é visível.

Decidido em 12/08/2026: **são dois produtos.** O iConnect Workspace organiza a
vida corporativa da empresa; o iConnect Platform organiza a operação de
atendimento aos clientes.

Posicionamento não é slide — ou está na ordem das faixas e no tratamento visual
dos tiles, ou não existe. Antes desta data a home abria por "Aplicativos" com o
iConnect como tile herói: a primeira coisa que o colaborador via era a lista de
sistemas, e o próprio trabalho vinha depois. Isso é um app launcher.

Estes testes existem porque a regressão é silenciosa: alguém acrescenta uma
faixa, ela cai no lugar errado, e o produto volta a ser launcher sem que nenhuma
tela quebre.
"""

from __future__ import annotations

import re

import pytest
from django.urls import reverse

from workspace.launcher import catalogo_semente

pytestmark = pytest.mark.django_db


# ── A ordem das faixas ──────────────────────────────────────────────


def _posicoes(corpo: str) -> dict[str, int]:
    """Onde cada faixa começa no HTML."""
    faixas = ("Meu dia", "Minha empresa", "Aplicativos")
    return {
        faixa: corpo.index(f'class="au-secao-titulo">{faixa}')
        for faixa in faixas
        if f'class="au-secao-titulo">{faixa}' in corpo
    }


def test_meu_dia_vem_antes_dos_aplicativos(client):
    """Primeiro o usuário, depois os sistemas."""
    corpo = client.get(reverse("workspace:home")).content.decode()
    pos = _posicoes(corpo)

    assert set(pos) == {"Meu dia", "Minha empresa", "Aplicativos"}, (
        f"faixa faltando ou renomeada: {sorted(pos)}"
    )
    assert pos["Meu dia"] < pos["Minha empresa"] < pos["Aplicativos"], (
        "a home voltou a abrir por sistemas — é o desenho de app launcher"
    )


def test_aplicativos_e_a_ultima_faixa(client):
    """Abrir outro sistema é o que a pessoa faz quando o Workspace não
    resolveu, não o objetivo dela ao entrar."""
    corpo = client.get(reverse("workspace:home")).content.decode()
    titulos = re.findall(r'class="au-secao-titulo">([^<]+)', corpo)

    assert titulos[-1] == "Aplicativos"


# ── O iConnect é um tile entre outros ───────────────────────────────


def test_iconnect_nao_tem_destaque():
    """Sem borda de marca, sem primeira posição.

    `destaque` pinta o tile com a cor da marca e o põe em evidência. Usá-lo no
    iConnect dizia que o Workspace existe para levar até lá.
    """
    iconnect = next(s for s in catalogo_semente() if s.chave == "iconnect")

    assert not iconnect.destaque, "o iConnect voltou a ser o tile herói da home"


def test_iconnect_se_chama_platform():
    iconnect = next(s for s in catalogo_semente() if s.chave == "iconnect")

    assert iconnect.nome == "iConnect Platform"
    assert "principal" not in iconnect.descricao.lower(), (
        "'sistema principal' descreve a relação antiga — são dois produtos"
    )


def test_nenhum_tile_de_aplicativo_tem_destaque():
    """A faixa inteira é plana. Um tile em destaque entre dez cria hierarquia
    que a nova posição não sustenta."""
    com_destaque = [s.chave for s in catalogo_semente() if s.destaque]

    assert not com_destaque, f"tiles em destaque: {com_destaque}"


def test_ordem_coloca_a_platform_no_fim():
    """A Platform é um destino entre outros, e fica no fim da faixa.

    Eram duas entradas — `iconnect` e `helpdesk`. O tile do HelpDesk saiu no
    §38: ele levava para fora e não fazia mais nada, enquanto
    `/workspace/chamados/` direciona, integra e mostra status e histórico.
    """
    ordens = {s.chave: s.ordem for s in catalogo_semente()}
    maior_modulo = max(v for k, v in ordens.items() if k != "iconnect")

    assert ordens["iconnect"] > maior_modulo


# ── O nome do produto ───────────────────────────────────────────────
#
# Em 12/08/2026 o produto deixou de se chamar "Portal" e virou "iConnect
# Workspace", e havia aqui um teste proibindo a palavra "Portal" em qualquer
# tela. Em 04/09/2026 ele voltou a ser Portal — **Portal ADB360** — por decisão
# do dono do produto, e aquele teste passou a guardar uma decisão revogada.
#
# O que ficou no lugar dele é mais durável que qualquer um dos dois nomes: o
# nome vive em `settings.PRODUTO_NOME`, e nenhum template o escreve à mão. Um
# terceiro rebatismo é uma linha, e não outra varredura.


def test_a_casca_usa_o_nome_do_produto(client, settings):
    corpo = client.get(reverse("workspace:home")).content.decode()

    assert f'class="au-brand-produto">{settings.PRODUTO_NOME}<' in corpo


def test_titulo_da_aba_tem_o_produto_como_sufixo(client, settings):
    corpo = client.get(reverse("workspace:home")).content.decode()

    assert f"<title>Início · {settings.PRODUTO_NOME}</title>" in corpo


def test_trocar_o_nome_no_settings_troca_a_tela_inteira(client, settings):
    """O teste que guarda a fonte única.

    Se alguém escrever "Portal ADB360" à mão num template novo, este teste passa
    — mas o dia do próximo rebatismo esse template fica para trás, e ninguém
    percebe até um usuário reparar. Trocar o valor e conferir que NADA sobrou do
    anterior é a única forma de provar que a fonte é mesmo única.
    """
    settings.PRODUTO_NOME = "Nome Inventado Para O Teste"

    rotas = [
        reverse("workspace:home"),
        reverse("workspace:modulo", args=("rh",)),
        reverse("workspace:servicos"),
        # As telas de estado vazio mandam a pessoa para o `/admin/` PELO NOME,
        # e são as que menos gente abre — o nome antigo sobreviveria aqui.
        reverse("workspace:reservas"),
    ]
    for rota in rotas:
        corpo = client.get(rota).content.decode()
        assert "Nome Inventado Para O Teste" in corpo, f"{rota} não usa o settings"
        assert "Portal ADB360" not in corpo, f"{rota} escreve o nome à mão"
        assert "iConnect Workspace" not in corpo, f"{rota} ficou com o nome antigo"


def test_nenhum_template_escreve_o_nome_a_mao():
    """A varredura que a rota não alcança.

    O teste acima só vê as telas que ele visita, e uma delas depende de estado
    vazio para renderizar. Este lê os arquivos: qualquer template com o nome
    literal é o próximo a ficar para trás."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent / "templates"
    # Sem os `{% comment %}`: eles não chegam ao usuário, e um comentário que
    # EXPLICA por que o nome não é escrito à mão não pode reprovar por citá-lo.
    sem_comentario = re.compile(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", re.S)
    sujos = [
        str(arquivo.relative_to(raiz))
        for arquivo in raiz.rglob("*.html")
        for texto in [sem_comentario.sub("", arquivo.read_text(encoding="utf-8"))]
        if "iConnect Workspace" in texto or "Portal ADB360" in texto
    ]

    assert not sujos, f"escrevem o nome à mão em vez de {{% produto %}}: {sujos}"


def test_o_alt_do_logo_e_a_empresa_e_nao_o_produto(client, settings):
    """"Portal ADB360" já está escrito ao lado, em texto. Repetir no `alt`
    faria o leitor de tela dizer o nome duas vezes e não dizer de quem é o
    portal — que é a única coisa que a imagem acrescenta."""
    corpo = client.get(reverse("workspace:home")).content.decode()

    assert f'alt="{settings.PRODUTO_MARCA}"' in corpo
    assert settings.PRODUTO_MARCA != settings.PRODUTO_NOME


# ── A marca ─────────────────────────────────────────────────────────
#
# Logo quebrado NÃO derruba tela nenhuma: o navegador desenha o ícone de imagem
# faltando e segue. É o tipo de defeito que sobrevive a um deploy inteiro,
# porque quem testa olha o conteúdo e o alto da página vira paisagem.


def _referencias_de_imagem(corpo: str) -> list[str]:
    return re.findall(r'(?:src|href)="/static/(workspace/img/[^"]+)"', corpo)


@pytest.mark.parametrize("rota", ["/workspace/", "/entrar/"])
def test_toda_imagem_da_marca_existe_no_disco(client, rota):
    from pathlib import Path

    estaticos = Path(__file__).resolve().parent.parent / "static"
    corpo = client.get(rota).content.decode()

    referencias = _referencias_de_imagem(corpo)
    assert referencias, f"{rota} não referencia imagem nenhuma da marca"
    for caminho in referencias:
        assert (estaticos / caminho).exists(), f"{rota} aponta para {caminho}, que não existe"


@pytest.mark.parametrize("rota", ["/workspace/", "/entrar/"])
def test_nenhuma_tela_ainda_carrega_a_marca_antiga(client, rota):
    """Os arquivos da iCODEV continuam no repositório — apagar marca é decisão
    de quem a possui, não faxina. Mas nenhuma tela pode mais carregá-los."""
    corpo = client.get(rota).content.decode()

    for caminho in _referencias_de_imagem(corpo):
        assert "icodev" not in caminho, f"{rota} ainda carrega {caminho}"


def test_o_favicon_e_quadrado(client):
    """O original da ADB é 240×189. Favicon é desenhado numa caixa quadrada, e
    quem não quadra o arquivo deixa o navegador decidir — uns esticam, outros
    recortam, e a águia sai deformada em metade deles."""
    from pathlib import Path

    from PIL import Image

    img = Path(__file__).resolve().parent.parent / "static/workspace/img"
    for nome in ("adb-512.png", "adb-apple-touch.png", "favicon-adb.ico"):
        largura, altura = Image.open(img / nome).size
        assert largura == altura, f"{nome} é {largura}×{altura}, e devia ser quadrado"


def test_o_apple_touch_nao_tem_transparencia():
    """O iOS pinta o alfa de PRETO. A águia é vermelha, e vermelho sobre preto
    é o contraste mais fraco que existe entre cores saturadas."""
    from pathlib import Path

    from PIL import Image

    caminho = (
        Path(__file__).resolve().parent.parent
        / "static/workspace/img/adb-apple-touch.png"
    )

    assert Image.open(caminho).mode == "RGB", "o apple-touch precisa ser opaco"
