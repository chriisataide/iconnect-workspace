"""A tela de pessoas e papéis — quem aprova o quê.

O `/admin/` do Django faz isso desde o primeiro dia. O que ele não faz é ser
usável por quem precisa: o R.H. que vai cadastrar o aprovador de Compras não
sabe o que é `AtribuicaoPapel`, e não tem como saber que escopo `global` dá à
pessoa acesso a todos os pedidos da empresa.

O que estes testes protegem:

1. **A tela é de quem administra** — e mais ninguém.
2. **Escopo amplo exige justificativa escrita**, porque é decisão e não
   configuração.
3. **Revogar encerra, não apaga**: "quem aprovava isso em março?" continua
   respondível.
4. **Área sem aprovador aparece marcada** — é o defeito que a tela existe para
   mostrar.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.models import AtribuicaoPapel, Papel
from identidade.services import administracao as adm
from workspace.services import mapa_aprovacao as mapa
from identidade.services.administracao import AdministracaoError
from identidade.tests import fabricas as f

pytestmark = pytest.mark.django_db


@pytest.fixture
def gente():
    rh, ana = f.pessoa("rh"), f.pessoa("ana")
    f.lotar(rh)
    f.lotar(ana)
    f.atribuir(rh, f.papel("rh-admin", ["rh.admin.global"], escopo="global"))
    papel_compras = f.papel("compras", ["com.aprovar.unidade"], escopo="unidade")
    return {"rh": rh, "ana": ana, "papel": papel_compras}


# ── Quem entra ──────────────────────────────────────────────────────


def test_a_tela_e_de_quem_administra(client, gente):
    client.force_login(gente["rh"])
    assert client.get(reverse("workspace:pessoas")).status_code == 200


def test_colaborador_comum_nao_entra(client, gente):
    """Ver quem aprova o quê é mapa de poder da empresa — e a tela também
    CONCEDE. Não é informação institucional."""
    client.force_login(gente["ana"])
    assert client.get(reverse("workspace:pessoas")).status_code == 403


def test_sem_sessao_manda_se_identificar(client, gente):
    resposta = client.get(reverse("workspace:pessoas"))
    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/entrar/")


# ── Conceder ────────────────────────────────────────────────────────


def test_conceder_registra_quem_concedeu(gente):
    """`concedido_por` é obrigatório aqui e opcional no admin. Concessão sem
    autor não responde à única pergunta que importa depois de um incidente."""
    atribuicao = adm.conceder(
        pessoa=gente["ana"], papel=gente["papel"], escopo="proprio", quem=gente["rh"]
    )

    assert atribuicao.concedido_por == gente["rh"]
    assert atribuicao.vigencia_fim is None


def test_escopo_amplo_exige_justificativa(gente):
    """É a diferença entre "aprova a própria equipe" e "aprova a empresa
    inteira", e no admin as duas são uma opção num `<select>` idêntico."""
    with pytest.raises(AdministracaoError, match="por que este acesso"):
        adm.conceder(
            pessoa=gente["ana"], papel=gente["papel"], escopo="global",
            quem=gente["rh"],
        )

    atribuicao = adm.conceder(
        pessoa=gente["ana"], papel=gente["papel"], escopo="global",
        quem=gente["rh"], justificativa="Cobre o diretor durante a licença",
    )
    assert "licença" in atribuicao.justificativa


def test_papel_para_quem_nao_tem_lotacao_e_recusado(gente):
    """Aprovador sem unidade e sem gestor é a origem das 881 lotações vazias
    que fizeram este produto existir separado."""
    solto = f.pessoa("terceiro")

    with pytest.raises(AdministracaoError, match="não tem lotação"):
        adm.conceder(
            pessoa=solto, papel=gente["papel"], escopo="proprio", quem=gente["rh"]
        )


def test_nao_concede_duas_vezes_o_mesmo(gente):
    adm.conceder(
        pessoa=gente["ana"], papel=gente["papel"], escopo="proprio", quem=gente["rh"]
    )
    with pytest.raises(AdministracaoError, match="já tem"):
        adm.conceder(
            pessoa=gente["ana"], papel=gente["papel"], escopo="proprio",
            quem=gente["rh"],
        )


def test_data_de_termino_no_passado_e_recusada(gente):
    with pytest.raises(AdministracaoError, match="já passou"):
        adm.conceder(
            pessoa=gente["ana"], papel=gente["papel"], escopo="proprio",
            quem=gente["rh"], vigencia_fim=timezone.localdate() - timedelta(days=1),
        )


def test_quem_nao_administra_nao_concede(gente):
    with pytest.raises(AdministracaoError, match="não pode conceder"):
        adm.conceder(
            pessoa=gente["ana"], papel=gente["papel"], escopo="proprio",
            quem=gente["ana"],
        )


# ── Revogar ─────────────────────────────────────────────────────────


