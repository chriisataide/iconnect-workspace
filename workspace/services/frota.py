"""FRT — a conta do consumo, e o aviso antes da apreensão. §18 e §19.

## O consumo é tanque-a-tanque, e a regra tem uma razão

`km/l` de um abastecimento é a distância percorrida DESDE O ANTERIOR dividida
pelos litros DESTE. Parece invertido e não é: o tanque foi enchido lá atrás,
gastou-se aquilo tudo no caminho, e o que se põe agora é exatamente o que foi
consumido no trecho.

Só entram enchimentos **completos**. Entre dois tanques parciais a conta divide
a distância por um volume que não corresponde a ela, e o resultado é um número
plausível — 18 km/l num utilitário — que ninguém questiona porque não parece
absurdo. Número errado com cara de certo é pior que número faltando.

## O odômetro nunca anda para trás

Km menor que o último registrado é erro de digitação em 100% dos casos reais, e
aceitá-lo produz consumo negativo em uma linha e absurdo na seguinte. O
lançamento é recusado com a mensagem que diz o número esperado — recusar sem
dizer qual é o último km faz a pessoa tentar de novo no escuro.

## Por que o aviso de vencimento é um comando, e não um sinal

Documento não vence porque alguém salvou um formulário: vence porque o dia
passou. Não há evento no sistema no instante certo, então quem dispara é o
relógio — `manage.py avisar_frota`, no mesmo desenho de `avisar_habilitacoes`.
"""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.urls import reverse
from django.utils import timezone

from identidade.services.autorizacao import pode
from workspace.models.frota import (
    DespesaVeiculo,
    SituacaoVeiculo,
    TipoDespesaVeiculo,
    Veiculo,
)
from workspace.models.notificacao import TipoNotificacao

PERMISSAO_LER = "log.frota.ler"
PERMISSAO_OPERAR = "log.frota.operar"

#: Com quantos dias de antecedência o documento vira aviso. Trinta é o prazo em
#: que ainda dá para agendar vistoria e pagar sem multa; abaixo disso o aviso
#: informa sem ajudar.
DIAS_DE_ALERTA = 30


class FrotaError(Exception):
    """O lançamento não pode acontecer. A mensagem é para quem digitou."""


def pode_ler(pessoa, cache: dict | None = None) -> bool:
    """Ver a frota. Quem OPERA também lê, pelo mesmo motivo do estoque."""
    return pode(pessoa, PERMISSAO_LER, cache=cache) or pode(
        pessoa, PERMISSAO_OPERAR, cache=cache
    )


def pode_operar(pessoa, cache: dict | None = None) -> bool:
    return pode(pessoa, PERMISSAO_OPERAR, cache=cache)


# ── Consulta ────────────────────────────────────────────────────────


def frota(unidade=None, incluir_baixados: bool = False):
    """Os veículos, com o recurso reservável já carregado."""
    consulta = Veiculo.objects.select_related("unidade", "recurso").da_unidade(unidade)
    if not incluir_baixados:
        consulta = consulta.exclude(situacao=SituacaoVeiculo.BAIXADO)
    return consulta


def com_prazo_estourando(unidade=None, dias: int = DIAS_DE_ALERTA) -> list[dict]:
    """`[{"veiculo": v, "prazo": {...}}]` — vencido primeiro, depois o mais perto.

    Uma linha por DOCUMENTO e não por veículo: o carro com licenciamento vencido
    e seguro vencendo tem dois problemas com donos e prazos diferentes, e uma
    linha só faria o segundo desaparecer quando o primeiro fosse resolvido.

    Em Python e não em SQL: são quatro colunas de data comparadas com hoje, e a
    consulta equivalente seria um `Q()` de quatro ramos que precisa ser mudado
    junto com `DOCUMENTOS_COM_PRAZO` — duas listas do mesmo fato divergem.
    """
    achados = []
    for veiculo in frota(unidade):
        for prazo in veiculo.prazos():
            if prazo["dias"] <= dias:
                achados.append({"veiculo": veiculo, "prazo": prazo})
    return sorted(achados, key=lambda a: a["prazo"]["dias"])


def despesas_de(veiculo: Veiculo, tipo: str | None = None, limite: int | None = None):
    consulta = DespesaVeiculo.objects.filter(veiculo=veiculo).select_related("quem")
    if tipo:
        consulta = consulta.filter(tipo=tipo)
    return consulta[:limite] if limite else consulta


