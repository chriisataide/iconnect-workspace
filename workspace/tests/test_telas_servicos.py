"""As telas operacionais — catálogo, pedido, minhas solicitações, bandeja.

É onde as quatro fundações aparecem juntas: `pode()` filtra o catálogo, APR monta
a cadeia, `Compromisso` alimenta a barra tripla e SVC amarra tudo.
"""

from __future__ import annotations

import re
from decimal import Decimal

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.models.orcamento import competencia_de
from workspace.models import (
    Compromisso,
    GrupoCatalogo,
    ItemCatalogo,
    RegraAprovacao,
    SituacaoServico,
    SolicitacaoServico,
    TipoAprovador,
)
from workspace.providers import orcamento as provedor
from workspace.providers.orcamento import OrcamentoProvider
from workspace.services import catalogo as svc


class ProviderFalso(OrcamentoProvider):
    key = "falso"

    def __init__(self, orcamento=Decimal("38000"), realizado=Decimal("22100")):
        self._o, self._r = orcamento, realizado

    def orcamento_mensal(self, centro_custo_codigo):
        return self._o

    def realizado_no_mes(self, centro_custo_codigo, competencia):
        return self._r


@pytest.fixture
def provider():
    anterior = provedor.obter()
    provedor.registrar(ProviderFalso())
    yield
    provedor.limpar()
    if anterior is not None:
        provedor.registrar(anterior)


@pytest.fixture
def cenario():
    diretor, gestor, ana = (f.pessoa(n) for n in ("diretor", "gestor", "ana"))
    f.lotar(diretor, centro_custo_codigo="1000")
    f.lotar(gestor, gestor=diretor, centro_custo_codigo="1008")
    f.lotar(ana, gestor=gestor, centro_custo_codigo="1008")
    RegraAprovacao.objects.create(dominio="*", tipo=TipoAprovador.GESTOR_DIRETO, ordem=10)

    item = ItemCatalogo.objects.create(
        chave="compra", nome="Comprar algo", descricao_curta="Material ou equipamento",
        grupo=GrupoCatalogo.DINHEIRO, dominio="com.requisicao", icone="cart",
        exige_valor=True, exige_centro_custo=True, prazo_prometido_dias=12,
        campos=[{"chave": "o_que", "rotulo": "O que você precisa", "obrigatorio": True}],
    )
    return {"ana": ana, "gestor": gestor, "diretor": diretor, "item": item}


# ── Acesso aberto ───────────────────────────────────────────────────


@pytest.mark.django_db
def test_o_catalogo_e_aberto(client):
    """A lista de serviços é institucional — quais existem, quanto demoram, o
    que exige aprovação. Fechá-la poria uma parede de login na frente do
    formulário que fica aberto de propósito.

    "Minhas solicitações" e a bandeja saíram desta lista: o conteúdo inteiro
    delas é de UMA pessoa, e sem sessão era o da primeira do organograma.
    """
    resposta = client.get(reverse("workspace:servicos"))
    assert resposta.status_code == 200


@pytest.mark.django_db
def test_catalogo_anonimo_nao_conta_pedido_de_ninguem(client, cenario):
    """Os contadores do trilho ("3 em aberto") são de quem está identificado."""
    svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("10"))

    resposta = client.get(reverse("workspace:servicos"))
    assert resposta.context["abertas"] == 0
    assert resposta.context["devolvidas"] == 0


@pytest.mark.django_db
def test_home_continua_publica(client):
    """A fronteira não vazou para a home."""
    assert client.get(reverse("workspace:home")).status_code == 200


# ── Ver é aberto; assinar exige identidade ──────────────────────────
#
# O acesso aberto vale para LER. Os atos abaixo escrevem em nome de alguém —
# e, sem sessão, `pessoa_da_requisicao()` devolve a primeira pessoa do
# organograma: qualquer visitante aprovaria pedidos, cancelaria o pedido de
# outro e baixaria o atestado médico dela, com o histórico registrando o nome
# de quem não fez nada disso.


