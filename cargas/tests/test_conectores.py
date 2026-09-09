"""Os quatro conectores — cada um contra a forma documentada da sua API.

Nenhum toca a rede. A fixture é a resposta GRAVADA, e `normalizar` é função pura
em cima dela: é exatamente por isso que `coletar` e `normalizar` são métodos
separados no protocolo.

As respostas daqui vieram da documentação vigente de cada fonte, conferida em
01/09/2026 — não de memória e não de exemplo antigo. Onde a doc não responde
(quais views o Sankhya da ADB expõe, quais ids de board a conta tem), o conector
declara o mapa em `settings` e falha alto quando ele falta.
"""

from __future__ import annotations

import io
import json
from datetime import date
from decimal import Decimal

import pytest

from cargas import transporte
from cargas.conectores import Janela
from cargas.conectores.csv import ConectorCSV
from cargas.conectores.monday import ConectorMonday
from cargas.conectores.platform import ConectorPlatform
from cargas.conectores.sankhya import ConectorSankhya


class _Resposta(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def rede(monkeypatch):
    """Uma fila de respostas gravadas, na ordem em que a API as devolveria."""

    def _preparar(*respostas):
        pedidos = []

        def _falso(requisicao, timeout=None):
            pedidos.append(requisicao)
            corpo = respostas[min(len(pedidos) - 1, len(respostas) - 1)]
            return _Resposta(json.dumps(corpo).encode())

        monkeypatch.setattr(transporte.urllib.request, "urlopen", _falso)
        return pedidos

    return _preparar


# ══ CSV ═════════════════════════════════════════════════════════════


@pytest.fixture
def diretorio_csv(tmp_path):
    def _escrever(entidade: str, cabecalho: str, *linhas: str):
        (tmp_path / f"{entidade}.csv").write_text(
            "\n".join([cabecalho, *linhas]), encoding="utf-8"
        )
        return tmp_path

    return _escrever


def test_csv_le_e_tipa(diretorio_csv):
    """String no `DecimalField` funciona por acidente e quebra na comparação de
    hash: `"12000.50" != Decimal("12000.50")` faria toda carga achar que tudo
    mudou, e `ignorados` seria sempre zero."""
    caminho = diretorio_csv(
        "contrato",
        "chave_externa,codigo,nome_cliente,servico,centro_custo,valor_mensal,fim_vigencia",
        "ext-1,C-100,Cliente Fictício,monitoramento,1042,12000.50,2026-12-31",
    )
    conector = ConectorCSV(caminho)

    (registro,) = list(conector.normalizar(conector.coletar(Janela())))

    assert registro.entidade == "contrato"
    assert registro.chave_externa == "ext-1"
    assert registro.dados["valor_mensal"] == Decimal("12000.50")
    assert registro.dados["fim_vigencia"] == date(2026, 12, 31)


def test_csv_aceita_data_brasileira_e_recusa_ambiguidade(diretorio_csv):
    """`03/04/2026` é lido como dia/mês, e nenhum outro formato é tentado.

    Adivinhar entre dia/mês e mês/dia é como um relatório de abril vira um de
    março sem ninguém notar.
    """
    caminho = diretorio_csv(
        "contrato",
        "chave_externa,codigo,fim_vigencia",
        "ext-1,C-1,03/04/2026",
        "ext-2,C-2,2026-04-03",
        "ext-3,C-3,April 3 2026",
    )
    conector = ConectorCSV(caminho)

    datas = [r.dados["fim_vigencia"] for r in conector.normalizar(conector.coletar(Janela()))]

    assert datas == [date(2026, 4, 3), date(2026, 4, 3), None]


def test_csv_sem_chave_externa_nao_vira_registro(diretorio_csv):
    caminho = diretorio_csv(
        "contrato", "chave_externa,codigo", ",C-1", "ext-2,C-2"
    )
    conector = ConectorCSV(caminho)

    codigos = [r.dados["codigo"] for r in conector.normalizar(conector.coletar(Janela()))]

    assert codigos == ["C-2"]


def test_csv_ignora_entidade_sem_arquivo(diretorio_csv):
    """Uma carga de contratos não tem por que reclamar da ausência de
    `avaliacao.csv` — quem manda o que existe é quem preencheu."""
    caminho = diretorio_csv("contrato", "chave_externa,codigo", "ext-1,C-1")

    assert len(list(ConectorCSV(caminho).coletar(Janela()))) == 1


def test_csv_sem_diretorio_nao_esta_disponivel(tmp_path):
    assert ConectorCSV(tmp_path / "nao-existe").disponivel() is False


# ══ monday ══════════════════════════════════════════════════════════


def _coluna(id_, tipo, **extra):
    return {"id": id_, "type": tipo, "text": extra.pop("text", ""), "value": None, **extra}


BOARDS_MONDAY = {
    "projeto": {
        "board": 4412,
        "colunas": {
            "situacao": "status",
            "responsavel": "person",
            "prazo": "date4",
            "percentual_concluido": "numeros",
            "contrato": "conexao_contrato",
            "cliente": "espelho_cliente",
        },
    }
}


def test_monday_manda_a_versao_da_api_e_o_token(rede, settings):
    """Sem o cabeçalho de versão, a conta cai na versão padrão do dia — e o dia
    em que o monday promover a release candidate, a carga muda de comportamento
    sozinha, num domingo."""
    settings.MONDAY_TOKEN = "tok"
    settings.MONDAY_BOARDS = BOARDS_MONDAY
    pedidos = rede({"data": {"boards": [{"items_page": {"cursor": None, "items": []}}]}})

    list(ConectorMonday().coletar(Janela()))

    assert pedidos[0].headers["Api-version"] == "2026-07"
    assert pedidos[0].headers["Authorization"] == "tok"
    assert pedidos[0].get_method() == "POST"


def test_monday_status_vem_do_rotulo_e_nao_do_texto(rede, settings):
    """Quem renomeia um rótulo na tela muda o `text` de todo o histórico.

    `label` é o campo tipado do `StatusValue`, e é o que a API garante.
    """
    settings.MONDAY_TOKEN = "tok"
    settings.MONDAY_BOARDS = BOARDS_MONDAY
    item = {
        "id": "9001",
        "name": "Migração de CFTV",
        "updated_at": "2026-08-30T12:00:00Z",
        "column_values": [_coluna("status", "status", label="Em andamento", text="lixo")],
    }
    rede({"data": {"boards": [{"items_page": {"cursor": None, "items": [item]}}]}})
    conector = ConectorMonday()

    (registro,) = list(conector.normalizar(conector.coletar(Janela())))

    assert registro.dados["situacao"] == "em_andamento"
    assert registro.chave_externa == "9001"
    assert registro.dados["codigo"] == "MON-9001"


def test_monday_board_relation_traz_id_e_nao_texto(rede, settings):
    settings.MONDAY_TOKEN = "tok"
    settings.MONDAY_BOARDS = BOARDS_MONDAY
    item = {
        "id": "9001",
        "name": "X",
        "column_values": [
            _coluna("conexao_contrato", "board_relation", linked_item_ids=["7788"]),
        ],
    }
    rede({"data": {"boards": [{"items_page": {"cursor": None, "items": [item]}}]}})
    conector = ConectorMonday()

    (registro,) = list(conector.normalizar(conector.coletar(Janela())))

    assert registro.dados["contrato"] == "7788"


def test_monday_ignora_mirror(rede, settings):
    """Mirror às vezes vem VAZIO na API mesmo aparecendo na tela.

    Um campo que existe na tela e não na resposta zeraria sozinho na carga
    seguinte — pior que um campo ausente, porque parece dado.
    """
    settings.MONDAY_TOKEN = "tok"
    settings.MONDAY_BOARDS = BOARDS_MONDAY
    item = {
        "id": "9001",
        "name": "X",
        "column_values": [_coluna("espelho_cliente", "mirror", text="")],
    }
    rede({"data": {"boards": [{"items_page": {"cursor": None, "items": [item]}}]}})
    conector = ConectorMonday()

    (registro,) = list(conector.normalizar(conector.coletar(Janela())))

    assert "cliente" not in registro.dados


def test_monday_pagina_por_cursor(rede, settings):
    """A segunda página vem de `next_items_page`, e não de repetir `items_page`
    dentro de `boards` — que multiplica o custo de complexidade da consulta."""
    settings.MONDAY_TOKEN = "tok"
    settings.MONDAY_BOARDS = BOARDS_MONDAY
    primeira = {
        "data": {"boards": [{"items_page": {"cursor": "abc", "items": [{"id": "1", "name": "A"}]}}]}
    }
    segunda = {"data": {"next_items_page": {"cursor": None, "items": [{"id": "2", "name": "B"}]}}}
    pedidos = rede(primeira, segunda)

    itens = list(ConectorMonday().coletar(Janela()))

    assert [i["id"] for i in itens] == ["1", "2"]
    assert b"next_items_page" in pedidos[1].data


def test_monday_board_invisivel_nao_vira_sucesso_vazio(rede, settings):
    """Zero projetos é indistinguível de "a empresa não tem projeto nenhum".

    Falhar alto é o que impede o espelho de esvaziar em silêncio quando alguém
    revoga o acesso do token.
    """
    settings.MONDAY_TOKEN = "tok"
    settings.MONDAY_BOARDS = BOARDS_MONDAY
    rede({"data": {"boards": []}})

    with pytest.raises(transporte.TransporteError, match="não existe ou não é visível"):
        list(ConectorMonday().coletar(Janela()))


def test_monday_sem_mapa_de_board_diz_o_que_falta(settings):
    settings.MONDAY_TOKEN = "tok"
    settings.MONDAY_BOARDS = None

    with pytest.raises(transporte.FonteNaoConfigurada, match="MONDAY_BOARDS"):
        list(ConectorMonday().coletar(Janela()))


# ══ Sankhya ═════════════════════════════════════════════════════════


CONSULTA_TESTE = {
    "competencia": {
        "rootEntity": "VW_RESULTADO_CC",
        "campos": ("CHAVE", "CODCENCUS", "ANO", "MES", "RECEITABRUTA", "EBITDA"),
        "campo_data": "DTREF",
    }
}


@pytest.fixture
def sankhya_configurado(settings):
    settings.SANKHYA_BASE_URL = "https://api.sankhya.com.br"
    settings.SANKHYA_CLIENT_ID = "cid"
    settings.SANKHYA_CLIENT_SECRET = "seg"
    settings.SANKHYA_TOKEN = "xtok"
    settings.SANKHYA_CONSULTAS = CONSULTA_TESTE
    return settings


def _linha(*valores):
    """A resposta do `loadRecords` é POSICIONAL — `f0`, `f1`… — e cada valor vem
    embrulhado em `{"$": ...}`, resquício do XML que sobreviveu ao JSON."""
    return {f"f{i}": {"$": v} for i, v in enumerate(valores)}


def test_sankhya_autentica_por_client_credentials(rede, sankhya_configurado):
    """O fluxo vigente é OAuth2 no Gateway, e NÃO o `username`/`password` em
    cabeçalho que ainda circula em exemplos antigos."""
    pedidos = rede(
        {"access_token": "jwt", "expires_in": 300},
        {"responseBody": {"entities": {"hasMoreResult": "false"}}},
    )

    list(ConectorSankhya().coletar(Janela()))

    login = pedidos[0]
    assert login.full_url.endswith("/authenticate")
    assert login.headers["X-token"] == "xtok"
    assert b"grant_type=client_credentials" in login.data
    assert pedidos[1].headers["Authorization"] == "Bearer jwt"


def test_sankhya_le_a_resposta_posicional(rede, sankhya_configurado):
    """Desencontrar `campos` do `fieldset` desloca todas as colunas e grava
    receita na coluna de imposto, sem erro nenhum — por isso as duas listas
    saem da MESMA tupla."""
    rede(
        {"access_token": "jwt", "expires_in": 300},
        {
            "responseBody": {
                "entities": {
                    "hasMoreResult": "false",
                    "entity": _linha("K1", "1042", "2026", "8", "150000.00", "22000.00"),
                }
            }
        },
    )
    conector = ConectorSankhya()

    (registro,) = list(conector.normalizar(conector.coletar(Janela())))

    assert registro.chave_externa == "K1"
    assert registro.dados["centro_custo"] == "1042"
    assert registro.dados["ano"] == 2026 and registro.dados["mes"] == 8
    assert registro.dados["receita_bruta"] == Decimal("150000.00")
    assert registro.dados["ebitda"] == Decimal("22000.00")


def test_sankhya_trata_registro_unico_como_lista(rede, sankhya_configurado):
    """O Sankhya devolve objeto quando há UM registro e lista quando há vários.

    Sem isto, a carga de uma competência só iteraria as chaves do dicionário e
    produziria lixo — e só na virada do mês, quando ninguém está olhando.
    """
    rede(
        {"access_token": "jwt", "expires_in": 300},
        {
            "responseBody": {
                "entities": {
                    "hasMoreResult": "false",
                    "entity": [_linha("K1", "1042", "2026", "8", "1", "1"),
                               _linha("K2", "1043", "2026", "8", "2", "2")],
                }
            }
        },
    )

    assert len(list(ConectorSankhya().coletar(Janela()))) == 2


def test_sankhya_pagina_por_offsetpage(rede, sankhya_configurado):
    rede(
        {"access_token": "jwt", "expires_in": 300},
        {
            "responseBody": {
                "entities": {
                    "hasMoreResult": "true",
                    "entity": _linha("K1", "1042", "2026", "8", "1", "1"),
                }
            }
        },
        {"responseBody": {"entities": {"hasMoreResult": "false"}}},
    )

    itens = list(ConectorSankhya().coletar(Janela()))

    assert len(itens) == 1


def test_sankhya_filtra_por_janela_com_parametro_e_nao_interpolacao(
    rede, sankhya_configurado
):
    """`criteria` do Sankhya é SQL. Placeholder `?` com `parameter`, sempre —
    é a mesma regra de SQL parametrizado, pelo mesmo motivo."""
    pedidos = rede(
        {"access_token": "jwt", "expires_in": 300},
        {"responseBody": {"entities": {"hasMoreResult": "false"}}},
    )

    list(ConectorSankhya().coletar(Janela(de=date(2026, 8, 1), ate=date(2026, 8, 31))))

    corpo = json.loads(pedidos[1].data)
    criteria = corpo["requestBody"]["dataSet"]["criteria"]
    assert criteria["expression"]["$"].count("?") == 2
    assert [p["$"] for p in criteria["parameter"]] == ["01/08/2026", "31/08/2026"]


def test_sankhya_sem_credencial_diz_o_que_falta(settings):
    settings.SANKHYA_BASE_URL = ""
    conector = ConectorSankhya()

    assert conector.disponivel() is False
    with pytest.raises(transporte.FonteNaoConfigurada, match="SANKHYA_"):
        conector._token_valido()


def test_sankhya_sem_access_token_nao_vaza_o_corpo_da_resposta(rede, sankhya_configurado):
    """O corpo de uma resposta de autenticação é o último lugar de onde copiar
    texto para uma tela."""
    rede({"erro": "credencial invalida", "detalhe": "segredo_no_corpo"})

    with pytest.raises(transporte.TransporteError) as erro:
        ConectorSankhya()._token_valido()

    assert "segredo_no_corpo" not in str(erro.value)


# ══ Platform ════════════════════════════════════════════════════════


@pytest.fixture
def platform_configurado(settings):
    settings.ICONNECT_API_URL = "https://iconnect.exemplo"
    settings.WORKSPACE_SHARED_SECRET = "segredo"
    settings.PLATFORM_ROTAS = {"contrato": "/api/v1/integracao/contratos/"}
    return settings


def test_platform_usa_o_segredo_que_ja_existe(rede, platform_configurado):
    """Uma segunda credencial para o mesmo par de sistemas seria uma segunda
    coisa para rotacionar — e a segunda é sempre a que fica para trás."""
    pedidos = rede({"results": [], "next": None})

    list(ConectorPlatform().coletar(Janela()))

    assert pedidos[0].headers["X-workspace-secret"] == "segredo"


def test_platform_nao_traz_dado_pessoal_mesmo_que_a_api_mande(rede, platform_configurado):
    """Lista explícita de recusados, e não confiança no outro lado.

    O dia em que o Platform acrescentar `cpf` ao payload, ele não vira coluna do
    espelho por acidente — que é como grade com CPF nasce.
    """
    rede(
        {
            "results": [
                {
                    "id": "1", "codigo": "C-1", "cliente": "Cliente Fictício",
                    "cpf": "000.000.000-00", "email": "alguem@cliente.exemplo",
                    "respondente_nome": "Fulano",
                }
            ],
            "next": None,
        }
    )
    conector = ConectorPlatform()

    (registro,) = list(conector.normalizar(conector.coletar(Janela())))

    assert registro.dados["nome_cliente"] == "Cliente Fictício"
    for proibido in ("cpf", "email", "respondente_nome"):
        assert proibido not in registro.dados


def test_platform_recusa_pagina_seguinte_para_outro_host(rede, platform_configurado):
    """Seguir a URL que o outro lado mandar é seguir um redirecionamento cego —
    e mandar o segredo compartilhado junto."""
    rede({"results": [], "next": "https://atacante.exemplo/roubar/"})

    with pytest.raises(transporte.TransporteError, match="aponta para fora"):
        list(ConectorPlatform().coletar(Janela()))


def test_platform_sem_configuracao_diz_o_que_falta(settings):
    settings.ICONNECT_API_URL = ""
    settings.WORKSPACE_SHARED_SECRET = ""

    with pytest.raises(transporte.FonteNaoConfigurada, match="ICONNECT_API_URL"):
        list(ConectorPlatform().coletar(Janela()))
