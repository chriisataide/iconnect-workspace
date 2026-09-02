"""A massa fictícia — e os quinze defeitos que ela planta de propósito.

Cada defeito exercita uma regra da tela de resultados. Se alguém "corrigir" a
massa achando que é bug, este arquivo cai e explica por quê — que é a única
forma de uma massa cheia de anomalias sobreviver à primeira faxina.

E ela entra pelo CARREGADOR, não por gravação direta. Se a semeadora precisar de
um caminho especial para gravar, o carregador está errado.
"""

from __future__ import annotations

from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from cargas.models import Divergencia, ExecucaoCarga, Fonte, StatusCarga
from resultados import services as svc
from resultados.models import (
    Apontamento, AvaliacaoCliente, CompetenciaResultado, Contrato, MarcoProjeto,
    Projeto, QuadroPessoas,
)

pytestmark = pytest.mark.django_db


def _rodar(*args) -> str:
    saida = StringIO()
    call_command(*args, stdout=saida, stderr=saida)
    return saida.getvalue()


@pytest.fixture
def massa(db):
    _rodar("semear_fontes", "--aplicar")
    _rodar("semear_resultados", "--aplicar")


# ── O caminho ───────────────────────────────────────────────────────


def test_a_massa_entra_pelo_carregador_e_nao_por_gravacao_direta(massa):
    """Cada fonte tem uma `ExecucaoCarga` de verdade.

    Sem isso, a semeadora seria um segundo caminho de escrita — e um bug do
    carregador só apareceria na primeira carga de madrugada.
    """
    fontes = set(
        ExecucaoCarga.objects.filter(status=StatusCarga.SUCESSO).values_list(
            "fonte__chave", flat=True
        )
    )

    assert {Fonte.SANKHYA, Fonte.MONDAY, Fonte.PLATFORM} <= fontes


def test_a_procedencia_e_MISTA_e_nao_uma_fonte_so(massa):
    """Financeiro do Sankhya, projetos do monday, contratos do Platform.

    Sem as três, a tela de fontes teria uma linha e o carimbo por bloco diria a
    mesma coisa nas seis faixas — e a primeira vez que alguém veria três
    carimbos diferentes na mesma tela seria em produção.
    """
    assert CompetenciaResultado.objects.filter(fonte=Fonte.SANKHYA).exists()
    assert Projeto.objects.filter(fonte=Fonte.MONDAY).exists()
    assert Contrato.objects.filter(fonte=Fonte.PLATFORM).exists()


def test_semear_duas_vezes_produz_exatamente_o_mesmo_banco(massa):
    """Semente fixa. Teste que depende de número aleatório falha na sexta.

    Na primeira versão eu usei `hash()` de string para derivar efetivo e horas —
    e o Python salga o hash por processo. A segunda passada reescrevia 276
    linhas com valores diferentes, e o único sinal era um contador que o resumo
    nem imprimia.
    """
    antes = list(
        CompetenciaResultado.objects.order_by("chave_externa").values_list(
            "chave_externa", "receita_bruta", "hash_conteudo"
        )
    )

    saida = _rodar("semear_resultados", "--aplicar")
    depois = list(
        CompetenciaResultado.objects.order_by("chave_externa").values_list(
            "chave_externa", "receita_bruta", "hash_conteudo"
        )
    )

    assert antes == depois
    assert "atualizados    0" in saida, "nada pode ser reescrito na segunda passada"


def test_sem_fonte_cadastrada_a_semeadora_avisa_em_vez_de_estourar(db):
    saida = _rodar("semear_resultados", "--aplicar")

    assert "semear_fontes" in saida
    assert not Contrato.objects.exists()


def test_simulacao_nao_grava(db):
    _rodar("semear_fontes", "--aplicar")

    saida = _rodar("semear_resultados")

    assert "SIMULAÇÃO" in saida
    assert not Contrato.objects.exists()


# ── Os quinze defeitos ──────────────────────────────────────────────


def _margem(contrato):
    return svc.margem_pct(list(contrato.competencias.order_by("-ano", "-mes")[:6]))


def test_defeito_1_tres_contratos_entre_quatro_e_nove_por_cento(massa):
    """A faixa que dispara a regra dos 10% SEM ser deficitária.

    Deficitário e "abaixo de 10%" são blocos diferentes na tela, e a massa
    precisa dos dois para a diferença ser testável.
    """
    baixos = [
        c.codigo for c in Contrato.objects.all()
        if (m := _margem(c)) is not None and Decimal("4") <= m < Decimal("10")
    ]

    assert len(baixos) == 3, f"esperava três, achei {baixos}"


