"""§58 — a auditoria final, executável.

Não é uma revisão de código escrita em prosa: é o conjunto de propriedades
estruturais que, quando quebram, quebram em silêncio. Rota que ninguém alcança,
template órfão, função que ninguém chama, modelo sem porta nenhuma, comentário
que descreve uma decisão revertida.

## O que ela achou na primeira execução

1. **`orcamento.baixar()` não tinha chamador.** O compromisso entrava na
   aprovação e só saía por cancelamento — pedido entregue continuava contando
   como comprometido para sempre. Como `consumido = realizado + comprometido`, a
   mesma compra passava a contar duas vezes assim que a nota era lançada.
2. **`estoque.conferir_razao()` não tinha chamador**, com a docstring dizendo
   "existe para que a divergência seja DETECTÁVEL". A função que detecta não era
   executada por ninguém.
3. **`Material` e `Curso` não tinham porta nenhuma** — nem tela, nem admin.
   Cadastrar material novo era editar o seeder ou abrir um shell.
4. **Cinco funções públicas de serviço sem uso**, três delas escritas por mim
   nesta rodada.

Todas corrigidas. Este arquivo é o que impede a sexta.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.django_db

RAIZ = Path(__file__).resolve().parent.parent.parent


def _fontes_e_telas() -> str:
    """Todo o código de PRODUÇÃO, sem os testes.

    Sem a exclusão, este arquivo se acharia: ele cita as frases proibidas para
    explicá-las, e o teste passaria a falhar por causa da própria explicação.
    Pior: uma função morta chamada só por um teste pareceria viva — que é
    exatamente o caso que a auditoria existe para pegar.
    """
    texto = ""
    for pasta in ("workspace", "identidade", "contas", "financas", "iconnect_workspace"):
        for caminho in (RAIZ / pasta).rglob("*"):
            if (
                caminho.suffix in (".py", ".html")
                and "migrations" not in caminho.parts
                and "tests" not in caminho.parts
            ):
                texto += caminho.read_text(encoding="utf-8")
    return texto


# ── Nada órfão ──────────────────────────────────────────────────────


def test_nenhuma_rota_do_workspace_e_inalcancavel():
    """Rota sem referência é uma tela que existe e ninguém abre — ou um resto de
    funcionalidade removida pela metade."""
    from django.urls import get_resolver

    fontes = _fontes_e_telas()
    nomes = []

    def coletar(padroes, prefixo=""):
        for padrao in padroes:
            if hasattr(padrao, "url_patterns"):
                coletar(
                    padrao.url_patterns,
                    prefixo + (f"{padrao.namespace}:" if padrao.namespace else ""),
                )
            elif padrao.name:
                nomes.append(prefixo + padrao.name)

    coletar(get_resolver().url_patterns)

    orfas = [
        nome
        for nome in nomes
        if nome.startswith("workspace:")
        and f"'{nome}'" not in fontes
        and f'"{nome}"' not in fontes
        and f"'{nome.split(':')[-1]}'" not in fontes
        and f'"{nome.split(":")[-1]}"' not in fontes
    ]

    assert orfas == [], f"rotas que ninguém alcança: {orfas}"


def test_nenhum_template_e_orfao():
    fontes = _fontes_e_telas()
    convencao = {"400.html", "403.html", "404.html", "500.html"}

    orfaos = [
        str(caminho.relative_to(RAIZ / "workspace" / "templates"))
        for caminho in (RAIZ / "workspace" / "templates").rglob("*.html")
        if caminho.name not in convencao
        and str(caminho.relative_to(RAIZ / "workspace" / "templates")) not in fontes
    ]

    assert orfaos == [], f"templates que ninguém renderiza: {orfaos}"


def test_nenhuma_funcao_publica_de_servico_esta_morta():
    """Função pública que ninguém chama é decisão de produto abandonada pela
    metade — e a próxima pessoa a lê como se estivesse valendo.

    Foi assim que `orcamento.baixar()` passou meses sem chamador enquanto o
    compromisso ficava eterno, e `estoque.conferir_razao()` prometia detectar
    divergência que ninguém mandava detectar.
    """
    fontes = _fontes_e_telas()
    mortas = []

    for caminho in (RAIZ / "workspace" / "services").glob("*.py"):
        texto = caminho.read_text(encoding="utf-8")
        for nome in re.findall(r"^def ([a-z][a-z0-9_]*)\(", texto, re.M):
            if nome.startswith("_"):
                continue
            # `- 1` desconta a própria definição, que também casa `nome(`.
            chamadas = len(re.findall(rf"\b{nome}\s*\(", fontes)) - 1
            # Receptor de sinal e ação de dicionário são referenciados SEM `(` —
            # `apr.vez_de.connect(ao_chegar_a_vez, ...)`, `{"arquivar": pub.arquivar}`.
            # A linha do `def` não entra aqui: ela é seguida de `(`.
            referencias = len(re.findall(rf"\b(?:\w+\.)?{nome}\b(?!\s*\()", fontes))
            if chamadas <= 0 and referencias == 0:
                mortas.append(f"{caminho.name}:{nome}")

    assert mortas == [], f"funções de serviço sem chamador: {mortas}"


def test_todo_modelo_tem_porta_ou_e_derivado():
    """Modelo sem tela e sem admin é um cadastro que só o shell alcança.

    A lista de exceções é escrita à mão e cada uma tem um motivo: são livros
    (razão, histórico, índice) e linhas derivadas de outra coisa. Nenhuma delas
    se edita à mão, e oferecer a edição seria o defeito.
    """
    from django.apps import apps
    from django.contrib import admin

    #: Modelos que NÃO devem ter porta de edição, e por quê.
    SEM_PORTA_DE_PROPOSITO = {
        # Livros: nada aqui se edita, é o desenho inteiro.
        "MovimentoEstoque", "EventoSolicitacao", "EntradaIndice", "SujeitoIndice",
        # Derivados de uma ação, nunca digitados.
        "SaldoEstoque", "Anexo", "ConfirmacaoLeitura", "EtapaAprovacao",
        "Notificacao", "ComentarioSolicitacao", "AcertoAdiantamento",
        "DespesaReembolso", "EvidenciaRelatorio", "DespesaVeiculo",
        # Têm tela própria no produto.
        "Custodia", "Veiculo", "Oportunidade", "PerguntaFrequente", "Relatorio",
        "Matricula",
    }

    registrados = {model.__name__ for model in admin.site._registry}
    # Modelo editado por INLINE também tem porta, e às vezes tem a porta certa:
    # `EtapaCiclo` numa tela própria produziria a pauta de três ciclos misturada
    # e ordenada por id — e a ordem é justamente o que uma pauta é. O teste
    # pergunta se existe caminho de edição, não se existe `ModelAdmin`.
    for opcoes in admin.site._registry.values():
        for inline in getattr(opcoes, "inlines", ()):
            registrados.add(inline.model.__name__)
    todos = {m.__name__ for m in apps.get_app_config("workspace").get_models()}

    sem_porta = todos - registrados - SEM_PORTA_DE_PROPOSITO

    assert sem_porta == set(), (
        f"modelos sem tela e sem admin: {sorted(sem_porta)} — só o shell os alcança"
    )


# ── Coerência ───────────────────────────────────────────────────────


def test_toda_migracao_esta_aplicavel_e_o_grafo_e_linear():
    """`makemigrations --check` falhando significa modelo mudado sem migração —
    e o deploy quebra na hora de subir, não aqui."""
    from io import StringIO

    from django.core.management import call_command

    call_command("makemigrations", "--check", "--dry-run", stdout=StringIO())


def test_todo_comando_de_gestao_tem_docstring_que_explica_o_porque():
    """Comando sem explicação é comando que ninguém agenda — e os quatro avisos
    diários do produto só valem alguma coisa agendados."""
    curtos = []
    pasta = RAIZ / "workspace" / "management" / "commands"
    for caminho in pasta.glob("*.py"):
        if caminho.name == "__init__.py":
            continue
        texto = caminho.read_text(encoding="utf-8")
        docstring = re.match(r'\s*"""(.*?)"""', texto, re.DOTALL)
        if docstring is None or len(docstring.group(1).strip()) < 120:
            curtos.append(caminho.name)

    assert curtos == [], f"comandos sem docstring que explique o porquê: {curtos}"


def test_nenhum_comentario_promete_ausencia_de_pdf():
    """O `reportlab` entrou no §35 e um comentário continuou dizendo "sem
    geração de PDF no servidor". Comentário que descreve decisão revertida é
    pior que comentário nenhum: quem lê confia nele."""
    fontes = _fontes_e_telas()

    assert "Sem geração de PDF no servidor" not in fontes


def test_nenhum_comentario_nega_publico_alvo_da_publicacao():
    """"Publicação não tem público-alvo ainda" ficou no índice depois de o campo
    nascer no §9 — e o índice entregava a todo mundo o comunicado de um
    departamento."""
    fontes = _fontes_e_telas()

    assert "Publicação não tem público-alvo ainda" not in fontes


def test_todo_estado_de_solicitacao_cabe_em_exatamente_uma_lista():
    """A partição é de três: na esteira, terminado, ou nem enviado."""
    from workspace.models.catalogo import (
        SITUACOES_NAO_ENVIADAS,
        SITUACOES_TERMINAIS,
        SituacaoServico,
    )
    from workspace.services import listagem as lst

    conjuntos = [set(lst.ABERTAS), set(SITUACOES_TERMINAIS), set(SITUACOES_NAO_ENVIADAS)]

    for i, um in enumerate(conjuntos):
        for outro in conjuntos[i + 1 :]:
            assert um & outro == set()
    assert set().union(*conjuntos) == set(SituacaoServico)


def test_o_produto_passa_no_system_check_do_django():
    """O `manage.py check` — o gate que 2.874 testes não substituem.

    ## Por que este teste existe

    Ele foi escrito depois de o produto ficar **sem conseguir subir** com a
    suíte inteira verde. Um `list_editable` apontando para o primeiro campo de
    `list_display` levantou `admin.E124` no `runserver`, e nenhum dos 2.874
    testes tocou nisso: eles exercitam views, serviços e models, e o
    `ModelAdmin` só é validado quando o Django faz o *check* de sistema.

    O sintoma era o pior possível — verde no CI, `SystemCheckError` na máquina
    de quem ia usar. Descobri porque alguém tentou abrir a tela; sem isso, o
    defeito iria para produção.

    ## Por que não `--deploy`

    Os checks de deploy (`SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`) falham
    de propósito no settings de desenvolvimento, e ligá-los aqui obrigaria a
    testar contra o settings de produção — que não é o que a suíte roda.
    Aqueles são cobertos por `test_auditoria_hardening.py`.
    """
    from io import StringIO

    from django.core.management import call_command

    saida = StringIO()
    # `call_command` levanta `SystemCheckError` quando há ERROR; a mensagem
    # dele já nomeia a classe e o código (`admin.E124`), então não há o que
    # acrescentar no `assert`.
    call_command("check", stdout=saida, stderr=saida)

    assert "issues" not in saida.getvalue() or "0 silenced" in saida.getvalue()
