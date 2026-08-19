"""MKT — o radar de oportunidades, e o aviso antes do prazo. §23.

## O que este módulo NÃO faz

**Não aprova nada.** Decidir ir a uma feira é gastar dinheiro da empresa, e esse
caminho já existe: o item `evento` do catálogo, que passa pelo gestor e pela
diretoria conforme a faixa e confere o orçamento do centro de custo. Aprovar
aqui seria um segundo fluxo para a mesma decisão — a duplicação que a frota já
mostrou de perto.

**Não coleta nada de fora.** O cadastro é manual, por decisão explícita. Varrer
sites de feira para preencher esta tabela seria coleta automatizada de
terceiros, e não é o que este produto faz.

## Por que o aviso é sobre o PRAZO DE DECISÃO, e não sobre a data do evento

Porque é o prazo que se perde. A feira de outubro tem inscrição antecipada até
junho; avisar em setembro é avisar depois que o stand acabou.
"""

from __future__ import annotations

from django.db import transaction
from django.urls import reverse

from identidade.services.autorizacao import pode
from workspace.models.marketing import (
    Oportunidade,
    SituacaoOportunidade,
    TipoOportunidade,
)
from workspace.models.notificacao import TipoNotificacao

PERMISSAO_LER = "mkt.ler"
PERMISSAO_OPERAR = "mkt.atender"

#: Com quantos dias de antecedência o prazo vira aviso. Quinze é o mínimo para
#: reunir quem decide, decidir e ainda conseguir se inscrever.
DIAS_DE_ALERTA = 15


class MarketingError(Exception):
    """O cadastro ou a decisão não pode acontecer."""


def pode_ler(pessoa, cache: dict | None = None) -> bool:
    """Quem OPERA também lê — sem a soma, o papel precisaria das duas."""
    return pode(pessoa, PERMISSAO_LER, cache=cache) or pode(
        pessoa, PERMISSAO_OPERAR, cache=cache
    )


def pode_operar(pessoa, cache: dict | None = None) -> bool:
    return pode(pessoa, PERMISSAO_OPERAR, cache=cache)


# ── Consulta ────────────────────────────────────────────────────────


def radar(situacao: str = ""):
    """As oportunidades, prazo mais próximo primeiro.

    Sem `situacao`, só as ABERTAS: o radar responde "o que precisa de decisão",
    e uma lista que abre com as feiras de 2024 já realizadas obriga a filtrar
    antes de poder usar.
    """
    consulta = Oportunidade.objects.select_related("responsavel", "solicitacao__item")
    if situacao:
        return consulta.filter(situacao=situacao)
    return consulta.abertas()


def com_prazo_estourando(dias: int = DIAS_DE_ALERTA) -> list[Oportunidade]:
    """Abertas cujo prazo de decisão já passou ou está perto. Perdido primeiro.

    Em Python e não em SQL: é uma comparação de data com hoje sobre uma tabela
    de dezenas de linhas, e a versão em `Q()` teria de ser mantida junto com
    `prazo_perdido` — duas definições de "está na hora" divergem.
    """
    achados = [
        o
        for o in Oportunidade.objects.com_prazo().select_related("responsavel")
        if o.dias_para_decidir is not None and o.dias_para_decidir <= dias
    ]
    return sorted(achados, key=lambda o: o.dias_para_decidir)


def resumo() -> dict:
    """Os números do topo da tela: quantas abertas, quantas com prazo apertado."""
    abertas = Oportunidade.objects.abertas().count()
    apertadas = com_prazo_estourando()
    return {
        "abertas": abertas,
        "no_prazo_curto": len(apertadas),
        "perdidas": len([o for o in apertadas if o.prazo_perdido]),
    }


# ── Cadastrar e decidir ─────────────────────────────────────────────


