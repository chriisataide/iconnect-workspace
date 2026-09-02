"""O PDF da Apresentação de Resultados.

Reaproveita o mesmo `reportlab` do relatório de campo, e pela mesma razão que
está escrita lá: `weasyprint` exigiria Cairo, Pango e GDK-PixBuf na imagem, e
o preço de desenhar o layout em código é menor que o de versionar bibliotecas C.

## O que este PDF NÃO leva

**Nenhum dado pessoal.** Nem nome de quem respondeu a pesquisa, nem nome de
colaborador, nem folha individual. O que sai são números agregados, contratos e
contagens.

O documento sai do prédio: vai para a pasta de downloads de alguém, para um
grupo de WhatsApp e para o anexo de um e-mail que ninguém audita. É o pior lugar
possível para um CPF, e o melhor lugar possível para alguém colar um sem pensar.

## E o que ele leva de propósito

**O carimbo de cada faixa.** Um PDF sem procedência é a pior versão do problema
que o carimbo existe para resolver: ele é lido dias depois, longe da tela, sem
como conferir se o número era de ontem ou de três semanas atrás.
"""

from __future__ import annotations

from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from workspace.services.pdf import APAGADO, LINHA, TINTA, _escapar, _estilos

MARGEM = 14 * mm

MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


def gerar(panorama: dict) -> bytes:
    """O PDF da competência, em memória.

    `bytes` e não arquivo: o documento é derivado e sai do banco a cada pedido.
    Guardar um PDF criaria uma segunda verdade que envelhece — e é a que alguém
    encontraria depois.
    """
    estilos = _estilos()
    buffer = BytesIO()
    # Paisagem: a dinâmica de seis colunas não cabe em retrato sem encolher a
    # fonte a um tamanho que ninguém lê numa reunião.
    documento = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=MARGEM, rightMargin=MARGEM,
        topMargin=MARGEM, bottomMargin=MARGEM,
        title="Apresentação de Resultados",
    )

    filtros = panorama["filtros"]
    competencia = filtros.competencia
    historia: list = [
        Paragraph("APRESENTAÇÃO DE RESULTADOS", estilos["titulo"]),
        Paragraph(
            _escapar(
                f"Competência de {MESES[competencia.month - 1]} de {competencia.year}"
                + ("" if panorama["escopo_total"] else " · recorte do seu escopo")
            ),
            estilos["texto"],
        ),
        Paragraph(
            _escapar(f"Emitido em {timezone.localtime():%d/%m/%Y %H:%M}"),
            estilos["texto"],
        ),
        Spacer(1, 6 * mm),
    ]

    destaques = panorama["destaques"]
    if destaques.disponivel:
        historia.append(Paragraph("DESTAQUES", estilos["rotulo"]))
        historia.append(_tabela_destaques(destaques.conteudo["cartoes"]))
        historia.append(Spacer(1, 5 * mm))

    for faixa in panorama["faixas"]:
        historia.extend(_faixa(faixa, estilos))

    documento.build(historia)
    return buffer.getvalue()


def _faixa(faixa, estilos) -> list:
    """Uma faixa: título, carimbo e o pouco que cabe em papel.

    O PDF é um RESUMO, e não a tela impressa. A tela tem tabela de treze meses e
    lista de dezoito contratos; no papel isso vira dez páginas que ninguém lê. O
    que fica é o que muda decisão.
    """
    carimbo = faixa.carimbo
    blocos = [
        Paragraph(_escapar(faixa.titulo.upper()), estilos["rotulo"]),
        Paragraph(
            _escapar(carimbo.texto + (f" · {carimbo.motivo}" if carimbo.motivo else "")),
            estilos["texto"],
        ),
    ]

    if not faixa.disponivel:
        blocos.append(Paragraph(_escapar(f"— {faixa.motivo}"), estilos["texto"]))
        return [KeepTogether(blocos), Spacer(1, 4 * mm)]

    tabela = _resumo(faixa)
    if tabela is not None:
        blocos.append(tabela)
    return [KeepTogether(blocos), Spacer(1, 4 * mm)]


