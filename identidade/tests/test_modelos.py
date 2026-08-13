"""Modelos de IDN — validações que protegem o grafo."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from identidade.models import (
    AtribuicaoPapel,
    Lotacao,
    Papel,
    Situacao,
    abrangencia,
)
from identidade.tests import fabricas as f


# ── Hierarquia de escopo ────────────────────────────────────────────


@pytest.mark.parametrize(
    ("menor", "maior"),
    [
        ("proprio", "equipe"),
        ("equipe", "departamento"),
        ("departamento", "unidade"),
        ("unidade", "global"),
    ],
)
def test_hierarquia_de_escopo_e_crescente(menor, maior):
    assert abrangencia(menor) < abrangencia(maior)


def test_escopo_desconhecido_e_o_mais_restrito():
    assert abrangencia("inventado") == -1


# ── Organograma ─────────────────────────────────────────────────────


@pytest.mark.django_db
def test_pessoa_nao_pode_ser_gestora_de_si_mesma():
    u = f.pessoa("ana")
    lot = Lotacao(user=u, gestor=u)
    with pytest.raises(ValidationError, match="gestora de si mesma"):
        lot.clean()


@pytest.mark.django_db
def test_ciclo_direto_e_rejeitado():
    """A → B → A. O caso que trava qualquer travessia recursiva."""
    a, b = f.pessoa("a"), f.pessoa("b")
    f.lotar(a)
    lot_b = f.lotar(b, gestor=a)

    lot_a = Lotacao.objects.get(user=a)
    lot_a.gestor = b
    with pytest.raises(ValidationError, match="ciclo"):
        lot_a.clean()
    assert lot_b.gestor_id == a.pk


@pytest.mark.django_db
def test_ciclo_indireto_e_rejeitado():
    """A → B → C → A, três níveis."""
    a, b, c = (f.pessoa(n) for n in ("a", "b", "c"))
    f.lotar(a)
    f.lotar(b, gestor=a)
    f.lotar(c, gestor=b)

    lot_a = Lotacao.objects.get(user=a)
    lot_a.gestor = c
    with pytest.raises(ValidationError, match="ciclo"):
        lot_a.clean()


@pytest.mark.django_db
def test_cadeia_valida_passa():
    a, b, c = (f.pessoa(n) for n in ("a", "b", "c"))
    f.lotar(a)
    f.lotar(b, gestor=a)
    lot_c = Lotacao(user=c, gestor=b)
    lot_c.clean()  # não levanta


@pytest.mark.django_db
def test_sem_gestor_passa():
    Lotacao(user=f.pessoa("topo")).clean()


@pytest.mark.django_db
def test_lotacao_ativas_exclui_desligado():
    ativo, desligado = f.pessoa("ativo"), f.pessoa("desligado")
    f.lotar(ativo)
    f.lotar(desligado, situacao=Situacao.DESLIGADO)

    ids = set(Lotacao.objects.ativas().values_list("user_id", flat=True))
    assert ids == {ativo.pk}


@pytest.mark.django_db
def test_str_de_lotacao_identifica_pessoa_e_cargo():
    u = f.pessoa("ana")
    assert "sem cargo" in str(f.lotar(u))
    assert "Analista" in str(f.lotar(f.pessoa("bruno"), cargo="Analista"))


# ── Papel ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_papel_recusa_permissoes_que_nao_sao_lista():
    p = Papel(chave="x", nome="X", permissoes="rh.ler")
    with pytest.raises(ValidationError, match="lista de strings"):
        p.clean()


@pytest.mark.django_db
@pytest.mark.parametrize("ruim", [[""], ["  "], [None], [123]])
def test_papel_recusa_permissao_invalida(ruim):
    p = Papel(chave="x", nome="X", permissoes=ruim)
    with pytest.raises(ValidationError, match="Permissão inválida"):
        p.clean()


@pytest.mark.django_db
def test_papel_aceita_lista_valida():
    Papel(chave="x", nome="X", permissoes=["rh.ler.equipe", "*"]).clean()


@pytest.mark.django_db
def test_str_de_papel_e_o_nome():
    assert str(f.papel("gestor", [])) == "Gestor"


# ── Atribuição ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_vigencia_invertida_e_rejeitada():
    hoje_ = timezone.localdate()
    a = AtribuicaoPapel(
        user=f.pessoa("ana"),
        papel=f.papel("p", []),
        escopo="proprio",
        vigencia_inicio=hoje_,
        vigencia_fim=hoje_ - timedelta(days=1),
    )
    with pytest.raises(ValidationError, match="antes do início"):
        a.clean()


@pytest.mark.django_db
def test_escopo_unidade_exige_unidade():
    a = AtribuicaoPapel(
        user=f.pessoa("ana"), papel=f.papel("p", []), escopo="unidade",
        vigencia_inicio=timezone.localdate(),
    )
    with pytest.raises(ValidationError, match="exige a unidade"):
        a.clean()


@pytest.mark.django_db
def test_escopo_departamento_exige_departamento():
    a = AtribuicaoPapel(
        user=f.pessoa("ana"), papel=f.papel("p", []), escopo="departamento",
        vigencia_inicio=timezone.localdate(),
    )
    with pytest.raises(ValidationError, match="exige o departamento"):
        a.clean()


@pytest.mark.django_db
def test_escopo_proprio_nao_exige_alvo():
    AtribuicaoPapel(
        user=f.pessoa("ana"), papel=f.papel("p", []), escopo="proprio",
        vigencia_inicio=timezone.localdate(),
    ).clean()


@pytest.mark.django_db
def test_atribuicao_duplicada_e_rejeitada_pelo_banco():
    """Constraint no banco, não só no formulário: duas atribuições idênticas
    dobrariam o resultado de toda consulta de concessão."""
    u, p = f.pessoa("ana"), f.papel("p", ["rh.ler"])
    hoje_ = timezone.localdate()
    f.atribuir(u, p, inicio=hoje_)
    with pytest.raises(IntegrityError), transaction.atomic():
        f.atribuir(u, p, inicio=hoje_)


@pytest.mark.django_db
def test_propriedade_vigente():
    hoje_ = timezone.localdate()
    u, p = f.pessoa("ana"), f.papel("p", [])
    assert f.atribuir(u, p, inicio=hoje_).vigente is True
    assert f.atribuir(u, p, inicio=hoje_ + timedelta(days=1)).vigente is False
    assert f.atribuir(
        u, p, inicio=hoje_ - timedelta(days=10), fim=hoje_ - timedelta(days=1)
    ).vigente is False


@pytest.mark.django_db
def test_str_de_atribuicao():
    u, p = f.pessoa("ana"), f.papel("gestor", [])
    assert str(f.atribuir(u, p)) == "ana · gestor · proprio"


# ── Delegação ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_nao_delega_para_si_mesmo():
    from identidade.models import Delegacao

    u = f.pessoa("ana")
    hoje_ = timezone.localdate()
    d = Delegacao(de_user=u, para_user=u, inicio=hoje_, fim=hoje_)
    with pytest.raises(ValidationError, match="para si mesmo"):
        d.clean()


@pytest.mark.django_db
def test_delegacao_com_periodo_invertido_e_rejeitada():
    from identidade.models import Delegacao

    hoje_ = timezone.localdate()
    d = Delegacao(
        de_user=f.pessoa("a"), para_user=f.pessoa("b"),
        inicio=hoje_, fim=hoje_ - timedelta(days=1),
    )
    with pytest.raises(ValidationError, match="antes do início"):
        d.clean()


@pytest.mark.django_db
def test_delegacao_valida_passa():
    from identidade.models import Delegacao

    hoje_ = timezone.localdate()
    Delegacao(
        de_user=f.pessoa("a"), para_user=f.pessoa("b"),
        inicio=hoje_, fim=hoje_ + timedelta(days=5),
    ).clean()


@pytest.mark.django_db
def test_propriedade_vigente_de_delegacao():
    hoje_ = timezone.localdate()
    a, b = f.pessoa("a"), f.pessoa("b")
    assert f.delegar(a, b, hoje_, hoje_ + timedelta(days=1)).vigente is True
    assert f.delegar(a, b, hoje_ + timedelta(days=1), hoje_ + timedelta(days=2)).vigente is False
    assert f.delegar(a, b, hoje_, hoje_ + timedelta(days=1), ativa=False).vigente is False


@pytest.mark.django_db
def test_str_de_delegacao():
    assert str(f.delegar(
        f.pessoa("a"), f.pessoa("b"), timezone.localdate(), timezone.localdate()
    )) == "a → b"


# ── Estrutura ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_str_de_unidade_e_departamento():
    assert str(f.unidade("SP", "Matriz")) == "SP · Matriz"
    assert str(f.departamento("TI", "Tecnologia")) == "TI · Tecnologia"


@pytest.mark.django_db
def test_atribuicao_vigentes_respeita_data_informada():
    """`vigentes(em=...)` permite responder "quem podia em tal data?" — é o que
    uma auditoria pergunta."""
    u, p = f.pessoa("ana"), f.papel("p", ["rh.ler"])
    hoje_ = timezone.localdate()
    f.atribuir(u, p, inicio=hoje_ - timedelta(days=10), fim=hoje_ - timedelta(days=5))

    assert AtribuicaoPapel.objects.vigentes().count() == 0
    assert AtribuicaoPapel.objects.vigentes(em=hoje_ - timedelta(days=7)).count() == 1


@pytest.mark.django_db
def test_cadeia_mais_profunda_que_o_teto_nao_trava():
    """O teto de 64 níveis é a rede contra ciclo pré-existente. Organograma
    legítimo mais fundo que isso não deve travar nem acusar ciclo falso."""
    anterior = None
    for i in range(66):
        u = f.pessoa(f"n{i:03d}")
        f.lotar(u, gestor=anterior)
        anterior = u

    folha = Lotacao.objects.get(user__email="n065@icodev.com.br")
    assert folha._cria_ciclo() is False