def test_defeito_2_um_contrato_com_margem_negativa(massa):
    deficitarios = [
        c.codigo for c in Contrato.objects.all()
        if (m := _margem(c)) is not None and m < 0
    ]

    assert deficitarios == ["CT-112"]


def test_defeito_3_e_4_um_layer_3_e_um_layer_1_vencendo(massa):
    """Os dois na mesma tela, com pesos diferentes.

    Perder um Layer 3 sem visita custa mais que perder três Layer 1 — e a faixa
    4 só prova que sabe disso se a massa tiver os dois.
    """
    hoje = timezone.localdate()
    vencendo = {
        c.codigo: (svc.layer_de(c).valor, (c.fim_vigencia - hoje).days)
        for c in Contrato.objects.filter(fim_vigencia__lte=hoje.replace(year=hoje.year + 1))
        if c.fim_vigencia and 0 < (c.fim_vigencia - hoje).days <= 60
    }

    assert ("3", 45) in vencendo.values()
    assert ("1", 25) in vencendo.values()


def test_defeito_5_um_centro_de_custo_quase_no_teto(massa):
    """97% comprometido: a barra tem de mostrar aperto sem mostrar estouro."""
    quase = [
        linha for linha in CompetenciaResultado.objects.filter(
            contrato__isnull=True, receita_orcada__isnull=False
        )
        if linha.receita_orcada
        and Decimal("0.96") < abs(linha.custo_indireto / linha.receita_orcada) < Decimal("0.98")
    ]

    assert quase, "nenhum centro de custo perto do teto"


def test_defeito_6_um_centro_de_custo_sem_orcamento(massa):
    """"Sem orçado" e "orçado zero" produzem leituras opostas.

    A faixa 2 marca a linha como "sem orçado" em vez de mostrar variação de
    100% — que é o que uma conciliação quebrada produz, e parece estouro sem ser.
    """
    orfaos = set(
        CompetenciaResultado.objects.filter(
            contrato__isnull=True, receita_orcada__isnull=True
        ).values_list("centro_custo", flat=True)
    )

    assert len(orfaos) == 1


def test_defeito_7_pico_de_hora_extra_de_ineficiencia_em_maio(massa):
    """Ineficiência é o número que muda comportamento.

    Serviço extra é receita; ineficiência é escala mal resolvida. Somá-los numa
    "HE total" produz um número que ninguém sabe consertar.
    """
    maio = Apontamento.objects.filter(mes=5).first()
    outro = Apontamento.objects.exclude(mes=5).first()

    assert maio is not None and outro is not None
    assert maio.he_ineficiencia / maio.horas_normais > Decimal("0.10")
    assert outro.he_ineficiencia / outro.horas_normais < Decimal("0.03")


def test_defeito_8_um_centro_de_custo_com_turnover_destoante(massa):
    """Um número alto sozinho não prova nada — ele vira achado quando há com o
    que comparar. E foi a MÉDIA que escondeu isso na primeira montagem da
    faixa 6."""
    altos = set(
        QuadroPessoas.objects.filter(turnover_pct__gt=5).values_list(
            "centro_custo", flat=True
        )
    )
    baixos = QuadroPessoas.objects.filter(turnover_pct__lt=3).count()

    assert len(altos) == 1
    assert baixos > 0


def test_defeito_9_dois_detratores_um_tratado_e_um_nao(massa):
    """Com tratativa é trabalho em andamento; sem, é uma pessoa esperando.

    Só o segundo vira destaque, e a massa precisa dos dois para a diferença ser
    testável.
    """
    detratores = AvaliacaoCliente.objects.filter(classificacao="detrator")

    assert detratores.count() == 2
    assert detratores.filter(tratativa_aberta=True).count() == 1
    assert detratores.filter(tratativa_aberta=False).count() == 1


def test_defeito_10_uma_competencia_com_receita_e_sem_custo(massa):
    """A tela mostra "—", nunca margem de 100%.

    Custo zero e custo desconhecido produzem o mesmo número e leituras opostas.
    """
    sem_custo = CompetenciaResultado.objects.filter(
        contrato__codigo="CT-102", custo_direto=0, receita_bruta__gt=0
    )

    assert sem_custo.exists()


def test_defeito_11_duas_conquistas_e_uma_perda_no_trimestre(massa):
    hoje = timezone.localdate()
    trimestre = hoje.toordinal() - 92

    conquistas = [
        c for c in Contrato.objects.all()
        if c.inicio_vigencia and c.inicio_vigencia.toordinal() >= trimestre
    ]
    perdas = [
        c for c in Contrato.objects.filter(status="encerrado")
        if c.fim_vigencia and c.fim_vigencia.toordinal() >= trimestre
    ]

    assert len(conquistas) >= 2
    assert len(perdas) == 1