@pytest.mark.django_db
@pytest.mark.parametrize(
    "rota,args",
    [
        ("workspace:decidir_aprovacao", [1]),
        ("workspace:aprovar_em_lote", []),
        ("workspace:cancelar_solicitacao", [1]),
        ("workspace:acerto", [1]),
        ("workspace:baixar_anexo", [1]),
        ("workspace:cancelar_reserva", [1]),
    ],
)
def test_ato_em_nome_de_alguem_exige_identidade(client, rota, args):
    destino = reverse(rota, args=args)
    resposta = client.get(destino)

    assert resposta.status_code == 302, f"{rota} respondeu sem sessão"
    assert resposta["Location"].startswith("/entrar/"), resposta["Location"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "rota",
    [
        "workspace:minhas_solicitacoes",
        "workspace:minhas_reservas",
        "workspace:aprovacoes",
        "workspace:meu_dia",
        "workspace:notificacoes",
    ],
)
def test_tela_que_e_de_uma_pessoa_exige_identidade(client, rota):
    """Estas cinco não têm conteúdo institucional nenhum: são os pedidos, as
    reservas, a fila de decisão, o dia e os avisos DE ALGUÉM. Sem sessão,
    mostravam os da primeira pessoa do organograma."""
    resposta = client.get(reverse(rota))

    assert resposta.status_code == 302, rota
    assert resposta["Location"].startswith("/entrar/"), rota


@pytest.mark.django_db
def test_confirmar_leitura_e_correspondencia_tambem_assinam(client):
    """Confirmar leitura de normativo é a linha que a empresa apresenta para
    provar conformidade; a correspondência revela quem recebe intimação."""
    for rota, args in [
        ("workspace:confirmar_leitura", ["qualquer-slug"]),
        ("workspace:correspondencias", []),
        ("workspace:registrar_correspondencia", []),
        ("workspace:entregar_correspondencia", [1]),
        ("workspace:identificar_correspondencia", [1]),
    ]:
        resposta = client.get(reverse(rota, args=args))
        assert resposta.status_code == 302, rota
        assert resposta["Location"].startswith("/entrar/"), rota


@pytest.mark.django_db
def test_o_formulario_abre_para_qualquer_um_mas_enviar_se_identifica(client, cenario):
    """O ato central do produto sem parede de login na frente, e sem pedido
    nascendo em nome de quem não pediu."""
    destino = reverse("workspace:pedir", args=[cenario["item"].chave])

    aberto = client.get(destino)
    assert aberto.status_code == 200
    # E a tela avisa antes, não na hora do envio.
    assert "identificar ao enviar" in aberto.content.decode()

    enviar = client.post(destino, {"o_que": "4 notebooks", "valor": "100,00"})
    assert enviar.status_code == 302
    assert enviar["Location"].startswith("/entrar/")
    assert not SolicitacaoServico.objects.exists()


@pytest.mark.django_db
def test_formulario_anonimo_nao_mostra_dado_de_ninguem(client, cenario):
    """Sem sessão, o centro de custo e os adiantamentos pendentes não são de
    ninguém — mostrar os da primeira pessoa do organograma seria vazamento."""
    corpo = client.get(
        reverse("workspace:pedir", args=[cenario["item"].chave])
    ).content.decode()

    assert "1008" not in corpo, "centro de custo de alguém apareceu para anônimo"
    assert "Peça ao RH" not in corpo, "aviso de lotação para quem não disse quem é"


@pytest.mark.django_db
def test_ver_a_agenda_de_uma_sala_continua_aberto(client):
    """A fronteira da reserva passa dentro da view: consultar é informação de
    escritório — é o que faz a pessoa parar de bater na porta da sala."""
    from workspace.models.reserva import Recurso, TipoRecurso

    Recurso.objects.create(
        codigo="sala-1", nome="Sala 1", tipo=TipoRecurso.SALA, capacidade=6
    )

    aberta = client.get(reverse("workspace:reservar", args=["sala-1"]))
    assert aberta.status_code == 200

    marcar = client.post(reverse("workspace:reservar", args=["sala-1"]), {})
    assert marcar.status_code == 302
    assert marcar["Location"].startswith("/entrar/")


@pytest.mark.django_db
def test_ha_onde_se_identificar(client):
    """Sem esta rota, exigir identidade seria trancar todo mundo do lado de
    fora: `/admin/login/` recusa quem não é staff, e não havia outra porta."""
    assert client.get("/entrar/").status_code == 200


