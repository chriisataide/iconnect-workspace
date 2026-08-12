"""Catálogo de serviços — pedir, validar e rotear.

Três coisas aqui não são óbvias e são as que decidem se o catálogo é usado:

1. **Prazo real medido, não prometido.** Depois de 5 conclusões, o card mostra o
   P50 do histórico. Prazo prometido que ninguém cumpre destrói a confiança mais
   rápido que prazo longo e honesto.
2. **Auto-aprovação dentro da política.** Se cabe no limite e no orçamento, não
   vai para fila humana. A maioria dos portais manda 100% dos pedidos para
   aprovação manual, e é por isso que parecem lentos.
3. **Validação antes do envio.** Bloquear com o motivo à vista, em vez de aceitar
   e recusar dois dias depois — que é o que treina o usuário a voltar para o
   e-mail.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import median

from django.db import models, transaction

from identidade.models import Lotacao
from identidade.services.autorizacao import pode
from workspace.models.catalogo import (
    ItemCatalogo,
    SituacaoServico,
    SolicitacaoServico,
)
from workspace.services import aprovacao as apr
from workspace.services import orcamento as orc

# Abaixo disto, a mediana de duração é ruído — 2 conclusões rápidas fariam a tela
# prometer 1 dia para sempre.
MINIMO_PARA_PRAZO_MEDIDO = 5


class SolicitacaoError(Exception):
    """Pedido inválido — campo faltando, sem permissão, item inativo."""


@dataclass(frozen=True)
class Impedimento:
    """Algo que bloqueia o envio, com o motivo em texto para a tela."""

    campo: str
    motivo: str


# ── Catálogo ────────────────────────────────────────────────────────


def catalogo_para(pessoa, cache: dict | None = None) -> list[ItemCatalogo]:
    """Itens que esta pessoa pode pedir, já filtrados por permissão.

    Filtrar aqui e não no template: item que aparece e recusa no envio é pior
    que item que não aparece.
    """
    itens = list(ItemCatalogo.objects.filter(ativo=True))
    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        # Catálogo é área pessoal: pedir exige saber quem pede.
        return []
    return [
        item
        for item in itens
        if not item.permissao or pode(pessoa, item.permissao, cache=cache)
    ]


def agrupado_para(pessoa, cache: dict | None = None) -> dict[str, list[ItemCatalogo]]:
    """Catálogo por grupo de intenção, na ordem de declaração de `GrupoCatalogo`.

    Ordem de declaração e NÃO alfabética: a alfabética põe "Desenvolvimento"
    primeiro e "Equipamento e acesso" em quarto, quando equipamento é o que a
    maioria vem pedir. A ordem do enum é a ordem de frequência de uso.
    """
    from workspace.models.catalogo import GrupoCatalogo

    por_grupo: dict[str, list[ItemCatalogo]] = {}
    for item in catalogo_para(pessoa, cache=cache):
        por_grupo.setdefault(item.grupo, []).append(item)

    agrupado: dict[str, list[ItemCatalogo]] = {}
    for grupo in GrupoCatalogo:
        itens = por_grupo.get(grupo.value)
        if itens:
            agrupado[grupo.label] = itens
    return agrupado


def q_dominios(prefixos, campo: str = "dominio") -> models.Q:
    """`Q` que casa qualquer um dos prefixos de domínio.

    Prefixo e não igualdade: o domínio é hierárquico (`rh.ferias`,
    `rh.ausencia`), e casar valor exato faria cada item novo nascer órfão do
    seu módulo.

    `campo` permite atravessar a FK (`item__dominio`) sem duplicar a função.
    """
    consulta = models.Q()
    for prefixo in prefixos:
        consulta |= models.Q(**{f"{campo}__startswith": prefixo})
    return consulta


def do_modulo(prefixos) -> list[ItemCatalogo]:
    """A vitrine de um módulo — os serviços que aquele departamento atende.

    SEM filtro de permissão, de propósito, e é a diferença para
    `catalogo_para()`: o Portal é aberto a quem está na rede da empresa, e
    listar o que um departamento atende é informação, não ação. Quem pode de
    fato PEDIR continua sendo decidido por `catalogo_para()` — a tela marca os
    itens fora do alcance em vez de escondê-los, porque saber que o serviço
    existe é justamente o que faz a pessoa parar de mandar e-mail.
    """
    if not prefixos:
        return []
    return list(ItemCatalogo.objects.filter(q_dominios(prefixos), ativo=True))


def prazo_medido(item: ItemCatalogo) -> tuple[int, bool]:
    """`(dias, e_medido)`. Cai no prometido enquanto não há histórico bastante."""
    duracoes = [
        s.dias_para_concluir
        for s in item.solicitacoes.concluidas().only("criado_em", "concluido_em")
        if s.dias_para_concluir is not None
    ]
    if len(duracoes) < MINIMO_PARA_PRAZO_MEDIDO:
        return item.prazo_prometido_dias, False
    return int(median(duracoes)), True


# ── Validação antes do envio ────────────────────────────────────────


def _centro_custo_de(pessoa) -> str:
    """Vem da identidade. O usuário não digita centro de custo."""
    return (
        Lotacao.objects.filter(user=pessoa)
        .values_list("centro_custo_codigo", flat=True)
        .first()
        or ""
    )


def verificar(
    item: ItemCatalogo,
    pessoa,
    dados: dict | None = None,
    valor: Decimal | None = None,
    cache: dict | None = None,
) -> list[Impedimento]:
    """O que impede este pedido de ser enviado. Vazio = pode enviar.

    Chamado pela tela a cada mudança (HTMX) para bloquear com o motivo à vista,
    e de novo dentro de `solicitar()` — a tela não é a fonte de verdade.
    """
    impedimentos: list[Impedimento] = []
    dados = dados or {}

    if not item.ativo:
        impedimentos.append(Impedimento("item", "Este serviço não está disponível."))

    if item.permissao and not pode(pessoa, item.permissao, cache=cache):
        impedimentos.append(Impedimento("item", "Você não tem acesso a este serviço."))

    for chave in item.campos_obrigatorios:
        valor_campo = dados.get(chave)
        if valor_campo is None or (isinstance(valor_campo, str) and not valor_campo.strip()):
            rotulo = next(
                (c.get("rotulo", chave) for c in item.campos if c["chave"] == chave), chave
            )
            impedimentos.append(Impedimento(chave, f"{rotulo} é obrigatório."))

    if item.exige_valor and (valor is None or valor <= 0):
        impedimentos.append(Impedimento("valor", "Informe o valor."))

    if item.exige_centro_custo and not _centro_custo_de(pessoa):
        impedimentos.append(
            Impedimento(
                "centro_custo",
                "Você não tem centro de custo na sua lotação. Peça ao RH para cadastrar.",
            )
        )

    return impedimentos


def _cabe_no_orcamento(centro_custo: str, valor: Decimal | None) -> bool:
    if not centro_custo or valor is None:
        return True
    return orc.resumo(centro_custo).cabe(valor)


def pode_auto_aprovar(
    item: ItemCatalogo, valor: Decimal | None, centro_custo: str
) -> bool:
    """Dentro do limite E dentro do orçamento não vai para fila humana."""
    if item.limite_auto_aprovacao is None:
        return False
    if valor is None:
        return True
    if valor > item.limite_auto_aprovacao:
        return False
    return _cabe_no_orcamento(centro_custo, valor)


# ── Pedir ───────────────────────────────────────────────────────────


@transaction.atomic
def solicitar(
    item: ItemCatalogo,
    pessoa,
    dados: dict | None = None,
    valor: Decimal | None = None,
    cache: dict | None = None,
) -> SolicitacaoServico:
    """Cria o pedido e o roteia — auto-aprovado ou para a cadeia de aprovação."""
    impedimentos = verificar(item, pessoa, dados, valor, cache=cache)
    if impedimentos:
        raise SolicitacaoError("; ".join(i.motivo for i in impedimentos))

    centro_custo = _centro_custo_de(pessoa) if item.exige_centro_custo else ""
    auto = pode_auto_aprovar(item, valor, centro_custo)

    solicitacao = SolicitacaoServico.objects.create(
        item=item,
        solicitante=pessoa,
        dados=dados or {},
        valor=valor,
        centro_custo_codigo=centro_custo,
        auto_aprovada=auto,
        situacao=(
            SituacaoServico.APROVADA if auto else SituacaoServico.AGUARDANDO_APROVACAO
        ),
    )

    if auto:
        # Automático não pode significar invisível: o compromisso é escriturado
        # do mesmo jeito, e o histórico registra que ninguém precisou decidir.
        if valor and centro_custo:
            from workspace.models.orcamento import Compromisso, competencia_de

            Compromisso.objects.create(
                dominio=item.dominio,
                origem_id=str(solicitacao.pk),
                descricao=item.nome[:200],
                centro_custo_codigo=centro_custo,
                valor=valor,
                competencia=competencia_de(),
                criado_por=pessoa,
            )
        return solicitacao

    aprovacao = apr.criar(
        dominio=item.dominio,
        titulo=item.nome,
        solicitante=pessoa,
        origem_id=str(solicitacao.pk),
        resumo=item.descricao_curta,
        valor=valor,
        centro_custo_codigo=centro_custo,
        dados={"item": item.chave, "campos": dados or {}},
    )
    solicitacao.aprovacao = aprovacao
    solicitacao.save(update_fields=["aprovacao"])
    return solicitacao


def minhas(pessoa):
    """As solicitações da pessoa, abertas primeiro."""
    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        return SolicitacaoServico.objects.none()
    return (
        SolicitacaoServico.objects.de(pessoa)
        .select_related("item", "aprovacao")
        .order_by("-criado_em")
    )


def minhas_do_modulo(pessoa, prefixos):
    """Os pedidos da pessoa dentro da fatia de um módulo, abertos primeiro."""
    if not prefixos:
        return SolicitacaoServico.objects.none()
    return minhas(pessoa).filter(q_dominios(prefixos, campo="item__dominio"))


@transaction.atomic
def cancelar(solicitacao: SolicitacaoServico, quem) -> SolicitacaoServico:
    """Só o solicitante cancela o próprio pedido."""
    if solicitacao.solicitante_id != getattr(quem, "pk", None):
        raise SolicitacaoError("Só quem pediu pode cancelar.")
    if not solicitacao.em_aberto:
        raise SolicitacaoError(
            f"Solicitação já está {solicitacao.get_situacao_display().lower()}."
        )

    solicitacao.situacao = SituacaoServico.CANCELADA
    solicitacao.save(update_fields=["situacao"])

    if solicitacao.aprovacao_id:
        try:
            apr.decidir(solicitacao.aprovacao, quem, apr.Decisao.CANCELAR)
        except apr.AprovacaoError:
            # A aprovação já foi decidida — o cancelamento do serviço vale, e o
            # orçamento é liberado abaixo de qualquer jeito.
            pass
        orc.cancelar(solicitacao.aprovacao)

    return solicitacao


# ── Reação à decisão de aprovação ───────────────────────────────────


def ao_decidir(sender, solicitacao, decisao, quem, **kwargs) -> None:
    """Ouvinte de `aprovacao_decidida` — reflete a decisão no pedido de serviço.

    O catálogo não é chamado pelo APR; ele ouve. Assim APR continua sem saber
    que catálogo existe.
    """
    servico = SolicitacaoServico.objects.filter(aprovacao=solicitacao).first()
    if servico is None:
        return

    if decisao == apr.Decisao.APROVAR:
        servico.situacao = SituacaoServico.APROVADA
    elif decisao == apr.Decisao.DEVOLVER:
        servico.situacao = SituacaoServico.DEVOLVIDA
        etapa = solicitacao.etapas.exclude(justificativa="").order_by("-decidido_em").first()
        servico.motivo_devolucao = etapa.justificativa if etapa else ""
    elif decisao == apr.Decisao.CANCELAR:
        servico.situacao = SituacaoServico.CANCELADA
    else:  # pragma: no cover - Decisao só tem três valores
        return

    servico.save(update_fields=["situacao", "motivo_devolucao"])


def conectar() -> None:
    """Liga o ouvinte. Chamado no `ready()` do app."""
    apr.aprovacao_decidida.connect(
        ao_decidir, dispatch_uid="workspace.catalogo.ao_decidir"
    )
