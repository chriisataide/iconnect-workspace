"""Motor de aprovação — criar cadeia, decidir, listar bandeja.

Toda regra vive aqui, não na view. Isso é o que permite decidir por HTTP, por
push, por WhatsApp e por comando de gestão sem triplicar a regra.

## Regras inegociáveis

1. **Ninguém aprova o próprio pedido.** Nem com permissão global. A etapa cujo
   aprovador resolvido é o solicitante é **pulada com motivo registrado**, não
   silenciosamente concedida.
2. **Decisão é idempotente.** Decidir duas vezes a mesma etapa não avança duas
   vezes a cadeia — é o que acontece com duplo-clique e com retry de push.
3. **Delegação não é caso especial.** Quem decide passa por `pode()`, que já
   resolve delegação. Aqui só se registra que `decidido_por` ≠ `aprovador`.
4. **Devolver encerra a solicitação.** Não "volta uma etapa": o solicitante
   corrige e reenvia. Cadeia que anda para trás produz estado que ninguém
   consegue explicar.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import F, OuterRef, Q, Subquery
from django.dispatch import Signal
from django.utils import timezone

from identidade.models import AtribuicaoPapel, Lotacao
from identidade.services.autorizacao import pode
from workspace.models.aprovacao import (
    EtapaAprovacao,
    RegraAprovacao,
    SituacaoEtapa,
    SituacaoSolicitacao,
    SolicitacaoAprovacao,
    TipoAprovador,
)

# O domínio ouve isto para aplicar o efeito (pagar o reembolso, gerar o pedido,
# lançar a ausência). APR não conhece o efeito — só anuncia a decisão.
#
#     aprovacao_decidida.connect(handler, sender=None)
#     handler(sender, solicitacao, decisao, quem, **kwargs)
aprovacao_decidida = Signal()

# Emitido quando uma etapa PASSA A SER a da vez — na criação da cadeia e depois
# de cada aprovação que não encerra o pedido.
#
#     vez_de.connect(handler, sender=None)
#     handler(sender, solicitacao, etapa, **kwargs)
#
# Sinal e não chamada direta: sem ele, `criar()` e `decidir()` precisariam
# conhecer o serviço de notificação, e o motor de aprovação passaria a ter opinião
# sobre como avisar as pessoas — que é assunto da superfície, não dele.
vez_de = Signal()

# Emitido quando um degrau é aprovado E A CADEIA CONTINUA — o pedido ainda não
# se resolveu.
#
#     etapa_aprovada.connect(handler, sender=None)
#     handler(sender, solicitacao, etapa, quem, **kwargs)
#
# Existe porque `aprovacao_decidida` só fala quando o pedido INTEIRO se resolve,
# e isso deixava a linha do tempo mentindo por omissão: numa cadeia de três
# degraus ela mostrava só o último aprovador, como se o gestor e a área nunca
# tivessem assinado. A informação estava em `EtapaAprovacao` e não chegava a
# quem lê.
#
# Separado de `aprovacao_decidida`, e não uma versão dele com mais argumentos:
# quem quer saber do DESFECHO (orçamento, notificação de aprovado) não quer ser
# acordado a cada degrau, e juntar os dois faria cada ouvinte reimplementar o
# filtro — que é o tipo de coisa que um deles esquece.
etapa_aprovada = Signal()

PERMISSAO_APROVAR = "apr.aprovar"


def _anunciar_vez(solicitacao) -> None:
    """Avisa quem tem a etapa da vez, se houver."""
    etapa = solicitacao.etapa_atual
    if etapa is not None:
        vez_de.send(sender=None, solicitacao=solicitacao, etapa=etapa)


class AprovacaoError(Exception):
    """Erro de fluxo — decisão inválida, sem permissão, já decidida."""


@dataclass(frozen=True)
class Decisao:
    APROVAR = "aprovar"
    DEVOLVER = "devolver"
    CANCELAR = "cancelar"


# ── Construção da cadeia ────────────────────────────────────────────


def _alcance(regra_dominio: str, dominio: str) -> int:
    """Quão específica esta regra é para este domínio. `-1` = não alcança.

    Três níveis, e o do meio é o que faltava: `*` alcança tudo (0), o PREFIXO
    alcança a área inteira (`rh.` pega `rh.ferias`, `rh.ausencia`, `rh.vaga`), e
    o domínio exato alcança um serviço só.

    O prefixo entrou quando a aprovação passou a ter etapa por ÁREA. Sem ele,
    "o R.H. revisa o que é de R.H." exigiria uma regra por item de catálogo — e
    a regra do item novo seria esquecida no dia em que ele nascesse, sem que
    nada avisasse. O resto do código já casava domínio por prefixo
    (`services/catalogo.q_dominios`); esta função alinha a aprovação com ele.
    """
    if regra_dominio == "*":
        return 0
    if regra_dominio == dominio:
        return len(regra_dominio) + 1
    if regra_dominio.endswith(".") and dominio.startswith(regra_dominio):
        return len(regra_dominio)
    return -1


def _regras_aplicaveis(dominio: str, valor: Decimal | None) -> list[RegraAprovacao]:
    """Regras do domínio que a solicitação alcança.

    Regra mais específica **substitui** a mais genérica na mesma ordem — senão
    uma empresa que configura "reembolso é diferente" acabaria com as duas
    cadeias somadas.
    """
    consulta = RegraAprovacao.objects.filter(ativa=True)
    if valor is not None:
        consulta = consulta.filter(valor_minimo__lte=valor)
    else:
        # Sem valor (férias, acesso), só regras de faixa zero fazem sentido.
        consulta = consulta.filter(valor_minimo=Decimal("0"))

    # Filtro por prefixo em Python e não no banco: a consulta seria
    # "coluna é prefixo do parâmetro", que nenhum índice serve — e a tabela de
    # regras tem dezenas de linhas, não milhões.
    escolhidas: dict[int, tuple[int, RegraAprovacao]] = {}
    for regra in consulta.select_related("papel", "aprovador").order_by("ordem", "valor_minimo"):
        alcance = _alcance(regra.dominio, dominio)
        if alcance < 0:
            continue
        anterior = escolhidas.get(regra.ordem)
        # Mais específica vence; empatando, a de maior `valor_minimo`, que é a
        # mais específica para aquele valor.
        if (
            anterior is None
            or alcance > anterior[0]
            or (alcance == anterior[0] and regra.valor_minimo >= anterior[1].valor_minimo)
        ):
            escolhidas[regra.ordem] = (alcance, regra)

    return [escolhidas[ordem][1] for ordem in sorted(escolhidas)]


def _resolver_aprovador(regra: RegraAprovacao, solicitante) -> tuple[object | None, object | None]:
    """`(aprovador_nominal, papel)` para esta regra. Um dos dois, nunca ambos."""
    if regra.tipo == TipoAprovador.NOMINAL:
        return regra.aprovador, None
    if regra.tipo == TipoAprovador.PAPEL:
        return None, regra.papel
    # GESTOR_DIRETO
    lotacao = Lotacao.objects.filter(user=solicitante).select_related("gestor").first()
    return (lotacao.gestor if lotacao else None), None


@transaction.atomic
def criar(
    *,
    dominio: str,
    titulo: str,
    solicitante,
    origem_id: str = "",
    resumo: str = "",
    valor: Decimal | None = None,
    centro_custo_codigo: str = "",
    dados: dict | None = None,
) -> SolicitacaoAprovacao:
    """Cria a solicitação e monta a cadeia.

    Sem nenhuma etapa resolvível (organograma vazio, nenhuma regra configurada),
    a solicitação **não** é aprovada automaticamente: fica aguardando e sem
    etapa. Auto-aprovar por ausência de configuração é como um pedido de
    R$ 50.000 passa sem ninguém ver.
    """
    solicitacao = SolicitacaoAprovacao.objects.create(
        dominio=dominio,
        origem_id=origem_id,
        titulo=titulo,
        resumo=resumo,
        solicitante=solicitante,
        valor=valor,
        centro_custo_codigo=centro_custo_codigo,
        dados=dados or {},
    )

    ordem = 0
    for regra in _regras_aplicaveis(dominio, valor):
        aprovador, papel = _resolver_aprovador(regra, solicitante)

        if aprovador is None and papel is None:
            # Gestor não cadastrado. Registrar a etapa pulada é melhor que
            # omiti-la: o dossiê mostra que faltou organograma.
            ordem += 1
            EtapaAprovacao.objects.create(
                solicitacao=solicitacao,
                ordem=ordem,
                papel=None,
                aprovador=None,
                situacao=SituacaoEtapa.PULADA,
                motivo_pulo="Aprovador não resolvido (organograma incompleto).",
            )
            continue

        ordem += 1
        pula_por_ser_o_solicitante = aprovador is not None and aprovador.pk == solicitante.pk
        EtapaAprovacao.objects.create(
            solicitacao=solicitacao,
            ordem=ordem,
            aprovador=aprovador,
            papel=papel,
            situacao=(
                SituacaoEtapa.PULADA if pula_por_ser_o_solicitante else SituacaoEtapa.PENDENTE
            ),
            motivo_pulo=(
                "Aprovador é o próprio solicitante." if pula_por_ser_o_solicitante else ""
            ),
        )

    _concluir_se_nao_ha_pendencia(solicitacao, quem=None)
    solicitacao.refresh_from_db()
    if solicitacao.situacao == SituacaoSolicitacao.AGUARDANDO:
        _anunciar_vez(solicitacao)
    return solicitacao


# ── Decisão ─────────────────────────────────────────────────────────


def _pode_decidir(quem, etapa: EtapaAprovacao, cache: dict | None = None) -> bool:
    """Quem pode decidir esta etapa.

    Etapa nominal: o titular, ou quem recebeu delegação dele — e `pode()` já
    resolve delegação, então basta a permissão.
    Etapa por papel: quem tem o papel vigente.
    """
    if quem is None or getattr(quem, "is_authenticated", False) is False:
        return False

    if etapa.aprovador_id and etapa.aprovador_id == quem.pk:
        return True

    # Delegação de etapa NOMINAL, verificada direto.
    #
    # Não dá para resolver isso por `pode()`: o titular decide a etapa dele por
    # ser o titular, não por ter `apr.aprovar` — um gestor direto normalmente não
    # tem papel nenhum. Sem esta checagem, delegar as férias de um gestor sem
    # papel não transferiria nada, que é justamente o caso mais comum.
    if etapa.aprovador_id:
        from identidade.models import Delegacao

        delegado = (
            Delegacao.objects.vigentes()
            .filter(de_user_id=etapa.aprovador_id, para_user=quem)
            .exists()
        )
        if delegado:
            return True

    if etapa.papel_id:
        tem_papel = (
            AtribuicaoPapel.objects.vigentes()
            .filter(user=quem, papel_id=etapa.papel_id, papel__ativo=True)
            .exists()
        )
        if tem_papel:
            return True

    # Etapa NOMINAL: quem tem `apr.aprovar` COM ESCOPO sobre o titular também
    # decide. É o caminho de destravamento quando o titular desaparece sem
    # delegação registrada — e fica auditado em `decidido_por`.
    if etapa.aprovador_id:
        return pode(quem, PERMISSAO_APROVAR, alvo=etapa.aprovador_id, cache=cache)

    # Etapa por PAPEL: só quem tem o papel. Sem fallback, de propósito.
    #
    # A tentação é cair em `pode(quem, "apr.aprovar")` aqui. Isso seria um furo:
    # sem `alvo`, `pode()` responde "posso em geral?", e QUALQUER escopo
    # satisfaz. Um gerente com `apr.aprovar.equipe` passaria a decidir etapa de
    # diretoria — anulando exatamente a cadeia por faixa de valor que a etapa
    # existe para impor.
    return False


def _concluir_se_nao_ha_pendencia(solicitacao: SolicitacaoAprovacao, quem) -> bool:
    """Fecha como aprovada se a cadeia terminou. Devolve se fechou."""
    if solicitacao.etapas.filter(situacao=SituacaoEtapa.PENDENTE).exists():
        return False
    if solicitacao.situacao != SituacaoSolicitacao.AGUARDANDO:
        return False

    # Cadeia inteira pulada = ninguém decidiu de fato. Não é aprovação.
    houve_decisao_humana = solicitacao.etapas.filter(
        situacao=SituacaoEtapa.APROVADA
    ).exists()
    if not houve_decisao_humana:
        return False

    solicitacao.situacao = SituacaoSolicitacao.APROVADA
    solicitacao.decidido_em = timezone.now()
    solicitacao.save(update_fields=["situacao", "decidido_em"])
    aprovacao_decidida.send(
        sender=None, solicitacao=solicitacao, decisao=Decisao.APROVAR, quem=quem
    )
    return True


@transaction.atomic
def decidir(
    solicitacao: SolicitacaoAprovacao,
    quem,
    decisao: str,
    justificativa: str = "",
    cache: dict | None = None,
) -> SolicitacaoAprovacao:
    """Registra a decisão de `quem` na etapa atual e avança a cadeia."""
    # `select_for_update` para que duplo-clique e retry de push não decidam duas
    # vezes. É o mesmo motivo pelo qual a etapa é relida aqui, não recebida.
    solicitacao = (
        SolicitacaoAprovacao.objects.select_for_update()
        .filter(pk=solicitacao.pk)
        .first()
    )
    if solicitacao is None:
        raise AprovacaoError("Solicitação não encontrada.")

    if solicitacao.situacao != SituacaoSolicitacao.AGUARDANDO:
        raise AprovacaoError(
            f"Solicitação já está {solicitacao.get_situacao_display().lower()}."
        )

    if decisao == Decisao.CANCELAR:
        return _cancelar(solicitacao, quem, justificativa)

    etapa = solicitacao.etapa_atual
    if etapa is None:
        raise AprovacaoError("Nenhuma etapa pendente para decidir.")

    if solicitacao.solicitante_id == getattr(quem, "pk", None):
        raise AprovacaoError("Ninguém aprova o próprio pedido.")

    if not _pode_decidir(quem, etapa, cache=cache):
        raise AprovacaoError("Sem permissão para decidir esta etapa.")

    if decisao == Decisao.APROVAR:
        etapa.situacao = SituacaoEtapa.APROVADA
    elif decisao == Decisao.DEVOLVER:
        if not justificativa.strip():
            # Devolver sem motivo obriga o solicitante a adivinhar, e adivinhar
            # gera um segundo envio igualmente errado.
            raise AprovacaoError("Devolver exige justificativa.")
        etapa.situacao = SituacaoEtapa.DEVOLVIDA
    else:
        raise AprovacaoError(f"Decisão desconhecida: {decisao!r}")

    etapa.decidido_por = quem
    etapa.decidido_em = timezone.now()
    etapa.justificativa = justificativa
    etapa.save(update_fields=["situacao", "decidido_por", "decidido_em", "justificativa"])

    if decisao == Decisao.DEVOLVER:
        solicitacao.situacao = SituacaoSolicitacao.DEVOLVIDA
        solicitacao.decidido_em = timezone.now()
        solicitacao.save(update_fields=["situacao", "decidido_em"])
        aprovacao_decidida.send(
            sender=None, solicitacao=solicitacao, decisao=Decisao.DEVOLVER, quem=quem
        )
    else:
        _concluir_se_nao_ha_pendencia(solicitacao, quem)

    solicitacao.refresh_from_db()
    if solicitacao.situacao == SituacaoSolicitacao.AGUARDANDO:
        if decisao == Decisao.APROVAR:
            # Degrau aprovado e a cadeia continua. Sem este anúncio, quem lê o
            # histórico veria só o último aprovador e concluiria que os
            # anteriores nunca assinaram.
            etapa_aprovada.send(
                sender=None, solicitacao=solicitacao, etapa=etapa, quem=quem
            )
        # A cadeia andou: o próximo degrau precisa saber que chegou a vez dele.
        # Sem isto, o aprovador descobre abrindo a tela — e é assim que um pedido
        # fica cinco dias parado sem ninguém ter culpa.
        _anunciar_vez(solicitacao)
    return solicitacao


def _cancelar(solicitacao, quem, justificativa: str):
    """Só o solicitante cancela — ou quem tem permissão global sobre ele."""
    e_o_solicitante = solicitacao.solicitante_id == getattr(quem, "pk", None)
    if not e_o_solicitante and not pode(quem, PERMISSAO_APROVAR, alvo=solicitacao.solicitante_id):
        raise AprovacaoError("Sem permissão para cancelar.")

    solicitacao.situacao = SituacaoSolicitacao.CANCELADA
    solicitacao.decidido_em = timezone.now()
    solicitacao.save(update_fields=["situacao", "decidido_em"])
    solicitacao.etapas.filter(situacao=SituacaoEtapa.PENDENTE).update(
        situacao=SituacaoEtapa.PULADA, motivo_pulo="Solicitação cancelada."
    )
    aprovacao_decidida.send(
        sender=None, solicitacao=solicitacao, decisao=Decisao.CANCELAR, quem=quem
    )
    return solicitacao


def decidir_em_lote(
    solicitacoes, quem, decisao: str, justificativa: str = "", cache: dict | None = None
) -> tuple[list[SolicitacaoAprovacao], list[tuple[int, str]]]:
    """Decide várias. Devolve `(decididas, falhas)`.

    **Não** aborta tudo quando uma falha: o gestor selecionou 6 e uma perdeu a
    corrida para outro aprovador. Cancelar as 5 boas por causa disso é o pior
    resultado possível — ele teria de refazer a seleção sem saber qual falhou.
    """
    decididas: list[SolicitacaoAprovacao] = []
    falhas: list[tuple[int, str]] = []
    for solicitacao in solicitacoes:
        try:
            decididas.append(
                decidir(solicitacao, quem, decisao, justificativa, cache=cache)
            )
        except AprovacaoError as erro:
            falhas.append((solicitacao.pk, str(erro)))
    return decididas, falhas


# ── Bandeja ─────────────────────────────────────────────────────────


def pendentes_para(quem, cache: dict | None = None):
    """As solicitações que esperam por esta pessoa.

    Uma query, sem `pode()` por linha — chamar autorização em laço sobre a
    bandeja é N+1 de autorização, que é o jeito mais fácil de tornar a tela mais
    importante do produto a mais lenta.
    """
    if quem is None or getattr(quem, "is_authenticated", False) is False:
        return SolicitacaoAprovacao.objects.none()

    papeis = list(
        AtribuicaoPapel.objects.vigentes()
        .filter(user=quem, papel__ativo=True)
        .values_list("papel_id", flat=True)
    )

    # Titulares que delegaram para esta pessoa: as etapas deles entram na
    # bandeja dela enquanto a delegação vigorar.
    from identidade.models import Delegacao

    delegantes = list(
        Delegacao.objects.vigentes().filter(para_user=quem).values_list("de_user_id", flat=True)
    )

    condicao = Q(aprovador=quem)
    if papeis:
        condicao |= Q(papel_id__in=papeis)
    if delegantes:
        condicao |= Q(aprovador_id__in=delegantes)

    # Só a etapa DA VEZ. Todas as etapas nascem `pendente` de uma vez, então
    # filtrar por "pendente e minha" traz também degraus futuros: com a cadeia
    # de três faixas, a diretoria via na bandeja um pedido cuja etapa 1 ainda
    # era do gerente — rotulado "Etapa 1 de 3 · você", e com o botão Aprovar
    # funcionando pela válvula de escopo global de `_pode_decidir`.
    #
    # A bandeja estava convidando ao atalho que a cadeia por faixa de valor
    # existe para impedir. Com um degrau só isso nunca apareceu.
    #
    # `Subquery` e não laço: o contrato desta função é uma query, sem N+1.
    ordem_da_vez = (
        EtapaAprovacao.objects.filter(
            solicitacao_id=OuterRef("solicitacao_id"),
            situacao=SituacaoEtapa.PENDENTE,
        )
        .order_by("ordem")
        .values("ordem")[:1]
    )
    ids = (
        EtapaAprovacao.objects.filter(condicao, situacao=SituacaoEtapa.PENDENTE)
        .annotate(ordem_da_vez=Subquery(ordem_da_vez))
        .filter(ordem=F("ordem_da_vez"))
        .values_list("solicitacao_id", flat=True)
    )
    return (
        SolicitacaoAprovacao.objects.aguardando()
        .filter(pk__in=ids)
        .exclude(solicitante=quem)  # nunca a própria
        # `servico` no select_related e `servico__anexos` no prefetch: o dossiê
        # mostra os anexos de cada pedido, e sem isto uma bandeja de 20 itens
        # faria 41 consultas a mais só para desenhar a lista de arquivos.
        .select_related("solicitante", "servico")
        .prefetch_related("servico__anexos")
        .order_by("criado_em")
    )


def resumo_da_bandeja(quem, cache: dict | None = None) -> dict:
    """Os KPIs do topo da bandeja, numa passada."""
    pendentes = list(pendentes_para(quem, cache=cache))
    total = sum((s.valor or Decimal("0")) for s in pendentes)
    mais_antiga = pendentes[0] if pendentes else None
    return {
        "quantidade": len(pendentes),
        "valor_represado": total,
        "dias_mais_antiga": mais_antiga.dias_esperando if mais_antiga else 0,
        "solicitacoes": pendentes,
    }


def historico(solicitacao: SolicitacaoAprovacao):
    """Etapas em ordem, para a timeline do dossiê."""
    return solicitacao.etapas.select_related("aprovador", "papel", "decidido_por").order_by(
        "ordem"
    )