def _resumo(faixa):
    conteudo = faixa.conteudo
    if faixa.chave == "dinheiro":
        totais = conteudo["totais"]
        return _tabela(
            ["Receita bruta", "Impostos", "Margem de contribuição", "EBITDA"],
            [[
                _dinheiro(totais["receita_bruta"]),
                _dinheiro(totais["impostos"]),
                _dinheiro(totais["margem_contribuicao"])
                + _pct(totais["margem_pct"]),
                _dinheiro(totais["ebitda"]) + _pct(totais["ebitda_pct"]),
            ]],
        )
    if faixa.chave == "contratos":
        return _tabela(
            ["Contratos", "Valor mensal", "Deficitários", "Abaixo de 10%"],
            [[
                str(conteudo["quantidade"]),
                _dinheiro(conteudo["valor_mensal"]),
                str(len(conteudo["deficitarios"])),
                str(len(conteudo["abaixo_da_margem"])),
            ]],
        )
    if faixa.chave == "vencimentos":
        return _tabela(
            [f"Até {b['dias']} dias" for b in conteudo["blocos"]],
            [[str(len(b["contratos"])) for b in conteudo["blocos"]]],
        )
    if faixa.chave == "projetos":
        return _tabela(
            ["Bloqueados", "Marcos em risco", "Parados"],
            [[
                str(len(conteudo["bloqueados"])),
                str(len(conteudo["marcos_em_risco"])),
                str(len(conteudo["parados"])),
            ]],
        )
    if faixa.chave == "pessoas":
        quadro = conteudo.get("quadro")
        if quadro is None:
            return None
        # Efetivo, turnover e absenteísmo — AGREGADOS. Nome de colaborador não
        # entra aqui em hipótese nenhuma, e por isso a tabela por centro de
        # custo da tela também não vem: ela nomeia o CC, e num PDF que circula
        # o CC identifica a equipe.
        return _tabela(
            ["Efetivo", "Admissões", "Rescisões", "Turnover", "Absenteísmo"],
            [[
                str(quadro.efetivo_ativo), str(quadro.admissoes),
                str(quadro.rescisoes), f"{quadro.turnover_pct}%",
                f"{quadro.absenteismo_pct}%",
            ]],
        )
    if faixa.chave == "satisfacao":
        contagem = conteudo["contagem"]
        # A CONTAGEM de detratores, e não a lista. A lista traz comentário de
        # cliente, e comentário de cliente num PDF que circula é o cliente
        # descobrindo o que a empresa achou da reclamação dele.
        return _tabela(
            ["Promotores", "Neutros", "Detratores", "Sem tratativa"],
            [[
                str(contagem["promotor"]), str(contagem["neutro"]),
                str(contagem["detrator"]), str(len(conteudo["sem_tratativa"])),
            ]],
        )
    return None


def _tabela_destaques(cartoes) -> Table:
    return _tabela(
        ["Ponto de atenção", "Valor", "Detalhe"],
        [[c.titulo, c.valor, c.detalhe] for c in cartoes],
    )


def _tabela(cabecalho: list[str], linhas: list[list[str]]) -> Table:
    tabela = Table([cabecalho, *linhas], hAlign="LEFT")
    tabela.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("TEXTCOLOR", (0, 0), (-1, 0), APAGADO),
            ("TEXTCOLOR", (0, 1), (-1, -1), TINTA),
            ("LINEBELOW", (0, 0), (-1, 0), 0.4, LINHA),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ])
    )
    return tabela


def _dinheiro(valor) -> str:
    return f"R$ {valor:,.2f}".replace(",", "·").replace(".", ",").replace("·", ".")


def _pct(valor) -> str:
    return f"  ({valor}%)" if valor is not None else ""


def nome_do_arquivo(competencia) -> str:
    """`resultados-2026-08.pdf` — legível, e ordenável por nome."""
    return f"resultados-{competencia:%Y-%m}.pdf"
