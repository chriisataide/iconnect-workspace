"""O PDF do relatório de campo — §35 e §36.

## Por que `reportlab` e não `weasyprint`

A alternativa converteria a mesma página HTML que já existe, e o documento
sairia idêntico à tela. Foi recusada pelo DEPLOY: `weasyprint` exige Cairo,
Pango e GDK-PixBuf instalados no sistema operacional — bibliotecas C que
precisam entrar na imagem, versionar junto e quebrar quando a base muda.

`reportlab` é Python puro: instala por wheel e a mesma imagem que roda o Django
roda o PDF. O preço é desenhar o layout em código, e é o que este módulo faz —
uma vez, aqui, em vez de espalhado.

## O documento, e o que ele precisa provar

Relatório de ocorrência é peça que sai da empresa e que alguém lê meses depois
para entender o que aconteceu. Três coisas são obrigatórias e não são
decoração:

1. **Numeração "página X de Y"** — sem ela, uma folha extraviada não denuncia a
   falta. É a razão de o documento ser montado em duas passadas.
2. **Data e hora da emissão no rodapé de toda página** — a versão do papel na
   mão de alguém tem de ser identificável.
3. **A marca de RASCUNHO por cima**, quando não emitido. Rascunho impresso sem
   marca vira documento definitivo na mesa de quem recebeu.
"""

from __future__ import annotations

from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

from workspace.models.relatorio import Relatorio
from workspace.services import relatorio as rel

MARGEM = 20 * mm
#: Sobra reservada para o rodapé. Sem ela o último parágrafo encosta na
#: numeração e o PDF sai com texto por cima de texto.
RODAPE = 16 * mm

TINTA = colors.HexColor("#0f172a")
APAGADO = colors.HexColor("#64748b")
LINHA = colors.HexColor("#cbd5e1")


def _estilos() -> dict:
    """Os estilos do documento.

    Helvetica e não fonte embarcada: ela é uma das 14 fontes que TODO leitor de
    PDF tem, então o arquivo abre igual em qualquer lugar e não carrega 300 KB
    de tipografia. Acentuação do português cabe no WinAnsi que o reportlab usa
    por padrão — testado, não suposto.
    """
    base = getSampleStyleSheet()
    return {
        "tipo": ParagraphStyle(
            "tipo", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=8, textColor=APAGADO, spaceAfter=2, leading=10,
        ),
        "titulo": ParagraphStyle(
            "titulo", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=17, textColor=TINTA, spaceAfter=10, leading=21,
        ),
        "rotulo": ParagraphStyle(
            "rotulo", parent=base["Normal"], fontName="Helvetica-Bold",
            fontSize=8.5, textColor=APAGADO, spaceAfter=3, leading=11,
        ),
        "texto": ParagraphStyle(
            "texto", parent=base["Normal"], fontName="Helvetica",
            fontSize=10, textColor=TINTA, leading=15, spaceAfter=12,
        ),
        "assinatura": ParagraphStyle(
            "assinatura", parent=base["Normal"], fontName="Helvetica",
            fontSize=9, textColor=APAGADO, alignment=TA_CENTER, leading=12,
        ),
    }


class _CanvasNumerado(Canvas):
    """O canvas que sabe escrever "página 3 de 7".

    O total só existe depois de montar o documento inteiro, e o rodapé é
    desenhado ANTES — em cada página, na hora em que ela fecha. A saída é
    guardar o estado de cada página em memória e só escrever tudo no `save()`,
    quando a contagem já é conhecida.

    Tentei antes com `multiBuild`, supondo que ele monta duas vezes. Não monta:
    ele só repassa quando há *indexing flowables* (sumário, índice remissivo).
    Sem eles roda uma vez só, e o rodapé saía "Página 1" sem o total — o que
    derruba justamente a garantia que a numeração existe para dar, que é uma
    folha extraviada denunciar a falta.
    """

    def __init__(self, *args, relatorio: Relatorio, **kwargs):
        super().__init__(*args, **kwargs)
        self.relatorio = relatorio
        self._paginas: list[dict] = []

    def showPage(self):  # noqa: N802 - assinatura do reportlab
        # Guarda em vez de emitir: emitir agora fecharia a página sem o total.
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self._decorar(total)
            super().showPage()
        super().save()

    def _decorar(self, total: int) -> None:
        self.saveState()
        self._rodape(total)
        if not self.relatorio.emitido:
            self._marca_dagua()
        self.restoreState()

    def _rodape(self, total: int) -> None:
        self.setStrokeColor(LINHA)
        self.setLineWidth(0.5)
        self.line(MARGEM, MARGEM + RODAPE - 4 * mm, A4[0] - MARGEM, MARGEM + RODAPE - 4 * mm)

        self.setFont("Helvetica", 7.5)
        self.setFillColor(APAGADO)
        emitido = self.relatorio.emitido_em or timezone.now()
        self.drawString(
            MARGEM, MARGEM + RODAPE - 9 * mm,
            f"{self.relatorio.titulo} · "
            f"{timezone.localtime(emitido).strftime('%d/%m/%Y %H:%M')}",
        )
        self.drawRightString(
            A4[0] - MARGEM, MARGEM + RODAPE - 9 * mm,
            f"Página {self._pageNumber} de {total}",
        )

    def _marca_dagua(self) -> None:
        """RASCUNHO em diagonal. Impresso sem isto, um rascunho vira documento
        definitivo na mesa de quem recebeu."""
        self.saveState()
        self.setFont("Helvetica-Bold", 68)
        self.setFillColor(colors.HexColor("#e2e8f0"))
        self.translate(A4[0] / 2, A4[1] / 2)
        self.rotate(50)
        self.drawCentredString(0, 0, "RASCUNHO")
        self.restoreState()


