"""§20, §21, §38, §52 e §18 — a integração com o iConnect.

## O que estes testes garantem, e por que nenhum toca a rede

Todos usam um transporte falso. Um teste que chama o iConnect de verdade falha
quando o outro lado cai, passa a depender de dado que alguém mudou lá, e não
roda na máquina de quem não tem acesso — três formas de a suíte deixar de
significar alguma coisa.

O que eles guardam:

1. **Nada aqui derruba uma tela.** Sem configuração, sem token, com timeout ou
   com o outro lado em 500, a tela desenha e diz o que houve **em português**.
2. **O contador do trilho nunca levanta.** Ele está em toda tela do portal; uma
   exceção ali derrubaria o produto inteiro por causa de outro deploy.
3. **`POST` não é repetido.** O único que fazemos consome um código de uso
   único — repetir seria queimá-lo duas vezes.
4. **O código do SSO sai da URL por redirecionamento**, e não por JavaScript.
5. **O Workspace não escreve no iConnect.** Abrir chamado é lá.
"""

from __future__ import annotations

import json
import urllib.error
from io import BytesIO

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.integracoes import cliente
from workspace.integracoes import iconnect as ic
from workspace.integracoes import sessao

pytestmark = pytest.mark.django_db


class RespostaFalsa:
    def __init__(self, corpo):
        self._corpo = corpo if isinstance(corpo, bytes) else json.dumps(corpo).encode()

    def read(self):
        return self._corpo

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def api(settings, monkeypatch):
    """Um iConnect de mentira. Guarda o que foi pedido e devolve o que mandarem."""
    settings.ICONNECT_API_URL = "https://iconnect.exemplo/"
    settings.ICONNECT_TIMEOUT = 1
    settings.WORKSPACE_SHARED_SECRET = ""
    monkeypatch.setattr(cliente.time, "sleep", lambda *_: None)

    estado = {"chamadas": [], "resposta": {"results": []}, "erro": None}

    def falso(requisicao, timeout=None):
        estado["chamadas"].append(
            {
                "url": requisicao.full_url,
                "metodo": requisicao.get_method(),
                "cabecalhos": dict(requisicao.header_items()),
                "corpo": requisicao.data,
            }
        )
        if estado["erro"] is not None:
            erro = estado["erro"]
            # Só o primeiro estouro, quando pedido — permite testar o retry.
            if estado.get("errar_uma_vez"):
                estado["erro"] = None
            raise erro
        return RespostaFalsa(estado["resposta"])

    # UM patch só: `cliente` e `sessao` importam o mesmo `urllib.request`, e o
    # módulo é o mesmo objeto — patchear os dois seria patchear duas vezes a
    # mesma coisa e esconder isso de quem lê.
    monkeypatch.setattr(cliente.urllib.request, "urlopen", falso)
    return estado


def http(codigo: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://iconnect.exemplo/x", codigo, "erro", {}, BytesIO(b"")
    )


@pytest.fixture
def pessoa_logada(client):
    pessoa = f.pessoa("ana")
    f.lotar(pessoa)
    client.force_login(pessoa)
    return pessoa


def com_token(client, token="jwt-de-teste"):
    sessao_do_cliente = client.session
    sessao_do_cliente[sessao.CHAVE_ACCESS] = token
    sessao_do_cliente.save()


# ── O transporte — §52 e §53 ────────────────────────────────────────


def test_sem_configuracao_a_chamada_nem_sai(settings):
    """Estado NORMAL e não falha: o Workspace roda sem o iConnect."""
    settings.ICONNECT_API_URL = ""

    assert cliente.disponivel() is False
    with pytest.raises(cliente.IntegracaoIndisponivel):
        cliente.chamar("/api/v1/tickets/")


def test_a_mensagem_de_indisponivel_e_em_portugues(settings):
    settings.ICONNECT_API_URL = ""

    assert "não está configurada" in str(cliente.IntegracaoIndisponivel())


def test_o_token_vai_no_cabecalho(api):
    cliente.chamar("/api/v1/tickets/", token="abc123")

    assert api["chamadas"][0]["cabecalhos"]["Authorization"] == "Bearer abc123"


