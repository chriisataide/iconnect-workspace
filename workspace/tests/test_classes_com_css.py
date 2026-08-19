"""Toda classe `au-*` escrita num template existe no CSS.

Escrito depois de encontrar a tela de identificação renderizando com as caixas
cruas do navegador, no meio de um produto inteiro estilizado. Ela usava
`au-form-entrar`, `au-campo-entrada` e `au-botao` — o vocabulário do projeto
anterior, que nunca existiu neste CSS. Nada quebrava: HTML aceita qualquer
classe, o Django renderiza feliz, e a suíte passava verde.

É a mesma família de defeito do teste de contraste ao lado: **estilo regride em
silêncio**. Não levanta exceção, não vira 500 — só fica feio numa tela que
ninguém abre com frequência. E `/entrar/` é exatamente uma tela dessas: ninguém
chega nela navegando, só ao tentar um ato que exige identidade.

O teste é bobo de propósito. Ele não sabe se o estilo está bonito; sabe se
alguém escreveu um nome de classe que o CSS nunca ouviu falar.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent.parent
ESTILOS = RAIZ / "workspace" / "static" / "workspace" / "src"


def _css() -> str:
    return "\n".join(
        arquivo.read_text(encoding="utf-8") for arquivo in ESTILOS.glob("*.css")
    )


def _classes_por_template() -> dict[str, set[str]]:
    """As classes literais de cada template.

    Valor com `{` fica de fora: `au-etiqueta--{{ s.situacao }}` é montado em
    tempo de render, e conferir isso exigiria enumerar os valores possíveis do
    enum — o teste passaria a falhar por um `TextChoices` novo, e não por uma
    classe sem estilo.
    """
    achadas: dict[str, set[str]] = {}
    for template in RAIZ.glob("**/templates/**/*.html"):
        if ".venv" in template.parts:
            continue
        for atributo in re.findall(r'class="([^"]*)"', template.read_text(encoding="utf-8")):
            if "{" in atributo:
                continue
            for classe in atributo.split():
                if classe.startswith("au-"):
                    achadas.setdefault(str(template.relative_to(RAIZ)), set()).add(classe)
    return achadas


def test_nenhuma_classe_de_template_ficou_sem_css():
    css = _css()
    orfas = {
        template: sorted(c for c in classes if f".{c}" not in css)
        for template, classes in _classes_por_template().items()
    }
    orfas = {t: c for t, c in orfas.items() if c}

    assert not orfas, "classes sem nenhuma regra no CSS:\n" + "\n".join(
        f"  {template}: {', '.join(classes)}" for template, classes in sorted(orfas.items())
    )


def test_o_teste_enxerga_os_templates_de_todos_os_apps():
    """Guarda contra o pior defeito possível aqui: um teste que não olha nada
    e passa verde para sempre. `contas/` tem a tela de identificação; se o
    varredor deixar de vê-la, é ela que volta a ficar sem estilo."""
    templates = _classes_por_template()

    assert any(t.startswith("workspace/templates/") for t in templates)
    assert any(t.startswith("contas/templates/") for t in templates)
    assert sum(len(c) for c in templates.values()) > 100


def test_nenhum_comentario_curto_vazou_para_a_pagina():
    """`{# … #}` só é comentário em UMA linha.

    Escrito em duas, o Django não o reconhece e imprime o texto na página. Foi
    o que aconteceu com a explicação do `type="time"`: a frase sobre os
    dois-pontos apareceu dentro do formulário de atestado, entre dois campos,
    e só foi notada porque um teste de fumaça contou os campos de hora e achou
    quatro onde deviam existir dois.

    Comentário de mais de uma linha usa `{% comment %}`.
    """
    vazados: list[str] = []
    for template in RAIZ.glob("**/templates/**/*.html"):
        if ".venv" in template.parts:
            continue
        linhas = template.read_text(encoding="utf-8").splitlines()
        for numero, linha in enumerate(linhas, start=1):
            if "{#" in linha and "#}" not in linha:
                vazados.append(f"{template.relative_to(RAIZ)}:{numero}")

    assert not vazados, (
        "comentário `{# #}` aberto numa linha e fechado em outra — o Django "
        "imprime isso na tela:\n  " + "\n  ".join(vazados)
    )


def test_todo_token_usado_no_css_existe():
    """`var(--au-7)` derrubou o padding de uma tela inteira, em silêncio.

    A escala de espaçamento **pula o 7**: existe `--au-6` e existe `--au-8`.
    Escrever `padding: var(--au-8) var(--au-7)` não é meio certo — é uma
    declaração inválida, e o navegador descarta o padding INTEIRO. A tela de
    identificar-se foi ao ar com os dois painéis sem margem nenhuma, texto
    colado na borda e o rótulo da direita cortado pelo painel da esquerda.

    É a mesma família dos dois testes acima: estilo regride sem levantar
    exceção. Aqui a diferença é que nem o nome da classe estava errado — o
    nome do token estava.

    `var(--x, fallback)` fica de fora: quem escreve o fallback declarou que o
    token pode não existir, e é assim que o CSS marca cor por dado.
    """
    css = _css()
    definidos = set(re.findall(r"(--au-[a-z0-9-]+)\s*:", css))

    # `var(--token)` sem vírgula — com vírgula há fallback, e aí é deliberado.
    usados = set(re.findall(r"var\(\s*(--au-[a-z0-9-]+)\s*\)", css))

    orfaos = sorted(usados - definidos)
    assert not orfaos, (
        "token usado e nunca definido — o navegador descarta a declaração "
        f"inteira, sem avisar: {orfaos}"
    )


def test_nenhuma_classe_base_e_redefinida_do_zero():
    """Duas regras `.au-x { ... }` para a mesma classe base, e a de baixo vence.

    Foi assim que a vitrine inteira de serviços quebrou: a grade de horas das
    reservas nasceu com o nome `au-grade`, que já era o grid do catálogo 400
    linhas acima. A regra nova redefiniu `display` e `grid-template-columns`, os
    cards perderam a largura de coluna e a última linha de cada grupo esticou.

    O guard de "classe usada sem CSS" fica VERDE nesse caso: a classe existe e
    tem regra. Só a tela mostra. Este teste é o que passa a mostrar antes.

    Modificador (`--`) e elemento (`-algo`) não contam: `.au-btn--primario`
    depois de `.au-btn` é a cascata sendo usada como se deve.
    """
    import re
    from collections import Counter
    from pathlib import Path

    css = Path("workspace/static/workspace/src/workspace.css").read_text()
    # Só as regras de topo de linha, sem seletor composto: `.au-x {` sozinha é
    # definição de base. `.au-x .au-y {` e `.au-x:hover {` são outra coisa.
    bases = re.findall(r"(?m)^\.(au-[a-z0-9-]+)\s*\{", css)
    bases = [c for c in bases if "--" not in c]

    repetidas = {c: n for c, n in Counter(bases).items() if n > 1}
    assert not repetidas, (
        "classe base definida mais de uma vez — a de baixo vence e a de cima "
        f"vira letra morta: {repetidas}"
    )


def test_ninguem_usa_now_date_no_lugar_de_localdate():
    """`timezone.now().date()` é o dia em UTC, não o dia daqui.

    No fuso de São Paulo os dois divergem das 21h à meia-noite — três horas por
    dia em que "hoje" quer dizer amanhã. Código escrito de manhã passa; a suíte
    rodada à noite reprova; e em produção o efeito é pior, porque não reprova
    nada: a data simplesmente entra errada.

    É a **quinta** armadilha de hora do dia desta suíte. As quatro anteriores
    foram consertadas uma a uma; esta é a que impede a sexta.

    O certo é `timezone.localdate()` — e, para converter um campo já gravado,
    `timezone.localtime(campo).date()`.
    """
    import re
    from pathlib import Path

    aqui = Path(__file__).resolve()
    culpados = []
    for arquivo in Path(".").glob("*/**/*.py"):
        partes = arquivo.parts
        if ".venv" in partes or "migrations" in partes:
            continue
        # O próprio guard fica de fora: ele PRECISA escrever o padrão que
        # procura, na regex e na explicação.
        if arquivo.resolve() == aqui:
            continue
        texto = arquivo.read_text(encoding="utf-8", errors="ignore")
        for numero, linha in enumerate(texto.splitlines(), 1):
            # Comentário citando o padrão não é uso dele — e explicar o defeito
            # ao lado do conserto é justamente o que se quer incentivar.
            if linha.lstrip().startswith("#"):
                continue
            if re.search(r"\bnow\(\)\.date\(\)", linha) and "localtime" not in linha:
                culpados.append(f"{arquivo}:{numero}")

    assert not culpados, (
        "use `timezone.localdate()` — `now().date()` devolve o dia em UTC:\n    "
        + "\n    ".join(culpados)
    )
