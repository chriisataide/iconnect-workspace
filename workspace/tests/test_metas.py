"""Metas, avaliação e PDI — o quadro de uma pessoa, e como ele vira nota.

Os três que mais protegem esta onda:

1. **Quadro aprovado não muda mais.** Mover a trave no meio do ciclo é o defeito
   que a palavra "meta" existe para impedir — e é o mais fácil de cometer sem
   má-fé, corrigindo em novembro um alvo que "estava errado".
2. **Fator sem amostra não vira zero.** A meta fica não apurada, com o motivo, e
   **fora do denominador da nota**. Contá-la como zero transformaria uma fonte
   fora do ar na nota de uma pessoa.
3. **O quadro é da pessoa e de quem lidera ela.** E nenhuma tela lista pessoas
   com nota ao lado — restrição 8, no lugar em que ela é mais fácil de violar
   sem perceber.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from django.core.management import call_command
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.models.meta import (
    CicloMetas,
    GrupoMeta,
    Meta,
    QuadroMetas,
    SituacaoCiclo,
    SituacaoQuadro,
    TipoCalculo,
)
from workspace.providers import resultados as contrato
from workspace.services import fatores as cat
from workspace.services import metas as svc

pytestmark = pytest.mark.django_db


# ── Cenário ─────────────────────────────────────────────────────────


class EspelhoDeMentira(contrato.ProvedorResultadoFinanceiro, contrato.ProvedorPessoas):
    """Um espelho que o teste controla.

    `None` em qualquer campo significa "o espelho não sabe" — é o caso que
    separa "não bateu" de "não deu para medir", e é o mais importante daqui.
    """

    def __init__(self, ebitda=Decimal("120000"), turnover=Decimal("2"), linhas=3):
        self._ebitda = ebitda
        self._turnover = turnover
        self._linhas = linhas

    def _de_onde(self, competencia):
        return contrato.Procedencia(
            fonte="sankhya", chave_externa="cc-1042", competencia=competencia
        )

    def consolidado(self, escopo, competencia):
        return contrato.ConsolidadoDTO(
            procedencia=self._de_onde(competencia),
            competencia=competencia,
            receita_bruta=Decimal("500000"),
            margem_contribuicao=Decimal("180000"),
            ebitda=self._ebitda,
            linhas=self._linhas,
        )

    def quadro(self, escopo, competencia):
        if self._turnover is None:
            return None
        return contrato.QuadroDTO(
            procedencia=self._de_onde(competencia),
            centro_custo="1042",
            ano=competencia.year,
            mes=competencia.month,
            efetivo_ativo=40,
            turnover_pct=self._turnover,
            absenteismo_pct=Decimal("1.5"),
        )


@pytest.fixture
def espelho():
    """Registra o espelho de mentira e devolve o registro ao fim.

    Estado de PROCESSO: sem devolver, o teste seguinte encontraria o contrato
    apontando para um objeto morto — e culparia o app errado.
    """
    guardados = dict(contrato._provedores)
    contrato.limpar()
    falso = EspelhoDeMentira()
    contrato.registrar(falso)
    yield falso
    contrato.limpar()
    contrato._provedores.update(guardados)


@pytest.fixture
def sem_espelho():
    guardados = dict(contrato._provedores)
    contrato.limpar()
    yield
    contrato.limpar()
    contrato._provedores.update(guardados)


@pytest.fixture
def ciclo(db):
    call_command("semear_ciclo_metas", "--aplicar", "--ano", "2026", verbosity=0)
    return CicloMetas.objects.get(chave="metas-2026")


def _pessoa_com(apelido, chave_do_papel, permissoes, gestor=None, cc="1042"):
    pessoa = f.pessoa(apelido, nome=apelido.title())
    f.lotar(pessoa, gestor=gestor, centro_custo_codigo=cc)
    f.atribuir(
        pessoa,
        f.papel(chave_do_papel, list(permissoes), escopo="global"),
        escopo="global",
    )
    return pessoa


@pytest.fixture
def gestor(db):
    return _pessoa_com(
        "gestora", "gestor",
        ["met.ler.equipe", "met.definir.equipe", "met.aprovar.equipe"],
    )


@pytest.fixture
def liderado(db, gestor):
    return _pessoa_com("liderado", "colaborador", ["met.ler.proprio"], gestor=gestor)


@pytest.fixture
def quadro(ciclo, gestor, liderado):
    return svc.abrir_quadro(liderado, ciclo, gestor)


def _meta(quadro, gestor, **campos):
    padrao = {
        "descricao": "EBITDA sobre o orçado",
        "fator_1": "ebitda",
        "fator_2": "",
        "alvo": "100000",
        "grupo": GrupoMeta.FINANCEIRA,
        "peso": 1,
        "tipo_calculo": TipoCalculo.DIRETO,
    }
    padrao.update(campos)
    return svc.salvar_meta(quadro, gestor, None, **padrao)


# ── 1. Quadro aprovado não muda mais ────────────────────────────────


def test_quadro_aprovado_nao_muda_mais(quadro, gestor, espelho):
    """O teste que justifica metade da onda.

    Mover a trave no meio do ciclo é o defeito que a palavra "meta" existe para
    impedir — e é o mais fácil de cometer sem má-fé.
    """
    meta = _meta(quadro, gestor)
    svc.aprovar(quadro, gestor)
    quadro.refresh_from_db()

    with pytest.raises(svc.MetaError, match="reabra o quadro"):
        svc.salvar_meta(
            quadro, gestor, meta, descricao="EBITDA sobre o orçado",
            fator_1="ebitda", alvo="1",
        )
    with pytest.raises(svc.MetaError):
        _meta(quadro, gestor, descricao="uma meta nova depois de aprovado")
    with pytest.raises(svc.MetaError):
        svc.remover_meta(meta, gestor)

    meta.refresh_from_db()
    assert meta.alvo == Decimal("100000")
    assert quadro.metas.count() == 1


def test_reabrir_exige_motivo_e_deixa_registro(quadro, gestor, espelho):
    """Reabrir é legítimo. O que não pode é acontecer em silêncio: um quadro
    reaberto três vezes num ciclo é um achado sobre como as metas foram
    definidas."""
    _meta(quadro, gestor)
    svc.aprovar(quadro, gestor)
    quadro.refresh_from_db()

    with pytest.raises(svc.MetaError, match="motivo"):
        svc.reabrir(quadro, gestor, motivo="   ")

    svc.reabrir(quadro, gestor, motivo="O alvo de EBITDA foi escrito errado.")
    quadro.refresh_from_db()

    assert quadro.situacao == SituacaoQuadro.RASCUNHO
    assert quadro.aprovado_em is None
    assert len(quadro.reaberturas) == 1
    assert "escrito errado" in quadro.reaberturas[0]["motivo"]
    assert quadro.reaberturas[0]["quem"] == "Gestora"


def test_quadro_apurado_nao_reabre(quadro, gestor, espelho):
    """A nota já foi para o comitê. Reabrir permitiria reescrever a meta depois
    de saber o resultado dela."""
    _meta(quadro, gestor)
    svc.aprovar(quadro, gestor)
    svc.apurar(quadro, gestor)
    quadro.refresh_from_db()

    with pytest.raises(svc.MetaError, match="não reabre"):
        svc.reabrir(quadro, gestor, motivo="quero mudar")


def test_quadro_vazio_nao_e_aprovado(quadro, gestor):
    """Quadro vazio aprovado é a forma mais silenciosa de não ter metas: conta
    como aprovado no painel e não cobra nada de ninguém."""
    with pytest.raises(svc.MetaError, match="sem meta nenhuma"):
        svc.aprovar(quadro, gestor)


def test_so_quadro_aprovado_e_apurado(quadro, gestor, espelho):
    """Apurar rascunho permitiria escrever a meta depois de ver o número."""
    _meta(quadro, gestor)

    with pytest.raises(svc.MetaError, match="Aprove primeiro"):
        svc.apurar(quadro, gestor)


# ── 2. Fator sem amostra não vira zero ──────────────────────────────


def test_fator_sem_amostra_nao_vira_zero(quadro, gestor, espelho):
    """A diferença entre "não bateu" e "não deu para medir" é a diferença entre
    uma conversa e uma injustiça."""
    espelho._turnover = None  # o espelho não sabe responder sobre pessoas
    _meta(
        quadro, gestor, descricao="Turnover abaixo de 3%", fator_1="turnover_pct",
        alvo="3", tipo_calculo=TipoCalculo.INVERSO,
    )
    svc.aprovar(quadro, gestor)

    svc.apurar(quadro, gestor)

    meta = quadro.metas.get()
    assert meta.apurada is True, "a apuração aconteceu"
    assert meta.atingimento_pct is None, "e não produziu um número"
    assert meta.realizado is None
    assert "não tem turnover" in meta.motivo_sem_apuracao


def test_a_meta_sem_apuracao_fica_fora_do_denominador_da_nota(
    quadro, gestor, espelho
):
    """Contá-la como zero transformaria uma fonte fora do ar na nota de uma
    pessoa."""
    espelho._turnover = None
    _meta(quadro, gestor, peso=1)  # ebitda: 120.000 sobre alvo 100.000 = 120%
    _meta(
        quadro, gestor, descricao="Turnover", fator_1="turnover_pct", alvo="3",
        tipo_calculo=TipoCalculo.INVERSO, peso=9,
    )
    svc.aprovar(quadro, gestor)
    svc.apurar(quadro, gestor)
    quadro.refresh_from_db()

    # Só a meta de peso 1 foi apurada. A nota é 120, e não 12 — que é o que sairia
    # se a de peso 9 entrasse como zero.
    assert quadro.nota == Decimal("120.0")
    assert len(quadro.nao_apuradas) == 1


def test_sem_nenhuma_meta_apurada_a_nota_e_none_e_nunca_zero(
    quadro, gestor, sem_espelho
):
    """"—" e não "0". Zero seria uma afirmação de que a pessoa falhou."""
    _meta(quadro, gestor)
    svc.aprovar(quadro, gestor)
    svc.apurar(quadro, gestor)
    quadro.refresh_from_db()

    assert quadro.nota is None
    assert quadro.metas.get().atingimento_pct is None


def test_consolidado_sem_linhas_nao_e_zero(quadro, gestor, espelho):
    """Zero linhas e soma zero são a mesma aparência e coisas diferentes — é o
    campo `linhas` do DTO existindo exatamente para isto."""
    espelho._linhas = 0
    _meta(quadro, gestor)
    svc.aprovar(quadro, gestor)
    svc.apurar(quadro, gestor)

    meta = quadro.metas.get()
    assert meta.atingimento_pct is None
    assert "não tem ebitda" in meta.motivo_sem_apuracao.lower()


def test_divisor_zero_diz_que_e_zero_e_nao_que_falta(quadro, gestor, espelho):
    """Divisor zero e divisor ausente levam ao mesmo lugar, e a mensagem
    distingue os dois — porque as ações são outras."""
    from workspace.providers import orcamento as orc

    class SemTeto(orc.OrcamentoProvider):
        key = "teste"

        def orcamento_mensal(self, codigo):
            return Decimal("0")

    guardado = orc.obter()
    orc.limpar()
    orc.registrar(SemTeto())
    try:
        _meta(quadro, gestor, fator_1="ebitda", fator_2="orcamento_mensal", alvo=None)
        svc.aprovar(quadro, gestor)
        svc.apurar(quadro, gestor)
    finally:
        orc.limpar()
        if guardado is not None:
            orc.registrar(guardado)

    meta = quadro.metas.get()
    assert meta.atingimento_pct is None
    assert "é zero" in meta.motivo_sem_apuracao


# ── 3. Quem vê o quê ────────────────────────────────────────────────


def test_o_quadro_e_da_pessoa_e_de_quem_lidera_ela(
    quadro, gestor, liderado, espelho, client
):
    _meta(quadro, gestor)

    client.force_login(liderado)
    assert client.get(reverse("workspace:metas")).status_code == 200

    client.force_login(gestor)
    resposta = client.get(
        reverse("workspace:metas_de", kwargs={"pessoa_id": liderado.pk})
    )
    assert resposta.status_code == 200
    assert b"EBITDA" in resposta.content


def test_colega_nao_ve_o_quadro_de_colega(quadro, gestor, liderado, client):
    colega = _pessoa_com("colega", "colega_de_equipe", ["met.ler.proprio"], gestor=gestor)
    client.force_login(colega)

    resposta = client.get(
        reverse("workspace:metas_de", kwargs={"pessoa_id": liderado.pk})
    )

    assert resposta.status_code == 403


def test_o_anonimo_nao_ve_metas(ciclo, client):
    resposta = client.get(reverse("workspace:metas"))

    assert resposta.status_code == 302
    assert "/entrar/" in resposta["Location"]


def test_o_liderado_nao_escreve_a_propria_meta(quadro, liderado):
    """A meta é combinada com quem lidera. Escrever a própria sozinho é o mesmo
    defeito que aprovar a própria."""
    with pytest.raises(svc.MetaError):
        _meta(quadro, liderado)


def test_ninguem_aprova_o_proprio_quadro(ciclo, gestor, espelho):
    """`met.aprovar.equipe` não alcança a própria pessoa: o `alvo` de `pode()` é
    quem está sendo avaliado, e o gestor não se lidera."""
    meu = QuadroMetas.objects.create(ciclo=ciclo, pessoa=gestor)
    Meta.objects.create(
        quadro=meu, descricao="minha meta", fator_1="ebitda", alvo=Decimal("1")
    )

    assert svc.pode_aprovar(meu, gestor) is False
    with pytest.raises(svc.MetaError):
        svc.aprovar(meu, gestor)


def test_a_diretoria_aprova_o_proprio_quadro_e_e_deliberado(ciclo, espelho):
    """É o único papel com `met.aprovar.global`, e é o que destrava o quadro de
    quem não tem gestor acima. Sem ele, a diretoria ficaria em rascunho para
    sempre."""
    diretor = _pessoa_com(
        "diretor", "diretoria",
        ["met.ler.global", "met.definir.global", "met.aprovar.global"],
    )
    meu = QuadroMetas.objects.create(ciclo=ciclo, pessoa=diretor)
    Meta.objects.create(
        quadro=meu, descricao="minha meta", fator_1="ebitda", alvo=Decimal("1")
    )

    assert svc.pode_aprovar(meu, diretor) is True


def test_a_lista_da_equipe_traz_situacao_e_nunca_a_nota(
    quadro, gestor, liderado, espelho, client
):
    """A restrição 8 no lugar em que ela é mais fácil de violar sem perceber:
    uma coluna de nota ao lado de uma lista de nomes é uma planilha de
    desempenho, e ela circula."""
    _meta(quadro, gestor)
    svc.aprovar(quadro, gestor)
    svc.apurar(quadro, gestor)

    linhas = svc.equipe_de(gestor, quadro.ciclo)

    assert linhas and linhas[0]["situacao"] == SituacaoQuadro.APURADO
    assert "nota" not in linhas[0]
    assert "atingimento" not in linhas[0]

    client.force_login(gestor)
    conteudo = client.get(reverse("workspace:metas")).content.decode()
    assert "Liderado" in conteudo
    assert "120.0%" not in conteudo, "a nota de terceiro não aparece na lista"


def test_o_resumo_do_rh_e_contagem_e_nao_lista(quadro, gestor, liderado, espelho):
    """A única visão agregada da onda, deliberadamente pobre: qualquer coisa a
    mais viraria um ranking."""
    _meta(quadro, gestor)
    svc.aprovar(quadro, gestor)

    resumo = svc.resumo_por_situacao(quadro.ciclo)

    assert resumo["aprovado"] == 1
    assert set(resumo) == {"total", "rascunho", "aprovado", "apurado"}


def test_meta_de_outro_quadro_nao_atravessa(ciclo, gestor, liderado, espelho):
    """O IDOR pela porta do formulário: um `pk` de meta de outro quadro
    escreveria na avaliação de outra pessoa."""
    outro = _pessoa_com("outro", "outro_colaborador", ["met.ler.proprio"], gestor=gestor)
    quadro_a = svc.abrir_quadro(liderado, ciclo, gestor)
    quadro_b = svc.abrir_quadro(outro, ciclo, gestor)
    alheia = _meta(quadro_b, gestor)

    with pytest.raises(svc.MetaError, match="não é deste quadro"):
        svc.salvar_meta(
            quadro_a, gestor, alheia, descricao="sequestrada", fator_1="ebitda",
            alvo="1",
        )


# ── A fórmula ───────────────────────────────────────────────────────


def test_a_formula_aparece_na_tela(quadro, gestor, liderado, espelho, client):
    """A meta é auditável porque a conta é pública."""
    _meta(quadro, gestor, fator_1="ebitda", fator_2="orcamento_mensal", alvo=None)
    client.force_login(liderado)

    conteudo = client.get(reverse("workspace:metas")).content.decode()

    assert "ebitda ÷ orcamento_mensal" in conteudo


def test_fator_fora_do_catalogo_e_recusado_na_hora(quadro, gestor):
    """Fator inventado é meta que nunca poderá ser apurada — e a descoberta
    aconteceria no fim do ciclo, quando já não dá para trocar."""
    with pytest.raises(svc.MetaError, match="Fator desconhecido"):
        _meta(quadro, gestor, fator_1="lucro_liquido")
    with pytest.raises(svc.MetaError, match="Fator desconhecido"):
        _meta(quadro, gestor, fator_1="ebitda", fator_2="inventado")


def test_meta_de_valor_absoluto_exige_alvo(quadro, gestor):
    """Sem `fator_2` e sem alvo, a meta não tem contra o que ser comparada — e
    apuraria para sempre como "não apurada"."""
    with pytest.raises(svc.MetaError, match="precisa de um alvo"):
        _meta(quadro, gestor, fator_2="", alvo=None)


def test_todo_fator_do_catalogo_declara_fonte_e_funcao(ciclo):
    """Fator "cadastrado" sem função atrás seria uma meta impossível de apurar,
    e o erro apareceria no dia da nota."""
    todos = cat.todos()

    assert todos, "o catálogo não pode nascer vazio"
    for fator in todos:
        assert fator.fonte, fator.chave
        assert callable(fator.valor), fator.chave
        assert fator.descricao, f"{fator.chave} não diz o que mede"


def test_fator_duplicado_e_recusado_no_registro(ciclo):
    """Dois fatores com a mesma chave significa que um some em silêncio — e uma
    meta apontando para o que sumiu passaria a ser apurada pela conta errada."""
    with pytest.raises(ValueError, match="Já existe fator"):
        cat.registrar(
            cat.Fator(
                chave="ebitda", rotulo="Outro EBITDA", unidade=cat.MOEDA,
                fonte="x", valor=lambda e, c: None,
            )
        )


# ── O cálculo ───────────────────────────────────────────────────────


def test_o_calculo_inverso_premia_o_menor(quadro, gestor, espelho):
    """Turnover, absenteísmo, custo: menor é melhor. Sem esta direção, quem
    perdeu metade da equipe apareceria com 140% de desempenho."""
    espelho._turnover = Decimal("2")  # alvo 3 → bateu, e sobrou
    _meta(
        quadro, gestor, descricao="Turnover", fator_1="turnover_pct", alvo="3",
        tipo_calculo=TipoCalculo.INVERSO,
    )
    svc.aprovar(quadro, gestor)
    svc.apurar(quadro, gestor)

    meta = quadro.metas.get()
    assert meta.realizado == Decimal("2.00")
    assert meta.atingimento_pct == Decimal("150.0"), "3/2 = 150%"


def test_o_calculo_inverso_pune_o_maior(quadro, gestor, espelho):
    espelho._turnover = Decimal("6")  # alvo 3 → o dobro do aceitável
    _meta(
        quadro, gestor, descricao="Turnover", fator_1="turnover_pct", alvo="3",
        tipo_calculo=TipoCalculo.INVERSO,
    )
    svc.aprovar(quadro, gestor)
    svc.apurar(quadro, gestor)

    assert quadro.metas.get().atingimento_pct == Decimal("50.0")


def test_o_atingimento_tem_teto(quadro, gestor, espelho):
    """400% numa meta de peso 3 dilui todas as outras e transforma o quadro num
    jogo de escolher a meta fácil."""
    _meta(quadro, gestor, alvo="10000")  # ebitda 120.000 = 1200%

    svc.aprovar(quadro, gestor)
    svc.apurar(quadro, gestor)

    assert quadro.metas.get().atingimento_pct == svc.TETO_DE_ATINGIMENTO


def test_a_apuracao_congela_o_carimbo_da_fonte(quadro, gestor, espelho):
    """Recalcular na leitura faria a nota de 2026 mudar em 2027, quando uma
    carga corrigisse um mês antigo. A nota é o que foi para o comitê."""
    _meta(quadro, gestor)
    svc.aprovar(quadro, gestor)
    svc.apurar(quadro, gestor)

    meta = quadro.metas.get()
    assert meta.carimbo_texto, "a meta diz de quando é o número que a pontua"
    assert meta.apurado_em is not None


def test_apurar_duas_vezes_reescreve_a_leitura_e_nao_duplica(quadro, gestor, espelho):
    """Apurar de novo é legítimo — uma carga corrigiu o mês — e não pode criar
    uma segunda meta nem uma segunda nota."""
    _meta(quadro, gestor)
    svc.aprovar(quadro, gestor)
    svc.apurar(quadro, gestor)
    quadro.refresh_from_db()

    espelho._ebitda = Decimal("50000")
    svc.apurar(quadro, gestor)
    quadro.refresh_from_db()

    assert quadro.metas.count() == 1
    assert quadro.metas.get().atingimento_pct == Decimal("50.0")


def test_o_escopo_da_apuracao_e_o_da_pessoa_avaliada(quadro, gestor, liderado):
    """A meta é sobre a operação DELA, e não sobre a de quem está olhando."""
    escopo = svc.escopo_da_pessoa(liderado)

    assert escopo.centros_custo == ("1042",)


# ── O PDI ───────────────────────────────────────────────────────────


def test_o_pdi_e_escrito_pela_propria_pessoa(ciclo, liderado, gestor, client):
    """A meta é combinada com quem lidera; o PDI é a conversa de carreira de
    quem o vive. Um PDI que só o gestor edita é um PDI que a pessoa não
    reconhece."""
    client.force_login(liderado)

    resposta = client.post(
        reverse("workspace:desenvolvimento"),
        {
            "ciclo": ciclo.chave,
            "responsabilidades": "Operação da regional sul.",
            "aspiracao_curta": "Coordenar uma equipe.",
        },
        follow=True,
    )

    plano = svc.pdi_de(liderado, ciclo)
    assert resposta.status_code == 200
    assert plano.aspiracao_curta == "Coordenar uma equipe."


def test_o_gestor_le_o_pdi_do_liderado_e_nao_escreve(ciclo, liderado, gestor, client):
    svc.salvar_pdi(liderado, ciclo, liderado, interesses="Dados.")
    client.force_login(gestor)

    conteudo = client.get(
        reverse("workspace:desenvolvimento_de", kwargs={"pessoa_id": liderado.pk})
    ).content.decode()

    assert "Dados." in conteudo
    assert "e não para redigir por ela" in conteudo
    assert 'name="aspiracao_curta"' not in conteudo


def test_a_acao_do_pdi_tem_mes_e_ano(ciclo, liderado):
    """"Fazer o curso em março de 2027" é o grão em que essa conversa acontece,
    e um seletor de dia obrigaria a inventar um número."""
    plano = svc.salvar_pdi(liderado, ciclo, liderado)

    acao = svc.acrescentar_acao(
        plano, liderado, descricao="Curso de análise de dados", mes=3, ano=2027
    )

    assert (acao.mes, acao.ano) == (3, 2027)
    assert acao.concluida is False


def test_acao_com_mes_invalido_e_recusada(ciclo, liderado):
    plano = svc.salvar_pdi(liderado, ciclo, liderado)

    with pytest.raises(svc.MetaError, match="Mês fora do calendário"):
        svc.acrescentar_acao(plano, liderado, descricao="x", mes=13, ano=2027)


def test_acao_atrasada_e_derivada_do_relogio(ciclo, liderado):
    plano = svc.salvar_pdi(liderado, ciclo, liderado)
    passada = svc.acrescentar_acao(plano, liderado, descricao="x", mes=1, ano=2020)
    futura = svc.acrescentar_acao(plano, liderado, descricao="y", mes=1, ano=2099)

    assert passada.atrasada is True
    assert futura.atrasada is False

    svc.concluir_acao(passada, liderado)
    assert passada.atrasada is False


def test_o_pdi_de_terceiro_nao_abre(ciclo, liderado, gestor, client):
    colega = _pessoa_com("colega", "colega_de_equipe", ["met.ler.proprio"], gestor=gestor)
    client.force_login(colega)

    resposta = client.get(
        reverse("workspace:desenvolvimento_de", kwargs={"pessoa_id": liderado.pk})
    )

    assert resposta.status_code == 403


# ── O ciclo e a semeadora ───────────────────────────────────────────


def test_a_competencia_de_apuracao_e_o_ultimo_mes_do_ciclo(ciclo):
    """Apurar pelo mês corrente daria notas diferentes a cada dia de acesso — e
    a nota é o que vai para o comitê."""
    assert ciclo.competencia_de_apuracao == date(2026, 12, 1)


def test_a_semeadora_e_idempotente(ciclo):
    call_command("semear_ciclo_metas", "--aplicar", "--ano", "2026", verbosity=0)

    assert CicloMetas.objects.filter(chave="metas-2026").count() == 1


def test_a_simulacao_nao_grava(db):
    call_command("semear_ciclo_metas", "--ano", "2027", verbosity=0)

    assert not CicloMetas.objects.filter(chave="metas-2027").exists()


def test_os_exemplos_nascem_em_rascunho(db, gestor, liderado):
    """Um quadro de exemplo aprovado entraria na contagem do R.H. como cobertura
    real, e a primeira pergunta da primeira reunião seria sobre um número que não
    existe."""
    call_command(
        "semear_ciclo_metas", "--aplicar", "--com-exemplos", "--ano", "2028",
        verbosity=0,
    )

    quadros = QuadroMetas.objects.filter(ciclo__chave="metas-2028")
    assert quadros.exists()
    assert all(q.situacao == SituacaoQuadro.RASCUNHO for q in quadros)
    assert all("EXEMPLO" in q.resumo for q in quadros)


def test_toda_meta_de_exemplo_aponta_para_fator_do_catalogo(db, gestor, liderado):
    """O defeito que este teste pega: um exemplo apontando para um fator que
    ninguém escreveu, e a primeira apuração de demonstração falhando inteira."""
    call_command(
        "semear_ciclo_metas", "--aplicar", "--com-exemplos", "--ano", "2029",
        verbosity=0,
    )

    orfas = [
        m.descricao
        for m in Meta.objects.filter(quadro__ciclo__chave="metas-2029")
        if cat.de(m.fator_1) is None or (m.fator_2 and cat.de(m.fator_2) is None)
    ]

    assert orfas == []


def test_ciclo_fechado_nao_recebe_quadro_novo(ciclo, gestor, liderado):
    """Abrir quadro em ciclo fechado produziria uma meta que nasce sem prazo de
    fazer nada — e ela entraria na contagem como rascunho pendente para sempre."""
    CicloMetas.objects.filter(pk=ciclo.pk).update(situacao=SituacaoCiclo.FECHADO)
    ciclo.refresh_from_db()
    novo = _pessoa_com("novato", "novato_papel", ["met.ler.proprio"], gestor=gestor)

    with pytest.raises(svc.MetaError, match="fechado"):
        svc.abrir_quadro(novo, ciclo, gestor)


def test_o_maximo_de_metas_e_um_teto_de_foco(quadro, gestor):
    """Quinze metas não são um foco: são uma lista de tarefas com peso."""
    for i in range(svc.MAXIMO_DE_METAS):
        _meta(quadro, gestor, descricao=f"meta {i}")

    with pytest.raises(svc.MetaError, match="não é foco"):
        _meta(quadro, gestor, descricao="a décima terceira")


# ── Pela view ───────────────────────────────────────────────────────
#
# Os testes acima chamam o serviço, que é onde a regra mora. Estes atravessam a
# view, que é onde a regra vira produto: a mensagem que a pessoa lê, o lugar
# para onde ela volta, e o que acontece quando o formulário chega torto.


def test_o_gestor_abre_o_quadro_do_liderado_pela_tela(ciclo, gestor, liderado, client):
    client.force_login(gestor)

    resposta = client.post(
        reverse("workspace:abrir_quadro", kwargs={"pessoa_id": liderado.pk}),
        {"ciclo": ciclo.chave},
        follow=True,
    )

    assert QuadroMetas.objects.filter(pessoa=liderado, ciclo=ciclo).exists()
    assert "aberto em rascunho" in resposta.content.decode()


def test_sem_quadro_a_tela_explica_o_que_falta(ciclo, liderado, client):
    """Estado vazio que EXPLICA — restrição 6. "Sem quadro" é diferente de "sem
    metas": o primeiro quer dizer que ninguém abriu, e a ação é de quem lidera."""
    client.force_login(liderado)

    conteudo = client.get(reverse("workspace:metas")).content.decode()

    assert "ainda não tem quadro" in conteudo
    assert "Quem lidera você é quem abre" in conteudo


