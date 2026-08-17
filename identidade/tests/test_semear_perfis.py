"""IDN — um usuário por papel, com o nome do papel.

O organograma de exemplo tem gente com nome de gente. É realista, e é péssimo
para testar: para saber quem vê a fila de Compras é preciso lembrar que Compras
caiu no gerente de suporte, e nada na tela diz isso.

Aqui o e-mail **é** a resposta. O que estes testes protegem:

1. **Um perfil por papel**, e o papel certo em cada um.
2. **A hierarquia existe** — sem ela a cadeia de aprovação não teria o primeiro
   degrau, que é GESTOR_DIRETO e sai da lotação, não de papel.
3. **Reexecutável**: rodar duas vezes não duplica pessoa nem atribuição.
4. **Não roda com `DEBUG=False`** sem alguém dizer que é isso mesmo — senha
   única e conhecida não pode existir num ambiente real.
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from identidade.management.commands.semear_perfis import (
    DOMINIO,
    PERFIS,
    SENHA_PADRAO,
)
from identidade.models import AtribuicaoPapel, Lotacao, Papel
from identidade.papeis import PAPEIS_V1
from identidade.tests import fabricas as f

pytestmark = pytest.mark.django_db


def semear(**opcoes):
    saida = StringIO()
    call_command("semear_perfis", stdout=saida, **opcoes)
    return saida.getvalue()


def perfil(chave):
    return get_user_model().objects.get(email=f"{chave}@{DOMINIO}")


@pytest.fixture(autouse=True)
def ambiente_de_desenvolvimento(settings):
    """O runner do Django força `DEBUG=False`, e o comando recusa rodar assim."""
    settings.DEBUG = True


@pytest.fixture(autouse=True)
def base(db):
    """Os papéis de verdade e um superusuário — toda concessão precisa de autor."""
    call_command("semear_papeis", "--aplicar", stdout=StringIO())
    f.pessoa("chefe", is_superuser=True)


# ── O que ele cria ──────────────────────────────────────────────────


def test_cria_um_perfil_por_papel():
    semear(aplicar=True)

    for chave, _, _ in PERFIS:
        assert perfil(chave), f"faltou {chave}@{DOMINIO}"


def test_cada_perfil_tem_o_papel_do_proprio_nome():
    """É a promessa inteira do comando: quem entra como `compras@` é Compras."""
    semear(aplicar=True)

    for chave, _, _ in PERFIS:
        tem = AtribuicaoPapel.objects.vigentes().filter(user=perfil(chave))
        assert [a.papel.chave for a in tem] == [chave]


def test_o_papel_vem_com_o_escopo_padrao_dele():
    semear(aplicar=True)

    atribuicao = AtribuicaoPapel.objects.vigentes().get(user=perfil("compras"))
    assert atribuicao.escopo == Papel.objects.get(chave="compras").escopo_padrao


def test_a_senha_e_a_mesma_para_todos():
    semear(aplicar=True)

    for chave, _, _ in PERFIS:
        assert perfil(chave).check_password(SENHA_PADRAO)


def test_da_para_escolher_outra_senha():
    semear(aplicar=True, senha="outra-senha-123")

    assert perfil("rh").check_password("outra-senha-123")


def test_o_nome_na_tela_e_o_do_papel():
    """A tela mostra "Compras aprovou", que é o que se quer ler ao conferir."""
    semear(aplicar=True)

    assert "Compras" in perfil("compras").get_full_name()


# ── A hierarquia ────────────────────────────────────────────────────


def test_a_cadeia_de_chefia_existe():
    """Sem ela o primeiro degrau da aprovação não teria em quem cair: a regra de
    ordem 10 é GESTOR_DIRETO, e sai da lotação, não de papel."""
    semear(aplicar=True)

    assert Lotacao.objects.get(user=perfil("colaborador")).gestor == perfil("gestor")
    assert Lotacao.objects.get(user=perfil("gestor")).gestor == perfil("diretoria")
    assert Lotacao.objects.get(user=perfil("diretoria")).gestor == perfil("socios")


def test_quem_esta_no_topo_nao_tem_chefe():
    semear(aplicar=True)

    assert Lotacao.objects.get(user=perfil("socios")).gestor is None


def test_as_areas_tambem_respondem_a_alguem():
    """Elas também PEDEM coisas, e pedido sem primeiro degrau não exercita a
    cadeia."""
    semear(aplicar=True)

    assert Lotacao.objects.get(user=perfil("financeiro")).gestor == perfil("gestor")


def test_todo_perfil_tem_lotacao_completa():
    """`conceder()` recusa papel para quem não tem lotação — aprovador sem
    unidade e sem gestor não tem escopo que signifique algo."""
    semear(aplicar=True)

    lotacao = Lotacao.objects.get(user=perfil("ti"))
    assert lotacao.unidade is not None
    assert lotacao.departamento is not None
    assert lotacao.cargo


# ── A cadeia de aprovação, de ponta a ponta ─────────────────────────


def test_o_colaborador_pede_e_o_gestor_recebe():
    """O teste que justifica a hierarquia: sem ela isto não sai do lugar."""
    from decimal import Decimal

    from workspace.models import GrupoCatalogo, ItemCatalogo, RegraAprovacao, TipoAprovador
    from workspace.services import catalogo as svc

    semear(aplicar=True)
    item = ItemCatalogo.objects.create(
        chave="cadeira", nome="Cadeira", grupo=GrupoCatalogo.EQUIPAMENTO,
        dominio="com.requisicao", exige_valor=True, limite_auto_aprovacao=None,
        campos=[{"chave": "o_que", "rotulo": "O quê", "obrigatorio": True}],
    )
    RegraAprovacao.objects.create(
        dominio="*", tipo=TipoAprovador.GESTOR_DIRETO, ordem=10
    )
    RegraAprovacao.objects.create(
        dominio="com.", tipo=TipoAprovador.PAPEL,
        papel=Papel.objects.get(chave="compras"), ordem=15,
    )

    pedido = svc.solicitar(
        item, perfil("colaborador"), {"o_que": "Cadeira"}, valor=Decimal("900")
    )

    etapas = list(pedido.aprovacao.etapas.order_by("ordem"))
    assert etapas[0].aprovador == perfil("gestor"), "o gestor direto, pela lotação"
    assert etapas[1].papel.chave == "compras", "depois a área"


# ── Reexecutar, e os guardas ────────────────────────────────────────


def test_reexecutar_nao_duplica():
    semear(aplicar=True)
    pessoas = get_user_model().objects.count()
    atribuicoes = AtribuicaoPapel.objects.count()

    semear(aplicar=True)

    assert get_user_model().objects.count() == pessoas
    assert AtribuicaoPapel.objects.count() == atribuicoes


def test_simulacao_nao_grava_nada():
    semear()

    assert not get_user_model().objects.filter(email=f"rh@{DOMINIO}").exists()


def test_a_simulacao_mostra_o_mapa_de_quem_seria_quem():
    """O relatório é metade do valor do comando: ele responde "quem eu uso para
    testar Compras?" sem precisar abrir o banco."""
    saida = semear()

    assert f"compras@{DOMINIO}" in saida
    assert "responde a" in saida