# ── Catálogo ────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_catalogo_agrupa_por_intencao(client, cenario):
    client.force_login(cenario["ana"])
    corpo = client.get(reverse("workspace:servicos")).content.decode()

    assert "Dinheiro" in corpo
    assert "Comprar algo" in corpo
    assert "Financeiro" not in corpo, "grupo é intenção, não departamento"


@pytest.mark.django_db
def test_catalogo_mostra_prazo_e_a_origem_do_numero(client, cenario):
    """Prazo prometido que ninguém cumpre destrói a confiança — a origem do
    número precisa estar visível."""
    client.force_login(cenario["ana"])
    corpo = client.get(reverse("workspace:servicos")).content.decode()

    assert "12 dias" in corpo
    assert "medido" not in corpo, "sem histórico, é estimado"


@pytest.mark.django_db
def test_catalogo_filtra_item_sem_permissao(client, cenario):
    ItemCatalogo.objects.create(
        chave="restrito", nome="Só para RH", grupo=GrupoCatalogo.TRABALHO,
        dominio="rh.x", permissao="rh.admin",
    )
    client.force_login(cenario["ana"])
    corpo = client.get(reverse("workspace:servicos")).content.decode()
    assert "Só para RH" not in corpo


@pytest.mark.django_db
def test_catalogo_vazio_diz_onde_popular(client, cenario):
    ItemCatalogo.objects.all().delete()
    client.force_login(cenario["ana"])
    corpo = client.get(reverse("workspace:servicos")).content.decode()
    assert "semear_catalogo" in corpo


@pytest.mark.django_db
def test_catalogo_avisa_de_devolvida(client, cenario):
    s = svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("100"))
    SolicitacaoServico.objects.filter(pk=s.pk).update(situacao=SituacaoServico.DEVOLVIDA)

    client.force_login(cenario["ana"])
    corpo = client.get(reverse("workspace:servicos")).content.decode()
    assert "devolvida" in corpo.lower()


# ── Pedir ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_formulario_renderiza_os_campos_do_item(client, cenario):
    client.force_login(cenario["ana"])
    corpo = client.get(
        reverse("workspace:pedir", args=[cenario["item"].chave])
    ).content.decode()

    assert 'name="o_que"' in corpo
    assert "O que você precisa" in corpo
    assert 'name="valor"' in corpo


@pytest.mark.django_db
def test_formulario_mostra_centro_de_custo_da_identidade(client, cenario):
    """O usuário não digita centro de custo."""
    client.force_login(cenario["ana"])
    corpo = client.get(
        reverse("workspace:pedir", args=[cenario["item"].chave])
    ).content.decode()
    assert "1008" in corpo


@pytest.mark.django_db
def test_envio_valido_cria_e_redireciona(client, cenario):
    client.force_login(cenario["ana"])
    resposta = client.post(
        reverse("workspace:pedir", args=[cenario["item"].chave]),
        {"o_que": "4 notebooks", "valor": "12.400,00"},
    )

    assert resposta.status_code == 302
    s = SolicitacaoServico.objects.get()
    assert s.valor == Decimal("12400.00"), "aceita 1.234,56 do jeito que se digita"
    assert s.dados["o_que"] == "4 notebooks"


@pytest.mark.django_db
def test_envio_invalido_devolve_TODOS_os_erros(client, cenario):
    """Corrigir um erro por vez é o que faz o usuário desistir no 3º envio."""
    client.force_login(cenario["ana"])
    corpo = client.post(
        reverse("workspace:pedir", args=[cenario["item"].chave]), {}
    ).content.decode()

    assert "Corrija antes de enviar" in corpo
    assert "O que você precisa é obrigatório" in corpo
    assert "Informe o valor" in corpo
    assert SolicitacaoServico.objects.count() == 0


@pytest.mark.django_db
def test_envio_invalido_preserva_o_que_foi_digitado(client, cenario):
    client.force_login(cenario["ana"])
    corpo = client.post(
        reverse("workspace:pedir", args=[cenario["item"].chave]),
        {"o_que": "4 notebooks"},
    ).content.decode()
    assert "4 notebooks" in corpo, "não faz o usuário digitar de novo"