def test_o_liderado_nao_ve_botao_de_abrir_o_proprio_quadro(ciclo, liderado, client):
    client.force_login(liderado)

    conteudo = client.get(reverse("workspace:metas")).content.decode()

    assert "Abrir quadro em rascunho" not in conteudo


def test_o_post_do_formulario_escreve_a_meta(quadro, gestor, client):
    client.force_login(gestor)

    resposta = client.post(
        reverse("workspace:meta_editar", kwargs={"quadro_id": quadro.pk}),
        {
            "descricao": "Margem sobre a receita",
            "fator_1": "margem_contribuicao",
            "fator_2": "receita_bruta",
            "grupo": "financeira",
            "peso": "3",
            "tipo_calculo": "direto",
            "detalhamento": "Quanto sobra de cada real faturado.",
        },
    )

    meta = quadro.metas.get()
    assert resposta.status_code == 302
    assert meta.formula == "margem_contribuicao ÷ receita_bruta"
    assert meta.peso == 3


def test_o_formulario_volta_com_o_motivo_quando_o_servico_recusa(
    quadro, gestor, client
):
    client.force_login(gestor)

    resposta = client.post(
        reverse("workspace:meta_editar", kwargs={"quadro_id": quadro.pk}),
        {"descricao": "sem fator", "fator_1": "inventado"},
        follow=True,
    )

    assert "Fator desconhecido" in resposta.content.decode()
    assert quadro.metas.count() == 0


