"""Acervo de documentos — quem vê, quem precisa confirmar, o que está vencendo.

## A regra que sustenta o resto

Documento vencido **não é apresentado como vigente**. Ele não desaparece — quem
tem o link ainda abre, e a tela diz que está vencido — mas sai da vitrine e sai
da busca. Acervo que apresenta POP vencido junto com POP em vigor é pior que não
ter acervo: a pessoa segue o procedimento errado achando que seguiu o certo.

## Por que a confirmação de leitura importa mais do que parece

Comunicado corporativo por e-mail não tem retorno. Documento com leitura
obrigatória e trilha por versão é requisito direto de ISO 9001/27001 e peça de
defesa trabalhista — e é a única métrica do acervo que vale dinheiro.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from identidade.services.autorizacao import subjects_de
from workspace.models.conteudo import (
    ConfirmacaoLeitura,
    Documento,
    SituacaoDocumento,
    TipoDocumento,
)

# Janela de aviso para o dono. 30 dias é o mínimo para reunir quem revisa,
# revisar e republicar sem virar urgência.
DIAS_DE_AVISO = 30


class ConteudoError(Exception):
    """Operação inválida sobre o acervo."""


# ── Leitura ─────────────────────────────────────────────────────────


def visiveis_para(pessoa, cache: dict | None = None):
    """Documentos vigentes que esta pessoa pode ver.

    Anônimo recebe só o que é público (`["*"]`) — o Workspace é aberto na rede da
    empresa, e uma política geral não é segredo. Documento de departamento exige
    saber a quem a pessoa pertence, e isso exige login.
    """
    subjects = subjects_de(pessoa, cache=cache)
    return Documento.objects.publicados().para_subjects(subjects)


def agrupado_para(pessoa, cache: dict | None = None) -> dict[str, list[Documento]]:
    """Por tipo, na ordem de declaração do enum — que é ordem de busca.

    Alfabética poria "Instrução de trabalho" antes de "POP", quando POP é o que a
    maioria vem procurar. Mesmo raciocínio do catálogo de serviços.
    """
    por_tipo: dict[str, list[Documento]] = {}
    for documento in visiveis_para(pessoa, cache=cache).select_related("dono"):
        por_tipo.setdefault(documento.tipo, []).append(documento)

    agrupado: dict[str, list[Documento]] = {}
    for tipo in TipoDocumento:
        itens = por_tipo.get(tipo.value)
        if itens:
            agrupado[tipo.label] = itens
    return agrupado


def pode_ver(documento: Documento, pessoa, cache: dict | None = None) -> bool:
    """Autorização de UM documento, para a tela de leitura.

    Vencido e revogado seguem acessíveis por link direto, de propósito: quem
    precisa saber o que dizia o POP anterior a uma ocorrência precisa poder abrir.
    O que muda é que a tela avisa, e a vitrine não lista.
    """
    if documento.situacao == SituacaoDocumento.RASCUNHO:
        # Rascunho é só do dono. Rascunho visível é meio-documento tratado como
        # norma, e alguém vai seguir.
        return getattr(pessoa, "pk", None) == documento.dono_id

    alvo = set(documento.publico_alvo or ["*"])
    return bool(alvo & set(subjects_de(pessoa, cache=cache)))


# ── Leitura obrigatória ─────────────────────────────────────────────


def pendentes_de_leitura(pessoa, cache: dict | None = None) -> list[Documento]:
    """Obrigatórios, visíveis, sem confirmação DA VERSÃO ATUAL.

    Uma consulta para as confirmações, não uma por documento: a lista aparece no
    Meu dia de toda pessoa, em toda visita.
    """
    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        return []

    obrigatorios = list(
        visiveis_para(pessoa, cache=cache).obrigatorios().select_related("dono")
    )
    if not obrigatorios:
        return []

    confirmadas = set(
        ConfirmacaoLeitura.objects.filter(
            pessoa=pessoa, documento__in=obrigatorios
        ).values_list("documento_id", "versao")
    )
    return [d for d in obrigatorios if (d.pk, d.versao) not in confirmadas]


@transaction.atomic
def confirmar(documento: Documento, pessoa) -> ConfirmacaoLeitura:
    """Registra a leitura da versão atual. Idempotente."""
    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        raise ConteudoError("Confirmação exige saber quem confirmou.")
    if not documento.vigente:
        # Confirmar leitura de documento vencido registraria conformidade com um
        # texto que não vale mais.
        raise ConteudoError("Este documento não está vigente.")

    # `get_or_create` e NÃO try/except IntegrityError.
    #
    # Capturar `IntegrityError` dentro de um `atomic` deixa a transação
    # QUEBRADA: a consulta seguinte estoura `TransactionManagementError`, e o
    # duplo clique em "Confirmo que li" viraria erro 500 em vez de idempotência.
    # `get_or_create` põe um savepoint em volta do insert, então a colisão
    # desfaz só o savepoint e a transação segue viva.
    confirmacao, _ = ConfirmacaoLeitura.objects.get_or_create(
        documento=documento, pessoa=pessoa, versao=documento.versao
    )
    return confirmacao


def ja_confirmou(documento: Documento, pessoa) -> bool:
    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        return False
    return ConfirmacaoLeitura.objects.filter(
        documento=documento, pessoa=pessoa, versao=documento.versao
    ).exists()


def cobertura_de_leitura(documento: Documento) -> dict:
    """Quantos confirmaram a versão atual. O número que vai para a auditoria.

    Sem denominador ainda: "quantas pessoas o público-alvo alcança" exige resolver
    sujeito → pessoas, que é consulta reversa do organograma e entra com o
    relatório de conformidade. Prometer um percentual agora seria inventar o
    denominador.
    """
    confirmadas = ConfirmacaoLeitura.objects.filter(
        documento=documento, versao=documento.versao
    ).count()
    return {"versao": documento.versao, "confirmadas": confirmadas}


# ── Para o dono ─────────────────────────────────────────────────────


def a_vencer(dono=None, dias: int = DIAS_DE_AVISO):
    """Documentos vigentes que vencem na janela. Filtra por dono se informado."""
    hoje = timezone.localdate()
    consulta = Documento.objects.publicados().filter(
        vigencia_fim__isnull=False, vigencia_fim__lte=hoje + timedelta(days=dias)
    )
    return consulta.filter(dono=dono) if dono is not None else consulta


def vencidos(dono=None):
    """Já vencidos e ainda marcados como vigentes — a fila de trabalho do dono."""
    consulta = Documento.objects.vencidos()
    return consulta.filter(dono=dono) if dono is not None else consulta