@pytest.mark.django_db
def test_item_inativo_da_404(client, cenario):
    cenario["item"].ativo = False
    cenario["item"].save()
    client.force_login(cenario["ana"])
    assert client.get(
        reverse("workspace:pedir", args=[cenario["item"].chave])
    ).status_code == 404


@pytest.mark.django_db
def test_valor_ilegivel_e_tratado_como_ausente(client, cenario):
    client.force_login(cenario["ana"])
    corpo = client.post(
        reverse("workspace:pedir", args=[cenario["item"].chave]),
        {"o_que": "x", "valor": "abc"},
    ).content.decode()
    assert "Informe o valor" in corpo


@pytest.mark.django_db
def test_auto_aprovada_avisa_que_foi_automatica(client, cenario):
    """Automático não pode significar invisível."""
    cenario["item"].limite_auto_aprovacao = Decimal("500")
    cenario["item"].save()
    client.force_login(cenario["ana"])

    client.post(
        reverse("workspace:pedir", args=[cenario["item"].chave]),
        {"o_que": "cabo", "valor": "100"}, follow=True,
    )
    corpo = client.get(reverse("workspace:minhas_solicitacoes")).content.decode()
    assert "automática" in corpo


# ── Minhas solicitações ─────────────────────────────────────────────


@pytest.mark.django_db
def test_minhas_lista_com_situacao_e_quem_esta_esperando(client, cenario):
    svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("500"))
    client.force_login(cenario["ana"])
    corpo = client.get(reverse("workspace:minhas_solicitacoes")).content.decode()

    assert "Comprar algo" in corpo
    assert "Aguardando aprovação" in corpo
    assert "gestor" in corpo, "mostra quem está com a bola"


@pytest.mark.django_db
def test_minhas_mostra_o_motivo_da_devolucao(client, cenario):
    """Devolução sem motivo obriga a adivinhar."""
    from workspace.services import aprovacao as apr

    s = svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("500"))
    apr.decidir(s.aprovacao, cenario["gestor"], apr.Decisao.DEVOLVER, "faltou cotação")

    client.force_login(cenario["ana"])
    corpo = client.get(reverse("workspace:minhas_solicitacoes")).content.decode()
    assert "faltou cotação" in corpo


@pytest.mark.django_db
def test_minhas_vazio_convida_ao_catalogo(client, cenario):
    client.force_login(cenario["ana"])
    corpo = client.get(reverse("workspace:minhas_solicitacoes")).content.decode()
    assert "ainda não pediu nada" in corpo
    assert reverse("workspace:servicos") in corpo


@pytest.mark.django_db
def test_nao_vejo_solicitacao_de_outro(client, cenario):
    svc.solicitar(cenario["item"], cenario["gestor"], {"o_que": "x"}, Decimal("500"))
    client.force_login(cenario["ana"])
    corpo = client.get(reverse("workspace:minhas_solicitacoes")).content.decode()
    assert "ainda não pediu nada" in corpo


@pytest.mark.django_db
def test_cancelar_pela_tela(client, cenario):
    s = svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("500"))
    client.force_login(cenario["ana"])
    client.post(reverse("workspace:cancelar_solicitacao", args=[s.pk]))

    s.refresh_from_db()
    assert s.situacao == SituacaoServico.CANCELADA


@pytest.mark.django_db
def test_nao_cancelo_solicitacao_de_outro(client, cenario):
    s = svc.solicitar(cenario["item"], cenario["gestor"], {"o_que": "x"}, Decimal("500"))
    client.force_login(cenario["ana"])
    assert client.post(
        reverse("workspace:cancelar_solicitacao", args=[s.pk])
    ).status_code == 404


# ── Bandeja e a barra tripla ────────────────────────────────────────


@pytest.mark.django_db
def test_bandeja_mostra_kpis(client, cenario, provider):
    svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("12400"))
    client.force_login(cenario["gestor"])
    corpo = client.get(reverse("workspace:aprovacoes")).content.decode()

    assert "Esperando você" in corpo
    assert "12.400,00" in corpo, "moeda pt-BR: ponto de milhar, vírgula decimal"