def test_peso_nao_numerico_e_recusado_com_a_mensagem_certa(quadro, gestor, client):
    client.force_login(gestor)

    resposta = client.post(
        reverse("workspace:meta_editar", kwargs={"quadro_id": quadro.pk}),
        {"descricao": "x", "fator_1": "ebitda", "alvo": "1", "peso": "três"},
        follow=True,
    )

    assert "número inteiro" in resposta.content.decode()


def test_alvo_nao_numerico_e_recusado(quadro, gestor, client):
    client.force_login(gestor)

    resposta = client.post(
        reverse("workspace:meta_editar", kwargs={"quadro_id": quadro.pk}),
        {"descricao": "x", "fator_1": "ebitda", "alvo": "cem mil"},
        follow=True,
    )

    assert "numérico inválido" in resposta.content.decode()


def test_meta_sem_descricao_e_recusada(quadro, gestor, client):
    client.force_login(gestor)

    resposta = client.post(
        reverse("workspace:meta_editar", kwargs={"quadro_id": quadro.pk}),
        {"descricao": "   ", "fator_1": "ebitda", "alvo": "1"},
        follow=True,
    )

    assert "precisa de uma descrição" in resposta.content.decode()


def test_o_formulario_de_meta_alheia_da_404(quadro, gestor, liderado, ciclo, client):
    outro = _pessoa_com("terceiro", "papel_terceiro", ["met.ler.proprio"],
                        gestor=gestor)
    quadro_b = svc.abrir_quadro(outro, ciclo, gestor)
    alheia = _meta(quadro_b, gestor)
    client.force_login(gestor)

    resposta = client.get(
        reverse("workspace:meta_editar", kwargs={"quadro_id": quadro.pk}),
        {"meta": alheia.pk},
    )

    assert resposta.status_code == 404


