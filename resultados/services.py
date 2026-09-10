"""As contas que o espelho sabe fazer — e a que ele se recusa a congelar.

O app guarda o que veio de fora. O que ele **calcula** é o pouco que só faz
sentido em cima do conjunto: a layer de um contrato e a consolidação de um
escopo. Nada disso é campo, e o motivo é o mesmo nos dois casos: o valor muda
quando o mês vira, sem ninguém carregar nada.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db.models import Count, Q, Sum

from .models import CompetenciaResultado, Contrato

# ── Layer ───────────────────────────────────────────────────────────

#: Faixas de ROB de 6 meses, do benchmark. Layer não é rótulo: ela converte
#: porte em OBRIGAÇÃO — Layer 3 deve apresentação de resultado, as outras não.
TETO_LAYER_1 = Decimal("300000")
TETO_LAYER_2 = Decimal("600000")

#: Meses de ROB necessários para o contrato ser avaliado. Abaixo disto ele não
#: recebe Layer 1: recebe "sem amostra".
#:
#: A diferença decide comportamento. Layer 1 quer dizer "pequeno, e por isso
#: não deve apresentação"; "sem amostra" quer dizer "ainda não dá para saber".
#: Chamar o segundo de primeiro faria um contrato novo de R$ 90 mil/mês nascer
#: dispensado da obrigação que ele provavelmente terá em março.
MESES_MINIMOS = 2

SEM_AMOSTRA = "sem_amostra"

MESES_DA_ROB = 6


@dataclass(frozen=True)
class Layer:
    valor: str
    rob: Decimal
    meses: int

    @property
    def tem_amostra(self) -> bool:
        return self.valor != SEM_AMOSTRA

    @property
    def deve_apresentacao(self) -> bool:
        """Só a Layer 3. "Sem amostra" NÃO deve — e é de propósito.

        Cobrar apresentação de um contrato de um mês seria cobrar de quem ainda
        não tem o que apresentar. A pendência dele é ganhar histórico.
        """
        return self.valor == "3"

    def __str__(self) -> str:
        return "sem amostra" if not self.tem_amostra else f"Layer {self.valor}"


def layer_de(contrato: Contrato, ate: date | None = None) -> Layer:
    """A layer deste contrato pela ROB dos últimos seis meses.

    Calculada e não gravada. Gravada, ela seria a resposta do dia da carga: um
    contrato que cresceu em julho continuaria Layer 1 até alguém rodar o cálculo
    de novo, e nada na tela diria que o rótulo está velho.
    """
    linhas = _janela_de_rob(contrato, ate)
    meses = len(linhas)
    rob = sum((linha.receita_bruta for linha in linhas), Decimal("0"))

    if meses < MESES_MINIMOS:
        return Layer(SEM_AMOSTRA, rob, meses)
    if rob <= TETO_LAYER_1:
        return Layer("1", rob, meses)
    if rob <= TETO_LAYER_2:
        return Layer("2", rob, meses)
    return Layer("3", rob, meses)


def _janela_de_rob(contrato: Contrato, ate: date | None):
    """As competências dos últimos seis meses, mais recente primeiro.

    Conta MESES COM LANÇAMENTO, não meses de calendário. Um contrato que existe
    há um ano e teve receita em dois meses tem dois meses de amostra, e não
    doze — a pergunta é quanto ele fatura, não há quanto tempo ele existe.
    """
    consulta = CompetenciaResultado.objects.filter(contrato=contrato)
    if ate is not None:
        # `Q` e não dois querysets com `|`: combinar querysets duplica o JOIN e
        # a contagem sai errada — e aqui a contagem É a regra da amostra.
        consulta = consulta.filter(
            Q(ano__lt=ate.year) | Q(ano=ate.year, mes__lte=ate.month)
        )
    return list(consulta.order_by("-ano", "-mes")[:MESES_DA_ROB])


def margem_pct(linhas) -> Decimal | None:
    """Margem de contribuição sobre receita, em pontos percentuais.

    `None` quando não há receita. Não é zero: margem de zero sobre receita zero
    é uma divisão que ninguém pediu, e mostrá-la como "0%" faria um contrato sem
    lançamento aparecer no bloco de deficitários.
    """
    receita = sum((l.receita_bruta for l in linhas), Decimal("0"))
    if receita <= 0:
        return None
    mc = sum(
        (x.margem_contribuicao for x in linhas if x.margem_contribuicao is not None),
        Decimal("0"),
    )
    return (mc / receita * 100).quantize(Decimal("0.01"))


# ── Consolidação ────────────────────────────────────────────────────


def consolidar(consulta, competencia: date | None = None) -> dict:
    """Soma um recorte. Devolve também a CONTAGEM de linhas.

    A contagem é o que separa "deu zero" de "não tem dado" — duas leituras
    opostas com a mesma aparência num painel.
    """
    if competencia is not None:
        consulta = consulta.filter(ano=competencia.year, mes=competencia.month)

    agregado = consulta.aggregate(
        receita=Sum("receita_bruta"),
        mc=Sum("margem_contribuicao"),
        ebitda=Sum("ebitda"),
        linhas=Count("pk"),
    )
    return {
        "receita_bruta": agregado["receita"] or Decimal("0"),
        "margem_contribuicao": agregado["mc"] or Decimal("0"),
        "ebitda": agregado["ebitda"] or Decimal("0"),
        "linhas": agregado["linhas"] or 0,
    }