# ── O consumo ───────────────────────────────────────────────────────


def consumo_de(veiculo: Veiculo) -> list[dict]:
    """Um item por abastecimento que rende conta, do mais recente ao mais antigo.

    O PRIMEIRO enchimento de todos nunca tem consumo: não há tanque anterior
    para saber quanto se rodou. A linha aparece assim mesmo, com `km_l` nulo —
    escondê-la faria o histórico de combustível ter um buraco no começo que
    ninguém consegue explicar.
    """
    cheios = list(
        DespesaVeiculo.objects.filter(
            veiculo=veiculo,
            tipo=TipoDespesaVeiculo.COMBUSTIVEL,
            tanque_cheio=True,
            km__isnull=False,
            litros__isnull=False,
        ).order_by("km", "data")
    )

    saida = []
    anterior = None
    for atual in cheios:
        km_l = None
        rodados = None
        if anterior is not None and atual.litros:
            rodados = atual.km - anterior.km
            if rodados > 0:
                km_l = (Decimal(rodados) / atual.litros).quantize(Decimal("0.01"))
        saida.append(
            {
                "despesa": atual,
                "rodados": rodados,
                "km_l": km_l,
                "preco_por_litro": atual.preco_por_litro,
            }
        )
        anterior = atual
    return list(reversed(saida))


def resumo_de(veiculo: Veiculo) -> dict:
    """Quanto custou, quanto rodou e quanto faz por litro.

    O consumo médio é a distância TOTAL sobre os litros TOTAIS — e não a média
    das médias. As duas dão números diferentes, e a média das médias dá peso
    igual a um tanque de 8 litros e a um de 60, o que faz um abastecimento de
    emergência mover o indicador do ano.
    """
    linhas = consumo_de(veiculo)
    com_conta = [l for l in linhas if l["km_l"] is not None]

    rodados = sum(l["rodados"] for l in com_conta) if com_conta else 0
    litros = sum(l["despesa"].litros for l in com_conta) if com_conta else Decimal("0")
    media = (
        (Decimal(rodados) / litros).quantize(Decimal("0.01")) if litros else None
    )

    total = DespesaVeiculo.objects.filter(veiculo=veiculo).aggregate(
        t=Sum("valor")
    )["t"] or Decimal("0")

    por_tipo = {
        linha["tipo"]: linha["total"]
        for linha in DespesaVeiculo.objects.filter(veiculo=veiculo)
        .values("tipo")
        .annotate(total=Sum("valor"))
    }

    # §19 — custo por MOTORISTA, e não por quem lançou. Quem digita a nota do
    # posto é o administrativo; quem dirigia é o técnico, e é o custo dele que a
    # pergunta quer. Sem a separação, o indicador mediria o administrativo.
    por_motorista = [
        {
            "motorista": linha["motorista__nome"] or "não informado",
            "total": linha["total"],
        }
        for linha in DespesaVeiculo.objects.filter(veiculo=veiculo)
        .values("motorista__nome")
        .annotate(total=Sum("valor"))
        .order_by("-total")
    ]

    return {
        "total": total,
        "por_motorista": por_motorista,
        "por_tipo": [
            {"tipo": valor, "rotulo": rotulo, "total": por_tipo.get(valor, Decimal("0"))}
            for valor, rotulo in TipoDespesaVeiculo.choices
        ],
        "rodados": rodados,
        "litros": litros,
        "media_km_l": media,
        # Custo por km sobre a distância MEDIDA entre abastecimentos, e não
        # sobre o odômetro do veículo: o odômetro inclui a vida do carro antes
        # de o controle existir, e dividir o gasto deste ano por ela daria um
        # centavo por quilômetro.
        "custo_por_km": (
            (total / Decimal(rodados)).quantize(Decimal("0.01")) if rodados else None
        ),
    }


# ── Lançar ──────────────────────────────────────────────────────────