def test_recusa_fora_do_debug(settings):
    settings.DEBUG = False

    with pytest.raises(CommandError, match="DEBUG=False"):
        semear(aplicar=True)


def test_sem_superusuario_recusa_em_vez_de_conceder_sem_autor():
    get_user_model().objects.filter(is_superuser=True).delete()

    with pytest.raises(CommandError, match="[Nn]enhum superusuário"):
        semear(aplicar=True)


# ── Coerência ───────────────────────────────────────────────────────


def test_existe_um_perfil_para_cada_papel_do_projeto():
    """Papel sem perfil é papel que ninguém vai testar — e é assim que uma área
    inteira fica sem cobertura sem ninguém notar."""
    conhecidos = {p["chave"] for p in PAPEIS_V1}
    cobertos = {chave for chave, _, _ in PERFIS}

    assert cobertos == conhecidos, f"descobertos: {conhecidos - cobertos}"


def test_todo_chefe_do_mapa_e_um_perfil_do_mapa():
    """Chefe apontando para quem não existe deixaria a lotação sem gestor, em
    silêncio, e o primeiro degrau da cadeia sumiria."""
    chaves = {chave for chave, _, _ in PERFIS}
    chefes = {chefe for _, _, chefe in PERFIS if chefe}

    assert chefes <= chaves


def test_o_chefe_vem_antes_de_quem_responde_a_ele():
    """A ordem da lista é o que garante que o gestor já exista na hora de
    vincular — inverter faria a lotação nascer sem gestor."""
    vistos = set()
    for chave, _, chefe in PERFIS:
        assert chefe is None or chefe in vistos, f"{chave} responde a {chefe}, ainda não criado"
        vistos.add(chave)
