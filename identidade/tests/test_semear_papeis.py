"""`semear_papeis` — a migração que não pode fazer ninguém perder acesso."""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command

from identidade.models import AtribuicaoPapel, Papel
from identidade.papeis import MAPA_PAPEL_LEGADO, PAPEIS_V1
from identidade.tests import fabricas as f


def semear(**kwargs) -> str:
    saida = StringIO()
    call_command("semear_papeis", stdout=saida, stderr=saida, **kwargs)
    return saida.getvalue()


def com_role(username: str, role: str):
    """Cria usuário com `UserRole` legado."""
    from dashboard.utils.rbac import UserRole

    user = f.pessoa(username)
    UserRole.objects.update_or_create(user=user, defaults={"role": role})
    return user


# ── Papéis ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_simulacao_nao_grava_nada():
    texto = semear()
    assert "SIMULAÇÃO" in texto
    assert Papel.objects.count() == 0


@pytest.mark.django_db
def test_aplicar_cria_os_papeis_do_v1():
    semear(aplicar=True)
    assert set(Papel.objects.values_list("chave", flat=True)) == {
        p["chave"] for p in PAPEIS_V1
    }


@pytest.mark.django_db
def test_reexecutavel_sem_duplicar():
    semear(aplicar=True)
    antes = Papel.objects.count()
    semear(aplicar=True)
    assert Papel.objects.count() == antes


@pytest.mark.django_db
def test_atualiza_permissoes_quando_a_lista_muda():
    semear(aplicar=True)
    gerente = Papel.objects.get(chave="gerente")
    gerente.permissoes = ["obsoleto"]
    gerente.save()

    semear(aplicar=True)
    gerente.refresh_from_db()
    assert "apr.aprovar.equipe" in gerente.permissoes


# ── Migração de UserRole ────────────────────────────────────────────


@pytest.mark.django_db
def test_cada_userrole_vira_atribuicao_equivalente():
    com_role("chefe", "gerente")
    com_role("tec", "tecnico_campo")
    semear(aplicar=True)

    por_user = {
        a.user.get_username(): a.papel.chave
        for a in AtribuicaoPapel.objects.select_related("user", "papel")
    }
    assert por_user == {"chefe": "gerente", "tec": "tecnico_campo"}


@pytest.mark.django_db
def test_ninguem_perde_acesso():
    """O aceite central: quem tinha papel continua podendo o que podia."""
    from identidade.services import pode

    chefe = com_role("chefe", "gerente")
    assert pode(chefe, "apr.aprovar") is False, "antes da migração, nada"

    semear(aplicar=True)
    assert pode(chefe, "apr.aprovar") is True


@pytest.mark.django_db
def test_migrado_tem_vigencia_aberta():
    """Papel migrado não pode expirar sozinho e derrubar acesso de todo mundo."""
    com_role("chefe", "gerente")
    semear(aplicar=True)
    assert AtribuicaoPapel.objects.get().vigencia_fim is None


@pytest.mark.django_db
def test_migracao_registra_a_origem():
    com_role("chefe", "gerente")
    semear(aplicar=True)
    assert "UserRole.role='gerente'" in AtribuicaoPapel.objects.get().justificativa


@pytest.mark.django_db
def test_segunda_execucao_nao_duplica_atribuicao():
    com_role("chefe", "gerente")
    semear(aplicar=True)
    semear(aplicar=True)
    assert AtribuicaoPapel.objects.count() == 1


@pytest.mark.django_db
def test_alias_legado_e_mapeado():
    """`supervisor` e `financeiro` eram aliases; não podem ficar sem papel."""
    com_role("sup", "supervisor")
    semear(aplicar=True)
    assert AtribuicaoPapel.objects.get(user__username="sup").papel.chave == "gerente"


@pytest.mark.django_db
def test_role_sem_mapa_e_relatado_e_nao_silenciado():
    """Falhar em silêncio aqui significa alguém sem acesso e ninguém sabendo."""
    from dashboard.utils.rbac import UserRole

    user = f.pessoa("estranho")
    UserRole.objects.update_or_create(user=user, defaults={"role": "gerente"})
    UserRole.objects.filter(user=user).update(role="papel_que_nao_existe")

    texto = semear(aplicar=True)
    assert "SEM MAPA" in texto
    assert "estranho" in texto
    assert not AtribuicaoPapel.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_todos_os_papeis_do_mapa_existem_no_v1():
    """Guarda contra o mapa apontar para papel inexistente — o que produziria
    'SEM MAPA' em produção sem ninguém ter mexido no mapa."""
    chaves = {p["chave"] for p in PAPEIS_V1}
    destinos = set(MAPA_PAPEL_LEGADO.values())
    assert destinos <= chaves, f"papéis inexistentes: {destinos - chaves}"


@pytest.mark.django_db
def test_os_seis_papeis_atuais_estao_todos_mapeados():
    from dashboard.utils.rbac import UserRole

    atuais = {chave for chave, _ in UserRole.ROLE_CHOICES}
    assert atuais <= set(MAPA_PAPEL_LEGADO), (
        f"papel de UserRole sem mapa: {atuais - set(MAPA_PAPEL_LEGADO)}"
    )


@pytest.mark.django_db
def test_simulacao_conta_o_que_migraria_sem_gravar():
    com_role("chefe", "gerente")
    texto = semear()
    assert "migradas     1" in texto
    assert AtribuicaoPapel.objects.count() == 0, "simulação não grava"