@pytest.mark.django_db
def test_bandeja_traz_a_barra_tripla_com_as_tres_faixas(client, cenario, provider):
    """O dossiê: realizado, comprometido, este pedido — antes de decidir."""
    svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("12400"))
    client.force_login(cenario["gestor"])
    resposta = client.get(reverse("workspace:aprovacoes"))
    corpo = resposta.content.decode()

    faixas = resposta.context["itens"][0]["faixas"]
    assert {f["nome"] for f in faixas} == {"realizado", "pedido"}, (
        "comprometido é zero neste cenário, então não desenha faixa"
    )
    assert "au-medidor-faixa--realizado" in corpo
    assert "realizado" in corpo and "comprometido" in corpo
    assert "após aprovar" in corpo


@pytest.mark.django_db
def test_barra_soma_o_comprometido_de_outro_pedido(client, cenario, provider):
    """O cenário dos dois gestores, na tela."""
    Compromisso.objects.create(
        dominio="x", descricao="outro pedido", centro_custo_codigo="1008",
        valor=Decimal("3200"),
        competencia=competencia_de(),
    )
    svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("12400"))

    client.force_login(cenario["gestor"])
    entrada = client.get(reverse("workspace:aprovacoes")).context["itens"][0]

    assert entrada["resumo"].comprometido == Decimal("3200")
    assert {f["nome"] for f in entrada["faixas"]} == {
        "realizado", "comprometido", "pedido"
    }


@pytest.mark.django_db
def test_barra_avisa_quando_estoura(client, cenario, provider):
    provedor.registrar(ProviderFalso(orcamento=Decimal("15000"), realizado=Decimal("10000")))
    svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("12400"))

    client.force_login(cenario["gestor"])
    resposta = client.get(reverse("workspace:aprovacoes"))

    assert resposta.context["itens"][0]["cabe"] is False
    assert "estoura o orçamento" in resposta.content.decode()


@pytest.mark.django_db
def test_faixa_do_pedido_nao_desenha_fora_do_grafico(client, cenario, provider):
    """Pedido que estoura não pode vazar do SVG — o alerta textual comunica."""
    provedor.registrar(ProviderFalso(orcamento=Decimal("1000"), realizado=Decimal("500")))
    svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("99999"))

    client.force_login(cenario["gestor"])
    faixas = client.get(reverse("workspace:aprovacoes")).context["itens"][0]["faixas"]

    fim = max(f["x_num"] + f["largura_num"] for f in faixas)
    assert fim <= 100.01, f"a barra terminou em {fim}"


@pytest.mark.django_db
def test_sem_orcamento_a_tela_diz_que_nao_calcula(client, cenario):
    """0% o aprovador leria como folga."""
    provedor.limpar()
    svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("12400"))

    client.force_login(cenario["gestor"])
    corpo = client.get(reverse("workspace:aprovacoes")).content.decode()
    assert "não tem orçamento" in corpo
    assert "não consigo calcular" in corpo


@pytest.mark.django_db
def test_bandeja_vazia_celebra(client, cenario):
    client.force_login(cenario["gestor"])
    corpo = client.get(reverse("workspace:aprovacoes")).content.decode()
    assert "Nada esperando por você" in corpo


@pytest.mark.django_db
def test_nao_vejo_a_minha_propria_solicitacao_na_bandeja(client, cenario):
    svc.solicitar(cenario["item"], cenario["gestor"], {"o_que": "x"}, Decimal("500"))
    client.force_login(cenario["gestor"])
    corpo = client.get(reverse("workspace:aprovacoes")).content.decode()
    assert "Nada esperando por você" in corpo


# ── Decidir pela tela ───────────────────────────────────────────────


@pytest.mark.django_db
def test_aprovar_pela_tela(client, cenario, provider):
    s = svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("500"))
    client.force_login(cenario["gestor"])

    client.post(
        reverse("workspace:decidir_aprovacao", args=[s.aprovacao.pk]),
        {"decisao": "aprovar"},
    )

    s.refresh_from_db()
    assert s.situacao == SituacaoServico.APROVADA
    assert Compromisso.objects.get().valor == Decimal("500")


@pytest.mark.django_db
def test_devolver_pela_tela_exige_motivo(client, cenario, provider):
    s = svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("500"))
    client.force_login(cenario["gestor"])

    resposta = client.post(
        reverse("workspace:decidir_aprovacao", args=[s.aprovacao.pk]),
        {"decisao": "devolver", "justificativa": ""}, follow=True,
    )

    s.refresh_from_db()
    assert s.situacao == SituacaoServico.AGUARDANDO_APROVACAO
    assert "exige justificativa" in resposta.content.decode()


