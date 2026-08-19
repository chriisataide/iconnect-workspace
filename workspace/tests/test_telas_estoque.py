"""§15 e §17 — as telas que faltavam para o estoque existir de verdade.

O modelo e o serviço estavam prontos desde a onda de Suprimentos; a tela, não.
Na prática isso significava que o razão só era alimentado pela conclusão de um
pedido: dava para GASTAR estoque pelo produto e não dava para repor, contar nem
registrar o que voltou de campo — que é o §15 inteiro.

O que estes testes guardam:

1. **Quem não pode ver o estoque leva 403, e não uma tela vazia.** "O estoque
   está zerado" para quem não pode ver estoque é mentira, e mentira que faz a
   pessoa procurar o material que está lá.
2. **Contar é permissão separada de movimentar.** Segregação de função: quem
   tira material da prateleira não deveria ser quem declara quanto sobrou.
3. **O filtro de unidade sobrevive ao POST.** Sem isso, registrar uma reversa em
   Campinas jogava a pessoa de volta na unidade dela — e a linha que ela acabou
   de gravar não aparecia, o que se lê como "não salvou".
4. **A tela de equipamentos é de todo mundo**, e a lista dos outros não.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.models.custodia import Custodia
from workspace.models.estoque import (
    CondicaoMaterial,
    Material,
    MovimentoEstoque,
    TipoMovimento,
)
from workspace.services import custodia as cst
from workspace.services import estoque as est

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    sp = f.unidade()
    rj = f.unidade(codigo="RJ", nome="Base RJ")
    almox, ana, contador = (f.pessoa(n) for n in ("almoxarife", "ana", "contador"))
    f.lotar(almox, uni=sp)
    f.lotar(ana, uni=sp)
    f.lotar(contador, uni=sp)
    f.atribuir(
        almox,
        f.papel(
            "sup",
            [
                "log.movimentar.global",
                "log.custodia.ler.global",
                "log.custodia.atribuir.global",
            ],
            escopo="global",
        ),
    )
    # Contar SEM movimentar — é a segregação de função em pessoa.
    f.atribuir(
        contador, f.papel("inv", ["log.inventario.contar.global"], escopo="global")
    )
    capacete = Material.objects.create(
        codigo="capacete", nome="Capacete", estoque_minimo=5
    )
    est.movimentar(capacete, sp, TipoMovimento.ENTRADA, 10)
    return {
        "sp": sp, "rj": rj, "almox": almox, "ana": ana,
        "contador": contador, "material": capacete,
    }


# ── A tela do estoque ───────────────────────────────────────────────


def test_quem_nao_ve_estoque_leva_403(cenario, client):
    client.force_login(cenario["ana"])

    assert client.get(reverse("workspace:estoque")).status_code == 403


def test_quem_movimenta_ve_sem_precisar_de_log_ler(cenario, client):
    """Sem a soma, Suprimentos precisaria declarar `log.ler` ao lado de
    `log.movimentar` para enxergar o que ele mesmo acabou de gravar."""
    client.force_login(cenario["almox"])

    corpo = client.get(reverse("workspace:estoque")).content.decode()

    assert "Capacete" in corpo


def test_a_tela_abre_na_unidade_de_quem_olha(cenario, client):
    est.movimentar(cenario["material"], cenario["rj"], TipoMovimento.ENTRADA, 3)
    client.force_login(cenario["almox"])

    resposta = client.get(reverse("workspace:estoque"))

    assert resposta.context["unidade"] == cenario["sp"]
    assert [linha.unidade for linha in resposta.context["saldos"]] == [cenario["sp"]]


def test_todas_as_unidades_quando_pedido(cenario, client):
    est.movimentar(cenario["material"], cenario["rj"], TipoMovimento.ENTRADA, 3)
    client.force_login(cenario["almox"])

    resposta = client.get(reverse("workspace:estoque"), {"unidade": "todas"})

    assert len(resposta.context["saldos"]) == 2


def test_unidade_inexistente_cai_na_da_pessoa(cenario, client):
    client.force_login(cenario["almox"])

    resposta = client.get(reverse("workspace:estoque"), {"unidade": "99999"})

    assert resposta.context["unidade"] == cenario["sp"]


def test_o_filtro_aponta_para_a_unidade_pedida(cenario, client):
    """Quem controla patrimônio precisa da empresa inteira, e não só da própria
    prateleira — é para isso que o `?unidade=` existe."""
    est.movimentar(cenario["material"], cenario["rj"], TipoMovimento.ENTRADA, 3)
    client.force_login(cenario["almox"])

    resposta = client.get(
        reverse("workspace:estoque"), {"unidade": cenario["rj"].pk}
    )

    assert resposta.context["unidade"] == cenario["rj"]
    assert [linha.unidade for linha in resposta.context["saldos"]] == [cenario["rj"]]


def test_abaixo_do_minimo_tem_secao_propria(cenario, client):
    est.movimentar(cenario["material"], cenario["sp"], TipoMovimento.SAIDA, 8)
    client.force_login(cenario["almox"])

    resposta = client.get(reverse("workspace:estoque"))

    assert len(resposta.context["em_falta"]) == 1
    assert "Abaixo do mínimo" in resposta.content.decode()


def test_o_razao_so_aparece_do_material_escolhido(cenario, client):
    client.force_login(cenario["almox"])

    sem_escolha = client.get(reverse("workspace:estoque"))
    assert sem_escolha.context["razao"] == ()

    com_escolha = client.get(reverse("workspace:estoque"), {"material": "capacete"})
    assert len(com_escolha.context["razao"]) == 1


def test_o_resumo_de_reversa_mostra_as_quatro_condicoes_mesmo_zeradas(cenario, client):
    """Omitir a condição sem movimento faria "0 em sucata" desaparecer da tela, e
    é esse número que alguém precisa ler para acreditar que a coluna existe."""
    client.force_login(cenario["almox"])

    resumo = client.get(reverse("workspace:estoque")).context["resumo_reversa"]

    assert len(resumo) == len(CondicaoMaterial.choices)
    assert all(linha["total"] == 0 for linha in resumo)


def test_a_sucata_e_marcada_como_fora_do_saldo_no_resumo(cenario, client):
    client.force_login(cenario["almox"])

    resumo = client.get(reverse("workspace:estoque")).context["resumo_reversa"]
    sucata = next(c for c in resumo if c["condicao"] == CondicaoMaterial.SUCATA)

    assert sucata["no_saldo"] is False


# ── Registrar movimento ─────────────────────────────────────────────


def registrar(client, cenario, **campos):
    dados = {
        "tipo": TipoMovimento.REVERSA,
        "material": "capacete",
        "unidade": cenario["sp"].pk,
        "quantidade": 2,
        "condicao": CondicaoMaterial.USADO_BOM,
    }
    dados.update(campos)
    return client.post(reverse("workspace:registrar_movimento"), dados)


def test_reversa_entra_com_procedencia(cenario, client):
    client.force_login(cenario["almox"])

    registrar(
        client, cenario,
        unidade_origem=cenario["rj"].pk, cliente="Contrato Alfa", patrimonio="P-9",
    )

    movimento = MovimentoEstoque.objects.get(tipo=TipoMovimento.REVERSA)
    assert movimento.unidade_origem == cenario["rj"]
    assert movimento.cliente == "Contrato Alfa"
    assert est.saldo_de(cenario["material"], cenario["sp"]) == 12


def test_reversa_de_sucata_nao_entra_no_saldo(cenario, client):
    client.force_login(cenario["almox"])

    registrar(client, cenario, condicao=CondicaoMaterial.SUCATA)

    assert est.saldo_de(cenario["material"], cenario["sp"]) == 10
    assert MovimentoEstoque.objects.filter(tipo=TipoMovimento.REVERSA).exists()


def test_quem_so_conta_nao_movimenta(cenario, client):
    """Segregação de função no produto, e não só no papel."""
    client.force_login(cenario["contador"])

    assert registrar(client, cenario).status_code == 403


def test_quem_so_movimenta_nao_conta(cenario, client):
    client.force_login(cenario["almox"])

    resposta = registrar(client, cenario, tipo=TipoMovimento.AJUSTE, quantidade=3)

    assert resposta.status_code == 403


def test_a_contagem_e_o_saldo_contado_e_nao_a_diferenca(cenario, client):
    client.force_login(cenario["contador"])

    registrar(client, cenario, tipo=TipoMovimento.AJUSTE, quantidade=7, condicao="")

    assert est.saldo_de(cenario["material"], cenario["sp"]) == 7


def test_contar_zero_e_contagem_valida(cenario, client):
    """"A prateleira está vazia" é a contagem mais importante que existe."""
    client.force_login(cenario["contador"])

    registrar(client, cenario, tipo=TipoMovimento.AJUSTE, quantidade=0, condicao="")

    assert est.saldo_de(cenario["material"], cenario["sp"]) == 0


def test_entrada_de_compra_soma_ao_saldo(cenario, client):
    client.force_login(cenario["almox"])

    registrar(client, cenario, tipo=TipoMovimento.ENTRADA, quantidade=5, condicao="")

    assert est.saldo_de(cenario["material"], cenario["sp"]) == 15


def test_o_filtro_de_unidade_sobrevive_ao_post(cenario, client):
    """Sem isto, a linha recém-gravada em outra unidade não aparece na volta — e
    isso se lê como "não salvou"."""
    client.force_login(cenario["almox"])

    resposta = registrar(
        client, cenario, unidade=cenario["rj"].pk, volta_unidade=cenario["rj"].pk
    )

    assert resposta["Location"].endswith(f"?unidade={cenario['rj'].pk}")


def test_material_desconhecido_nao_grava(cenario, client):
    client.force_login(cenario["almox"])

    registrar(client, cenario, material="nao-existe")

    assert not MovimentoEstoque.objects.filter(tipo=TipoMovimento.REVERSA).exists()


def test_quantidade_nao_numerica_nao_grava(cenario, client):
    client.force_login(cenario["almox"])

    registrar(client, cenario, quantidade="muitos")

    assert not MovimentoEstoque.objects.filter(tipo=TipoMovimento.REVERSA).exists()


def test_tipo_desconhecido_nao_grava(cenario, client):
    client.force_login(cenario["almox"])

    registrar(client, cenario, tipo="teletransporte")

    assert MovimentoEstoque.objects.count() == 1


def test_erro_do_servico_vira_recado_e_nao_500(cenario, client):
    client.force_login(cenario["almox"])

    resposta = registrar(client, cenario, tipo=TipoMovimento.ENTRADA, quantidade=0)

    assert resposta.status_code == 302
    assert est.saldo_de(cenario["material"], cenario["sp"]) == 10


def test_sem_unidade_no_formulario_usa_a_de_quem_registra(cenario, client):
    """O campo é um `<select>` já preenchido; um POST sem ele vem de fora da
    tela, e cair na unidade de quem registra é mais útil que recusar."""
    client.force_login(cenario["almox"])

    registrar(client, cenario, unidade="")

    assert est.saldo_de(cenario["material"], cenario["sp"]) == 12


def test_sem_unidade_e_sem_lotacao_nao_grava(cenario, client):
    """Não há de qual prateleira tirar. Escolher uma qualquer deixaria o erro
    para a conferência do mês."""
    avulso = f.pessoa("avulso")
    f.atribuir(avulso, f.papel("mov", ["log.movimentar.global"], escopo="global"))
    client.force_login(avulso)

    registrar(client, cenario, unidade="")

    assert not MovimentoEstoque.objects.filter(tipo=TipoMovimento.REVERSA).exists()


def test_get_no_movimentar_volta_para_a_tela(cenario, client):
    client.force_login(cenario["almox"])

    resposta = client.get(reverse("workspace:registrar_movimento"))

    assert resposta["Location"] == reverse("workspace:estoque")


# ── A tela de equipamentos ──────────────────────────────────────────


def entregar(cenario, **extras):
    return cst.entregar(
        cenario["material"], cenario["ana"], cenario["almox"], **extras
    )


def test_a_tela_de_equipamentos_e_de_todo_mundo(cenario, client):
    entregar(cenario)
    client.force_login(cenario["ana"])

    resposta = client.get(reverse("workspace:custodia"))

    assert resposta.status_code == 200
    assert len(resposta.context["minhas"]) == 1
    assert resposta.context["controla"] is False


def test_a_lista_dos_outros_so_para_quem_controla(cenario, client):
    entregar(cenario)

    client.force_login(cenario["ana"])
    assert client.get(reverse("workspace:custodia")).context["de_terceiros"] == []

    client.force_login(cenario["almox"])
    assert len(client.get(reverse("workspace:custodia")).context["de_terceiros"]) == 1


def test_quem_entrega_nao_aparece_na_lista_de_destinatarios(cenario, client):
    """Segregação de função na interface, e não só no serviço: oferecer o próprio
    nome e recusar depois é pedir o erro para então reclamar dele."""
    client.force_login(cenario["almox"])

    pessoas = client.get(reverse("workspace:custodia")).context["pessoas"]

    assert cenario["almox"] not in pessoas


def test_entregar_pela_tela(cenario, client):
    client.force_login(cenario["almox"])

    client.post(
        reverse("workspace:entregar_custodia"),
        {
            "pessoa": cenario["ana"].pk,
            "material": "capacete",
            "quantidade": 1,
            "patrimonio": "P-1",
        },
    )

    assert Custodia.objects.filter(pessoa=cenario["ana"]).exists()
    assert est.saldo_de(cenario["material"], cenario["sp"]) == 9


def test_entregar_sem_pessoa_nao_grava(cenario, client):
    client.force_login(cenario["almox"])

    client.post(
        reverse("workspace:entregar_custodia"),
        {"pessoa": "", "material": "capacete", "quantidade": 1},
    )

    assert not Custodia.objects.exists()


def test_entregar_material_desconhecido_nao_grava(cenario, client):
    client.force_login(cenario["almox"])

    client.post(
        reverse("workspace:entregar_custodia"),
        {"pessoa": cenario["ana"].pk, "material": "nao-existe", "quantidade": 1},
    )

    assert not Custodia.objects.exists()


def test_entregar_quantidade_nao_numerica_nao_grava(cenario, client):
    client.force_login(cenario["almox"])

    client.post(
        reverse("workspace:entregar_custodia"),
        {"pessoa": cenario["ana"].pk, "material": "capacete", "quantidade": "duas"},
    )

    assert not Custodia.objects.exists()


def test_aceitar_pela_tela(cenario, client):
    guarda = entregar(cenario)
    client.force_login(cenario["ana"])

    client.post(reverse("workspace:aceitar_custodia", args=[guarda.pk]))
    guarda.refresh_from_db()

    assert guarda.aceita


def test_ninguem_aceita_pelo_colega(cenario, client):
    guarda = entregar(cenario)
    client.force_login(cenario["almox"])

    client.post(reverse("workspace:aceitar_custodia", args=[guarda.pk]))
    guarda.refresh_from_db()

    assert not guarda.aceita


def test_devolver_pela_tela(cenario, client):
    guarda = entregar(cenario)
    client.force_login(cenario["almox"])

    client.post(
        reverse("workspace:devolver_custodia", args=[guarda.pk]),
        {"condicao": CondicaoMaterial.USADO_BOM},
    )
    guarda.refresh_from_db()

    assert not guarda.em_uso
    assert est.saldo_de(cenario["material"], cenario["sp"]) == 10


def test_devolver_sem_condicao_nao_encerra(cenario, client):
    guarda = entregar(cenario)
    client.force_login(cenario["almox"])

    client.post(reverse("workspace:devolver_custodia", args=[guarda.pk]), {})
    guarda.refresh_from_db()

    assert guarda.em_uso


def test_get_nas_acoes_de_custodia_volta_para_a_tela(cenario, client):
    guarda = entregar(cenario)
    client.force_login(cenario["almox"])
    destino = reverse("workspace:custodia")

    assert client.get(reverse("workspace:entregar_custodia"))["Location"] == destino
    assert (
        client.get(reverse("workspace:aceitar_custodia", args=[guarda.pk]))["Location"]
        == destino
    )
    assert (
        client.get(reverse("workspace:devolver_custodia", args=[guarda.pk]))["Location"]
        == destino
    )


# ── O trilho ────────────────────────────────────────────────────────


def test_o_trilho_so_oferece_estoque_a_quem_pode_abrir(cenario, client):
    """Item que leva a um 403 ensina a pessoa a ignorar o trilho inteiro."""
    client.force_login(cenario["ana"])
    assert reverse("workspace:estoque") not in client.get(
        reverse("workspace:meu_dia")
    ).content.decode()

    client.force_login(cenario["almox"])
    assert reverse("workspace:estoque") in client.get(
        reverse("workspace:meu_dia")
    ).content.decode()


def test_o_contador_de_aceite_aparece_no_trilho(cenario, client):
    entregar(cenario)
    client.force_login(cenario["ana"])

    resposta = client.get(reverse("workspace:meu_dia"))

    assert resposta.context["custodias_a_aceitar"] == 1


def test_o_contador_zera_depois_do_aceite(cenario, client):
    guarda = entregar(cenario)
    cst.aceitar(guarda, cenario["ana"])
    client.force_login(cenario["ana"])

    assert client.get(reverse("workspace:meu_dia")).context["custodias_a_aceitar"] == 0
