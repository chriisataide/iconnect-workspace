"""Orçamento — os três números da barra tripla, e quem os escritura.

    realizado     o que já saiu           ← provider do domínio financeiro
    comprometido  aprovado e não pago     ← Compromisso, deste app
    este pedido   o que está em decisão   ← passado pelo chamador

É esse conjunto que transforma aprovação de carimbo em decisão: o aprovador vê o
efeito ANTES de decidir, não no fechamento.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone

from workspace.models.aprovacao import SolicitacaoAprovacao
from workspace.models.orcamento import (
    Compromisso,
    SituacaoCompromisso,
    competencia_de,
)
from workspace.providers import orcamento as provedor


@dataclass(frozen=True)
class ResumoOrcamento:
    """Os números de um centro de custo num mês.

    `orcamento is None` significa **não definido**, não zero. A tela precisa
    dizer "CC sem orçamento — não consigo calcular impacto" em vez de mostrar
    0%, que o aprovador leria como "tem folga".
    """

    centro_custo_codigo: str
    competencia: date
    orcamento: Decimal | None
    realizado: Decimal
    comprometido: Decimal

    @property
    def consumido(self) -> Decimal:
        return self.realizado + self.comprometido

    @property
    def disponivel(self) -> Decimal | None:
        if self.orcamento is None:
            return None
        return self.orcamento - self.consumido

    @property
    def tem_orcamento(self) -> bool:
        return self.orcamento is not None and self.orcamento > 0

    def percentual(self, adicional: Decimal | None = None) -> Decimal | None:
        """Percentual consumido, opcionalmente somando um pedido em decisão."""
        if not self.tem_orcamento:
            return None
        total = self.consumido + (adicional or Decimal("0"))
        return (total / self.orcamento * Decimal("100")).quantize(Decimal("0.1"))

    def cabe(self, valor: Decimal) -> bool:
        """Este valor cabe no que resta?

        Sem orçamento definido devolve `True`: o Workspace não é quem barra por
        falta de cadastro — barrar aqui esconderia o problema real, que é o CC
        sem orçamento.
        """
        disponivel = self.disponivel
        if disponivel is None:
            return True
        return valor <= disponivel


def resumo(centro_custo_codigo: str, competencia: date | None = None) -> ResumoOrcamento:
    """Os três números. Sem provider registrado, orçamento e realizado ficam vazios."""
    mes = competencia_de(competencia)
    provider = provedor.obter()

    orcamento = provider.orcamento_mensal(centro_custo_codigo) if provider else None
    realizado = (
        provider.realizado_no_mes(centro_custo_codigo, mes) if provider else Decimal("0")
    )
    comprometido = (
        Compromisso.objects.ativos()
        .do_centro_custo(centro_custo_codigo, mes)
        .total()
    )

    return ResumoOrcamento(
        centro_custo_codigo=centro_custo_codigo,
        competencia=mes,
        orcamento=orcamento,
        realizado=realizado,
        comprometido=comprometido,
    )


# ── Cadastro de centro de custo ─────────────────────────────────────


class OrcamentoError(Exception):
    """O cadastro de orçamento não pode ser gravado assim."""


def centros_de_custo() -> list:
    """A lista de centros de custo, ou vazia quando não há domínio financeiro.

    Vazia e não erro: o Workspace roda sem `financas` instalado — é a mesma
    razão de `resumo()` responder "sem orçamento" em vez de estourar.
    """
    provider = provedor.obter()
    return provider.centros() if provider else []


def salvar_centro_de_custo(codigo: str, nome: str, orcamento_mensal=None, ativo: bool = True):
    """Cria ou atualiza um centro de custo pelo contrato. `None` sem domínio.

    Quem chama precisa tratar o `None`: sem provider registrado a tela tem de
    dizer que o cadastro financeiro não está disponível, e não fingir que
    gravou.
    """
    codigo = (codigo or "").strip()
    nome = (nome or "").strip()
    if not codigo:
        raise OrcamentoError("O código do centro de custo é obrigatório.")
    if not nome:
        raise OrcamentoError("O centro de custo precisa de um nome.")

    provider = provedor.obter()
    if provider is None:
        return None
    return provider.salvar_centro(
        codigo=codigo[:20], nome=nome[:120], orcamento_mensal=orcamento_mensal, ativo=ativo
    )


# ── Escrituração ────────────────────────────────────────────────────


@transaction.atomic
def escriturar(solicitacao: SolicitacaoAprovacao, quem=None) -> Compromisso | None:
    """Cria o compromisso de uma solicitação aprovada.

    Devolve `None` — sem erro — quando não há o que comprometer: solicitação sem
    valor (férias) ou sem centro de custo. Levantar exceção aqui quebraria a
    aprovação de férias, que é legítima e não toca orçamento.

    Idempotente pela constraint: um retry do sinal não dobra o comprometido.
    """
    if not solicitacao.valor or solicitacao.valor <= 0:
        return None
    if not solicitacao.centro_custo_codigo:
        return None

    existente = Compromisso.objects.filter(solicitacao=solicitacao).first()
    if existente is not None:
        return existente

    return Compromisso.objects.create(
        solicitacao=solicitacao,
        dominio=solicitacao.dominio,
        origem_id=solicitacao.origem_id,
        descricao=solicitacao.titulo[:200],
        centro_custo_codigo=solicitacao.centro_custo_codigo,
        valor=solicitacao.valor,
        competencia=competencia_de(),
        criado_por=quem,
    )


@transaction.atomic
def baixar(compromisso: Compromisso, movimentacao_id: str = "") -> Compromisso:
    """A movimentação real entrou — o compromisso sai do comprometido.

    Não apaga: "o que foi comprometido em setembro" é o dado que permite
    explicar o fechamento depois.
    """
    if compromisso.situacao != SituacaoCompromisso.ATIVO:
        return compromisso

    compromisso.situacao = SituacaoCompromisso.BAIXADO
    compromisso.movimentacao_id = str(movimentacao_id or "")
    compromisso.baixado_em = timezone.now()
    compromisso.save(update_fields=["situacao", "movimentacao_id", "baixado_em"])
    return compromisso


@transaction.atomic
def baixar_do_pedido(solicitacao_servico) -> int:
    """Baixa o compromisso do pedido ENTREGUE. Devolve quantos saíram — §58.

    ## O defeito que isto conserta

    `baixar()` existia e **ninguém a chamava**. O compromisso entrava na
    aprovação e só saía por cancelamento: pedido entregue continuava contando
    como "comprometido" para sempre.

    A consequência é aritmética. `consumido = realizado + comprometido`, e
    assim que a nota é lançada no sistema financeiro a mesma compra passa a
    contar duas vezes — uma como realizada, outra como comprometida. A barra do
    centro de custo sobe sozinha todo mês, e um dia recusa um pedido legítimo
    dizendo que o orçamento acabou.

    ## Por que a conclusão, e não o pagamento

    Pagar é fato do sistema financeiro, e o Workspace não o conhece — é por isso
    que `movimentacao_id` existe como referência frouxa. Concluir é o último
    fato que ESTE produto observa, e é quando a despesa deixa de ser promessa e
    vira dinheiro que o financeiro vai lançar. Esperar por um evento que não
    chega é como o compromisso ficou eterno.

    Pega os dois caminhos de escrituração: o da cadeia de aprovação, que amarra
    pela FK, e o do auto-aprovado, que grava só `dominio` + `origem_id`. Um só
    deixaria metade dos pedidos comprometida para sempre — e seria justamente a
    metade mais comum, que é a que nunca passa por bandeja.
    """
    filtros = models.Q(dominio=solicitacao_servico.item.dominio) & models.Q(
        origem_id=str(solicitacao_servico.pk)
    )
    if solicitacao_servico.aprovacao_id:
        filtros |= models.Q(solicitacao_id=solicitacao_servico.aprovacao_id)

    baixados = 0
    for compromisso in Compromisso.objects.ativos().filter(filtros):
        baixar(compromisso)
        baixados += 1
    return baixados


@transaction.atomic
def cancelar(solicitacao: SolicitacaoAprovacao) -> int:
    """Solicitação cancelada ou devolvida libera o orçamento reservado."""
    return (
        Compromisso.objects.filter(solicitacao=solicitacao)
        .ativos()
        .update(situacao=SituacaoCompromisso.CANCELADO)
    )


# ── Ligação com o motor de aprovação ────────────────────────────────


def ao_decidir(sender, solicitacao, decisao, quem, **kwargs) -> None:
    """Ouvinte de `aprovacao_decidida`.

    É aqui que o motor de aprovação e o orçamento se encontram — sem que APR
    conheça `Compromisso` nem orçamento conheça cadeia de aprovação.
    """
    from workspace.services.aprovacao import Decisao

    if decisao == Decisao.APROVAR:
        escriturar(solicitacao, quem=quem)
    elif decisao in (Decisao.DEVOLVER, Decisao.CANCELAR):
        cancelar(solicitacao)


def conectar() -> None:
    """Liga o ouvinte. Chamado no `ready()` do app."""
    from workspace.services.aprovacao import aprovacao_decidida

    # `dispatch_uid` evita ouvinte duplicado quando `ready()` roda duas vezes —
    # acontece em teste e com autoreload do runserver, e duplicado dobraria o
    # comprometido.
    aprovacao_decidida.connect(ao_decidir, dispatch_uid="workspace.orcamento.ao_decidir")


# ── A grade anual (Onda 8) ──────────────────────────────────────────
#
# ## A decisão que veio antes do model
#
# Já existiam DOIS orçados neste produto, e a onda começou por decidir de quem
# é cada um:
#
#   `financas`     teto de OPERAÇÃO   → responde "isto cabe?" na aprovação
#   `resultados`   orçado CONTÁBIL    → responde "o mês fechou onde deveria?"
#
# Eles não se fundem. Quando divergem, isso é **divergência entre fontes** — a
# regra que a ingestão já criou —, e não algo que um `if` resolve. Ver ADR-036.
#
# ## As seis colunas
#
# O benchmark (§3.7) usa `realizado | ajustes | realizado ajustado | orçado |
# %RExOR | diferença`, e a coluna do meio é onde a operação declara o que já
# aconteceu e ainda não bateu na contabilidade — "sem ela a conversa vira briga
# sobre o número em vez de decisão".
#
# A nossa coluna do meio é o **comprometido**: aprovado e não pago. É o mesmo
# papel, com um número que o Workspace POSSUI — ele nasce da aprovação, que é
# daqui.


PERMISSAO_ORCAMENTO = "fin.orcamento.ler"
PERMISSAO_REVISAR = "fin.orcamento.revisar"

MESES = (
    "jan", "fev", "mar", "abr", "mai", "jun",
    "jul", "ago", "set", "out", "nov", "dez",
)


class SemOrcamento(Exception):
    """Esta pessoa não responde por centro de custo nenhum."""


@dataclass(frozen=True)
class LinhaDoMes:
    """Um mês da grade — as seis colunas."""

    mes: int
    orcado: Decimal | None
    comprometido: Decimal
    realizado: Decimal

    @property
    def rotulo(self) -> str:
        return MESES[self.mes - 1]

    @property
    def consumido(self) -> Decimal:
        """Realizado + comprometido. A coluna que decide, e não o realizado.

        Decidir por realizado é como se estoura um orçamento sem ninguém
        perceber: o que foi aprovado e ainda não pagou já é dinheiro gasto, só
        que invisível no extrato.
        """
        return self.realizado + self.comprometido

    @property
    def saldo(self) -> Decimal | None:
        if self.orcado is None:
            return None
        return self.orcado - self.consumido

    @property
    def percentual(self) -> Decimal | None:
        """`None` sem orçado, e nunca 0. Sem teto não há denominador."""
        if not self.orcado:
            return None
        return (self.consumido / self.orcado * Decimal("100")).quantize(Decimal("0.1"))

    @property
    def estourado(self) -> bool:
        saldo = self.saldo
        return saldo is not None and saldo < 0


def pode_ler_orcamento(pessoa, cache: dict | None = None) -> bool:
    from identidade.services.autorizacao import pode

    return pode(pessoa, PERMISSAO_ORCAMENTO, cache=cache)


def pode_revisar(pessoa, cache: dict | None = None) -> bool:
    from identidade.services.autorizacao import pode

    return pode(pessoa, PERMISSAO_REVISAR, cache=cache)


def centros_visiveis(pessoa, cache: dict | None = None) -> list:
    """Os centros de custo que esta pessoa alcança.

    Escopo global vê todos; qualquer outro vê o da própria lotação. Levanta
    `SemOrcamento` para quem não alcança nenhum — 403, e não uma grade de zeros:
    uma grade zerada para quem nunca vai ter dado faz a pessoa achar que a
    empresa não gastou nada.
    """
    from identidade.services.autorizacao import ESCOPO_GLOBAL, escopo_de

    if not pode_ler_orcamento(pessoa, cache=cache):
        raise SemOrcamento("Orçamento é de quem responde por centro de custo.")

    todos = centros_de_custo()
    if escopo_de(pessoa, PERMISSAO_ORCAMENTO, cache=cache) == ESCOPO_GLOBAL:
        return todos

    from identidade.models import Lotacao

    codigo = (
        Lotacao.objects.filter(user=pessoa)
        .values_list("centro_custo_codigo", flat=True)
        .first()
    )
    meus = [c for c in todos if codigo and c.codigo == codigo]
    if not meus:
        raise SemOrcamento(
            "Sua lotação não aponta para nenhum centro de custo com orçamento."
        )
    return meus


def grade_anual(centro_custo_codigo: str, ano: int) -> list[LinhaDoMes]:
    """Os doze meses, com as seis colunas. Nenhuma chamada de rede.

    O orçado vem do contrato; o comprometido, de `Compromisso`, que é daqui; o
    realizado, do contrato de novo. Um mês sem orçado devolve `None` e não zero
    — e a tela escreve "—".
    """
    provider = provedor.obter()
    do_ano = provider.orcamento_do_ano(centro_custo_codigo, ano) if provider else {}

    linhas = []
    for mes in range(1, 13):
        competencia = date(ano, mes, 1)
        orcado = do_ano.get(mes)
        if orcado is None and provider is not None:
            # Cai no teto avulso do centro de custo — é o que a bandeja usa, e a
            # grade precisa mostrar o MESMO número, senão as duas telas
            # discordam sobre o mesmo mês.
            orcado = provider.orcamento_do_mes(centro_custo_codigo, competencia)
        linhas.append(
            LinhaDoMes(
                mes=mes,
                orcado=orcado,
                comprometido=(
                    Compromisso.objects.ativos()
                    .do_centro_custo(centro_custo_codigo, competencia)
                    .total()
                ),
                realizado=(
                    provider.realizado_no_mes(centro_custo_codigo, competencia)
                    if provider
                    else Decimal("0")
                ),
            )
        )
    return linhas


def revisoes(centro_custo_codigo: str, ano: int) -> list:
    provider = provedor.obter()
    return provider.revisoes_do_ano(centro_custo_codigo, ano) if provider else []


def montar(centro_custo_codigo: str, ano: int, valores: dict, quem, cache=None) -> bool:
    """Escreve o rascunho do ano. Recusa em orçamento vigente."""
    if not pode_revisar(quem, cache=cache):
        raise OrcamentoError("Montar o orçamento é de quem responde pelo dinheiro.")
    provider = provedor.obter()
    if provider is None:
        return False
    return provider.montar_orcamento(centro_custo_codigo, ano, valores)


def vigorar(centro_custo_codigo: str, ano: int, quem, cache=None) -> bool:
    if not pode_revisar(quem, cache=cache):
        raise OrcamentoError("Pôr um orçamento em vigor é de quem responde pelo dinheiro.")
    provider = provedor.obter()
    if provider is None:
        return False
    return provider.vigorar_orcamento(centro_custo_codigo, ano, quem)


def revisar(centro_custo_codigo: str, ano: int, deltas: dict, motivo: str, quem,
            cache=None):
    """A ÚNICA forma de mexer num orçamento vigente. Motivo obrigatório.

    É a regra do benchmark — "só pode gastar se tiver recurso e fizer a revisão
    orçamentária" — pelo lado que importa: o teto não muda sem revisão. Antes
    desta onda, alguém com `is_staff` editava o campo e ninguém ficava sabendo.
    """
    if not pode_revisar(quem, cache=cache):
        raise OrcamentoError("Revisar o orçamento é de quem responde pelo dinheiro.")
    motivo = (motivo or "").strip()
    if not motivo:
        # Sem motivo a revisão vira uma edição com data. O motivo é a metade que
        # sobrevive à pessoa que a fez.
        raise OrcamentoError("A revisão exige o motivo. Ele fica no histórico.")
    provider = provedor.obter()
    if provider is None:
        return None
    return provider.revisar_orcamento(centro_custo_codigo, ano, deltas, motivo, quem)


def confronto_com_o_espelho(centro_custo_codigo: str, ano: int) -> list[dict]:
    """O nosso teto contra o orçado do Sankhya, lado a lado — e SEM desempate.

    Nenhum código escolhe vencedor aqui. Os dois números aparecem, a diferença
    aparece, e resolver é decisão de gente com a regra de precedência na mão.
    Escolher dentro de um `if` é o que a restrição 5 do produto proíbe, e o
    motivo é simples: o `if` teria razão até o dia em que não tivesse, e ninguém
    saberia dizer quando esse dia foi.

    Lista vazia quando o espelho não está conectado — que é estado normal, e não
    falha.
    """
    from workspace.providers import resultados as espelho

    provedor_financeiro = espelho.obter(espelho.ProvedorResultadoFinanceiro)
    if provedor_financeiro is None:
        return []

    provider = provedor.obter()
    nosso = provider.orcamento_do_ano(centro_custo_codigo, ano) if provider else {}

    # `serie_competencia` e não `consolidado`: o orçado por mês está no
    # `CompetenciaDTO`, e o consolidado é uma soma que não carrega orçado nenhum.
    # Uma consulta para os doze meses, e não doze — a tela abre com o ano
    # inteiro, e doze idas ao espelho por centro de custo seriam N+1 por página.
    do_espelho = {
        c.mes: c.custo_orcado
        for c in provedor_financeiro.serie_competencia(
            espelho.Escopo(centros_custo=(centro_custo_codigo,)),
            date(ano, 1, 1),
            date(ano, 12, 1),
        )
        if c.ano == ano
    }

    linhas = []
    for mes in range(1, 13):
        contabil = do_espelho.get(mes)
        meu = nosso.get(mes)
        if meu is None and contabil is None:
            continue
        linhas.append(
            {
                "mes": mes,
                "rotulo": MESES[mes - 1],
                "operacao": meu,
                "contabil": contabil,
                "diferenca": (
                    (meu - contabil) if meu is not None and contabil is not None
                    else None
                ),
            }
        )
    return linhas