@pytest.mark.django_db
def test_aprovar_em_lote_pela_tela(client, cenario, provider):
    pedidos = [
        svc.solicitar(cenario["item"], cenario["ana"], {"o_que": f"item {i}"}, Decimal("100"))
        for i in range(3)
    ]
    client.force_login(cenario["gestor"])

    client.post(
        reverse("workspace:aprovar_em_lote"),
        {"selecionadas": [str(p.aprovacao.pk) for p in pedidos]},
        follow=True,
    )

    for p in pedidos:
        p.refresh_from_db()
        assert p.situacao == SituacaoServico.APROVADA


@pytest.mark.django_db
def test_lote_reporta_a_que_falhou_sem_abortar_as_boas(client, cenario, provider):
    boas = [
        svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("100"))
        for _ in range(2)
    ]
    propria = svc.solicitar(cenario["item"], cenario["gestor"], {"o_que": "y"}, Decimal("100"))

    client.force_login(cenario["gestor"])
    resposta = client.post(
        reverse("workspace:aprovar_em_lote"),
        {"selecionadas": [str(p.aprovacao.pk) for p in boas + [propria]]},
        follow=True,
    )

    corpo = resposta.content.decode()
    assert "2 aprovada" in corpo
    assert "próprio pedido" in corpo, (
        "a guarda de auto-aprovação vem ANTES da de permissão, e é ela que pega"
    )
    for p in boas:
        p.refresh_from_db()
        assert p.situacao == SituacaoServico.APROVADA


@pytest.mark.django_db
def test_get_em_rota_de_decisao_apenas_redireciona(client, cenario):
    """Decisão é POST. GET não decide nada — só volta para a bandeja."""
    s = svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("500"))

    client.force_login(cenario["gestor"])
    for url in [
        reverse("workspace:decidir_aprovacao", args=[s.aprovacao.pk]),
        reverse("workspace:aprovar_em_lote"),
    ]:
        assert client.get(url).status_code == 302

    client.force_login(cenario["ana"])
    assert client.get(
        reverse("workspace:cancelar_solicitacao", args=[s.pk])
    ).status_code == 302


# ── Rail ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_rail_mostra_bandeja_para_quem_pode_aprovar_mesmo_com_zero(client, cenario):
    """A porta não some quando a pessoa termina de usá-la.

    A regra antiga era "só aparece com pendência", e ela se voltava contra o
    aprovador: ele decidia o último pedido, o contador ia a zero e o item
    desaparecia do trilho. No dia seguinte não havia por onde entrar — e o
    caminho que sobrava era procurar a URL.

    Zero é informação: diz "nada esperando por mim", que é justamente o que o
    aprovador precisa ler para confiar que não esqueceu ninguém. A regra vale
    para QUEM PODE APROVAR — para os outros o item continua fora, porque aí sim
    seria um item que não leva a nada.
    """
    client.force_login(cenario["gestor"])
    corpo = client.get(reverse("workspace:servicos")).content.decode()
    assert "Bandeja" in corpo

    svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("500"))
    assert "Bandeja" in client.get(reverse("workspace:servicos")).content.decode()


@pytest.mark.django_db
def test_rail_esconde_a_bandeja_de_quem_nao_aprova_nada(client, cenario):
    client.force_login(cenario["ana"])

    assert "Bandeja" not in client.get(reverse("workspace:servicos")).content.decode()


@pytest.mark.django_db
def test_contexto_do_rail_nao_roda_fora_do_portal(client, cenario):
    """ADR-009: curto-circuito fora de /workspace/. A home pública é a tela mais
    acessada e não pode pagar por contador de área pessoal."""
    from workspace.context import rail

    class Req:
        path = "/dashboard/"
        user = cenario["ana"]

    assert rail(Req()) == {}