@transaction.atomic
def registrar(
    pessoa,
    titulo: str,
    tipo: str,
    oportunidade: Oportunidade | None = None,
    organizador: str = "",
    cidade: str = "",
    site: str = "",
    data_inicio=None,
    data_fim=None,
    prazo_decisao=None,
    custo_estimado=None,
    publico_estimado=None,
    retorno_esperado: str = "",
    origem: str = "",
    responsavel=None,
    cache: dict | None = None,
) -> Oportunidade:
    """Cria ou atualiza. Uma função para os dois, como na redação de comunicados."""
    if not pode_operar(pessoa, cache=cache):
        raise MarketingError("Você não pode cadastrar oportunidades.")
    if not titulo.strip():
        raise MarketingError("A oportunidade precisa de um nome.")
    if tipo not in TipoOportunidade.values:
        raise MarketingError("Tipo de oportunidade inválido.")
    if data_fim and data_inicio and data_fim < data_inicio:
        raise MarketingError("O evento termina antes de começar.")

    alvo = oportunidade or Oportunidade(criado_por=pessoa)
    alvo.titulo = titulo.strip()[:200]
    alvo.tipo = tipo
    alvo.organizador = organizador.strip()[:160]
    alvo.cidade = cidade.strip()[:120]
    alvo.site = site.strip()[:300]
    alvo.data_inicio = data_inicio
    alvo.data_fim = data_fim
    alvo.prazo_decisao = prazo_decisao
    alvo.custo_estimado = custo_estimado
    alvo.publico_estimado = publico_estimado
    alvo.retorno_esperado = retorno_esperado
    alvo.origem = origem.strip()[:200]
    alvo.responsavel = responsavel
    alvo.save()
    return alvo


@transaction.atomic
def decidir(
    oportunidade: Oportunidade,
    pessoa,
    situacao: str,
    motivo: str = "",
    solicitacao=None,
    cache: dict | None = None,
) -> Oportunidade:
    """Move a oportunidade de fase. Descartar EXIGE motivo.

    Exige porque é o campo mais útil da tabela: sem ele, a mesma feira volta
    todo ano e a discussão recomeça do zero. Com ele, a resposta de doze meses
    atrás está do lado do convite.
    """
    if not pode_operar(pessoa, cache=cache):
        raise MarketingError("Você não pode decidir sobre oportunidades.")
    if situacao not in SituacaoOportunidade.values:
        raise MarketingError("Situação inválida.")
    if situacao == SituacaoOportunidade.DESCARTADA and not motivo.strip():
        raise MarketingError(
            "Diga por que foi descartada — é o que evita a mesma discussão no ano que vem."
        )

    oportunidade.situacao = situacao
    if motivo.strip():
        oportunidade.motivo = motivo.strip()[:300]
    if solicitacao is not None:
        oportunidade.solicitacao = solicitacao
    oportunidade.save(update_fields=["situacao", "motivo", "solicitacao"])
    return oportunidade


# ── O aviso ─────────────────────────────────────────────────────────


def avisar_prazos(dias: int = DIAS_DE_ALERTA, cache: dict | None = None) -> int:
    """Avisa quem opera marketing sobre prazo de decisão perto ou vencido.

    Vai para quem tem `mkt.atender` e não para o responsável da linha: o
    responsável pode estar de férias, e a oportunidade tem prazo de qualquer
    jeito. Quando há responsável, ele recebe também.
    """
    from workspace.services import notificacoes as nt

    destinatarios = _quem_opera(cache=cache)
    enviados = 0
    for oportunidade in com_prazo_estourando(dias=dias):
        dias_restantes = oportunidade.dias_para_decidir
        titulo = (
            f"Prazo de {oportunidade.titulo} venceu"
            if oportunidade.prazo_perdido
            else f"{oportunidade.titulo} — decidir em {dias_restantes} dias"
        )
        corpo = (
            f"{oportunidade.get_tipo_display()} · prazo de decisão em "
            f"{oportunidade.prazo_decisao.strftime('%d/%m/%Y')}."
        )
        alvo = set(destinatarios)
        if oportunidade.responsavel is not None:
            alvo.add(oportunidade.responsavel)
        for quem in alvo:
            if nt.criar(
                quem,
                TipoNotificacao.PRAZO_DE_OPORTUNIDADE,
                titulo,
                corpo,
                url=reverse("workspace:marketing"),
                dominio="mkt.oportunidade",
                origem_id=f"{oportunidade.pk}:{oportunidade.prazo_decisao.isoformat()}",
            ):
                enviados += 1
    return enviados


def _quem_opera(cache: dict | None = None) -> list:
    """Quem tem `mkt.atender` hoje — busca inversa, como `atendimento.quem_atende`."""
    from django.contrib.auth import get_user_model

    from identidade.models import AtribuicaoPapel

    com_papel = AtribuicaoPapel.objects.vigentes().values_list("user_id", flat=True)
    candidatos = (
        get_user_model()
        .objects.filter(pk__in=com_papel, is_active=True, is_superuser=False)
        .distinct()
    )
    return [p for p in candidatos if pode(p, PERMISSAO_OPERAR, cache=cache)]
