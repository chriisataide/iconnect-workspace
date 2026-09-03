"""O comando que diz o que falta para cada fonte entrar no ar.

O que ele protege, em ordem de importância:

1. **Ele nunca imprime credencial.** A saída deste comando vai ser colada num
   chamado — é literalmente para isso que ele existe. Segredo mascarado em log é
   segredo em log com uma falsa sensação de cuidado: quatro caracteres de um
   token bastam para confirmar um palpite.
2. **Ele separa "não configurei" de "a credencial foi recusada".** Sem essa
   separação, a única forma de descobrir era rodar uma carga e ler o motivo da
   falha — que mistura as duas com "o endpoint mudou".
3. **Sem `--testar`, ele não toca a rede.** Diagnóstico que faz chamada por
   padrão é diagnóstico que ninguém roda em produção.
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command

from cargas.conectores import registro
from cargas.models import Fonte, FonteDados

pytestmark = pytest.mark.django_db

#: Valores que NÃO podem aparecer na saída. Escolhidos para parecerem
#: credenciais de verdade — um teste com "x" passaria por acidente.
SEGREDO_MONDAY = "eyJhbGciOiJIUzI1NiJ9.SEGREDO-DO-MONDAY.assinatura"
SEGREDO_SANKHYA = "sk-live-9f2b7c41d8e6a05b3f19"


@pytest.fixture
def fontes(db):
    call_command("semear_fontes", "--aplicar", verbosity=0)
    return {f.chave: f for f in FonteDados.objects.all()}


def _saida(*args, **opcoes) -> str:
    fluxo = StringIO()
    call_command("conferir_integracoes", *args, stdout=fluxo, stderr=fluxo, **opcoes)
    return fluxo.getvalue()


# ── 1. Nunca imprime credencial ─────────────────────────────────────


def test_o_comando_nunca_imprime_credencial(fontes, settings):
    """O teste que mais importa: esta saída vai para um chamado."""
    settings.MONDAY_TOKEN = SEGREDO_MONDAY
    settings.MONDAY_BOARDS = {"projetos": 123456}
    settings.SANKHYA_BASE_URL = "https://api.sankhya.com.br"
    settings.SANKHYA_CLIENT_ID = "cliente-de-teste"
    settings.SANKHYA_CLIENT_SECRET = SEGREDO_SANKHYA
    settings.SANKHYA_TOKEN = SEGREDO_SANKHYA

    texto = _saida()

    assert SEGREDO_MONDAY not in texto
    assert SEGREDO_SANKHYA not in texto
    # Nem um pedaço: quatro caracteres de um token confirmam um palpite.
    assert SEGREDO_MONDAY[:8] not in texto
    assert SEGREDO_SANKHYA[:8] not in texto
    assert "definida" in texto, "ele diz que existe, sem dizer o quê"


def test_o_que_falta_aparece_com_o_nome_da_variavel_e_onde_conseguir(fontes):
    """"Falta credencial" manda a pessoa abrir um chamado. O nome da variável e
    a origem dela fazem ela resolver."""
    texto = _saida()

    assert "SANKHYA_TOKEN: FALTA" in texto
    assert "Configurações Gateway" in texto
    assert "NÃO é o client_secret" in texto, "é onde a maioria trava"
    assert "usuário de SERVIÇO" in texto


# ── 2. Separa não configurado de recusado ───────────────────────────


def test_sem_configuracao_ele_diz_que_e_estado_normal(fontes):
    """Fonte não configurada não é falha: a carga registra isso e o carimbo diz
    "sem registro de carga". Um comando que gritasse aqui ensinaria a ignorá-lo."""
    texto = _saida()

    assert "0 de 3 fonte(s) configurada(s)" in texto
    assert "estado NORMAL" in texto


def test_com_configuracao_ele_aponta_o_proximo_passo(fontes, settings):
    settings.MONDAY_TOKEN = SEGREDO_MONDAY
    settings.MONDAY_BOARDS = {"projetos": 123456}

    texto = _saida("monday")

    assert "o conector está disponível" in texto
    assert "--testar" in texto, "diz como conferir o lado de lá"


def test_o_testar_relata_a_recusa_sem_derrubar_o_comando(fontes, settings, monkeypatch):
    """Descobrir que o token está errado não deveria custar uma varredura de
    doze meses — nem uma exceção não tratada."""
    settings.MONDAY_TOKEN = SEGREDO_MONDAY
    settings.MONDAY_BOARDS = {"projetos": 123456}

    conector = registro.conector_de(Fonte.MONDAY)

    def recusa(janela):
        raise PermissionError("401 Unauthorized")
        yield  # pragma: no cover - `coletar` é gerador

    monkeypatch.setattr(conector, "coletar", recusa)

    texto = _saida("monday", "--testar")

    assert "o lado de lá recusou" in texto
    assert "PermissionError" in texto
    assert "1 de 1" not in texto


def test_o_testar_confirma_quando_o_lado_de_la_responde(fontes, settings, monkeypatch):
    settings.MONDAY_TOKEN = SEGREDO_MONDAY
    settings.MONDAY_BOARDS = {"projetos": 123456}

    conector = registro.conector_de(Fonte.MONDAY)
    monkeypatch.setattr(conector, "coletar", lambda janela: iter([{"id": "1"}]))

    texto = _saida("monday", "--testar")

    assert "o lado de lá respondeu" in texto
    assert "1 de 1 fonte(s) configurada(s)" in texto


def test_a_mensagem_de_erro_nao_vaza_a_url_com_token(fontes, settings, monkeypatch):
    """Alguns clientes HTTP põem a URL — com token na query — no `repr` da
    exceção. O comando imprime o nome do tipo e a mensagem, nunca o `repr`."""
    settings.MONDAY_TOKEN = SEGREDO_MONDAY
    settings.MONDAY_BOARDS = {"projetos": 1}

    class ErroComUrl(Exception):
        def __repr__(self):
            return f"ErroComUrl('https://api.monday.com/?token={SEGREDO_MONDAY}')"

        def __str__(self):
            return "credencial recusada"

    conector = registro.conector_de(Fonte.MONDAY)

    def estoura(janela):
        raise ErroComUrl()
        yield  # pragma: no cover

    monkeypatch.setattr(conector, "coletar", estoura)

    texto = _saida("monday", "--testar")

    assert SEGREDO_MONDAY not in texto
    assert "credencial recusada" in texto


# ── 3. Sem --testar não toca a rede ─────────────────────────────────


def test_sem_testar_o_comando_nao_chama_ninguem(fontes, settings, monkeypatch):
    """Diagnóstico que faz chamada por padrão é diagnóstico que ninguém roda em
    produção."""
    settings.MONDAY_TOKEN = SEGREDO_MONDAY
    settings.MONDAY_BOARDS = {"projetos": 1}

    chamou = []
    conector = registro.conector_de(Fonte.MONDAY)
    monkeypatch.setattr(
        conector, "coletar", lambda janela: chamou.append(1) or iter([])
    )

    _saida("monday")

    assert chamou == []


# ── As bordas ───────────────────────────────────────────────────────


def test_sem_semear_fontes_ele_diz_qual_comando_rodar(db):
    """Sem registro de fonte o carregador RECUSA começar, de propósito: carga
    sem procedência é dado sem procedência."""
    texto = _saida()

    assert "sem registro em FonteDados" in texto
    assert "semear_fontes --aplicar" in texto


def test_fonte_desativada_a_mao_e_anunciada(fontes):
    """Desativar é o freio de quem opera, quase sempre no meio de um incidente.
    O comando avisa que o freio está puxado, em vez de dizer que falta
    configurar."""
    FonteDados.objects.filter(chave=Fonte.MONDAY).update(ativa=False)

    texto = _saida("monday")

    assert "DESATIVADA" in texto
    assert "nunca reativa sozinha" in texto


def test_chave_desconhecida_lista_as_conhecidas(fontes):
    texto = _saida("sap")

    assert "Fonte desconhecida" in texto
    assert "sankhya" in texto


def test_uma_fonte_por_vez(fontes):
    texto = _saida("sankhya")

    assert "── sankhya ──" in texto
    assert "── monday ──" not in texto


def test_a_carga_por_arquivo_nao_entra_na_conferencia(fontes):
    """O conector de CSV não tem credencial: ele lê um diretório. Cobrá-lo aqui
    produziria uma linha "FALTA" para algo que ninguém precisa preencher."""
    texto = _saida()

    assert "── csv ──" not in texto


def test_fonte_sem_conector_registrado_e_denunciada(fontes, monkeypatch):
    """Acontece quando alguém registra a fonte no banco e esquece o código — e o
    sintoma sem esta linha seria "a carga não roda", sem dizer por quê."""
    monkeypatch.setattr(registro, "conector_de", lambda chave: None)

    texto = _saida("monday")

    assert "nenhum conector registrado" in texto