def test_parametro_vazio_nao_vira_filtro(api):
    """`?status=None` viraria um filtro literal pela string "None" do outro lado."""
    cliente.chamar("/api/v1/tickets/", parametros={"status": None, "ordering": "-id"})

    assert "status" not in api["chamadas"][0]["url"]
    assert "ordering=-id" in api["chamadas"][0]["url"]


def test_get_com_erro_de_rede_e_repetido(api):
    api["erro"] = urllib.error.URLError("recusou")
    api["errar_uma_vez"] = True

    cliente.chamar("/api/v1/tickets/")

    assert len(api["chamadas"]) == 2


def test_get_com_500_e_repetido(api):
    api["erro"] = http(503)
    api["errar_uma_vez"] = True

    cliente.chamar("/api/v1/tickets/")

    assert len(api["chamadas"]) == 2


def test_erro_de_permissao_nao_e_repetido(api):
    """Insistir num 403 só demora mais para dar o mesmo erro."""
    api["erro"] = http(403)

    with pytest.raises(cliente.IntegracaoError, match="sessão"):
        cliente.chamar("/api/v1/tickets/")

    assert len(api["chamadas"]) == 1


def test_post_nunca_e_repetido(api):
    """Repetir um `POST` é reenviar — e o único que fazemos consome um código de
    uso único."""
    api["erro"] = http(503)

    with pytest.raises(cliente.IntegracaoError):
        cliente.chamar("/api/v1/x/", metodo="POST", corpo={"a": 1})

    assert len(api["chamadas"]) == 1


def test_o_corpo_bruto_do_outro_lado_nunca_vai_para_a_tela(api):
    """O 403 do iConnect às vezes vem como PÁGINA HTML — o `role_required`
    deles. Mostrar o corpo cru despejaria HTML na tela."""
    api["erro"] = http(500)

    with pytest.raises(cliente.IntegracaoError) as capturado:
        cliente.chamar("/api/v1/tickets/")

    assert "<" not in str(capturado.value)
    assert "problema" in str(capturado.value)


def test_json_malformado_vira_mensagem_e_nao_stacktrace(api):
    api["resposta"] = b"<html>desculpe</html>"

    with pytest.raises(cliente.IntegracaoError, match="formato inesperado"):
        cliente.chamar("/api/v1/tickets/")


def test_sucesso_falso_com_http_200_e_tratado_como_erro(api):
    """§10 do `API.md`: vários endpoints devolvem `{"success": false}` com HTTP
    200. Confiar só no status faria a falha passar por sucesso."""
    api["resposta"] = {"success": False, "error": "faltou parâmetro"}

    with pytest.raises(cliente.IntegracaoError, match="faltou parâmetro"):
        cliente.chamar("/api/v1/x/")


def test_corpo_vazio_e_resposta_legitima(api):
    """`204` é resposta normal, e tratá-la como falha faria uma operação
    bem-sucedida aparecer como problema."""
    api["resposta"] = b""

    assert cliente.chamar("/api/v1/x/") == {}


# ── A ponte SSO → JWT — §21 ─────────────────────────────────────────


def test_a_ponte_troca_o_codigo_por_um_jwt(api, client, pessoa_logada):
    api["resposta"] = {"access": "novo-access", "refresh": "novo-refresh"}

    client.get(reverse("workspace:home"), {"sso_exchange": "codigo-de-uso-unico"})

    assert client.session[sessao.CHAVE_ACCESS] == "novo-access"
    assert client.session[sessao.CHAVE_REFRESH] == "novo-refresh"


def test_o_codigo_sai_da_url_por_redirecionamento(api, client, pessoa_logada):
    """Mais forte que `history.replaceState`: o código nunca chega a existir numa
    URL que o navegador guarda, e nunca entra no `Referer` da requisição
    seguinte."""
    api["resposta"] = {"access": "x"}

    resposta = client.get(reverse("workspace:home"), {"sso_exchange": "abc"})

    assert resposta.status_code == 302
    assert "sso_exchange" not in resposta["Location"]


def test_o_redirecionamento_preserva_os_outros_parametros(api, client, pessoa_logada):
    api["resposta"] = {"access": "x"}

    resposta = client.get(
        reverse("workspace:minhas_solicitacoes"),
        {"sso_exchange": "abc", "situacao": "abertas"},
    )

    assert "situacao=abertas" in resposta["Location"]
    assert "sso_exchange" not in resposta["Location"]


