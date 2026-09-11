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
    # O PLANO DE CONTAS antes da massa: o razão por conta aponta para ele, e
    # sem plano o seeder pula o razão inteiro (com aviso). A ordem é a mesma
    # que o guia de QA manda seguir.
    _rodar("semear_plano_de_contas", "--aplicar")
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
        contrato__codigo="CT-102", custo_direto__isnull=True, receita_bruta__gt=0
    )

    assert sem_custo.exists(), "o custo ausente é NULO, e não zero"
    # E o zero continua existindo como número: um mês em que o custo foi zero é
    # outra coisa, e o espelho precisa saber dizer as duas.
    assert not CompetenciaResultado.objects.filter(
        contrato__codigo="CT-102", custo_direto=0
    ).exists()


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


# ── O razão por conta — bloco D ─────────────────────────────────────


def test_o_razao_fecha_com_o_agregado_em_TODA_competencia(massa):
    """A única coisa que o bloco D não pode errar.

    A tabela contábil aparece logo abaixo da faixa do dinheiro. Se a soma das
    contas de um contrato não der exatamente receita + impostos + custo direto
    daquele mês, as duas discordam na mesma tela — e quem confere para de
    acreditar nas duas.

    Confere TODAS, e não uma amostra: o erro de arredondamento que a
    decomposição pode introduzir não aparece em todo mês, e uma amostra o
    encontraria em uma execução e não na seguinte.
    """
    from decimal import Decimal

    from django.db.models import Sum

    from resultados.models import CompetenciaResultado, ResultadoPorConta

    meses = set(ResultadoPorConta.objects.values_list("ano", "mes"))
    assert meses, "sem razão não há o que conferir"

    divergentes = []
    for competencia in CompetenciaResultado.objects.filter(
        contrato__isnull=False
    ).select_related("contrato"):
        if (competencia.ano, competencia.mes) not in meses:
            # Fora da janela do razão — ver `MESES_DE_RAZAO`. A tabela diz
            # "sem lançamento" nesses meses, e não há o que fechar.
            continue
        esperado = (
            (competencia.receita_bruta or Decimal("0"))
            + (competencia.impostos or Decimal("0"))
            + (competencia.custo_direto or Decimal("0"))
        )
        soma = ResultadoPorConta.objects.filter(
            contrato=competencia.contrato,
            ano=competencia.ano,
            mes=competencia.mes,
        ).aggregate(t=Sum("valor_realizado"))["t"] or Decimal("0")
        if esperado != soma:
            divergentes.append(
                f"{competencia.contrato.codigo} {competencia.mes:02d}/"
                f"{competencia.ano}: agregado {esperado} × razão {soma}"
            )

    assert not divergentes, "o detalhe não fecha com o total: " + "; ".join(
        divergentes[:5]
    )


def test_nenhuma_linha_do_razao_cai_em_conta_desconhecida(massa):
    """"Conta não cadastrada" existe para o dia em que a fonte real mandar um
    código novo — e não para a massa se enganar sozinha.

    Ela já se enganou uma vez: 431 linhas nasceram apontando para `41801001`,
    `41403003` e `41505003`, que não existem no plano porque aqueles grupos são
    lançados direto no sintético. O sintoma era um aviso na tela sobre um
    problema que o próprio seeder criou.
    """
    from resultados.models import ResultadoPorConta

    orfas = ResultadoPorConta.objects.filter(conta__isnull=True)

    assert not orfas.exists(), (
        "códigos fora do plano: "
        + ", ".join(sorted(set(orfas.values_list("codigo_origem", flat=True)))[:8])
    )


def test_o_rateio_de_centro_de_custo_tem_razao_tambem(massa):
    """Sem ele a tabela contábil não fecha com a faixa do dinheiro: os rateios
    entram numa e não na outra, e a diferença é o custo indireto inteiro."""
    from resultados.models import ResultadoPorConta

    assert ResultadoPorConta.objects.filter(contrato__isnull=True).exists()


