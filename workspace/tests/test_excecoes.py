"""O painel de exceções — a lista de regras que nasce endereçada.

Os três que mais protegem esta onda:

1. **Regra com zero NÃO some.** Sumir esconde que a regra existe, e a discussão
   sobre "deveríamos vigiar X" volta em seis meses.
2. **"Não avaliada" NÃO é zero.** Zero é tranquilidade; não avaliada é uma fonte
   para ligar, e somá-las faria uma fonte caída parecer um mês sem problema.
3. **A grade nunca traz documento nem e-mail.** Quem abre a tela tem o papel da
   regra, e não o direito de ver dado pessoal de terceiro.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace import excecoes as reg
from workspace.models.excecao import RegraExcecao, ResultadoExcecao
from workspace.services import excecoes as svc

pytestmark = pytest.mark.django_db


@pytest.fixture
def regras(db):
    call_command("semear_regras_excecao", "--aplicar", verbosity=0)
    return {r.chave: r for r in RegraExcecao.objects.all()}


def _com_papel(apelido, chave_do_papel, permissoes=()):
    pessoa = f.pessoa(apelido, nome=apelido.title())
    f.lotar(pessoa, centro_custo_codigo="1042")
    f.atribuir(
        pessoa,
        f.papel(chave_do_papel, list(permissoes), escopo="global"),
        escopo="global",
    )
    return pessoa


# ── As regras existem e ficam ───────────────────────────────────────


def test_a_semeadora_registra_as_ligadas_e_as_desligadas(regras):
    """As desligadas respondem "por que não vigiamos ASO?" sem ninguém
    perguntar — e impedem a mesma discussão de voltar em seis meses."""
    ligadas = RegraExcecao.objects.filter(ativa=True).count()
    desligadas = RegraExcecao.objects.filter(ativa=False)

    assert ligadas == 18
    assert desligadas.count() == 5
    assert all(r.fonte_requerida for r in desligadas), "cada uma diz do que depende"


def test_a_semeadora_nao_reativa_regra_desligada_a_mao(regras):
    """Desligar uma regra é decisão de quem opera, quase sempre porque ela está
    gerando ruído. A semeadora roda no deploy seguinte — que é exatamente quando
    desfazer isso seria pior."""
    RegraExcecao.objects.filter(chave="reserva-sem-uso").update(ativa=False)

    call_command("semear_regras_excecao", "--aplicar", verbosity=0)

    assert RegraExcecao.objects.get(chave="reserva-sem-uso").ativa is False


def test_todo_avaliador_registrado_tem_regra_no_banco(regras):
    """Avaliador sem regra é código que nunca roda.

    Ele passaria em toda revisão — não quebra nada, não aparece em lugar
    nenhum, e some da cabeça de todo mundo em duas semanas.
    """
    do_banco = set(RegraExcecao.objects.values_list("chave", flat=True))
    do_codigo = set(reg.todas())

    assert do_codigo - do_banco == set(), f"avaliador órfão: {do_codigo - do_banco}"


def test_regra_ligada_sem_avaliador_aparece_como_nao_avaliada(regras):
    """E não como zero.

    Uma regra ligada no `/admin/` e sem código atrás dela é erro de operação —
    e a tela precisa dizer isso em vez de mostrar "sem ocorrências", que seria
    uma afirmação sobre uma verificação que não aconteceu.
    """
    RegraExcecao.objects.filter(chave="aso-vencido").update(ativa=True)

    avaliacao = svc.avaliar(RegraExcecao.objects.get(chave="aso-vencido"))

    assert avaliacao.avaliada is False
    assert "sem avaliador" in avaliacao.motivo
    assert "hris" in avaliacao.motivo


# ── Zero, não-avaliada e ocorrência ─────────────────────────────────


def test_regra_com_zero_continua_na_lista(client, regras):
    """O teste que mais protege esta onda.

    Sumir esconderia que a regra existe — e o efeito prático é alguém reabrir a
    discussão sobre "deveríamos vigiar X" seis meses depois de já estarmos
    vigiando.
    """
    rh = _com_papel("rh", "rh")
    client.force_login(rh)

    resposta = client.get(reverse("workspace:excecoes"))
    chaves = [a.regra.chave for a in resposta.context["avaliacoes"]]

    assert "lotacao-sem-cc" in chaves
    assert b"sem ocorr" in resposta.content


def test_nao_avaliada_nao_e_zero(client, regras, monkeypatch):
    """Somá-las faria uma fonte caída parecer um mês sem problema."""
    from workspace.providers import resultados as contrato

    monkeypatch.setattr(contrato, "obter", lambda tipo: None)
    financeiro = _com_papel("financeiro", "financeiro")
    client.force_login(financeiro)

    resposta = client.get(reverse("workspace:excecoes"))
    margem = next(
        a for a in resposta.context["avaliacoes"] if a.regra.chave == "margem-abaixo-de-10"
    )

    assert margem.situacao == "nao_avaliada"
    assert margem.total == 0
    assert margem not in [a for a in resposta.context["avaliacoes"] if a.situacao == "sem_ocorrencias"]
    assert "não está disponível" in margem.motivo
    assert b"n\xc3\xa3o avaliada" in resposta.content


def test_o_total_da_tela_nao_conta_as_nao_avaliadas(regras, monkeypatch):
    """Um painel que somasse zero por uma fonte fora do ar diria que está tudo
    em ordem justamente quando não se sabe."""
    from workspace.providers import resultados as contrato

    monkeypatch.setattr(contrato, "obter", lambda tipo: None)
    panorama = svc.painel(_com_papel("dir", "diretoria", ["exc.ler.global"]))

    assert panorama["nao_avaliadas"]
    assert panorama["total_de_ocorrencias"] == sum(
        a.total for a in panorama["avaliacoes"] if a.avaliada
    )


def test_regra_que_estoura_nao_derruba_as_outras(regras, monkeypatch):
    """O painel existe justamente para ser aberto quando algo está errado.

    Uma regra que estoura viraria uma tela 500 — e a pessoa perderia as
    dezessete que funcionavam.
    """
    class Explode(reg.RegraBase):
        chave = "lotacao-sem-cc"

        def avaliar(self, janela):
            raise RuntimeError("boom")

    reg.registrar(Explode(), substituir=True)
    try:
        avaliacao = svc.avaliar(RegraExcecao.objects.get(chave="lotacao-sem-cc"))
    finally:
        reg.limpar()
        reg.semear()

    assert avaliacao.avaliada is False
    assert "RuntimeError" in avaliacao.motivo


# ── Quem vê o quê ───────────────────────────────────────────────────


def test_quem_nao_responde_por_regra_nenhuma_recebe_403(client, regras):
    """403, e não uma lista vazia.

    Lista vazia para quem nunca vai ter regra é a mesma mentira de um painel de
    zeros: faz a pessoa achar que está tudo em ordem quando ela não está
    olhando nada.
    """
    ana = f.pessoa("ana")
    f.lotar(ana)
    client.force_login(ana)

    assert client.get(reverse("workspace:excecoes")).status_code == 403


def test_anonimo_nao_entra(client, regras):
    resposta = client.get(reverse("workspace:excecoes"))

    assert resposta.status_code in (302, 403)


def test_cada_papel_ve_as_SUAS_regras(client, regras):
    """O R.H. não vê as regras do Financeiro, e vice-versa.

    O painel inteiro é da diretoria; cada área vê o que ela pode resolver.
    """
    client.force_login(_com_papel("rh", "rh"))
    do_rh = {
        a.regra.chave for a in client.get(reverse("workspace:excecoes")).context["avaliacoes"]
    }

    assert "lotacao-sem-cc" in do_rh
    assert "cc-sem-orcamento" not in do_rh, "isso é do Financeiro"


def test_as_regras_sem_papel_aparecem_para_quem_ja_esta_no_painel(client, regras):
    """Fonte atrasada e divergência não são de departamento nenhum.

    Elas vigiam o mecanismo, e por isso `escopo_papel` fica vazio.
    """
    client.force_login(_com_papel("rh", "rh"))

    chaves = {
        a.regra.chave for a in client.get(reverse("workspace:excecoes")).context["avaliacoes"]
    }

    assert "fonte-atrasada" in chaves
    assert "solicitacao-parada" in chaves


def test_so_as_regras_sem_papel_nao_bastam_para_abrir_o_painel(client, regras):
    """Mostrá-las sozinhas transformaria o painel numa tela de infraestrutura
    para quem não opera infraestrutura."""
    solto = _com_papel("marketing", "marketing")
    client.force_login(solto)

    assert client.get(reverse("workspace:excecoes")).status_code == 403


def test_a_diretoria_ve_o_painel_inteiro(client, regras):
    client.force_login(_com_papel("dir", "diretoria", ["exc.ler.global"]))

    chaves = {
        a.regra.chave for a in client.get(reverse("workspace:excecoes")).context["avaliacoes"]
    }

    assert chaves == set(RegraExcecao.objects.filter(ativa=True).values_list("chave", flat=True))


# ── A grade ─────────────────────────────────────────────────────────


def test_a_ocorrencia_nasce_endereçada(client, regras):
    """O responsável em cada linha — é o que o benchmark faz ao pôr o e-mail do
    gestor na grade. Sem isso a lista vira um relatório que alguém distribui à
    mão."""
    _com_papel("rh", "rh")
    orfa = f.pessoa("orfa", nome="Pessoa Sem CC")
    f.lotar(orfa, centro_custo_codigo="")
    client.force_login(f.pessoa("chefe", nome="Chefe") if False else _com_papel("dir", "diretoria", ["exc.ler.global"]))

    avaliacoes = client.get(reverse("workspace:excecoes")).context["avaliacoes"]
    lotacao = next(a for a in avaliacoes if a.regra.chave == "lotacao-sem-cc")

    assert lotacao.total >= 1
    assert all(o.responsavel for o in lotacao.ocorrencias)
    assert all(o.papel == "rh" for o in lotacao.ocorrencias)


def test_papel_sem_dono_aparece_como_ninguem_e_nao_em_branco(regras):
    """Exceção sem dono é exceção que ninguém resolve.

    Coluna vazia pareceria defeito de renderização — e o achado real, que é o
    papel sem ocupante, passaria despercebido.
    """
    assert reg.quem_responde("papel-que-nao-existe") == "ninguém"


def test_a_grade_nao_traz_documento_nem_e_mail(client, regras):
    """Quem abre a tela tem o PAPEL da regra, e não o direito de ver dado
    pessoal de terceiro. Grade com CPF é o que a leitura do benchmark marcou
    como não copiar."""
    orfa = f.pessoa("orfa", nome="Pessoa Sem CC")
    f.lotar(orfa, centro_custo_codigo="")
    client.force_login(_com_papel("dir", "diretoria", ["exc.ler.global"]))

    conteudo = client.get(reverse("workspace:excecoes")).content.decode()

    assert "Pessoa Sem CC" in conteudo, "o nome aparece — é como se sabe de quem se fala"
    assert "@icodev.com.br" not in conteudo, "o e-mail, não"


# ── Tendência ───────────────────────────────────────────────────────


def test_sem_historico_a_tela_nao_inventa_uma_seta(client, regras):
    """`None` e não zero: uma seta inventada é pior que seta nenhuma."""
    client.force_login(_com_papel("rh", "rh"))

    avaliacoes = client.get(reverse("workspace:excecoes")).context["avaliacoes"]

    assert all(a.variacao is None for a in avaliacoes)


def test_a_tendencia_sai_do_ultimo_retrato(regras):
    """Uma regra que foi de 3 para 40 importa mais que uma que está em 40 há um
    ano — e a contagem sozinha não conta isso."""
    regra = RegraExcecao.objects.get(chave="lotacao-sem-cc")
    ResultadoExcecao.objects.create(regra=regra, total=3, avaliada=True)
    f.lotar(f.pessoa("orfa", nome="Pessoa Sem CC"), centro_custo_codigo="")

    avaliacao = svc.avaliar(regra)

    assert avaliacao.anterior == 3
    assert avaliacao.variacao == avaliacao.total - 3


def test_o_retrato_guarda_a_chave_do_registro_e_nunca_da_pessoa(regras):
    """O histórico é consultado por quem não abriu a tela e não passou por
    permissão nenhuma."""
    f.lotar(f.pessoa("orfa", nome="Pessoa Sem CC"), centro_custo_codigo="")
    avaliacao = svc.avaliar(RegraExcecao.objects.get(chave="lotacao-sem-cc"))

    resultado = svc.registrar_resultado(avaliacao)

    assert resultado.total == avaliacao.total
    assert all(c.startswith("lotacao:") for c in resultado.chaves)
    assert not any("@" in c for c in resultado.chaves)


# ── As duas ações ───────────────────────────────────────────────────


def test_avisar_manda_um_aviso_por_PESSOA_e_nao_por_ocorrencia(client, regras):
    """Quarenta avisos sobre a mesma regra transformam o sino num lugar que se
    aprende a ignorar — e o aviso que importa some junto."""
    from workspace.models.notificacao import Notificacao

    rh = _com_papel("rh", "rh")
    for i in range(5):
        f.lotar(f.pessoa(f"orfa{i}", nome=f"Pessoa {i}"), centro_custo_codigo="")
    client.force_login(rh)

    resposta = client.post(
        reverse("workspace:notificar_excecao", args=("lotacao-sem-cc",)), follow=True
    )

    avisos = Notificacao.objects.filter(destinatario=rh)
    assert avisos.count() == 1, "um aviso, e não cinco"
    assert "5" in avisos.first().titulo
    assert any("1 pessoa" in str(m) for m in resposta.context["messages"])


def test_avisar_e_POST_e_nunca_GET(client, regras):
    """Um `GET` faria um prefetch do navegador mandar notificação — e a segunda
    vez que isso acontecesse, ninguém mais leria as notificações do produto."""
    client.force_login(_com_papel("rh", "rh"))

    resposta = client.get(reverse("workspace:notificar_excecao", args=("lotacao-sem-cc",)))

    assert resposta.status_code == 405


def test_nao_se_avisa_por_regra_que_nao_se_ve(client, regras):
    """Sem esta checagem, o painel viraria um jeito de mandar notificação para
    departamentos alheios."""
    client.force_login(_com_papel("rh", "rh"))

    resposta = client.post(
        reverse("workspace:notificar_excecao", args=("cc-sem-orcamento",))
    )

    assert resposta.status_code == 403


def test_avisar_regra_desligada_da_404(client, regras):
    client.force_login(_com_papel("dir", "diretoria", ["exc.ler.global"]))

    resposta = client.post(reverse("workspace:notificar_excecao", args=("aso-vencido",)))

    assert resposta.status_code == 404


def test_papel_sem_dono_avisa_ninguem_e_diz_isso(client, regras):
    """Zero é resposta legítima — e é a regra 2 aparecendo por outro caminho."""
    dir_ = _com_papel("dir", "diretoria", ["exc.ler.global"])
    f.lotar(f.pessoa("orfa", nome="Pessoa Sem CC"), centro_custo_codigo="")
    client.force_login(dir_)

    resposta = client.post(
        reverse("workspace:notificar_excecao", args=("lotacao-sem-cc",)), follow=True
    )

    assert any("Ninguém ocupa o papel" in str(m) for m in resposta.context["messages"])


def test_abrir_solicitacao_leva_a_origem_e_nao_o_conteudo(client, regras):
    """Pré-preenche a ORIGEM, nunca o conteúdo.

    Pedido com dado adivinhado é pior que pedido vazio: o formulário mostra o
    que vai ser enviado, e o palpite não. É a mesma decisão do §57 sobre a
    busca.
    """
    f.lotar(f.pessoa("orfa", nome="Pessoa Sem CC"), centro_custo_codigo="")
    client.force_login(_com_papel("dir", "diretoria", ["exc.ler.global"]))

    conteudo = client.get(reverse("workspace:excecoes")).content.decode()

    assert "origem=excecao:lotacao-sem-cc" in conteudo


def test_a_origem_atravessa_o_envio_e_vira_historico(client, regras):
    """"Por que este pedido existe?" é pergunta sobre o passado — e passado é o
    que o histórico guarda."""
    from decimal import Decimal

    from workspace.models import GrupoCatalogo, ItemCatalogo
    from workspace.models.evento import EventoSolicitacao

    item = ItemCatalogo.objects.create(
        chave="ferias", nome="Férias", grupo=GrupoCatalogo.TRABALHO,
        dominio="rh.ferias", prazo_prometido_dias=5,
        limite_auto_aprovacao=Decimal("0"),
        campos=[{"chave": "quando", "rotulo": "Quando", "obrigatorio": True}],
    )
    ana = f.pessoa("ana", nome="Ana Souza")
    f.lotar(ana, centro_custo_codigo="1042")
    client.force_login(ana)

    client.post(
        reverse("workspace:pedir", args=(item.chave,)),
        {"quando": "março", "origem": "excecao:lotacao-sem-cc"},
    )

    evento = EventoSolicitacao.objects.order_by("quando").first()
    assert evento is not None
    assert evento.observacao == "excecao:lotacao-sem-cc"


# ── O comando ───────────────────────────────────────────────────────


def test_o_comando_simula_por_padrao(regras):
    from io import StringIO

    saida = StringIO()
    call_command("avaliar_excecoes", stdout=saida, stderr=saida)

    assert "SIMULAÇÃO" in saida.getvalue()
    assert not ResultadoExcecao.objects.exists()


def test_o_comando_grava_o_retrato_inclusive_da_nao_avaliada(regras, monkeypatch):
    """Sem ele, o histórico teria um buraco onde deveria estar "neste dia a
    fonte estava fora do ar" — e a tendência da próxima avaliação compararia com
    um número de três dias atrás como se fosse de ontem."""
    from io import StringIO

    from workspace.providers import resultados as contrato

    monkeypatch.setattr(contrato, "obter", lambda tipo: None)
    call_command("avaliar_excecoes", "--aplicar", stdout=StringIO(), stderr=StringIO())

    margem = ResultadoExcecao.objects.get(regra__chave="margem-abaixo-de-10")
    assert margem.avaliada is False
    assert margem.total == 0


def test_o_comando_avisa_so_com_avisar(regras):
    from io import StringIO

    from workspace.models.notificacao import Notificacao

    _com_papel("rh", "rh")
    f.lotar(f.pessoa("orfa", nome="Pessoa Sem CC"), centro_custo_codigo="")

    call_command("avaliar_excecoes", "--aplicar", stdout=StringIO(), stderr=StringIO())
    assert not Notificacao.objects.exists()

    call_command(
        "avaliar_excecoes", "--aplicar", "--avisar", stdout=StringIO(), stderr=StringIO()
    )
    assert Notificacao.objects.exists()


def test_o_comando_aceita_uma_regra_so(regras):
    from io import StringIO

    saida = StringIO()
    call_command("avaliar_excecoes", "--aplicar", "--regra", "lotacao-sem-cc",
                 stdout=saida, stderr=saida)

    assert ResultadoExcecao.objects.count() == 1


def test_o_comando_recusa_regra_desconhecida(regras):
    from io import StringIO

    saida = StringIO()
    call_command("avaliar_excecoes", "--regra", "nao-existe", stdout=saida, stderr=saida)

    assert "não existe" in saida.getvalue()


def test_a_semeadora_atualiza_o_texto_e_relata(regras):
    """Descrição e severidade mudam. A semeadora atualiza e DIZ que atualizou,
    para quem opera saber que o deploy mexeu ali."""
    from io import StringIO

    RegraExcecao.objects.filter(chave="reserva-sem-uso").update(
        descricao_curta="texto antigo", ordem=999
    )

    saida = StringIO()
    call_command("semear_regras_excecao", "--aplicar", stdout=saida, stderr=saida)

    assert "~ reserva-sem-uso" in saida.getvalue()
    regra = RegraExcecao.objects.get(chave="reserva-sem-uso")
    assert regra.descricao_curta != "texto antigo"
    assert regra.ordem == 100
