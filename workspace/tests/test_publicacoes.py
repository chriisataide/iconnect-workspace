"""§9 — publicar comunicado e notícia de dentro do portal.

## O que estava errado

O modelo `Publicacao` existia desde a primeira onda, e a única porta para ele
era o **Django admin** — que exige `is_staff`. Quem escreve comunicado da
empresa é o R.H. e a diretoria, e nenhum dos dois tem `is_staff`, nem deveria: o
admin edita a base sem passar pelas regras nem pelo histórico do produto.

Na prática, publicar significava pedir para outra pessoa. O efeito disso num
portal é conhecido — a comunicação volta para o e-mail, e o mural fica com três
avisos de dois anos atrás.

## O público-alvo, e a armadilha dele

Vazio significa **todo mundo**, não "ninguém". O contrário faria toda publicação
já existente sumir no dia em que o campo nasceu, e o comunicado que a empresa
inteira precisava ler seria o primeiro a desaparecer.

## Arquivar não é despublicar

Despublicar é "tirar do ar por enquanto"; arquivar é "isto acabou". Com um campo
só, a lista de rascunhos encheria de comunicado velho que ninguém tem coragem de
apagar, e o rascunho de verdade se perderia no meio.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.models.comunicacao import Publicacao, TipoPublicacao
from workspace.services import publicacao as pub
from workspace.services.publicacao import PublicacaoError

pytestmark = pytest.mark.django_db


@pytest.fixture
def cenario():
    unidade = f.unidade()
    financeiro = f.departamento(codigo="FIN", nome="Financeiro")
    editor, ana = f.pessoa("editor"), f.pessoa("ana")
    f.lotar(editor, uni=unidade)
    f.lotar(ana, uni=unidade, dep=financeiro)
    f.atribuir(editor, f.papel("com", ["com.publicar.global"], escopo="global"))
    return {
        "editor": editor, "ana": ana, "unidade": unidade, "financeiro": financeiro,
    }


def escrever(cenario, **extras):
    dados = {
        "titulo": "Mudança na política de despesas",
        "tipo": TipoPublicacao.COMUNICADO,
        "publicar": True,
    }
    dados.update(extras)
    return pub.salvar(cenario["editor"], **dados)


# ── Quem pode ───────────────────────────────────────────────────────


def test_quem_nao_publica_nao_entra(client, cenario):
    """403 e não tela vazia, pela mesma razão do painel de indicadores: uma
    redação vazia para quem nunca vai publicar faz a pessoa achar que a empresa
    parou de comunicar."""
    client.force_login(cenario["ana"])

    assert client.get(reverse("workspace:publicacoes")).status_code == 403


def test_quem_publica_entra(client, cenario):
    client.force_login(cenario["editor"])

    assert client.get(reverse("workspace:publicacoes")).status_code == 200


def test_a_tela_exige_sessao(client):
    resposta = client.get(reverse("workspace:publicacoes"))

    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/entrar/")


def test_salvar_sem_permissao_e_recusado(cenario):
    with pytest.raises(PublicacaoError, match="não pode publicar"):
        pub.salvar(cenario["ana"], titulo="x", tipo=TipoPublicacao.COMUNICADO)


# ── Rascunho, publicado, arquivado ──────────────────────────────────


def test_rascunho_nao_vai_ao_ar(cenario):
    rascunho = escrever(cenario, publicar=False)

    assert rascunho.situacao == "rascunho"
    assert not rascunho.no_ar
    assert rascunho not in Publicacao.objects.publicadas()


def test_publicado_vai_ao_ar(cenario):
    publicada = escrever(cenario)

    assert publicada.situacao == "no_ar"
    assert publicada in Publicacao.objects.publicadas()


def test_agendado_espera_a_data(cenario):
    """E continua visível para quem escreveu — sem isso, o comunicado agendado
    some da tela do autor e ele reescreve."""
    daqui = timezone.now() + timedelta(days=3)
    agendada = escrever(cenario, publicar_em=daqui)

    assert agendada.situacao == "agendado"
    assert agendada not in Publicacao.objects.publicadas()
    assert agendada in pub.redacao(cenario["editor"])


def test_publicar_agora_puxa_a_data_agendada(cenario):
    """Quem clica "publicar" quer que apareça AGORA. Manter a data futura faria
    o botão não fazer nada visível, e a pessoa clicaria de novo."""
    agendada = escrever(cenario, publicar=False, publicar_em=timezone.now() + timedelta(days=3))

    pub.publicar(agendada, cenario["editor"])

    assert agendada.situacao == "no_ar"


def test_despublicar_devolve_para_rascunho(cenario):
    publicada = escrever(cenario)

    pub.despublicar(publicada, cenario["editor"])

    assert publicada.situacao == "rascunho"
    assert publicada in pub.redacao(cenario["editor"])


def test_arquivar_tira_da_redacao(cenario):
    """Sem os dois estados, a lista de rascunhos enche de comunicado velho e o
    rascunho de verdade se perde no meio."""
    publicada = escrever(cenario)

    pub.arquivar(publicada, cenario["editor"])

    assert publicada.situacao == "arquivado"
    assert publicada not in pub.redacao(cenario["editor"])
    assert publicada in pub.arquivadas(cenario["editor"])
    assert publicada not in Publicacao.objects.publicadas()


def test_expirado_sai_do_ar_sozinho(cenario):
    passada = escrever(
        cenario,
        publicar_em=timezone.now() - timedelta(days=10),
        expira_em=timezone.now() - timedelta(days=1),
    )

    assert passada.situacao == "expirado"
    assert passada not in Publicacao.objects.publicadas()


def test_excluir_so_vale_para_rascunho(cenario):
    """O que já foi ao ar não se apaga: alguém leu, alguém agiu, e "o que a
    empresa comunicou em março" precisa de resposta."""
    publicada = escrever(cenario)

    with pytest.raises(PublicacaoError, match="não se apaga"):
        pub.excluir(publicada, cenario["editor"])