@pytest.mark.django_db
def test_contexto_do_rail_usa_pessoa_aberta_para_anonimo():
    from django.contrib.auth.models import AnonymousUser

    from workspace.context import rail

    class Req:
        path = "/workspace/"
        user = AnonymousUser()

    assert rail(Req()) == {
        # Anônimo não é ninguém, e a topbar não escreve nome nenhum para ele.
        # O rail usa `pessoa_da_requisicao()` — que devolve uma pessoa de
        # REFERÊNCIA para calcular alcance —, e usar a mesma coisa aqui poria o
        # nome de um colega no canto da tela de quem nunca entrou.
        "eu": None,
        "abertas": 0,
        # §43 — rascunho tem contador próprio, e o do anônimo também é zero.
        "rascunhos": 0,
        "pendentes_aprovacao": 0,
        "nao_lidas": 0,
        "notificacoes_recentes": (),
        # Anônimo não atende fila nenhuma, e o item "Atender" nem aparece no
        # trilho: contador zerado é o que faz alguém aprender a ignorá-lo.
        "na_fila": 0,
        # Nem administra papéis — a tela de quem aprova o quê é mapa de poder
        # da empresa, e ela também concede.
        "administra_papeis": False,
        # O painel de indicadores segue a mesma regra: sem sessão, sem item.
        "ve_aprovacoes": False,
        "habilitacoes_pendentes": 0,
        "ve_faq": False,
        "ve_publicacoes": False,
        "ve_indicadores": False,
        # §Onda 3 — a tela de resultados e a de fontes. `False` para
        # anônimo pela razão mais simples possível: resultado
        # financeiro não é informação institucional, e a tela de
        # fontes conta quais sistemas a empresa usa.
        "ve_resultados": False,
        # §Onda 4 — o painel de exceções. `False` para anônimo pela
        # mesma razão dos outros dois: a lista de regras conta o que a
        # empresa vigia, e a grade nomeia gente.
        "ve_excecoes": False,
        "ve_fontes": False,
        # E o mesmo para estoque e equipamentos: a porta do estoque não é
        # oferecida a quem não pode abri-la, e "0 para confirmar" seria o número
        # de outra pessoa.
        "ve_estoque": False,
        "custodias_a_aceitar": 0,
        "ve_frota": False,
        "prazos_de_veiculo": 0,
        # §37 — leitura obrigatória e vigência de documento seguem a mesma
        # regra: são de UMA pessoa, e o anônimo não é ninguém.
        "leituras_pendentes": 0,
        "ve_documentos": False,
        "documentos_a_vencer": 0,
        "ve_marketing": False,
        "prazos_de_marketing": 0,
        "ve_candidaturas": False,
        "chamados_abertos": 0,
    }


# ── CSP: nenhum estilo inline ───────────────────────────────────────


@pytest.mark.django_db
@pytest.mark.parametrize(
    "rota", ["workspace:home", "workspace:servicos", "workspace:minhas_solicitacoes",
             "workspace:aprovacoes"]
)
def test_nenhuma_tela_usa_atributo_style(client, cenario, rota):
    """A CSP de produção traz nonce em `style-src`, e navegador moderno IGNORA
    `unsafe-inline` quando há nonce — nonce não se aplica a atributo `style=""`.

    Foi por isso que a barra de orçamento virou SVG: `width` é atributo, não
    estilo. Este teste impede a regressão silenciosa, que só apareceria em
    produção como layout quebrado.
    """
    client.force_login(cenario["ana"])
    corpo = client.get(reverse(rota)).content.decode()
    encontrados = re.findall(r"<[^>]+\sstyle=", corpo)
    assert not encontrados, f"style inline em {rota}: {encontrados[:3]}"


@pytest.mark.django_db
def test_cancelar_o_que_ja_esta_concluido_mostra_o_erro(client, cenario):
    """Erro do serviço vira mensagem na tela, não 500."""
    s = svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("500"))
    s.concluir()

    client.force_login(cenario["ana"])
    resposta = client.post(
        reverse("workspace:cancelar_solicitacao", args=[s.pk]), follow=True
    )
    assert "já está concluída" in resposta.content.decode()


