"""`semear_papeis` — cria os papéis do Portal.

Os papéis do Portal NÃO são os do iConnect: aquela plataforma tem 1432 técnicos
e clientes; o Portal é dos funcionários da icodev.
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command

from identidade.models import Papel
from identidade.papeis import AUTOATENDIMENTO, PAPEIS_V1


def semear(**kwargs) -> str:
    saida = StringIO()
    call_command("semear_papeis", stdout=saida, stderr=saida, **kwargs)
    return saida.getvalue()


# ── Semeadura ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_simulacao_nao_grava():
    texto = semear()
    assert "SIMULAÇÃO" in texto
    assert Papel.objects.count() == 0


@pytest.mark.django_db
def test_aplicar_cria_todos_os_papeis():
    semear(aplicar=True)
    assert set(Papel.objects.values_list("chave", flat=True)) == {
        p["chave"] for p in PAPEIS_V1
    }


@pytest.mark.django_db
def test_reexecutavel_sem_duplicar():
    semear(aplicar=True)
    antes = Papel.objects.count()
    texto = semear(aplicar=True)
    assert Papel.objects.count() == antes
    assert f"sem mudança  {antes}" in texto


@pytest.mark.django_db
def test_atualiza_quando_a_lista_de_permissoes_muda():
    semear(aplicar=True)
    gestor = Papel.objects.get(chave="gestor")
    gestor.permissoes = ["obsoleto"]
    gestor.save()

    texto = semear(aplicar=True)
    gestor.refresh_from_db()
    assert "apr.aprovar.equipe" in gestor.permissoes
    assert "atualizados  1" in texto


@pytest.mark.django_db
def test_nao_mexe_em_papel_criado_a_mao():
    """Papel que a empresa inventou não é apagado nem alterado."""
    Papel.objects.create(chave="jurídico-interno", nome="Jurídico", permissoes=["jur.ler"])
    semear(aplicar=True)

    assert Papel.objects.get(chave="jurídico-interno").permissoes == ["jur.ler"]


@pytest.mark.django_db
def test_nao_atribui_papel_a_ninguem():
    """Atribuir papel é ato deliberado: admin ou CSV, nunca efeito colateral."""
    from identidade.models import AtribuicaoPapel

    semear(aplicar=True)
    assert AtribuicaoPapel.objects.count() == 0


# ── Coerência do conjunto ───────────────────────────────────────────


def test_chaves_sao_unicas():
    chaves = [p["chave"] for p in PAPEIS_V1]
    assert len(chaves) == len(set(chaves))


def test_todo_papel_tem_descricao():
    """Papel sem descrição é papel que ninguém sabe quando atribuir."""
    sem = [p["chave"] for p in PAPEIS_V1 if not p.get("descricao", "").strip()]
    assert sem == []


def test_todo_papel_tem_ao_menos_uma_permissao():
    vazios = [p["chave"] for p in PAPEIS_V1 if not p["permissoes"]]
    assert vazios == []


def test_permissoes_seguem_o_formato_pontuado():
    """`<dominio>.<acao>` no mínimo, todos os segmentos preenchidos.

    Terminar em escopo é OPCIONAL: `rh.ler.equipe` traz o escopo embutido;
    `ti.status.ler` não traz, e aí vale o escopo da atribuição. As duas formas
    são válidas e `_casa_permissao` trata ambas.
    """
    for papel in PAPEIS_V1:
        for permissao in papel["permissoes"]:
            partes = permissao.split(".")
            assert len(partes) >= 2, f"{papel['chave']}: {permissao!r} sem domínio.ação"
            assert all(partes), f"{papel['chave']}: {permissao!r} tem segmento vazio"
            assert permissao == permissao.lower(), (
                f"{papel['chave']}: {permissao!r} deveria ser minúscula"
            )


def test_escopo_embutido_quando_existe_e_valido():
    """Um escopo escrito errado (`rh.ler.equipes`) seria tratado como AÇÃO e a
    permissão nunca casaria. Este teste pega o erro de digitação."""
    from identidade.models import HIERARQUIA_ESCOPO

    quase_escopos = {"equipes", "unidades", "departamentos", "proprios", "globais", "todos"}
    for papel in PAPEIS_V1:
        for permissao in papel["permissoes"]:
            ultimo = permissao.split(".")[-1]
            assert ultimo not in quase_escopos, (
                f"{papel['chave']}: {permissao!r} — escopo válido é um de "
                f"{HIERARQUIA_ESCOPO}"
            )


def test_todo_papel_de_funcionario_inclui_autoatendimento():
    """Quem trabalha na empresa vê as próprias férias. As exceções são papéis
    que não descrevem um funcionário: monitoramento (posto 24h) e auditoria
    (pode ser externa)."""
    excecoes = {"monitoramento", "auditoria"}
    for papel in PAPEIS_V1:
        if papel["chave"] in excecoes:
            continue
        faltando = set(AUTOATENDIMENTO) - set(papel["permissoes"])
        assert not faltando, f"{papel['chave']} não tem: {sorted(faltando)}"


def test_monitoramento_nao_despacha():
    """Turno de 12h com poder de despacho e sem supervisão é onde acidente
    operacional acontece."""
    papel = next(p for p in PAPEIS_V1 if p["chave"] == "monitoramento")
    assert not any("despachar" in p for p in papel["permissoes"])
    assert not any("aprovar" in p for p in papel["permissoes"])


def test_compras_nao_aprova():
    """Quem pede não aprova, quem aprova não compra, quem compra não recebe."""
    papel = next(p for p in PAPEIS_V1 if p["chave"] == "compras")
    assert not any(p.startswith("com.aprovar") for p in papel["permissoes"])


def test_logistica_nao_fecha_inventario():
    """Segregação de função: quem conta não fecha."""
    papel = next(p for p in PAPEIS_V1 if p["chave"] == "logistica")
    assert "log.inventario.contar.unidade" in papel["permissoes"]
    assert not any("inventario.fechar" in p for p in papel["permissoes"])


def test_so_diretoria_libera_excecao_de_habilitacao():
    """Se qualquer gestor liberasse, o bloqueio de despacho seria decorativo."""
    com_excecao = [
        p["chave"] for p in PAPEIS_V1 if "ops.excecao.certificacao" in p["permissoes"]
    ]
    assert com_excecao == ["diretoria"]


def test_sesmt_valida_evidencia_e_operacao_nao():
    """Quem coordena a operação tem incentivo para liberar o técnico."""
    sesmt = next(p for p in PAPEIS_V1 if p["chave"] == "sesmt")
    operacao = next(p for p in PAPEIS_V1 if p["chave"] == "operacao")
    assert "hab.validar.evidencia" in sesmt["permissoes"]
    assert "hab.validar.evidencia" not in operacao["permissoes"]


def test_auditoria_e_somente_leitura():
    """O auditor pode ser externo — cliente auditando fornecedor."""
    papel = next(p for p in PAPEIS_V1 if p["chave"] == "auditoria")
    escrita = [
        p
        for p in papel["permissoes"]
        if any(verbo in p for verbo in ("aprovar", "publicar", "admin", "movimentar", "editar"))
    ]
    assert escrita == []


def test_nenhum_papel_usa_curinga_total():
    """`*` só faz sentido para superusuário do Django, que já passa direto em
    `pode()`. Papel com `*` seria um admin paralelo, sem trilha."""
    for papel in PAPEIS_V1:
        assert "*" not in papel["permissoes"], papel["chave"]


# ── Integração com pode() ───────────────────────────────────────────


@pytest.mark.django_db
def test_papel_semeado_funciona_em_pode():
    from identidade.services import pode
    from identidade.tests import fabricas as f

    semear(aplicar=True)
    ana = f.pessoa("ana")
    f.atribuir(ana, Papel.objects.get(chave="colaborador"))

    assert pode(ana, "rh.ler", alvo=ana) is True
    assert pode(ana, "apr.aprovar") is False


@pytest.mark.django_db
def test_gestor_semeado_alcanca_a_equipe():
    from identidade.services import pode
    from identidade.tests import fabricas as f

    semear(aplicar=True)
    chefe, liderado, fora = (f.pessoa(n) for n in ("chefe", "lid", "fora"))
    f.lotar(chefe)
    f.lotar(liderado, gestor=chefe)
    f.lotar(fora)
    f.atribuir(chefe, Papel.objects.get(chave="gestor"), escopo="equipe")

    assert pode(chefe, "rh.ler", alvo=liderado) is True
    assert pode(chefe, "rh.ler", alvo=fora) is False
