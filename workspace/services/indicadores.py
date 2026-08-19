"""IND — os números que respondem se o portal está funcionando.

## Por que este módulo existe

O índice `wks_evento_quem_idx` foi criado com um comentário dizendo para que
servia — *"quantos o Fulano concluiu em julho"* — e **nada consultava**. O
produto media tudo e não mostrava nada: cada pedido tinha data de criação, de
aprovação, de conclusão e de reabertura, e a única forma de somar isso era
abrir o `/admin/`.

Quem assinou o projeto pergunta quatro coisas, e o produto não respondia
nenhuma:

1. quanto pedido entra, por área;
2. quanto tempo leva até resolver — e quanto disso é espera por aprovação;
3. onde trava;
4. o que volta sem resolver.

## As decisões que valem estar escritas

**Mediana, não média.** Um pedido esquecido oitenta dias numa fila puxa a média
de uma área inteira e faz parecer que o setor é lento. A mediana diz o que
acontece com o pedido do meio, que é a experiência real de quem pede. A média
mede o pior caso disfarçado de caso típico.

**Tempo até APROVAR e tempo até ATENDER, separados.** Somados, eles viram um
número que ninguém sabe consertar: se um pedido leva doze dias, o setor não
sabe se contrata gente ou se cobra o gestor que não decide. Separados, a
resposta é uma só.

**Janela móvel.** O painel olha um período, não a história inteira. Indicador
acumulado desde a fundação nunca melhora, por melhor que a equipe fique — e um
indicador que não reage a nada é um indicador que ninguém consulta duas vezes.

**Área sem movimento não vira linha.** Zero em todas as colunas não é
informação; é ruído que empurra para baixo as áreas que têm o que mostrar.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from statistics import median

from django.db.models import Count, Q
from django.utils import timezone

from identidade.services.autorizacao import pode
from workspace.models.catalogo import (
    SITUACOES_FORA_DA_ESTEIRA,
    SITUACOES_NAO_ENVIADAS,
    SituacaoServico,
    SolicitacaoServico,
)
from workspace.models.evento import AcaoSolicitacao, EventoSolicitacao
from workspace.services import atendimento as atd

#: A permissão de ver o painel INTEIRO — Diretoria, Sócios e R.H.
VER_TUDO = "ind.ler"

#: Períodos que a tela oferece. Trinta dias é o mês corrente; noventa é o
#: trimestre, que é como a diretoria pensa; um ano serve para comparar.
PERIODOS = ((30, "30 dias"), (90, "90 dias"), (365, "1 ano"))
PERIODO_PADRAO = 90


class SemPainel(Exception):
    """Esta pessoa não tem área nenhuma para ver."""


def dominios_visiveis(pessoa, cache: dict | None = None) -> list[str] | None:
    """As raízes de domínio que esta pessoa pode ver. `None` = todas.

    Duas portas, e não uma:

    - quem tem `ind.ler` vê a empresa inteira. É para eles que o painel existe;
    - quem ATENDE uma fila vê a própria área. O gerente de Compras tem direito
      aos números de Compras sem precisar dos números do R.H., e negar isso
      obrigaria a pedir relatório para a diretoria toda semana.

    Quem não é nem um nem outro não tem painel — e recebe 403 em vez de uma
    tela zerada, pela mesma razão da fila de atendimento: tela vazia para quem
    nunca vai ter dado é mentira.
    """
    if pode(pessoa, VER_TUDO, cache=cache):
        return None

    raizes = [p.rstrip(".") for p in atd.prefixos_que_atende(pessoa, cache=cache)]
    if not raizes:
        raise SemPainel("Você não tem indicadores para ver.")
    return raizes


def tem_painel(pessoa, cache: dict | None = None) -> bool:
    """Se o trilho mostra o item de Indicadores.

    Existe para a casca não precisar capturar `SemPainel` só para decidir se
    desenha um link — exceção é para o caminho errado, não para um `if`.
    """
    try:
        dominios_visiveis(pessoa, cache=cache)
    except SemPainel:
        return False
    return True


def _raiz(dominio: str) -> str:
    return dominio.split(".", 1)[0]


def _dias(inicio, fim) -> int | None:
    if inicio is None or fim is None:
        return None
    return (fim - inicio).days


def panorama(pessoa, dias: int = PERIODO_PADRAO, cache: dict | None = None) -> dict:
    """Tudo que a tela mostra, em quatro consultas.

    Quatro e não uma por área: o painel é a tela que mais tenta virar N+1,
    porque a cabeça pensa "para cada área, calcule...". A consulta é sempre
    sobre o conjunto, e o agrupamento acontece em Python.
    """
    raizes = dominios_visiveis(pessoa, cache=cache)
    corte = timezone.now() - timedelta(days=dias)

    # RASCUNHO fora da base inteira — §43. Um formulário que ninguém enviou não
    # é trabalho da área: sem esta exclusão, o rascunho que alguém deixou pela
    # metade apareceria como pedido aberto e, passado o prazo prometido do item,
    # como pedido ATRASADO — no painel de uma área que nunca soube dele.
    base = SolicitacaoServico.objects.filter(criado_em__gte=corte).exclude(
        situacao__in=SITUACOES_NAO_ENVIADAS
    )
    if raizes is not None:
        consulta = Q()
        for raiz in raizes:
            consulta |= Q(item__dominio__startswith=f"{raiz}.")
        base = base.filter(consulta)

    linhas = list(
        base.select_related("item", "aprovacao").values_list(
            "item__dominio",
            "item__prazo_prometido_dias",
            "situacao",
            "criado_em",
            "concluido_em",
            "reaberturas",
            "aprovacao__criado_em",
            "aprovacao__decidido_em",
        )
    )

    por_area: dict[str, dict] = defaultdict(
        lambda: {
            "abertos": 0,
            "concluidos": 0,
            # Quantos JÁ FORAM entregues alguma vez — inclui o que voltou e
            # ainda está aberto. É o denominador honesto da taxa de reabertura:
            # usando só os concluídos AGORA, o pedido que voltou some de baixo
            # e continua em cima, e a taxa passa de 100%. Foi o que aconteceu
            # na primeira medição do painel: 200%.
            "entregues": 0,
            "devolvidos": 0,
            "reabertos": 0,
            "atrasados": 0,
            "ate_aprovar": [],
            "ate_concluir": [],
        }
    )
    agora = timezone.now()

    for (
        dominio,
        prazo,
        situacao,
        criado_em,
        concluido_em,
        reaberturas,
        aprovacao_criada,
        aprovacao_decidida,
    ) in linhas:
        area = por_area[_raiz(dominio or "?")]

        if situacao == SituacaoServico.CONCLUIDA:
            area["concluidos"] += 1
            area["entregues"] += 1
            levou = _dias(criado_em, concluido_em)
            if levou is not None:
                area["ate_concluir"].append(levou)
        elif situacao == SituacaoServico.DEVOLVIDA:
            area["devolvidos"] += 1
        elif situacao not in SITUACOES_FORA_DA_ESTEIRA:
            # A condição era `!= CANCELADA`, escrita à mão, e por isso um pedido
            # REPROVADO contava como aberto para sempre — e como ATRASADO
            # assim que passasse o prazo prometido do item. O gestor tinha dito
            # não meses antes; o painel da área continuava cobrando.
            area["abertos"] += 1
            # Atraso só faz sentido no que AINDA está aberto: o que já foi
            # entregue tem o tempo real medido na coluna do lado, e contar as
            # duas coisas juntas somaria o mesmo pedido duas vezes.
            if (agora - criado_em).days > (prazo or 0):
                area["atrasados"] += 1

        if reaberturas:
            area["reabertos"] += 1
            if situacao != SituacaoServico.CONCLUIDA:
                # Voltou e ainda não fechou de novo: foi entregue uma vez, e
                # essa entrega conta.
                area["entregues"] += 1

        espera = _dias(aprovacao_criada, aprovacao_decidida)
        if espera is not None:
            area["ate_aprovar"].append(espera)

    areas = []
    for raiz, dados in sorted(por_area.items()):
        total = dados["abertos"] + dados["concluidos"] + dados["devolvidos"]
        if not total and not dados["reabertos"]:
            continue  # área sem movimento não vira linha
        areas.append(
            {
                "dominio": raiz,
                "nome": _NOME_DA_AREA.get(raiz, raiz.upper()),
                "total": total,
                "abertos": dados["abertos"],
                "concluidos": dados["concluidos"],
                "devolvidos": dados["devolvidos"],
                "atrasados": dados["atrasados"],
                "reabertos": dados["reabertos"],
                "ate_aprovar": _mediana(dados["ate_aprovar"]),
                "ate_concluir": _mediana(dados["ate_concluir"]),
                # A taxa que diz se "concluído" significa alguma coisa. Sobre os
                # CONCLUÍDOS, e não sobre o total: o que ainda está aberto não
                # teve chance de voltar.
                "entregues": dados["entregues"],
                "taxa_reabertura": _percentual(
                    dados["reabertos"], dados["entregues"]
                ),
            }
        )

    return {
        "dias": dias,
        "periodos": PERIODOS,
        "areas": areas,
        "total": sum(a["total"] for a in areas),
        "abertos": sum(a["abertos"] for a in areas),
        "concluidos": sum(a["concluidos"] for a in areas),
        "atrasados": sum(a["atrasados"] for a in areas),
        "reabertos": sum(a["reabertos"] for a in areas),
        "taxa_reabertura": _percentual(
            sum(a["reabertos"] for a in areas),
            sum(a["entregues"] for a in areas),
        ),
        "mais_pedidos": _mais_pedidos(base),
        "quem_entregou": _quem_entregou(corte, raizes),
        "tudo": raizes is None,
    }


def _mediana(valores) -> int | None:
    """`None` e não zero quando não há amostra: zero diria "resolve no mesmo
    dia", que é o oposto de "ainda não sei"."""
    return int(median(valores)) if valores else None