def test_remover_meta_pela_tela(quadro, gestor, client):
    meta = _meta(quadro, gestor)
    client.force_login(gestor)

    client.post(
        reverse("workspace:meta_remover", kwargs={"quadro_id": quadro.pk}),
        {"meta": meta.pk},
    )

    assert quadro.metas.count() == 0


def test_remover_meta_de_quadro_aprovado_volta_com_o_motivo(
    quadro, gestor, espelho, client
):
    meta = _meta(quadro, gestor)
    svc.aprovar(quadro, gestor)
    client.force_login(gestor)

    resposta = client.post(
        reverse("workspace:meta_remover", kwargs={"quadro_id": quadro.pk}),
        {"meta": meta.pk},
        follow=True,
    )

    assert "Reabra o quadro" in resposta.content.decode()
    assert quadro.metas.count() == 1


def test_remover_meta_inexistente_da_404(quadro, gestor, client):
    client.force_login(gestor)

    resposta = client.post(
        reverse("workspace:meta_remover", kwargs={"quadro_id": quadro.pk}),
        {"meta": 999999},
    )

    assert resposta.status_code == 404


def test_aprovar_apurar_e_reabrir_pela_tela(quadro, gestor, espelho, client):
    _meta(quadro, gestor)
    client.force_login(gestor)
    url = reverse("workspace:quadro_acao", kwargs={"quadro_id": quadro.pk})

    aprovada = client.post(url, {"acao": "aprovar"}, follow=True)
    assert "Quadro aprovado" in aprovada.content.decode()

    reaberta = client.post(
        url, {"acao": "reabrir", "motivo": "alvo errado"}, follow=True
    )
    assert "motivo ficou registrado" in reaberta.content.decode()

    client.post(url, {"acao": "aprovar"})
    apurada = client.post(url, {"acao": "apurar"}, follow=True)
    assert "Quadro apurado" in apurada.content.decode()

    quadro.refresh_from_db()
    assert quadro.situacao == SituacaoQuadro.APURADO


