"""A concentração — §E1, a terceira categoria da faixa de destaques.

Destaque e ponto de atenção são derivados de regra e ninguém os edita. A
concentração é a única coisa desta tela que uma pessoa escreve, e por isso é a
única que precisa de permissão, de limite e de histórico.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.models import Concentracao
from workspace.services import concentracao as svc

pytestmark = pytest.mark.django_db


@pytest.fixture
def diretor(db):
    pessoa = f.pessoa("dir_conc", nome="Diretor")
    f.lotar(pessoa, centro_custo_codigo="1042")
    f.atribuir(
        pessoa,
        f.papel(
            "dir_conc_papel",
            ["eco.ler.global", "eco.concentrar.global"],
            escopo="global",
        ),
        escopo="global",
    )
    return pessoa


@pytest.fixture
def leitor(db):
    """Lê o resultado e NÃO decide onde a empresa se concentra."""
    pessoa = f.pessoa("leitor_conc", nome="Leitor")
    f.lotar(pessoa, centro_custo_codigo="1042")
    f.atribuir(
        pessoa,
        f.papel("leitor_conc_papel", ["eco.ler.global"], escopo="global"),
        escopo="global",
    )
    return pessoa


def _abrir(pessoa, **campos):
    return svc.abrir(
        pessoa,
        origem_tipo=campos.pop("origem_tipo", "contrato"),
        origem_ref=campos.pop("origem_ref", "CT-107"),
        titulo=campos.pop("titulo", "Recuperar a margem"),
        motivo=campos.pop("motivo", "Garantia e retrabalho acima do normal."),
        responsavel=campos.pop("responsavel", pessoa),
        **campos,
    )


# ── Quem pode ──────────────────────────────────────────────────────


def test_ler_resultado_NAO_da_direito_de_marcar(leitor):
    """Declarar onde a empresa vai se concentrar é de quem responde pelo
    período. Com `eco.ler`, R.H. e Financeiro editariam a lista de foco da
    diretoria — e uma lista que qualquer um edita deixa de ser foco."""
    assert not svc.pode_concentrar(leitor)
    with pytest.raises(svc.ConcentracaoError):
        _abrir(leitor)


def test_a_diretoria_marca(diretor):
    assert svc.pode_concentrar(diretor)
    assert _abrir(diretor).pk


# ── O motivo e o resultado, obrigatórios ────────────────────────────


def test_sem_MOTIVO_nao_abre(diretor):
    """Uma concentração sem motivo é um item de lista, e listas de itens sem
    motivo é o que reuniões produzem quando ninguém decide nada."""
    with pytest.raises(svc.ConcentracaoError, match="POR QUE"):
        _abrir(diretor, motivo="   ")


def test_sem_RESULTADO_nao_encerra(diretor):
    """Encerrar sem dizer o que aconteceu transformaria o histórico numa lista
    de datas — e a pergunta que ele existe para responder ficaria sem resposta."""
    foco = _abrir(diretor)

    with pytest.raises(svc.ConcentracaoError, match="o que aconteceu"):
        svc.encerrar(foco, diretor, "  ")

    foco.refresh_from_db()
    assert foco.aberta


def test_sem_titulo_ou_referencia_nao_abre(diretor):
    with pytest.raises(svc.ConcentracaoError):
        _abrir(diretor, titulo="")
    with pytest.raises(svc.ConcentracaoError):
        _abrir(diretor, origem_ref="")


def test_origem_invalida_nao_abre(diretor):
    with pytest.raises(svc.ConcentracaoError):
        _abrir(diretor, origem_tipo="chute")


# ── O limite ────────────────────────────────────────────────────────


def test_o_sexto_foco_obriga_a_encerrar_um(diretor):
    """Não é limite técnico: é o que "concentração" quer dizer. Uma lista de
    quinze focos é uma lista de tarefas, e a diretoria já tem uma."""
    for i in range(svc.MAXIMO_ABERTAS):
        _abrir(diretor, origem_ref=f"CT-{i}")

    with pytest.raises(svc.ConcentracaoError, match="Encerre uma"):
        _abrir(diretor, origem_ref="CT-X")


def test_encerrar_libera_a_vaga(diretor):
    focos = [_abrir(diretor, origem_ref=f"CT-{i}") for i in range(svc.MAXIMO_ABERTAS)]
    svc.encerrar(focos[0], diretor, "Renegociado.")

    assert _abrir(diretor, origem_ref="CT-X").pk


# ── O histórico ─────────────────────────────────────────────────────


def test_encerrada_sai_das_abertas_e_entra_no_historico(diretor):
    foco = _abrir(diretor)
    svc.encerrar(foco, diretor, "Margem recuperada em dois meses.")

    assert svc.abertas() == []
    assert [c.pk for c in svc.encerradas()] == [foco.pk]
    assert svc.encerradas()[0].resultado.startswith("Margem recuperada")


def test_nao_ha_caminho_de_exclusao():
    """Encerrar é o fim da vida de uma concentração. Um botão de excluir
    apagaria, uma decisão de cada vez, a resposta a "a empresa resolve o que
    decide olhar?"."""
    assert not hasattr(svc, "excluir")
    assert not hasattr(svc, "apagar")


def test_encerrar_duas_vezes_avisa_em_vez_de_estourar(diretor):
    """Duas pessoas na mesma reunião, dois cliques. A segunda precisa de uma
    frase, e não de um 500."""
    foco = _abrir(diretor)
    svc.encerrar(foco, diretor, "Feito.")

    with pytest.raises(svc.ConcentracaoError, match="já foi encerrada"):
        svc.encerrar(foco, diretor, "De novo.")


