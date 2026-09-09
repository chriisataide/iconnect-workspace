"""A conversão de tipos — onde uma carga silenciosamente errada nasce.

Nenhum destes testes é sobre rede. São sobre o momento em que um texto vira um
número, uma data ou um nulo — e é aí que mora o defeito que ninguém vê: uma data
lida ao contrário não estoura, ela só põe o resultado de abril em março.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cargas.conectores import base
from cargas.conectores.csv import ConectorCSV, _converter_valor, _IGNORAR
from cargas.conectores.platform import ConectorPlatform, _tipar
from cargas.conectores.registro import limpar, registrar, todos


# ── CSV ─────────────────────────────────────────────────────────────


def test_coluna_vazia_de_data_vira_none_e_nao_some(tmp_path):
    """`fim_vigencia` vazio significa "sem fim de vigência", e isso É um valor.

    Se a coluna sumisse, a linha manteria a vigência antiga do espelho — e um
    contrato renovado por prazo indeterminado continuaria vencendo em dezembro.
    """
    assert _converter_valor("fim_vigencia", "") is None


def test_coluna_vazia_de_orcado_vira_none_e_nao_zero():
    """"Sem orçado" e "orçado zero" produzem leituras opostas na faixa
    financeira: a primeira é conciliação a resolver, a segunda é teto de fato."""
    assert _converter_valor("receita_orcada", "") is None
    assert _converter_valor("custo_orcado", "") is None


def test_coluna_vazia_comum_nao_entra():
    """Inventar `""` para um campo que a planilha não preencheu apagaria o que
    outra fonte gravou. Ausente é ausente."""
    assert _converter_valor("nome_cliente", "") is _IGNORAR


def test_numero_com_virgula_decimal(tmp_path):
    """Planilha brasileira escreve `1.200,50`. O separador de milhar é problema
    de quem exporta; a vírgula decimal, não — ela chega o tempo todo."""
    assert _converter_valor("valor_mensal", "1200,50") == Decimal("1200.50")
    assert _converter_valor("ano", "2026") == 2026
    assert _converter_valor("percentual_concluido", "45,0") == 45


def test_numero_impossivel_nao_derruba_a_linha_inteira():
    """Uma célula com "n/a" recusa a COLUNA, não o registro.

    Recusar o registro perderia as outras quinze colunas boas por causa de uma.
    """
    assert _converter_valor("valor_mensal", "n/a") is _IGNORAR
    assert _converter_valor("ano", "dois mil") is _IGNORAR


@pytest.mark.parametrize("texto", ["1", "sim", "S", "true", "Verdadeiro", "yes"])
def test_booleano_aceita_o_que_gente_escreve(texto):
    assert _converter_valor("bloqueado", texto) is True


@pytest.mark.parametrize("texto", ["0", "nao", "", "qualquer coisa"])
def test_booleano_so_e_verdadeiro_no_que_esta_na_lista(texto):
    """Lista de verdadeiros, e não lista de falsos.

    Com lista de falsos, uma célula com lixo viraria `True` — e um projeto
    apareceria bloqueado por causa de um erro de digitação.
    """
    assert _converter_valor("bloqueado", texto) is not True


def test_referencia_a_registro_que_ainda_nao_chegou_vira_none(db):
    """Um marco cujo projeto vem no arquivo seguinte é caso normal.

    Rejeitar aqui obrigaria a ordenar os arquivos, e a ordem de um diretório não
    é contrato. O carregador recusa depois, se a chave de negócio exigir — e aí
    a rejeição diz o que falta.
    """
    assert _converter_valor("contrato", "C-QUE-NAO-EXISTE") is None


def test_arquivo_com_bom_do_excel_e_lido(tmp_path):
    """O Excel salva CSV com BOM, e o BOM entra no NOME da primeira coluna.

    Sem `utf-8-sig`, `chave_externa` vira `\\ufeffchave_externa`, nenhuma linha
    tem chave, e o arquivo inteiro é rejeitado com um motivo que não ajuda.
    """
    (tmp_path / "contrato.csv").write_text(
        "chave_externa,codigo\next-1,C-1\n", encoding="utf-8-sig"
    )
    conector = ConectorCSV(tmp_path)

    (registro,) = list(conector.normalizar(conector.coletar(base.Janela())))

    assert registro.chave_externa == "ext-1"


# ── Platform ────────────────────────────────────────────────────────


def test_platform_tipa_data_decimal_inteiro_e_booleano():
    assert _tipar("data", "2026-08-15T10:00:00Z") == date(2026, 8, 15)
    assert _tipar("valor_mensal", "1200.50") == Decimal("1200.50")
    assert _tipar("nota", "9") == 9
    assert _tipar("tratativa_aberta", True) is True
    assert _tipar("comentario", "  texto  ") == "texto"


@pytest.mark.parametrize(
    ("campo", "bruto"),
    [("data", "15/08/2026"), ("valor_mensal", "muito"), ("nota", "nove")],
)
def test_platform_recusa_o_que_nao_consegue_converter(campo, bruto):
    """`None` e não um chute. Um valor inventado num campo de dinheiro é pior
    que um campo vazio, porque ele entra na soma."""
    assert _tipar(campo, bruto) is None


def test_platform_avaliacao_sem_contrato_nao_vira_registro(db, settings):
    """Avaliação órfã não aparece em tela nenhuma e some do relatório.

    Gravá-la faria a contagem de detratores incluir gente que a faixa de
    satisfação nunca mostra — e o total pararia de bater com a lista.
    """
    settings.ICONNECT_API_URL = "https://iconnect.exemplo"
    settings.WORKSPACE_SHARED_SECRET = "s"
    conector = ConectorPlatform()

    item = {
        "_entidade": "avaliacao", "id": "av-1", "contrato": "C-INEXISTENTE",
        "data": "2026-08-10", "nota": 3, "classificacao": "detrator",
    }

    assert list(conector.normalizar([item])) == []


def test_platform_avaliacao_liga_no_contrato_que_existe(db, settings):
    from resultados.models import Contrato, Fonte

    settings.ICONNECT_API_URL = "https://iconnect.exemplo"
    settings.WORKSPACE_SHARED_SECRET = "s"
    contrato = Contrato.objects.create(
        fonte=Fonte.PLATFORM, chave_externa="c1", codigo="C-1",
        nome_cliente="Cliente Fictício", servico="monitoramento", centro_custo="1042",
    )
    item = {
        "_entidade": "avaliacao", "id": "av-1", "contrato": "C-1",
        "data": "2026-08-10", "nota": 3, "classificacao": "detrator",
        "comentario": "Demorou", "tratativa_aberta": False,
    }

    (registro,) = list(ConectorPlatform().normalizar([item]))

    assert registro.dados["contrato"] == contrato
    assert registro.dados["nota"] == 3


def test_platform_entidade_fora_da_traducao_e_ignorada(db):
    assert list(ConectorPlatform().normalizar([{"_entidade": "ocorrencia", "id": "1"}])) == []


def test_platform_sem_id_nem_codigo_nao_vira_registro(db):
    """Sem identidade na origem não há idempotência."""
    assert list(ConectorPlatform().normalizar([{"_entidade": "contrato"}])) == []


# ── O registro de conectores ────────────────────────────────────────


def test_conector_sem_chave_e_recusado():
    class Anonimo:
        chave = ""

    with pytest.raises(ValueError, match="chave"):
        registrar(Anonimo())


def test_chave_duplicada_e_erro_e_nao_substituicao_silenciosa():
    """Dois conectores para a mesma fonte significa que um deles some — e o que
    some é sempre o que alguém acabou de escrever."""
    guardados = todos()
    try:
        class Um:
            chave = "duplicado"

        registrar(Um())
        with pytest.raises(ValueError, match="Já existe conector"):
            registrar(Um())
    finally:
        limpar()
        for conector in guardados.values():
            registrar(conector, substituir=True)


def test_o_protocolo_tem_implementacao_padrao_vazia():
    """`ConectorBase` responde a tudo sem fazer nada.

    Herdar é opcional — o protocolo é o que vale —, mas quem herda não deve
    precisar escrever três métodos vazios para começar.
    """
    conector = base.ConectorBase()

    assert conector.disponivel() is True
    assert list(conector.coletar(base.Janela())) == []
    assert list(conector.normalizar([])) == []
    assert "ConectorBase" in repr(conector)


def test_a_janela_se_apresenta_em_portugues():
    """Ela aparece na saída do comando, que é onde o operador confere se pediu
    o mês certo."""
    assert str(base.Janela()) == "tudo"
    assert str(base.Janela(de=date(2026, 8, 1), ate=date(2026, 8, 31))) == (
        "2026-08-01 a 2026-08-31"
    )


def test_o_registro_se_apresenta_por_entidade_e_chave():
    registro = base.Registro(entidade="contrato", chave_externa="ext-1")

    assert str(registro) == "contrato:ext-1"


# ── monday: os cantos que a documentação avisa ──────────────────────


def test_monday_data_invalida_nao_derruba_a_linha():
    """A API devolve `date` nulo em coluna nunca preenchida, e texto livre em
    coluna que alguém converteu de tipo. Nenhum dos dois pode parar a carga."""
    from cargas.conectores.monday import _converter_coluna, _dia, _instante

    assert _dia(None) is None
    assert _dia("amanhã") is None
    assert _instante("") is None
    assert _instante("data errada") is None
    assert _converter_coluna("prazo", {"type": "date", "date": None, "text": ""}) is None


def test_monday_numero_nao_numerico_vira_none():
    from cargas.conectores.monday import _converter_coluna

    valor = {"type": "numbers", "text": "quase 50"}

    assert _converter_coluna("percentual_concluido", valor) is None


def test_monday_coluna_de_texto_vazia_nao_entra():
    """`""` sobrescreveria o que outra carga gravou. Ausente é ausente."""
    from cargas.conectores.monday import _converter_coluna

    assert _converter_coluna("responsavel", {"type": "text", "text": "   "}) is None


def test_monday_erro_do_graphql_nao_devolve_a_query_inteira(rede_monday, settings):
    """A mensagem vai para `erro_resumo`, que aparece na tela de fontes.

    O corpo de erro do GraphQL às vezes traz de volta a query COM as variáveis —
    e as variáveis de uma consulta autenticada não são para uma tela.
    """
    from cargas import transporte
    from cargas.conectores.monday import ConectorMonday

    settings.MONDAY_TOKEN = "tok"
    settings.MONDAY_BOARDS = {"projeto": {"board": 1, "colunas": {}}}
    rede_monday({"errors": [{"message": "x" * 500}]})

    with pytest.raises(transporte.TransporteError) as erro:
        list(ConectorMonday().coletar(base.Janela()))

    assert len(str(erro.value)) < 300


def test_monday_board_sem_id_declarado_e_erro_e_nao_silencio(rede_monday, settings):
    from cargas import transporte
    from cargas.conectores.monday import ConectorMonday

    settings.MONDAY_TOKEN = "tok"
    settings.MONDAY_BOARDS = {"projeto": {"colunas": {}}}

    with pytest.raises(transporte.TransporteError, match="board não declarado"):
        list(ConectorMonday().coletar(base.Janela()))


def test_monday_so_esta_disponivel_com_token_E_mapa(settings):
    from cargas.conectores.monday import ConectorMonday

    settings.MONDAY_TOKEN = ""
    settings.MONDAY_BOARDS = {"projeto": {"board": 1}}
    assert ConectorMonday().disponivel() is False

    settings.MONDAY_TOKEN = "tok"
    settings.MONDAY_BOARDS = None
    assert ConectorMonday().disponivel() is False


def test_monday_item_sem_entidade_nao_vira_registro():
    from cargas.conectores.monday import ConectorMonday

    assert list(ConectorMonday().normalizar([{"id": "1"}])) == []


# ── Sankhya: os cantos ──────────────────────────────────────────────


def test_sankhya_valor_desembrulhado_e_tipado():
    from cargas.conectores.sankhya import _tipar, _valor

    assert _valor({"$": "1200"}) == "1200"
    assert _valor("cru") == "cru"
    assert _tipar("ano", "2026") == 2026
    assert _tipar("ano", "n/a") is None
    assert _tipar("centro_custo", "  1042 ") == "1042"
    assert _tipar("receita_bruta", "1200,50") == Decimal("1200.50")
    assert _tipar("receita_bruta", None) is None


def test_sankhya_texto_onde_se_esperava_numero_vira_texto_e_nao_estoura():
    """Uma view que devolve "N/D" numa coluna de dinheiro existe.

    Estourar aqui perderia a competência inteira; devolver o texto deixa o
    carregador rejeitar a LINHA, com motivo.
    """
    from cargas.conectores.sankhya import _tipar

    assert _tipar("receita_bruta", "N/D") == "N/D"


def test_sankhya_registro_sem_chave_nao_vira_registro():
    from cargas.conectores.sankhya import ConectorSankhya

    item = {"_entidade": "competencia", "_campos": ("CHAVE",), "f0": {"$": ""}}

    assert list(ConectorSankhya().normalizar([item])) == []


def test_sankhya_entidade_fora_da_traducao_e_ignorada():
    from cargas.conectores.sankhya import ConectorSankhya

    assert list(ConectorSankhya().normalizar([{"_entidade": "compras"}])) == []


def test_sankhya_reaproveita_o_token_dentro_da_validade(rede_monday, sankhya_env):
    """O token dura ~300 s e uma carga de competência passa disso.

    Reautenticar a cada página gastaria uma chamada por página — e o Gateway
    conta chamada.
    """
    from cargas.conectores.sankhya import ConectorSankhya

    pedidos = rede_monday(
        {"access_token": "jwt", "expires_in": 300},
        {"responseBody": {"entities": {"hasMoreResult": "false"}}},
    )
    conector = ConectorSankhya()

    list(conector.coletar(base.Janela()))
    list(conector.coletar(base.Janela()))

    autenticacoes = [p for p in pedidos if p.full_url.endswith("/authenticate")]
    assert len(autenticacoes) == 1


# ── Platform: a janela vira query string ────────────────────────────


def test_platform_manda_a_janela_no_query_string(rede_monday, settings):
    from cargas.conectores.platform import ConectorPlatform

    settings.ICONNECT_API_URL = "https://iconnect.exemplo"
    settings.WORKSPACE_SHARED_SECRET = "s"
    settings.PLATFORM_ROTAS = {"contrato": "/api/v1/integracao/contratos/"}
    pedidos = rede_monday({"results": [], "next": None})

    list(ConectorPlatform().coletar(base.Janela(de=date(2026, 8, 1), ate=date(2026, 8, 31))))

    assert "de=2026-08-01" in pedidos[0].full_url
    assert "ate=2026-08-31" in pedidos[0].full_url


# ── Transporte: os cantos do recuo ──────────────────────────────────


def test_retry_after_com_texto_cai_no_recuo_proprio():
    """`Retry-After` pode vir como data HTTP, e não como segundos.

    Não vale tentar interpretar as duas formas: errar a data faria esperar
    horas. O recuo próprio é a resposta segura.
    """
    import io
    import urllib.error

    from cargas import transporte

    erro = urllib.error.HTTPError(
        "https://x/y", 429, "e", {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"},
        io.BytesIO(b"{}"),
    )

    assert transporte._espera_pedida(erro) is None


def test_corpo_de_erro_que_nao_e_json_nao_quebra_o_recuo():
    import io
    import urllib.error

    from cargas import transporte

    erro = urllib.error.HTTPError("https://x/y", 500, "e", {}, io.BytesIO(b"<html>"))

    assert transporte._espera_pedida(erro) is None


def test_fonte_que_nunca_responde_desiste_com_mensagem(monkeypatch):
    """Erro de REDE, e não HTTP: o outro lado nem respondeu."""
    import urllib.error

    from cargas import transporte

    def _cai(requisicao, timeout=None):
        raise urllib.error.URLError("sem rota")

    monkeypatch.setattr(transporte.urllib.request, "urlopen", _cai)

    with pytest.raises(transporte.TransporteError, match="não respondeu"):
        transporte.pedir("https://fonte.exemplo/x", dormir=lambda _: None)
