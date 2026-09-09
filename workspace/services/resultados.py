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
from workspace.graficos import formato as fmt
from workspace.services import frescor as frs

PERMISSAO = "eco.ler"

#: As duas telas irmãs, com permissão PRÓPRIA — ver ADR-042.
#:
#: Quadro e jornada e Satisfação do cliente eram faixas da tela 10. São
#: perguntas de outra gente: o turnover de um centro de custo é conversa de
#: R.H., e o NPS é do comercial. Enquanto exigiam `eco.ler`, dar qualquer uma
#: das duas a essa gente significava dar junto a margem de todo contrato — e por
#: isso ninguém dava, e as duas ficavam sendo lidas só pela diretoria.
PERMISSAO_PESSOAS = "eco.pessoas"
PERMISSAO_SATISFACAO = "eco.satisfacao"

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


def escopo_de(
    pessoa,
    permissao: str = PERMISSAO,
    cache: dict | None = None,
    recusa: str = "Esta tela é de quem responde por resultado.",
) -> contrato.Escopo:
    """O recorte desta pessoa, traduzido do que `pode()` respondeu.

    Três respostas possíveis, e a terceira é 403:

    - **global** — a empresa inteira. Diretoria, sócios, R.H. e Financeiro.
    - **departamento/unidade** — o próprio centro de custo, e a regional quando
      a lotação tem unidade. É o gerente, que precisa dos números da operação
      dele sem ver os da empresa.
    - **nada** — 403. Resultado financeiro não é informação institucional.

    `permissao` é parâmetro porque as três telas — 10, 16 e 17 — recortam
    IGUAL e autorizam DIFERENTE. Copiar esta função para cada uma criaria três
    lugares onde "o gerente vê só o centro de custo dele" está escrito, e o dia
    em que discordassem uma delas vazaria sem deixar rastro.
    """
    escopo = escopo_da_permissao(pessoa, permissao, cache=cache)
    if escopo is None:
        raise SemResultados(recusa)
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


def tem_acesso(
    pessoa, permissao: str = PERMISSAO, cache: dict | None = None
) -> bool:
    """Se o trilho mostra o item. Exceção é para o caminho errado, não para um `if`."""
    try:
        escopo_de(pessoa, permissao, cache=cache)
    except SemResultados:
        return False
    return True


def tem_acesso_a_pessoas(pessoa, cache: dict | None = None) -> bool:
    return tem_acesso(pessoa, PERMISSAO_PESSOAS, cache=cache)