# ── O prazo ─────────────────────────────────────────────────────────


def test_sem_prazo_a_tela_NAO_cobra(diretor):
    """Concentração sem prazo é decisão em aberto. Chamá-la de atrasada faria a
    tela cobrar quem ainda não se comprometeu com data nenhuma."""
    foco = _abrir(diretor, prazo=None)

    assert not foco.atrasada
    assert foco.dias_para_o_prazo is None
    assert Concentracao.objects.atrasadas().count() == 0


def test_prazo_vencido_conta_os_dias_em_positivo(diretor):
    ontem = timezone.localdate() - timedelta(days=3)
    foco = _abrir(diretor, prazo=ontem)

    assert foco.atrasada
    assert foco.dias_para_o_prazo == -3
    assert foco.dias_de_atraso == 3


def test_encerrada_deixa_de_contar_prazo(diretor):
    foco = _abrir(diretor, prazo=timezone.localdate() - timedelta(days=3))
    svc.encerrar(foco, diretor, "Resolvido.")

    assert not foco.atrasada
    assert foco.dias_para_o_prazo is None


# ── Na tela ─────────────────────────────────────────────────────────


def _tela(client):
    return client.get(reverse("workspace:resultados")).content.decode()


def test_a_lista_aparece_MESMO_sem_cartao_disparando(client, diretor):
    """A concentração é decisão humana e existe independentemente de o mês estar
    tranquilo — aliás, é no mês tranquilo que ela mais importa, porque é quando
    dá para atacar o que se decidiu em vez de apagar incêndio."""
    _abrir(diretor, titulo="Recuperar CT-107")
    client.force_login(diretor)

    corpo = _tela(client)

    assert "Onde estamos concentrados" in corpo
    assert "Recuperar CT-107" in corpo


def test_quem_nao_pode_marcar_VE_a_lista_e_nao_o_formulario(client, diretor, leitor):
    _abrir(diretor, titulo="Recuperar CT-107")
    client.force_login(leitor)

    corpo = _tela(client)

    assert "Recuperar CT-107" in corpo
    assert "Marcar uma concentração" not in corpo


def test_abrir_e_encerrar_pela_tela(client, diretor):
    client.force_login(diretor)

    client.post(
        reverse("workspace:concentracao_abrir"),
        {
            "origem_tipo": "contrato", "origem_ref": "CT-107",
            "titulo": "Recuperar a margem", "motivo": "Retrabalho alto.",
            "responsavel": str(diretor.pk),
        },
    )
    foco = Concentracao.objects.get()

    client.post(
        reverse("workspace:concentracao_encerrar", args=[foco.pk]),
        {"resultado": "Renegociado com o cliente."},
    )

    foco.refresh_from_db()
    assert not foco.aberta
    assert foco.resultado == "Renegociado com o cliente."


def test_GET_nao_abre_concentracao(client, diretor):
    """`GET` faria um prefetch do navegador abrir um foco sozinho."""
    client.force_login(diretor)

    assert client.get(reverse("workspace:concentracao_abrir")).status_code == 405
    assert Concentracao.objects.count() == 0


def test_o_erro_volta_como_MENSAGEM_e_nao_como_500(client, diretor):
    client.force_login(diretor)

    resposta = client.post(
        reverse("workspace:concentracao_abrir"),
        {"origem_tipo": "contrato", "origem_ref": "CT-1", "titulo": "x",
         "motivo": "", "responsavel": str(diretor.pk)},
        follow=True,
    )

    assert resposta.status_code == 200
    assert Concentracao.objects.count() == 0
    assert any("POR QUE" in str(m) for m in resposta.context["messages"])


# ── A categoria positiva ────────────────────────────────────────────


def test_existe_cartao_de_destaque_positivo(client, diretor):
    """Até 09/09/2026 TODO cartão era um problema, e a faixa se chamava
    "Destaques e pontos de atenção" mostrando só a segunda metade do nome. Um
    painel em que nada nunca dá certo ensina que a tela é lugar de má notícia."""
    from workspace.services import resultados as res

    faixa = res.Faixa(chave="contratos", titulo="t", fonte="p")

    class _C:
        def __init__(self, pct):
            self.margem_contribuicao_pct = Decimal(pct)
            self.valor_mensal = Decimal("100")
            self.codigo = "X"

    faixa.conteudo = {"carteira": [_C("30"), _C("25"), _C("5")]}

    cartoes = res._cartoes_do_que_foi_bem({"contratos": faixa})

    assert [c.severidade for c in cartoes] == ["bom"]
    assert "2 de 3" in cartoes[0].valor


def test_destaque_NAO_dispara_quando_os_bons_sao_minoria():
    """Três contratos bons numa carteira de trinta não são um destaque da
    empresa — são três contratos bons. Destaque barato desvaloriza destaque."""
    from workspace.services import resultados as res

    faixa = res.Faixa(chave="contratos", titulo="t", fonte="p")

    class _C:
        def __init__(self, pct):
            self.margem_contribuicao_pct = Decimal(pct)
            self.valor_mensal = Decimal("100")
            self.codigo = "X"

    faixa.conteudo = {"carteira": [_C("30"), _C("5"), _C("5")]}

    assert res._cartoes_do_que_foi_bem({"contratos": faixa}) == []