@transaction.atomic
def lancar_despesa(
    veiculo: Veiculo,
    tipo: str,
    valor,
    quem=None,
    data=None,
    km: int | None = None,
    litros=None,
    tanque_cheio: bool = True,
    fornecedor: str = "",
    observacao: str = "",
    motorista=None,
    destino: str = "",
    finalidade: str = "",
    cache: dict | None = None,
) -> DespesaVeiculo:
    """Grava o gasto e adianta o odômetro do veículo, quando houver km."""
    if not pode_operar(quem, cache=cache):
        raise FrotaError("Você não pode lançar despesas da frota.")
    if tipo not in TipoDespesaVeiculo.values:
        raise FrotaError("Tipo de despesa inválido.")

    valor = Decimal(str(valor))
    if valor <= 0:
        raise FrotaError("O valor tem de ser maior que zero.")

    if tipo == TipoDespesaVeiculo.COMBUSTIVEL and not litros:
        # Sem litro o abastecimento vira só um valor, e o §19 inteiro — quanto
        # este carro faz por litro — deixa de ter resposta.
        raise FrotaError("Abastecimento exige os litros.")

    if km is not None and km < veiculo.km_atual:
        raise FrotaError(
            f"O odômetro não anda para trás: o último km registrado é "
            f"{veiculo.km_atual}."
        )

    despesa = DespesaVeiculo.objects.create(
        veiculo=veiculo,
        tipo=tipo,
        valor=valor,
        data=data or timezone.localdate(),
        km=km,
        litros=Decimal(str(litros)) if litros else None,
        tanque_cheio=bool(tanque_cheio),
        fornecedor=fornecedor.strip()[:120],
        motorista=motorista,
        destino=destino.strip()[:160],
        finalidade=finalidade.strip()[:200],
        quem=quem,
        observacao=observacao.strip()[:300],
    )

    if km is not None and km > veiculo.km_atual:
        veiculo.km_atual = km
        veiculo.save(update_fields=["km_atual"])

    return despesa


# ── O aviso ─────────────────────────────────────────────────────────


def avisar_vencimentos(dias: int = DIAS_DE_ALERTA, cache: dict | None = None) -> int:
    """Avisa quem opera a frota sobre documento vencido ou vencendo.

    Vai para quem tem `log.frota.operar` e não para o último motorista: quem
    paga o IPVA é Suprimentos, e avisar quem dirigiu ontem transfere para a
    pessoa errada uma responsabilidade que ela não pode cumprir.

    O dedupe do `criar()` usa `origem_id`, e aqui ele inclui o CAMPO do prazo —
    sem isso, o aviso do licenciamento silenciaria o do seguro do mesmo carro.
    """
    from workspace.services import notificacoes as nt

    destinatarios = _quem_opera(cache=cache)
    if not destinatarios:
        return 0

    enviados = 0
    for achado in com_prazo_estourando(dias=dias):
        veiculo, prazo = achado["veiculo"], achado["prazo"]
        titulo = (
            f"{prazo['rotulo']} de {veiculo.placa} venceu"
            if prazo["vencido"]
            else f"{prazo['rotulo']} de {veiculo.placa} vence em {prazo['dias']} dias"
        )
        corpo = (
            f"{veiculo.modelo} · vencimento em "
            f"{prazo['data'].strftime('%d/%m/%Y')}."
        )
        for pessoa in destinatarios:
            if nt.criar(
                pessoa,
                TipoNotificacao.DOCUMENTO_DE_VEICULO,
                titulo,
                corpo,
                url=reverse("workspace:frota"),
                dominio="log.frota",
                origem_id=f"{veiculo.pk}:{prazo['campo']}",
            ):
                enviados += 1
    return enviados


def _quem_opera(cache: dict | None = None) -> list:
    """Quem tem `log.frota.operar` hoje.

    Busca inversa como `atendimento.quem_atende`, e com a mesma economia: os
    candidatos são quem tem alguma atribuição VIGENTE, e não a tabela inteira de
    gente. Perguntar `pode()` para cada colaborador da empresa custaria uma
    consulta por pessoa para descobrir que a resposta é não para quase todas.

    Sem superusuário — conta técnica não é dona de processo, e enchê-la de aviso
    operacional é o jeito mais rápido de o sino dela virar ruído.
    """
    from django.contrib.auth import get_user_model

    from identidade.models import AtribuicaoPapel

    com_papel = AtribuicaoPapel.objects.vigentes().values_list("user_id", flat=True)
    candidatos = (
        get_user_model()
        .objects.filter(pk__in=com_papel, is_active=True, is_superuser=False)
        .distinct()
    )
    return [p for p in candidatos if pode(p, PERMISSAO_OPERAR, cache=cache)]