def test_codigo_recusado_nao_impede_a_pessoa_de_entrar(api, client, pessoa_logada):
    """Código expirado é rotina — a pessoa deixou a aba aberta um minuto a mais.
    O que ela perde é a leitura do iConnect, não o Workspace."""
    api["erro"] = http(400)

    resposta = client.get(reverse("workspace:home"), {"sso_exchange": "velho"})

    assert resposta.status_code == 302
    assert sessao.CHAVE_ACCESS not in client.session


def test_o_codigo_e_limpo_da_url_mesmo_quando_a_troca_falha(api, client, pessoa_logada):
    """Ele já foi consumido (ou já era inválido); deixá-lo na URL só o expõe."""
    api["erro"] = http(400)

    resposta = client.get(reverse("workspace:home"), {"sso_exchange": "velho"})

    assert "sso_exchange" not in resposta["Location"]


def test_o_segredo_compartilhado_vai_no_cabecalho(api, client, pessoa_logada, settings):
    settings.WORKSPACE_SHARED_SECRET = "segredo"
    api["resposta"] = {"access": "x"}

    client.get(reverse("workspace:home"), {"sso_exchange": "abc"})

    assert api["chamadas"][0]["cabecalhos"]["X-workspace-secret"] == "segredo"


def test_sem_integracao_a_ponte_nao_faz_nada(client, pessoa_logada, settings):
    settings.ICONNECT_API_URL = ""

    resposta = client.get(reverse("workspace:home"), {"sso_exchange": "abc"})

    assert resposta.status_code == 302
    assert sessao.CHAVE_ACCESS not in client.session


# ── Chamados — §21 e §38 ────────────────────────────────────────────


UM_TICKET = {
    "results": [
        {
            "id": 4211,
            "titulo": "Notebook não liga",
            "categoria": "Hardware",
            "status": "em_andamento",
            "prioridade": "alta",
            "agente_nome": "Bruno Lima",
            "criado_em": "2026-08-10T09:00:00Z",
            "atualizado_em": "2026-08-18T14:30:00Z",
        }
    ]
}


def test_a_tela_de_chamados_mostra_a_tabela_do_prompt(api, client, pessoa_logada):
    api["resposta"] = UM_TICKET
    com_token(client)

    corpo = client.get(reverse("workspace:chamados")).content.decode()

    assert "#4211" in corpo
    assert "Notebook não liga" in corpo
    assert "Em andamento" in corpo
    assert "Bruno Lima" in corpo


def test_status_desconhecido_nao_vira_erro(api, client, pessoa_logada):
    """Inventar rótulo para o que não se conhece é como uma tela passa a mentir
    sobre o estado de um chamado."""
    assert ic.rotulo_do_status("triagem_avancada") == "Triagem avancada"
    assert ic.rotulo_do_status("") == "—"


def test_a_tela_de_chamados_nao_abre_chamado(api, client, pessoa_logada):
    """§38 — abrir é no iConnect, que é onde ele é atendido."""
    api["resposta"] = UM_TICKET
    com_token(client)

    corpo = client.get(reverse("workspace:chamados")).content.decode()

    assert "<form" not in corpo.split("au-modulo-corpo")[-1].split("</main>")[0]
    assert "Abrir chamado no iConnect" in corpo


def test_sem_token_a_tela_diz_como_conectar(api, client, pessoa_logada):
    resposta = client.get(reverse("workspace:chamados"))

    assert resposta.status_code == 200
    assert "não está conectado ao iConnect" in resposta.content.decode()


def test_sem_configuracao_a_tela_diz_isso_e_nao_quebra(client, pessoa_logada, settings):
    settings.ICONNECT_API_URL = ""

    resposta = client.get(reverse("workspace:chamados"))

    assert resposta.status_code == 200
    assert "não está configurada" in resposta.content.decode()


def test_iconnect_fora_do_ar_nao_derruba_a_tela(api, client, pessoa_logada):
    api["erro"] = http(500)
    com_token(client)

    resposta = client.get(reverse("workspace:chamados"))

    assert resposta.status_code == 200
    assert "problema" in resposta.content.decode()


def test_o_contador_do_trilho_nunca_levanta(api, client, pessoa_logada):
    """Ele está em TODA tela do portal: uma exceção ali derrubaria o produto
    inteiro por causa de um sistema que é de outro deploy."""
    api["erro"] = http(500)
    com_token(client)

    resposta = client.get(reverse("workspace:meu_dia"))

    assert resposta.status_code == 200
    assert resposta.context["chamados_abertos"] == 0


