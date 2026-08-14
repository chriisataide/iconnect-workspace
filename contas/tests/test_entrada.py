"""O freio de tentativas em `/entrar/`.

A tela de identificação voltou a existir sem limite nenhum: senha ilimitada,
contra contas reais, num formulário aberto na rede da empresa. Estes testes
protegem as quatro decisões do freio, e uma delas é a ausência de uma regra:

1. cinco erros na mesma conta, da mesma origem, e ela para de tentar;
2. vinte erros da mesma origem, em contas diferentes, e a origem para;
3. **não existe contagem por e-mail sozinho** — ela permitiria trancar qualquer
   pessoa da empresa de fora do produto de propósito;
4. acertar a senha limpa a contagem da conta, mas não a da origem.
"""

from __future__ import annotations

import pytest
from django.core.cache import cache
from django.urls import reverse

from contas.entrada import LIMITE_POR_CONTA
from contas.models import Pessoa

SENHA = "senha-correta-12345"
ERRADA = "senha-errada"


@pytest.fixture(autouse=True)
def cache_limpo():
    """Contador vive em cache, e cache vaza entre testes: sem isto, o segundo
    teste herdaria as tentativas do primeiro e falharia sozinho."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def pessoa(db):
    return Pessoa.objects.create_user("ana@icodev.com.br", nome="Ana", password=SENHA)


def tentar(client, email, senha=ERRADA, ip="10.0.0.1"):
    return client.post(
        reverse("entrar"),
        {"username": email, "password": senha},
        REMOTE_ADDR=ip,
    )


# ── O que o freio impede ────────────────────────────────────────────


@pytest.mark.django_db
def test_erra_demais_na_mesma_conta_e_para(client, pessoa):
    for _ in range(LIMITE_POR_CONTA):
        assert tentar(client, pessoa.email).status_code == 200

    bloqueada = tentar(client, pessoa.email)
    assert bloqueada.status_code == 429
    assert "aguarde alguns minutos" in bloqueada.content.decode()


@pytest.mark.django_db
def test_bloqueado_nao_chega_a_testar_a_senha(client, pessoa):
    """Sem isto, cada tentativa a mais ainda custaria uma verificação de hash —
    que é lenta de propósito — e o freio viraria um jeito de gastar CPU."""
    for _ in range(LIMITE_POR_CONTA):
        tentar(client, pessoa.email)

    # A senha CERTA, já bloqueado: continua barrado, e sem sessão.
    resposta = tentar(client, pessoa.email, senha=SENHA)
    assert resposta.status_code == 429
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_varredura_de_contas_da_mesma_origem_para(client, pessoa, settings):
    """Muitas contas, uma origem: é a varredura, e a contagem por e-mail não
    pega, porque cada e-mail erra uma vez só."""
    settings.LOGIN_LIMITE_POR_ORIGEM = 4

    for numero in range(4):
        assert tentar(client, f"pessoa{numero}@icodev.com.br").status_code == 200

    assert tentar(client, "outra@icodev.com.br").status_code == 429


# ── O que o freio NÃO faz, e é decisão ──────────────────────────────


@pytest.mark.django_db
def test_ninguem_tranca_outra_pessoa_de_fora(client, pessoa):
    """A regra que NÃO existe, e é a mais importante do arquivo.

    Se houvesse contagem por e-mail sozinho, cinco tentativas erradas contra o
    e-mail de alguém trancariam essa pessoa para fora do produto. Bloqueio que
    se vira contra a vítima é pior que o ataque que ele evita.
    """
    for _ in range(LIMITE_POR_CONTA * 3):
        tentar(client, pessoa.email, ip="203.0.113.7")

    # A vítima, do lugar dela, entra normalmente.
    resposta = tentar(client, pessoa.email, senha=SENHA, ip="10.0.0.9")
    assert resposta.status_code == 302
    assert "_auth_user_id" in client.session


@pytest.mark.django_db
def test_acertar_a_senha_limpa_a_conta_mas_nao_a_origem(client, pessoa, settings):
    settings.LOGIN_LIMITE_POR_ORIGEM = 6

    for _ in range(3):
        tentar(client, pessoa.email)
    assert tentar(client, pessoa.email, senha=SENHA).status_code == 302

    client.logout()
    # A conta zerou: erra três vezes de novo sem bater no limite de 5.
    for _ in range(3):
        assert tentar(client, pessoa.email).status_code == 200

    # A origem não zerou — as 6 falhas dela contam, e a sétima para.
    assert tentar(client, "outra@icodev.com.br").status_code == 429


@pytest.mark.django_db
def test_a_mensagem_nao_diz_se_a_conta_existe(client, pessoa):
    """Nem no erro comum, nem no bloqueio: a tela não pode virar um verificador
    de quem trabalha na empresa."""
    de_quem_existe = tentar(client, pessoa.email).content.decode()
    de_quem_nao_existe = tentar(client, "ninguem@icodev.com.br").content.decode()

    assert "E-mail ou senha não conferem." in de_quem_existe
    assert "E-mail ou senha não conferem." in de_quem_nao_existe
    for texto in ("não existe", "não encontrada", "conta inválida"):
        assert texto not in de_quem_existe.lower()


@pytest.mark.django_db
def test_maiuscula_no_email_nao_ganha_tentativas_de_graca(client, pessoa):
    """`Ana@…` e `ana@…` são a mesma conta; contar separado daria o dobro."""
    for _ in range(LIMITE_POR_CONTA):
        tentar(client, pessoa.email.upper())

    assert tentar(client, pessoa.email).status_code == 429


@pytest.mark.django_db
def test_a_porta_continua_aberta_para_quem_acerta(client, pessoa):
    """O freio não pode ser o defeito: quem sabe a senha entra."""
    resposta = tentar(client, pessoa.email, senha=SENHA)

    assert resposta.status_code == 302
    assert "_auth_user_id" in client.session