@pytest.mark.django_db
def test_svg_usa_ponto_decimal_e_nao_virgula(client, cenario, provider):
    """Bug que só o console do browser mostra.

    O Django localiza número no template (pt-BR → `8,42`), e vírgula é INVÁLIDA
    em atributo SVG: o navegador descarta o `<rect>` e a barra simplesmente não
    desenha. Teste de servidor passaria felizmente.
    """
    svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("12400"))
    client.force_login(cenario["gestor"])
    corpo = client.get(reverse("workspace:aprovacoes")).content.decode()

    numeros = re.findall(r'<rect[^>]*\s(?:x|width)="([^"]+)"', corpo)
    assert numeros, "nenhum <rect> encontrado na barra"
    for valor in numeros:
        assert "," not in valor, f"vírgula em atributo SVG: {valor!r}"
        float(valor)  # levanta se não for número válido


@pytest.mark.django_db
def test_linha_este_pedido_some_quando_nao_ha_valor(client, cenario, provider):
    """Férias e viagem sem valor renderizavam "este pedido R$" vazio."""
    sem_valor = ItemCatalogo.objects.create(
        chave="ferias", nome="Férias", grupo=GrupoCatalogo.TRABALHO,
        dominio="rh.ferias", exige_centro_custo=True,
    )
    svc.solicitar(sem_valor, cenario["ana"])

    client.force_login(cenario["gestor"])
    corpo = client.get(reverse("workspace:aprovacoes")).content.decode()
    assert "este pedido" not in corpo


@pytest.mark.django_db
def test_moeda_tem_separador_de_milhar(client, cenario, provider):
    """`R$ 13720,00` exige contar dígitos."""
    svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("12400"))
    client.force_login(cenario["gestor"])
    corpo = client.get(reverse("workspace:aprovacoes")).content.decode()

    assert "12.400,00" in corpo
    assert "12400,00" not in corpo


@pytest.mark.django_db
def test_lote_sem_selecao_avisa_em_vez_de_aprovar_zero(client, cenario, provider):
    svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("100"))
    client.force_login(cenario["gestor"])

    resposta = client.post(reverse("workspace:aprovar_em_lote"), {}, follow=True)
    corpo = resposta.content.decode()

    assert "Selecione ao menos uma" in corpo
    assert "0 aprovada" not in corpo


# ── Os ajustes da revisão de tela ───────────────────────────────────


@pytest.mark.django_db
def test_toda_tela_de_modulo_tem_por_onde_voltar(client, cenario):
    """Voltar no canto superior direito, em todas elas.

    É um LINK com destino, e não `history.back()`: quem chegou por um link
    colado no chat, ou depois de um envio que redirecionou, tem histórico que
    não leva onde espera — e um botão que às vezes volta para o lugar certo é
    pior que um que sempre volta para o mesmo.
    """
    client.force_login(cenario["ana"])

    for rota in [
        "workspace:servicos",
        "workspace:minhas_solicitacoes",
        "workspace:meu_dia",
        "workspace:notificacoes",
        "workspace:documentacao",
        "workspace:reservas",
    ]:
        corpo = client.get(reverse(rota)).content.decode()
        assert 'class="au-voltar"' in corpo, rota


@pytest.mark.django_db
def test_a_linha_de_minhas_solicitacoes_e_clicavel_sem_botao(client, cenario):
    """Sem botão dentro da tabela: ele desenhava uma borda no lugar onde se
    espera texto, e criava dois alvos de clique para a mesma coisa.

    `tabindex` e `role` ficam, senão a linha clicável não recebe foco e não
    responde a Enter.
    """
    svc.solicitar(cenario["item"], cenario["ana"], {"o_que": "x"}, Decimal("10"))
    client.force_login(cenario["ana"])

    corpo = client.get(reverse("workspace:minhas_solicitacoes")).content.decode()

    assert 'tabindex="0" role="button"' in corpo
    assert "au-link-tabela" not in corpo, "o botão saiu da linha"


@pytest.mark.django_db
def test_o_estatico_e_versionado_em_desenvolvimento(client, settings):
    """Sem versão na URL, o navegador serve o JS da manhã à tarde.

    Aconteceu: uma tela pareceu quebrada porque o navegador tinha o JS de antes
    do stepper e o CSS de antes do `[hidden]`. Em produção o
    `ManifestStaticFilesStorage` já põe hash no nome; em desenvolvimento não há
    hash nenhum, e é aqui que a versão entra.
    """
    settings.DEBUG = True
    corpo = client.get(reverse("workspace:home")).content.decode()

    assert "workspace.js?v=" in corpo
    assert "workspace.css?v=" in corpo