def test_o_contador_conta_so_os_abertos(api, client, pessoa_logada):
    api["resposta"] = {
        "results": [
            {"id": 1, "status": "aberto"},
            {"id": 2, "status": "encerrado"},
            {"id": 3, "status": "em_andamento"},
        ]
    }
    com_token(client)

    assert client.get(reverse("workspace:meu_dia")).context["chamados_abertos"] == 2


def test_o_token_expirado_e_renovado_uma_vez(api, client, pessoa_logada, monkeypatch):
    """O access do iConnect vale 1 hora; sem renovar, a tela quebraria depois do
    almoço para quem entrou de manhã."""
    sessao_do_cliente = client.session
    sessao_do_cliente[sessao.CHAVE_ACCESS] = "velho"
    sessao_do_cliente[sessao.CHAVE_REFRESH] = "refresh-bom"
    sessao_do_cliente.save()

    chamadas = {"n": 0, "renovou": 0}

    def alterna(requisicao, timeout=None):
        if "refresh" in requisicao.full_url:
            chamadas["renovou"] += 1
            return RespostaFalsa({"access": "novo"})
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            raise http(401)
        return RespostaFalsa(UM_TICKET)

    monkeypatch.setattr(cliente.urllib.request, "urlopen", alterna)

    corpo = client.get(reverse("workspace:chamados")).content.decode()

    assert "Notebook não liga" in corpo
    assert client.session[sessao.CHAVE_ACCESS] == "novo"
    # UMA renovação, e não uma por leitura: o contador do trilho e a tela
    # chamam a API na mesma requisição, e renovar duas vezes seria queimar o
    # refresh à toa.
    assert chamadas["renovou"] == 1


# ── Campo — §18 ─────────────────────────────────────────────────────


def test_o_campo_exige_quem_opera_a_frota(api, client, pessoa_logada):
    """A posição de uma pessoa em tempo real é dado sensível sobre ela, não
    informação institucional."""
    assert client.get(reverse("workspace:campo")).status_code == 403


@pytest.fixture
def operador_de_frota(client):
    pessoa = f.pessoa("almoxarife")
    f.lotar(pessoa)
    f.atribuir(pessoa, f.papel("sup", ["log.frota.ler.global"], escopo="global"))
    client.force_login(pessoa)
    return pessoa


def test_o_campo_mostra_onde_a_equipe_esta(api, client, operador_de_frota):
    api["resposta"] = {
        "results": [
            {
                "tecnico_nome": "Carlos Souza",
                "lat": -23.5,
                "lng": -46.6,
                "speed_kmh": 42,
                "is_moving": True,
                "battery": 78,
            }
        ]
    }
    com_token(client)

    corpo = client.get(reverse("workspace:campo")).content.decode()

    assert "Carlos Souza" in corpo
    assert "Em deslocamento" in corpo
    assert "42 km/h" in corpo


def test_o_workspace_nao_coleta_gps(api, client, operador_de_frota):
    """Um segundo rastreamento produziria duas verdades sobre onde a mesma
    pessoa está — e a que diverge seria a que alguém usou para despachar."""
    com_token(client)
    client.get(reverse("workspace:campo"))

    metodos = {c["metodo"] for c in api["chamadas"]}
    assert metodos == {"GET"}
    assert not any("tracking/batch" in c["url"] for c in api["chamadas"])


def test_a_sequencia_de_rota_vem_calculada_de_la(api, client, operador_de_frota):
    """Reordenar aqui seria escrever um segundo otimizador que discorda do
    primeiro — e o técnico segue o app, não esta tela."""
    api["resposta"] = {
        "results": [
            {
                "codigo": "OS-77",
                "titulo": "Troca de DVR",
                "tecnico_nome": "Carlos",
                "sequencia_rota": 3,
                "duracao_estimada_min": 45,
                "sla_violado": True,
                "status_label": "A caminho",
            }
        ]
    }
    com_token(client)

    corpo = client.get(reverse("workspace:campo")).content.decode()

    assert "OS-77" in corpo
    assert "SLA estourado" in corpo
    assert "45 min" in corpo


