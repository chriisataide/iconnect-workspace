"""§49 — a revisão de design e usabilidade, executável.

Consistência visual não é opinião quando está escrita como regra. Estes testes
guardam as regras do design system que, quando quebram, quebram em silêncio:
a tela continua renderizando e só a pessoa que usa percebe.

## O que a revisão achou na primeira execução

1. **Um campo com `placeholder` no lugar de rótulo.** Placeholder some no
   instante em que a pessoa digita — e é o motivo da devolução do pedido, que é
   texto que se escreve devagar.
2. **Oito transições e nenhum `prefers-reduced-motion`.** Uma vitrine de vinte
   cards que "sobem" no hover é desconforto físico para quem tem distúrbio
   vestibular. WCAG 2.3.3.
3. **Quatro cores literais no `workspace.css`**, duas delas repetindo valores
   que já eram token. Cor literal fora de `tokens.css` é a que ninguém encontra
   no dia em que a marca muda.

## O que NÃO está aqui

Contraste (`test_contraste`), classe sem CSS e redefinição de classe base
(`test_classes_com_css`), ícone inexistente (`test_icones`) e ordem das faixas
(`test_posicionamento`) já têm arquivo próprio. Este cobre o que sobrava.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent.parent
TEMPLATES = RAIZ / "workspace" / "templates"
CSS = RAIZ / "workspace" / "static" / "workspace" / "src" / "workspace.css"
TOKENS = RAIZ / "workspace" / "static" / "workspace" / "src" / "tokens.css"


def _sem_comentarios_html(texto: str) -> str:
    """Tira os blocos `{% comment %}`.

    Sem isto a varredura acha `<select>` dentro de um comentário que EXPLICA por
    que o `<select>` tem opção vazia — e acusa falta de rótulo num texto."""
    return re.sub(r"{%\s*comment\s*%}.*?{%\s*endcomment\s*%}", "", texto, flags=re.DOTALL)


def _sem_comentarios_css(texto: str) -> str:
    return re.sub(r"/\*.*?\*/", "", texto, flags=re.DOTALL)


# ── Formulário ──────────────────────────────────────────────────────


def test_todo_campo_tem_rotulo_de_verdade():
    """`placeholder` não é rótulo: some quando a pessoa digita, e cada leitor de
    tela o trata de um jeito. Rótulo invisível (`au-sr`) resolve os dois."""
    sem_rotulo = []

    for caminho in TEMPLATES.rglob("*.html"):
        texto = _sem_comentarios_html(caminho.read_text(encoding="utf-8"))
        rotulados = set(re.findall(r'<label[^>]*\bfor="([^"]+)"', texto))

        for achado in re.finditer(r"<(?:input|select|textarea)\b[^>]*>", texto):
            tag = achado.group(0)
            if re.search(r'type="(hidden|checkbox|radio|submit|button)"', tag):
                continue
            if "aria-label" in tag:
                continue
            ident = re.search(r'\bid="([^"]+)"', tag)
            if ident is None:
                sem_rotulo.append(f"{caminho.name}: {' '.join(tag.split())[:70]}")
                continue
            alvo = ident.group(1)
            if alvo in rotulados:
                continue
            # `id="motivo-{{ s.pk }}"`: o rótulo usa a MESMA variável, então
            # basta o prefixo bater.
            prefixo = alvo.split("{")[0]
            if prefixo and any(r.startswith(prefixo) for r in rotulados):
                continue
            sem_rotulo.append(f"{caminho.name}: {' '.join(tag.split())[:70]}")

    assert sem_rotulo == [], f"campos sem rótulo: {sem_rotulo}"


def test_toda_imagem_tem_alt():
    """`alt=""` é resposta válida — decoração não se descreve. Ausente não é."""
    sem_alt = [
        f"{caminho.name}: {achado.group(0)[:60]}"
        for caminho in TEMPLATES.rglob("*.html")
        for achado in re.finditer(r"<img\b[^>]*>", caminho.read_text(encoding="utf-8"))
        if "alt=" not in achado.group(0)
    ]

    assert sem_alt == [], sem_alt


def test_todo_formulario_de_post_tem_um_botao_de_envio():
    """Formulário sem botão só é enviável com Enter num campo de texto — e não é
    enviável de jeito nenhum quando só tem `<select>`.

    O botão pode estar FORA do formulário, ligado por `form="id"`. É o padrão da
    bandeja: aninhar `<form>` é HTML inválido, então os formulários de decisão
    ficam depois da tabela e os botões dentro dela apontam para eles. Um teste
    que ignorasse isso empurraria o código de volta para o HTML inválido.
    """
    mudos = []
    for caminho in TEMPLATES.rglob("*.html"):
        texto = _sem_comentarios_html(caminho.read_text(encoding="utf-8"))
        ligados_por_atributo = set(re.findall(r'\bform="([^"]+)"', texto))

        for bloco in re.finditer(
            r'<form([^>]*method=["\']post["\'][^>]*)>(.*?)</form>', texto, re.DOTALL | re.I
        ):
            abertura, corpo = bloco.group(1), bloco.group(2)
            if 'type="submit"' in corpo:
                continue
            ident = re.search(r'\bid="([^"]+)"', abertura)
            if ident and ident.group(1) in ligados_por_atributo:
                continue
            mudos.append(caminho.name)

    assert mudos == [], f"formulário POST sem botão de envio: {sorted(set(mudos))}"


# ── Cor e espaçamento ───────────────────────────────────────────────


def test_nenhuma_cor_literal_fora_dos_tokens():
    """Cor escrita à mão no `workspace.css` é a que ninguém encontra no dia em
    que a marca muda — e a que não acompanha o tema escuro.

    `@media print` é a exceção declarada: papel é branco nos dois temas.
    """
    texto = _sem_comentarios_css(CSS.read_text(encoding="utf-8"))
    # Recorta o bloco de impressão, que legitimamente fixa preto e branco.
    texto = re.sub(r"@media print\s*\{.*?\n\}", "", texto, flags=re.DOTALL)

    literais = sorted(set(re.findall(r"#[0-9a-fA-F]{3,8}\b", texto)))

    assert literais == [], f"cores literais fora de tokens.css: {literais}"


def test_todo_token_de_cor_existe_no_arquivo_de_tokens():
    """`var(--au-cor-que-nao-existe)` não quebra a página: o navegador ignora a
    declaração em silêncio, e o elemento fica com a cor herdada."""
    css = CSS.read_text(encoding="utf-8")
    tokens = TOKENS.read_text(encoding="utf-8")

    usados = set(re.findall(r"var\((--au-[a-z0-9-]+)", css))
    # Os tokens moram VÁRIOS na mesma linha (`--au-1:4px; --au-2:8px;`), então a
    # busca não pode ancorar no começo da linha.
    definidos = set(re.findall(r"(--au-[a-z0-9-]+)\s*:", tokens))
    definidos |= set(re.findall(r"(--au-[a-z0-9-]+)\s*:", css))
    # `--au-cor` e `--au-cor-bg` são escritos pelo próprio CSS em classes
    # utilitárias de cor, e não vivem em `tokens.css`.
    definidos |= {"--au-cor", "--au-cor-bg"}

    assert usados - definidos == set(), (
        f"tokens usados e nunca definidos: {sorted(usados - definidos)}"
    )


# ── Movimento ───────────────────────────────────────────────────────


def test_o_movimento_respeita_a_preferencia_do_sistema():
    """WCAG 2.3.3. Uma vitrine de vinte cards que "sobem" no hover é desconforto
    físico para quem tem distúrbio vestibular, não capricho de estilo."""
    texto = CSS.read_text(encoding="utf-8")

    assert "prefers-reduced-motion" in texto, (
        "há transições no arquivo e nenhum bloco de movimento reduzido"
    )
    bloco = texto[texto.index("prefers-reduced-motion") :]
    assert "transition-duration" in bloco
    assert "transform: none" in bloco


def test_o_teclado_enxerga_o_foco():
    """Sem `:focus-visible`, navegar por Tab é navegar às cegas — e o
    `outline: none` de reset é o jeito mais rápido de chegar lá."""
    texto = _sem_comentarios_css(CSS.read_text(encoding="utf-8"))

    assert texto.count("focus-visible") >= 3

    # A regra não é "nunca remova o outline" — é "não deixe a pessoa sem
    # indicação nenhuma". Remover o contorno padrão e desenhar um anel de
    # `box-shadow` no MESMO bloco é a prática correta, e é o que o produto faz.
    sem_substituto = []
    for achado in re.finditer(r"\{[^{}]*outline:\s*none[^{}]*\}", texto):
        if "box-shadow" not in achado.group(0):
            sem_substituto.append(" ".join(achado.group(0).split())[:70])

    assert sem_substituto == [], f"foco removido sem anel no lugar: {sem_substituto}"


# ── Estado vazio ────────────────────────────────────────────────────


#: As telas de lista do produto. Cada uma precisa dizer o que fazer quando não
#: há nada — moldura em volta do nada é pior que um app launcher (ADR-012).
TELAS_DE_LISTA = (
    "workspace/servicos/minhas.html",
    "workspace/servicos/fila.html",
    "workspace/correspondencias.html",
    "workspace/custodia.html",
    "workspace/estoque.html",
    "workspace/frota.html",
    "workspace/marketing.html",
    "workspace/documentos.html",
    "workspace/relatorios/lista.html",
    "workspace/publicacoes/lista.html",
)


@pytest.mark.parametrize("template", TELAS_DE_LISTA)
def test_toda_tela_de_lista_tem_estado_vazio(template):
    """"Nenhum resultado" sem explicar o que fazer é a tela que faz a pessoa
    achar que o sistema quebrou."""
    texto = (TEMPLATES / template).read_text(encoding="utf-8")

    assert "au-vazio" in texto or "au-agenda-livre" in texto, (
        f"{template} não diz nada quando a lista está vazia"
    )


def test_o_estado_vazio_explica_o_que_fazer():
    """Título sozinho é constatação; a dica é o que transforma em instrução."""
    sem_dica = []
    for caminho in TEMPLATES.rglob("*.html"):
        texto = caminho.read_text(encoding="utf-8")
        if "au-vazio-titulo" in texto and "au-vazio-dica" not in texto:
            sem_dica.append(caminho.name)

    assert sem_dica == [], f"estado vazio sem dica: {sem_dica}"
