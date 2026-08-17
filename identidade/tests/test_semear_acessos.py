"""IDN — dar acesso e papel às pessoas do organograma de demonstração.

O `importar_organograma` traz quem é quem, e não traz credencial — CSV de
organograma não tem senha, e não deveria ter. O resultado era um ambiente com o
organograma certo e ninguém conseguindo entrar, e cinco áreas de aprovação sem
titular engolindo pedido.

O que estes testes protegem são principalmente as coisas que o comando **não**
pode fazer:

1. **Não troca senha que já existe** — rodar por engano não pode ser o jeito de
   perder o acesso ao próprio ambiente.
2. **Não toca em superusuário** — conta de emergência não é de demonstração.
3. **Não roda com `DEBUG=False`** sem alguém dizer que é isso mesmo.
4. **Não imprime senha na simulação**, porque a transação volta e quem anotasse
   descobriria depois que o que está no papel não vale.
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from identidade.models import AtribuicaoPapel, Papel
from identidade.papeis import PAPEIS_V1
from identidade.tests import fabricas as f

pytestmark = pytest.mark.django_db


def semear(**opcoes):
    saida = StringIO()
    call_command("semear_acessos", stdout=saida, **opcoes)
    return saida.getvalue()


@pytest.fixture(autouse=True)
def ambiente_de_desenvolvimento(settings):
    """O runner do Django força `DEBUG=False`, e o comando recusa rodar assim.

    Ligar aqui é o que deixa a suíte exercitar o caminho normal; os dois testes
    do guarda desligam de volta, e são eles que provam que ele existe.
    """
    settings.DEBUG = True


@pytest.fixture
def papeis():
    """Os papéis de verdade — o comando casa por chave com `identidade.papeis`."""
    call_command("semear_papeis", "--aplicar", stdout=StringIO())
    return {p.chave: p for p in Papel.objects.all()}


@pytest.fixture
def organograma(papeis):
    """Um recorte do organograma de exemplo: um cargo de cada tipo."""
    pessoas = {}
    for apelido, cargo in [
        ("socio", "Sócio"),
        ("diretor", "Diretor de Operações"),
        ("gerente", "Gerente de Suporte"),
        ("tecnico", "Técnico de Campo"),
    ]:
        pessoa = f.pessoa(apelido)
        # Sem senha utilizável, que é como o `importar_organograma` deixa: o CSV
        # traz cargo e hierarquia, não credencial. É justamente esse estado que
        # este comando existe para resolver.
        pessoa.set_unusable_password()
        pessoa.save(update_fields=["password"])
        f.lotar(pessoa, cargo=cargo)
        pessoas[apelido] = pessoa

    pessoas["chefe"] = f.pessoa("chefe", is_superuser=True)
    f.lotar(pessoas["chefe"], cargo="Diretor de Tecnologia")
    return pessoas


# ── O que ele faz ───────────────────────────────────────────────────


def test_concede_o_papel_do_cargo(organograma, papeis):
    semear(aplicar=True)

    tem = AtribuicaoPapel.objects.vigentes().filter(user=organograma["socio"])
    assert [a.papel.chave for a in tem] == ["socios"]


def test_um_cargo_pode_render_mais_de_um_papel(organograma):
    """O Gerente de Suporte é gestor da equipe DELE e ainda destrava o degrau de
    Compras, que é o que mais aparece na cadeia."""
    semear(aplicar=True)

    tem = AtribuicaoPapel.objects.vigentes().filter(user=organograma["gerente"])
    assert {a.papel.chave for a in tem} == {"gestor", "compras"}


def test_sorteia_senha_para_quem_nao_tinha(organograma):
    semear(aplicar=True)

    organograma["tecnico"].refresh_from_db()
    assert organograma["tecnico"].has_usable_password()


def test_a_senha_e_diferente_para_cada_pessoa(organograma):
    saida = semear(aplicar=True)

    bloco = saida.split("anote agora")[1]
    senhas = [linha.split()[-1] for linha in bloco.splitlines() if "@" in linha]

    assert len(senhas) == 4, "as quatro pessoas sem senha do organograma"
    assert len(set(senhas)) == len(senhas), "senha repetida é senha adivinhável"


def test_a_concessao_tem_autor_e_justificativa(organograma):
    """Concessão sem autor não responde à única pergunta que importa depois de
    um incidente: quem deu esse acesso?"""
    semear(aplicar=True)

    atribuicao = AtribuicaoPapel.objects.vigentes().filter(
        user=organograma["socio"]
    ).first()
    assert atribuicao.concedido_por == organograma["chefe"]
    assert atribuicao.justificativa


def test_reexecutar_nao_duplica(organograma):
    semear(aplicar=True)
    antes = AtribuicaoPapel.objects.count()

    semear(aplicar=True)

    assert AtribuicaoPapel.objects.count() == antes


# ── O que ele NÃO faz ───────────────────────────────────────────────


def test_nao_troca_senha_de_quem_ja_entra(organograma):
    """Rodar isto por engano não pode ser o jeito de perder o próprio acesso."""
    pessoa = organograma["tecnico"]
    pessoa.set_password("a-que-eu-escolhi")
    pessoa.save(update_fields=["password"])

    semear(aplicar=True)

    pessoa.refresh_from_db()
    assert pessoa.check_password("a-que-eu-escolhi")


def test_senha_escolhida_vale_para_todo_mundo(organograma):
    """Para demonstrar de mesa: uma senha que dá para digitar sem consultar."""
    semear(aplicar=True, senha="workspace123")

    for apelido in ("socio", "diretor", "gerente", "tecnico"):
        organograma[apelido].refresh_from_db()
        assert organograma[apelido].check_password("workspace123")


def test_senha_escolhida_avisa_que_e_so_para_demonstracao(organograma):
    saida = semear(aplicar=True, senha="workspace123")

    assert "SENHA ÚNICA" in saida


def test_senha_escolhida_nao_alcanca_superusuario(organograma):
    """Nem a senha fácil entra na conta de emergência."""
    chefe = organograma["chefe"]
    antes = chefe.password

    semear(aplicar=True, senha="workspace123", resortear=True)

    chefe.refresh_from_db()
    assert chefe.password == antes


def test_resortear_troca_a_senha_de_quem_ja_tem(organograma):
    """Para quando a senha passou por um lugar por onde não devia."""
    semear(aplicar=True)
    pessoa = organograma["tecnico"]
    pessoa.refresh_from_db()
    antes = pessoa.password

    semear(aplicar=True, resortear=True)

    pessoa.refresh_from_db()
    assert pessoa.password != antes
    assert pessoa.has_usable_password()


def test_resortear_ainda_nao_toca_em_superusuario(organograma):
    """A flag afrouxa a regra da senha existente, não a do superusuário."""
    chefe = organograma["chefe"]
    antes = chefe.password

    semear(aplicar=True, resortear=True)

    chefe.refresh_from_db()
    assert chefe.password == antes


def test_nao_toca_em_superusuario(organograma):
    """Conta de emergência não é conta de demonstração."""
    chefe = organograma["chefe"]
    antes = chefe.password

    semear(aplicar=True)

    chefe.refresh_from_db()
    assert chefe.password == antes
    assert not AtribuicaoPapel.objects.filter(user=chefe).exists()


def test_cargo_desconhecido_nao_ganha_papel(organograma):
    """Heurística sobre o texto do cargo acerta hoje e erra no primeiro cargo
    novo, em silêncio. O mapa é explícito, e o que não está nele fica de fora."""
    estranho = f.pessoa("estranho")
    f.lotar(estranho, cargo="Domador de Leões")

    semear(aplicar=True)

    assert not AtribuicaoPapel.objects.filter(user=estranho).exists()

    estranho.refresh_from_db()
    assert estranho.has_usable_password(), "sem papel, mas entra — são coisas separadas"


def test_simulacao_nao_grava_nada(organograma):
    semear()

    assert AtribuicaoPapel.objects.count() == 0
    organograma["tecnico"].refresh_from_db()
    assert not organograma["tecnico"].has_usable_password()


def test_simulacao_nao_imprime_senha(organograma):
    """A transação volta. Quem anotasse descobriria na hora de entrar que o que
    está no papel não vale — pior que não ter mostrado nada."""
    saida = semear()

    assert "(sorteada ao aplicar)" in saida
    assert "anote agora" not in saida


def test_recusa_fora_do_debug(organograma, settings):
    """Semear senha conhecida em produção é o acidente que este guarda impede."""
    settings.DEBUG = False

    with pytest.raises(CommandError, match="DEBUG=False"):
        semear(aplicar=True)


def test_forcar_passa_por_cima_do_guarda(organograma, settings):
    settings.DEBUG = False

    semear(aplicar=True, forcar=True)

    assert AtribuicaoPapel.objects.exists()


def test_sem_superusuario_recusa_em_vez_de_conceder_sem_autor(papeis):
    pessoa = f.pessoa("sozinha")
    f.lotar(pessoa, cargo="Sócio")

    with pytest.raises(CommandError, match="[Nn]enhum superusuário"):
        semear(aplicar=True)


def test_papel_que_nao_existe_e_relatado_e_nao_estoura(organograma):
    """`semear_papeis` roda antes deste comando. Se não rodou, o comando diz —
    em vez de conceder metade e calar sobre o resto."""
    Papel.objects.filter(chave="compras").delete()

    saida = semear(aplicar=True)

    assert "PAPEL NÃO EXISTE" in saida
    assert AtribuicaoPapel.objects.filter(papel__chave="gestor").exists(), (
        "o resto do trabalho continua"
    )


# ── Coerência com o resto do produto ────────────────────────────────


def test_todo_papel_do_mapa_existe_de_verdade(papeis):
    """Um erro de digitação no mapa vira uma área órfã que ninguém procura."""
    from identidade.management.commands.semear_acessos import POR_CARGO

    conhecidos = {p["chave"] for p in PAPEIS_V1}
    usados = {chave for chaves in POR_CARGO.values() for chave in chaves}

    assert usados <= conhecidos, f"papéis inventados: {usados - conhecidos}"