def test_excluir_rascunho_funciona(cenario):
    rascunho = escrever(cenario, publicar=False)

    pub.excluir(rascunho, cenario["editor"])

    assert not Publicacao.objects.exists()


# ── Público-alvo ────────────────────────────────────────────────────


def test_sem_alvo_alcanca_todo_mundo(cenario):
    """Vazio = todos, e não "ninguém". O contrário faria toda publicação já
    existente sumir no dia em que o campo nasceu."""
    geral = escrever(cenario)

    assert geral in Publicacao.objects.para(cenario["ana"])


def test_alvo_por_departamento_alcanca_so_ele(cenario):
    do_financeiro = escrever(cenario, departamentos=[cenario["financeiro"].pk])

    assert do_financeiro in Publicacao.objects.para(cenario["ana"])
    assert do_financeiro not in Publicacao.objects.para(cenario["editor"])


def test_alvo_por_unidade_alcanca_so_ela(cenario):
    outra = f.unidade(codigo="RJ", nome="Filial RJ")
    de_outra = escrever(cenario, unidades=[outra.pk])

    assert de_outra not in Publicacao.objects.para(cenario["ana"])


def test_os_dois_alvos_se_combinam_por_e(cenario):
    """Marcar Salvador + Financeiro alcança o Financeiro DE Salvador, que é o
    que quem publica espera ao marcar as duas."""
    outra = f.unidade(codigo="RJ", nome="Filial RJ")
    certa = escrever(
        cenario,
        unidades=[cenario["unidade"].pk],
        departamentos=[cenario["financeiro"].pk],
    )
    errada = escrever(
        cenario, titulo="Outra", unidades=[outra.pk],
        departamentos=[cenario["financeiro"].pk],
    )

    alcanca = Publicacao.objects.para(cenario["ana"])
    assert certa in alcanca
    assert errada not in alcanca


def test_quem_nao_tem_lotacao_recebe_so_o_geral(cenario):
    """Comunicado endereçado ao Financeiro não deve alcançar quem o R.H. ainda
    não lotou em lugar nenhum."""
    novato = f.pessoa("novato")
    geral = escrever(cenario)
    dirigida = escrever(cenario, titulo="Só o Financeiro",
                        departamentos=[cenario["financeiro"].pk])

    alcanca = Publicacao.objects.para(novato)
    assert geral in alcanca
    assert dirigida not in alcanca


def test_publicacao_com_varios_alvos_aparece_uma_vez_so(cenario):
    """O M2M multiplica linhas: sem `distinct`, publicação com três
    departamentos-alvo apareceria três vezes na lista."""
    outro = f.departamento(codigo="OPS", nome="Operações")
    escrever(cenario, departamentos=[cenario["financeiro"].pk, outro.pk])

    assert Publicacao.objects.para(cenario["ana"]).count() == 1


def test_editar_tirando_alvo_realmente_tira(cenario):
    """Com `add` em vez de `set`, o alvo só cresceria — e a publicação restrita
    ao Financeiro continuaria alcançando quem foi marcado por engano."""
    p = escrever(cenario, departamentos=[cenario["financeiro"].pk])

    pub.salvar(
        cenario["editor"], p, titulo=p.titulo, tipo=p.tipo, publicar=True,
        departamentos=[],
    )

    assert p.departamentos.count() == 0
    assert p in Publicacao.objects.para(cenario["editor"])


