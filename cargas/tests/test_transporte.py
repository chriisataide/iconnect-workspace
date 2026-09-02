"""O transporte dos conectores — e a disciplina que ele divide com o do iConnect.

O teste que mais importa aqui não é sobre HTTP: é
`test_nenhum_transporte_registra_credencial`. Ele exercita os DOIS transportes
do repositório e afirma que nenhum valor de cabeçalho chega ao log.

É de propósito que a garantia esteja num teste e não numa classe-base
compartilhada. Os dois transportes têm requisitos opostos — 4 s contra 60 s,
retry linear contra exponencial, "nunca repete POST" contra "POST é o método de
leitura do monday" —, e um módulo com seis parâmetros para servir aos dois não
serviria bem a nenhum. Código compartilhado ainda pode ser mal usado; o teste
amarra os dois independentemente de como cada um é escrito.
"""

from __future__ import annotations

import io
import json
import logging
import urllib.error

import pytest

from cargas import transporte

SEGREDO = "tok_ultrassecreto_123456"


class _Resposta(io.BytesIO):
    """O mínimo que `urlopen` devolve: um arquivo com `__enter__`."""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _erro(codigo: int, corpo: dict | None = None, cabecalhos: dict | None = None):
    return urllib.error.HTTPError(
        "https://fonte.exemplo/x",
        codigo,
        "erro",
        cabecalhos or {},
        io.BytesIO(json.dumps(corpo or {}).encode()),
    )


@pytest.fixture
def resposta_falsa(monkeypatch):
    """Substitui `urlopen` por uma sequência de respostas ou erros."""

    def _preparar(*passos):
        chamadas = []

        def _falso(requisicao, timeout=None):
            chamadas.append(requisicao)
            passo = passos[min(len(chamadas) - 1, len(passos) - 1)]
            if isinstance(passo, Exception):
                raise passo
            return _Resposta(json.dumps(passo).encode())

        monkeypatch.setattr(transporte.urllib.request, "urlopen", _falso)
        return chamadas

    return _preparar


# ── Recuo ───────────────────────────────────────────────────────────


def test_o_recuo_e_exponencial_e_nao_linear():
    """1 s, 2 s, 4 s — e não 1, 1, 1.

    Três batidas seguidas num serviço em recuperação é como um `429` vira um
    bloqueio. O transporte do iConnect usa recuo linear curto porque tem uma
    tela esperando; aqui não tem ninguém esperando, e o certo é dar espaço.
    """
    assert [transporte._recuo(n) for n in (1, 2, 3)] == [1.0, 2.0, 4.0]


def test_o_recuo_tem_teto():
    """Sem teto, uma sequência longa esperaria minutos entre tentativas e a
    carga estouraria a janela sem nunca falhar de vez."""
    assert transporte._recuo(20) == transporte.RECUO_MAXIMO


def test_honra_o_tempo_que_a_propria_fonte_pediu(resposta_falsa):
    """O monday devolve `retry_in_seconds` no erro de limite.

    O número da fonte vence o nosso chute: o recuo exponencial pode esperar de
    menos e queimar as tentativas, ou de mais e estourar a janela.
    """
    esperas = []
    resposta_falsa(_erro(429, {"retry_in_seconds": 7}), {"ok": True})

    transporte.pedir(
        "https://api.monday.com/v2", metodo="POST", dormir=esperas.append
    )

    assert esperas == [7.0], "esperou o que a fonte pediu, e não o recuo próprio"


def test_retry_after_do_padrao_http_tambem_vale(resposta_falsa):
    esperas = []
    resposta_falsa(_erro(503, cabecalhos={"Retry-After": "3"}), {"ok": True})

    transporte.pedir("https://fonte.exemplo/x", dormir=esperas.append)

    assert esperas == [3.0]


def test_espera_pedida_absurda_e_limitada_pelo_teto(resposta_falsa):
    """Uma fonte pedindo uma hora não pode segurar a janela de carga inteira."""
    esperas = []
    resposta_falsa(_erro(429, {"retry_in_seconds": 3600}), {"ok": True})

    transporte.pedir("https://fonte.exemplo/x", dormir=esperas.append)

    assert esperas == [transporte.RECUO_MAXIMO]


# ── O que repete e o que não ────────────────────────────────────────


def test_post_repete_porque_no_monday_post_e_leitura(resposta_falsa):
    """A diferença que separa este transporte do outro.

    O cliente do iConnect recusa repetir `POST` — corretamente, porque o único
    `POST` dele consome um código de uso único. A API do monday é GraphQL: toda
    LEITURA é um `POST`, e não repetir tornaria a carga refém do primeiro 502.
    """
    chamadas = resposta_falsa(_erro(502), {"data": {}})

    transporte.pedir("https://api.monday.com/v2", metodo="POST", dormir=lambda _: None)

    assert len(chamadas) == 2


@pytest.mark.parametrize("codigo", [400, 401, 403, 404, 422])
def test_nao_insiste_no_que_nao_vai_mudar(resposta_falsa, codigo):
    """`4xx` de permissão ou payload não melhora com repetição: insistir só
    demora mais para dar o mesmo erro, três vezes."""
    chamadas = resposta_falsa(_erro(codigo))

    with pytest.raises(transporte.TransporteError):
        transporte.pedir("https://fonte.exemplo/x", dormir=lambda _: None)

    assert len(chamadas) == 1


