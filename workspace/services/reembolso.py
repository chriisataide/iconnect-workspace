"""RMB — despesas item a item e o acerto do adiantamento.

A regra que dá nome ao módulo: **quem soma é o sistema**. O usuário informa uma
linha por compra; o total do pedido, a diferença contra o adiantamento e o lado
para o qual ela corre são derivados, nunca digitados. Valor total digitado à mão
é o campo que diverge da soma dos anexos, e a divergência só aparece na
conferência do Financeiro — semanas depois, com o dinheiro já pago.

O acerto tem três saídas e nenhuma é opcional:

    gastou menos  →  devolver     a pessoa deposita na conta da empresa
    gastou mais   →  receber      a empresa paga na conta da pessoa
    gastou igual  →  quitado      nada a fazer, e ainda assim registrado

`quitado` existe como registro porque "não houve diferença" e "ninguém conferiu"
são estados diferentes, e sem o registro o Financeiro não consegue distinguir os
dois na hora de cobrar prestação de contas.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.db import models, transaction

from workspace.models.catalogo import (
    SituacaoServico,
    SolicitacaoServico,
    TipoCampo,
)
from workspace.models.reembolso import (
    AcertoAdiantamento,
    DespesaReembolso,
    SentidoAcerto,
)

# O domínio, e não a chave do item: o domínio é o que roteia o pedido, e um dia
# pode existir "adiantamento de viagem" — que continua sendo `fin.adiantamento`
# e continua tendo de ser prestado contas.
DOMINIO_ADIANTAMENTO = "fin.adiantamento"

# Teto de linhas por reembolso. Mesma razão do teto de anexos: uma prestação de
# contas com 60 compras não é conferida, é carimbada. Quem tem mais que isso
# está prestando contas de um mês inteiro de uma vez, e o combinado é por viagem
# ou por evento.
MAXIMO_DESPESAS = 20


class ReembolsoError(Exception):
    """Linha de despesa inválida, ou acerto que não pode ser confirmado."""


@dataclass(frozen=True)
class Linha:
    """Uma compra vinda do formulário, antes de virar `DespesaReembolso`."""

    valor: Decimal | None
    motivo: str
    arquivo: object | None = None


@dataclass(frozen=True)
class Acerto:
    """A conta entre o adiantado e o gasto. Só leitura — quem grava é
    `confirmar_acerto()`."""

    sentido: str
    total_adiantado: Decimal
    total_gasto: Decimal
    diferenca: Decimal

    @property
    def devolver(self) -> bool:
        return self.sentido == SentidoAcerto.DEVOLVER

    @property
    def receber(self) -> bool:
        return self.sentido == SentidoAcerto.RECEBER

    @property
    def quitado(self) -> bool:
        return self.sentido == SentidoAcerto.QUITADO


# ── Leitura do formulário ───────────────────────────────────────────


# `1.234` é mil duzentos e trinta e quatro; `12.50` são doze e cinquenta. O que
# separa os dois casos é o ponto seguido de EXATAMENTE três dígitos, repetido
# até o fim — a forma como se escreve milhar em português.
_MILHAR = re.compile(r"\d{1,3}(\.\d{3})+")


def valor_de(bruto: str | None) -> Decimal | None:
    """`1.234,56`, `1234.56` e `12,50` viram o número que a pessoa quis dizer.

    Antes desta função, "apaga todo ponto e troca vírgula por ponto" era a
    regra — e ela lê `1234.56` como **cento e vinte e três mil**. Num campo de
    reembolso isso não é um arredondamento: é um pedido cem vezes maior que o
    gasto, aprovado por quem confiou no número da tela.

    Então: onde há vírgula, ela é o decimal e o ponto é milhar. Onde não há,
    só é milhar o ponto que separa exatamente três dígitos.
    """
    if not bruto:
        return None

    texto = bruto.strip()
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif _MILHAR.fullmatch(texto):
        texto = texto.replace(".", "")

    try:
        valor = Decimal(texto)
    except (InvalidOperation, ValueError):
        return None
    return valor.quantize(Decimal("0.01"))


def tem_despesas(item) -> bool:
    """O item pede as compras uma a uma?"""
    return any(c.get("tipo") == TipoCampo.DESPESAS for c in item.campos)


def aceita_adiantamento(item) -> bool:
    return any(c.get("tipo") == TipoCampo.ADIANTAMENTO for c in item.campos)


def total(linhas) -> Decimal:
    """A soma das compras. Linha sem valor conta como zero — quem barra linha
    incompleta é `verificar_linhas()`, e somar aqui não pode estourar."""
    return sum(
        (linha.valor for linha in linhas if linha.valor is not None), Decimal("0")
    )


def verificar_linhas(linhas) -> list[str]:
    """Os motivos que impedem estas linhas de entrar. Vazio = podem entrar.

    Devolve a lista inteira, e não a primeira falha: corrigir um erro por vez é
    o que faz a pessoa desistir no terceiro envio.
    """
    from workspace.services import anexos as anx

    motivos: list[str] = []

    if not linhas:
        motivos.append("Adicione ao menos uma compra, com comprovante e valor.")
        return motivos

    if len(linhas) > MAXIMO_DESPESAS:
        motivos.append(f"No máximo {MAXIMO_DESPESAS} compras por reembolso.")

    for numero, linha in enumerate(linhas, start=1):
        if linha.valor is None:
            motivos.append(f"Compra {numero}: informe o valor.")
        elif linha.valor <= Decimal("0"):
            motivos.append(f"Compra {numero}: o valor tem de ser positivo.")
        if not (linha.motivo or "").strip():
            motivos.append(f"Compra {numero}: informe o motivo.")
        if linha.arquivo is None:
            motivos.append(f"Compra {numero}: anexe o comprovante.")
        else:
            recusa = anx.validar(linha.arquivo)
            if recusa:
                motivos.append(f"Compra {numero}: {recusa}")

    return motivos


# ── Adiantamentos a prestar contas ──────────────────────────────────

# Um adiantamento já decidido: o dinheiro foi liberado, então ele deve
# prestação de contas. Pedido ainda em aprovação não deve nada — não há o que
# prestar contas de dinheiro que não saiu.
_LIBERADOS = [
    SituacaoServico.APROVADA,
    SituacaoServico.EM_ATENDIMENTO,
    SituacaoServico.CONCLUIDA,
]


def adiantamentos_pendentes(pessoa):
    """Os adiantamentos desta pessoa que ainda não foram prestados contas.

    "Pendente" é definido pela ausência de uma prestação VIVA: reembolso
    cancelado não segura o adiantamento, senão um cancelamento acidental
    deixaria a pessoa sem como prestar contas para sempre.
    """
    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        return SolicitacaoServico.objects.none()

    vivas = SolicitacaoServico.objects.filter(
        adiantamento=models.OuterRef("pk")
    ).exclude(situacao=SituacaoServico.CANCELADA)

    return (
        SolicitacaoServico.objects.de(pessoa)
        .filter(
            item__dominio__startswith=DOMINIO_ADIANTAMENTO,
            situacao__in=_LIBERADOS,
            valor__isnull=False,
        )
        .exclude(models.Exists(vivas))
        .select_related("item")
        .order_by("-criado_em")
    )


def adiantamento_escolhido(pessoa, pk_bruto: str | None):
    """Resolve o id vindo do formulário. `None` quando não veio nada.

    Busca dentro de `adiantamentos_pendentes` de propósito: assim um id de
    outra pessoa, ou de um adiantamento já prestado, não é "não encontrado" por
    acaso — é impossível por construção.
    """
    if not pk_bruto:
        return None
    try:
        pk = int(pk_bruto)
    except (TypeError, ValueError):
        raise ReembolsoError("Adiantamento inválido.")

    escolhido = adiantamentos_pendentes(pessoa).filter(pk=pk).first()
    if escolhido is None:
        raise ReembolsoError(
            "Este adiantamento não está pendente de prestação de contas."
        )
    return escolhido


# ── Gravação ────────────────────────────────────────────────────────


@transaction.atomic
def gravar_linhas(solicitacao: SolicitacaoServico, linhas, quem) -> list[DespesaReembolso]:
    """Cria uma `DespesaReembolso` por compra, cada uma com o seu anexo.

    Um anexo por linha, e não um lote no fim: é o vínculo entre o comprovante e
    o valor que faz a conferência deixar de ser adivinhação.
    """
    from workspace.services import anexos as anx

    motivos = verificar_linhas(linhas)
    if motivos:
        raise ReembolsoError("; ".join(motivos))

    criadas: list[DespesaReembolso] = []
    for ordem, linha in enumerate(linhas):
        # `campo` numerado para que o anexo continue rastreável mesmo se a
        # linha for apagada: o nome do campo diz de qual compra ele veio.
        anexos = anx.guardar(solicitacao, {f"despesa-{ordem}": [linha.arquivo]}, quem)
        criadas.append(
            DespesaReembolso.objects.create(
                solicitacao=solicitacao,
                ordem=ordem,
                valor=linha.valor,
                motivo=linha.motivo.strip()[:200],
                anexo=anexos[0] if anexos else None,
            )
        )
    return criadas


# ── O acerto ────────────────────────────────────────────────────────


def calcular_acerto(prestacao: SolicitacaoServico) -> Acerto | None:
    """A conta desta prestação. `None` quando o pedido não presta contas de nada."""
    adiantamento = prestacao.adiantamento
    if adiantamento is None:
        return None

    adiantado = adiantamento.valor or Decimal("0")
    gasto = prestacao.total_despesas
    if gasto is None:
        gasto = prestacao.valor or Decimal("0")

    diferenca = gasto - adiantado
    if diferenca < 0:
        sentido = SentidoAcerto.DEVOLVER
    elif diferenca > 0:
        sentido = SentidoAcerto.RECEBER
    else:
        sentido = SentidoAcerto.QUITADO

    return Acerto(
        sentido=sentido,
        total_adiantado=adiantado,
        total_gasto=gasto,
        # Módulo: o lado já está em `sentido`, e "-5,00" numa tela de devolução
        # faz a pessoa perguntar se deve devolver ou receber.
        diferenca=abs(diferenca),
    )


@transaction.atomic
def confirmar_acerto(
    prestacao: SolicitacaoServico,
    quem,
    dados_bancarios: str = "",
    comprovante=None,
) -> AcertoAdiantamento:
    """Fecha a conta do adiantamento. Uma vez só.

    O que cada lado exige:

    - **devolver** — o comprovante do depósito. Sem ele, o acerto seria a
      pessoa dizendo que devolveu, que é exatamente o que já acontecia por
      fora.
    - **receber** — a conta onde a empresa deposita. Sem ela não há para onde
      pagar, e o pedido pararia na mesa do Financeiro esperando um e-mail.
    - **quitado** — nada, e mesmo assim vira registro.
    """
    from workspace.services import anexos as anx

    if getattr(prestacao, "solicitante_id", None) != getattr(quem, "pk", None):
        raise ReembolsoError("Só quem prestou contas pode confirmar o acerto.")

    conta = calcular_acerto(prestacao)
    if conta is None:
        raise ReembolsoError("Este pedido não presta contas de um adiantamento.")

    if AcertoAdiantamento.objects.filter(prestacao=prestacao).exists():
        raise ReembolsoError("O acerto deste pedido já foi confirmado.")

    dados_bancarios = (dados_bancarios or "").strip()
    anexo = None

    if conta.devolver:
        if comprovante is None:
            raise ReembolsoError("Anexe o comprovante da devolução.")
        recusa = anx.validar(comprovante)
        if recusa:
            raise ReembolsoError(recusa)
        anexo = anx.guardar(prestacao, {"devolucao": [comprovante]}, quem)[0]
        # A conta da empresa é copiada para o registro: conta bancária muda, e
        # o histórico tem de dizer para onde o dinheiro foi na época.
        dados_bancarios = dados_bancarios or conta_da_empresa()
    elif conta.receber and not dados_bancarios:
        raise ReembolsoError("Informe a conta onde a empresa deve depositar.")

    from workspace.services import historico as hst

    hst.registrar(
        prestacao, hst.Acao.ACERTO, quem=quem,
        observacao=f"{SentidoAcerto(conta.sentido).label} · R$ {conta.diferenca}",
    )
    return AcertoAdiantamento.objects.create(
        prestacao=prestacao,
        sentido=conta.sentido,
        total_adiantado=conta.total_adiantado,
        total_gasto=conta.total_gasto,
        diferenca=conta.diferenca,
        dados_bancarios=dados_bancarios,
        comprovante=anexo,
        confirmado_por=quem,
    )


def conta_da_empresa() -> str:
    """Para onde a pessoa devolve o que sobrou.

    Em `settings` e não no banco porque é dado de configuração da instalação, e
    porque uma conta bancária editável por qualquer um com acesso ao admin é um
    convite a fraude — mudar a conta passa a exigir deploy.
    """
    from django.conf import settings

    return getattr(settings, "CONTA_BANCARIA_EMPRESA", "").strip()


def conta_sugerida(prestacao: SolicitacaoServico) -> str:
    """A conta que a pessoa informou no adiantamento, para pré-preencher.

    Pré-preencher AQUI é seguro, e é o oposto da regra da busca (que não
    pré-preenche pedido): este é um dado que a própria pessoa digitou neste
    mesmo fluxo, não um palpite sobre o que ela quis dizer.
    """
    adiantamento = prestacao.adiantamento
    if adiantamento is None:
        return ""
    return (adiantamento.dados or {}).get("dados_bancarios", "") or ""