def test_a_apuracao_avisa_quando_alguma_meta_ficou_sem_numero(
    quadro, gestor, espelho, client
):
    """"Não apurada" não é zero, e a mensagem diz isso na hora — sem ela, quem
    apurou leria a nota como se fosse sobre tudo."""
    espelho._turnover = None
    _meta(quadro, gestor)
    _meta(quadro, gestor, descricao="Turnover", fator_1="turnover_pct", alvo="3")
    svc.aprovar(quadro, gestor)
    client.force_login(gestor)

    resposta = client.post(
        reverse("workspace:quadro_acao", kwargs={"quadro_id": quadro.pk}),
        {"acao": "apurar"},
        follow=True,
    )

    assert "ficaram SEM apuração" in resposta.content.decode()


def test_acao_desconhecida_no_quadro_da_404(quadro, gestor, client):
    client.force_login(gestor)

    resposta = client.post(
        reverse("workspace:quadro_acao", kwargs={"quadro_id": quadro.pk}),
        {"acao": "apagar tudo"},
    )

    assert resposta.status_code == 404


def test_o_liderado_nao_aprova_pela_tela(quadro, gestor, liderado, espelho, client):
    _meta(quadro, gestor)
    client.force_login(liderado)

    resposta = client.post(
        reverse("workspace:quadro_acao", kwargs={"quadro_id": quadro.pk}),
        {"acao": "aprovar"},
        follow=True,
    )

    quadro.refresh_from_db()
    assert quadro.situacao == SituacaoQuadro.RASCUNHO
    assert "é de quem lidera a pessoa" in resposta.content.decode()