# ── Validação ───────────────────────────────────────────────────────


def test_titulo_vazio_e_recusado(cenario):
    with pytest.raises(PublicacaoError, match="título"):
        escrever(cenario, titulo="   ")


def test_tipo_invalido_e_recusado(cenario):
    with pytest.raises(PublicacaoError, match="Tipo"):
        escrever(cenario, tipo="fofoca")


def test_expiracao_antes_da_publicacao_e_recusada(cenario):
    """Publicação que expira antes de sair nunca aparece para ninguém, e quem
    escreveu só descobre quando pergunta por que ninguém leu."""
    agora = timezone.now()

    with pytest.raises(PublicacaoError, match="depois da publicação"):
        escrever(cenario, publicar_em=agora + timedelta(days=2), expira_em=agora)


def test_editar_nao_rouba_a_autoria(cenario):
    """Quem corrigiu uma vírgula não passa a assinar o comunicado de outra
    pessoa."""
    outro = f.pessoa("outro")
    f.lotar(outro)
    f.atribuir(outro, f.papel("com2", ["com.publicar.global"], escopo="global"))
    p = escrever(cenario)

    pub.salvar(outro, p, titulo="Corrigido", tipo=p.tipo, publicar=True)

    assert p.autor == cenario["editor"]


# ── Pela tela ───────────────────────────────────────────────────────


def test_escrever_pela_tela_grava_rascunho(client, cenario):
    """O estado sai de QUAL botão foi clicado, e não de uma caixinha que a
    pessoa esquece de marcar — e aí escreve o comunicado inteiro e ele não vai
    ao ar."""
    client.force_login(cenario["editor"])

    client.post(
        reverse("workspace:publicacao_nova"),
        {"titulo": "Aviso de obra", "tipo": TipoPublicacao.COMUNICADO, "acao": "rascunho"},
    )

    assert Publicacao.objects.get().situacao == "rascunho"


def test_escrever_pela_tela_publicando(client, cenario):
    client.force_login(cenario["editor"])

    client.post(
        reverse("workspace:publicacao_nova"),
        {"titulo": "Aviso de obra", "tipo": TipoPublicacao.COMUNICADO, "acao": "publicar"},
    )

    assert Publicacao.objects.get().situacao == "no_ar"


def test_data_invalida_nao_perde_o_texto(client, cenario):
    """O texto do comunicado é o que custa caro para reescrever. Perdê-lo porque
    alguém digitou a data errada seria trocar um campo por uma tela inteira."""
    client.force_login(cenario["editor"])

    client.post(
        reverse("workspace:publicacao_nova"),
        {
            "titulo": "Aviso de obra", "corpo": "Texto longo",
            "tipo": TipoPublicacao.COMUNICADO, "acao": "publicar",
            "expira_em": "amanhã de manhã",
        },
    )

    assert Publicacao.objects.get().corpo == "Texto longo"


def test_a_lista_mostra_o_que_nao_esta_no_ar(client, cenario):
    escrever(cenario, titulo="Rascunho meu", publicar=False)
    client.force_login(cenario["editor"])

    corpo = client.get(reverse("workspace:publicacoes")).content.decode()

    assert "Rascunho meu" in corpo
    assert "Rascunho" in corpo


def test_a_lista_diz_todo_mundo_quando_nao_ha_alvo(client, cenario):
    """Célula vazia se lê como "ninguém definiu", que é a leitura oposta."""
    escrever(cenario)
    client.force_login(cenario["editor"])

    assert "todo mundo" in client.get(reverse("workspace:publicacoes")).content.decode()


def test_acao_pela_tela(client, cenario):
    p = escrever(cenario)
    client.force_login(cenario["editor"])

    client.post(reverse("workspace:publicacao_acao", args=[p.pk]), {"acao": "arquivar"})

    p.refresh_from_db()
    assert p.arquivado


def test_acao_desconhecida_nao_faz_nada(client, cenario):
    p = escrever(cenario)
    client.force_login(cenario["editor"])

    client.post(reverse("workspace:publicacao_acao", args=[p.pk]), {"acao": "explodir"})

    p.refresh_from_db()
    assert p.situacao == "no_ar"


def test_o_trilho_mostra_a_redacao_para_quem_publica(client, cenario):
    client.force_login(cenario["editor"])

    corpo = client.get(reverse("workspace:servicos")).content.decode()

    assert reverse("workspace:publicacoes") in corpo


