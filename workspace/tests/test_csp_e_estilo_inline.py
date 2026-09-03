"""A CSP depois da Onda 9.5, e o lint que passou a ser a única trava.

## Por que este arquivo existe separado

Até aqui, "nenhum `style=` em template" era garantido pelo NAVEGADOR: a CSP não
tinha `unsafe-inline`, e um estilo inline simplesmente não desenhava. O teste que
existia — quatro rotas renderizadas — era rede de segurança de uma regra que o
browser já cobrava.

`style-src` abriu (ADR-040). O navegador aceita agora. **Este arquivo é o que
sobrou cobrando**, e por isso ele varre o repositório inteiro em vez de quatro
telas: o que a biblioteca de gráficos injeta é aceito, o que nós escrevemos, não.

É isso que mantém aberta a porta de voltar atrás. No dia em que a biblioteca sair,
fechar `style-src` de novo tem de ser uma linha no settings — e não uma auditoria.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from django.conf import settings
from django.urls import reverse

RAIZ = Path(__file__).resolve().parent.parent.parent

#: `<algo … style=`. O `\s` antes evita casar `data-style=` e `au-style=`.
ESTILO_INLINE = re.compile(r"<[^>]+\sstyle=")

#: Interpolação do Django dentro de `<style>…</style>`.
#:
#: O que ele procura é conteúdo VINDO DO USUÁRIO virando CSS. Com `style-src`
#: aberta, `{{ algo }}` dentro de uma folha de estilo é injeção de CSS direta —
#: e injeção de CSS lê valor de campo com seletor de atributo e o manda para
#: fora por `background-image`.
INTERPOLACAO_EM_STYLE = re.compile(r"<style\b[^>]*>.*?\{\{.*?</style>", re.S)


def _templates() -> list[Path]:
    return [
        caminho
        for caminho in RAIZ.glob("**/templates/**/*.html")
        if ".venv" not in caminho.parts and "staticfiles" not in caminho.parts
    ]


# ── A política ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_a_csp_abriu_style_e_nao_abriu_script(client):
    """O teste que afirma a política montada, e não a intenção dela.

    Os quatro fatos que precisam ser verdade ao mesmo tempo. Qualquer um deles
    sozinho passa despercebido numa revisão.
    """
    csp = client.get(reverse("workspace:home"))["Content-Security-Policy"]
    diretivas = {
        parte.split(" ", 1)[0]: parte
        for parte in (p.strip() for p in csp.split(";"))
        if parte
    }

    assert "'unsafe-inline'" not in diretivas["script-src"], (
        "script-src abriu. Nenhuma biblioteca de gráfico precisa disso — se "
        "alguma exigir, ela sai."
    )
    assert "'nonce-" in diretivas["script-src"]
    assert "'unsafe-inline'" in diretivas["style-src"]
    # O detalhe que não pode ser errado: navegador ignora `unsafe-inline` quando
    # há nonce na MESMA diretiva. Nonce em style-src manteria o comportamento
    # antigo com a aparência de ter aberto.
    assert "'nonce-" not in diretivas["style-src"], (
        "nonce em style-src ANULA o unsafe-inline ao lado — o gráfico sairia "
        "errado em silêncio."
    )


@pytest.mark.django_db
def test_as_contrapartidas_estao_no_lugar(client):
    """Com `style-src` aberta, o vetor é injeção de CSS — e injeção de CSS
    exfiltra por `background-image`. Estas são as saídas fechadas."""
    csp = client.get(reverse("workspace:home"))["Content-Security-Policy"]

    for diretiva in (
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "frame-src 'none'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ):
        assert diretiva in csp, f"contrapartida ausente: {diretiva}"


@pytest.mark.django_db
def test_o_nonce_muda_a_cada_requisicao(client):
    """Nonce reutilizado é nonce que não serve para nada: quem o descobre uma
    vez escreve o `<script>` que quiser em toda página seguinte."""
    primeiro = client.get(reverse("workspace:home"))["Content-Security-Policy"]
    segundo = client.get(reverse("workspace:home"))["Content-Security-Policy"]

    assert primeiro != segundo


@pytest.mark.django_db
def test_o_nonce_chega_ao_template_pela_requisicao(client):
    """`request.csp_nonce`, e não um `threading.local`: o segundo sobrevive à
    requisição num servidor com pool de threads, e nonce que vaza de uma
    requisição para outra é nonce reutilizável."""
    resposta = client.get(reverse("workspace:home"))

    assert getattr(resposta.wsgi_request, "csp_nonce", "")
    assert resposta.wsgi_request.csp_nonce in resposta["Content-Security-Policy"]


def test_o_molde_da_csp_nao_tem_unsafe_eval_em_lugar_nenhum():
    """`unsafe-eval` não entrou e não entra. Biblioteca que precise dele
    interpreta string como código — e a string vem de um JSON do servidor."""
    assert "unsafe-eval" not in settings.SEGURANCA_CSP_MOLDE


# ── O lint ──────────────────────────────────────────────────────────


def test_nenhum_template_nosso_escreve_style():
    """O que a biblioteca injeta é aceito; o que nós escrevemos, não.

    Varre o REPOSITÓRIO, e não quatro rotas renderizadas. A versão anterior
    cobria quatro telas de trinta e cinco — e cobria porque o navegador fazia o
    resto do trabalho. Ele não faz mais.
    """
    culpados = {}
    for template in _templates():
        achados = ESTILO_INLINE.findall(template.read_text(encoding="utf-8"))
        if achados:
            culpados[str(template.relative_to(RAIZ))] = achados[:3]

    assert not culpados, (
        "estilo inline em template nosso:\n"
        + "\n".join(f"  {t}: {a}" for t, a in culpados.items())
        + "\n\nA CSP não cobra mais isso — este teste cobra. Desenhe em SVG, "
        "onde `width` e `height` são atributos, ou use uma classe."
    )


def test_nenhum_template_interpola_dentro_de_style():
    """Conteúdo vindo do usuário dentro de `<style>` é injeção de CSS direta.

    E injeção de CSS não é enfeite: um seletor de atributo com
    `background-image: url(...)` lê o valor de um campo e o manda para um
    domínio externo, caractere por caractere. `img-src 'self' data:` fecha a
    saída; esta regra fecha a entrada.
    """
    culpados = [
        str(t.relative_to(RAIZ))
        for t in _templates()
        if INTERPOLACAO_EM_STYLE.search(t.read_text(encoding="utf-8"))
    ]

    assert not culpados, f"interpolação dentro de <style>: {culpados}"


def test_o_lint_varre_o_repositorio_inteiro_e_nao_um_punhado():
    """O teste do teste.

    Sem isto, um `glob` que pare de casar — uma pasta renomeada, um `**` a menos
    — faria o lint passar varrendo zero arquivo, verde e inútil.
    """
    achados = _templates()

    assert len(achados) > 60, f"o lint achou só {len(achados)} templates"
    nomes = {t.name for t in achados}
    assert "home.html" in nomes
    assert "entrar.html" in nomes, "o lint precisa alcançar os templates de contas"