def test_o_quadro_de_terceiro_nao_abre_nem_para_agir(ciclo, gestor, liderado, client):
    quadro = svc.abrir_quadro(liderado, ciclo, gestor)
    de_fora = _pessoa_com("estranho", "papel_estranho", ["met.ler.proprio"])
    client.force_login(de_fora)

    assert client.get(
        reverse("workspace:meta_editar", kwargs={"quadro_id": quadro.pk})
    ).status_code == 403
    assert client.post(
        reverse("workspace:quadro_acao", kwargs={"quadro_id": quadro.pk}),
        {"acao": "aprovar"},
    ).status_code == 403


def test_ciclo_desconhecido_na_url_da_404(ciclo, liderado, client):
    client.force_login(liderado)

    resposta = client.get(reverse("workspace:metas"), {"ciclo": "metas-1999"})

    assert resposta.status_code == 404


def test_sem_ciclo_nenhum_a_tela_diz_o_que_falta(db, liderado, client):
    """Renderizar um quadro vazio faria parecer defeito. A mensagem diz qual
    comando rodar."""
    CicloMetas.objects.all().delete()
    client.force_login(liderado)

    resposta = client.get(reverse("workspace:metas"))

    assert resposta.status_code == 404


def test_o_seletor_de_ciclo_muda_a_tela(ciclo, gestor, liderado, espelho, client):
    call_command("semear_ciclo_metas", "--aplicar", "--ano", "2025", verbosity=0)
    client.force_login(liderado)

    conteudo = client.get(
        reverse("workspace:metas"), {"ciclo": "metas-2025"}
    ).content.decode()

    assert "Ciclo de metas 2025" in conteudo


def test_a_acao_do_pdi_entra_e_conclui_pela_tela(ciclo, liderado, client):
    svc.salvar_pdi(liderado, ciclo, liderado)
    client.force_login(liderado)
    url = reverse("workspace:acao_pdi")

    client.post(
        url,
        {"ciclo": ciclo.chave, "descricao": "Curso de dados", "mes": "3", "ano": "2027"},
    )
    acao = svc.pdi_de(liderado, ciclo).acoes.get()

    client.post(url, {"ciclo": ciclo.chave, "acao": "concluir", "item": acao.pk})
    acao.refresh_from_db()

    assert acao.concluida is True


def test_acao_de_pdi_inexistente_da_404(ciclo, liderado, client):
    svc.salvar_pdi(liderado, ciclo, liderado)
    client.force_login(liderado)

    resposta = client.post(
        reverse("workspace:acao_pdi"),
        {"ciclo": ciclo.chave, "acao": "concluir", "item": 999999},
    )

    assert resposta.status_code == 404


def test_acao_sem_plano_da_404(ciclo, liderado, client):
    client.force_login(liderado)

    resposta = client.post(
        reverse("workspace:acao_pdi"),
        {"ciclo": ciclo.chave, "descricao": "x", "mes": "1", "ano": "2027"},
    )

    assert resposta.status_code == 404