class _Documento(BaseDocTemplate):
    """A moldura: uma página A4 com margem e espaço reservado para o rodapé."""

    def __init__(self, buffer, **kwargs):
        super().__init__(buffer, pagesize=A4, **kwargs)
        quadro = Frame(
            MARGEM, MARGEM + RODAPE,
            A4[0] - 2 * MARGEM, A4[1] - 2 * MARGEM - RODAPE,
            id="corpo", showBoundary=0,
        )
        self.addPageTemplates([PageTemplate(id="folha", frames=[quadro])])


def _escapar(texto) -> str:
    """`Paragraph` interpreta um subconjunto de HTML.

    Sem escapar, um relatório que descreve "switch <porta 3> queimou" perde o
    trecho — e, pior, um `<` sem par faz o reportlab levantar no meio da
    geração, transformando um texto legítimo em erro 500.
    """
    from django.utils.html import escape

    return escape(str(texto)).replace("\n", "<br/>")


def _cabecalho(relatorio: Relatorio, estilos: dict) -> list:
    return [
        Paragraph(relatorio.get_tipo_display().upper(), estilos["tipo"]),
        Paragraph(_escapar(relatorio.titulo), estilos["titulo"]),
    ]


def _ficha(relatorio: Relatorio) -> Table:
    """Os dados de identificação, em duas colunas.

    Tabela e não parágrafos: cliente, local, data e responsável são campos de
    FICHA — quem procura um deles procura pela posição, não lendo o texto.
    """
    quando = relatorio.ocorrido_em.strftime("%d/%m/%Y")
    if relatorio.horario:
        quando += f" · {relatorio.horario.strftime('%H:%M')}"

    linhas = [("Ocorrido em", quando)]
    if relatorio.cliente:
        linhas.append(("Cliente", relatorio.cliente))
    if relatorio.local:
        linhas.append(("Local", relatorio.local))
    linhas.append(
        ("Responsável", relatorio.autor.get_full_name() or relatorio.autor.email)
    )
    if relatorio.emitido_em:
        linhas.append(
            ("Emitido em", timezone.localtime(relatorio.emitido_em).strftime("%d/%m/%Y %H:%M"))
        )

    tabela = Table(
        [[r, v] for r, v in linhas],
        colWidths=[35 * mm, A4[0] - 2 * MARGEM - 35 * mm],
        hAlign="LEFT",
    )
    tabela.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), APAGADO),
            ("TEXTCOLOR", (1, 0), (1, -1), TINTA),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("LINEBELOW", (0, -1), (-1, -1), 1, TINTA),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
        ])
    )
    return tabela


def _assinatura(relatorio: Relatorio, estilos: dict) -> list:
    """Só no emitido. Assinar rascunho é assinar documento que ainda vai mudar."""
    if not relatorio.emitido:
        return []

    risco = Table([[""]], colWidths=[80 * mm], rowHeights=[0.1])
    risco.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.7, TINTA)]))
    return [
        Spacer(1, 22 * mm),
        risco,
        Spacer(1, 2 * mm),
        Paragraph(
            _escapar(relatorio.autor.get_full_name() or relatorio.autor.email),
            estilos["assinatura"],
        ),
    ]


def gerar(relatorio: Relatorio) -> bytes:
    """O PDF do relatório, em memória.

    Devolve `bytes` e não escreve arquivo: o documento é derivado — sai do banco
    a cada pedido e reflete o estado atual. Guardar um PDF ao emitir criaria uma
    segunda verdade que envelhece, e é a que alguém encontraria depois.
    """
    estilos = _estilos()
    buffer = BytesIO()
    documento = _Documento(buffer)

    historia: list = [*_cabecalho(relatorio, estilos), _ficha(relatorio), Spacer(1, 8 * mm)]

    for linha in rel.para_impressao(relatorio):
        # `KeepTogether` para o rótulo não ficar órfão no pé da página, separado
        # do texto que ele nomeia — o defeito clássico de relatório longo.
        historia.append(
            KeepTogether([
                Paragraph(_escapar(linha["rotulo"]).upper(), estilos["rotulo"]),
                Paragraph(_escapar(linha["valor"]), estilos["texto"]),
            ])
        )

    evidencias = list(relatorio.evidencias.all())
    if evidencias:
        historia.append(Paragraph("EVIDÊNCIAS", estilos["rotulo"]))
        historia.append(
            Paragraph(
                "<br/>".join(
                    _escapar(f"• {e.nome_original}" + (f" — {e.legenda}" if e.legenda else ""))
                    for e in evidencias
                ),
                estilos["texto"],
            )
        )

    historia.extend(_assinatura(relatorio, estilos))

    # O canvas numerado guarda as páginas e só escreve no fim, quando o total
    # já é conhecido — ver `_CanvasNumerado`.
    documento.build(
        historia,
        canvasmaker=lambda *a, **k: _CanvasNumerado(*a, relatorio=relatorio, **k),
    )
    return buffer.getvalue()


def nome_do_arquivo(relatorio: Relatorio) -> str:
    """`relatorio-de-entrega-2026-08-18-farol.pdf`.

    Nome legível e não o id: o arquivo vai para a pasta de downloads de alguém e
    para o e-mail de um cliente, e `12.pdf` é o que ninguém acha depois.
    """
    from django.utils.text import slugify

    pedaco = slugify(relatorio.titulo)[:60] or "relatorio"
    return f"{relatorio.tipo}-{relatorio.ocorrido_em:%Y-%m-%d}-{pedaco}.pdf"
