"""Isolamento arquitetural — as três direções que não podem inverter.

## A regra, inalterada desde o ST-002

    o domínio pode depender do CONTRATO (`workspace.providers`),
    nunca da SUPERFÍCIE (`workspace.views`, `.models`, `.services`, `.urls`…).

O contrato é consumido por todos; a superfície é folha. Este teste é o que impede
a primeira violação de entrar sem ninguém perceber — e ela entra sempre pelo
caminho conveniente, num `apps.py`, num domingo.

## O que mudou na separação dos produtos

Antes, os domínios eram `dashboard`, `fsm`, `km_audit` e `calculo_vigilante`, e
eles moravam no mesmo repositório. Agora o Workspace é um produto à parte: o
único domínio é `financas`, e a ligação com o iConnect Platform é **um link**
(`settings.ICONNECT_URL`).

Isso adicionou uma invariante que antes não existia e que hoje é a mais
importante daqui: **nada neste repositório pode importar app do iConnect**. Um
`from dashboard.models import ...` esquecido não quebraria o teste antigo — ele
falharia no import, em produção, na primeira requisição que passasse ali. É
exatamente o tipo de resíduo que uma extração deixa.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent.parent

# Apps de domínio deste projeto: podem falar com o contrato, não com a superfície.
#
# `resultados` é o espelho do que vem de fora; `cargas` é quem traz. Os dois
# entraram na onda de ingestão, e a direção que eles adicionam é:
#
#     cargas ──► resultados ──implementa──► workspace.providers ◄── workspace
#
# `cargas` PODE importar `resultados` — é para lá que ele escreve. O que nenhum
# dos dois pode é importar a superfície, e o que o `workspace` não pode é
# conhecer qualquer um dos dois.
DOMINIOS = ("financas", "resultados", "cargas")

# O único subpacote de `workspace` que um domínio pode importar.
CONTRATO_PERMITIDO = "workspace.providers"

# Apps que ficaram no iConnect Platform. Nenhum arquivo daqui pode importá-los —
# eles não existem neste repositório, e um import assim é resíduo da extração.
APPS_DO_ICONNECT = (
    "dashboard",
    "fsm",
    "km_audit",
    "calculo_vigilante",
    "estoque",
    "financeiro",
    "pagamento_tecnico",
    "equipamentos",
)

# Tudo o que é nosso, para varrer de uma vez.
NOSSOS_APPS = (
    "workspace", "identidade", "contas", "financas", "resultados", "cargas",
    "iconnect_workspace",
)


def _arquivos_python(app: str) -> list[Path]:
    diretorio = RAIZ / app
    if not diretorio.is_dir():
        return []
    return [
        caminho
        for caminho in diretorio.rglob("*.py")
        if "migrations" not in caminho.parts and "__pycache__" not in caminho.parts
    ]


def _importados(caminho: Path) -> list[str]:
    """Todos os módulos importados por este arquivo, absolutos."""
    try:
        arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    except SyntaxError:  # pragma: no cover - sintaxe é problema de outro gate
        return []

    encontrados: list[str] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            encontrados += [alias.name for alias in no.names]
        elif isinstance(no, ast.ImportFrom) and no.level == 0 and no.module:
            # `level > 0` é import relativo: nunca alcança outro app.
            encontrados.append(no.module)
    return encontrados


def _de_workspace(modulos: list[str]) -> list[str]:
    return [
        m for m in modulos if m == "workspace" or m.startswith("workspace.")
    ]


# ── Direção 1: domínio → contrato, nunca superfície ─────────────────


@pytest.mark.parametrize("app", DOMINIOS)
def test_dominio_nao_importa_superficie_do_workspace(app):
    """A regra vale para o código que RODA, e não para o que o verifica.

    `tests/` fica de fora, e é uma exceção deliberada — anotada aqui porque
    afrouxar um teste de arquitetura sem dizer por quê é como a regra morre.

    O que esta trava protege é a direção em PRODUÇÃO: um domínio que importasse
    `workspace.services` passaria a quebrar quando a superfície mudasse. Um
    teste não embarca dependência nenhuma no domínio — e há testes que só
    existem porque atravessam a fronteira de propósito:

    - `cargas/tests/test_transporte.py` exercita os DOIS transportes do
      repositório para afirmar que nenhum registra credencial. A garantia mora
      num teste justamente porque os dois transportes não podem dividir código.
    - `cargas/tests/test_frescor.py` prova que registrar o provider muda o
      carimbo que a tela mostra — o que exige ver os dois lados.

    A trava do iConnect (`test_nenhum_arquivo_importa_app_do_iconnect`) CONTINUA
    varrendo os testes, e de propósito: lá o problema é um módulo que não existe
    neste repositório, e foi num teste que sobrou a última referência.
    """
    violacoes = []
    for caminho in _arquivos_python(app):
        if "tests" in caminho.parts:
            continue
        for modulo in _de_workspace(_importados(caminho)):
            permitido = modulo == CONTRATO_PERMITIDO or modulo.startswith(
                CONTRATO_PERMITIDO + "."
            )
            if not permitido:
                violacoes.append(f"{caminho.relative_to(RAIZ)}: importa {modulo}")

    assert not violacoes, (
        "Domínio importando a superfície do Workspace — WKS é folha.\n"
        f"Permitido apenas `{CONTRATO_PERMITIDO}`.\n  " + "\n  ".join(violacoes)
    )


def test_o_provider_real_importa_so_o_contrato():
    """`financas` é o domínio que responde sobre orçamento.

    Ele existe porque a separação dos produtos deixou a barra tripla da bandeja
    sem fonte: `CentroCusto` morava no iConnect. O Workspace assumiu o orçamento,
    mas a costura sobreviveu — e é isto que este teste verifica.
    """
    importados = set()
    for caminho in _arquivos_python("financas"):
        importados.update(_de_workspace(_importados(caminho)))

    assert importados, "financas deveria registrar seu provider de orçamento"
    for modulo in importados:
        assert modulo == CONTRATO_PERMITIDO or modulo.startswith(
            CONTRATO_PERMITIDO + "."
        ), f"financas importa {modulo}, que não é o contrato"


# ── Direção 2: a superfície não consulta model de domínio ───────────


def test_workspace_nao_importa_app_de_dominio():
    """O caminho inverso: a superfície pergunta pelo contrato, não pelo model.

    Se o Workspace importasse `financas.models`, trocar a fonte do realizado
    exigiria mexer em dois apps — e o Workspace viraria um segundo lugar onde o
    dado financeiro mora e diverge.
    """
    violacoes = []
    for caminho in _arquivos_python("workspace"):
        if "tests" in caminho.parts:
            continue
        for modulo in _importados(caminho):
            if modulo.split(".")[0] in DOMINIOS:
                violacoes.append(f"{caminho.relative_to(RAIZ)}: importa {modulo}")

    assert not violacoes, (
        "Workspace importando app de domínio diretamente — use o provider.\n  "
        + "\n  ".join(violacoes)
    )


def test_o_espelho_nao_conhece_quem_carrega():
    """A direção da ingestão, no sentido que costuma inverter.

    `cargas` escreve em `resultados`. O caminho de volta é o que tenta nascer
    sozinho: basta alguém querer uma FK de `Contrato` para `FonteDados` — e é
    o pedido mais natural do mundo, porque procedência com integridade
    referencial é melhor que procedência sem.

    O preço seria um ciclo entre dois apps, e ciclo entre apps é como o grafo de
    migração vira um problema de fim de semana. `resultados` guarda `fonte` e
    `carga_id` soltos, pelo mesmo motivo que `EntradaIndice` guarda `dominio` e
    `origem_id`: o espelho sobrevive à origem.
    """
    violacoes = []
    for caminho in _arquivos_python("resultados"):
        if "tests" in caminho.parts:
            continue
        for modulo in _importados(caminho):
            if modulo.split(".")[0] == "cargas":
                violacoes.append(f"{caminho.relative_to(RAIZ)}: importa {modulo}")

    assert not violacoes, (
        "O espelho importando quem carrega — a direção é cargas → resultados.\n  "
        + "\n  ".join(violacoes)
    )


def test_os_conectores_nao_conhecem_a_superficie():
    """Nenhum conector importa `workspace.integracoes`.

    O transporte do iConnect é tentador — ele já existe, já tem retry e já
    trata erro. E é superfície: roda dentro de uma requisição, com timeout de
    4 s e recusando repetir `POST`. A API do monday é GraphQL, onde toda
    LEITURA é um `POST`; passar por lá quebraria a regra dele ou o conector.

    Ver `cargas/transporte.py` para a tabela dos requisitos opostos.
    """
    violacoes = []
    for caminho in _arquivos_python("cargas"):
        if "tests" in caminho.parts:
            continue
        for modulo in _de_workspace(_importados(caminho)):
            permitido = modulo == CONTRATO_PERMITIDO or modulo.startswith(
                CONTRATO_PERMITIDO + "."
            )
            if not permitido:
                violacoes.append(f"{caminho.relative_to(RAIZ)}: importa {modulo}")

    assert not violacoes, (
        "Conector importando a superfície do Workspace.\n"
        f"Permitido apenas `{CONTRATO_PERMITIDO}`.\n  " + "\n  ".join(violacoes)
    )


def test_identidade_e_raiz_e_nao_conhece_o_workspace():
    """IDN é raiz: só conhece o modelo de usuário.

    Escopo de permissão é consultado dezenas de vezes por requisição; se
    `identidade` passasse a importar a superfície, qualquer mudança de tela
    poderia mudar o resultado de `pode()`.
    """
    violacoes = []
    for caminho in _arquivos_python("identidade"):
        if "tests" in caminho.parts:
            continue
        for modulo in _importados(caminho):
            if modulo.split(".")[0] in ("workspace", "financas"):
                violacoes.append(f"{caminho.relative_to(RAIZ)}: importa {modulo}")

    assert not violacoes, (
        "identidade é a raiz da dependência e não pode importar outro app nosso.\n  "
        + "\n  ".join(violacoes)
    )


# ── Direção 3: nada aqui conhece o iConnect Platform ────────────────


@pytest.mark.parametrize("app", NOSSOS_APPS)
def test_nenhum_arquivo_importa_app_do_iconnect(app):
    """A invariante que guarda a separação dos dois produtos.

    O iConnect Platform é alcançado por **um link**, e só. Um import residual
    aqui não é acoplamento teórico: é `ModuleNotFoundError` na primeira
    requisição que passar pela linha, porque aqueles apps não existem neste
    repositório.

    Vale para os testes também, e de propósito — foi num teste que sobrou a
    última referência a `dashboard` na extração.
    """
    violacoes = []
    for caminho in _arquivos_python(app):
        for modulo in _importados(caminho):
            if modulo.split(".")[0] in APPS_DO_ICONNECT:
                violacoes.append(f"{caminho.relative_to(RAIZ)}: importa {modulo}")

    assert not violacoes, (
        "Import de app do iConnect Platform — ele não existe neste repositório.\n"
        "A ligação entre os produtos é `settings.ICONNECT_URL`, um link.\n  "
        + "\n  ".join(violacoes)
    )
