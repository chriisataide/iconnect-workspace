"""A ponte entre o Portal e o n8n — e as duas barreiras do modo de teste.

O navegador nunca fala com o n8n nem com a Evolution API. O caminho é sempre:

    navegador → Django → este módulo → n8n → Evolution API → WhatsApp

## O que mudou em relação à automação original

Antes, o n8n lia o Excel de um arquivo montado e decidia sozinho o destino de
cada mensagem. Agora ele recebe deste módulo uma lista de destinos já
resolvidos, já validados, com o identificador do lote — e a decisão de para
quem mandar deixa de existir do lado de lá.

## As duas barreiras

A automação tinha duas conferências do modo de teste dentro do workflow, e elas
continuam lá. Este módulo acrescenta as suas próprias, ANTES da rede:

1. `destinos_do_lote` substitui todo destino pelo telefone de teste quando o
   lote está em teste. Não há caminho que monte um envio de teste com outro
   número: o telefone da planilha não é lido nessa função.
2. `_conferir_barreira` percorre o que foi montado e compara cada destino, um
   a um, com o telefone de teste. Qualquer divergência levanta `FalhaDeSeguranca`
   e o lote inteiro para — não o item, o lote.

A segunda parece redundante com a primeira, e é de propósito. A primeira
protege contra o dado errado; a segunda protege contra o CÓDIGO errado — uma
refatoração futura que monte destino por outro caminho encontra a barreira
antes que alguém receba uma mensagem que não devia.

Nunca há retorno ao telefone real em caso de falha. Um `except` que "tenta o
número verdadeiro" seria a única forma de o modo de teste vazar, então ele não
existe: a falha fecha o lote.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone

from workspace.models.ponto import (
    ColaboradorPonto,
    EnvioPonto,
    LotePonto,
    ModoEnvio,
    SituacaoEnvio,
    SituacaoLote,
)
from workspace.services.ponto import mascarar_telefone, normalizar_telefone

logger = logging.getLogger(__name__)


class FalhaDeSeguranca(Exception):
    """Um destino não bate com o modo do lote. O lote para; nada é enviado."""


class FalhaDeIntegracao(Exception):
    """O n8n não respondeu, recusou ou devolveu algo que não dá para interpretar."""


@dataclass(frozen=True)
class Resultado:
    enviados: int
    falhas: int
    detalhe: str = ""


# ── Montagem dos destinos ───────────────────────────────────────────


def destinos_do_lote(lote: LotePonto, colaboradores) -> list[tuple[ColaboradorPonto, str]]:
    """Para onde cada mensagem vai, de verdade.

    Em teste o telefone da pessoa não é sequer consultado. Essa é a diferença
    entre "substituímos o destino" e "não existe o destino real neste caminho".
    """
    if lote.em_teste:
        destino = normalizar_telefone(lote.telefone_teste)
        if not destino:
            raise FalhaDeSeguranca(
                "O telefone de teste não é um celular válido. "
                "Informe um número no formato (DD) 9XXXX-XXXX."
            )
        return [(c, destino) for c in colaboradores]

    # Produção: cada um com o seu, e quem não tem telefone bom fica de fora em
    # vez de virar erro no meio do disparo.
    return [(c, c.telefone_efetivo) for c in colaboradores if c.pode_produzir]


def _conferir_barreira(lote: LotePonto, pares: list[tuple[ColaboradorPonto, str]]) -> None:
    """A segunda barreira. Percorre o que foi montado e recusa o lote inteiro."""
    if lote.em_teste:
        esperado = normalizar_telefone(lote.telefone_teste)
        if not esperado:
            raise FalhaDeSeguranca("Modo de teste sem telefone de teste válido.")
        for colaborador, destino in pares:
            if destino != esperado:
                # O log leva o mascarado. Um alerta de segurança que imprime o
                # telefone da pessoa cria o vazamento que ele deveria evitar.
                logger.error(
                    "ponto: barreira de teste bloqueou lote %s (destino %s)",
                    lote.pk,
                    mascarar_telefone(destino),
                )
                raise FalhaDeSeguranca(
                    "Falha de segurança: destinatário diferente do telefone de teste. "
                    f"O envio de “{colaborador.nome}” não foi para o número de teste. "
                    "Nenhuma mensagem foi enviada."
                )
        return

    for colaborador, destino in pares:
        if not normalizar_telefone(destino):
            raise FalhaDeSeguranca(
                f"Falha de segurança: “{colaborador.nome}” está sem telefone válido "
                "e o lote está em modo de produção. Nenhuma mensagem foi enviada."
            )

    if len(pares) > settings.PONTO_MAXIMO_POR_LOTE:
        raise FalhaDeSeguranca(
            f"O lote tem {len(pares)} destinatários e o teto por disparo é "
            f"{settings.PONTO_MAXIMO_POR_LOTE}. Divida a planilha."
        )


# ── Preparo dos envios ──────────────────────────────────────────────


def preparar_envios(lote: LotePonto, colaboradores) -> list[EnvioPonto]:
    """Cria as linhas de `EnvioPonto` já com o destino conferido.

    As duas barreiras rodam aqui, antes de qualquer linha ser gravada. Um lote
    que não passa não deixa nem rastro de tentativa — o que ficou foi o evento
    de auditoria, escrito por quem chamou.
    """
    pares = destinos_do_lote(lote, colaboradores)
    if not pares:
        raise FalhaDeSeguranca("Nenhum colaborador selecionado tem destino válido.")

    _conferir_barreira(lote, pares)

    from workspace.services.ponto import Colaborador, Pendencia

    envios = []
    for colaborador, destino in pares:
        espelho = Colaborador(
            nome=colaborador.nome,
            pendencias=[
                Pendencia(data=p.get("data", ""), motivo=p.get("motivo", ""))
                for p in colaborador.pendencias
            ],
        )
        envios.append(
            EnvioPonto(
                lote=lote,
                colaborador=colaborador,
                modo=lote.modo,
                destino=destino,
                mensagem=espelho.mensagem(),
                situacao=SituacaoEnvio.PENDENTE,
            )
        )

    return EnvioPonto.objects.bulk_create(envios)


# ── Conversa com o n8n ──────────────────────────────────────────────


def montar_payload(lote: LotePonto, envios: list[EnvioPonto]) -> dict:
    """O que o n8n recebe: dados prontos e o identificador do lote.

    Ele não recebe o caminho de um Excel nem precisa abrir arquivo nenhum. A
    lista já vem agrupada por pessoa, com a mensagem montada e o destino
    decidido — ao n8n resta entregar e dizer o que aconteceu.
    """
    return {
        "loteId": lote.pk,
        "modo": lote.modo,
        "modoTeste": lote.em_teste,
        "telefoneTeste": normalizar_telefone(lote.telefone_teste) if lote.em_teste else "",
        "total": len(envios),
        "mensagens": [
            {
                "envioId": e.pk,
                "nome": e.colaborador.nome,
                "telefoneDestino": e.destino,
                "mensagem": e.mensagem,
                "quantidadePendencias": e.colaborador.quantidade_pendencias,
            }
            for e in envios
        ],
    }


def despachar(lote: LotePonto, envios: list[EnvioPonto]) -> Resultado:
    """Manda o lote ao n8n e interpreta a resposta.

    Timeout, recusa e resposta ilegível caem todos em `FalhaDeIntegracao`, e o
    lote fica em `CONCLUIDO_COM_ERROS` em vez de sumir: §26 pede que o lote não
    se perca, e um lote sem estado final é um lote perdido.
    """
    url = (settings.PONTO_N8N_WEBHOOK_URL or "").strip()
    if not url:
        raise FalhaDeIntegracao(
            "A integração não está configurada. Defina N8N_PONTO_WEBHOOK_URL no ambiente."
        )

    payload = montar_payload(lote, envios)
    corpo = json.dumps(payload).encode("utf-8")

    cabecalhos = {"Content-Type": "application/json"}
    if settings.PONTO_N8N_TOKEN:
        cabecalhos["Authorization"] = f"Bearer {settings.PONTO_N8N_TOKEN}"

    requisicao = urllib.request.Request(url, data=corpo, headers=cabecalhos, method="POST")

    EnvioPonto.objects.filter(pk__in=[e.pk for e in envios]).update(
        situacao=SituacaoEnvio.ENVIANDO
    )

    try:
        with urllib.request.urlopen(requisicao, timeout=settings.PONTO_N8N_TIMEOUT) as resposta:
            bruto = resposta.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as erro:
        # O corpo do erro pode trazer o motivo; o token, não — ele foi no
        # cabeçalho da ida e nunca volta na resposta.
        detalhe = f"HTTP {erro.code}"
        _marcar_falha(envios, detalhe)
        raise FalhaDeIntegracao(f"O n8n recusou o lote ({detalhe}).") from erro
    except urllib.error.URLError as erro:
        _marcar_falha(envios, str(erro.reason))
        raise FalhaDeIntegracao(
            "Não foi possível falar com o n8n. Verifique se a automação está no ar."
        ) from erro
    except TimeoutError as erro:
        _marcar_falha(envios, "timeout")
        raise FalhaDeIntegracao(
            f"O n8n não respondeu em {settings.PONTO_N8N_TIMEOUT}s. "
            "O lote continua registrado e pode ser consultado no histórico."
        ) from erro

    return _interpretar(envios, bruto)


def _marcar_falha(envios: list[EnvioPonto], erro: str) -> None:
    EnvioPonto.objects.filter(pk__in=[e.pk for e in envios]).update(
        situacao=SituacaoEnvio.ERRO, erro=erro[:500], enviado_em=timezone.now()
    )


def _interpretar(envios: list[EnvioPonto], bruto: str) -> Resultado:
    """Lê o retorno do n8n; o que ele não mencionar conta como enviado.

    O workflow devolve uma lista de resultados por `envioId`. Quando a resposta
    não traz detalhe nenhum — n8n configurado para responder imediatamente —,
    o lote fica como enviado e o erro, se houver, aparece na execução do n8n.
    """
    agora = timezone.now()
    por_id = {e.pk: e for e in envios}

    try:
        dados = json.loads(bruto) if bruto.strip() else {}
    except json.JSONDecodeError:
        dados = {}

    resultados = dados.get("resultados") if isinstance(dados, dict) else None
    if isinstance(dados, list):
        resultados = dados

    falhas = 0
    if isinstance(resultados, list) and resultados:
        vistos = set()
        for item in resultados:
            if not isinstance(item, dict):
                continue
            envio = por_id.get(item.get("envioId"))
            if envio is None:
                continue
            vistos.add(envio.pk)
            deu_erro = bool(item.get("erro")) or item.get("status") in {
                "erro_envio",
                "bloqueado_seguranca",
                "telefone_invalido",
            }
            envio.situacao = SituacaoEnvio.ERRO if deu_erro else SituacaoEnvio.ENVIADO
            envio.erro = str(item.get("erro") or "")[:500]
            envio.resposta = item
            envio.enviado_em = agora
            falhas += 1 if deu_erro else 0
        for envio in envios:
            if envio.pk not in vistos:
                envio.situacao = SituacaoEnvio.ENVIADO
                envio.enviado_em = agora
    else:
        for envio in envios:
            envio.situacao = SituacaoEnvio.ENVIADO
            envio.enviado_em = agora

    EnvioPonto.objects.bulk_update(
        envios, ["situacao", "erro", "resposta", "enviado_em"], batch_size=200
    )
    return Resultado(enviados=len(envios) - falhas, falhas=falhas)


def fechar_lote(lote: LotePonto, resultado: Resultado) -> None:
    lote.situacao = (
        SituacaoLote.CONCLUIDO_COM_ERROS if resultado.falhas else SituacaoLote.CONCLUIDO
    )
    lote.concluido_em = timezone.now()
    lote.save(update_fields=["situacao", "concluido_em", "atualizado_em"])


def progresso(lote: LotePonto) -> dict:
    """O que a tela pergunta enquanto o lote roda — §26, por polling simples."""
    contagem = {
        chave: lote.envios.filter(situacao=chave).count() for chave, _ in SituacaoEnvio.choices
    }
    total = sum(contagem.values())
    concluidos = contagem[SituacaoEnvio.ENVIADO] + contagem[SituacaoEnvio.ERRO]
    return {
        "situacao": lote.situacao,
        "total": total,
        "enviados": contagem[SituacaoEnvio.ENVIADO],
        "falhas": contagem[SituacaoEnvio.ERRO],
        "restantes": max(total - concluidos, 0),
        "terminou": lote.situacao
        in (SituacaoLote.CONCLUIDO, SituacaoLote.CONCLUIDO_COM_ERROS, SituacaoLote.CANCELADO),
    }


__all__ = [
    "FalhaDeIntegracao",
    "FalhaDeSeguranca",
    "ModoEnvio",
    "Resultado",
    "despachar",
    "destinos_do_lote",
    "fechar_lote",
    "montar_payload",
    "preparar_envios",
    "progresso",
]