def test_acao_com_mes_invalido_volta_com_o_motivo(ciclo, liderado, client):
    svc.salvar_pdi(liderado, ciclo, liderado)
    client.force_login(liderado)

    resposta = client.post(
        reverse("workspace:acao_pdi"),
        {"ciclo": ciclo.chave, "descricao": "x", "mes": "0", "ano": "2027"},
        follow=True,
    )

    assert "Mês fora do calendário" in resposta.content.decode()


def test_pdi_em_ciclo_fechado_nao_grava(ciclo, liderado, client):
    CicloMetas.objects.filter(pk=ciclo.pk).update(situacao=SituacaoCiclo.FECHADO)
    client.force_login(liderado)

    resposta = client.post(
        reverse("workspace:desenvolvimento"),
        {"ciclo": ciclo.chave, "interesses": "Dados."},
        follow=True,
    )

    assert "fechado" in resposta.content.decode()
    assert svc.pdi_de(liderado, ciclo) is None


def test_o_trilho_mostra_metas_para_quem_esta_identificado(ciclo, liderado, client):
    client.force_login(liderado)
    conteudo = client.get(reverse("workspace:servicos")).content.decode()
    assert "/workspace/metas/" in conteudo

    client.logout()
    anonimo = client.get(reverse("workspace:servicos")).content.decode()
    assert "/workspace/metas/" not in anonimo


# ── As bordas ───────────────────────────────────────────────────────


def test_quadros_visiveis_recorta_pelo_escopo_da_permissao(
    ciclo, gestor, liderado, espelho
):
    """O escopo da permissão faz o recorte da consulta. Uma segunda regra de
    alcance escrita à mão divergiria do organograma na primeira mudança de
    gestor."""
    svc.abrir_quadro(liderado, ciclo, gestor)
    de_fora = _pessoa_com("alheio", "papel_alheio", ["met.ler.proprio"])
    rh = _pessoa_com("rh", "rh", ["met.ler.global"])

    assert svc.quadros_visiveis(gestor, ciclo).count() == 1
    assert svc.quadros_visiveis(liderado, ciclo).count() == 1
    assert svc.quadros_visiveis(de_fora, ciclo).count() == 0
    assert svc.quadros_visiveis(rh, ciclo).count() == 1


def test_sem_a_permissao_de_ler_nao_ha_quadro_nenhum(ciclo):
    sem_nada = f.pessoa("ninguem", nome="Ninguém")

    with pytest.raises(svc.SemMetas):
        svc.quadros_visiveis(sem_nada, ciclo)


def test_abrir_quadro_e_idempotente(ciclo, gestor, liderado):
    primeiro = svc.abrir_quadro(liderado, ciclo, gestor)
    segundo = svc.abrir_quadro(liderado, ciclo, gestor)

    assert primeiro.pk == segundo.pk
    assert QuadroMetas.objects.filter(ciclo=ciclo).count() == 1


def test_quem_nao_lidera_nao_abre_quadro(ciclo, liderado):
    alheio = _pessoa_com("intruso", "papel_intruso", ["met.ler.proprio"])

    with pytest.raises(svc.MetaError, match="exige liderar"):
        svc.abrir_quadro(liderado, ciclo, alheio)


def test_peso_zero_e_recusado(quadro, gestor):
    with pytest.raises(svc.MetaError, match="pelo menos 1"):
        _meta(quadro, gestor, peso=0)


def test_aprovar_quadro_ja_aprovado_nao_muda_nada(quadro, gestor, espelho):
    _meta(quadro, gestor)
    svc.aprovar(quadro, gestor)
    quando = quadro.aprovado_em

    svc.aprovar(quadro, gestor)

    assert quadro.aprovado_em == quando


def test_quem_nao_aprova_nao_reabre(quadro, gestor, liderado, espelho):
    _meta(quadro, gestor)
    svc.aprovar(quadro, gestor)

    with pytest.raises(svc.MetaError, match="de quem o aprovou"):
        svc.reabrir(quadro, liderado, motivo="quero mudar")


def test_quem_nao_lidera_nao_apura(quadro, gestor, liderado, espelho):
    _meta(quadro, gestor)
    svc.aprovar(quadro, gestor)

    with pytest.raises(svc.MetaError, match="de quem lidera"):
        svc.apurar(quadro, liderado)


def test_pessoa_sem_lotacao_nao_recorta_e_o_escopo_fica_vazio(ciclo):
    """Sem lotação não há de onde tirar o centro de custo. `Escopo()` vazio é a
    empresa inteira — e por isso a apuração de quem não está no organograma
    devolve o consolidado geral, que é o comportamento a documentar, não a
    esconder."""
    solto = f.pessoa("solto", nome="Solto")

    assert svc.escopo_da_pessoa(solto).tudo is True


def test_meta_apontando_para_fator_removido_nao_estoura(quadro, gestor, espelho):
    """Fator some do catálogo entre a definição e a apuração — deploy no meio do
    ciclo. A meta fica sem apuração, com o motivo, e o quadro apura o resto."""
    meta = _meta(quadro, gestor)
    _meta(quadro, gestor, descricao="segunda")
    svc.aprovar(quadro, gestor)
    Meta.objects.filter(pk=meta.pk).update(fator_1="fator_que_saiu")

    svc.apurar(quadro, gestor)

    fantasma = Meta.objects.get(pk=meta.pk)
    assert fantasma.atingimento_pct is None
    assert "não existe mais" in fantasma.motivo_sem_apuracao
    assert quadro.metas.exclude(pk=meta.pk).get().atingimento_pct is not None


def test_alvo_zero_nao_divide(quadro, gestor, espelho):
    meta = _meta(quadro, gestor)
    svc.aprovar(quadro, gestor)
    Meta.objects.filter(pk=meta.pk).update(alvo=Decimal("0"))

    svc.apurar(quadro, gestor)

    assert Meta.objects.get(pk=meta.pk).motivo_sem_apuracao == "O alvo é zero."


def test_espelho_que_estoura_nao_derruba_a_apuracao(quadro, gestor, espelho):
    """A apuração roda em lote, e uma meta que estoura não pode deixar as outras
    sem número."""
    class Explode:
        def consolidado(self, escopo, competencia):
            raise RuntimeError("o espelho respondeu HTML")

        def quadro(self, escopo, competencia):
            return None

    contrato.limpar()
    contrato._provedores[contrato.ProvedorResultadoFinanceiro] = Explode()

    _meta(quadro, gestor)
    svc.aprovar(quadro, gestor)
    svc.apurar(quadro, gestor)

    assert "falhou ao responder" in quadro.metas.get().motivo_sem_apuracao


