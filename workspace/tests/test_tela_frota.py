"""A tela da frota — §18 e §19 na interface.

O que ela guarda, além do óbvio:

1. **Não há reserva de veículo aqui.** O link "Reservar" leva para a GRADE, que
   é a única coisa no produto que garante ausência de choque. Um formulário de
   reserva nesta tela recriaria a duplicação que o §18 desfez.
2. **Recurso já amarrado não é oferecido de novo** — oferecer e recusar depois
   é pedir o erro para então reclamar dele.
3. **Valor não numérico vira recado, e não 500.** `Decimal("abacaxi")` levanta
   `InvalidOperation`, e um 500 por causa de um campo de texto seria a forma
   mais cara possível de dizer "digite um número".
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.models.frota import (
    DespesaVeiculo,
    SituacaoVeiculo,
    TipoDespesaVeiculo,
    Veiculo,
)
from workspace.models.reserva import Recurso, TipoRecurso

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    unidade = f.unidade()
    almox, ana, leitor = (f.pessoa(n) for n in ("almoxarife", "ana", "leitor"))
    for pessoa in (almox, ana, leitor):
        f.lotar(pessoa, uni=unidade)
    f.atribuir(
        almox,
        f.papel(
            "sup", ["log.frota.ler.global", "log.frota.operar.global"], escopo="global"
        ),
    )
    f.atribuir(leitor, f.papel("ler", ["log.frota.ler.global"], escopo="global"))
    recurso = Recurso.objects.create(
        codigo="van-1", nome="Van 1", tipo=TipoRecurso.VEICULO
    )
    veiculo = Veiculo.objects.create(
        placa="RTA1B23", modelo="Ducato", unidade=unidade, km_atual=80000,
        recurso=recurso,
    )
    return {
        "unidade": unidade, "almox": almox, "ana": ana, "leitor": leitor,
        "veiculo": veiculo, "recurso": recurso,
    }


# ── Acesso ──────────────────────────────────────────────────────────


def test_quem_nao_ve_a_frota_leva_403(cenario, client):
    client.force_login(cenario["ana"])

    assert client.get(reverse("workspace:frota")).status_code == 403


def test_quem_so_le_nao_ve_os_formularios(cenario, client):
    client.force_login(cenario["leitor"])

    resposta = client.get(reverse("workspace:frota"))

    assert resposta.status_code == 200
    assert resposta.context["opera"] is False
    assert "Cadastrar veículo" not in resposta.content.decode()


def test_quem_so_le_nao_cadastra(cenario, client):
    client.force_login(cenario["leitor"])

    resposta = client.post(
        reverse("workspace:cadastrar_veiculo"), {"placa": "XXX1A11", "modelo": "Onix"}
    )

    assert resposta.status_code == 403
    assert not Veiculo.objects.filter(placa="XXX1A11").exists()


# ── Reservar é na grade ─────────────────────────────────────────────


def test_reservar_leva_para_a_grade_e_nao_para_um_formulario_daqui(cenario, client):
    """A decisão que mais importa deste módulo. Duas portas para marcar o mesmo
    veículo foi como duas equipes acabaram na porta esperando a mesma van."""
    client.force_login(cenario["almox"])

    corpo = client.get(reverse("workspace:frota")).content.decode()

    assert reverse("workspace:reservar", args=["van-1"]) in corpo


def test_carro_em_manutencao_nao_oferece_reserva(cenario, client):
    veiculo = cenario["veiculo"]
    veiculo.situacao = SituacaoVeiculo.MANUTENCAO
    veiculo.save()
    client.force_login(cenario["almox"])

    corpo = client.get(reverse("workspace:frota")).content.decode()

    assert reverse("workspace:reservar", args=["van-1"]) not in corpo
    assert "fora da grade" in corpo


def test_recurso_ja_amarrado_nao_e_oferecido_de_novo(cenario, client):
    """Oferecer um recurso já ligado a outra placa produziria justamente a dupla
    ficha que o `OneToOne` existe para impedir."""
    livre = Recurso.objects.create(
        codigo="utilitario-1", nome="Utilitário 1", tipo=TipoRecurso.VEICULO
    )
    client.force_login(cenario["almox"])

    oferecidos = client.get(reverse("workspace:frota")).context["recursos"]

    assert list(oferecidos) == [livre]


# ── Cadastro ────────────────────────────────────────────────────────


def cadastrar(client, seguir=False, **campos):
    dados = {"placa": "rtx4y56", "modelo": "Onix", "marca": "Chevrolet"}
    dados.update(campos)
    return client.post(
        reverse("workspace:cadastrar_veiculo"), dados, follow=seguir
    )


def test_cadastrar_normaliza_a_placa(cenario, client):
    client.force_login(cenario["almox"])

    cadastrar(client)

    assert Veiculo.objects.filter(placa="RTX4Y56").exists()


def test_cadastrar_sem_modelo_nao_grava(cenario, client):
    client.force_login(cenario["almox"])

    cadastrar(client, modelo="")

    assert Veiculo.objects.count() == 1


def test_placa_repetida_recusa_dizendo_qual(cenario, client):
    """Duas fichas para a mesma placa é como a frota passa a ter dois históricos
    de manutenção."""
    client.force_login(cenario["almox"])

    resposta = cadastrar(client, seguir=True, placa="RTA1B23")

    assert Veiculo.objects.count() == 1
    assert "RTA1B23" in resposta.content.decode()


def test_cadastrar_com_ano_e_km_invalidos_nao_quebra(cenario, client):
    """Campo numérico que veio texto vira `None`, não 500."""
    client.force_login(cenario["almox"])

    cadastrar(client, ano="ontem", km_atual="muitos")

    novo = Veiculo.objects.get(placa="RTX4Y56")
    assert novo.ano is None
    assert novo.km_atual == 0


def test_cadastrar_amarra_o_recurso(cenario, client):
    livre = Recurso.objects.create(
        codigo="utilitario-1", nome="Utilitário 1", tipo=TipoRecurso.VEICULO
    )
    client.force_login(cenario["almox"])

    cadastrar(client, recurso=livre.pk, unidade=cenario["unidade"].pk)

    assert Veiculo.objects.get(placa="RTX4Y56").recurso == livre


def test_recurso_que_nao_e_veiculo_e_ignorado(cenario, client):
    """Amarrar uma SALA a um carro é o tipo de dado que ninguém percebe até a
    grade oferecer a sala de reunião como veículo da frota."""
    sala = Recurso.objects.create(
        codigo="sala-1", nome="Sala 1", tipo=TipoRecurso.SALA
    )
    client.force_login(cenario["almox"])

    cadastrar(client, recurso=sala.pk)

    assert Veiculo.objects.get(placa="RTX4Y56").recurso is None


# ── Atualizar ───────────────────────────────────────────────────────


def test_atualizar_grava_os_prazos(cenario, client):
    client.force_login(cenario["almox"])

    client.post(
        reverse("workspace:atualizar_veiculo", args=[cenario["veiculo"].pk]),
        {
            "situacao": SituacaoVeiculo.ATIVO,
            "licenciamento_ate": "2027-03-10",
            "seguro_ate": "",
            "ipva_ate": "",
            "revisao_em": "",
        },
    )
    cenario["veiculo"].refresh_from_db()

    assert cenario["veiculo"].licenciamento_ate.isoformat() == "2027-03-10"


def test_atualizar_pode_tirar_o_carro_da_grade(cenario, client):
    client.force_login(cenario["almox"])

    client.post(
        reverse("workspace:atualizar_veiculo", args=[cenario["veiculo"].pk]),
        {"situacao": SituacaoVeiculo.ATIVO, "recurso": ""},
    )
    cenario["veiculo"].refresh_from_db()

    assert cenario["veiculo"].recurso is None


def test_quem_so_le_nao_atualiza(cenario, client):
    """Prazo de documento é o que decide se o carro sai da garagem — quem só lê
    não move essa data."""
    client.force_login(cenario["leitor"])

    resposta = client.post(
        reverse("workspace:atualizar_veiculo", args=[cenario["veiculo"].pk]),
        {"situacao": SituacaoVeiculo.BAIXADO},
    )
    cenario["veiculo"].refresh_from_db()

    assert resposta.status_code == 403
    assert cenario["veiculo"].situacao == SituacaoVeiculo.ATIVO


def test_atualizar_nao_toca_na_placa(cenario, client):
    """Se a placa está errada, o veículo é outro — e trocá-la levaria junto o
    histórico de multa e manutenção do carro anterior."""
    client.force_login(cenario["almox"])

    client.post(
        reverse("workspace:atualizar_veiculo", args=[cenario["veiculo"].pk]),
        {"placa": "ZZZ9Z99", "situacao": SituacaoVeiculo.MANUTENCAO},
    )
    cenario["veiculo"].refresh_from_db()

    assert cenario["veiculo"].placa == "RTA1B23"
    assert cenario["veiculo"].situacao == SituacaoVeiculo.MANUTENCAO


# ── Lançar despesa ──────────────────────────────────────────────────


def lancar(client, cenario, seguir=False, **campos):
    dados = {
        "tipo": TipoDespesaVeiculo.COMBUSTIVEL,
        "valor": "300.00",
        "km": "80400",
        "litros": "40",
        "tanque_cheio": "1",
    }
    dados.update(campos)
    return client.post(
        reverse("workspace:lancar_despesa_veiculo", args=[cenario["veiculo"].pk]),
        dados,
        follow=seguir,
    )


def test_lancar_abastecimento_pela_tela(cenario, client):
    client.force_login(cenario["almox"])

    lancar(client, cenario)

    despesa = DespesaVeiculo.objects.get()
    assert despesa.litros == Decimal("40.000")
    assert despesa.tanque_cheio


def test_tanque_parcial_quando_a_caixa_e_desmarcada(cenario, client):
    client.force_login(cenario["almox"])

    lancar(client, cenario, tanque_cheio="")

    assert not DespesaVeiculo.objects.get().tanque_cheio


def test_valor_nao_numerico_vira_recado_e_nao_500(cenario, client):
    client.force_login(cenario["almox"])

    resposta = lancar(client, cenario, valor="abacaxi")

    assert resposta.status_code == 302
    assert not DespesaVeiculo.objects.exists()


def test_odometro_para_tras_vira_recado(cenario, client):
    client.force_login(cenario["almox"])

    resposta = lancar(client, cenario, seguir=True, km="79000")

    assert not DespesaVeiculo.objects.exists()
    assert "80000" in resposta.content.decode()


def test_lancar_volta_para_o_veiculo_aberto(cenario, client):
    """Sem isto, lançar jogava a pessoa na lista e o gasto recém-gravado não
    aparecia — o que se lê como "não salvou"."""
    client.force_login(cenario["almox"])

    resposta = lancar(client, cenario)

    assert resposta["Location"].endswith("?placa=RTA1B23")


def test_quem_so_le_nao_lanca(cenario, client):
    client.force_login(cenario["leitor"])

    lancar(client, cenario)

    assert not DespesaVeiculo.objects.exists()


# ── O detalhe ───────────────────────────────────────────────────────


def test_o_detalhe_abre_pela_placa(cenario, client):
    client.force_login(cenario["almox"])

    resposta = client.get(reverse("workspace:frota"), {"placa": "rta1b23"})

    assert resposta.context["veiculo"] == cenario["veiculo"]
    assert resposta.context["resumo"] is not None


def test_sem_placa_nao_ha_detalhe(cenario, client):
    """O consumo da frota inteira numa tela só seria uma tabela que ninguém lê:
    a pergunta é sempre sobre UM carro."""
    client.force_login(cenario["almox"])

    resposta = client.get(reverse("workspace:frota"))

    assert resposta.context["veiculo"] is None
    assert resposta.context["consumo"] == ()


def test_placa_desconhecida_nao_quebra(cenario, client):
    client.force_login(cenario["almox"])

    resposta = client.get(reverse("workspace:frota"), {"placa": "ZZZ9Z99"})

    assert resposta.status_code == 200
    assert resposta.context["veiculo"] is None


def test_get_nas_acoes_volta_para_a_tela(cenario, client):
    client.force_login(cenario["almox"])
    destino = reverse("workspace:frota")

    assert client.get(reverse("workspace:cadastrar_veiculo"))["Location"] == destino
    assert (
        client.get(
            reverse("workspace:atualizar_veiculo", args=[cenario["veiculo"].pk])
        )["Location"]
        == destino
    )
    assert (
        client.get(
            reverse("workspace:lancar_despesa_veiculo", args=[cenario["veiculo"].pk])
        )["Location"]
        == destino
    )


# ── O trilho ────────────────────────────────────────────────────────


def test_o_trilho_so_oferece_a_frota_a_quem_pode_abrir(cenario, client):
    client.force_login(cenario["ana"])
    assert reverse("workspace:frota") not in client.get(
        reverse("workspace:meu_dia")
    ).content.decode()

    client.force_login(cenario["almox"])
    assert reverse("workspace:frota") in client.get(
        reverse("workspace:meu_dia")
    ).content.decode()


def test_o_contador_do_trilho_conta_documento_estourando(cenario, client):
    from datetime import timedelta

    veiculo = cenario["veiculo"]
    veiculo.licenciamento_ate = timezone.localdate() - timedelta(days=2)
    veiculo.save()
    client.force_login(cenario["almox"])

    assert client.get(reverse("workspace:meu_dia")).context["prazos_de_veiculo"] == 1


def test_quem_nao_ve_a_frota_nao_paga_a_conta_dos_prazos(cenario, client):
    """A conta varre os prazos de todos os veículos. Cobrá-la de cada requisição
    de quem não pode nem abrir a tela é pagar por um número que ninguém lê."""
    client.force_login(cenario["ana"])

    assert client.get(reverse("workspace:meu_dia")).context["prazos_de_veiculo"] == 0
