"""O PAINEL DA EMPRESA — §I1. A camada acima de `/resultados/`.

`painel_empresa` e não `painel`: `services/painel.py` já existe e é outra coisa
— os contadores do trilho e dos cards da home (§50). Reusar o nome apagaria
aquele módulo, e o trilho pararia de contar sem ninguém ligar as duas coisas.

## O que ele NÃO é

**Não é a tela 10 com outro nome.** Aqui só entra o que responde uma pergunta de
EMPRESA, e todo bloco leva ao detalhe em `/resultados/` com o filtro já
aplicado. Indicador que não leva a lugar nenhum é decoração — e decoração numa
tela executiva é o que faz ela parar de ser aberta.

**Não é `/workspace/indicadores/`.** Aquela tela mede SLA de solicitações, e
continua onde está. Trocar a rota dela para dar o nome bonito a esta quebraria
link compartilhado, favorito e teste para ganhar uma palavra. O que resolve a
ambiguidade é o RÓTULO, e não a estrutura — foi o que resolveu `/marketing/`.

## Toda comparação é DUPLA

Mês anterior E mesmo mês do ano anterior. Uma só induz a erro num negócio com
sazonalidade: dezembro contra novembro diz uma coisa, dezembro contra dezembro
diz outra, e quem vê só a primeira decide sobre um efeito de calendário.

## Nove blocos, e o teto é o produto

A décima informação sempre parece necessária. É ela que faz o CEO parar de abrir
a tela — e uma tela que ninguém abre não tem indicador nenhum.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from workspace.graficos import formato as fmt
from workspace.providers import resultados as contrato
from workspace.services.resultados import (
    FAIXAS_DE_VENCIMENTO,
    MARGEM_MINIMA,
    SemResultados,
    escopo_de,
    tem_acesso_a_pessoas,
    tem_acesso_a_satisfacao,
)

#: Quantos meses a curva mostra. Vinte e quatro: é o que deixa ver o mesmo mês
#: do ano passado ao lado do atual sem obrigar a rolar.
MESES_DA_CURVA = 24

#: Quantos clientes entram na conta de dependência. Cinco — o número que se cita
#: em conselho, e o que ainda cabe numa frase.
MAIORES_CLIENTES = 5

#: A partir de quanto a dependência dos cinco maiores vira alerta.
DEPENDENCIA_ATENCAO = Decimal("50")
DEPENDENCIA_CRITICA = Decimal("70")


@dataclass
class Numero:
    """Um dos cinco números, com as DUAS comparações."""

    chave: str
    titulo: str
    valor: str
    #: Variação em relação ao mês anterior e ao mesmo mês do ano anterior.
    #: `None` quando não há com que comparar — e `None` não é zero.
    contra_mes: Decimal | None = None
    contra_ano: Decimal | None = None
    url: str = ""
    #: `True` quando cair é bom (turnover, por exemplo). Decide a cor da seta.
    menor_melhor: bool = False


@dataclass
class LinhaDeArea:
    codigo: str
    nome: str
    receita: Decimal
    margem: Decimal | None
    farol: object
    url: str
    contratos: int = 0


@dataclass
class Painel:
    numeros: list[Numero] = field(default_factory=list)
    areas: list[LinhaDeArea] = field(default_factory=list)
    curva: object = None
    dependencia: dict = field(default_factory=dict)
    vencimentos: list[dict] = field(default_factory=list)
    pessoas: dict = field(default_factory=dict)
    projetos: dict = field(default_factory=dict)
    satisfacao: dict = field(default_factory=dict)
    competencia: date | None = None


def montar(pessoa, competencia: date | None = None, cache: dict | None = None) -> Painel:
    """Os nove blocos. Levanta `SemResultados` — 403, nunca tela zerada.

    Reusa `escopo_de` da tela 10: o painel é a mesma pergunta num grão maior, e
    um segundo caminho de escopo aqui daria à empresa duas respostas para "quem
    vê o quê".
    """
    escopo = escopo_de(pessoa, cache=cache)
    hoje = timezone.localdate()
    competencia = competencia or date(hoje.year, hoje.month, 1)

    financeiro = contrato.obter(contrato.ProvedorResultadoFinanceiro)
    carteira_prov = contrato.obter(contrato.ProvedorCarteira)

    painel = Painel(competencia=competencia)
    serie = (
        financeiro.serie_competencia(escopo, _recuar(competencia, MESES_DA_CURVA - 1), _fim(competencia))
        if financeiro
        else []
    )
    carteira = carteira_prov.contratos(escopo, competencia) if carteira_prov else []

    painel.numeros = _cinco_numeros(serie, carteira, competencia)
    painel.areas = _semaforo_por_area(carteira, competencia)
    painel.curva = _curva(serie)
    painel.dependencia = _dependencia(carteira)
    painel.vencimentos = _vencimentos(carteira_prov, escopo)
    if tem_acesso_a_pessoas(pessoa, cache=cache):
        painel.pessoas = _pessoas(escopo, competencia)
    painel.projetos = _projetos(escopo)
    if tem_acesso_a_satisfacao(pessoa, cache=cache):
        painel.satisfacao = _satisfacao(escopo, competencia)
    return painel


# ── 1 · Os cinco números ────────────────────────────────────────────


def _cinco_numeros(serie, carteira, competencia: date) -> list[Numero]:
    do_mes = _no_mes(serie, competencia)
    mes_anterior = _no_mes(serie, _recuar(competencia, 1))
    ano_anterior = _no_mes(serie, _recuar(competencia, 12))

    def receita(linhas):
        return sum((x.receita_bruta or Decimal("0")) for x in linhas)

    def margem(linhas):
        # SÓ as linhas com contrato — a mesma definição do cartão da tela 10.
        # Somar o rateio daria margem depois do indireto, que tem outro nome.
        com_contrato = [x for x in linhas if x.contrato]
        base = receita(com_contrato)
        if not base:
            return None
        mc = sum((x.margem_contribuicao or Decimal("0")) for x in com_contrato)
        return (mc / base * 100).quantize(Decimal("0.1"))

    def ebitda(linhas):
        return sum((x.ebitda or Decimal("0")) for x in linhas)

    base = reverse("workspace:resultados")
    mes = f"?mes={competencia:%Y-%m}"
    valor_carteira = sum((c.valor_mensal for c in carteira), Decimal("0"))

    return [
        Numero(
            "receita", "Receita bruta", fmt.moeda_curta(receita(do_mes)),
            _variacao(receita(do_mes), receita(mes_anterior)),
            _variacao(receita(do_mes), receita(ano_anterior)),
            url=f"{base}{mes}#dinheiro",
        ),
        Numero(
            "margem", "Margem de contribuição",
            fmt.percentual(margem(do_mes)) if margem(do_mes) is not None else fmt.VAZIO,
            _pontos(margem(do_mes), margem(mes_anterior)),
            _pontos(margem(do_mes), margem(ano_anterior)),
            url=f"{base}{mes}#dinheiro",
        ),
        Numero(
            "ebitda", "EBITDA", fmt.moeda_curta(ebitda(do_mes)),
            _variacao(ebitda(do_mes), ebitda(mes_anterior)),
            _variacao(ebitda(do_mes), ebitda(ano_anterior)),
            url=f"{base}{mes}#dinheiro",
        ),
        Numero(
            "carteira", "Carteira mensal", fmt.moeda_curta(valor_carteira),
            url=f"{base}{mes}#contratos",
        ),
        Numero(
            "contratos", "Contratos ativos", str(len(carteira)),
            url=f"{base}{mes}#contratos",
        ),
    ]


# ── 2 · O semáforo por área ─────────────────────────────────────────


def _semaforo_por_area(carteira, competencia: date) -> list[LinhaDeArea]:
    """Uma linha por área, e clicar leva ao detalhe com o filtro aplicado."""
    from workspace.graficos import series as g

    por_area: dict[tuple[str, str], list] = {}
    for c in carteira:
        chave = (c.area or "sem-area", c.area_nome or "Sem área")
        por_area.setdefault(chave, []).append(c)

    base = reverse("workspace:resultados")
    linhas = []
    for (codigo, nome), contratos in sorted(por_area.items()):
        margens = [
            c.margem_contribuicao_pct
            for c in contratos
            if c.margem_contribuicao_pct is not None
        ]
        # MEDIANA e não média: uma área com um contrato muito grande e vários
        # pequenos teria a média puxada pelo maior, e o farol diria que a área
        # está bem quando a maioria dos contratos dela não está.
        media = _mediana(margens)
        linhas.append(
            LinhaDeArea(
                codigo=codigo,
                nome=nome,
                receita=sum((c.valor_mensal for c in contratos), Decimal("0")),
                margem=media,
                farol=g.farol(
                    media, critico=MARGEM_MINIMA, atencao=MARGEM_MINIMA * 2
                ),
                url=f"{base}?mes={competencia:%Y-%m}&area={codigo}",
                contratos=len(contratos),
            )
        )
    return sorted(linhas, key=lambda linha: -linha.receita)


# ── 3 · A curva de 24 meses ─────────────────────────────────────────


def _curva(serie):
    from workspace.graficos import series as g

    if not serie:
        return None
    por_mes: dict[str, Decimal] = {}
    ordem: list[str] = []
    for linha in serie:
        rotulo = f"{linha.mes:02d}/{str(linha.ano)[2:]}"
        if rotulo not in por_mes:
            por_mes[rotulo] = Decimal("0")
            ordem.append(rotulo)
        por_mes[rotulo] += linha.receita_bruta or Decimal("0")
    return g.serie_temporal(
        [(rotulo, por_mes[rotulo]) for rotulo in ordem],
        chave="curva",
        titulo=f"Receita, {len(ordem)} meses",
    )


# ── 4 · Dependência de cliente ──────────────────────────────────────


def _dependencia(carteira) -> dict:
    """Quanto da receita depende dos cinco maiores clientes.

    ## Por que "dependência" e não "concentração"

    `Concentracao` já é a curadoria da diretoria — o que a empresa decidiu
    olhar (§E1). Duas coisas com o mesmo nome nas duas telas que linkam uma
    para a outra é o defeito que `/marketing/` já pagou uma vez.
    """
    from workspace.graficos import series as g

    total = sum((c.valor_mensal for c in carteira), Decimal("0"))
    if not total:
        return {}

    por_cliente: dict[str, Decimal] = {}
    for c in carteira:
        por_cliente[c.nome_cliente] = por_cliente.get(
            c.nome_cliente, Decimal("0")
        ) + c.valor_mensal
    maiores = sorted(por_cliente.items(), key=lambda par: -par[1])[:MAIORES_CLIENTES]
    peso = (sum(v for _, v in maiores) / total * 100).quantize(Decimal("0.1"))

    return {
        "percentual": peso,
        "clientes": [
            {"nome": nome, "valor": valor, "pct": (valor / total * 100).quantize(Decimal("0.1"))}
            for nome, valor in maiores
        ],
        # `menor_melhor`: aqui, depender MENOS é estar melhor.
        "farol": g.farol(
            peso,
            critico=DEPENDENCIA_CRITICA,
            atencao=DEPENDENCIA_ATENCAO,
            maior_melhor=False,
        ),
        "total": total,
    }


# ── 5 a 8 · Vencimentos, pessoas, projetos e satisfação ─────────────


def _vencimentos(provedor, escopo) -> list[dict]:
    if provedor is None:
        return []
    base = reverse("workspace:resultados")
    faixas, ja_vistos = [], set()
    for dias in FAIXAS_DE_VENCIMENTO:
        contratos = [
            c for c in provedor.vencimentos(escopo, dias) if c.codigo not in ja_vistos
        ]
        ja_vistos |= {c.codigo for c in contratos}
        faixas.append(
            {
                "dias": dias,
                "quantos": len(contratos),
                "valor": sum((c.valor_mensal for c in contratos), Decimal("0")),
                "url": f"{base}#vencimentos",
            }
        )
    return faixas


def _pessoas(escopo, competencia: date) -> dict:
    provedor = contrato.obter(contrato.ProvedorPessoas)
    jornada = contrato.obter(contrato.ProvedorJornada)
    quadro = provedor.quadro(escopo, competencia) if provedor else None
    if quadro is None:
        return {}
    apontamento = jornada.apontamentos(escopo, competencia) if jornada else None
    return {
        "efetivo": quadro.efetivo_ativo,
        "turnover": quadro.turnover_pct,
        "absenteismo": quadro.absenteismo_pct,
        "he_ineficiencia": getattr(apontamento, "he_ineficiencia", None),
        "url": reverse("workspace:quadro"),
    }


def _projetos(escopo) -> dict:
    provedor = contrato.obter(contrato.ProvedorProjetos)
    if provedor is None:
        return {}
    todos = provedor.projetos(escopo)
    if not todos:
        return {}
    hoje = timezone.localdate()
    # ABERTOS: concluído e cancelado não estão em execução, e contá-los como
    # atrasados poria no painel um projeto que terminou em março.
    abertos = [
        proj for proj in todos
        if proj.situacao not in ("concluido", "cancelado")
    ]
    return {
        "total": len(abertos),
        "atrasados": sum(
            1 for proj in abertos if proj.prazo and proj.prazo < hoje
        ),
        "bloqueados": sum(1 for proj in abertos if proj.bloqueado),
        "url": f"{reverse('workspace:resultados')}#projetos",
    }


def _satisfacao(escopo, competencia: date) -> dict:
    provedor = contrato.obter(contrato.ProvedorSatisfacao)
    if provedor is None:
        return {}
    avaliacoes = provedor.avaliacoes(
        escopo, _recuar(competencia, 5), _fim(competencia)
    )
    if not avaliacoes:
        return {}
    notas = [a.nota for a in avaliacoes]
    detratores = [a for a in avaliacoes if a.classificacao == "detrator"]
    return {
        "nota": (Decimal(sum(notas)) / len(notas)).quantize(Decimal("0.1")),
        "detratores": len(detratores),
        "sem_tratativa": sum(1 for a in detratores if a.detrator_sem_tratativa),
        "url": reverse("workspace:satisfacao"),
    }


# ── Auxiliares ──────────────────────────────────────────────────────


def _no_mes(serie, competencia: date):
    return [
        linha
        for linha in serie
        if (linha.ano, linha.mes) == (competencia.year, competencia.month)
    ]


def _recuar(momento: date, meses: int) -> date:
    total = momento.year * 12 + (momento.month - 1) - meses
    return date(total // 12, total % 12 + 1, 1)


def _fim(competencia: date) -> date:
    ultimo = calendar.monthrange(competencia.year, competencia.month)[1]
    return date(competencia.year, competencia.month, ultimo)


def _variacao(agora: Decimal, antes: Decimal) -> Decimal | None:
    """Variação percentual. `None` sem base — e `None` não é 0%."""
    if not antes:
        return None
    return ((agora - antes) / abs(antes) * 100).quantize(Decimal("0.1"))


def _pontos(agora: Decimal | None, antes: Decimal | None) -> Decimal | None:
    """Diferença em PONTOS. A margem já é percentual, e "caiu 12%" sobre 19% é
    ambíguo entre 7 e 16,7."""
    if agora is None or antes is None:
        return None
    return (agora - antes).quantize(Decimal("0.1"))


def _mediana(valores) -> Decimal | None:
    if not valores:
        return None
    ordenados = sorted(valores)
    meio = len(ordenados) // 2
    if len(ordenados) % 2:
        return ordenados[meio]
    return ((ordenados[meio - 1] + ordenados[meio]) / 2).quantize(Decimal("0.1"))


__all__ = ["Painel", "SemResultados", "montar"]