def test_revogar_encerra_sem_apagar(gente):
    """A pergunta "quem aprovava isso em março?" tem de continuar respondível
    depois que a pessoa muda de área."""
    atribuicao = adm.conceder(
        pessoa=gente["ana"], papel=gente["papel"], escopo="proprio", quem=gente["rh"]
    )

    # Concedido ONTEM: é o caso comum, e o que permite testar o corte imediato.
    atribuicao.vigencia_inicio = timezone.localdate() - timedelta(days=1)
    atribuicao.save(update_fields=["vigencia_inicio"])

    adm.revogar(atribuicao, gente["rh"], motivo="Mudou de área")

    atribuicao.refresh_from_db()
    assert AtribuicaoPapel.objects.filter(pk=atribuicao.pk).exists(), "a linha fica"
    assert "Mudou de área" in atribuicao.justificativa
    # Vale ATÉ ONTEM: `vigentes()` inclui o dia de fim, e "encerrar" que só faz
    # efeito à meia-noite não encerra nada para quem apertou o botão porque a
    # pessoa saiu da empresa hoje.
    assert atribuicao.vigencia_fim == timezone.localdate() - timedelta(days=1)
    assert not AtribuicaoPapel.objects.vigentes().filter(pk=atribuicao.pk).exists()


def test_revogar_no_mesmo_dia_da_concessao_nao_termina_antes_de_comecar(gente):
    """A borda: papel dado e tirado no mesmo dia. Ele vale até a meia-noite —
    é um acesso de minutos, dado e tirado pela mesma pessoa, e uma vigência que
    termina antes de começar seria uma linha impossível no histórico."""
    atribuicao = adm.conceder(
        pessoa=gente["ana"], papel=gente["papel"], escopo="proprio", quem=gente["rh"]
    )

    adm.revogar(atribuicao, gente["rh"])

    atribuicao.refresh_from_db()
    assert atribuicao.vigencia_fim == atribuicao.vigencia_inicio


def test_nao_revoga_duas_vezes(gente):
    atribuicao = adm.conceder(
        pessoa=gente["ana"], papel=gente["papel"], escopo="proprio", quem=gente["rh"]
    )
    adm.revogar(atribuicao, gente["rh"])

    with pytest.raises(AdministracaoError, match="já estava encerrado"):
        adm.revogar(atribuicao, gente["rh"])


# ── O mapa de aprovação ─────────────────────────────────────────────


def test_area_sem_aprovador_aparece_marcada(gente):
    """O defeito que a tela existe para mostrar: a cadeia manda o pedido para um
    papel que não tem dono, e ele fica parado sem que ninguém seja avisado."""
    from decimal import Decimal

    from workspace.models.aprovacao import RegraAprovacao, TipoAprovador

    RegraAprovacao.objects.create(
        dominio="com.", ordem=15, valor_minimo=Decimal("0"),
        tipo=TipoAprovador.PAPEL, papel=gente["papel"],
    )

    orfas = [linha for linha in mapa.resumo_de_aprovacao() if linha["orfa"]]
    assert [linha["dominio"] for linha in orfas] == ["com."]

    adm.conceder(
        pessoa=gente["ana"], papel=gente["papel"], escopo="unidade",
        quem=gente["rh"], justificativa="Responsável pela área",
    )
    assert not [linha for linha in mapa.resumo_de_aprovacao() if linha["orfa"]]


def test_a_tela_mostra_o_mapa_e_a_area_orfa(client, gente):
    from decimal import Decimal

    from workspace.models.aprovacao import RegraAprovacao, TipoAprovador

    RegraAprovacao.objects.create(
        dominio="com.", ordem=15, valor_minimo=Decimal("0"),
        tipo=TipoAprovador.PAPEL, papel=gente["papel"],
    )
    client.force_login(gente["rh"])

    corpo = client.get(reverse("workspace:pessoas")).content.decode()
    assert "com." in corpo
    assert "o pedido fica parado" in corpo


def test_conceder_pela_tela(client, gente):
    client.force_login(gente["rh"])

    client.post(
        reverse("workspace:conceder_papel"),
        {
            "pessoa": gente["ana"].pk,
            "papel": gente["papel"].pk,
            "escopo": "unidade",
            "justificativa": "Passa a responder por Compras da base",
        },
    )

    assert AtribuicaoPapel.objects.vigentes().filter(
        user=gente["ana"], papel=gente["papel"]
    ).exists()


def test_conceder_sem_justificativa_pela_tela_explica(client, gente):
    client.force_login(gente["rh"])

    resposta = client.post(
        reverse("workspace:conceder_papel"),
        {"pessoa": gente["ana"].pk, "papel": gente["papel"].pk, "escopo": "global"},
        follow=True,
    )

    assert "Escreva por que" in resposta.content.decode()
    assert not AtribuicaoPapel.objects.filter(user=gente["ana"]).exists()


def test_o_trilho_mostra_administrar_so_para_quem_administra(client, gente):
    client.force_login(gente["rh"])
    assert "Pessoas e papéis" in client.get(
        reverse("workspace:servicos")
    ).content.decode()

    client.force_login(gente["ana"])
    assert "Pessoas e papéis" not in client.get(
        reverse("workspace:servicos")
    ).content.decode()