def _percentual(parte: int, total: int) -> int | None:
    return round(100 * parte / total) if total else None


def _mais_pedidos(base, limite: int = 5) -> list[dict]:
    """Os serviços mais pedidos do período.

    É o que diz onde investir: o item que aparece toda semana merece formulário
    mais curto, prazo revisto e, às vezes, deixar de exigir aprovação.
    """
    return [
        {"nome": linha["item__nome"], "total": linha["quantos"]}
        for linha in base.values("item__nome")
        .annotate(quantos=Count("pk"))
        .order_by("-quantos", "item__nome")[:limite]
    ]


def _quem_entregou(corte, raizes, limite: int = 8) -> list[dict]:
    """Quem concluiu quanto, no período — a pergunta que o índice esperava.

    `wks_evento_quem_idx` é `(quem, acao, quando)`, e existe desde o histórico
    justamente para esta consulta. Ela é sobre ENTREGA, não sobre pessoas:
    serve para ver se uma fila inteira está nas costas de uma pessoa só, que é
    o gargalo mais comum e o mais fácil de não enxergar.
    """
    consulta = EventoSolicitacao.objects.filter(
        acao=AcaoSolicitacao.CONCLUIDA,
        quando__gte=corte,
        quem__isnull=False,
    )
    if raizes is not None:
        alcance = Q()
        for raiz in raizes:
            alcance |= Q(solicitacao__item__dominio__startswith=f"{raiz}.")
        consulta = consulta.filter(alcance)

    return [
        {"quem": linha["quem__nome"] or linha["quem__email"], "total": linha["quantos"]}
        for linha in consulta.values("quem__nome", "quem__email")
        .annotate(quantos=Count("pk"))
        .order_by("-quantos")[:limite]
    ]


_NOME_DA_AREA = {
    "com": "Compras",
    "fin": "Financeiro",
    "hab": "SESMT",
    "jur": "Jurídico",
    "log": "Suprimentos",
    "mkt": "Marketing",
    "ops": "Operação",
    "rh": "R.H.",
    "ti": "TI",
    "ven": "Vendas",
}