def test_pdi_de_terceiro_nao_se_escreve_pelo_servico(ciclo, liderado, gestor):
    alheio = _pessoa_com("outro_intruso", "papel_outro_intruso", ["met.ler.proprio"])

    with pytest.raises(svc.MetaError, match="não é seu"):
        svc.salvar_pdi(liderado, ciclo, alheio, interesses="x")

    plano = svc.salvar_pdi(liderado, ciclo, liderado)
    with pytest.raises(svc.MetaError, match="não é seu"):
        svc.acrescentar_acao(plano, alheio, descricao="x", mes=1, ano=2027)

    acao = svc.acrescentar_acao(plano, liderado, descricao="x", mes=1, ano=2027)
    with pytest.raises(svc.MetaError, match="não é sua"):
        svc.concluir_acao(acao, alheio)


def test_acao_sem_descricao_e_recusada(ciclo, liderado):
    plano = svc.salvar_pdi(liderado, ciclo, liderado)

    with pytest.raises(svc.MetaError, match="precisa de uma descrição"):
        svc.acrescentar_acao(plano, liderado, descricao="  ", mes=1, ano=2027)


def test_acao_com_mes_nao_numerico_e_recusada(ciclo, liderado):
    plano = svc.salvar_pdi(liderado, ciclo, liderado)

    with pytest.raises(svc.MetaError, match="precisam ser números"):
        svc.acrescentar_acao(plano, liderado, descricao="x", mes="março", ano=2027)


def test_concluir_acao_ja_concluida_nao_muda_a_data(ciclo, liderado):
    plano = svc.salvar_pdi(liderado, ciclo, liderado)
    acao = svc.acrescentar_acao(plano, liderado, descricao="x", mes=1, ano=2027)
    svc.concluir_acao(acao, liderado)
    quando = acao.concluida_em

    svc.concluir_acao(acao, liderado)

    assert acao.concluida_em == quando


def test_a_tela_de_quadro_inexistente_de_terceiro_e_403(ciclo, gestor):
    """Sem quadro, a checagem é sobre a PESSOA — senão bastaria pedir o quadro
    de alguém que ainda não tem para descobrir que ela existe."""
    alheio = _pessoa_com("curioso", "papel_curioso", ["met.ler.proprio"])

    with pytest.raises(svc.SemMetas):
        svc.tela_do_quadro(gestor, ciclo, alheio)


def test_a_equipe_e_vazia_para_quem_nao_lidera_ninguem(ciclo, liderado):
    assert svc.equipe_de(liderado, ciclo) == []


def test_o_rh_ve_a_cobertura_de_todos_os_quadros(ciclo, gestor, liderado):
    svc.abrir_quadro(liderado, ciclo, gestor)
    rh = _pessoa_com("rh_global", "rh_metas", ["met.ler.global"])

    linhas = svc.equipe_de(rh, ciclo)

    assert len(linhas) == 1
    assert "nota" not in linhas[0]


def test_o_ciclo_corrente_prefere_o_aberto_e_cai_no_ultimo_fechado(db):
    call_command("semear_ciclo_metas", "--aplicar", "--ano", "2024", verbosity=0)
    call_command("semear_ciclo_metas", "--aplicar", "--ano", "2026", verbosity=0)

    assert svc.ciclo_corrente().chave == "metas-2026"

    CicloMetas.objects.update(situacao=SituacaoCiclo.FECHADO)
    assert svc.ciclo_corrente().chave == "metas-2026", "cai no último, e não em nada"


def test_o_catalogo_recusa_quem_nao_e_fator(ciclo):
    with pytest.raises(TypeError, match="não é um Fator"):
        cat.registrar({"chave": "gambiarra"})


def test_carimbo_de_fator_desconhecido_e_none(ciclo):
    assert cat.carimbo_de("nao_existe") is None


def test_fator_de_orcamento_sem_provedor_devolve_none(quadro, gestor, espelho):
    """Sem `financas` instalado, o fator não sabe responder — e a meta fica sem
    apuração, em vez de valer zero."""
    from workspace.providers import orcamento as orc

    guardado = orc.obter()
    orc.limpar()
    try:
        escopo = svc.escopo_da_pessoa(quadro.pessoa)
        assert cat.de("orcamento_mensal").valor(escopo, date(2026, 12, 1)) is None
        assert cat.de("realizado_no_mes").valor(escopo, date(2026, 12, 1)) is None
    finally:
        if guardado is not None:
            orc.registrar(guardado)


def test_fator_de_orcamento_sem_centro_de_custo_devolve_none(ciclo, gestor):
    """Somar o orçamento da empresa inteira exigiria enumerar todo centro de
    custo — e um total que muda quando alguém cadastra um CC novo não é
    denominador de meta."""
    from workspace.providers import resultados as res

    vazio = res.Escopo()
    assert cat.de("orcamento_mensal").valor(vazio, date(2026, 12, 1)) is None
    assert cat.de("realizado_no_mes").valor(vazio, date(2026, 12, 1)) is None


def test_o_str_de_cada_model_diz_o_que_e(ciclo, quadro, gestor, liderado):
    """`__str__` aparece no `/admin/` e em toda mensagem de erro. Um `<QuadroMetas
    object (3)>` numa lista de trinta é uma tela inútil."""
    meta = _meta(quadro, gestor)
    plano = svc.salvar_pdi(liderado, ciclo, liderado)
    acao = svc.acrescentar_acao(plano, liderado, descricao="Curso", mes=3, ano=2027)
    fator = cat.de("ebitda")

    assert str(ciclo) == "Ciclo de metas 2026"
    assert "metas-2026" in str(quadro)
    assert str(meta) == "EBITDA sobre o orçado"
    assert "PDI" in str(plano)
    assert "03/2027" in str(acao)
    assert str(fator) == "EBITDA"


def test_a_semeadora_de_exemplos_nao_duplica_quadro_existente(db, gestor, liderado):
    call_command(
        "semear_ciclo_metas", "--aplicar", "--com-exemplos", "--ano", "2030",
        verbosity=0,
    )
    antes = QuadroMetas.objects.filter(ciclo__chave="metas-2030").count()

    call_command(
        "semear_ciclo_metas", "--aplicar", "--com-exemplos", "--ano", "2030",
        verbosity=0,
    )

    assert QuadroMetas.objects.filter(ciclo__chave="metas-2030").count() == antes


def test_a_simulacao_com_exemplos_conta_sem_gravar(db, gestor, liderado):
    call_command("semear_ciclo_metas", "--com-exemplos", "--ano", "2031", verbosity=0)

    assert not CicloMetas.objects.filter(chave="metas-2031").exists()
    assert not QuadroMetas.objects.filter(ciclo__chave="metas-2031").exists()
