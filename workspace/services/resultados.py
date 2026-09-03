"""A Apresentação de Resultados — as sete faixas, montadas dos contratos.

## O que esta camada faz, e o que ela recusa fazer

Ela **pergunta** ao contrato (`workspace.providers.resultados`) e monta o que a
tela mostra. Não conhece Sankhya, monday nem Platform; não conhece os apps
`cargas` e `resultados`; não abre uma conexão de rede. Se um número vem de fora,
ele já está no espelho quando a tela abre.

## Nenhuma faixa nasce vazia

Faixa sem provedor registrado **não some**: ela aparece dizendo que a fonte não
está conectada. Faixa com provedor e sem dado na competência aparece dizendo
"—" e o motivo. Sumir esconderia que a faixa existe, e um zero mentiria — as
duas coisas que a leitura do benchmark marcou como não copiar.

## O escopo é decidido AQUI, e uma vez só

`escopo_de()` traduz o que `pode()` respondeu num `Escopo`, e o `Escopo` vira
`WHERE` lá no espelho. O provedor não decide alcance; se decidisse, existiriam
dois lugares onde "quem vê o quê" está escrito.

E quem não tem escopo nenhum recebe **403**, nunca tela zerada. Números todos em
zero para quem nunca vai ter dado faz a pessoa achar que a empresa parou — é a
mesma regra de `/workspace/indicadores/`.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from django.utils import timezone

from identidade.services.autorizacao import (
    ESCOPO_GLOBAL,
    escopo_de as escopo_da_permissao,
)
from workspace.providers import resultados as contrato
from workspace.providers.frescor import NATIVO
from workspace.services import frescor as frs

PERMISSAO = "eco.ler"

#: Treze meses: doze para comparar com o mesmo mês do ano passado, mais o atual.
#: Doze não bastam — a comparação anual é a única que separa crescimento de
#: sazonalidade, e dezembro contra novembro não diz nada numa empresa que fatura
#: menos em dezembro todo ano.
MESES_DA_SERIE = 13

#: Faixas de vencimento do benchmark. 30 primeiro porque é a que tem dono hoje.
FAIXAS_DE_VENCIMENTO = (30, 60, 90, 180)

#: Abaixo disto o contrato exige justificativa. É a regra dos 10% do benchmark,
#: e ela não é alerta: é obrigação.
MARGEM_MINIMA = Decimal("10")

#: O valor que o contrato devolve quando não há histórico para avaliar.
#:
#: Repetido aqui e não importado de `resultados.services`: o Workspace não
#: conhece aquele app, e a string chega pelo DTO. É a mesma duplicação
#: deliberada de `Fonte` entre `cargas` e `resultados`, pelo mesmo motivo — e
#: `test_o_sem_amostra_do_contrato_e_o_mesmo_do_espelho` reprova a divergência.
SEM_AMOSTRA = "sem_amostra"

#: Marcos que vencem nos próximos N dias entram no bloco de risco.
DIAS_DE_RISCO = 15

#: Projeto sem movimento além disto vira linha de atenção. Quinze dias porque é
#: mais que uma quinzena de férias e menos que um mês de esquecimento.
DIAS_SEM_MOVIMENTO = 21


class SemResultados(Exception):
    """Esta pessoa não tem resultado nenhum para ver."""


# ── Escopo ──────────────────────────────────────────────────────────


def escopo_de(pessoa, cache: dict | None = None) -> contrato.Escopo:
    """O recorte desta pessoa, traduzido do que `pode()` respondeu.

    Três respostas possíveis, e a terceira é 403:

    - **global** — a empresa inteira. Diretoria, sócios, R.H. e Financeiro.
    - **departamento/unidade** — o próprio centro de custo, e a regional quando
      a lotação tem unidade. É o gerente, que precisa dos números da operação
      dele sem ver os da empresa.
    - **nada** — 403. Resultado financeiro não é informação institucional.
    """
    escopo = escopo_da_permissao(pessoa, PERMISSAO, cache=cache)
    if escopo is None:
        raise SemResultados("Esta tela é de quem responde por resultado.")
    if escopo == ESCOPO_GLOBAL:
        return contrato.Escopo()

    lotacao = _lotacao(pessoa)
    if lotacao is None:
        # Permissão sem lotação: a pessoa tem o papel e não está no organograma,
        # então não há de onde tirar o recorte. Devolver `Escopo()` aqui daria a
        # ela a empresa inteira — que é como uma permissão restrita vira global
        # por acidente de cadastro.
        raise SemResultados(
            "Você tem acesso a resultados, mas não está lotado em nenhum centro "
            "de custo — não há de onde recortar os números."
        )

    centros = (lotacao.centro_custo_codigo,) if lotacao.centro_custo_codigo else ()
    regionais = (lotacao.unidade.nome,) if lotacao.unidade_id else ()
    if not centros and not regionais:
        raise SemResultados(
            "Sua lotação não tem centro de custo nem unidade definidos."
        )
    return contrato.Escopo(regionais=regionais, centros_custo=centros)


def tem_acesso(pessoa, cache: dict | None = None) -> bool:
    """Se o trilho mostra o item. Exceção é para o caminho errado, não para um `if`."""
    try:
        escopo_de(pessoa, cache=cache)
    except SemResultados:
        return False
    return True


def _lotacao(pessoa):
    from identidade.models import Lotacao

    return (
        Lotacao.objects.select_related("unidade", "departamento")
        .filter(user=pessoa)
        .first()
    )


# ── Filtros ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Filtros:
    """A barra de filtros, que se repete em toda tela futura.

    Tudo na *query string*, com nome: a tela é **linkável**. "Manda a 10 de
    agosto do Sudeste" vira uma URL, e a outra pessoa vê exatamente a mesma
    coisa — que é metade do valor de existir uma tela em vez de um relatório.

    **Nenhum dado pessoal aqui.** A query string vai para o histórico do
    navegador, para o log do servidor e para o corpo do e-mail em que alguém
    cola o link.
    """

    competencia: date
    regional: str = ""
    centro_custo: str = ""
    contrato: str = ""
    servico: str = ""
    status: str = ""
    #: `"1"`, `"2"`, `"3"` — o porte do contrato. String e não inteiro porque
    #: `sem_amostra` é uma resposta legítima do espelho, e não um número.
    layer: str = ""
    deficitario: bool = False
    #: Quantos meses a série mostra. É filtro de LEITURA e não de dado: treze
    #: meses num gráfico com rótulo por ponto é o limite do que cabe, e seis é
    #: o que se olha numa reunião mensal.
    #:
    #: Nasceu de uma reclamação concreta — "os números ficam um em cima do
    #: outro". Girar o rótulo resolveu metade; poder estreitar a janela é a
    #: outra metade, e é a que a pessoa controla.
    janela: int = MESES_DA_SERIE

    @property
    def de(self) -> date:
        """O início da série."""
        ano, mes = self.competencia.year, self.competencia.month
        total = ano * 12 + (mes - 1) - (self.meses - 1)
        return date(total // 12, total % 12 + 1, 1)

    @property
    def meses(self) -> int:
        """A janela, presa entre 3 e o teto da série.

        Três é o mínimo em que uma tendência existe; abaixo disso o gráfico é
        uma comparação, e comparação se lê melhor em tabela.
        """
        return max(3, min(int(self.janela or MESES_DA_SERIE), MESES_DA_SERIE))

    @property
    def ate(self) -> date:
        ultimo = calendar.monthrange(self.competencia.year, self.competencia.month)[1]
        return date(self.competencia.year, self.competencia.month, ultimo)

    def aplicar(self, escopo: contrato.Escopo) -> contrato.Escopo:
        """O filtro ESTREITA o escopo; nunca o alarga.

        Um gerente que digitasse `?regional=Sul` na URL continua vendo só o
        dela — o filtro entra por interseção, e o que ele não pode ver não volta
        por uma query string.
        """
        regionais = _estreitar(escopo.regionais, self.regional)
        centros = _estreitar(escopo.centros_custo, self.centro_custo)
        contratos = _estreitar(escopo.contratos, self.contrato)
        return contrato.Escopo(
            regionais=regionais, centros_custo=centros, contratos=contratos
        )


def _estreitar(permitidos: tuple[str, ...], pedido: str) -> tuple[str, ...]:
    if not pedido:
        return permitidos
    if not permitidos:
        return (pedido,)
    return (pedido,) if pedido in permitidos else permitidos


def ler_filtros(parametros, hoje: date | None = None) -> Filtros:
    """Lê a query string. Valor impossível cai no padrão, e não em erro.

    `?competencia=9999-99` é uma URL digitada errada, não um ataque — e responder
    500 a ela ensinaria a não brincar com a barra de endereço, que é justamente
    o que a tela quer que as pessoas façam.
    """
    hoje = hoje or timezone.localdate()
    return Filtros(
        competencia=_competencia(parametros.get("competencia"), hoje),
        regional=(parametros.get("regional") or "").strip()[:60],
        centro_custo=(parametros.get("cc") or "").strip()[:20],
        contrato=(parametros.get("contrato") or "").strip()[:40],
        servico=(parametros.get("servico") or "").strip()[:20],
        status=(parametros.get("status") or "").strip()[:20],
        layer=(parametros.get("layer") or "").strip()[:12],
        deficitario=parametros.get("deficitario") in ("1", "true", "sim"),
        janela=_inteiro(parametros.get("janela"), MESES_DA_SERIE),
    )


def _inteiro(texto, padrao: int) -> int:
    """`?janela=abacaxi` é uma URL digitada errada, não um ataque."""
    try:
        return int(texto)
    except (TypeError, ValueError):
        return padrao


def _competencia(texto: str | None, hoje: date) -> date:
    padrao = date(hoje.year, hoje.month, 1)
    if not texto:
        return padrao
    try:
        ano, mes = (int(p) for p in str(texto).split("-", 1))
        return date(ano, mes, 1)
    except (ValueError, TypeError):
        return padrao


# ── O esqueleto de uma faixa ────────────────────────────────────────


@dataclass
class Faixa:
    """Uma faixa da tela. Nunca nasce vazia — no máximo, nasce explicada."""

    chave: str
    titulo: str
    fonte: str
    disponivel: bool = True
    #: Por que não há o que mostrar. Texto que explica o que falta, e não um
    #: espaço em branco: "sem dado" e "sem fonte conectada" pedem ações
    #: diferentes de quem lê.
    motivo: str = ""
    conteudo: dict = field(default_factory=dict)
    #: A competência pedida. Entra no carimbo como janela — "competência
    #: AGO/2026" diz mais sobre o número do que qualquer descrição de cadência.
    competencia: date | None = None

    @property
    def carimbo(self):
        return frs.de(self.fonte, competencia=self.competencia)


#: Título e fonte de cada faixa, num lugar só. O montador consulta daqui, e a
#: tela de fontes também — sem isto, o mapa "faixa → fonte" da tela 99 seria uma
#: lista paralela, e listas paralelas nascem desatualizadas na primeira faixa
#: nova.
DEFINICOES: dict[str, tuple[str, str]] = {
    "destaques": ("Destaques e pontos de atenção", NATIVO),
    "dinheiro": ("O dinheiro", "sankhya"),
    "contratos": ("Os contratos", "iconnect_platform"),
    "vencimentos": ("O que está prestes a vencer", "iconnect_platform"),
    "projetos": ("Os projetos", "monday"),
    "pessoas": ("As pessoas e a jornada", "sankhya"),
    "satisfacao": ("A avaliação do cliente", "iconnect_platform"),
}


def _faixa(chave: str, competencia: date) -> Faixa:
    titulo, fonte = DEFINICOES[chave]
    return Faixa(chave=chave, titulo=titulo, fonte=fonte, competencia=competencia)


def _sem_fonte(faixa: Faixa, nome: str) -> Faixa:
    faixa.disponivel = False
    faixa.motivo = (
        f"A fonte {nome} ainda não está conectada neste ambiente. "
        "Assim que a primeira carga rodar, os números aparecem aqui."
    )
    return faixa


def _sem_dado(faixa: Faixa, o_que: str) -> Faixa:
    faixa.disponivel = False
    faixa.motivo = f"Sem {o_que} nesta competência."
    return faixa


# ── Faixa 2 · O dinheiro ────────────────────────────────────────────


def dinheiro(escopo: contrato.Escopo, filtros: Filtros) -> Faixa:
    """Realizado × orçado, com a **coluna do meio**.

    A dinâmica não é `realizado | orçado | variação`. São seis colunas, e a
    terceira é onde a operação declara o que já aconteceu e ainda não bateu na
    contabilidade. Sem ela, a reunião vira briga sobre o número em vez de
    decisão sobre o que fazer.
    """
    faixa = _faixa("dinheiro", filtros.competencia)
    provedor = contrato.obter(contrato.ProvedorResultadoFinanceiro)
    if provedor is None:
        return _sem_fonte(faixa, "Sankhya")

    serie = provedor.serie_competencia(escopo, filtros.de, filtros.ate)
    if not serie:
        return _sem_dado(faixa, "lançamento financeiro")

    do_mes = [linha for linha in serie if _no_mes(linha, filtros.competencia)]

    faixa.conteudo = {
        "serie": serie,
        "linhas": [_linha_de_dinamica(linha) for linha in do_mes],
        "totais": _totais(do_mes),
        "consolidado": provedor.consolidado(escopo, filtros.competencia),
        # Dois gráficos e não seis. Receita responde "quanto entrou" e EBITDA
        # responde "quanto sobrou" — as outras quatro linhas do benchmark são
        # decomposição, e decomposição se lê na tabela, não em barra.
        #
        # Onda 10: o realizado CONTRA o orçado, com a razão em linha no eixo
        # direito — a 1.1.02 do benchmark. É o desenho que responde "o mês
        # fechou onde deveria" numa olhada, e a razão de a linha existir.
        "grafico_receita": _bloco_comparado(
            serie, "receita_bruta", "receita_orcada", "receita",
            f"Receita bruta, {filtros.meses} meses",
        ),
        # EBITDA fica SEM par: o espelho não traz EBITDA orçado. Inventar um
        # denominador para ter a linha seria a pior forma de completar um
        # gráfico — o bloco diz o que tem, e a razão fica de fora.
        "grafico_ebitda": _bloco_mensal(
            serie, "ebitda", "ebitda", f"EBITDA, {filtros.meses} meses"
        ),
    }
    return faixa


def _com_perfuracao(faixa, escopo, filtros: Filtros):
    """Acrescenta a trilha e a barra do nível seguinte à faixa do dinheiro.

    Só nesta faixa, e é o passo 7 do plano: um mecanismo isolado, numa faixa só.
    Ligar a perfuração nas cinco de uma vez tornaria impossível dizer qual delas
    quebrou.
    """
    from django.urls import reverse

    if not faixa.disponivel or not faixa.conteudo:
        return faixa
    base = reverse("workspace:resultados")
    faixa.conteudo["migalhas"] = migalhas(filtros, base)
    faixa.conteudo["perfuracao"] = _bloco_perfuracao(escopo, filtros, base)
    return faixa


def _por_mes(linhas, campo: str) -> tuple[list[str], dict[str, Decimal | None]]:
    """Soma um campo por mês. `None` quando NENHUMA linha do mês tem o valor.

    A diferença entre `None` e `Decimal("0")` é a de sempre: um mês sem orçado
    não é um mês de orçado zero, e somá-lo como zero faria a razão dar 0% num
    mês em que ninguém orçou nada.
    """
    total: dict[str, Decimal | None] = {}
    ordem: list[str] = []
    for linha in linhas:
        rotulo = f"{linha.mes:02d}/{str(linha.ano)[2:]}"
        if rotulo not in total:
            total[rotulo] = None
            ordem.append(rotulo)
        valor = getattr(linha, campo, None)
        if valor is not None:
            total[rotulo] = (total[rotulo] or Decimal("0")) + valor
    return ordem, total


def _bloco_mensal(linhas, campo: str, chave: str, titulo: str):
    """Um mês por ponto, somando o campo entre contratos.

    A soma por rótulo existe porque a série vem por CONTRATO e por mês: sem ela,
    treze meses de doze contratos virariam 156 barras.
    """
    from workspace.graficos import series

    ordem, total = _por_mes(linhas, campo)
    return series.serie_temporal(
        [(rotulo, total[rotulo]) for rotulo in ordem],
        chave=chave,
        titulo=titulo,
        rotulo_serie=titulo.split(",")[0],
    )


def _bloco_comparado(linhas, campo_re: str, campo_or: str, chave: str, titulo: str):
    """Realizado × orçado, com `%RExOR` na linha do eixo direito.

    A linha é o que a faixa existe para mostrar: dois números lado a lado dizem
    quanto; a razão entre eles diz se está onde deveria. É a leitura que o
    benchmark põe em etiqueta escura sobre a linha, e é a primeira coisa que
    alguém procura na reunião.

    Mês sem orçado fica sem barra clara e **sem ponto na linha** — e não com um
    ponto em zero, que seria lido como "não cumpriu nada".
    """
    from workspace.graficos import series

    ordem, realizado = _por_mes(linhas, campo_re)
    _, orcado = _por_mes(linhas, campo_or)

    pontos = [(rotulo, realizado[rotulo], orcado.get(rotulo)) for rotulo in ordem]
    razao = [
        (
            (re / orc * 100) if (re is not None and orc) else None
        )
        for _, re, orc in pontos
    ]

    return series.barras_comparadas(
        pontos,
        chave=chave,
        titulo=titulo,
        rotulo_a="Realizado",
        rotulo_b="Orçado",
        rotulo_linha="%RExOR",
        linha=razao,
    )


def _no_mes(linha, competencia: date) -> bool:
    return (linha.ano, linha.mes) == (competencia.year, competencia.month)


def _linha_de_dinamica(linha) -> dict:
    """As seis colunas do benchmark, para uma competência.

    `%RExOR` e `diferença` são `None` — e não zero — quando não há orçado. Zero
    seria lido como "bateu na mosca"; `None` vira "—" na tela, que é o que uma
    conciliação de centro de custo pendente realmente significa.
    """
    ajustado = linha.receita_bruta + linha.ajuste_potencial
    orcado = linha.receita_orcada
    return {
        "rotulo": linha.contrato or linha.centro_custo,
        "realizado": linha.receita_bruta,
        "ajuste": linha.ajuste_potencial,
        "ajustado": ajustado,
        "orcado": orcado,
        "percentual": _percentual(ajustado, orcado),
        "diferenca": (ajustado - orcado) if orcado is not None else None,
        "procedencia": linha.procedencia,
    }


def _percentual(realizado: Decimal, orcado: Decimal | None) -> Decimal | None:
    if orcado is None or orcado == 0:
        return None
    return (realizado / orcado * 100).quantize(Decimal("0.1"))


def _totais(linhas) -> dict:
    def soma(campo):
        return sum((getattr(l, campo) for l in linhas), Decimal("0"))

    receita = soma("receita_bruta")
    return {
        "receita_bruta": receita,
        "impostos": soma("impostos"),
        "custo_direto": soma("custo_direto"),
        "custo_indireto": soma("custo_indireto"),
        "margem_contribuicao": soma("margem_contribuicao"),
        "ebitda": soma("ebitda"),
        # Percentual sobre receita, como o benchmark mostra. `None` sem receita:
        # dividir por zero para exibir "0%" faria um mês sem lançamento parecer
        # um mês de margem zero.
        "margem_pct": _sobre(soma("margem_contribuicao"), receita),
        "ebitda_pct": _sobre(soma("ebitda"), receita),
    }


def _sobre(valor: Decimal, base: Decimal) -> Decimal | None:
    if base <= 0:
        return None
    return (valor / base * 100).quantize(Decimal("0.1"))


# ── Faixa 3 · Os contratos ──────────────────────────────────────────


def contratos(escopo: contrato.Escopo, filtros: Filtros) -> Faixa:
    """Carteira, movimentação e rentabilidade.

    **Contrato deficitário aparece separado, no topo, sempre.** Ele é a única
    coisa desta tela que não espera a pessoa rolar até encontrar.
    """
    faixa = _faixa("contratos", filtros.competencia)
    provedor = contrato.obter(contrato.ProvedorCarteira)
    if provedor is None:
        return _sem_fonte(faixa, "iConnect Platform")

    carteira = provedor.contratos(escopo, filtros.competencia)
    carteira = _filtrar_carteira(carteira, filtros)
    if not carteira:
        return _sem_dado(faixa, "contrato")

    deficitarios = [c for c in carteira if c.deficitario]
    # "Sem amostra" fica de fora, e é a linha que faz a regra ser justa: cobrar
    # justificativa de margem de um contrato que faturou uma vez é cobrar de
    # quem ainda não tem o que explicar. A pendência dele é ganhar histórico.
    #
    # O comentário estava aqui antes do código — foi
    # `test_contrato_de_um_mes_nao_recebe_layer_nem_entra_na_regra_dos_dez` que
    # cobrou o que ele prometia.
    abaixo = [
        c for c in carteira
        if not c.deficitario
        and c.layer != SEM_AMOSTRA
        and c.margem_contribuicao_pct is not None
        and c.margem_contribuicao_pct < MARGEM_MINIMA
    ]
    faixa.conteudo = {
        "carteira": carteira,
        "quantidade": len(carteira),
        "valor_mensal": sum((c.valor_mensal for c in carteira), Decimal("0")),
        "mix": _mix(carteira),
        "deficitarios": deficitarios,
        # Sem amostra NÃO entra: cobrar justificativa de margem de um contrato
        # que faturou uma vez é cobrar de quem ainda não tem o que explicar.
        "abaixo_da_margem": abaixo,
        "movimentacao": provedor.movimentacoes(escopo, filtros.de, filtros.ate),
    }
    return faixa


def _filtrar_carteira(carteira, filtros: Filtros):
    if filtros.servico:
        carteira = [c for c in carteira if c.servico == filtros.servico]
    if filtros.status:
        carteira = [c for c in carteira if c.status == filtros.status]
    if filtros.layer:
        carteira = [c for c in carteira if c.layer == filtros.layer]
    if filtros.deficitario:
        carteira = [c for c in carteira if c.deficitario]
    return carteira


def _mix(carteira) -> list[dict]:
    """Quantidade e valor por serviço, do maior para o menor.

    Por VALOR e não por quantidade: cem alarmes e três monitoramentos podem ter
    o mesmo peso na receita, e ordenar por contagem esconderia isso.
    """
    por_servico: dict[str, dict] = {}
    for c in carteira:
        entrada = por_servico.setdefault(
            c.servico, {"servico": c.servico, "quantidade": 0, "valor": Decimal("0")}
        )
        entrada["quantidade"] += 1
        entrada["valor"] += c.valor_mensal
    return sorted(por_servico.values(), key=lambda e: e["valor"], reverse=True)


# ── Faixa 4 · O que está prestes a vencer ───────────────────────────


def vencimentos(escopo: contrato.Escopo, filtros: Filtros) -> Faixa:
    """A "Defesa de Território" do benchmark, reduzida ao que a ADB responde.

    Faixas cumulativas do jeito que o benchmark usa: um contrato que vence em 45
    dias aparece em "60" e não em "30". Repeti-lo nas duas faria a soma das
    faixas não bater com a carteira, e alguém contaria duas vezes.
    """
    faixa = _faixa("vencimentos", filtros.competencia)
    provedor = contrato.obter(contrato.ProvedorCarteira)
    if provedor is None:
        return _sem_fonte(faixa, "iConnect Platform")

    ja_vistos: set[str] = set()
    blocos = []
    for dias in FAIXAS_DE_VENCIMENTO:
        achados = [
            c for c in provedor.vencimentos(escopo, dias) if c.codigo not in ja_vistos
        ]
        ja_vistos.update(c.codigo for c in achados)
        blocos.append(
            {
                "dias": dias,
                "contratos": sorted(achados, key=lambda c: c.valor_mensal, reverse=True),
                "valor": sum((c.valor_mensal for c in achados), Decimal("0")),
            }
        )

    if not any(bloco["contratos"] for bloco in blocos):
        return _sem_dado(faixa, "contrato vencendo em até 180 dias")

    faixa.conteudo = {"blocos": blocos}
    return faixa


# ── Faixa 5 · Os projetos ───────────────────────────────────────────


def projetos(escopo: contrato.Escopo, filtros: Filtros) -> Faixa:
    faixa = _faixa("projetos", filtros.competencia)
    provedor = contrato.obter(contrato.ProvedorProjetos)
    if provedor is None:
        return _sem_fonte(faixa, "monday.com")

    todos = provedor.projetos(escopo)
    if not todos:
        return _sem_dado(faixa, "projeto")

    faixa.conteudo = {
        "por_situacao": _por_situacao(todos),
        "bloqueados": [p for p in todos if p.bloqueado],
        "marcos_em_risco": provedor.marcos_em_risco(escopo, DIAS_DE_RISCO),
        # "Sem movimento" sai do instante do LADO DE LÁ, e não da nossa carga:
        # um projeto parado há um mês num monday que carregou há dez minutos
        # continua parado há um mês.
        "parados": [p for p in todos if p.parado_ha(DIAS_SEM_MOVIMENTO)],
        "dias_sem_movimento": DIAS_SEM_MOVIMENTO,
    }
    return faixa


def _por_situacao(projetos_) -> list[dict]:
    contagem: dict[str, int] = {}
    for p in projetos_:
        contagem[p.situacao] = contagem.get(p.situacao, 0) + 1
    return [{"situacao": s, "quantidade": q} for s, q in sorted(contagem.items())]


# ── Faixa 6 · As pessoas e a jornada ────────────────────────────────


def pessoas(escopo: contrato.Escopo, filtros: Filtros) -> Faixa:
    faixa = _faixa("pessoas", filtros.competencia)
    provedor = contrato.obter(contrato.ProvedorPessoas)
    jornada = contrato.obter(contrato.ProvedorJornada)
    if provedor is None or jornada is None:
        return _sem_fonte(faixa, "Sankhya")

    quadro = provedor.quadro(escopo, filtros.competencia)
    apontamento = jornada.apontamentos(escopo, filtros.competencia)
    if quadro is None and apontamento is None:
        return _sem_dado(faixa, "dado de folha ou de ponto")

    # O agregado E o recorte por centro de custo. O agregado responde "como
    # está a empresa"; o recorte é o único que mostra o centro de custo que
    # destoa — e é o que destoa que pede ação.
    por_centro = provedor.quadros(escopo, filtros.competencia)
    faixa.conteudo = {
        "quadro": quadro,
        "por_centro": sorted(por_centro, key=lambda q: q.turnover_pct, reverse=True),
        "movimentacao": provedor.movimentacao(escopo, filtros.de, filtros.ate),
        "apontamento": apontamento,
        "horas": _horas(apontamento),
        # Conformidade legal do ponto: folha pendente e contrato sem assinatura
        # são as duas que viram autuação, e por isso saem da tabela de horas
        # para um bloco próprio.
        "conformidade": {
            "folhas_pendentes": getattr(apontamento, "folhas_ponto_pendentes", 0),
            "contratos_pendentes": getattr(
                apontamento, "contratos_pendentes_assinatura", 0
            ),
        },
    }
    return faixa


def _horas(apontamento) -> list[dict]:
    """Cada tipo de hora sobre as horas NORMAIS, como o benchmark mostra.

    O percentual é o que torna o número comparável entre um centro de custo de
    dez pessoas e um de duzentas — e é o que faz "1.200 h extras" virar "6,7%",
    que é uma frase sobre a escala e não sobre o tamanho da equipe.
    """
    if apontamento is None:
        return []
    base = apontamento.horas_normais
    tipos = (
        ("HE total", apontamento.he_total),
        ("HE de ineficiência", apontamento.he_ineficiencia),
        ("HE de serviço extra", apontamento.he_servico_extra),
        ("HE sem classificação", apontamento.he_sem_classificacao),
        ("Hora noturna", apontamento.hora_noturna),
        ("Abono", apontamento.hora_abono),
        ("Desconto", apontamento.hora_desconto),
    )
    return [
        {"rotulo": rotulo, "horas": horas, "percentual": _sobre(horas, base)}
        for rotulo, horas in tipos
    ]


# ── Faixa 7 · A avaliação do cliente ────────────────────────────────


def satisfacao(escopo: contrato.Escopo, filtros: Filtros) -> Faixa:
    """Promotores, neutros, detratores — e o detrator SEM tratativa em destaque.

    Detrator com tratativa é trabalho em andamento. Sem tratativa é uma pessoa
    esperando, e por isso ele não é linha de tabela: é destaque.
    """
    faixa = _faixa("satisfacao", filtros.competencia)
    provedor = contrato.obter(contrato.ProvedorSatisfacao)
    if provedor is None:
        return _sem_fonte(faixa, "iConnect Platform")

    avaliacoes = provedor.avaliacoes(escopo, filtros.de, filtros.ate)
    if not avaliacoes:
        return _sem_dado(faixa, "avaliação")

    por_classe = {"promotor": 0, "neutro": 0, "detrator": 0}
    for a in avaliacoes:
        if a.classificacao in por_classe:
            por_classe[a.classificacao] += 1
    total = len(avaliacoes)

    faixa.conteudo = {
        "total": total,
        "contagem": por_classe,
        "percentuais": {
            classe: _sobre(Decimal(quantidade), Decimal(total))
            for classe, quantidade in por_classe.items()
        },
        "detratores": [a for a in avaliacoes if a.classificacao == "detrator"],
        "sem_tratativa": [a for a in avaliacoes if a.detrator_sem_tratativa],
    }
    return faixa


# ── Faixa 1 · Destaques e pontos de atenção ─────────────────────────
#
# Cartão gerado por REGRA, nunca escrito à mão, e só quando a regra dispara.
# Painel que sempre mostra oito cartões ensina a ignorar os oito — foi assim que
# o "Painel Gestão de Efetivo" do benchmark virou uma tela que ninguém abre.


@dataclass(frozen=True)
class Destaque:
    chave: str
    titulo: str
    valor: str
    detalhe: str = ""
    #: `atencao` pinta; `neutro` informa. Só a primeira classe tem cor, porque
    #: cor que aparece sempre deixa de significar alguma coisa.
    severidade: str = "atencao"
    fonte: str = ""
    ancora: str = ""


def destaques(faixas: dict[str, Faixa], filtros: Filtros) -> Faixa:
    """Os cartões, derivados do que as outras faixas já sabem.

    Derivados e não recalculados: consultar de novo produziria uma segunda
    verdade — e, pior, uma que poderia discordar da faixa logo abaixo na mesma
    tela.
    """
    faixa = _faixa("destaques", filtros.competencia)
    cartoes: list[Destaque] = []

    # A fonte quebrada vem PRIMEIRO. Sem isso, alguém lê a tela inteira e decide
    # em cima de um número de três dias atrás sem saber.
    cartoes += _cartoes_de_fonte(faixas)

    cartoes += _cartoes_de_contrato(faixas.get("contratos"))
    cartoes += _cartoes_de_vencimento(faixas.get("vencimentos"))
    cartoes += _cartoes_de_projeto(faixas.get("projetos"))
    cartoes += _cartoes_de_satisfacao(faixas.get("satisfacao"))
    cartoes += _cartoes_de_dinheiro(faixas.get("dinheiro"))
    cartoes += _cartoes_de_pessoas(faixas.get("pessoas"))

    faixa.conteudo = {"cartoes": cartoes}
    if not cartoes:
        # Vazio aqui é BOA notícia, e a tela precisa dizer isso — "nenhum
        # destaque" lido como falha de carregamento faria alguém procurar
        # defeito onde há tranquilidade.
        faixa.disponivel = False
        faixa.motivo = (
            "Nenhuma regra disparou nesta competência. As faixas abaixo "
            "continuam com os números."
        )
    return faixa


def _cartoes_de_fonte(faixas: dict[str, Faixa]) -> list[Destaque]:
    vistas: set[str] = set()
    cartoes = []
    for faixa in faixas.values():
        carimbo = faixa.carimbo
        if faixa.fonte in vistas or faixa.fonte == NATIVO or not carimbo.alerta:
            continue
        if not carimbo.conhecido:
            # "Não sei nada sobre esta fonte" NÃO é "a fonte está desatualizada".
            #
            # Fonte sem registro de carga é fonte que ninguém ligou ainda — e a
            # própria faixa já diz isso, com o nome da fonte. Um cartão de
            # "desatualizada" aqui mandaria alguém procurar uma carga que nunca
            # existiu, num ambiente onde não existir é o estado normal.
            continue
        vistas.add(faixa.fonte)
        cartoes.append(
            Destaque(
                chave=f"fonte-{faixa.fonte}",
                titulo=f"{carimbo.rotulo} está desatualizada",
                valor=carimbo.idade or "sem carga",
                detalhe=carimbo.motivo or "A última carga não terminou bem.",
                fonte=faixa.fonte,
                ancora="fontes",
            )
        )
    return cartoes


def _cartoes_de_contrato(faixa: Faixa | None) -> list[Destaque]:
    if faixa is None or not faixa.disponivel:
        return []
    cartoes = []
    deficitarios = faixa.conteudo["deficitarios"]
    abaixo = faixa.conteudo["abaixo_da_margem"]
    if deficitarios:
        cartoes.append(
            Destaque(
                chave="deficitarios",
                titulo="Contratos deficitários",
                valor=str(len(deficitarios)),
                detalhe=", ".join(c.codigo for c in deficitarios[:3]),
                fonte=faixa.fonte,
                ancora="contratos",
            )
        )
    if abaixo:
        cartoes.append(
            Destaque(
                chave="abaixo-da-margem",
                titulo=f"Margem abaixo de {MARGEM_MINIMA:.0f}%",
                valor=str(len(abaixo)),
                detalhe="Exige justificativa e plano de ação.",
                fonte=faixa.fonte,
                ancora="contratos",
            )
        )
    return cartoes


def _cartoes_de_vencimento(faixa: Faixa | None) -> list[Destaque]:
    """Layer 3 vencendo é o cartão que mais vale desta faixa.

    Layer 3 é quem deve apresentação de resultado. Perder um deles sem visita
    custa mais do que perder três Layer 1 — e a faixa 4 inteira existe por isso.
    """
    if faixa is None or not faixa.disponivel:
        return []
    proximos = [
        c
        for bloco in faixa.conteudo["blocos"]
        if bloco["dias"] <= 60
        for c in bloco["contratos"]
    ]
    grandes = [c for c in proximos if c.layer == "3"]
    if not grandes:
        return []
    return [
        Destaque(
            chave="layer3-vencendo",
            titulo="Layer 3 vencendo em até 60 dias",
            valor=str(len(grandes)),
            detalhe=", ".join(c.codigo for c in grandes[:3]),
            fonte=faixa.fonte,
            ancora="vencimentos",
        )
    ]


def _cartoes_de_projeto(faixa: Faixa | None) -> list[Destaque]:
    if faixa is None or not faixa.disponivel:
        return []
    cartoes = []
    bloqueados = faixa.conteudo["bloqueados"]
    vencidos = [m for m in faixa.conteudo["marcos_em_risco"] if m.vencido]
    if bloqueados:
        cartoes.append(
            Destaque(
                chave="projetos-bloqueados",
                titulo="Projetos bloqueados",
                valor=str(len(bloqueados)),
                detalhe=bloqueados[0].motivo_bloqueio or "",
                fonte=faixa.fonte,
                ancora="projetos",
            )
        )
    if vencidos:
        cartoes.append(
            Destaque(
                chave="marcos-vencidos",
                titulo="Marcos vencidos",
                valor=str(len(vencidos)),
                detalhe="Sem replanejamento.",
                fonte=faixa.fonte,
                ancora="projetos",
            )
        )
    return cartoes


def _cartoes_de_satisfacao(faixa: Faixa | None) -> list[Destaque]:
    if faixa is None or not faixa.disponivel:
        return []
    soltos = faixa.conteudo["sem_tratativa"]
    if not soltos:
        return []
    return [
        Destaque(
            chave="detrator-sem-tratativa",
            titulo="Detratores sem tratativa",
            valor=str(len(soltos)),
            detalhe="Cada um é um cliente esperando resposta.",
            fonte=faixa.fonte,
            ancora="satisfacao",
        )
    ]


def _cartoes_de_dinheiro(faixa: Faixa | None) -> list[Destaque]:
    """A conciliação de centro de custo, que é a armadilha da onda do orçamento.

    Linha com realizado e SEM orçado parece estouro de orçamento e não é: é
    código de centro de custo que existe de um lado e não do outro. Sem este
    cartão, a diferença só apareceria como uma variação absurda no meio da
    tabela.
    """
    if faixa is None or not faixa.disponivel:
        return []
    orfas = [linha for linha in faixa.conteudo["linhas"] if linha["orcado"] is None]
    if not orfas:
        return []
    return [
        Destaque(
            chave="sem-orcado",
            titulo="Linhas com realizado e sem orçado",
            valor=str(len(orfas)),
            detalhe="Parece estouro de orçamento e não é — é código de centro "
                    "de custo que não bate entre o ERP e o orçamento.",
            fonte=faixa.fonte,
            ancora="dinheiro",
        )
    ]


#: HE de ineficiência acima disto, sobre as horas normais, vira cartão. Cinco
#: por cento é onde a cobertura de ausência deixa de ser eventual.
TETO_INEFICIENCIA = Decimal("5")

#: Turnover mensal acima disto vira cartão.
TETO_TURNOVER = Decimal("5")


def _cartoes_de_pessoas(faixa: Faixa | None) -> list[Destaque]:
    if faixa is None or not faixa.disponivel:
        return []
    cartoes = []
    apontamento = faixa.conteudo.get("apontamento")
    quadro = faixa.conteudo.get("quadro")

    if apontamento is not None:
        pct = _sobre(apontamento.he_ineficiencia, apontamento.horas_normais)
        if pct is not None and pct > TETO_INEFICIENCIA:
            cartoes.append(
                Destaque(
                    chave="he-ineficiencia",
                    titulo="Hora extra de ineficiência",
                    valor=f"{pct}%",
                    detalhe="Cobertura de ausência e escala — não é serviço extra.",
                    fonte=faixa.fonte,
                    ancora="pessoas",
                )
            )

    conformidade = faixa.conteudo.get("conformidade") or {}
    pendentes = conformidade.get("folhas_pendentes", 0)
    if pendentes:
        cartoes.append(
            Destaque(
                chave="folhas-pendentes",
                titulo="Folhas de ponto pendentes",
                valor=str(pendentes),
                detalhe="Conformidade legal do ponto.",
                fonte=faixa.fonte,
                ancora="pessoas",
            )
        )

    # O outlier, e não a média. Um turnover de 8,4% num centro contra 2,1% nos
    # outros vira 2,6% no agregado — e o número que pedia ação desaparece dentro
    # de um número tranquilo. Foi a média que escondeu o defeito plantado 8 na
    # primeira montagem desta faixa.
    acima = [
        q for q in faixa.conteudo.get("por_centro", []) if q.turnover_pct > TETO_TURNOVER
    ]
    if acima:
        pior = acima[0]
        cartoes.append(
            Destaque(
                chave="turnover",
                titulo="Turnover acima do aceitável",
                valor=f"{pior.turnover_pct}%",
                detalhe=(
                    f"Centro de custo {pior.centro_custo}"
                    + (f" e mais {len(acima) - 1}." if len(acima) > 1 else ".")
                ),
                fonte=faixa.fonte,
                ancora="pessoas",
            )
        )
    return cartoes


# ── O painel ────────────────────────────────────────────────────────


#: A ordem das faixas na tela É a mensagem, como a ordem da home. Primeiro o que
#: exige decisão, depois o dinheiro, depois o que sustenta o dinheiro.
MONTADORES = (
    ("dinheiro", dinheiro),
    ("contratos", contratos),
    ("vencimentos", vencimentos),
    ("projetos", projetos),
    ("pessoas", pessoas),
    ("satisfacao", satisfacao),
)


def painel(pessoa, parametros, cache: dict | None = None) -> dict:
    """Tudo o que a tela mostra. Levanta `SemResultados` para quem não tem escopo."""
    escopo = escopo_de(pessoa, cache=cache)
    filtros = ler_filtros(parametros)
    recorte = _estreitar_por_atributo(filtros.aplicar(escopo), filtros)

    faixas: dict[str, Faixa] = {}
    for chave, montador in MONTADORES:
        faixas[chave] = montador(recorte, filtros)

    # A perfuração entra DEPOIS de a faixa existir, e só na do dinheiro — é o
    # passo 7 do plano: um mecanismo isolado, numa faixa só. Ligar nas cinco de
    # uma vez tornaria impossível dizer qual delas quebrou.
    _com_perfuracao(faixas["dinheiro"], recorte, filtros)

    return {
        "filtros": filtros,
        "escopo": recorte,
        "escopo_total": escopo.tudo,
        "destaques": destaques(faixas, filtros),
        "faixas": [faixas[chave] for chave, _ in MONTADORES],
        "por_chave": faixas,
        "competencias": _competencias_oferecidas(filtros.competencia),
        # Os serviços que EXISTEM no espelho, e não uma lista escrita à mão:
        # uma opção que não devolve linha nenhuma é pior que a ausência dela.
        "servicos": _servicos_oferecidos(faixas),
        "janelas": JANELAS,
    }


#: As janelas oferecidas. Três é o mínimo em que uma tendência existe; treze é
#: o teto do que cabe com rótulo por ponto.
JANELAS: tuple[int, ...] = (3, 6, 12, MESES_DA_SERIE)


# ── Perfuração — Onda 11, mecanismo 1 ───────────────────────────────
#
# Descer na MESMA dimensão: empresa → regional → centro de custo → contrato.
#
# ## O estado mora na URL, e é por isso que a tela é compartilhável
#
# Nada de estado no cliente. `?regional=Sudeste&cc=1042` é a tela inteira, e
# colar essa URL numa mensagem reproduz exatamente o que a pessoa está vendo.
# É metade do valor de existir uma tela em vez de um relatório.
#
# ## A perfuração usa os filtros que já existem
#
# Descer para "Sudeste" é o mesmo que filtrar por `regional=Sudeste` — e por
# isso não há parâmetro `nivel` na URL: o nível é **derivado** do que está
# preenchido. Um `?nivel=cc` ao lado de `?cc=1042` seria uma segunda verdade
# sobre o mesmo fato, e as duas discordariam no dia em que alguém editasse a URL
# à mão.
#
# ## O último nível diz que é o último
#
# Perfurar até o contrato funciona; até a ocorrência, não — o detalhe
# operacional mora no Platform, e trazê-lo para cá refaria o acoplamento que
# custou 881 lotações órfãs. No fim da hierarquia o produto diz isso e oferece o
# link. Beco sem saída silencioso é pior que a ausência do nível.

#: `(parâmetro na URL, rótulo, atributo do contrato)`, do topo para o fundo.
HIERARQUIA: tuple[tuple[str, str, str], ...] = (
    ("regional", "Regional", "regional"),
    ("cc", "Centro de custo", "centro_custo"),
    ("contrato", "Contrato", "codigo"),
)

#: O que a tela diz quando não há mais para onde descer.
FRONTEIRA = (
    "Este é o último nível daqui. Ocorrência, medição e ticket moram no "
    "iConnect Platform — trazer o detalhe operacional para cá refaria o "
    "acoplamento que este produto existe para desfazer."
)


def nivel_de(filtros: Filtros) -> int:
    """Quantos degraus a pessoa já desceu. `0` é a empresa inteira.

    Derivado dos filtros e não lido da URL: um `?nivel=` ao lado de `?cc=` seria
    uma segunda verdade sobre o mesmo fato.
    """
    valores = (filtros.regional, filtros.centro_custo, filtros.contrato)
    profundidade = 0
    for valor in valores:
        if not valor:
            break
        profundidade += 1
    return profundidade


def _url_com(base: str, filtros: Filtros, **mudancas) -> str:
    """A URL da tela com alguns filtros trocados. Os demais são preservados.

    Preservar é o ponto: descer um nível não pode perder a janela de seis meses
    nem o serviço que a pessoa acabou de escolher — e perder isso é como alguém
    conclui que o filtro "não funciona".
    """
    from urllib.parse import urlencode

    atual = {
        "competencia": filtros.competencia.strftime("%Y-%m"),
        "regional": filtros.regional,
        "cc": filtros.centro_custo,
        "contrato": filtros.contrato,
        "servico": filtros.servico,
        "layer": filtros.layer,
        "janela": str(filtros.meses),
    }
    if filtros.deficitario:
        atual["deficitario"] = "1"
    atual.update(mudancas)
    return f"{base}?{urlencode({k: v for k, v in atual.items() if v})}"


def migalhas(filtros: Filtros, base: str) -> list:
    """A trilha, sempre visível e sempre clicável.

    Trilha e não botão "voltar": quem desceu três níveis precisa poder subir
    dois, e um botão só sobe um. E ela aparece **mesmo na raiz**, com um degrau
    só — sem isso, ela nasce no primeiro clique e some no último, que é quando
    a pessoa mais precisa saber onde está.
    """
    from workspace.graficos.series import Migalha

    profundidade = nivel_de(filtros)
    trilha = [
        Migalha(
            rotulo="Empresa",
            url=_url_com(base, filtros, regional="", cc="", contrato=""),
            atual=profundidade == 0,
        )
    ]
    valores = (filtros.regional, filtros.centro_custo, filtros.contrato)
    for indice, (parametro, _, _) in enumerate(HIERARQUIA):
        if not valores[indice]:
            break
        # Ao voltar para um degrau, os de baixo são LIMPOS: subir para a regional
        # com o centro de custo ainda no filtro mostraria a regional recortada
        # por um CC que a trilha diz não estar mais ativo.
        limpeza = {p: "" for p, _, _ in HIERARQUIA[indice + 1:]}
        trilha.append(
            Migalha(
                rotulo=valores[indice],
                url=_url_com(base, filtros, **limpeza),
                atual=indice + 1 == profundidade,
            )
        )
    return trilha


def _bloco_perfuracao(escopo, filtros: Filtros, base: str):
    """A barra do nível seguinte — cada barra desce um degrau.

    Sai da CARTEIRA e não de uma consulta própria: ela já respeita o escopo da
    pessoa, e uma segunda consulta poderia oferecer uma regional que ela não
    alcança — o que revelaria a existência dela.
    """
    from workspace.graficos import series

    profundidade = nivel_de(filtros)
    if profundidade >= len(HIERARQUIA):
        return series.barras_por_categoria(
            [], chave="perfuracao", titulo="Detalhe", fronteira=FRONTEIRA
        )

    parametro, rotulo, atributo = HIERARQUIA[profundidade]
    provedor = contrato.obter(contrato.ProvedorCarteira)
    if provedor is None:
        return series.barras_por_categoria(
            [], chave="perfuracao", titulo=f"Receita por {rotulo.lower()}"
        )

    carteira = _filtrar_carteira(provedor.contratos(escopo), filtros)
    por_categoria: dict[str, Decimal] = {}
    for c in carteira:
        chave_cat = getattr(c, atributo, "") or "—"
        por_categoria[chave_cat] = por_categoria.get(chave_cat, Decimal("0")) + (
            c.valor_mensal or Decimal("0")
        )

    pontos = [
        series.Ponto(
            rotulo=nome,
            valor=valor,
            # A URL pronta, do servidor. O JS só navega.
            url=_url_com(base, filtros, **{parametro: nome}) if nome != "—" else "",
        )
        for nome, valor in sorted(por_categoria.items(), key=lambda p: -p[1])
    ]

    return series.barras_por_categoria(
        pontos,
        chave="perfuracao",
        titulo=f"Receita mensal por {rotulo.lower()}",
        rotulo_serie="Valor mensal",
    )


def _estreitar_por_atributo(recorte: contrato.Escopo, filtros: Filtros):
    """Traduz `serviço` e `layer` em uma LISTA DE CONTRATOS, e estreita o escopo.

    Sem isto, os dois filtravam só a faixa da carteira: a pessoa escolhia
    "serviço = cftv", a lista de contratos encolhia, e o gráfico do dinheiro
    continuava mostrando a empresa inteira.

    Duas faixas discordando sobre o mesmo filtro, na mesma tela, é o defeito que
    faz alguém deixar de confiar no número — e ele não dá erro nem aparece em
    log.

    A tradução acontece UMA vez, aqui, e vale para todas as faixas. Fazê-la
    dentro de cada montador seria a mesma consulta cinco vezes, e cinco lugares
    para ela divergir.
    """
    if not (filtros.servico or filtros.layer):
        return recorte

    provedor = contrato.obter(contrato.ProvedorCarteira)
    if provedor is None:
        # Sem carteira não há como traduzir. Devolver o recorte largo mostraria
        # mais do que o filtro pediu; devolver vazio esconderia tudo. O largo é
        # o menos errado: a faixa da carteira já diz que a fonte não respondeu.
        return recorte

    codigos = tuple(
        sorted(
            c.codigo
            for c in provedor.contratos(recorte)
            if (not filtros.servico or c.servico == filtros.servico)
            and (not filtros.layer or c.layer == filtros.layer)
        )
    )
    if not codigos:
        # Nenhum contrato casa. `("",)` é um código que não existe — e é o que
        # faz as faixas dizerem "sem dado" em vez de mostrarem tudo, que é o que
        # uma tupla vazia significaria em `Escopo`.
        codigos = ("",)

    return contrato.Escopo(
        regionais=recorte.regionais,
        centros_custo=recorte.centros_custo,
        contratos=codigos,
    )


def _servicos_oferecidos(faixas: dict) -> list[str]:
    """Os serviços presentes na carteira visível, ordenados.

    Sai das FAIXAS já montadas e não de uma consulta nova: elas já respeitam o
    escopo da pessoa, e uma segunda consulta poderia oferecer um serviço que ela
    não alcança — o que revelaria a existência dele.
    """
    contratos = getattr(faixas.get("contratos"), "conteudo", None) or {}
    return sorted({c.servico for c in contratos.get("carteira", []) if c.servico})


def _competencias_oferecidas(atual: date, quantas: int = MESES_DA_SERIE) -> list[date]:
    """Os meses que o seletor oferece, do mais recente para trás.

    Do ATUAL para trás e não do mês corrente: quem abriu agosto e volta ao
    seletor tem de encontrar julho ao lado, e não descobrir que a lista pulou
    para o mês de hoje.
    """
    meses = []
    ano, mes = atual.year, atual.month
    for passo in range(quantas):
        total = ano * 12 + (mes - 1) - passo
        meses.append(date(total // 12, total % 12 + 1, 1))
    return meses


# ── A tela irmã · de onde vem esse número ───────────────────────────

PERMISSAO_FONTES = "eco.carga"


def pode_ver_fontes(pessoa, cache: dict | None = None) -> bool:
    """Quem opera e a diretoria.

    Separada de `eco.ler` de propósito: **ver a tela de fontes não dá acesso aos
    números**. O T.I. precisa consertar uma carga sem enxergar o resultado
    financeiro, e a diretoria precisa saber de onde vem o número sem precisar de
    um chamado.
    """
    from identidade.services.autorizacao import pode

    return pode(pessoa, PERMISSAO_FONTES, cache=cache)


def pode_recarregar(pessoa, cache: dict | None = None) -> bool:
    """Mesma permissão da tela, e é deliberado.

    Um botão que só quem opera enxerga, numa tela que a diretoria abre, seria
    duas regras para o mesmo assunto. Quem pode abrir a tela pode mandar
    recarregar — a ação é idempotente e o registro guarda quem pediu.
    """
    return pode_ver_fontes(pessoa, cache=cache)


def mapa_das_faixas() -> list[dict]:
    """Faixa → fonte, para a tela 99 responder "de onde vem esse número".

    Sai de `DEFINICOES`, e não de uma lista à mão nem de montar as seis faixas
    só para ler dois campos de cada: a primeira opção apodrece, a segunda toca o
    banco numa tela que não mostra número nenhum.
    """
    return [
        {"chave": chave, "faixa": DEFINICOES[chave][0], "fonte": DEFINICOES[chave][1]}
        for chave, _ in MONTADORES
    ]


def panorama_das_fontes() -> dict:
    """Tudo o que a tela 99 mostra.

    Sem provedor registrado, ela **não some**: mostra o mapa das faixas e diz
    que nenhuma fonte se registrou. Sumir esconderia que a tela existe — e ela
    existe justamente para quando algo está errado.
    """
    from workspace.providers import frescor as contrato_frescor

    provedor = contrato_frescor.obter()
    if provedor is None:
        return {
            "fontes": [],
            "historico": [],
            "divergencias": [],
            "mapa": mapa_das_faixas(),
            "motivo": (
                "Nenhuma fonte se registrou neste ambiente. O app de cargas não "
                "está instalado, ou o registro não rodou."
            ),
        }

    fontes = provedor.fontes()
    return {
        "fontes": [
            {"fonte": fonte, "carimbo": frs.de(fonte.chave)} for fonte in fontes
        ],
        "historico": provedor.historico(limite=20),
        "divergencias": provedor.divergencias(abertas=True),
        "mapa": mapa_das_faixas(),
        "motivo": "",
    }