def tem_acesso_a_satisfacao(pessoa, cache: dict | None = None) -> bool:
    return tem_acesso(pessoa, PERMISSAO_SATISFACAO, cache=cache)


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
    #: A UNIDADE do organograma. NÃO é campo de formulário: ela é a ponte entre
    #: a permissão e o espelho (`Escopo.regionais` vem de `lotacao.unidade.nome`),
    #: e continua existindo como nível da perfuração. Quem quer recortar a
    #: carteira usa `area` — ver `resultados.models.Area`.
    regional: str = ""
    centro_custo: str = ""
    contrato: str = ""
    #: ÁREA e SERVIÇO aceitam vários valores; os três acima, um só.
    #:
    #: A diferença não é de gosto: os três acima são uma hierarquia, e "desça
    #: para dois lugares ao mesmo tempo" não é uma pergunta. Área e serviço são
    #: atributos — comparar a Área 01 com a 03 é exatamente o que se quer.
    area: tuple[str, ...] = ()
    servico: tuple[str, ...] = ()
    status: str = ""
    #: `"1"`, `"2"`, `"3"` — o porte do contrato. String e não inteiro porque
    #: `sem_amostra` é uma resposta legítima do espelho, e não um número.
    layer: str = ""
    deficitario: bool = False
    #: O período da leitura: `mes`, `3m`, `6m`, `9m` ou `12m`.
    #:
    #: Filtro de LEITURA e não de dado. Nasceu de uma reclamação concreta — "os
    #: números ficam um em cima do outro". Girar o rótulo resolveu metade; poder
    #: estreitar o período é a outra metade, e é a que a pessoa controla.
    #:
    #: Era `janela: int` até 08/09/2026, com o número de meses direto na URL.
    #: Virou nome por dois motivos: `?janela=9` não diz o que significa a quem
    #: lê o link, e o inteiro livre aceitava `?janela=7`, um recorte que a tela
    #: oferece sem oferecer — e que ninguém sabe interpretar.
    periodo: str = ""
    #: COM QUE COMPARAR — F1. Vazio é "com nada", e é o padrão.
    #:
    #: Separado do período de propósito: "quero ver seis meses" e "quero ver
    #: contra o ano passado" são duas perguntas, e um seletor só para as duas
    #: obrigaria a escolher entre elas.
    comparar: str = ""
    #: Os grupos abertos na tabela contábil — D1. Na URL para o link chegar
    #: aberto no ponto certo do outro lado.
    expandidos: tuple[str, ...] = ()
    #: Por qual dimensão o bloco de perfuração agrupa. Vazio = a do nível
    #: seguinte na hierarquia, que é o que quem não escolheu nada quer.
    dimensao: str = ""

    @property
    def de(self) -> date:
        """O início da série."""
        ano, mes = self.competencia.year, self.competencia.month
        total = ano * 12 + (mes - 1) - (self.meses - 1)
        return date(total // 12, total % 12 + 1, 1)

    @property
    def meses(self) -> int:
        """Quantos meses a série cobre, do período escolhido.

        Preso ao teto da série. O PISO deixou de ser três em 08/09/2026, com a
        entrada de "Mês atual" — ver `PERIODOS` para o que isso custa e por que
        vale.
        """
        return max(1, min(MESES_POR_PERIODO.get(self.periodo, PERIODO_PADRAO_MESES),
                          MESES_DA_SERIE))

    @property
    def so_o_mes(self) -> bool:
        """"Mês atual" — o único período em que NÃO há série para desenhar.

        A tela usa isto para trocar o gráfico pela tabela do mês em vez de
        desenhar uma barra sozinha. Uma barra sem vizinha não mostra tendência
        nenhuma e ocupa o espaço de quem mostraria.
        """
        return self.meses == 1

    @property
    def rotulo_do_periodo(self) -> str:
        """"últimos 12 meses" — o texto que entra no título de cada gráfico.

        No título e não só na barra de filtros: o gráfico é o que a pessoa
        fotografa e cola numa mensagem, e fora da tela ele perde o recorte.
        """
        return ROTULO_DO_PERIODO.get(self.periodo, "")

    @property
    def ate(self) -> date:
        ultimo = calendar.monthrange(self.competencia.year, self.competencia.month)[1]
        return date(self.competencia.year, self.competencia.month, ultimo)

    @property
    def meses_atras(self) -> int:
        """Quantos meses a comparação recua. `0` = não há comparação."""
        return MESES_DA_COMPARACAO.get(self.comparar, 0)

    @property
    def de_comparado(self) -> date | None:
        """O início da janela comparada, ou `None`.

        Recua a janela INTEIRA, e não só o mês: comparar seis meses de 2026 com
        um mês de 2025 seria comparar coisas diferentes com a mesma altura na
        tela — o erro que mais gera decisão errada em reunião.
        """
        return _recuar(self.de, self.meses_atras) if self.meses_atras else None

    @property
    def ate_comparado(self) -> date | None:
        if not self.meses_atras:
            return None
        fim = _recuar(self.competencia, self.meses_atras)
        ultimo = calendar.monthrange(fim.year, fim.month)[1]
        return date(fim.year, fim.month, ultimo)

    @property
    def rotulo_do_comparado(self) -> str:
        return ROTULO_DA_COMPARACAO.get(self.comparar, "")

    def aplicar(self, escopo: contrato.Escopo) -> contrato.Escopo:
        """O filtro ESTREITA o escopo; nunca o alarga.

        Um gerente que digitasse `?cc=1055` na URL continua vendo só o dele — o
        filtro entra por INTERSEÇÃO, e o que ele não pode ver não volta por uma
        query string.

        **Área e serviço não passam por `_estreitar`, e a razão importa:**
        `_estreitar` existe para o caso em que a permissão já limitou o
        conjunto. Ninguém é lotado numa área comercial nem num tipo de serviço —
        a permissão nunca preenche esses dois. Eles só podem ESTREITAR, porque
        entram com **E** contra o nível no `_recortar` do espelho: pedir uma
        área que a pessoa não alcança devolve vazio, e não a área.
        """
        regionais = _estreitar(escopo.regionais, self.regional)
        centros = _estreitar(escopo.centros_custo, self.centro_custo)
        contratos = _estreitar(escopo.contratos, self.contrato)
        return contrato.Escopo(
            regionais=regionais,
            centros_custo=centros,
            contratos=contratos,
            areas=self.area,
            servicos=self.servico,
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
        competencia=_competencia(_mes_pedido(parametros), hoje),
        regional=(parametros.get("regional") or "").strip()[:60],
        centro_custo=(parametros.get("cc") or "").strip()[:20],
        contrato=(parametros.get("contrato") or "").strip()[:40],
        area=_lista(parametros, "area", 20),
        servico=_lista(parametros, "servico", 20),
        status=(parametros.get("status") or "").strip()[:20],
        layer=(parametros.get("layer") or "").strip()[:12],
        deficitario=parametros.get("deficitario") in ("1", "true", "sim"),
        periodo=_periodo(parametros),
        comparar=_comparacao(parametros),
        expandidos=_expandidos(parametros),
        dimensao=(parametros.get("dim") or "").strip()[:20],
    )


#: Quantos valores um filtro multi aceita. Doze é mais que as cinco áreas e os
#: cinco serviços somados — o teto existe para uma URL forjada com duzentos
#: valores não virar um `IN` de duzentos itens no banco.
MAXIMO_MULTI = 12


def _lista(parametros, nome: str, tamanho: int) -> tuple[str, ...]:
    """Os valores de um filtro multi, sem repetição e na ordem em que vieram.

    `getlist` quando existe (é um `QueryDict`) e `get` quando não (é um dict
    comum, como os testes passam). Sem esse cuidado, a mesma função devolveria
    coisas diferentes conforme quem chama — e o teste passaria enquanto a tela
    não funcionaria.

    Ordem preservada porque ela aparece na frase do recorte: "Área 01 e Área 03"
    tem de sair na ordem em que a pessoa marcou, senão o texto muda sozinho a
    cada recarga.
    """
    if hasattr(parametros, "getlist"):
        crus = parametros.getlist(nome)
    else:
        bruto = parametros.get(nome)
        crus = bruto if isinstance(bruto, (list, tuple)) else [bruto]

    vistos: list[str] = []
    for valor in crus:
        limpo = (str(valor) if valor is not None else "").strip()[:tamanho]
        if limpo and limpo not in vistos:
            vistos.append(limpo)
    return tuple(vistos[:MAXIMO_MULTI])


def _mes_pedido(parametros) -> str | None:
    """`?mes=` é o nome; `?competencia=` continua sendo lido — A1.

    O nome mudou porque "competência" é palavra de contabilidade e a barra é
    lida por quem não é do financeiro. O antigo continua valendo por uma versão
    porque links já foram compartilhados: quebrá-los faria alguém abrir a tela
    no mês errado sem perceber, que é pior que o nome ruim.

    O NOVO tem precedência quando os dois vêm — se alguém montar a URL com os
    dois, quis o que digitou por último, e o que digitou por último é `mes`.

    Remover em: qualquer momento depois de 03/2027, quando os links de 2026
    tiverem envelhecido.
    """
    return parametros.get("mes") or parametros.get("competencia")


def _recuar(momento: date, meses: int) -> date:
    """`date` deslocada `meses` para trás, no dia 1º."""
    total = momento.year * 12 + (momento.month - 1) - meses
    return date(total // 12, total % 12 + 1, 1)


def _comparacao(parametros) -> str:
    """`?comparar=` — valor fora da lista vira "nenhum", e não erro."""
    pedido = (parametros.get("comparar") or "").strip().lower()
    return pedido if pedido in MESES_DA_COMPARACAO else ""


def _periodo(parametros) -> str:
    """O período pedido, ou o padrão. Valor fora da lista NÃO é erro.

    `?periodo=abacaxi` é uma URL digitada errada, e responder 500 a ela
    ensinaria a não brincar com a barra de endereço — que é justamente o que a
    tela quer que as pessoas façam.

    Lê `?janela=` também, pelo mesmo motivo de `_mes_pedido`: `?janela=6` já
    circulou em links, e o número traduz direto para o período equivalente.
    """
    pedido = (parametros.get("periodo") or "").strip().lower()
    if pedido in MESES_POR_PERIODO:
        return pedido

    antigo = _inteiro(parametros.get("janela"), 0)
    if antigo:
        # O período cujo tamanho mais se aproxima, sem passar do teto.
        cabe = [v for v, _, m in PERIODOS if m <= antigo]
        if cabe:
            return cabe[-1]
    return PERIODO_PADRAO


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
    "contabil": ("Com o que foi gasto", "sankhya"),
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

    # A JANELA COMPARADA — F1. Segunda consulta e não um recorte da primeira:
    # ela está fora do intervalo que a primeira pediu, e reaproveitar seria
    # buscar treze meses para mostrar doze, que foi exatamente o que o período
    # nomeado veio desfazer.
    comparada = []
    if filtros.de_comparado is not None:
        comparada = provedor.serie_competencia(
            escopo, filtros.de_comparado, filtros.ate_comparado
        )

    faixa.conteudo = {
        "serie": serie,
        "comparacao": _comparacao_em_texto(serie, comparada, filtros),
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
            _titulo("Receita bruta", filtros),
            comparada=comparada,
            rotulo_comparado=filtros.rotulo_do_comparado,
        ),
        # EBITDA fica SEM par: o espelho não traz EBITDA orçado. Inventar um
        # denominador para ter a linha seria a pior forma de completar um
        # gráfico — o bloco diz o que tem, e a razão fica de fora.
        "grafico_ebitda": _bloco_mensal(
            serie, "ebitda", "ebitda", _titulo("EBITDA", filtros)
        ),
    }
    return faixa


def _com_graficos(faixas: dict) -> None:
    """Acrescenta o gráfico de cada faixa — passo 6.

    Fora dos montadores de propósito: eles são a leitura do espelho, e desenhar
    é outra coisa. Misturar as duas faria cada montador precisar do catálogo de
    gráficos para responder quantos contratos existem.
    """
    contratos_ = faixas.get("contratos")
    if contratos_ is not None and contratos_.disponivel and contratos_.conteudo:
        contratos_.conteudo["grafico"] = _grafico_da_carteira(contratos_.conteudo)
        contratos_.conteudo["grafico_mix"] = _grafico_do_mix(contratos_.conteudo)
        contratos_.conteudo["fora_do_grafico"] = sum(
            1
            for c in contratos_.conteudo.get("carteira", [])
            if c.margem_contribuicao_pct is None or c.layer == SEM_AMOSTRA
        )

    vencimentos_ = faixas.get("vencimentos")
    if vencimentos_ is not None and vencimentos_.disponivel and vencimentos_.conteudo:
        vencimentos_.conteudo["grafico"] = _grafico_dos_vencimentos(
            vencimentos_.conteudo
        )

    projetos_ = faixas.get("projetos")
    if projetos_ is not None and projetos_.disponivel and projetos_.conteudo:
        rosca, bullet = _grafico_dos_projetos(projetos_.conteudo)
        projetos_.conteudo["grafico"] = rosca
        projetos_.conteudo["grafico_marcos"] = bullet

    pessoas_ = faixas.get("pessoas")
    if pessoas_ is not None and pessoas_.disponivel and pessoas_.conteudo:
        pessoas_.conteudo["mapa"] = _mapa_do_quadro(pessoas_.conteudo)

    satisfacao_ = faixas.get("satisfacao")
    if satisfacao_ is not None and satisfacao_.disponivel and satisfacao_.conteudo:
        satisfacao_.conteudo["grafico"] = _grafico_da_satisfacao(satisfacao_.conteudo)


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
    faixa.conteudo["dimensoes"] = [
        {
            "parametro": parametro,
            "rotulo": rotulo,
            "url": _url_com(base, filtros, dim=parametro),
            "atual": parametro == dimensao_de(filtros)[0],
        }
        for parametro, rotulo, _, _ in DIMENSOES
    ]
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


def _titulo(assunto: str, filtros: Filtros) -> str:
    """"Receita bruta — últimos 12 meses" — A2.

    O recorte vai no TÍTULO, e não só na barra de filtros: o gráfico é o que a
    pessoa fotografa e cola numa mensagem, e fora da tela ele perde o recorte.
    Um gráfico de seis meses lido como se fosse de doze é o tipo de erro que
    ninguém percebe porque nada parece errado.
    """
    recorte = filtros.rotulo_do_periodo
    return f"{assunto} — {recorte}" if recorte else assunto


def _comparacao_em_texto(serie, comparada, filtros: Filtros) -> dict | None:
    """Período atual, período comparado e a VARIAÇÃO — F1.

    "Nunca deixar a comparação implícita": o gráfico mostra duas curvas, e duas
    curvas não dizem de quanto foi a diferença. Sem o número escrito, cada
    pessoa na reunião estima uma coisa olhando a mesma tela.

    Devolve `None` quando não há comparação pedida OU quando o período anterior
    não tem dado. A segunda é importante: uma variação contra zero é sempre
    "+∞%", e mostrá-la seria pior que não mostrar nada.
    """
    if not comparada:
        return None

    atual = sum((linha.receita_bruta or Decimal("0")) for linha in serie)
    antes = sum((linha.receita_bruta or Decimal("0")) for linha in comparada)
    if not antes:
        return None

    variacao = ((atual - antes) / antes * Decimal("100")).quantize(Decimal("0.1"))
    return {
        "rotulo": filtros.rotulo_do_comparado,
        "atual": atual,
        "anterior": antes,
        "variacao": variacao,
        # FORMATADO AQUI, e não no template. A regra de pt-BR mora num lugar
        # só; um filtro novo para isto seria o segundo, e o dia em que os dois
        # arredondassem diferente ninguém saberia qual está certo.
        #
        # `com_sinal` porque em variação a DIREÇÃO é a informação — é o que
        # separa "+2,3%" de "2,3%", que sozinho não diz nada.
        "variacao_texto": fmt.percentual(variacao, com_sinal=True),
        "atual_texto": fmt.moeda(atual),
        "anterior_texto": fmt.moeda(antes),
        "de": filtros.de_comparado,
        "ate": filtros.ate_comparado,
        # `subiu` e não só o sinal: a tela precisa escolher a palavra e a cor, e
        # `variacao > 0` espalhado por template é a regra em dois lugares.
        "subiu": variacao > 0,
    }


def _alinhar_por_posicao(serie, comparada, campo: str) -> list:
    """A série comparada, na ordem dos meses da série atual.

    Por POSIÇÃO e não por rótulo: os meses têm nomes diferentes — 09/25 contra
    09/26 —, e casar por nome não casaria nada. A posição é o que faz "o
    primeiro mês da janela" encontrar "o primeiro mês da janela anterior".

    Sobra vira `None` em vez de erro: janelas de tamanhos diferentes acontecem
    quando o espelho não tem todos os meses do período anterior, e um mês sem
    par é um ponto ausente na linha — não uma tela quebrada.
    """
    _, atual = _por_mes(serie, campo)
    ordem_antes, antes = _por_mes(comparada, campo)
    valores = [antes[rotulo] for rotulo in ordem_antes]
    faltam = len(atual) - len(valores)
    return valores + [None] * faltam if faltam > 0 else valores[: len(atual)]


def _bloco_comparado(
    linhas,
    campo_re: str,
    campo_or: str,
    chave: str,
    titulo: str,
    comparada=(),
    rotulo_comparado: str = "",
):
    """Realizado × orçado, com o `% do orçado` na linha do eixo direito.

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
        comparado=(
            _alinhar_por_posicao(linhas, comparada, campo_re) if comparada else None
        ),
        rotulo_comparado=rotulo_comparado,
        rotulo_a="Realizado",
        rotulo_b="Orçado",
        # "%RExOR" era a sigla do benchmark, e ela ia para a LEGENDA — onde o
        # "x" no meio faz parecer multiplicação. É divisão.
        rotulo_linha="% do orçado",
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


# ── O bloco D · a tabela contábil ───────────────────────────────────


#: Quantos grupos podem estar abertos ao mesmo tempo. Não é limite técnico: é o
#: que cabe numa tela sem a linha de total sair de vista, e a linha de total é o
#: que faz a tabela ser conferível.
MAXIMO_EXPANDIDO = 8


def _expandidos(parametros) -> tuple[str, ...]:
    """Os grupos abertos, de `?expandir=41101,41106`.

    Na URL e não em `sessionStorage`: mandar o link **já aberto no ponto certo**
    é o que faz a reunião andar. Guardado no navegador, o link chegaria fechado
    do outro lado e a pessoa teria de procurar de novo o que já foi mostrado.
    """
    bruto = (parametros.get("expandir") or "").strip()
    if not bruto:
        return ()
    vistos: list[str] = []
    for codigo in bruto.split(","):
        limpo = codigo.strip()[:20]
        if limpo and limpo not in vistos:
            vistos.append(limpo)
    return tuple(vistos[:MAXIMO_EXPANDIDO])


def contabil(escopo: contrato.Escopo, filtros: Filtros) -> Faixa:
    """"Sei que meu contrato vale 30 milhões, mas preciso saber com o que
    gastei."

    ## A tabela é do MÊS, e não do período

    O período move os gráficos; esta tabela responde "onde foi o dinheiro DESTE
    mês". Somar doze meses por conta produziria um número que não bate com
    nenhum fechamento contábil, e é contra o fechamento que alguém confere.

    ## Os totais saem das MESMAS linhas que a tabela mostra

    Um total calculado à parte pode discordar da soma visível — e detalhe que
    não bate com o total destrói a confiança na tela inteira. É a mesma regra
    que a perfuração já segue.
    """
    faixa = _faixa("contabil", filtros.competencia)
    provedor = contrato.obter(contrato.ProvedorResultadoFinanceiro)
    if provedor is None:
        return _sem_fonte(faixa, "Sankhya")

    inicio = date(filtros.competencia.year, filtros.competencia.month, 1)
    linhas = provedor.por_conta(escopo, inicio, filtros.ate)
    if not linhas:
        return _sem_dado(faixa, "lançamento por conta contábil")

    receita_liquida = _receita_liquida(linhas)
    faixa.conteudo = {
        "grupos": _agrupar_por_conta(linhas, receita_liquida, filtros),
        "totais": _totais_contabeis(linhas, receita_liquida),
        "receita_liquida": receita_liquida,
        "expandidos": filtros.expandidos,
        # Quantas linhas a fonte mandou com código fora do plano. Zero é o
        # normal; qualquer outra coisa é um aviso na tela, e não um silêncio.
        "desconhecidas": sum(1 for linha in linhas if linha.desconhecida),
    }
    return faixa


#: As naturezas que SAEM do caixa. Elas entram na tabela com sinal negativo.
NATUREZAS_NEGATIVAS = frozenset({"imposto", "custo", "indireto"})


def _sinal(natureza: str) -> int:
    """`+1` para o que entra, `-1` para o que sai.

    O SINAL e não só a cor. Duas razões, e a segunda é a que decide:

    A regra do produto é "cor nunca sozinha" — e aqui ela seria pior que o
    normal, porque a tabela tem linha de receita e linha de despesa: vermelho
    sobre um número que já é negativo diria a mesma coisa duas vezes enquanto
    deixa o positivo mudo.

    E sem sinal o TOTAL não significa nada. Somando receita, imposto e custo
    como números positivos, a última linha da tabela dá dois milhões e duzentos
    mil de coisa nenhuma. Com sinal, ela é o resultado — que é justamente o
    número contra o qual alguém confere a tabela inteira.
    """
    return -1 if natureza in NATUREZAS_NEGATIVAS else 1


def _receita_liquida(linhas) -> Decimal:
    """Receita bruta menos impostos — o denominador de toda coluna de `%`.

    Calculada uma vez e passada adiante, e não recalculada em cada grupo: com
    vinte e oito grupos seriam vinte e oito somas da mesma coisa, e a primeira
    que divergisse faria dois percentuais da mesma tabela não fecharem.
    """
    receita = sum(
        (linha.realizado_ajustado for linha in linhas if linha.natureza == "receita"),
        Decimal("0"),
    )
    impostos = sum(
        (linha.realizado_ajustado for linha in linhas if linha.natureza == "imposto"),
        Decimal("0"),
    )
    return receita - impostos


def _agrupar_por_conta(
    linhas, receita_liquida: Decimal, filtros: Filtros | None = None
) -> list[dict]:
    """Os dois primeiros níveis: grupo sintético e conta analítica.

    O terceiro — rateio por contrato — sai de `contas_do_contrato`, e só quando
    alguém expande a conta. Montá-lo aqui produziria centenas de linhas que
    ninguém pediu, e a tela ficaria pesada para responder a pergunta de sempre,
    que é a do nível 1.
    """
    grupos: dict[str, dict] = {}
    for linha in linhas:
        grupo = grupos.setdefault(
            linha.grupo_codigo,
            {
                "codigo": linha.grupo_codigo,
                "nome": linha.grupo_nome,
                "degrau": linha.degrau,
                "natureza": linha.natureza,
                "desconhecida": linha.desconhecida,
                "contas": {},
                "realizado": Decimal("0"),
                "ajustes": Decimal("0"),
                "orcado": None,
            },
        )
        conta = grupo["contas"].setdefault(
            linha.codigo,
            {
                "codigo": linha.codigo,
                "nome": linha.nome,
                "realizado": Decimal("0"),
                "ajustes": Decimal("0"),
                "orcado": None,
            },
        )
        sinal = _sinal(linha.natureza)
        for alvo in (grupo, conta):
            alvo["realizado"] += linha.realizado * sinal
            alvo["ajustes"] += linha.ajustes * sinal
            if linha.orcado is not None:
                alvo["orcado"] = (
                    (alvo["orcado"] or Decimal("0")) + linha.orcado * sinal
                )

    montados = []
    for grupo in grupos.values():
        grupo["contas"] = [
            _com_derivadas(conta, receita_liquida)
            for conta in sorted(grupo["contas"].values(), key=lambda c: c["codigo"])
        ]
        _com_expansao(grupo, filtros)
        montados.append(_com_derivadas(grupo, receita_liquida))
    return sorted(montados, key=lambda g: g["codigo"])


def _com_expansao(grupo: dict, filtros: Filtros | None) -> None:
    """`aberto` e a URL que alterna — montada em PYTHON.

    A URL sai daqui pela mesma razão da perfuração: só o servidor sabe quais
    filtros preservar ao mudar um deles. Montá-la em JavaScript replicaria essa
    regra num segundo lugar, e ela mudaria sozinha na primeira dimensão nova.
    """
    if filtros is None:
        grupo["aberto"] = False
        grupo["url_alternar"] = ""
        return

    from django.urls import reverse

    codigo = grupo["codigo"]
    abertos = filtros.expandidos
    grupo["aberto"] = codigo in abertos
    # Fechar TIRA o próprio; abrir ACRESCENTA no fim. Acrescentar no começo
    # faria a ordem da URL mudar a cada clique, e dois links do mesmo estado
    # ficariam com textos diferentes.
    novos = (
        tuple(c for c in abertos if c != codigo)
        if grupo["aberto"]
        else (*abertos, codigo)
    )
    grupo["url_alternar"] = _url_com(
        reverse("workspace:resultados"), filtros, expandir=",".join(novos)
    )


def _com_derivadas(linha: dict, receita_liquida: Decimal) -> dict:
    """As colunas que se calculam — D3.

    Elas ficam no SERVIÇO e não no template, porque `% da receita` é regra de
    negócio: o dia em que a base mudar de receita líquida para bruta, ela muda
    num lugar. Num filtro de template, mudaria em cada tela que o usasse.
    """
    realizado = linha["realizado"]
    ajustado = realizado + linha["ajustes"]
    orcado = linha["orcado"]
    linha["realizado_ajustado"] = ajustado
    linha["pct_re_or"] = _percentual(ajustado, orcado)
    # `orçado − realizado`, e não o contrário: positivo é FOLGA. Invertido, um
    # número positivo significaria estouro, e a leitura de relance seria o
    # oposto do que a cor sugere.
    linha["dif_or_re"] = (orcado - ajustado) if orcado is not None else None
    # O PERCENTUAL usa o valor ABSOLUTO, e o número ao lado carrega o sinal.
    #
    # "Pessoal: −207.412, 18,9% da receita líquida" é como se lê em voz alta.
    # Com o percentual negativo junto, a mesma linha diria a direção duas vezes
    # e a coluna deixaria de somar 100% entre as despesas.
    linha["pct_da_receita"] = _sobre(abs(ajustado), receita_liquida)
    return linha


def _totais_contabeis(linhas, receita_liquida: Decimal) -> dict:
    total = {
        "realizado": sum(
            (linha.realizado * _sinal(linha.natureza) for linha in linhas),
            Decimal("0"),
        ),
        "ajustes": sum(
            (linha.ajustes * _sinal(linha.natureza) for linha in linhas),
            Decimal("0"),
        ),
        "orcado": None,
    }
    orcados = [
        linha.orcado * _sinal(linha.natureza)
        for linha in linhas
        if linha.orcado is not None
    ]
    if orcados:
        total["orcado"] = sum(orcados, Decimal("0"))
    return _com_derivadas(total, receita_liquida)


def contas_do_contrato(
    escopo: contrato.Escopo, filtros: Filtros, conta: str
) -> list[dict]:
    """O NÍVEL 3 — o rateio de uma conta por contrato.

    Só existe porque o Sankhya traz o contrato na linha do razão. Sem isso a
    coluna ficaria sempre vazia, e coluna sempre vazia é pior que a ausência
    dela: ela promete um detalhe que não vem.
    """
    provedor = contrato.obter(contrato.ProvedorResultadoFinanceiro)
    if provedor is None:
        return []

    inicio = date(filtros.competencia.year, filtros.competencia.month, 1)
    por_contrato: dict[str, dict] = {}
    for linha in provedor.por_conta(escopo, inicio, filtros.ate):
        if linha.codigo != conta:
            continue
        chave = linha.contrato or ""
        alvo = por_contrato.setdefault(
            chave,
            {
                "contrato": chave,
                # Sem contrato é o RATEIO do centro de custo, e ele precisa
                # aparecer nomeado — some da lista, o nível 3 não fecha com o
                # nível 2 logo acima.
                "rotulo": chave or f"Rateio do CC {linha.centro_custo}",
                "realizado": Decimal("0"),
                "ajustes": Decimal("0"),
                "orcado": None,
            },
        )
        alvo["realizado"] += linha.realizado
        alvo["ajustes"] += linha.ajustes
        if linha.orcado is not None:
            alvo["orcado"] = (alvo["orcado"] or Decimal("0")) + linha.orcado

    return sorted(por_contrato.values(), key=lambda c: -c["realizado"])


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
    # Área e serviço NÃO aparecem aqui: eles já foram filtrados em SQL, no
    # `_recortar` do espelho. Repetir o filtro em Python seria um segundo lugar
    # com a mesma regra — e o dia em que os dois discordassem, a carteira e o
    # gráfico do dinheiro mostrariam contratos diferentes sem ninguém saber.
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

    percentuais = {
        classe: _sobre(Decimal(quantidade), Decimal(total))
        for classe, quantidade in por_classe.items()
    }
    faixa.conteudo = {
        "total": total,
        "contagem": por_classe,
        "percentuais": percentuais,
        # O NPS — e ele NÃO estava em lugar nenhum desta tela.
        #
        # A tela mostrava a distribuição três vezes (a barra, a tabela irmã e
        # uma linha de três indicadores) e nunca o número que dá nome a ela.
        # Promotores menos detratores, em pontos percentuais: é assim que o
        # índice é definido, e é o que alguém pergunta primeiro.
        "nps": (percentuais["promotor"] - percentuais["detrator"]).quantize(
            Decimal("0.1")
        ),
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
    #: `critico` > `atencao` > `neutro`. A distinção não é decorativa: o cartão
    #: de FONTE DESATUALIZADA invalida a leitura de tudo o que está abaixo dele
    #: na tela, e os outros apontam um número que merece conversa. Lidos com o
    #: mesmo peso, a pessoa trata "o Sankhya não carregou" como se fosse mais um
    #: contrato deficitário — e decide sobre um dado velho sem saber.
    #:
    #: Todos os cartões nasciam `atencao`, e um campo que sempre tem o mesmo
    #: valor não diferencia nada.
    severidade: str = "atencao"
    fonte: str = ""
    ancora: str = ""
    #: A pergunta que o cartão responde, para quem não sabe o que ele é. Vai no
    #: `title` do link — o valor sozinho diz "3" e não diz três do quê.
    explicacao: str = ""


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
                severidade="critico",
                fonte=faixa.fonte,
                ancora="fontes",
                explicacao=(
                    "Enquanto esta fonte não carregar, os números das faixas "
                    "que dependem dela são os da última carga boa."
                ),
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
                    valor=fmt.percentual(pct),
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
                valor=fmt.percentual(pior.turnover_pct),
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
#: As quatro faixas da tela 10. `pessoas` e `satisfacao` SAÍRAM daqui em
#: 04/09/2026: são perguntas de outra gente, e viraram as telas 16 e 17.
#:
#: A tela 10 responde "o que a empresa produziu". Quadro e jornada respondem
#: "como está a equipe", e a avaliação responde "o que o cliente achou" — e
#: nenhuma das duas é lida por quem lê as outras quatro.
MONTADORES = (
    ("dinheiro", dinheiro),
    # A TABELA CONTÁBIL vem logo depois do dinheiro, e antes dos contratos.
    #
    # A ordem é a da pergunta: o bloco do dinheiro responde "quanto entrou e
    # quanto sobrou"; este responde "com o que foi gasto". Quem lê o segundo
    # sem o primeiro não tem denominador, e quem lê os contratos antes de saber
    # onde o dinheiro foi já perdeu a pergunta.
    ("contabil", contabil),
    ("contratos", contratos),
    ("vencimentos", vencimentos),
    ("projetos", projetos),
)

MONTADORES_PESSOAS = (("pessoas", pessoas),)
MONTADORES_SATISFACAO = (("satisfacao", satisfacao),)


def _painel(
    pessoa,
    parametros,
    *,
    permissao: str,
    montadores,
    rota: str,
    recusa: str,
    perfura: bool = False,
    cache: dict | None = None,
) -> dict:
    """O corpo comum das três telas de resultado.

    As três recortam igual, filtram igual, carimbam igual e desenham igual — o
    que muda é a permissão que abre a porta e quais faixas entram. Três cópias
    desta função seriam três lugares onde "o gerente vê só o centro de custo
    dele" está escrito.
    """
    from django.urls import reverse

    escopo = escopo_de(pessoa, permissao, cache=cache, recusa=recusa)
    filtros = ler_filtros(parametros)
    base_url = reverse(rota)
    recorte = _estreitar_por_atributo(filtros.aplicar(escopo), filtros)

    faixas: dict[str, Faixa] = {}
    for chave, montador in montadores:
        faixas[chave] = montador(recorte, filtros)

    # A perfuração entra DEPOIS de a faixa existir, e só na do dinheiro — é o
    # passo 7 do plano: um mecanismo isolado, numa faixa só. Ligar nas cinco de
    # uma vez tornaria impossível dizer qual delas quebrou.
    if perfura:
        _com_perfuracao(faixas["dinheiro"], recorte, filtros)
    _com_graficos(faixas)

    opcoes = _opcoes_de_atributo(escopo)

    return {
        "filtros": filtros,
        "escopo": recorte,
        "escopo_total": escopo.tudo,
        "destaques": destaques(faixas, filtros),
        "faixas": [faixas[chave] for chave, _ in montadores],
        "por_chave": faixas,
        "competencias": _competencias_oferecidas(filtros.competencia),
        # As OPÇÕES saem do que a pessoa ALCANÇA, e não do que ela já filtrou —
        # ver `_opcoes_de_atributo`.
        **opcoes,
        "periodos": PERIODOS,
        "comparacoes": COMPARACOES,
        "recorte_em_texto": recorte_em_texto(filtros, opcoes["areas"]),
        # As TARJAS. Sempre no contexto — inclusive em apresentação, onde os
        # controles somem e elas ficam. Filtro invisível é a principal fonte de
        # "esse número está errado" que não está.
        "filtros_ativos": filtros_ativos(filtros, base_url),
        "url_limpar": url_limpa(filtros, base_url),
        "url_apresentar": url_de_apresentacao(filtros, base_url),
        "url_detalhe": _url_com(reverse("workspace:resultados_detalhe"), filtros),
    }


def painel(pessoa, parametros, cache: dict | None = None) -> dict:
    """Tudo o que a tela mostra. Levanta `SemResultados` para quem não tem escopo."""
    return _painel(
        pessoa,
        parametros,
        permissao=PERMISSAO,
        montadores=MONTADORES,
        rota="workspace:resultados",
        recusa="Esta tela é de quem responde por resultado.",
        perfura=True,
        cache=cache,
    )


def painel_de_pessoas(pessoa, parametros, cache: dict | None = None) -> dict:
    return _painel(
        pessoa,
        parametros,
        permissao=PERMISSAO_PESSOAS,
        montadores=MONTADORES_PESSOAS,
        rota="workspace:quadro",
        recusa="Esta tela é de quem responde por gente.",
        cache=cache,
    )


def painel_de_satisfacao(pessoa, parametros, cache: dict | None = None) -> dict:
    return _painel(
        pessoa,
        parametros,
        permissao=PERMISSAO_SATISFACAO,
        montadores=MONTADORES_SATISFACAO,
        rota="workspace:satisfacao",
        recusa="Esta tela é de quem responde pela relação com o cliente.",
        cache=cache,
    )


#: OS PERÍODOS OFERECIDOS — `(valor, rótulo, meses)`.
#:
#: Nomeados e fechados, em vez de um inteiro livre. `?janela=9` não dizia o que
#: significava a quem lia o link, e aceitava `?janela=7` — um recorte que a tela
#: oferecia sem oferecer, e que ninguém sabe interpretar.
#:
#: **"Mês atual" quebra o piso de três meses, de propósito.** A regra antiga
#: dizia: "três é o mínimo em que uma tendência existe; abaixo disso o gráfico é
#: uma comparação, e comparação se lê melhor em tabela." A regra continua certa,
#: e é por isso que `so_o_mes` existe — nesse período a tela mostra a TABELA do
#: mês em vez de desenhar uma barra sozinha. O período entrou porque "como
#: fechou este mês" é a pergunta mais frequente da reunião mensal; a resposta
#: foi atendê-la sem fingir que uma barra é uma série.
PERIODOS: tuple[tuple[str, str, int], ...] = (
    ("mes", "Mês atual", 1),
    ("3m", "3 meses", 3),
    ("6m", "6 meses", 6),
    ("9m", "9 meses", 9),
    ("12m", "12 meses", 12),
)

#: Doze e não treze. Os treze existiam para o mesmo mês do ano anterior caber na
#: série; a comparação com o ano anterior passou a ser explícita (bloco F), e a
#: série volta a ter o tamanho que a pessoa pediu.
PERIODO_PADRAO = "12m"
PERIODO_PADRAO_MESES = 12

#: COM QUE COMPARAR — `(valor, rótulo, meses de recuo)`. F1.
#:
#: "Nenhum" é uma opção EXPLÍCITA e é a primeira. Sem ela o seletor não teria
#: como desligar a comparação, e uma comparação que não se desliga acaba
#: ficando ligada sem ninguém lembrar de a ter pedido.
#:
#: O trimestre do ano anterior recua doze meses como o ano — o que muda é o
#: RECORTE que a pessoa escolhe no período, não o salto no tempo. Ele existe
#: separado porque nomeia a pergunta que a diretoria faz ("como foi o mesmo
#: trimestre?"), e um seletor que obriga a traduzir a pergunta para "12 meses
#: com período de 3" é um seletor que ninguém usa.
COMPARACOES: tuple[tuple[str, str, int], ...] = (
    ("", "Nenhum", 0),
    ("ano_anterior", "Ano anterior", 12),
    ("trimestre_ano_anterior", "Mesmo trimestre do ano anterior", 12),
    ("dois_anos", "Dois anos atrás", 24),
)

MESES_DA_COMPARACAO: dict[str, int] = {v: m for v, _, m in COMPARACOES if m}
ROTULO_DA_COMPARACAO: dict[str, str] = {v: r for v, r, m in COMPARACOES if m}

MESES_POR_PERIODO: dict[str, int] = {v: m for v, _, m in PERIODOS}
ROTULO_DO_PERIODO: dict[str, str] = {
    "mes": "no mês",
    "3m": "últimos 3 meses",
    "6m": "últimos 6 meses",
    "9m": "últimos 9 meses",
    "12m": "últimos 12 meses",
}


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
    # "Unidade" e não "Regional": este degrau é o nome da unidade do organograma
    # (`lotacao.unidade.nome`), que é o que a permissão usa. Chamá-lo de
    # "regional" fazia parecer recorte comercial — e é por aí que alguém tenta
    # trocá-lo pela área e quebra o acesso do gerente.
    ("regional", "Unidade", "regional"),
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
        # `mes` e não `competencia`: a URL que a tela GERA usa o nome novo. O
        # antigo continua sendo lido (ver `_mes_pedido`), mas não é mais
        # produzido — senão a compatibilidade nunca envelhece e nunca sai.
        "mes": filtros.competencia.strftime("%Y-%m"),
        "regional": filtros.regional,
        "cc": filtros.centro_custo,
        "contrato": filtros.contrato,
        # Tuplas. `urlencode(..., doseq=True)` as expande em `area=a&area=b`,
        # que é a forma que `getlist` lê de volta — o par tem de casar, senão o
        # link que a pessoa manda por e-mail abre com um filtro só.
        "area": filtros.area,
        "servico": filtros.servico,
        "layer": filtros.layer,
        "periodo": filtros.periodo or PERIODO_PADRAO,
        "comparar": filtros.comparar,
        "expandir": ",".join(filtros.expandidos),
        "dim": filtros.dimensao,
    }
    if filtros.deficitario:
        atual["deficitario"] = "1"
    atual.update(mudancas)
    return f"{base}?{urlencode({k: v for k, v in atual.items() if v}, doseq=True)}"


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


# ── Filtro visível — Onda 11, mecanismos 2 e 3 ──────────────────────


@dataclass(frozen=True)
class FiltroAtivo:
    """Um filtro em vigor, com o caminho para removê-lo.

    ## Por que as tarjas existem

    > *"Filtro invisível é a principal fonte de 'esse número está errado' que não
    > está."*

    E no modo apresentação o problema era literal: `{% if not apresentacao %}`
    escondia a barra inteira, então `?apresentacao=1&layer=1` mostrava números
    recortados **sem nada na tela dizendo que eram**. Numa reunião, projetado.

    As tarjas aparecem SEMPRE — inclusive em apresentação, onde os controles
    somem e elas ficam.
    """

    chave: str
    rotulo: str
    valor: str
    url_remover: str


#: Os filtros que ganham tarja, na ordem em que a tela os oferece.
#: `(parâmetro, rótulo)`.
COM_TARJA: tuple[tuple[str, str], ...] = (
    ("regional", "Unidade"),
    ("cc", "Centro de custo"),
    ("contrato", "Contrato"),
    ("area", "Área"),
    ("servico", "Serviço"),
    ("layer", "Layer"),
    ("deficitario", "Só deficitários"),
)

#: Os filtros que aceitam mais de um valor. Cada valor ganha a PRÓPRIA tarja,
#: com o próprio X — remover "Área 03" não pode levar "Área 01" junto, que é o
#: que uma tarja só para os dois faria.
MULTIVALOR: frozenset[str] = frozenset({"area", "servico"})

#: Quantos filtros CRUZADOS cabem ao mesmo tempo. O quarto substitui o mais
#: antigo e avisa — quatro recortes simultâneos produzem um número que ninguém
#: consegue explicar de cabeça, e é aí que a tela deixa de ser usada.
#:
#: Não conta os da hierarquia (regional, cc, contrato): aqueles são o NÍVEL, e a
#: trilha já os mostra.
MAXIMO_DE_CRUZADOS = 3

CRUZAVEIS: tuple[str, ...] = ("area", "servico", "layer", "deficitario")


def filtros_ativos(filtros: Filtros, base: str) -> list[FiltroAtivo]:
    """As tarjas. Vazia quando nada está filtrado."""
    valores = {
        "regional": filtros.regional,
        "cc": filtros.centro_custo,
        "contrato": filtros.contrato,
        "area": filtros.area,
        "servico": filtros.servico,
        "layer": filtros.layer,
        "deficitario": "sim" if filtros.deficitario else "",
    }
    ativos = []
    for parametro, rotulo in COM_TARJA:
        if not valores[parametro]:
            continue

        if parametro in MULTIVALOR:
            ativos.extend(
                _tarjas_multi(filtros, base, parametro, rotulo, valores[parametro])
            )
            continue

        # Remover um degrau da hierarquia limpa os de baixo, pela mesma razão da
        # trilha: a unidade recortada por um CC que a tela diz não estar ativo
        # é um número que não bate com nada.
        limpeza = {parametro: ""}
        if parametro == "regional":
            limpeza.update({"cc": "", "contrato": ""})
        elif parametro == "cc":
            limpeza["contrato"] = ""
        ativos.append(
            FiltroAtivo(
                chave=parametro,
                rotulo=rotulo,
                valor=valores[parametro],
                url_remover=_url_com(base, filtros, **limpeza),
            )
        )
    return ativos


def _tarjas_multi(
    filtros: Filtros, base: str, parametro: str, rotulo: str, escolhidos: tuple
) -> list[FiltroAtivo]:
    """Uma tarja por valor, e o X de cada uma remove só o seu.

    A alternativa — uma tarja "Área: 01, 03" com um X só — obriga a pessoa a
    limpar tudo e remarcar para tirar uma das duas. Ela faz isso uma vez e passa
    a não usar mais de um valor.
    """
    return [
        FiltroAtivo(
            chave=f"{parametro}:{valor}",
            rotulo=rotulo,
            valor=valor,
            url_remover=_url_com(
                base, filtros,
                **{parametro: tuple(v for v in escolhidos if v != valor)},
            ),
        )
        for valor in escolhidos
    ]


def recorte_em_texto(filtros: Filtros, areas: list[dict]) -> str:
    """O recorte ativo em frase — A6.

        "Área 01 e Área 03 · monitoramento · últimos 6 meses até AGO/2026"

    ## Frase E tarjas, e não uma das duas

    As tarjas dizem *o que remover*, uma por uma, com o X. A frase diz *o que
    estou vendo*, de uma vez. Quem chega à tela lê a frase; quem quer mudar
    clica na tarja. Uma tarja de cada vez não forma a leitura completa, e a
    frase sozinha não deixa desfazer nada.

    Sai da MESMA função de filtros que as tarjas, e não de um segundo cálculo:
    duas verdades sobre o mesmo recorte, na mesma barra, é como alguém descobre
    que a tela mente.

    ## Se a frase não couber, o recorte já é complexo demais

    Não há truncamento aqui de propósito. A frase crescer é o sinal — e o sinal
    é para a pessoa, não para o CSS.
    """
    nomes = {a["codigo"]: a["nome"] for a in areas}
    partes: list[str] = []

    if filtros.area:
        partes.append(_e_comercial([nomes.get(c, c) for c in filtros.area]))
    if filtros.centro_custo:
        partes.append(f"CC {filtros.centro_custo}")
    if filtros.contrato:
        partes.append(filtros.contrato)
    if filtros.servico:
        partes.append(_e_comercial(list(filtros.servico)))
    if filtros.layer:
        partes.append(f"layer {filtros.layer}")
    if filtros.deficitario:
        partes.append("só deficitários")

    periodo = filtros.rotulo_do_periodo
    mes = f"{filtros.competencia:%m/%Y}"
    partes.append(f"{periodo} até {mes}" if periodo else mes)
    return " · ".join(partes)


def _e_comercial(valores: list[str]) -> str:
    """`["a", "b", "c"]` → `"a, b e c"`. Português, não vírgula até o fim."""
    if len(valores) <= 1:
        return valores[0] if valores else ""
    return f"{', '.join(valores[:-1])} e {valores[-1]}"


def url_limpa(filtros: Filtros, base: str) -> str:
    """"Limpar tudo" — preserva a competência e a janela, e só elas.

    Competência não é filtro: é o assunto da tela. E limpar a janela devolveria
    treze meses a quem escolheu seis, o que é uma surpresa e não uma limpeza.
    """
    return _url_com(
        base, filtros,
        regional="", cc="", contrato="", area=(), servico=(),
        layer="", deficitario="",
    )


def url_de_apresentacao(filtros: Filtros, base: str) -> str:
    """O modo apresentação PRESERVANDO os filtros.

    Antes ele levava só a competência: clicar em "Apresentar" com um recorte
    ativo trocava os números em silêncio, no caminho entre a tela e o projetor.
    """
    return _url_com(base, filtros, apresentacao="1")


def cruzar(filtros: Filtros, base: str, parametro: str, valor: str) -> tuple[str, bool]:
    """A URL que ACRESCENTA um filtro cruzado. Devolve `(url, substituiu)`.

    O limite de três não é estético: quatro recortes simultâneos produzem um
    número que ninguém explica de cabeça, e é aí que a tela deixa de ser usada.

    Quando o limite estoura, o mais ANTIGO sai — e a tela avisa. Recusar o
    quarto clique seria pior: a pessoa clicaria de novo achando que não pegou.
    """
    if parametro not in CRUZAVEIS:
        return _url_com(base, filtros, **{parametro: valor}), False

    ordem = [p for p in CRUZAVEIS if _valor_do_filtro(filtros, p)]
    substituiu = False
    # Num filtro multivalor, clicar ACRESCENTA. Substituir faria o segundo
    # clique desfazer o primeiro, e comparar duas áreas — que é a razão de o
    # filtro aceitar mais de uma — ficaria impossível pelo gráfico.
    if parametro in MULTIVALOR:
        ja = _valor_do_filtro(filtros, parametro) or ()
        mudancas = {parametro: ja if valor in ja else (*ja, valor)}
    else:
        mudancas = {parametro: valor}
    if parametro not in ordem and len(ordem) >= MAXIMO_DE_CRUZADOS:
        mudancas[ordem[0]] = ""
        substituiu = True
    return _url_com(base, filtros, **mudancas), substituiu


def _valor_do_filtro(filtros: Filtros, parametro: str):
    return {
        "regional": filtros.regional,
        "cc": filtros.centro_custo,
        "contrato": filtros.contrato,
        "area": filtros.area,
        "servico": filtros.servico,
        "layer": filtros.layer,
        "deficitario": "1" if filtros.deficitario else "",
    }.get(parametro, "")


# ── Pivotar — Onda 11, mecanismo 3 ──────────────────────────────────

#: As dimensões pelas quais o bloco de perfuração pode agrupar.
#: `(parâmetro, rótulo, atributo do contrato, cruzável)`.
#:
#: Regional, centro de custo e contrato são a HIERARQUIA — escolhê-las troca o
#: nível. Serviço e layer são atributos: escolhê-los reagrupa sem descer, e o
#: clique vira filtro cruzado.
DIMENSOES: tuple[tuple[str, str, str, bool], ...] = (
    ("regional", "Unidade", "regional", False),
    ("cc", "Centro de custo", "centro_custo", False),
    ("contrato", "Contrato", "codigo", False),
    # ÁREA é atributo e não nível, e a diferença não é arbitrária: um centro de
    # custo atende contratos de áreas diferentes, então nenhuma das duas CONTÉM
    # a outra. Como nível, descer para uma área depois de escolher um CC faria a
    # lista crescer — o defeito que a Onda 11 corrigiu na hierarquia.
    ("area", "Área", "area", True),
    ("servico", "Serviço", "servico", True),
    ("layer", "Layer", "layer", True),
)


def dimensao_de(filtros: Filtros) -> tuple[str, str, str, bool]:
    """A dimensão do bloco de perfuração: a escolhida, ou a do nível seguinte.

    O padrão é a hierarquia — quem não escolheu nada quer descer. Escolher é o
    mecanismo 3: o mesmo número por outra dimensão.
    """
    if filtros.dimensao:
        for entrada in DIMENSOES:
            if entrada[0] == filtros.dimensao:
                return entrada
    profundidade = nivel_de(filtros)
    if profundidade >= len(HIERARQUIA):
        return ("", "", "", False)
    parametro, rotulo, atributo = HIERARQUIA[profundidade]
    return (parametro, rotulo, atributo, False)


def _bloco_perfuracao(escopo, filtros: Filtros, base: str):
    """A barra do nível seguinte — cada barra desce um degrau.

    Sai da CARTEIRA e não de uma consulta própria: ela já respeita o escopo da
    pessoa, e uma segunda consulta poderia oferecer uma regional que ela não
    alcança — o que revelaria a existência dela.
    """
    from workspace.graficos import series

    parametro, rotulo, atributo, cruzavel = dimensao_de(filtros)
    if not parametro:
        return series.barras_por_categoria(
            [], chave="perfuracao", titulo="Detalhe", fronteira=FRONTEIRA
        )

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

    pontos = []
    substituiria = False
    for nome, valor in sorted(por_categoria.items(), key=lambda p: -p[1]):
        if nome == "—":
            # Categoria em branco não vira filtro: `?servico=` é a ausência de
            # filtro, e clicar nela pareceria não fazer nada.
            pontos.append(series.Ponto(rotulo=nome, valor=valor))
            continue
        # Dimensão da HIERARQUIA desce um nível; atributo vira filtro CRUZADO —
        # o mesmo nível, recortado. É a diferença entre os mecanismos 1 e 2.
        url, substitui = cruzar(filtros, base, parametro, nome)
        substituiria = substituiria or substitui
        pontos.append(series.Ponto(rotulo=nome, valor=valor, url=url))

    bloco = series.barras_por_categoria(
        pontos,
        chave="perfuracao",
        titulo=f"Receita mensal por {rotulo.lower()}",
        rotulo_serie="Valor mensal",
    )
    bloco.cruzado = cruzavel
    bloco.aviso_de_substituicao = (
        f"Já há {MAXIMO_DE_CRUZADOS} recortes ativos. Clicar aqui troca o mais "
        "antigo — quatro ao mesmo tempo produzem um número que ninguém explica."
        if substituiria
        else ""
    )
    return bloco


def _estreitar_por_atributo(recorte: contrato.Escopo, filtros: Filtros):
    """Traduz `layer` em uma LISTA DE CONTRATOS, e estreita o escopo.

    Sem isto, o layer filtrava só a faixa da carteira: a pessoa escolhia
    "layer = 1", a lista de contratos encolhia, e o gráfico do dinheiro
    continuava mostrando a empresa inteira. Duas faixas discordando sobre o
    mesmo filtro, na mesma tela, é o defeito que faz alguém deixar de confiar no
    número — e ele não dá erro nem aparece em log.

    ## Serviço saiu daqui, e área nunca entrou

    Os dois são CAMPO do contrato, e agora viajam no próprio `Escopo`
    (`servicos`, `areas`), filtrados em SQL pelo `_recortar` do espelho. Traduzir
    para lista de códigos custaria uma volta ao provedor para chegar ao mesmo
    lugar, e uma tupla de dezoito códigos onde cabia um `IN` de um valor.

    **Layer não é campo.** Ele é calculado a partir da receita dos últimos meses
    — não existe coluna para o banco filtrar —, e por isso continua precisando
    da tradução. É a diferença que decide quem fica aqui.
    """
    if not filtros.layer:
        return recorte

    provedor = contrato.obter(contrato.ProvedorCarteira)
    if provedor is None:
        # Sem carteira não há como traduzir. Devolver o recorte largo mostraria
        # mais do que o filtro pediu; devolver vazio esconderia tudo. O largo é
        # o menos errado: a faixa da carteira já diz que a fonte não respondeu.
        return recorte

    # `provedor.contratos(recorte)` JÁ aplicou área e serviço — a tradução do
    # layer acontece dentro do que os outros filtros deixaram passar.
    codigos = tuple(
        sorted(c.codigo for c in provedor.contratos(recorte) if c.layer == filtros.layer)
    )
    if not codigos:
        # Nenhum contrato casa. `("",)` é um código que não existe — e é o que
        # faz as faixas dizerem "sem dado" em vez de mostrarem tudo, que é o que
        # uma tupla vazia significaria em `Escopo`.
        codigos = ("",)

    # Área e serviço seguem junto. Sem isto, o recorte por atributo APAGARIA o
    # filtro de área — e a tela mostraria, para quem filtrou a Área 03, os
    # contratos de layer 1 da empresa inteira.
    return contrato.Escopo(
        regionais=recorte.regionais,
        centros_custo=recorte.centros_custo,
        contratos=codigos,
        areas=recorte.areas,
        servicos=recorte.servicos,
    )


def _opcoes_de_atributo(escopo: contrato.Escopo) -> dict:
    """As áreas e os serviços que a pessoa ALCANÇA — não os que ela já filtrou.

    ## Por que do escopo, e não das faixas já montadas

    A versão anterior tirava os serviços da carteira montada, que já passou
    pelos filtros. Isso tem uma consequência que só aparece com multi-seleção:
    escolher "monitoramento" deixava a caixa com **uma opção só**, e não havia
    como acrescentar "manutenção" sem editar a URL à mão. Com um valor por vez o
    defeito era invisível; comparar dois serviços é exatamente a razão de o
    filtro aceitar mais de um. É o mesmo cuidado que o filtro de editais do
    radar já tomava.

    ## E por que continua respeitando a permissão

    O escopo aqui é o da PESSOA — apenas sem os filtros de área e serviço, que
    não vêm da permissão. Não é o espelho inteiro: uma opção fora do alcance
    dela não aparece, e a caixa não revela a existência de contrato que ela não
    pode ver.
    """
    provedor = contrato.obter(contrato.ProvedorCarteira)
    if provedor is None:
        return {"servicos": [], "areas": []}

    # A HIERARQUIA fica; os dois atributos saem. É o que a permissão permite,
    # antes de os filtros de leitura recortarem.
    alcance = contrato.Escopo(
        regionais=escopo.regionais,
        centros_custo=escopo.centros_custo,
        contratos=escopo.contratos,
    )
    carteira = provedor.contratos(alcance)

    areas: dict[str, str] = {}
    tem_sem_area = False
    for c in carteira:
        if c.area:
            areas[c.area] = c.area_nome or c.area
        else:
            tem_sem_area = True

    ordenadas = [
        {"codigo": codigo, "nome": nome}
        for codigo, nome in sorted(areas.items(), key=lambda par: par[1])
    ]
    if tem_sem_area:
        # NO FIM, e sempre presente quando existe: "Sem área" é uma escolha, e
        # não uma ausência. Escondê-la faria o contrato não agrupado sumir da
        # soma no instante em que alguém marcasse qualquer área.
        ordenadas.append({"codigo": "sem-area", "nome": "Sem área"})

    return {
        "servicos": sorted({c.servico for c in carteira if c.servico}),
        "areas": ordenadas,
    }


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

    AS SEIS, e não as quatro da tela 10. A pergunta desta tela é "de onde vem
    cada número do produto", e ela não muda porque duas faixas passaram a morar
    em telas próprias — quem abre a 99 está atrás da fonte, não da tela.
    """
    return [
        {"chave": chave, "faixa": DEFINICOES[chave][0], "fonte": DEFINICOES[chave][1]}
        for chave, _ in MONTADORES + MONTADORES_PESSOAS + MONTADORES_SATISFACAO
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


# ── Detalhar — Onda 11, mecanismo 4 ─────────────────────────────────

#: Quantas linhas por página no detalhamento. Cinquenta é o que cabe numa tela
#: sem rolar até perder a referência do cabeçalho.
POR_PAGINA_DETALHE = 50


def detalhe(pessoa, parametros, cache: dict | None = None) -> dict:
    """As LINHAS por trás do agregado — o botão "Detalhamento" do benchmark.

    ## A regra que sustenta a confiança na tela inteira

    O detalhe **herda todos os filtros ativos** e **mostra quais são no topo**.
    Detalhe que não bate com o agregado destrói a confiança na tela inteira: a
    pessoa some com o número, não com a tela.

    Por isso ele reusa `escopo_de`, `ler_filtros` e `_estreitar_por_atributo` —
    as MESMAS funções da tela. Uma segunda leitura de filtro aqui divergiria da
    primeira, e o sintoma seria exatamente esse.

    ## E ele soma o que mostra

    `total_das_linhas` sai da mesma lista que a tabela pagina. Um total calculado
    à parte poderia discordar da soma visível — e o teste que amarra os dois é o
    que prova que o detalhe bate com o agregado.
    """
    from django.urls import reverse

    escopo = escopo_de(pessoa, cache=cache)
    filtros = ler_filtros(parametros)
    base_url = reverse("workspace:resultados")
    recorte = _estreitar_por_atributo(filtros.aplicar(escopo), filtros)

    provedor = contrato.obter(contrato.ProvedorResultadoFinanceiro)
    linhas = []
    if provedor is not None:
        for linha in provedor.serie_competencia(recorte, filtros.de, filtros.ate):
            if not _no_mes(linha, filtros.competencia):
                continue
            linhas.append(
                {
                    "contrato": linha.contrato or linha.centro_custo,
                    "centro_custo": linha.centro_custo,
                    "competencia": f"{linha.mes:02d}/{linha.ano}",
                    "receita_bruta": linha.receita_bruta,
                    "custo_direto": linha.custo_direto,
                    "margem_contribuicao": linha.margem_contribuicao,
                    "ebitda": linha.ebitda,
                    "procedencia": str(linha.procedencia),
                }
            )
    linhas.sort(key=lambda l: -(l["receita_bruta"] or Decimal("0")))

    pagina = max(1, _inteiro(parametros.get("p"), 1))
    inicio = (pagina - 1) * POR_PAGINA_DETALHE
    visiveis = linhas[inicio: inicio + POR_PAGINA_DETALHE]

    return {
        "filtros": filtros,
        # As tarjas AQUI TAMBÉM, e é a metade que o mecanismo 4 exige: o detalhe
        # mostra quais filtros herdou.
        "filtros_ativos": filtros_ativos(filtros, base_url),
        "url_voltar": _url_com(base_url, filtros),
        "linhas": visiveis,
        "pagina": pagina,
        "paginas": max(1, -(-len(linhas) // POR_PAGINA_DETALHE)),
        "total_de_linhas": len(linhas),
        # A soma da lista INTEIRA, e não da página: o agregado da tela é do
        # recorte todo, e comparar com a soma de uma página seria comparar coisas
        # diferentes.
        "total_das_linhas": sum(
            (l["receita_bruta"] or Decimal("0") for l in linhas), Decimal("0")
        ),
        "url_pagina": lambda n: _url_com(
            reverse("workspace:resultados_detalhe"), filtros, p=str(n)
        ),
    }


def dados(pessoa, parametros, cache: dict | None = None) -> dict:
    """O agregado em JSON — o contrato de dados do mecanismo 2.

    **Mesma verificação de escopo da tela.** É o erro clássico que o prompt
    nomeia: a tela filtra por regional e a API devolve tudo. Aqui não há como
    divergir, porque as duas chamam `escopo_de` e `ler_filtros` — as mesmas
    funções, no mesmo módulo.

    Ele existe para o detalhamento carregado sob demanda e para quem quiser
    conferir um número sem raspar HTML. O volume é pequeno: treze meses e poucas
    dimensões.
    """
    escopo = escopo_de(pessoa, cache=cache)
    filtros = ler_filtros(parametros)
    recorte = _estreitar_por_atributo(filtros.aplicar(escopo), filtros)

    provedor = contrato.obter(contrato.ProvedorResultadoFinanceiro)
    serie = provedor.serie_competencia(recorte, filtros.de, filtros.ate) if provedor else []

    ordem, receita = _por_mes(serie, "receita_bruta")
    _, orcado = _por_mes(serie, "receita_orcada")
    _, ebitda = _por_mes(serie, "ebitda")

    return {
        "competencia": filtros.competencia.strftime("%Y-%m"),
        "janela": filtros.meses,
        "escopo": {
            "regionais": list(recorte.regionais),
            "centros_custo": list(recorte.centros_custo),
            "contratos": list(recorte.contratos),
        },
        "meses": [
            {
                "mes": rotulo,
                "receita_bruta": receita[rotulo],
                "receita_orcada": orcado.get(rotulo),
                "ebitda": ebitda.get(rotulo),
            }
            for rotulo in ordem
        ],
    }


# ── Os gráficos das faixas 3 a 7 — passo 6 ──────────────────────────
#
# Um tipo por faixa, e cada escolha responde a uma pergunta diferente. Repetir
# barra em todas seria mais fácil de escrever e diria menos: o tipo do gráfico é
# parte do que ele afirma.


def _grafico_da_carteira(conteudo: dict):
    """Dispersão: receita × margem, tamanho pelo valor mensal.

    É a adição nossa ao catálogo, e é aqui que ela ganha sentido: o quadrante
    direito-inferior — **grande e pouco rentável** — é o que nenhuma tabela
    ordenada mostra, porque ordenar por um esconde o outro.

    A linha do limiar de 10% é a fronteira do quadrante. Sem ela, ele existe e
    ninguém vê onde começa.
    """
    from workspace.graficos import series

    pontos = [
        (
            c.codigo,
            c.valor_mensal or Decimal("0"),
            c.margem_contribuicao_pct,
            c.valor_mensal or Decimal("0"),
        )
        for c in conteudo.get("carteira", [])
        # Sem amostra fica FORA do gráfico: um contrato que faturou uma vez
        # apareceria no quadrante errado por falta de histórico, e não por
        # desempenho. O rodapé diz quantos ficaram de fora.
        if c.margem_contribuicao_pct is not None and c.layer != SEM_AMOSTRA
    ]
    return series.dispersao(
        pontos,
        chave="carteira",
        titulo="Receita mensal × margem, por contrato",
        rotulo_x="Receita mensal",
        # SEM o "%" aqui: quem acrescenta a unidade ao nome do eixo é
        # `series.dispersao`, e escrevê-la nos dois lugares produzia
        # "Margem % (%)" na tela.
        rotulo_y="Margem",
        limiar_y=MARGEM_MINIMA,
    )


def _grafico_do_mix(conteudo: dict):
    """Rosca do mix por serviço, com o total no centro."""
    from workspace.graficos import series

    return series.rosca(
        [(item["servico"], item["valor"]) for item in conteudo.get("mix", [])],
        chave="mix",
        titulo="Mix da carteira, por serviço",
        centro_rotulo="carteira mensal",
    )


def _grafico_dos_vencimentos(conteudo: dict):
    """Barras por faixa de vencimento — 30, 60, 90, 180 dias.

    Barra e não rosca: as faixas são **cumulativas no tempo** e têm ordem. Uma
    rosca ordena por tamanho e perde a única coisa que importa aqui, que é qual
    vence antes.
    """
    from workspace.graficos import series

    return series.barras_por_categoria(
        [
            series.Ponto(
                rotulo=f"até {bloco['dias']} dias",
                valor=sum(
                    (c.valor_mensal or Decimal("0") for c in bloco["contratos"]),
                    Decimal("0"),
                ),
            )
            for bloco in conteudo.get("blocos", [])
        ],
        chave="vencimentos",
        titulo="Valor mensal a vencer, por faixa",
        rotulo_serie="Valor mensal",
    )


def _grafico_dos_projetos(conteudo: dict):
    """Rosca por situação, e o bullet dos marcos em risco.

    Devolve os DOIS: a rosca responde "como está a carteira de projetos" e o
    bullet responde "o que vence antes do quê". São perguntas diferentes, e
    espremê-las num gráfico só produziria um que não responde nenhuma.
    """
    from workspace.graficos import series

    rosca = series.rosca(
        [
            (item["situacao"], Decimal(item["quantidade"]))
            for item in conteudo.get("por_situacao", [])
        ],
        chave="projetos-situacao",
        titulo="Projetos por situação",
        centro_rotulo="projetos",
        centro_valor=str(
            sum(i["quantidade"] for i in conteudo.get("por_situacao", []))
        ),
        formatar_tabela=lambda v: fmt.numero(v),
    )

    hoje = timezone.localdate()
    marcos = [
        (
            f"{m.projeto} · {m.titulo}"[:40],
            Decimal((m.prazo - hoje).days) if m.prazo else None,
            Decimal("0"),
        )
        for m in conteudo.get("marcos_em_risco", [])
    ]
    bullet = series.bullet(
        marcos,
        chave="projetos-marcos",
        titulo="Marcos em risco — dias até o prazo",
        rotulo_valor="Dias restantes",
        rotulo_meta="Hoje",
        formatar=lambda v: fmt.numero(v) + " d" if v is not None else fmt.VAZIO,
        formatar_tabela=lambda v: fmt.numero(v) + " d" if v is not None else fmt.VAZIO,
    )
    return rosca, bullet


def _mapa_do_quadro(conteudo: dict):
    """Mapa de calor do turnover por centro de custo.

    Tabela e não `heatmap`: é a grade do Score PEC do benchmark, e o número
    precisa ser selecionável — alguém vai copiar uma linha dela para um e-mail.

    **Menor é melhor**, e por isso os limiares invertem: turnover de 8,4% é
    crítico, não excelente.
    """
    from workspace.graficos import series

    por_centro = conteudo.get("por_centro", [])
    return series.mapa_calor_tabela(
        ["Turnover", "Absenteísmo"],
        [
            (q.centro_custo or "—", [q.turnover_pct, q.absenteismo_pct])
            for q in por_centro
        ],
        chave="quadro",
        titulo="Turnover e absenteísmo por centro de custo",
        critico=Decimal("5"),
        atencao=Decimal("3"),
        maior_melhor=False,
    )


def _grafico_da_satisfacao(conteudo: dict):
    """Barra de composição: promotor, neutro, detrator.

    Composição e não rosca: são três categorias com **ordem** — de promotor a
    detrator —, e a rosca embaralha essa ordem ao ordenar por tamanho.

    O valor absoluto fica dentro de cada segmento: uma barra de 100% esconde se
    ela vale doze respostas ou mil, e doze é o número real desta massa.
    """
    from workspace.graficos import series

    contagem = conteudo.get("contagem", {})
    return series.barra_composicao(
        [
            (rotulo, Decimal(contagem.get(chave, 0)))
            for chave, rotulo in (
                ("promotor", "Promotores"),
                ("neutro", "Neutros"),
                ("detrator", "Detratores"),
            )
            if contagem.get(chave)
        ],
        chave="satisfacao",
        titulo="Distribuição das avaliações",
        formatar=lambda v: fmt.numero(v),
        formatar_tabela=lambda v: fmt.numero(v),
    )