def test_o_peso_das_contas_MUDA_com_o_tipo_de_servico(massa):
    """É isto que torna o detalhamento útil.

    Sem a diferença, todo contrato tem a mesma cara e abrir a tabela não ensina
    nada — a pessoa olha uma vez e não volta. Monitoramento pesa em pessoal;
    manutenção, em transportes e equipamento.
    """
    from django.db.models import Sum

    from resultados.models import Contrato, ResultadoPorConta

    def perfil(servico: str) -> dict[str, float]:
        codigos = Contrato.objects.filter(servico=servico).values_list(
            "codigo", flat=True
        )
        linhas = ResultadoPorConta.objects.filter(
            contrato__codigo__in=list(codigos), conta__isnull=False
        )
        total = linhas.aggregate(t=Sum("valor_realizado"))["t"] or 0
        if not total:
            return {}
        por_grupo = linhas.values("conta__pai__codigo", "conta__codigo").annotate(
            t=Sum("valor_realizado")
        )
        peso: dict[str, float] = {}
        for linha in por_grupo:
            grupo = linha["conta__pai__codigo"] or linha["conta__codigo"]
            peso[grupo] = peso.get(grupo, 0) + float(linha["t"]) / float(total)
        return peso

    monitoramento = perfil("monitoramento")
    manutencao = perfil("manutencao")
    assert monitoramento and manutencao, "a massa precisa dos dois serviços"

    # Pessoal pesa MAIS no monitoramento; transportes, mais na manutenção.
    assert monitoramento.get("41101", 0) > manutencao.get("41101", 0)
    assert manutencao.get("41301", 0) > monitoramento.get("41301", 0)


def test_semear_duas_vezes_no_MESMO_dia_nao_escreve_nada(massa):
    """Idempotência — e o defeito que este teste teria pego.

    A chave de negócio da avaliação é `(contrato, data)` e a `chave_externa` era
    fixa (`plt-av-0`). Com a data saindo de `hoje`, semear num dia diferente do
    anterior criava uma data que não casava com linha nenhuma: o carregador
    tentava CRIAR e batia no `UNIQUE (fonte, chave_externa)`.

    O sintoma era uma carga `parcial` — "a fonte mandou o mesmo registro duas
    vezes" — e ficou escondido porque a suíte semeia uma vez, num dia só. Só
    apareceu quando uma sessão de trabalho atravessou a meia-noite.

    Este teste segura o caso do mesmo dia. O do dia seguinte está logo abaixo.
    """
    from cargas.models import ExecucaoCarga, StatusCarga

    _rodar("semear_resultados", "--aplicar")

    ultimas = ExecucaoCarga.objects.order_by("-id")[:3]
    assert all(e.status == StatusCarga.SUCESSO for e in ultimas), [
        (e.fonte.chave, e.status, e.erro_resumo) for e in ultimas
    ]


def test_semear_no_DIA_SEGUINTE_tambem_e_idempotente(massa, monkeypatch):
    """O caso que o defeito real produzia. Ancorar as avaliações no primeiro dia
    do mês é o que faz o segundo dia encontrar as mesmas linhas."""
    from datetime import timedelta

    from django.utils import timezone

    from cargas.management.commands import semear_resultados as comando
    from cargas.models import ExecucaoCarga, StatusCarga

    amanha = timezone.localdate() + timedelta(days=1)

    # Só `localdate`, e não o módulo inteiro: o carregador usa `timezone.now`
    # no mesmo módulo, e substituí-lo por um objeto sem `now` quebrava a carga
    # por uma razão que não tem nada a ver com o que este teste afirma.
    monkeypatch.setattr(
        comando.timezone, "localdate", staticmethod(lambda: amanha)
    )
    _rodar("semear_resultados", "--aplicar")

    ultimas = ExecucaoCarga.objects.order_by("-id")[:3]
    assert all(e.status == StatusCarga.SUCESSO for e in ultimas), [
        (e.fonte.chave, e.status, e.erro_resumo) for e in ultimas
    ]


def test_sem_plano_de_contas_o_seeder_AVISA_em_vez_de_sujar(db):
    """O achado de 09/09/2026, e o motivo de o aviso existir.

    O razão aponta para o plano de contas. Sem ele, as três mil linhas nasciam
    com `conta` nula — e a tela dizia "3.000 lançamentos vieram com códigos que
    não estão no plano de contas", um alarme sobre um problema que o próprio
    seeder tinha criado. Ficou escondido porque o banco de desenvolvimento já
    tinha o plano semeado à mão.

    A massa continua sendo gerada: ela é válida sem o bloco D, e quem só quer
    ver as outras faixas não deve ser bloqueado por causa dele.
    """
    from resultados.models import ResultadoPorConta

    _rodar("semear_fontes", "--aplicar")
    saida = _rodar("semear_resultados", "--aplicar")

    assert "plano de contas está vazio" in saida
    assert "semear_plano_de_contas" in saida
    assert not ResultadoPorConta.objects.exists(), "nenhuma linha órfã"
    # E o resto da massa entrou.
    from resultados.models import Contrato

    assert Contrato.objects.exists()
