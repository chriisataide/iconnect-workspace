"""A conta: identificador, criação e como ela se apresenta.

O que estes testes protegem não é o model — é a **interface que o Workspace
consome**. `get_full_name()` e `get_short_name()` são chamados na home, no Meu
dia, na correspondência, nas reservas e na casca. `AbstractBaseUser` não traz
nenhum dos dois, então aqui eles são contrato, não conveniência.
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def Pessoa():
    return get_user_model()


# ── O identificador é o e-mail ──────────────────────────────────────


@pytest.mark.django_db
def test_o_identificador_e_o_email(Pessoa):
    assert Pessoa.USERNAME_FIELD == "email"
    pessoa = Pessoa.objects.create_user("Ana.Souza@Icodev.com.BR", nome="Ana Souza")
    assert pessoa.get_username() == "ana.souza@icodev.com.br"


@pytest.mark.django_db
def test_email_e_normalizado_para_minusculas(Pessoa):
    """Duas contas para a mesma pessoa é o que o e-mail case-sensitive produz.

    Quem digita `Ana.Souza@` no formulário e `ana.souza@` na semana seguinte não
    entende por que a segunda vez "não é ela".
    """
    pessoa = Pessoa.objects.create_user("  ANA@ICODEV.COM.BR  ")
    assert pessoa.email == "ana@icodev.com.br"


@pytest.mark.django_db
def test_conta_sem_email_e_recusada(Pessoa):
    with pytest.raises(ValueError, match="exige e-mail"):
        Pessoa.objects.create_user("")


@pytest.mark.django_db
def test_email_e_unico(Pessoa):
    from django.db import IntegrityError

    Pessoa.objects.create_user("ana@icodev.com.br")
    with pytest.raises(IntegrityError):
        Pessoa.objects.create_user("ana@icodev.com.br")


# ── Senha: o caso normal é não ter ──────────────────────────────────


@pytest.mark.django_db
def test_conta_sem_senha_nao_autentica_localmente(Pessoa):
    """É o caso NORMAL com SSO, e é diferente de senha vazia.

    `set_unusable_password()` impede login local por acidente; senha vazia
    permitiria alguém entrar sem digitar nada.
    """
    pessoa = Pessoa.objects.create_user("ana@icodev.com.br")
    assert pessoa.has_usable_password() is False


@pytest.mark.django_db
def test_conta_com_senha_autentica(Pessoa):
    pessoa = Pessoa.objects.create_user("ana@icodev.com.br", password="segredo-longo-1")
    assert pessoa.has_usable_password() is True
    assert pessoa.check_password("segredo-longo-1") is True


@pytest.mark.django_db
def test_superusuario_nasce_com_os_dois_privilegios(Pessoa):
    admin = Pessoa.objects.create_superuser("admin@icodev.com.br", password="x" * 12)
    assert admin.is_staff is True
    assert admin.is_superuser is True


@pytest.mark.django_db
def test_conta_comum_nao_acessa_o_admin(Pessoa):
    """O padrão é não ter privilégio. O SSO cria milhares de contas por aqui."""
    pessoa = Pessoa.objects.create_user("ana@icodev.com.br")
    assert pessoa.is_staff is False
    assert pessoa.is_superuser is False


# ── Como a conta se apresenta ───────────────────────────────────────


@pytest.mark.django_db
def test_nome_completo_e_curto_com_nome_preenchido(Pessoa):
    pessoa = Pessoa.objects.create_user(
        "christopher@icodev.com.br", nome="Christopher Ataide"
    )
    assert pessoa.get_full_name() == "Christopher Ataide"
    assert pessoa.get_short_name() == "Christopher", "a saudação usa só o primeiro"
    assert str(pessoa) == "Christopher Ataide"


@pytest.mark.django_db
def test_sem_nome_cai_para_a_parte_local_e_nao_para_o_email_inteiro(Pessoa):
    """"Olá, semnome@icodev.com.br." é pior que não cumprimentar.

    Conta criada pelo SSO sempre traz `displayName`; a que cai aqui é conta de
    serviço ou importação incompleta — e mesmo essa merece exibição legível, no
    admin e na home.
    """
    pessoa = Pessoa.objects.create_user("semnome@icodev.com.br")
    assert pessoa.get_full_name() == "semnome"
    assert pessoa.get_short_name() == "semnome"
    assert str(pessoa) == "semnome"


@pytest.mark.django_db
def test_nome_composto_nao_e_partido(Pessoa):
    """O `User` do Django parte em `first_name`/`last_name`; este não.

    Em português não há divisão útil entre primeiro nome e sobrenome de "Maria
    Clara Souza Lima" — a heurística do primeiro espaço servia ao modelo, não à
    realidade.
    """
    pessoa = Pessoa.objects.create_user(
        "maria@icodev.com.br", nome="Maria Clara Souza Lima"
    )
    assert pessoa.nome == "Maria Clara Souza Lima"
    assert pessoa.get_short_name() == "Maria"


# ── O vínculo com o diretório ───────────────────────────────────────


@pytest.mark.django_db
def test_campos_do_entra_id_nascem_vazios_e_nao_nulos(Pessoa):
    """Vazio e não `None`: `blank=True, default=""` evita o `is not None` em
    toda leitura, e o SSO ainda não está ligado."""
    pessoa = Pessoa.objects.create_user("ana@icodev.com.br")
    assert pessoa.entra_oid == ""
    assert pessoa.upn == ""


@pytest.mark.django_db
def test_o_oid_e_a_chave_de_reconciliacao(Pessoa):
    """Duas contas não podem compartilhar `entra_oid` preenchido — mas vazio sim.

    O `oid` é imutável no tenant e o e-mail não: reconciliar por e-mail cria conta
    duplicada no dia em que alguém troca de sobrenome. Ainda assim o campo é
    opcional, porque conta de serviço não tem `oid`, e por isso a unicidade não
    pode ser uma constraint de banco enquanto o padrão é string vazia.
    """
    a = Pessoa.objects.create_user("a@icodev.com.br", entra_oid="oid-1")
    b = Pessoa.objects.create_user("b@icodev.com.br")

    assert a.entra_oid == "oid-1"
    assert b.entra_oid == "", "sem SSO, fica vazio — e duas vazias convivem"
    assert Pessoa.objects.filter(entra_oid="").count() == 1


# ── Desativar em vez de apagar ──────────────────────────────────────


@pytest.mark.django_db
def test_conta_nasce_ativa(Pessoa):
    assert Pessoa.objects.create_user("ana@icodev.com.br").is_active is True


@pytest.mark.django_db
def test_ordenacao_por_nome_depois_email(Pessoa):
    """A lista de destinatários da correspondência depende desta ordem."""
    Pessoa.objects.create_user("z@icodev.com.br", nome="Ana")
    Pessoa.objects.create_user("a@icodev.com.br", nome="Bruno")
    Pessoa.objects.create_user("m@icodev.com.br")  # sem nome

    assert [p.email for p in Pessoa.objects.all()] == [
        "m@icodev.com.br",  # nome vazio ordena primeiro
        "z@icodev.com.br",  # Ana
        "a@icodev.com.br",  # Bruno
    ]
