"""A SOLEIRA — a tela de identificar-se, e o que ela não pode carregar.

O defeito que deu origem a estes testes era visível numa captura de tela: a
topbar do Workspace ganhou um botão "Entrar", e ele passou a aparecer **dentro
da própria tela de entrar**. Botão que leva à página onde você já está faz a
pessoa duvidar se clicou.

O botão foi o sintoma. A causa é que esta tela estendia a casca do Workspace,
que é escrita para quem já está dentro: busca ⌘K, rodapé, trilho, nome de quem
está logado. Aqui ninguém está dentro ainda.

O que estes testes protegem:

1. **Nenhum pedaço da casca do produto** entra nesta tela.
2. **A tela continua funcionando** — entrar, errar a senha, voltar ao hub.
3. **O botão de enviar usa o botão do produto**, e não o token de "deu certo".
   Ele já foi verde: `--au-success` significa "operação concluída", e a marca
   da icodev é navy e crimson — verde não vinha de lugar nenhum.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.urls import reverse

from contas.models import Pessoa

SENHA = "senha-correta-12345"

pytestmark = pytest.mark.django_db


@pytest.fixture
def pessoa():
    return Pessoa.objects.create_user("ana@icodev.com.br", password=SENHA)


@pytest.fixture
def pagina(client):
    return client.get(reverse("entrar")).content.decode()


# ── A casca do produto não entra aqui ───────────────────────────────


def test_a_tela_de_entrar_nao_tem_botao_de_entrar(pagina):
    """O defeito da captura de tela: botão que leva à página onde você está."""
    assert "au-topbar" not in pagina


@pytest.mark.parametrize(
    "pedaco, por_que",
    [
        ("au-topbar", "a topbar traz busca, sino e o botão Entrar"),
        ("au-rodape", "o rodapé é do produto, não da soleira"),
        ("au-paleta", "⌘K busca no Workspace — não há Workspace aqui ainda"),
        ("au-rail", "o trilho é navegação de quem já está dentro"),
    ],
)
def test_nenhum_pedaco_da_casca_do_workspace(pagina, pedaco, por_que):
    assert pedaco not in pagina, por_que


def test_a_marca_continua(pagina):
    """Tirar a casca não pode significar tirar a identidade visual."""
    assert "au-porta-marca" in pagina
    assert "icodev" in pagina


# ── O desenho ───────────────────────────────────────────────────────


def test_o_botao_usa_o_primario_do_produto(pagina):
    """Ele já foi verde, com `--au-success` — o token de "deu certo" dizendo
    "enviar". A marca é navy e crimson; verde não vinha de lugar nenhum."""
    assert "au-btn--primario" in pagina
    assert "au-entrar-enviar" not in pagina, "a classe do botão verde saiu"


def test_o_painel_explica_por_que_a_senha_e_pedida(pagina):
    """Quem foi parado aqui não veio navegando: veio tentar um ato que assina
    em nome de alguém. A tela responde isso, em vez de decorar."""
    assert "O que exige o seu nome" in pagina


def test_toda_classe_au_da_tela_existe_no_css(pagina):
    """Esta tela já foi ao ar usando cinco classes que não existiam no CSS, e
    o resultado foi um formulário sem estilo nenhum."""
    css = Path("workspace/static/workspace/src/workspace.css").read_text()
    usadas = {
        classe
        for grupo in re.findall(r'class="([^"]+)"', pagina)
        for classe in grupo.split()
        if classe.startswith("au-")
    }

    sem_css = sorted(c for c in usadas if f".{c}" not in css)
    assert not sem_css, f"classes sem CSS: {sem_css}"


def test_o_css_da_soleira_nao_esta_duplicado():
    """Havia DUAS versões das regras de login no arquivo, uma sobrescrevendo a
    outra — e a que ganhava era a antiga, por vir depois. Junto delas viajava
    uma cópia byte a byte do bloco do Stepper."""
    css = Path("workspace/static/workspace/src/workspace.css").read_text()

    assert css.count("A SOLEIRA") == 1
    assert css.count("── Stepper: trilha e passos") == 1
    assert ".au-entrar" not in css, "sobrou regra do desenho antigo"


# ── E continua sendo um login ───────────────────────────────────────


def test_entrar_de_verdade(client, pessoa):
    resposta = client.post(
        reverse("entrar"), {"username": pessoa.email, "password": SENHA}
    )

    assert resposta.status_code == 302
    assert "_auth_user_id" in client.session


def test_senha_errada_avisa_sem_dizer_qual_campo(client, pessoa):
    """"Este e-mail não existe" transforma a tela num verificador de quem
    trabalha aqui."""
    corpo = client.post(
        reverse("entrar"), {"username": pessoa.email, "password": "errada"}
    ).content.decode()

    assert "não conferem" in corpo
    assert "não existe" not in corpo


def test_da_para_voltar_ao_workspace_sem_entrar(pagina):
    """O hub é aberto. Quem caiu aqui por engano não pode ficar preso."""
    assert reverse("workspace:home") in pagina
