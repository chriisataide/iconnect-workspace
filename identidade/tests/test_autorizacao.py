"""`pode()` — a única porta de autorização.

Aceite do ST-014 exige **100% de cobertura neste módulo**, porque erro aqui é
falha de segurança e lentidão aqui é lentidão em tudo. Uma home chama isto ~40
vezes.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone

from identidade.services.autorizacao import (
    _casa_permissao,
    cadeia_de_gestores,
    escopo_de,
    hoje,
    liderados_recursivos,
    pode,
    situacao_de,
    subjects_de,
)
from identidade.tests import fabricas as f


# ── Portas de entrada ───────────────────────────────────────────────


@pytest.mark.django_db
def test_none_nunca_pode():
    assert pode(None, "rh.ler") is False


@pytest.mark.django_db
def test_anonimo_nunca_pode():
    assert pode(AnonymousUser(), "rh.ler") is False


@pytest.mark.django_db
def test_superusuario_pode_tudo():
    """Saída de emergência do Django. Retirá-la quebraria o admin."""
    admin = f.pessoa("root", is_superuser=True)
    assert pode(admin, "qualquer.coisa.inventada") is True


@pytest.mark.django_db
def test_usuario_sem_pk_nao_pode():
    from django.contrib.auth import get_user_model

    assert pode(get_user_model()(email="nao_salvo@icodev.com.br"), "rh.ler") is False


@pytest.mark.django_db
def test_sem_atribuicao_nao_pode():
    assert pode(f.pessoa("joao"), "rh.ler") is False


# ── Casamento de permissão ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("concedida", "pedida", "esperado"),
    [
        ("*", "qualquer.coisa", "global"),
        ("rh.ler.equipe", "rh.ler", "equipe"),
        ("rh.ler", "rh.ler", ""),
        ("rh.*", "rh.aprovar", "global"),
        ("rh.*", "fin.aprovar", None),
        ("rh.ler", "rh.ler.detalhe", ""),
        ("rh.ler.equipe", "fin.ler", None),
        ("rh.aprovar.global", "rh.aprovar", "global"),
        ("fin", "fin.ler", ""),
    ],
)
def test_casa_permissao(concedida, pedida, esperado):
    assert _casa_permissao(concedida, pedida) == esperado


@pytest.mark.django_db
def test_curinga_de_dominio_cobre_o_dominio():
    u = f.pessoa("ana")
    f.atribuir(u, f.papel("rh_full", ["rh.*"], escopo="global"))
    assert pode(u, "rh.ler") is True
    assert pode(u, "rh.aprovar") is True
    assert pode(u, "fin.ler") is False


# ── Os cinco escopos ────────────────────────────────────────────────


@pytest.mark.django_db
def test_escopo_proprio_alcanca_so_a_propria_pessoa():
    ana, bruno = f.pessoa("ana"), f.pessoa("bruno")
    f.atribuir(ana, f.papel("self", ["rh.ler.proprio"]))

    assert pode(ana, "rh.ler", alvo=ana) is True
    assert pode(ana, "rh.ler", alvo=bruno) is False


@pytest.mark.django_db
def test_escopo_equipe_alcanca_liderado_direto_e_indireto():
    chefe, meio, base, fora = (f.pessoa(n) for n in ("chefe", "meio", "base", "fora"))
    f.lotar(chefe)
    f.lotar(meio, gestor=chefe)
    f.lotar(base, gestor=meio)
    f.lotar(fora)
    f.atribuir(chefe, f.papel("gestor", ["rh.ler.equipe"], escopo="equipe"))

    assert pode(chefe, "rh.ler", alvo=meio) is True
    assert pode(chefe, "rh.ler", alvo=base) is True, "liderado indireto conta"
    assert pode(chefe, "rh.ler", alvo=chefe) is True, "equipe inclui a própria pessoa"
    assert pode(chefe, "rh.ler", alvo=fora) is False


@pytest.mark.django_db
def test_escopo_unidade_com_unidade_explicita():
    sp, rj = f.unidade("SP"), f.unidade("RJ", "Filial RJ")
    gestor, em_sp, em_rj = (f.pessoa(n) for n in ("gestor", "em_sp", "em_rj"))
    f.lotar(gestor, uni=sp)
    f.lotar(em_sp, uni=sp)
    f.lotar(em_rj, uni=rj)
    f.atribuir(gestor, f.papel("rh_sp", ["rh.ler.unidade"], escopo="unidade"), uni=sp)

    assert pode(gestor, "rh.ler", alvo=em_sp) is True
    assert pode(gestor, "rh.ler", alvo=em_rj) is False, "não vaza entre unidades"


@pytest.mark.django_db
def test_escopo_unidade_sem_unidade_explicita_usa_a_propria():
    sp, rj = f.unidade("SP"), f.unidade("RJ", "Filial RJ")
    gestor, em_sp, em_rj = (f.pessoa(n) for n in ("gestor", "em_sp", "em_rj"))
    f.lotar(gestor, uni=sp)
    f.lotar(em_sp, uni=sp)
    f.lotar(em_rj, uni=rj)
    f.atribuir(gestor, f.papel("rh_uni", ["rh.ler.unidade"], escopo="unidade"))

    assert pode(gestor, "rh.ler", alvo=em_sp) is True
    assert pode(gestor, "rh.ler", alvo=em_rj) is False


@pytest.mark.django_db
def test_escopo_unidade_nao_alcanca_alvo_sem_lotacao():
    sp = f.unidade("SP")
    gestor, sem_lotacao = f.pessoa("gestor"), f.pessoa("sem")
    f.lotar(gestor, uni=sp)
    f.atribuir(gestor, f.papel("rh_uni", ["rh.ler.unidade"], escopo="unidade"), uni=sp)

    assert pode(gestor, "rh.ler", alvo=sem_lotacao) is False


@pytest.mark.django_db
def test_escopo_unidade_nao_alcanca_alvo_sem_unidade():
    sp = f.unidade("SP")
    gestor, sem_uni = f.pessoa("gestor"), f.pessoa("sem_uni")
    f.lotar(gestor, uni=sp)
    f.lotar(sem_uni)
    f.atribuir(gestor, f.papel("rh_uni", ["rh.ler.unidade"], escopo="unidade"), uni=sp)

    assert pode(gestor, "rh.ler", alvo=sem_uni) is False


@pytest.mark.django_db
def test_escopo_unidade_sem_explicita_e_pessoa_sem_lotacao():
    sp = f.unidade("SP")
    gestor, alvo = f.pessoa("gestor"), f.pessoa("alvo")
    f.lotar(alvo, uni=sp)
    f.atribuir(gestor, f.papel("rh_uni", ["rh.ler.unidade"], escopo="unidade"))

    assert pode(gestor, "rh.ler", alvo=alvo) is False


@pytest.mark.django_db
def test_escopo_departamento():
    ti, rh_dep = f.departamento("TI"), f.departamento("RH", "Pessoas")
    bp, em_ti, em_rh = (f.pessoa(n) for n in ("bp", "em_ti", "em_rh"))
    f.lotar(bp, dep=ti)
    f.lotar(em_ti, dep=ti)
    f.lotar(em_rh, dep=rh_dep)
    f.atribuir(bp, f.papel("bp_ti", ["rh.ler.departamento"], escopo="departamento"), dep=ti)

    assert pode(bp, "rh.ler", alvo=em_ti) is True
    assert pode(bp, "rh.ler", alvo=em_rh) is False


@pytest.mark.django_db
def test_escopo_departamento_sem_explicito_usa_o_proprio():
    ti, outro = f.departamento("TI"), f.departamento("FIN", "Financeiro")
    bp, em_ti, em_fin = (f.pessoa(n) for n in ("bp", "em_ti", "em_fin"))
    f.lotar(bp, dep=ti)
    f.lotar(em_ti, dep=ti)
    f.lotar(em_fin, dep=outro)
    f.atribuir(bp, f.papel("bp", ["rh.ler.departamento"], escopo="departamento"))

    assert pode(bp, "rh.ler", alvo=em_ti) is True
    assert pode(bp, "rh.ler", alvo=em_fin) is False


@pytest.mark.django_db
def test_escopo_departamento_nao_alcanca_alvo_sem_departamento():
    ti = f.departamento("TI")
    bp, sem = f.pessoa("bp"), f.pessoa("sem")
    f.lotar(bp, dep=ti)
    f.lotar(sem)
    f.atribuir(bp, f.papel("bp", ["rh.ler.departamento"], escopo="departamento"), dep=ti)

    assert pode(bp, "rh.ler", alvo=sem) is False


@pytest.mark.django_db
def test_escopo_departamento_sem_explicito_e_pessoa_sem_departamento():
    ti = f.departamento("TI")
    bp, alvo = f.pessoa("bp"), f.pessoa("alvo")
    f.lotar(alvo, dep=ti)
    f.atribuir(bp, f.papel("bp", ["rh.ler.departamento"], escopo="departamento"))

    assert pode(bp, "rh.ler", alvo=alvo) is False


@pytest.mark.django_db
def test_escopo_global_alcanca_qualquer_alvo():
    corp, qualquer = f.pessoa("corp"), f.pessoa("qualquer")
    f.atribuir(corp, f.papel("corp", ["rh.ler.global"], escopo="global"))
    assert pode(corp, "rh.ler", alvo=qualquer) is True


@pytest.mark.django_db
def test_escopo_maior_satisfaz_pergunta_menor():
    """Quem tem global também pode sobre si mesmo."""
    corp = f.pessoa("corp")
    f.atribuir(corp, f.papel("corp", ["rh.ler.global"], escopo="global"))
    assert pode(corp, "rh.ler", alvo=corp) is True


@pytest.mark.django_db
def test_escopo_desconhecido_nao_concede():
    """Escopo fora da hierarquia nega — nunca libera por omissão."""
    u = f.pessoa("ana")
    alvo = f.pessoa("bruno")
    f.atribuir(u, f.papel("estranho", ["rh.ler"], escopo="proprio"), escopo="galactico")
    assert pode(u, "rh.ler", alvo=alvo) is False


@pytest.mark.django_db
def test_alvo_none_pergunta_se_pode_em_geral():
    """Tela de listagem pergunta sem alvo; o recorte é da consulta."""
    u = f.pessoa("ana")
    f.atribuir(u, f.papel("self", ["rh.ler.proprio"]))
    assert pode(u, "rh.ler") is True


# ── Formas de alvo aceitas ──────────────────────────────────────────


@pytest.mark.django_db
def test_alvo_aceita_user_lotacao_e_id():
    ana, bruno = f.pessoa("ana"), f.pessoa("bruno")
    f.lotar(ana)
    lot_bruno = f.lotar(bruno, gestor=ana)
    f.atribuir(ana, f.papel("gestor", ["rh.ler.equipe"], escopo="equipe"))

    assert pode(ana, "rh.ler", alvo=bruno) is True, "User"
    assert pode(ana, "rh.ler", alvo=lot_bruno) is True, "Lotacao"
    assert pode(ana, "rh.ler", alvo=bruno.pk) is True, "int"


@pytest.mark.django_db
def test_alvo_aceita_objeto_com_atributo_user():
    class Envelope:
        def __init__(self, user):
            self.user = user

    ana, bruno = f.pessoa("ana"), f.pessoa("bruno")
    f.lotar(ana)
    f.lotar(bruno, gestor=ana)
    f.atribuir(ana, f.papel("gestor", ["rh.ler.equipe"], escopo="equipe"))

    assert pode(ana, "rh.ler", alvo=Envelope(bruno)) is True


@pytest.mark.django_db
def test_alvo_objeto_sem_user_nem_pk_nao_quebra():
    class Vazio:
        pass

    u = f.pessoa("ana")
    f.atribuir(u, f.papel("self", ["rh.ler.proprio"]))
    # pk None → tratado como "em geral"
    assert pode(u, "rh.ler", alvo=Vazio()) is True


# ── Vigência ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_atribuicao_vencida_nao_concede():
    u = f.pessoa("ana")
    ontem = timezone.localdate() - timedelta(days=1)
    f.atribuir(u, f.papel("p", ["rh.ler.global"], escopo="global"),
               inicio=ontem - timedelta(days=30), fim=ontem)
    assert pode(u, "rh.ler") is False


@pytest.mark.django_db
def test_atribuicao_futura_nao_concede():
    u = f.pessoa("ana")
    amanha = timezone.localdate() + timedelta(days=1)
    f.atribuir(u, f.papel("p", ["rh.ler.global"], escopo="global"), inicio=amanha)
    assert pode(u, "rh.ler") is False


@pytest.mark.django_db
def test_vigencia_aberta_nunca_expira():
    u = f.pessoa("ana")
    f.atribuir(u, f.papel("p", ["rh.ler.global"], escopo="global"), fim=None)
    assert pode(u, "rh.ler") is True


@pytest.mark.django_db
def test_papel_inativo_nao_concede():
    u = f.pessoa("ana")
    f.atribuir(u, f.papel("morto", ["rh.ler.global"], escopo="global", ativo=False))
    assert pode(u, "rh.ler") is False


# ── Delegação ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_delegacao_transfere_permissao():
    chefe, subs = f.pessoa("chefe"), f.pessoa("subs")
    f.atribuir(chefe, f.papel("aprov", ["apr.aprovar.global"], escopo="global"))
    hoje_ = timezone.localdate()
    f.delegar(chefe, subs, hoje_ - timedelta(days=1), hoje_ + timedelta(days=5))

    assert pode(subs, "apr.aprovar") is True


@pytest.mark.django_db
def test_delegacao_vencida_nao_transfere():
    chefe, subs = f.pessoa("chefe"), f.pessoa("subs")
    f.atribuir(chefe, f.papel("aprov", ["apr.aprovar.global"], escopo="global"))
    hoje_ = timezone.localdate()
    f.delegar(chefe, subs, hoje_ - timedelta(days=30), hoje_ - timedelta(days=1))

    assert pode(subs, "apr.aprovar") is False


@pytest.mark.django_db
def test_delegacao_inativa_nao_transfere():
    chefe, subs = f.pessoa("chefe"), f.pessoa("subs")
    f.atribuir(chefe, f.papel("aprov", ["apr.aprovar.global"], escopo="global"))
    hoje_ = timezone.localdate()
    f.delegar(chefe, subs, hoje_, hoje_ + timedelta(days=5), ativa=False)

    assert pode(subs, "apr.aprovar") is False


@pytest.mark.django_db
def test_delegacao_nao_amplia():
    """A regra que impede escalonamento de privilégio.

    O delegante só tem `apr.aprovar`. Delegar não pode dar `rh.admin`.
    """
    chefe, subs = f.pessoa("chefe"), f.pessoa("subs")
    f.atribuir(chefe, f.papel("aprov", ["apr.aprovar.global"], escopo="global"))
    hoje_ = timezone.localdate()
    f.delegar(chefe, subs, hoje_, hoje_ + timedelta(days=5))

    assert pode(subs, "apr.aprovar") is True
    assert pode(subs, "rh.admin") is False


@pytest.mark.django_db
def test_delegacao_de_papel_especifico_nao_leva_os_outros():
    chefe, subs = f.pessoa("chefe"), f.pessoa("subs")
    so_esse = f.papel("aprov", ["apr.aprovar.global"], escopo="global")
    outro = f.papel("rh", ["rh.admin.global"], escopo="global")
    f.atribuir(chefe, so_esse)
    f.atribuir(chefe, outro)
    hoje_ = timezone.localdate()
    f.delegar(chefe, subs, hoje_, hoje_ + timedelta(days=5), papeis=[so_esse])

    assert pode(subs, "apr.aprovar") is True
    assert pode(subs, "rh.admin") is False, "papel não delegado não passa"


@pytest.mark.django_db
def test_delegacao_perde_o_que_o_delegante_perdeu():
    """Interseção com o que o delegante tem HOJE, não com o que tinha."""
    chefe, subs = f.pessoa("chefe"), f.pessoa("subs")
    hoje_ = timezone.localdate()
    atrib = f.atribuir(chefe, f.papel("aprov", ["apr.aprovar.global"], escopo="global"))
    f.delegar(chefe, subs, hoje_, hoje_ + timedelta(days=5))
    assert pode(subs, "apr.aprovar") is True

    atrib.vigencia_fim = hoje_ - timedelta(days=1)
    atrib.save()
    assert pode(subs, "apr.aprovar") is False


# ── Cache ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_cache_evita_query_repetida(django_assert_num_queries):
    """Contrato: 40 chamadas na mesma requisição não fazem 40 rodadas de query."""
    u = f.pessoa("ana")
    f.atribuir(u, f.papel("p", ["rh.ler.global"], escopo="global"))

    cache: dict = {}
    pode(u, "rh.ler", cache=cache)  # aquece
    with django_assert_num_queries(0):
        for _ in range(40):
            assert pode(u, "rh.ler", cache=cache) is True


@pytest.mark.django_db
def test_sem_cache_cada_chamada_consulta():
    u = f.pessoa("ana")
    f.atribuir(u, f.papel("p", ["rh.ler.global"], escopo="global"))
    assert pode(u, "rh.ler") is True
    assert pode(u, "rh.ler") is True


@pytest.mark.django_db
def test_mudanca_de_papel_vale_na_requisicao_seguinte():
    """O cache vive só no request — nunca entre requests."""
    u = f.pessoa("ana")
    cache_req1: dict = {}
    assert pode(u, "rh.ler", cache=cache_req1) is False

    f.atribuir(u, f.papel("p", ["rh.ler.global"], escopo="global"))
    assert pode(u, "rh.ler", cache=cache_req1) is False, "cache do request antigo não muda"

    cache_req2: dict = {}
    assert pode(u, "rh.ler", cache=cache_req2) is True, "request novo já vê"


# ── escopo_de ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_escopo_de_devolve_o_mais_amplo():
    u = f.pessoa("ana")
    f.atribuir(u, f.papel("a", ["rh.ler.proprio"]))
    f.atribuir(u, f.papel("b", ["rh.ler.unidade"], escopo="unidade"), uni=f.unidade("SP"))
    assert escopo_de(u, "rh.ler") == "unidade"


@pytest.mark.django_db
def test_escopo_de_sem_permissao_e_none():
    assert escopo_de(f.pessoa("ana"), "rh.ler") is None


@pytest.mark.django_db
def test_escopo_de_superusuario_e_global():
    assert escopo_de(f.pessoa("root", is_superuser=True), "qualquer") == "global"


@pytest.mark.django_db
def test_escopo_de_anonimo_e_none():
    assert escopo_de(AnonymousUser(), "rh.ler") is None
    assert escopo_de(None, "rh.ler") is None


@pytest.mark.django_db
def test_escopo_de_usuario_sem_pk_e_none():
    from django.contrib.auth import get_user_model

    assert escopo_de(get_user_model()(email="nao_salvo@icodev.com.br"), "rh.ler") is None


# ── subjects_de ─────────────────────────────────────────────────────


@pytest.mark.django_db
def test_subjects_de_anonimo_tem_so_publico():
    assert subjects_de(AnonymousUser()) == ["*"]
    assert subjects_de(None) == ["*"]


@pytest.mark.django_db
def test_subjects_de_inclui_pessoa_unidade_depto_e_papel():
    sp, ti = f.unidade("SP"), f.departamento("TI")
    u = f.pessoa("ana")
    f.lotar(u, uni=sp, dep=ti)
    f.atribuir(u, f.papel("gestor", ["rh.ler.equipe"], escopo="equipe"))

    subjects = subjects_de(u)
    assert "*" in subjects
    assert f"pessoa:{u.pk}" in subjects
    assert f"unidade:{sp.pk}" in subjects
    assert f"depto:{ti.pk}" in subjects
    assert "papel:gestor" in subjects


@pytest.mark.django_db
def test_subjects_de_sem_lotacao_nao_quebra():
    u = f.pessoa("ana")
    assert subjects_de(u) == ["*", f"pessoa:{u.pk}"]


@pytest.mark.django_db
def test_subjects_de_lotacao_sem_unidade_nem_depto():
    u = f.pessoa("ana")
    f.lotar(u)
    assert subjects_de(u) == ["*", f"pessoa:{u.pk}"]


# ── Organograma ─────────────────────────────────────────────────────


@pytest.mark.django_db
def test_liderados_recursivos_desce_todos_os_niveis():
    n1, n2, n3, n4 = (f.pessoa(f"n{i}") for i in range(1, 5))
    f.lotar(n1)
    f.lotar(n2, gestor=n1)
    f.lotar(n3, gestor=n2)
    f.lotar(n4, gestor=n3)

    assert liderados_recursivos(n1.pk) == {n2.pk, n3.pk, n4.pk}
    assert liderados_recursivos(n3.pk) == {n4.pk}
    assert liderados_recursivos(n4.pk) == set()


@pytest.mark.django_db
def test_liderados_recursivos_em_uma_query(django_assert_num_queries):
    """Uma CTE, não uma query por nível."""
    n1, n2, n3 = (f.pessoa(f"n{i}") for i in range(1, 4))
    f.lotar(n1)
    f.lotar(n2, gestor=n1)
    f.lotar(n3, gestor=n2)

    with django_assert_num_queries(1):
        liderados_recursivos(n1.pk)


@pytest.mark.django_db
def test_liderados_recursivos_usa_memo():
    n1, n2 = f.pessoa("n1"), f.pessoa("n2")
    f.lotar(n1)
    f.lotar(n2, gestor=n1)
    cache: dict = {}
    primeiro = liderados_recursivos(n1.pk, cache=cache)
    assert liderados_recursivos(n1.pk, cache=cache) is primeiro


@pytest.mark.django_db
def test_cadeia_de_gestores_sobe_ate_o_topo():
    topo, meio, base = (f.pessoa(n) for n in ("topo", "meio", "base"))
    f.lotar(topo)
    f.lotar(meio, gestor=topo)
    f.lotar(base, gestor=meio)

    assert cadeia_de_gestores(base.pk) == [meio.pk, topo.pk]
    assert cadeia_de_gestores(topo.pk) == []


@pytest.mark.django_db
def test_cadeia_de_gestores_sem_lotacao_e_vazia():
    assert cadeia_de_gestores(f.pessoa("solto").pk) == []


@pytest.mark.django_db
def test_cadeia_de_gestores_nao_gira_em_ciclo_existente():
    """Ciclo inserido antes da validação não pode travar a função."""
    a, b = f.pessoa("a"), f.pessoa("b")
    la = f.lotar(a)
    f.lotar(b, gestor=a)
    # Fecha o ciclo por baixo do `clean()`.
    from identidade.models import Lotacao

    Lotacao.objects.filter(pk=la.pk).update(gestor=b)

    cadeia = cadeia_de_gestores(a.pk)
    assert cadeia == [b.pk], "para ao reencontrar quem já viu"


@pytest.mark.django_db
def test_liderados_nao_gira_em_ciclo_existente():
    a, b = f.pessoa("a"), f.pessoa("b")
    la = f.lotar(a)
    f.lotar(b, gestor=a)
    from identidade.models import Lotacao

    Lotacao.objects.filter(pk=la.pk).update(gestor=b)

    assert liderados_recursivos(a.pk) == {a.pk, b.pk}


# ── Auxiliares ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_situacao_de():
    u = f.pessoa("ana")
    f.lotar(u, situacao="ferias")
    assert situacao_de(u.pk) == "ferias"
    assert situacao_de(f.pessoa("sem").pk) is None


def test_hoje_e_data_local():
    assert hoje() == timezone.localdate()


# ── Desempenho ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_desempenho_com_organograma_grande(django_assert_max_num_queries):
    """Aceite ⑥ do ST-014: a home chama ~40 vezes e não pode explodir.

    Aqui medimos o que é determinístico — número de queries. Tempo de parede
    varia demais entre máquina local e CI para virar asserção útil.
    """
    chefe = f.pessoa("chefe")
    f.lotar(chefe)
    gerentes = []
    for i in range(10):
        g = f.pessoa(f"ger{i}")
        f.lotar(g, gestor=chefe)
        gerentes.append(g)
    for i, g in enumerate(gerentes):
        for j in range(9):
            f.lotar(f.pessoa(f"col{i}_{j}"), gestor=g)

    f.atribuir(chefe, f.papel("gestor", ["rh.ler.equipe"], escopo="equipe"))
    alvo = gerentes[0]

    cache: dict = {}
    # 3 queries, sempre: atribuições vigentes + delegações recebidas + a CTE de
    # liderados. As outras 39 chamadas fazem ZERO — é isso que o teste protege.
    # O número absoluto importa menos que ele não crescer com a quantidade de
    # chamadas nem com o tamanho do organograma.
    with django_assert_max_num_queries(3):
        for _ in range(40):
            assert pode(chefe, "rh.ler", alvo=alvo, cache=cache) is True


@pytest.mark.django_db
def test_escopo_de_ignora_permissao_de_outro_dominio():
    """A pessoa tem permissão, mas não a pedida — o laço precisa seguir."""
    u = f.pessoa("ana")
    f.atribuir(u, f.papel("fin", ["fin.ler.global"], escopo="global"))
    assert escopo_de(u, "rh.ler") is None
    assert escopo_de(u, "fin.ler") == "global"