def test_defeito_12_folhas_e_contratos_pendentes(massa):
    """As duas viram autuação, e por isso saem da tabela de horas para um bloco
    próprio."""
    pendente = Apontamento.objects.filter(folhas_ponto_pendentes__gt=0).first()

    assert pendente is not None
    assert pendente.folhas_ponto_pendentes == 14
    assert pendente.contratos_pendentes_assinatura == 3


def test_defeito_13_tres_projetos_bloqueados_e_dois_marcos_vencidos(massa):
    """Bloqueio COM motivo. Sem motivo é uma bandeira vermelha que ninguém sabe
    o que fazer com — e a próxima pergunta na reunião seria exatamente essa."""
    hoje = timezone.localdate()
    bloqueados = Projeto.objects.filter(bloqueado=True)
    vencidos = MarcoProjeto.objects.filter(concluido_em__isnull=True, prazo__lt=hoje)

    assert bloqueados.count() == 3
    assert all(p.motivo_bloqueio for p in bloqueados)
    assert vencidos.count() == 2


def test_defeito_14_o_monday_com_carga_falha_ha_trinta_horas(massa):
    """A faixa precisa mostrar dado VELHO com a idade em destaque, e não sumir.

    A ordem importa e eu errei na primeira versão: a carga BOA vai para 30 h
    atrás e a falha para agora. Ao contrário, o carimbo sai tranquilo — porque a
    última tentativa foi a bem-sucedida.
    """
    from workspace.services import frescor as frs

    carimbo = frs.de("monday")

    assert carimbo.alerta is True
    assert "há 30 h" in carimbo.texto
    assert "board" in carimbo.motivo


def test_defeito_15_uma_divergencia_plantada_entre_fontes(massa):
    """Os dois valores lado a lado, e não só o vencedor.

    A tela de fontes existe para alguém ir descobrir POR QUE os sistemas
    discordam — e para isso é preciso ver o que cada um disse.
    """
    divergencia = Divergencia.objects.filter(entidade="projeto").first()

    assert divergencia is not None
    assert divergencia.fonte_a != divergencia.fonte_b
    assert divergencia.valor_a and divergencia.valor_b


# ── Porte e amostra ─────────────────────────────────────────────────


def test_as_tres_layers_existem_e_o_contrato_novo_fica_sem_amostra(massa):
    """Sem Layer 3 a regra de apresentação nunca é exercida; sem contrato novo,
    o "sem amostra" também não."""
    layers: dict[str, int] = {}
    for contrato in Contrato.objects.all():
        valor = svc.layer_de(contrato).valor
        layers[valor] = layers.get(valor, 0) + 1

    assert layers == {"1": 9, "2": 5, "3": 3, svc.SEM_AMOSTRA: 1}


def test_a_massa_nao_tem_dado_pessoal(massa):
    """Nem CPF, nem e-mail, nem nome de gente do organograma.

    A varredura é boba de propósito: ela não sabe distinguir um nome inventado
    de um real. O que ela pega é o descuido de colar dado de verdade.
    """
    textos = [
        *Contrato.objects.values_list("nome_cliente", flat=True),
        *Projeto.objects.values_list("responsavel", flat=True),
        *AvaliacaoCliente.objects.values_list("comentario", flat=True),
    ]

    for texto in textos:
        assert "@" not in texto, f"e-mail na massa: {texto}"
        assert not any(c.isdigit() and len(texto.replace(".", "").replace("-", "")) == 11
                       for c in texto), f"parece documento: {texto}"


def test_a_sazonalidade_existe_e_a_serie_nao_e_uma_reta(massa):
    """Série sem sazonalidade vira reta e não testa gráfico nenhum.

    Dezembro e janeiro fracos, março e setembro com pico de instalação — que é a
    sazonalidade real da segurança eletrônica.
    """
    from django.db.models import Sum

    por_mes = {
        linha["mes"]: linha["total"]
        for linha in CompetenciaResultado.objects.filter(contrato__isnull=False)
        .values("mes")
        .annotate(total=Sum("receita_bruta"))
    }
    if 12 not in por_mes or 3 not in por_mes:
        pytest.skip("a janela de 24 meses não cobriu dezembro e março")

    assert por_mes[3] > por_mes[12], "março tem de faturar mais que dezembro"
