"""Plano de ação com limiar — a regra dos 10% do benchmark, generalizada.

Os três que mais protegem esta onda:

1. **O desfecho é reverificado, nunca declarado.** Um plano fecha como
   *resolvido* só quando a regra parou de encontrar a ocorrência. Fechar
   dizendo que resolveu, com a regra ainda disparando, grava *não resolvido*.
   Sem isso, a tela mede quem preenche formulário.
2. **Ocorrência que deve plano e não tem aparece como DÍVIDA.** E não some
   quando alguém escreve justificativa sem ação, nem quando o prazo passa.
3. **Fonte fora do ar não fecha plano nenhum.** Um conector caído fecharia como
   resolvido todo plano que dependesse dele — um mês inteiro de metas batidas
   por causa de uma credencial vencida.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace import excecoes as reg
from workspace.excecoes.base import Ocorrencia, RegraBase
from workspace.models.excecao import RegraExcecao
from workspace.models.plano import PlanoAcao, SituacaoPlano, VerificacaoPlano
from workspace.services import planos as svc

pytestmark = pytest.mark.django_db


# ── Cenário ─────────────────────────────────────────────────────────


class RegraDeMentira(RegraBase):
    """Um avaliador que o teste controla.

    Substitui o registrado sob a mesma chave: exercitar o desfecho pela regra de
    margem real exigiria montar um espelho inteiro por teste, e o que está sob
    prova aqui é a MECÂNICA do plano, não a regra.
    """

    chave = "margem-abaixo-de-10"
    fonte = "iconnect_platform"

    def __init__(self, chaves=("contrato:CT-100",), disponivel=True, estoura=False):
        self.chaves = list(chaves)
        self._disponivel = disponivel
        self.estoura = estoura

    def disponivel(self) -> bool:
        return self._disponivel

    def avaliar(self, janela: int):
        if self.estoura:
            raise RuntimeError("a fonte respondeu HTML")
        return [
            Ocorrencia(
                chave=c,
                titulo=f"{c.split(':')[-1]} · Cliente de Mentira",
                detalhe="margem de 4,2%",
                responsavel="Fulano",
                papel="financeiro",
            )
            for c in self.chaves
        ]


@pytest.fixture
def regras(db):
    call_command("semear_regras_excecao", "--aplicar", verbosity=0)
    return {r.chave: r for r in RegraExcecao.objects.all()}


@pytest.fixture
def margem(regras):
    return RegraExcecao.objects.get(chave="margem-abaixo-de-10")


@pytest.fixture
def avaliador(regras):
    """Troca o avaliador de `margem-abaixo-de-10` e devolve o de mentira."""
    original = reg.regra_de("margem-abaixo-de-10")
    falso = RegraDeMentira()
    reg.registrar(falso, substituir=True)
    yield falso
    if original is not None:
        reg.registrar(original, substituir=True)


def _com_papel(apelido, chave_do_papel, permissoes=()):
    pessoa = f.pessoa(apelido, nome=apelido.title())
    f.lotar(pessoa, centro_custo_codigo="1042")
    f.atribuir(
        pessoa,
        f.papel(chave_do_papel, list(permissoes), escopo="global"),
        escopo="global",
    )
    return pessoa


@pytest.fixture
def responde(db):
    """Quem atende a regra de margem: o Financeiro."""
    return _com_papel(
        "financeiro", "financeiro", ["exc.ler.global", "pla.responder.global"]
    )


@pytest.fixture
def so_le(db):
    """Vê a regra e NÃO responde por ela.

    Papel `auditoria` e não `financeiro`: quem vê a regra pelo `exc.ler.global`
    vê o painel inteiro, e é justamente esse o caso que separa ler de responder
    — o auditor acompanha o plano do Financeiro sem poder fechá-lo.
    """
    return _com_papel("auditor", "auditoria", ["exc.ler.global"])


def _plano(margem, responde, prazo_em=10, chave="contrato:CT-100"):
    """Abre um plano pelo serviço. `prazo_em` negativo produz um VENCIDO.

    O serviço recusa prazo no passado, e com razão: um plano que nasce vencido
    fecharia na primeira verificação, antes de alguém ter tido um dia para agir.
    Para simular o tempo passando, o teste abre com prazo válido e recua a data
    por `update()` — que é o que o relógio faz, e sem passar pela validação de
    novo.
    """
    plano = svc.abrir(
        margem,
        chave,
        responde,
        justificativa="Reajuste não repassado no aniversário do contrato.",
        acao="Renegociar o índice com o cliente até o fechamento do trimestre.",
        responsavel=responde,
        prazo=timezone.localdate() + timedelta(days=abs(prazo_em) or 1),
    )
    if prazo_em < 0:
        PlanoAcao.objects.filter(pk=plano.pk).update(
            prazo=timezone.localdate() + timedelta(days=prazo_em)
        )
        plano.refresh_from_db()
    return plano


# ── 1. O desfecho é reverificado, e não declarado ───────────────────


def test_o_desfecho_e_reverificado_e_nao_declarado(margem, avaliador, responde):
    """O teste que justifica a onda inteira.

    Quem fecha escreve o que aconteceu; quem decide se resolveu é a regra. Sem
    isto, a tela mede quem preenche formulário.
    """
    plano = _plano(margem, responde)

    fechado = svc.fechar(plano, responde, desfecho="Resolvido, pode fechar.")

    assert fechado.situacao == SituacaoPlano.NAO_RESOLVIDO
    assert fechado.verificacoes.get().ainda_ocorre is True
    # O texto de quem fechou FICA — ele é o que a pessoa entendeu, e some junto
    # com a chance de descobrir por que ela entendeu errado.
    assert fechado.desfecho == "Resolvido, pode fechar."


def test_o_plano_fecha_como_resolvido_quando_a_regra_para_de_encontrar(
    margem, avaliador, responde
):
    plano = _plano(margem, responde)
    avaliador.chaves = []

    fechado = svc.fechar(plano, responde, desfecho="Índice renegociado.")

    assert fechado.situacao == SituacaoPlano.RESOLVIDO
    assert fechado.verificacoes.get().ainda_ocorre is False
    assert fechado.fechado_em is not None


def test_o_vencimento_confere_sozinho_e_sem_opiniao(margem, avaliador, responde):
    """É o comando do cron. Ninguém clica, e o desfecho é o da regra."""
    plano = _plano(margem, responde, prazo_em=-10)
    avaliador.chaves = []

    call_command("verificar_planos", "--aplicar", verbosity=0)

    plano.refresh_from_db()
    assert plano.situacao == SituacaoPlano.RESOLVIDO
    assert "Conferido no vencimento" in plano.desfecho


def test_o_vencimento_fecha_como_nao_resolvido_quando_a_ocorrencia_persiste(
    margem, avaliador, responde
):
    plano = _plano(margem, responde, prazo_em=-10)

    call_command("verificar_planos", "--aplicar", verbosity=0)

    plano.refresh_from_db()
    assert plano.situacao == SituacaoPlano.NAO_RESOLVIDO


def test_a_carencia_segura_o_plano_que_acabou_de_vencer(margem, avaliador, responde):
    """O cron pode ter ficado fora do ar. Fechar no primeiro dia em que a
    máquina voltou, com a fonte ainda subindo, daria desfecho aleatório."""
    _plano(margem, responde, prazo_em=-1)

    assert svc.vencidos_para_verificar() == []


def test_o_historico_de_conferencias_mostra_o_que_some_e_volta(
    margem, avaliador, responde
):
    """Guardar só a última esconderia o padrão mais caro de todos: o problema
    que se resolve e reaparece."""
    plano = _plano(margem, responde)

    svc.verificar(plano)
    avaliador.chaves = []
    svc.verificar(plano)
    avaliador.chaves = ["contrato:CT-100"]
    svc.verificar(plano)

    assert [v.ainda_ocorre for v in plano.verificacoes.all()] == [True, False, True]


# ── 2. A dívida ─────────────────────────────────────────────────────


def test_ocorrencia_que_exige_plano_e_nao_tem_aparece_como_divida(
    margem, avaliador, responde, client
):
    """"Dívida" e não "pendência": a obrigação já existe, e o que falta é a
    resposta."""
    client.force_login(responde)

    resposta = client.get(reverse("workspace:planos"))

    dividas = resposta.context["dividas"]
    assert [d.chave for d in dividas] == ["contrato:CT-100"]
    assert b"Devem plano" in resposta.content


def test_a_divida_some_quando_o_plano_e_aberto_e_volta_quando_ele_fecha(
    margem, avaliador, responde
):
    """O contrato que continua abaixo do limiar depois de um plano fechado volta
    a dever resposta. É o ciclo inteiro, e é o que impede um plano de valer para
    sempre."""
    plano = _plano(margem, responde)
    assert svc.dividas_de(responde) == []

    svc.fechar(plano, responde)

    assert [d.chave for d in svc.dividas_de(responde)] == ["contrato:CT-100"]


def test_plano_sem_justificativa_ou_sem_acao_nao_entra(margem, avaliador, responde):
    """As duas metades da exigência do benchmark. Ação sem justificativa é
    tarefa sem diagnóstico."""
    with pytest.raises(svc.PlanoError):
        svc.abrir(margem, "contrato:CT-100", responde, justificativa="  ",
                  acao="renegociar", responsavel=responde)
    with pytest.raises(svc.PlanoError):
        svc.abrir(margem, "contrato:CT-100", responde, justificativa="reajuste",
                  acao="   ", responsavel=responde)

    assert PlanoAcao.objects.count() == 0


def test_nao_ha_dois_planos_abertos_para_a_mesma_ocorrencia(
    margem, avaliador, responde
):
    """Dois planos abertos produzem duas versões do que a empresa vai fazer, e a
    reverificação fecharia as duas com o mesmo desfecho."""
    _plano(margem, responde)

    with pytest.raises(svc.PlanoError):
        _plano(margem, responde)

    assert PlanoAcao.objects.abertos().count() == 1


def test_o_mesmo_contrato_pode_ter_um_plano_novo_depois_de_um_fechado(
    margem, avaliador, responde
):
    """A margem cair de novo em março depois de um plano cumprido em janeiro é
    justamente o que o histórico precisa mostrar."""
    primeiro = _plano(margem, responde)
    svc.fechar(primeiro, responde)

    segundo = _plano(margem, responde)

    assert segundo.pk != primeiro.pk
    assert PlanoAcao.objects.count() == 2


def test_plano_sobre_ocorrencia_que_sumiu_e_recusado(margem, avaliador, responde):
    """Registrar um plano sobre um problema que já não existe produziria um
    plano que fecha como resolvido sem ninguém ter feito nada — e a efetividade
    da tela subiria de graça."""
    avaliador.chaves = []

    with pytest.raises(svc.PlanoError):
        _plano(margem, responde)


def test_prazo_no_passado_e_recusado(margem, avaliador, responde):
    """Um plano que nasce vencido fecharia na primeira verificação, antes de
    alguém ter tido um dia para agir."""
    with pytest.raises(svc.PlanoError):
        svc.abrir(
            margem, "contrato:CT-100", responde,
            justificativa="reajuste", acao="renegociar", responsavel=responde,
            prazo=timezone.localdate() - timedelta(days=1),
        )

    assert PlanoAcao.objects.count() == 0


def test_regra_sem_limiar_nao_aceita_plano(regras, responde):
    """Plano em regra que não gera obrigação viraria uma segunda lista de
    tarefas, ao lado do catálogo — que já existe e é onde trabalho pedido mora."""
    sem_limiar = RegraExcecao.objects.get(chave="cc-comprometido")

    with pytest.raises(svc.PlanoError):
        svc.abrir(sem_limiar, "cc:1042", responde, justificativa="x", acao="y",
                  responsavel=responde)


# ── 3. Fonte fora do ar ─────────────────────────────────────────────


def test_fonte_fora_do_ar_nao_fecha_plano_nenhum(margem, avaliador, responde):
    """Um conector caído fecharia como resolvido todo plano que dependesse dele
    — um mês inteiro de metas batidas por causa de uma credencial vencida."""
    plano = _plano(margem, responde, prazo_em=-10)
    avaliador._disponivel = False

    call_command("verificar_planos", "--aplicar", verbosity=0)

    plano.refresh_from_db()
    assert plano.situacao == SituacaoPlano.ABERTO
    verificacao = plano.verificacoes.get()
    assert verificacao.avaliada is False
    assert verificacao.ainda_ocorre is True, "na dúvida, o problema continua"


def test_fechar_a_mao_com_a_fonte_fora_do_ar_recusa(margem, avaliador, responde):
    plano = _plano(margem, responde)
    avaliador._disponivel = False

    with pytest.raises(svc.PlanoError):
        svc.fechar(plano, responde, desfecho="resolvi")

    plano.refresh_from_db()
    assert plano.situacao == SituacaoPlano.ABERTO


def test_regra_que_estoura_nao_fecha_plano_e_nao_derruba_o_comando(
    margem, avaliador, responde
):
    """O comando roda no cron, sem ninguém olhando. Uma regra que estoura não
    pode deixar os outros planos sem conferência."""
    plano = _plano(margem, responde, prazo_em=-10)
    avaliador.estoura = True

    call_command("verificar_planos", "--aplicar", verbosity=0)

    plano.refresh_from_db()
    assert plano.situacao == SituacaoPlano.ABERTO
    assert plano.verificacoes.get().avaliada is False


def test_regra_nao_avaliada_nao_gera_divida(margem, avaliador, responde):
    """Cobrar plano por uma ocorrência que ninguém conseguiu verificar seria
    cobrar do responsável a queda de um conector."""
    avaliador._disponivel = False

    assert svc.dividas_de(responde) == []


def test_regra_saida_do_catalogo_nao_derruba_o_plano(margem, avaliador, responde):
    """O plano é registro de uma decisão tomada. Ele sobrevive à regra."""
    plano = _plano(margem, responde, prazo_em=-10)
    RegraExcecao.objects.filter(chave="margem-abaixo-de-10").delete()

    call_command("verificar_planos", "--aplicar", verbosity=0)

    plano.refresh_from_db()
    assert plano.situacao == SituacaoPlano.ABERTO
    assert plano.verificacoes.get().avaliada is False


# ── A fronteira ─────────────────────────────────────────────────────


def test_quem_ve_a_regra_le_o_plano_e_so_o_papel_responde(
    margem, avaliador, responde, so_le, client
):
    plano = _plano(margem, responde)
    client.force_login(so_le)

    assert client.get(reverse("workspace:planos")).status_code == 200
    assert client.get(
        reverse("workspace:plano", kwargs={"pk": plano.pk})
    ).status_code == 200

    assert client.post(
        reverse("workspace:fechar_plano", kwargs={"pk": plano.pk})
    ).status_code == 403
    assert client.get(
        reverse("workspace:plano_novo") + "?regra=margem-abaixo-de-10"
    ).status_code == 403


def test_o_anonimo_nao_le_plano_nenhum(margem, avaliador, client):
    resposta = client.get(reverse("workspace:planos"))

    assert resposta.status_code == 302
    assert "/entrar/" in resposta["Location"]


def test_quem_nao_acompanha_regra_com_limiar_recebe_403(margem, avaliador, client):
    """403, e não uma tela de zeros. Lista vazia diria que a empresa não cobra
    nada de ninguém."""
    de_fora = _com_papel("almoxarife", "estoque", ["est.ler.global"])
    client.force_login(de_fora)

    assert client.get(reverse("workspace:planos")).status_code == 403


def test_plano_de_regra_alheia_nao_abre(margem, avaliador, responde, client):
    plano = _plano(margem, responde)
    de_fora = _com_papel("almoxarife", "estoque", ["est.ler.global"])
    client.force_login(de_fora)

    assert client.get(
        reverse("workspace:plano", kwargs={"pk": plano.pk})
    ).status_code == 403


def test_regra_sem_papel_exige_escopo_global_para_responder(regras):
    """Um plano sobre "fonte atrasada" é da operação de dados, e não de quem
    passou pela tela — e a regra não declara papel nenhum."""
    sem_papel = RegraExcecao.objects.get(chave="fonte-atrasada")
    sem_papel.exige_plano = True
    sem_papel.save(update_fields=["exige_plano"])
    qualquer = _com_papel("gerente", "gestor",
                          ["exc.ler.global", "pla.responder.departamento"])

    assert svc.pode_responder(sem_papel, qualquer) is False


def test_sem_a_permissao_de_responder_o_papel_nao_basta(margem, so_le):
    """O papel diz QUAL regra; a permissão diz SE responde."""
    assert svc.pode_responder(margem, so_le) is False


# ── A tela ──────────────────────────────────────────────────────────


def test_a_tela_mostra_os_quatro_estados_mesmo_vazios(
    margem, avaliador, responde, client
):
    """Estado que some quando está zerado esconde que ele existe — a mesma razão
    pela qual uma regra com zero continua na lista."""
    client.force_login(responde)

    conteudo = client.get(reverse("workspace:planos")).content.decode()

    assert "Em andamento, fora do prazo" in conteudo
    assert "Em andamento, no prazo" in conteudo
    assert "NÃO resolvidos" in conteudo
    assert "Resolvidos" in conteudo


def test_a_efetividade_nao_aparece_sem_plano_fechado(
    margem, avaliador, responde, client
):
    """0% de efetividade é uma afirmação sobre um trabalho que não houve."""
    _plano(margem, responde)
    client.force_login(responde)

    resposta = client.get(reverse("workspace:planos"))

    assert resposta.context["efetividade"] is None
    assert b"dos planos fechados" not in resposta.content


def test_a_efetividade_conta_so_os_fechados(margem, avaliador, responde, client):
    primeiro = _plano(margem, responde)
    avaliador.chaves = []
    svc.fechar(primeiro, responde)
    avaliador.chaves = ["contrato:CT-100", "contrato:CT-200"]
    segundo = _plano(margem, responde, chave="contrato:CT-200")
    svc.fechar(segundo, responde)
    _plano(margem, responde)

    client.force_login(responde)
    resposta = client.get(reverse("workspace:planos"))

    assert resposta.context["efetividade"] == 50


def test_o_plano_atrasado_e_derivado_do_relogio(margem, avaliador, responde):
    """Um campo `atrasado` precisaria de um processo para mantê-lo, e o plano
    ficaria "no prazo" até o cron rodar."""
    plano = _plano(margem, responde, prazo_em=5)
    assert plano.atrasado is False
    assert plano.estado == "no_prazo"

    PlanoAcao.objects.filter(pk=plano.pk).update(
        prazo=timezone.localdate() - timedelta(days=1)
    )
    plano.refresh_from_db()

    assert plano.atrasado is True
    assert plano.estado == "fora_do_prazo"


def test_o_titulo_do_plano_e_congelado(margem, avaliador, responde):
    """Reler a regra para reconstruir o título faria um plano de março mudar de
    assunto em setembro, quando o contrato mudasse de nome."""
    plano = _plano(margem, responde)
    congelado = plano.titulo

    avaliador.chaves = []

    plano.refresh_from_db()
    assert plano.titulo == congelado
    assert "Cliente de Mentira" in congelado


def test_o_formulario_nao_abre_para_ocorrencia_que_sumiu(
    margem, avaliador, responde, client
):
    avaliador.chaves = []
    client.force_login(responde)

    resposta = client.get(
        reverse("workspace:plano_novo"),
        {"regra": "margem-abaixo-de-10", "ocorrencia": "contrato:CT-100"},
    )

    assert resposta.status_code == 200
    assert "não encontra mais esta ocorrência" in resposta.content.decode()
    assert 'name="justificativa"' not in resposta.content.decode()


def test_o_post_do_formulario_registra_o_plano(margem, avaliador, responde, client):
    client.force_login(responde)

    resposta = client.post(
        reverse("workspace:plano_novo"),
        {
            "regra": "margem-abaixo-de-10",
            "ocorrencia": "contrato:CT-100",
            "justificativa": "Reajuste não repassado.",
            "acao": "Renegociar o índice.",
            "responsavel": responde.pk,
            "prazo": (timezone.localdate() + timedelta(days=20)).isoformat(),
        },
    )

    plano = PlanoAcao.objects.get()
    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("workspace:plano", kwargs={"pk": plano.pk})
    assert plano.responsavel_id == responde.pk


def test_o_trilho_so_mostra_planos_para_quem_acompanha(margem, avaliador, client):
    de_fora = _com_papel("almoxarife", "estoque", ["est.ler.global"])
    client.force_login(de_fora)

    conteudo = client.get(reverse("workspace:servicos")).content.decode()

    assert "/workspace/planos/" not in conteudo


def test_o_painel_de_excecoes_aponta_para_os_planos(margem, avaliador, responde, client):
    """Regra com limiar cobra resposta, e a tela de planos é onde ela fica."""
    client.force_login(responde)

    conteudo = client.get(reverse("workspace:excecoes")).content.decode()

    assert "/workspace/planos/#dividas" in conteudo


# ── A semeadura ─────────────────────────────────────────────────────


def test_as_regras_do_benchmark_nascem_com_limiar(regras):
    """A dos 10% e a do detrator são as duas que o benchmark nomeia."""
    com_limiar = set(
        RegraExcecao.objects.filter(exige_plano=True).values_list("chave", flat=True)
    )

    assert "margem-abaixo-de-10" in com_limiar
    assert "detrator-sem-tratativa" in com_limiar
    assert all(
        RegraExcecao.objects.get(chave=c).prazo_do_plano > 0 for c in com_limiar
    ), "regra que exige plano declara o prazo em que ele será conferido"


def test_toda_regra_com_limiar_tem_avaliador(regras):
    """Limiar numa regra sem avaliador cobraria um plano que nunca poderia ser
    conferido — e o plano ficaria aberto para sempre."""
    sem_avaliador = [
        r.chave
        for r in RegraExcecao.objects.ativas().filter(exige_plano=True)
        if reg.regra_de(r.chave) is None
    ]

    assert sem_avaliador == []


def test_a_simulacao_do_comando_nao_escreve(margem, avaliador, responde):
    """Uma simulação que grava no banco não é simulação."""
    _plano(margem, responde, prazo_em=-10)

    call_command("verificar_planos", verbosity=0)

    assert VerificacaoPlano.objects.count() == 0
    assert PlanoAcao.objects.abertos().count() == 1


# ── As bordas ───────────────────────────────────────────────────────


def test_o_comando_enxerga_as_regras_sem_pessoa(regras):
    """Ele roda no cron, sem sessão. Recortar por permissão ali deixaria o
    comando conferindo só o que o último usuário logado podia ver."""
    todas = svc.regras_com_limiar()

    assert {r.chave for r in todas} >= {"margem-abaixo-de-10", "detrator-sem-tratativa"}


def test_quem_responde_pelo_papel_e_nao_pelo_escopo_global(margem, avaliador):
    """`pla.responder.departamento` + o papel da regra é o caminho normal. O
    escopo global é o atalho da diretoria, não a única porta."""
    do_papel = _com_papel(
        "analista_fin", "financeiro",
        ["exc.ler.global", "pla.responder.departamento"],
    )

    assert svc.pode_responder(margem, do_papel) is True


def test_plano_sem_responsavel_e_recusado(margem, avaliador, responde):
    with pytest.raises(svc.PlanoError):
        svc.abrir(margem, "contrato:CT-100", responde, justificativa="x",
                  acao="y", responsavel=None)


def test_fechar_plano_ja_fechado_nao_muda_nada(margem, avaliador, responde):
    """Fechar duas vezes não gera uma segunda conferência — e não reabre a
    discussão sobre um desfecho que já está registrado."""
    plano = _plano(margem, responde)
    avaliador.chaves = []
    svc.fechar(plano, responde)
    quantas = plano.verificacoes.count()

    svc.fechar(plano, responde, desfecho="mudei de ideia")

    plano.refresh_from_db()
    assert plano.situacao == SituacaoPlano.RESOLVIDO
    assert plano.verificacoes.count() == quantas


def test_fechar_plano_de_regra_que_sumiu_do_catalogo_recusa(
    margem, avaliador, responde
):
    plano = _plano(margem, responde)
    RegraExcecao.objects.filter(chave="margem-abaixo-de-10").delete()

    with pytest.raises(svc.PlanoError):
        svc.fechar(plano, responde)


def test_ocorrencia_de_devolve_none_com_a_fonte_fora_do_ar(margem, avaliador):
    """Não é "sumiu": é "não sei". As duas levam a não abrir plano, e é o
    desfecho certo — mas a tela diz coisas diferentes."""
    avaliador._disponivel = False

    assert svc.ocorrencia_de(margem, "contrato:CT-100") is None


def test_regra_fora_do_escopo_no_formulario_da_404(margem, avaliador, responde, client):
    client.force_login(responde)

    resposta = client.get(
        reverse("workspace:plano_novo"), {"regra": "nao-existe", "ocorrencia": "x"}
    )

    assert resposta.status_code == 404


def test_prazo_invalido_no_formulario_avisa_e_usa_o_padrao(
    margem, avaliador, responde, client
):
    """Perder o plano por causa do campo de data seria o pior desfecho: a
    justificativa e a ação são o que a pessoa acabou de escrever."""
    client.force_login(responde)

    resposta = client.post(
        reverse("workspace:plano_novo"),
        {
            "regra": "margem-abaixo-de-10",
            "ocorrencia": "contrato:CT-100",
            "justificativa": "Reajuste não repassado.",
            "acao": "Renegociar o índice.",
            "responsavel": responde.pk,
            "prazo": "31/02/2026",
        },
        follow=True,
    )

    plano = PlanoAcao.objects.get()
    assert plano.prazo == svc.prazo_de(margem)
    assert "Data de prazo inválida" in resposta.content.decode()


def test_o_formulario_volta_com_o_motivo_quando_o_servico_recusa(
    margem, avaliador, responde, client
):
    _plano(margem, responde)
    client.force_login(responde)

    resposta = client.post(
        reverse("workspace:plano_novo"),
        {
            "regra": "margem-abaixo-de-10",
            "ocorrencia": "contrato:CT-100",
            "justificativa": "de novo",
            "acao": "de novo",
            "responsavel": responde.pk,
        },
        follow=True,
    )

    assert "Já existe um plano aberto" in resposta.content.decode()
    assert PlanoAcao.objects.count() == 1


def test_fechar_pela_view_avisa_quando_a_regra_ainda_encontra(
    margem, avaliador, responde, client
):
    """A mensagem diz o que a REGRA respondeu, e não o que quem fechou escreveu.
    É onde a diferença entre esforço e resultado aparece para a pessoa."""
    plano = _plano(margem, responde)
    client.force_login(responde)

    resposta = client.post(
        reverse("workspace:fechar_plano", kwargs={"pk": plano.pk}),
        {"desfecho": "resolvido"},
        follow=True,
    )

    assert "NÃO resolvido" in resposta.content.decode()


def test_fechar_pela_view_confirma_quando_a_regra_para_de_encontrar(
    margem, avaliador, responde, client
):
    plano = _plano(margem, responde)
    avaliador.chaves = []
    client.force_login(responde)

    resposta = client.post(
        reverse("workspace:fechar_plano", kwargs={"pk": plano.pk}),
        {"desfecho": "índice renegociado"},
        follow=True,
    )

    assert "não encontra mais a ocorrência" in resposta.content.decode()


def test_fechar_pela_view_com_a_fonte_fora_do_ar_mostra_o_motivo(
    margem, avaliador, responde, client
):
    plano = _plano(margem, responde)
    avaliador._disponivel = False
    client.force_login(responde)

    resposta = client.post(
        reverse("workspace:fechar_plano", kwargs={"pk": plano.pk}), follow=True
    )

    assert "continua aberto" in resposta.content.decode()
    plano.refresh_from_db()
    assert plano.situacao == SituacaoPlano.ABERTO


def test_a_tela_do_plano_lista_as_conferencias(margem, avaliador, responde, client):
    plano = _plano(margem, responde)
    svc.verificar(plano)
    client.force_login(responde)

    conteudo = client.get(
        reverse("workspace:plano", kwargs={"pk": plano.pk})
    ).content.decode()

    assert "Conferências" in conteudo
    assert "ainda encontra esta ocorrência" in conteudo


def test_abrir_e_fechar_sem_o_papel_levantam_no_servico(margem, avaliador, responde, so_le):
    """A view confere antes, e o serviço confere de novo. Duas trancas na mesma
    porta porque a segunda é a que vale quando alguém escrever a terceira view."""
    plano = _plano(margem, responde)

    with pytest.raises(svc.PlanoError):
        svc.abrir(margem, "contrato:CT-200", so_le, justificativa="x", acao="y",
                  responsavel=so_le)
    with pytest.raises(svc.PlanoError):
        svc.fechar(plano, so_le)


def test_fechar_plano_de_regra_alheia_pela_view_e_403(margem, avaliador, responde, client):
    plano = _plano(margem, responde)
    de_fora = _com_papel("almoxarife", "estoque", ["est.ler.global"])
    client.force_login(de_fora)

    resposta = client.post(
        reverse("workspace:fechar_plano", kwargs={"pk": plano.pk})
    )

    assert resposta.status_code == 403
    plano.refresh_from_db()
    assert plano.situacao == SituacaoPlano.ABERTO