def test_o_campo_nao_quebra_com_o_fsm_fora_do_ar(api, client, operador_de_frota):
    api["erro"] = http(502)
    com_token(client)

    resposta = client.get(reverse("workspace:campo"))

    assert resposta.status_code == 200
    assert "problema" in resposta.content.decode()


def test_a_lista_vem_do_envelope_paginado_ou_cru(api):
    assert ic._pagina({"results": [1, 2]}) == [1, 2]
    assert ic._pagina([1, 2]) == [1, 2]
    assert ic._pagina({"nada": 1}) == []


# ── Os caminhos de falha da sessão — §53 ────────────────────────────
#
# São eles que decidem se uma indisponibilidade do outro lado vira uma tela com
# recado ou um 500. Ficar sem teste aqui seria testar só o dia bom.


class RequisicaoFalsa:
    """Um objeto com `session`, que é tudo o que estas funções precisam."""

    def __init__(self, session=None):
        self.session = {} if session is None else session


def test_resposta_sem_access_nao_conecta(api):
    """O iConnect respondeu 200 e não mandou token. Guardar `None` faria a
    chamada seguinte ir com `Bearer None`."""
    api["resposta"] = {"refresh": "só o refresh"}
    requisicao = RequisicaoFalsa()

    assert sessao.trocar_codigo(requisicao, "abc") is False
    assert sessao.CHAVE_ACCESS not in requisicao.session


def test_codigo_vazio_nem_tenta(api):
    assert sessao.trocar_codigo(RequisicaoFalsa(), "") is False
    assert api["chamadas"] == []


def test_erro_de_rede_na_troca_nao_levanta(api):
    api["erro"] = urllib.error.URLError("sem rota")

    assert sessao.trocar_codigo(RequisicaoFalsa(), "abc") is False


def test_json_invalido_na_troca_nao_levanta(api):
    api["resposta"] = b"nao sou json"

    assert sessao.trocar_codigo(RequisicaoFalsa(), "abc") is False


def test_renovar_sem_refresh_e_falso(api):
    assert sessao.renovar(RequisicaoFalsa()) is False


def test_renovar_com_refresh_recusado_esquece_tudo(api):
    """Insistir com um refresh morto faria toda tela do portal esperar por uma
    chamada que já se sabe que falha."""
    api["erro"] = http(401)
    requisicao = RequisicaoFalsa(
        {sessao.CHAVE_ACCESS: "velho", sessao.CHAVE_REFRESH: "morto"}
    )

    assert sessao.renovar(requisicao) is False
    assert requisicao.session == {}


def test_renovar_com_resposta_sem_access_esquece_tudo(api):
    api["resposta"] = {"detail": "ok mas sem token"}
    requisicao = RequisicaoFalsa(
        {sessao.CHAVE_ACCESS: "velho", sessao.CHAVE_REFRESH: "vivo"}
    )

    assert sessao.renovar(requisicao) is False
    assert requisicao.session == {}


def test_renovar_grava_o_access_novo(api):
    api["resposta"] = {"access": "novissimo"}
    requisicao = RequisicaoFalsa(
        {sessao.CHAVE_ACCESS: "velho", sessao.CHAVE_REFRESH: "vivo"}
    )

    assert sessao.renovar(requisicao) is True
    assert requisicao.session[sessao.CHAVE_ACCESS] == "novissimo"


def test_esquecer_e_seguro_sem_sessao():
    """Objeto sem `session` acontece em comando de linha e em teste — e uma
    exceção aqui derrubaria o caminho de limpeza justamente quando ele importa."""
    class SemSessao:
        pass

    sessao.esquecer(SemSessao())
    assert sessao.token_de(SemSessao()) == ""


def test_conectado_exige_configuracao_E_token(api, settings):
    requisicao = RequisicaoFalsa({sessao.CHAVE_ACCESS: "x"})
    assert sessao.conectado(requisicao) is True

    settings.ICONNECT_API_URL = ""
    assert sessao.conectado(requisicao) is False


def test_sem_token_a_leitura_diz_isso_e_nao_finge_queda(api):
    """Quem entrou por senha, sem passar pelo SSO, simplesmente não tem token —
    e a tela precisa distinguir isso de "o iConnect caiu"."""
    with pytest.raises(cliente.IntegracaoError, match="ainda não está conectado"):
        ic.chamados_de(RequisicaoFalsa())