def test_o_trilho_esconde_a_redacao_de_quem_nao_publica(client, cenario):
    client.force_login(cenario["ana"])

    corpo = client.get(reverse("workspace:servicos")).content.decode()

    assert reverse("workspace:publicacoes") not in corpo


def test_a_home_respeita_o_publico_alvo(client, cenario):
    """O público-alvo só vale se a home o respeitar — antes disto ela lia
    `publicadas()`, que ignora o alvo."""
    escrever(cenario, titulo="Só o Financeiro",
             departamentos=[cenario["financeiro"].pk])
    client.force_login(cenario["editor"])

    corpo = client.get(reverse("workspace:home")).content.decode()

    assert "Só o Financeiro" not in corpo


def test_o_anonimo_ve_so_o_comunicado_geral(client, cenario):
    """`request.user` e não a pessoa de referência do hub aberto: usá-la aqui
    mostraria ao visitante o comunicado dirigido ao departamento dela."""
    escrever(cenario, titulo="Para todos")
    escrever(cenario, titulo="Só o Financeiro",
             departamentos=[cenario["financeiro"].pk])

    corpo = client.get(reverse("workspace:home")).content.decode()

    assert "Para todos" in corpo
    assert "Só o Financeiro" not in corpo


# ── Os caminhos de erro da tela ─────────────────────────────────────


def test_a_tela_mostra_o_motivo_da_recusa_e_nao_grava(client, cenario):
    """Erro de validação volta para o formulário com a mensagem, e não para a
    lista: mandar a pessoa de volta ao índice apaga o que ela escreveu."""
    client.force_login(cenario["editor"])

    resposta = client.post(
        reverse("workspace:publicacao_nova"),
        {"titulo": "   ", "tipo": TipoPublicacao.COMUNICADO, "acao": "publicar"},
    )

    assert resposta.status_code == 200
    assert "título é obrigatório" in resposta.content.decode()
    assert not Publicacao.objects.exists()


def test_editar_carrega_o_que_ja_esta_gravado(client, cenario):
    p = escrever(cenario, corpo="Texto original",
                 departamentos=[cenario["financeiro"].pk])
    client.force_login(cenario["editor"])

    corpo = client.get(
        reverse("workspace:publicacao_editar", args=[p.pk])
    ).content.decode()

    assert "Texto original" in corpo
    assert 'value="{}" selected'.format(cenario["financeiro"].pk) in corpo


def test_editar_pela_tela_altera_e_nao_duplica(client, cenario):
    p = escrever(cenario, publicar=False)
    client.force_login(cenario["editor"])

    client.post(
        reverse("workspace:publicacao_editar", args=[p.pk]),
        {"titulo": "Título novo", "tipo": p.tipo, "acao": "rascunho"},
    )

    assert Publicacao.objects.count() == 1
    p.refresh_from_db()
    assert p.titulo == "Título novo"


def test_a_data_com_hora_e_aceita(client, cenario):
    """`datetime-local` manda `2026-09-01T08:30`. Sem `make_aware` o Django
    avisa de naive datetime e a comparação de vigência erra por um fuso."""
    client.force_login(cenario["editor"])

    client.post(
        reverse("workspace:publicacao_nova"),
        {
            "titulo": "Agendado", "tipo": TipoPublicacao.COMUNICADO,
            "acao": "rascunho", "publicar_em": "2026-09-01T08:30",
        },
    )

    quando = Publicacao.objects.get().publicar_em
    assert timezone.localtime(quando).hour == 8
    assert timezone.is_aware(quando)


def test_acao_por_get_nao_faz_nada(client, cenario):
    """Ação que muda estado exige POST. Por GET, um link colado num chat
    arquivaria o comunicado de quem clicasse."""
    p = escrever(cenario)
    client.force_login(cenario["editor"])

    client.get(reverse("workspace:publicacao_acao", args=[p.pk]))

    p.refresh_from_db()
    assert p.situacao == "no_ar"


def test_excluir_publicado_pela_tela_mostra_o_motivo(client, cenario):
    p = escrever(cenario)
    client.force_login(cenario["editor"])

    client.post(reverse("workspace:publicacao_acao", args=[p.pk]), {"acao": "excluir"})

    assert Publicacao.objects.filter(pk=p.pk).exists()


def test_acao_sem_permissao_e_recusada(client, cenario):
    p = escrever(cenario)
    client.force_login(cenario["ana"])

    resposta = client.post(
        reverse("workspace:publicacao_acao", args=[p.pk]), {"acao": "arquivar"}
    )

    assert resposta.status_code == 403
    p.refresh_from_db()
    assert not p.arquivado
