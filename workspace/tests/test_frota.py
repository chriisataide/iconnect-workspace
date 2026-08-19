"""§18 e §19 — a frota, seus prazos e o que ela consome.

## A duplicação que a auditoria encontrou antes da primeira linha

Veículo já existia DUAS vezes no produto, e as duas metades não se conheciam:
a grade de Reservas, que garante por transação que duas pessoas não peguem a
van no mesmo horário, e um item de catálogo com "período" em TEXTO LIVRE.

Marcar por um caminho não bloqueava o outro, e o choque não era detectável em
lugar nenhum — um lado guardava `datetime`, o outro guardava a frase "de terça
a quinta". No dia, duas equipes na porta esperando o mesmo veículo.

O que estes testes guardam:

1. **Há um caminho só para reservar**, e o carro da frota é o MESMO recurso da
   grade — não uma segunda ficha com o mesmo nome.
2. **O consumo é tanque-a-tanque, e só entre tanques cheios.** Entre dois
   parciais a conta devolve um número plausível e errado, que é pior que
   nenhum.
3. **O odômetro não anda para trás.**
4. **Documento vencido é derivado da data**, nunca um campo — um booleano
   gravado estaria errado no dia seguinte.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.models.frota import (
    DespesaVeiculo,
    SituacaoVeiculo,
    TipoDespesaVeiculo,
    Veiculo,
)
from workspace.models.notificacao import Notificacao, TipoNotificacao
from workspace.models.reserva import Recurso, TipoRecurso
from workspace.services import frota as frt
from workspace.services.frota import FrotaError

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    unidade = f.unidade()
    almox, ana = f.pessoa("almoxarife"), f.pessoa("ana")
    f.lotar(almox, uni=unidade)
    f.lotar(ana, uni=unidade)
    f.atribuir(
        almox,
        f.papel(
            "sup", ["log.frota.ler.global", "log.frota.operar.global"], escopo="global"
        ),
    )
    veiculo = Veiculo.objects.create(
        placa="RTA1B23", modelo="Ducato", marca="Fiat", unidade=unidade, km_atual=80000
    )
    return {"unidade": unidade, "almox": almox, "ana": ana, "veiculo": veiculo}


def abastecer(cenario, km, litros, valor="300.00", cheio=True, data=None):
    return frt.lancar_despesa(
        cenario["veiculo"],
        TipoDespesaVeiculo.COMBUSTIVEL,
        valor,
        quem=cenario["almox"],
        km=km,
        litros=litros,
        tanque_cheio=cheio,
        data=data,
    )


# ── O elo com a reserva ─────────────────────────────────────────────


def test_o_veiculo_da_frota_e_o_mesmo_recurso_da_grade(cenario):
    """Sem esse elo, a terceira lista de veículos nasce no primeiro mês."""
    recurso = Recurso.objects.create(
        codigo="van-1", nome="Van 1", tipo=TipoRecurso.VEICULO
    )
    cenario["veiculo"].recurso = recurso
    cenario["veiculo"].save()

    assert cenario["veiculo"].reservavel
    assert recurso.veiculo == cenario["veiculo"]


def test_um_recurso_nao_serve_a_duas_placas(cenario):
    """É o `OneToOne` fazendo o trabalho: duas fichas para o mesmo carro é como
    a frota passa a ter dois históricos de manutenção."""
    from django.db import IntegrityError, transaction

    recurso = Recurso.objects.create(
        codigo="van-1", nome="Van 1", tipo=TipoRecurso.VEICULO
    )
    cenario["veiculo"].recurso = recurso
    cenario["veiculo"].save()

    with pytest.raises(IntegrityError), transaction.atomic():
        Veiculo.objects.create(placa="RTZ9Z99", modelo="Outro", recurso=recurso)


def test_carro_em_manutencao_sai_da_grade_sem_perder_o_elo(cenario):
    """Desligar e religar o recurso perderia o histórico de reservas."""
    recurso = Recurso.objects.create(
        codigo="van-1", nome="Van 1", tipo=TipoRecurso.VEICULO
    )
    veiculo = cenario["veiculo"]
    veiculo.recurso = recurso
    veiculo.situacao = SituacaoVeiculo.MANUTENCAO
    veiculo.save()

    assert not veiculo.reservavel
    assert veiculo.recurso_id == recurso.pk


def test_o_item_de_catalogo_de_veiculo_esta_aposentado(db):
    """A metade duplicada. Desativada, não apagada: os pedidos já feitos
    continuam no histórico, e os indicadores do período continuam certos."""
    from io import StringIO

    from django.core.management import call_command

    from workspace.models.catalogo import ItemCatalogo

    call_command("semear_catalogo", "--aplicar", stdout=StringIO())

    assert not ItemCatalogo.objects.filter(chave="veiculo", ativo=True).exists()


# ── A placa ─────────────────────────────────────────────────────────


def test_a_placa_e_normalizada_para_maiuscula():
    """Sem isto "abc1d23" e "ABC1D23" são dois veículos, e o `unique` não
    impede — o banco compara byte a byte."""
    veiculo = Veiculo.objects.create(placa=" rtx4y56 ", modelo="Onix")

    assert veiculo.placa == "RTX4Y56"


# ── Os prazos ───────────────────────────────────────────────────────


def test_documento_sem_data_nao_conta_como_vencido(cenario):
    """Não saber a data do seguro é diferente de o seguro ter vencido — e
    tratar as duas coisas igual faria a tela gritar sobre a frota inteira no dia
    do cadastro."""
    assert cenario["veiculo"].prazos() == []
    assert not cenario["veiculo"].tem_pendencia


def test_prazo_vencido_e_derivado_da_data(cenario):
    """Um `vencido = BooleanField` estaria errado no dia seguinte ao ser
    gravado, e ninguém rodaria o comando que o corrige."""
    hoje = timezone.localdate()
    veiculo = cenario["veiculo"]
    veiculo.licenciamento_ate = hoje - timedelta(days=1)
    veiculo.save()

    prazo = veiculo.prazos()[0]
    assert prazo["vencido"]
    assert prazo["dias"] == -1
    assert veiculo.tem_pendencia


def test_um_carro_com_dois_documentos_produz_duas_linhas(cenario):
    """Uma linha só faria o segundo problema sumir quando o primeiro fosse
    resolvido."""
    hoje = timezone.localdate()
    veiculo = cenario["veiculo"]
    veiculo.licenciamento_ate = hoje - timedelta(days=5)
    veiculo.seguro_ate = hoje + timedelta(days=10)
    veiculo.save()

    achados = frt.com_prazo_estourando()

    assert len(achados) == 2
    # Vencido primeiro: é o que faz o carro ser apreendido.
    assert achados[0]["prazo"]["campo"] == "licenciamento_ate"


def test_prazo_distante_nao_entra_no_alerta(cenario):
    veiculo = cenario["veiculo"]
    veiculo.ipva_ate = timezone.localdate() + timedelta(days=200)
    veiculo.save()

    assert frt.com_prazo_estourando() == []


def test_veiculo_baixado_sai_da_frota(cenario):
    """Baixado e não apagado: multa e imposto de um carro vendido continuam
    chegando por anos, e a placa precisa achar o histórico."""
    veiculo = cenario["veiculo"]
    veiculo.situacao = SituacaoVeiculo.BAIXADO
    veiculo.licenciamento_ate = timezone.localdate() - timedelta(days=1)
    veiculo.save()

    assert not frt.frota().exists()
    assert frt.frota(incluir_baixados=True).exists()
    assert frt.com_prazo_estourando() == []


# ── O consumo — §19 ─────────────────────────────────────────────────


def test_o_primeiro_tanque_nunca_tem_consumo(cenario):
    """Não há tanque anterior para saber quanto se rodou. A linha aparece assim
    mesmo — escondê-la deixaria um buraco no começo do histórico."""
    abastecer(cenario, km=80000, litros="40")

    linhas = frt.consumo_de(cenario["veiculo"])

    assert len(linhas) == 1
    assert linhas[0]["km_l"] is None


def test_o_consumo_e_tanque_a_tanque(cenario):
    """400 km rodados desde o tanque anterior, 40 litros para enchê-lo de novo:
    10 km/l."""
    abastecer(cenario, km=80000, litros="50")
    abastecer(cenario, km=80400, litros="40")

    recente = frt.consumo_de(cenario["veiculo"])[0]

    assert recente["rodados"] == 400
    assert recente["km_l"] == Decimal("10.00")


def test_tanque_parcial_fica_fora_da_conta(cenario):
    """Entre dois parciais a conta divide a distância por um volume que não
    corresponde a ela — e devolve um número plausível e errado."""
    abastecer(cenario, km=80000, litros="50")
    abastecer(cenario, km=80200, litros="20", cheio=False)
    abastecer(cenario, km=80400, litros="40")

    linhas = frt.consumo_de(cenario["veiculo"])

    assert len(linhas) == 2
    # A distância medida é a dos DOIS trechos: 400 km, e não 200.
    assert linhas[0]["rodados"] == 400


def test_a_media_e_o_total_sobre_o_total(cenario):
    """E não a média das médias: essa dá peso igual a um tanque de 8 litros e a
    um de 60, e um abastecimento de emergência moveria o indicador do ano."""
    abastecer(cenario, km=80000, litros="50")
    abastecer(cenario, km=80100, litros="20")   # 5,00 km/l
    abastecer(cenario, km=81100, litros="50")   # 20,00 km/l

    resumo = frt.resumo_de(cenario["veiculo"])

    # Média das médias daria 12,50. O certo é 1100 km / 70 litros.
    assert resumo["media_km_l"] == Decimal("15.71")


def test_o_resumo_soma_todos_os_tipos_de_gasto(cenario):
    abastecer(cenario, km=80000, litros="40", valor="300.00")
    frt.lancar_despesa(
        cenario["veiculo"], TipoDespesaVeiculo.PEDAGIO, "27.50",
        quem=cenario["almox"],
    )

    resumo = frt.resumo_de(cenario["veiculo"])

    assert resumo["total"] == Decimal("327.50")
    pedagio = next(
        l for l in resumo["por_tipo"] if l["tipo"] == TipoDespesaVeiculo.PEDAGIO
    )
    assert pedagio["total"] == Decimal("27.50")


def test_o_resumo_mostra_todos_os_tipos_mesmo_zerados(cenario):
    """Omitir o tipo sem lançamento faria "R$ 0,00 em multa" desaparecer — e é
    esse número que alguém precisa ler para acreditar que a coluna existe."""
    resumo = frt.resumo_de(cenario["veiculo"])

    assert len(resumo["por_tipo"]) == len(TipoDespesaVeiculo.choices)
    assert all(l["total"] == Decimal("0") for l in resumo["por_tipo"])


def test_custo_por_km_usa_a_distancia_medida_e_nao_o_odometro(cenario):
    """O odômetro inclui a vida do carro antes de o controle existir, e dividir
    o gasto deste ano por ela daria um centavo por quilômetro."""
    abastecer(cenario, km=80000, litros="50", valor="250.00")
    abastecer(cenario, km=80500, litros="50", valor="250.00")

    resumo = frt.resumo_de(cenario["veiculo"])

    assert resumo["rodados"] == 500
    assert resumo["custo_por_km"] == Decimal("1.00")


def test_sem_abastecimento_o_custo_por_km_e_nulo_e_nao_zero(cenario):
    """Zero afirmaria que rodar não custa nada. Nulo diz que ainda não dá para
    saber, que é a verdade."""
    frt.lancar_despesa(
        cenario["veiculo"], TipoDespesaVeiculo.PEDAGIO, "10.00", quem=cenario["almox"]
    )

    resumo = frt.resumo_de(cenario["veiculo"])

    assert resumo["custo_por_km"] is None
    assert resumo["media_km_l"] is None


# ── Lançar ──────────────────────────────────────────────────────────


def test_o_odometro_nao_anda_para_tras(cenario):
    """Km menor que o último é erro de digitação em 100% dos casos reais, e
    aceitá-lo produz consumo negativo numa linha e absurdo na seguinte."""
    with pytest.raises(FrotaError, match="80000"):
        abastecer(cenario, km=79000, litros="40")


def test_lancar_com_km_adianta_o_odometro(cenario):
    abastecer(cenario, km=80500, litros="40")
    cenario["veiculo"].refresh_from_db()

    assert cenario["veiculo"].km_atual == 80500


def test_pedagio_sem_km_nao_mexe_no_odometro(cenario):
    """Exigir km no pedágio faria quem lança inventar um número — pior que o
    vazio: o cálculo de consumo passaria a mentir com aparência de precisão."""
    frt.lancar_despesa(
        cenario["veiculo"], TipoDespesaVeiculo.PEDAGIO, "12.30", quem=cenario["almox"]
    )
    cenario["veiculo"].refresh_from_db()

    assert cenario["veiculo"].km_atual == 80000


def test_abastecimento_exige_litros(cenario):
    """Sem litro o abastecimento vira só um valor, e o §19 inteiro — quanto este
    carro faz por litro — deixa de ter resposta."""
    with pytest.raises(FrotaError, match="litros"):
        frt.lancar_despesa(
            cenario["veiculo"], TipoDespesaVeiculo.COMBUSTIVEL, "300.00",
            quem=cenario["almox"], km=80100,
        )


def test_valor_zero_ou_negativo_recusa(cenario):
    for valor in ("0", "-10"):
        with pytest.raises(FrotaError, match="maior que zero"):
            frt.lancar_despesa(
                cenario["veiculo"], TipoDespesaVeiculo.PEDAGIO, valor,
                quem=cenario["almox"],
            )


def test_tipo_invalido_recusa(cenario):
    with pytest.raises(FrotaError, match="inválido"):
        frt.lancar_despesa(
            cenario["veiculo"], "teletransporte", "10", quem=cenario["almox"]
        )


def test_quem_nao_opera_nao_lanca(cenario):
    with pytest.raises(FrotaError, match="não pode lançar"):
        frt.lancar_despesa(
            cenario["veiculo"], TipoDespesaVeiculo.PEDAGIO, "10", quem=cenario["ana"]
        )


def test_quem_opera_tambem_le(cenario):
    """Sem a soma, o papel que lança abastecimento não enxergaria o que acabou
    de lançar."""
    so_opera = f.pessoa("carlos")
    f.lotar(so_opera, uni=cenario["unidade"])
    f.atribuir(
        so_opera, f.papel("op", ["log.frota.operar.global"], escopo="global")
    )

    assert frt.pode_ler(so_opera)
    assert not frt.pode_ler(cenario["ana"])


def test_preco_por_litro_e_derivado(cenario):
    despesa = abastecer(cenario, km=80000, litros="50", valor="300.00")

    assert despesa.preco_por_litro == Decimal("6.000")


def test_despesa_sem_litros_nao_tem_preco_por_litro(cenario):
    despesa = frt.lancar_despesa(
        cenario["veiculo"], TipoDespesaVeiculo.LAVAGEM, "45.00", quem=cenario["almox"]
    )

    assert despesa.preco_por_litro is None


# ── O aviso ─────────────────────────────────────────────────────────


def test_avisa_quem_opera_a_frota(cenario):
    """Vai para Suprimentos e não para o último motorista: quem paga o IPVA e
    agenda a vistoria é quem opera."""
    veiculo = cenario["veiculo"]
    veiculo.licenciamento_ate = timezone.localdate() - timedelta(days=3)
    veiculo.save()

    assert frt.avisar_vencimentos() == 1

    aviso = Notificacao.objects.de(cenario["almox"]).get()
    assert aviso.tipo == TipoNotificacao.DOCUMENTO_DE_VEICULO
    assert "RTA1B23" in aviso.titulo
    assert not Notificacao.objects.de(cenario["ana"]).exists()


def test_dois_documentos_do_mesmo_carro_geram_dois_avisos(cenario):
    """O dedupe usa `origem_id`, e ele inclui o CAMPO do prazo — sem isso o
    aviso do licenciamento silenciaria o do seguro."""
    hoje = timezone.localdate()
    veiculo = cenario["veiculo"]
    veiculo.licenciamento_ate = hoje - timedelta(days=3)
    veiculo.seguro_ate = hoje + timedelta(days=5)
    veiculo.save()

    assert frt.avisar_vencimentos() == 2


def test_rodar_duas_vezes_nao_duplica_o_aviso(cenario):
    """O comando é diário. Trinta cópias do mesmo alerta é como o sino vira
    ruído."""
    veiculo = cenario["veiculo"]
    veiculo.licenciamento_ate = timezone.localdate() - timedelta(days=3)
    veiculo.save()

    frt.avisar_vencimentos()
    frt.avisar_vencimentos()

    assert Notificacao.objects.de(cenario["almox"]).count() == 1


def test_sem_ninguem_operando_a_frota_nao_ha_aviso(cenario):
    """E não uma exceção: documento vencendo sem dono é problema de papel, não
    de código."""
    from identidade.models import AtribuicaoPapel

    AtribuicaoPapel.objects.all().delete()
    veiculo = cenario["veiculo"]
    veiculo.licenciamento_ate = timezone.localdate() - timedelta(days=3)
    veiculo.save()

    assert frt.avisar_vencimentos() == 0


def test_o_aviso_diz_quantos_dias_faltam_quando_ainda_nao_venceu(cenario):
    veiculo = cenario["veiculo"]
    veiculo.ipva_ate = timezone.localdate() + timedelta(days=7)
    veiculo.save()

    frt.avisar_vencimentos()

    assert "7 dias" in Notificacao.objects.de(cenario["almox"]).get().titulo


# ── Os comandos ─────────────────────────────────────────────────────


def test_semear_frota_liga_o_veiculo_ao_recurso_existente(db):
    """O ponto do comando não é criar carros — é amarrá-los. Sem o elo, o banco
    de demonstração nasceria com duas listas de veículos."""
    from io import StringIO

    from django.core.management import call_command

    f.unidade()
    Recurso.objects.create(codigo="van-1", nome="Van 1", tipo=TipoRecurso.VEICULO)
    call_command("semear_frota", "--aplicar", stdout=StringIO())

    assert Veiculo.objects.get(placa="RTA1B23").recurso.codigo == "van-1"


def test_semear_frota_sem_aplicar_nao_grava(db):
    from io import StringIO

    from django.core.management import call_command

    call_command("semear_frota", stdout=StringIO())

    assert not Veiculo.objects.exists()


def test_semear_frota_nao_duplica(db):
    from io import StringIO

    from django.core.management import call_command

    call_command("semear_frota", "--aplicar", stdout=StringIO())
    call_command("semear_frota", "--aplicar", stdout=StringIO())

    assert Veiculo.objects.count() == 3


def test_avisar_frota_sem_aplicar_nao_grava(cenario):
    from io import StringIO

    from django.core.management import call_command

    veiculo = cenario["veiculo"]
    veiculo.licenciamento_ate = timezone.localdate() - timedelta(days=3)
    veiculo.save()

    call_command("avisar_frota", stdout=StringIO())

    assert not Notificacao.objects.exists()


def test_avisar_frota_aplica(cenario):
    from io import StringIO

    from django.core.management import call_command

    veiculo = cenario["veiculo"]
    veiculo.licenciamento_ate = timezone.localdate() - timedelta(days=3)
    veiculo.save()

    saida = StringIO()
    call_command("avisar_frota", "--aplicar", stdout=saida)

    assert Notificacao.objects.count() == 1
    assert "RTA1B23" in saida.getvalue()


def test_avisar_frota_aceita_outra_antecedencia(cenario):
    from io import StringIO

    from django.core.management import call_command

    veiculo = cenario["veiculo"]
    veiculo.ipva_ate = timezone.localdate() + timedelta(days=45)
    veiculo.save()

    call_command("avisar_frota", "--dias", "60", "--aplicar", stdout=StringIO())

    assert Notificacao.objects.count() == 1


def test_despesa_protege_o_veiculo(cenario):
    """`PROTECT`: apagar o carro levaria junto o histórico de multa e
    abastecimento, que é o que responde quanto ele custou."""
    from django.db import models

    abastecer(cenario, km=80000, litros="40")

    with pytest.raises(models.ProtectedError):
        cenario["veiculo"].delete()


def test_despesas_de_filtra_por_tipo(cenario):
    abastecer(cenario, km=80000, litros="40")
    frt.lancar_despesa(
        cenario["veiculo"], TipoDespesaVeiculo.PEDAGIO, "10", quem=cenario["almox"]
    )

    assert frt.despesas_de(
        cenario["veiculo"], tipo=TipoDespesaVeiculo.PEDAGIO
    ).count() == 1
    assert DespesaVeiculo.objects.count() == 2