def test_desiste_depois_das_tentativas(resposta_falsa):
    chamadas = resposta_falsa(_erro(503))

    with pytest.raises(transporte.TransporteError):
        transporte.pedir("https://fonte.exemplo/x", dormir=lambda _: None)

    assert len(chamadas) == transporte.TENTATIVAS


def test_resposta_que_nao_e_json_vira_erro_com_mensagem(resposta_falsa, monkeypatch):
    """Uma página de login HTML no lugar do JSON é o sintoma nº 1 de credencial
    vencida — e "Expecting value: line 1 column 1" não conta isso a ninguém."""

    def _html(requisicao, timeout=None):
        return _Resposta(b"<html>faca login</html>")

    monkeypatch.setattr(transporte.urllib.request, "urlopen", _html)

    with pytest.raises(transporte.TransporteError, match="não é JSON"):
        transporte.pedir("https://fonte.exemplo/x")


def test_lista_na_raiz_e_embrulhada_em_vez_de_estourar(resposta_falsa):
    """API que devolve lista na raiz existe. Embrulhar é melhor que levantar:
    o conector sabe o que fazer com `{"lista": [...]}`."""
    resposta_falsa([{"id": 1}])

    assert transporte.pedir("https://fonte.exemplo/x") == {"lista": [{"id": 1}]}


# ── Forma do corpo ──────────────────────────────────────────────────


def test_forma_form_e_o_que_o_sankhya_exige(resposta_falsa):
    """O `/authenticate` do Sankhya é `x-www-form-urlencoded`, não JSON.

    Mandar JSON ali devolve 400 — e sem este caminho o conector do Sankhya
    simplesmente não autentica.
    """
    chamadas = resposta_falsa({"access_token": "x"})

    transporte.pedir(
        "https://api.sankhya.com.br/authenticate",
        metodo="POST",
        corpo={"grant_type": "client_credentials"},
        forma="form",
    )

    requisicao = chamadas[0]
    assert requisicao.headers["Content-type"] == "application/x-www-form-urlencoded"
    assert requisicao.data == b"grant_type=client_credentials"


# ── A disciplina compartilhada ──────────────────────────────────────


@pytest.fixture
def trilha():
    """Captura o que os dois transportes registram.

    Handler direto nos loggers porque `caplog` não pega logger com
    `propagate: False` — e o de segurança deste projeto tem.
    """
    registros = []

    class _Coletor(logging.Handler):
        def emit(self, registro):
            registros.append(self.format(registro))

    coletor = _Coletor()
    coletor.setFormatter(logging.Formatter("%(message)s"))
    alvos = [logging.getLogger("cargas"), logging.getLogger("workspace.integracoes.cliente")]
    for logger in alvos:
        logger.addHandler(coletor)
        logger.setLevel(logging.DEBUG)
    yield registros
    for logger in alvos:
        logger.removeHandler(coletor)


def test_nenhum_transporte_registra_credencial(trilha, monkeypatch, settings):
    """O teste que os dois transportes dividem, no lugar de dividirem código.

    Exercita `cargas.transporte` e `workspace.integracoes.cliente` com um
    segredo reconhecível no cabeçalho e afirma que ele não aparece em log
    nenhum. A tela de fontes é visível à diretoria, e `erro_resumo` sai daqui.
    """
    from workspace.integracoes import cliente

    def _explode(requisicao, timeout=None):
        raise urllib.error.HTTPError(requisicao.full_url, 500, "erro", {}, io.BytesIO(b"{}"))

    monkeypatch.setattr(transporte.urllib.request, "urlopen", _explode)
    monkeypatch.setattr(cliente.urllib.request, "urlopen", _explode)
    monkeypatch.setattr(cliente.time, "sleep", lambda *_: None)
    settings.ICONNECT_API_URL = "https://iconnect.exemplo"

    with pytest.raises(transporte.TransporteError):
        transporte.pedir(
            "https://fonte.exemplo/x",
            cabecalhos={"Authorization": SEGREDO, "X-Token": SEGREDO},
            dormir=lambda _: None,
        )
    with pytest.raises(cliente.IntegracaoError):
        cliente.chamar("/api/v1/tickets/", token=SEGREDO)

    assert trilha, "os dois transportes precisam registrar ALGUMA coisa"
    for linha in trilha:
        assert SEGREDO not in linha, f"credencial no log: {linha}"


def test_o_erro_que_vai_para_a_tela_nao_carrega_a_url_inteira(resposta_falsa):
    """`erro_resumo` aparece na tela de fontes.

    Uma URL com token no querystring viraria vazamento numa tela que ninguém
    audita — por isso a mensagem cita host e caminho, e nunca a URL crua.
    """
    resposta_falsa(_erro(404))

    with pytest.raises(transporte.TransporteError) as erro:
        transporte.pedir(
            "https://fonte.exemplo/dados?access_token=" + SEGREDO,
            dormir=lambda _: None,
        )

    assert SEGREDO not in str(erro.value)
    assert "fonte.exemplo/dados" in str(erro.value)
