"""Meu dia — o que exige esta pessoa hoje.

A pergunta que a tela responde é estreita de propósito: **o que exige você**, não
"o que aconteceu". Feed de atividade é outra coisa e mora na Central de
Notificações; misturar os dois produz uma lista onde o que precisa de ação some
no meio do que é só informação.

## Duas origens, uma lista

1. **Do Workspace** — aprovações esperando decisão, pedidos devolvidos que
   exigem correção, pedidos que passaram do prazo prometido.
2. **Dos domínios** — cada `WorkspaceProvider` registrado responde
   `pending_items(pessoa)`. É como um chamado atribuído no iConnect Platform
   aparece aqui sem que o Workspace saiba o que é um `Ticket`.

A segunda é o que separa este produto de um app launcher, e é a razão de o
contrato de provider existir desde a Etapa 3.

## Nenhum widget nasce vazio (ADR-012)

Cada bloco declara o que mostrar quando não tem dado: `None`. A view descarta os
vazios, e a tela não desenha moldura em volta de nada. Dez cartões zerados são
piores que um app launcher, porque o launcher ao menos funciona.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from workspace.providers import registry
from workspace.providers.base import PendingItemDTO
from workspace.services import aprovacao as apr
from workspace.services import catalogo as svc

logger = logging.getLogger(__name__)

# Acima disto a lista deixa de ser "o que exige você" e vira backlog. Quem tem 40
# pendências precisa da tela do domínio, não do resumo.
LIMITE_POR_BLOCO = 6


@dataclass(frozen=True)
class Bloco:
    """Um agrupamento de itens que exigem ação, com o seu destino."""

    chave: str
    titulo: str
    icone: str
    itens: list
    url: str = ""
    rotulo_url: str = ""
    urgente: bool = False
    total: int = 0
    resumo: str = ""

    @property
    def excedente(self) -> int:
        """Quantos ficaram fora do recorte."""
        return max(0, self.total - len(self.itens))


@dataclass(frozen=True)
class Item:
    """Uma linha de `Bloco`. Deliberadamente pobre — a tela não decide nada."""

    titulo: str
    subtitulo: str = ""
    url: str = ""
    etiqueta: str = ""
    dias: int | None = None
    campos: dict = field(default_factory=dict)


# ── Blocos do Workspace ─────────────────────────────────────────────


def _aprovacoes(pessoa, cache: dict | None = None) -> Bloco | None:
    resumo = apr.resumo_da_bandeja(pessoa, cache=cache)
    if not resumo["quantidade"]:
        return None

    from workspace.templatetags.wks import moeda

    itens = [
        Item(
            titulo=s.titulo,
            subtitulo=f"{s.solicitante.get_short_name() or s.solicitante.get_username()}"
            + (f" · R$ {moeda(s.valor)}" if s.valor else ""),
            url=reverse("workspace:aprovacoes"),
            dias=s.dias_esperando,
        )
        for s in resumo["solicitacoes"][:LIMITE_POR_BLOCO]
    ]
    represado = resumo["valor_represado"]
    return Bloco(
        chave="aprovacoes",
        titulo="Esperando sua decisão",
        icone="check",
        itens=itens,
        url=reverse("workspace:aprovacoes"),
        rotulo_url="Abrir a bandeja",
        # Urgente porque é o único bloco onde a inação bloqueia OUTRA pessoa.
        urgente=True,
        total=resumo["quantidade"],
        resumo=(f"R$ {moeda(represado)} represados" if represado else ""),
    )


def _devolvidas(pessoa) -> Bloco | None:
    """Pedidos devolvidos — exigem correção de quem pediu.

    Vem antes de "em andamento" na tela porque devolução é a única situação em
    que a bola está com o solicitante e ele pode não saber.
    """
    devolvidas = list(
        svc.minhas(pessoa).filter(situacao="devolvida")[: LIMITE_POR_BLOCO + 1]
    )
    if not devolvidas:
        return None

    itens = [
        Item(
            titulo=s.item.nome,
            subtitulo=s.motivo_devolucao or "Sem motivo registrado.",
            url=reverse("workspace:minhas_solicitacoes"),
            etiqueta="devolvido",
        )
        for s in devolvidas[:LIMITE_POR_BLOCO]
    ]
    return Bloco(
        chave="devolvidas",
        titulo="Precisam da sua correção",
        icone="devolver",
        itens=itens,
        url=reverse("workspace:minhas_solicitacoes"),
        rotulo_url="Ver minhas solicitações",
        urgente=True,
        total=len(devolvidas),
    )


def _atrasadas(pessoa) -> Bloco | None:
    """Pedidos que passaram do prazo prometido.

    Não é ação da pessoa — é munição. Sem isto, o prazo do catálogo é promessa
    que ninguém cobra, e prazo que ninguém cobra deixa de existir em três meses.
    """
    agora = timezone.now()
    atrasadas = []
    for s in svc.minhas(pessoa).filter(situacao__in=("aguardando_aprovacao", "em_atendimento")):
        limite = s.criado_em + timedelta(days=s.item.prazo_prometido_dias)
        if limite < agora:
            atrasadas.append((s, (agora - limite).days))

    if not atrasadas:
        return None

    itens = [
        Item(
            titulo=s.item.nome,
            subtitulo=f"prometido em {s.item.prazo_prometido_dias} dia(s)",
            url=reverse("workspace:minhas_solicitacoes"),
            etiqueta="atrasado",
            dias=dias,
        )
        for s, dias in atrasadas[:LIMITE_POR_BLOCO]
    ]
    return Bloco(
        chave="atrasadas",
        titulo="Passaram do prazo",
        icone="relogio",
        itens=itens,
        url=reverse("workspace:minhas_solicitacoes"),
        rotulo_url="Ver minhas solicitações",
        total=len(atrasadas),
    )


def _leituras(pessoa, cache: dict | None = None) -> Bloco | None:
    """Documentos com leitura obrigatória pendentes.

    Urgente porque é obrigação, e porque o valor do acervo está exatamente aqui:
    comunicado sem retorno é e-mail; documento com confirmação por versão é
    trilha de auditoria.
    """
    from workspace.services import conteudo as cnt

    pendentes = cnt.pendentes_de_leitura(pessoa, cache=cache)
    if not pendentes:
        return None

    itens = [
        Item(
            titulo=d.titulo,
            subtitulo=f"{d.get_tipo_display()} · v{d.versao}",
            url=reverse("workspace:documento", args=(d.slug,)),
            etiqueta="obrigatório",
        )
        for d in pendentes[:LIMITE_POR_BLOCO]
    ]
    return Bloco(
        chave="leituras",
        titulo="Leitura obrigatória",
        icone="book",
        itens=itens,
        url=reverse("workspace:documentacao"),
        rotulo_url="Ver a documentação",
        urgente=True,
        total=len(pendentes),
    )


def _documentos_a_vencer(pessoa) -> Bloco | None:
    """Só para quem é DONO de documento. Ninguém mais precisa ver isto.

    Documento normativo sem dono é documento que ninguém atualiza; o aviso de
    vencimento é o que transforma "tem dono" em "o dono age".
    """
    from workspace.services import conteudo as cnt

    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        return None

    vencidos = list(cnt.vencidos(dono=pessoa))
    a_vencer = list(cnt.a_vencer(dono=pessoa))
    tudo = vencidos + [d for d in a_vencer if d not in vencidos]
    if not tudo:
        return None

    itens = []
    for documento in tudo[:LIMITE_POR_BLOCO]:
        dias = documento.dias_para_vencer
        itens.append(
            Item(
                titulo=documento.titulo,
                subtitulo=(
                    "vencido" if documento.vencido else f"vence em {dias} dia(s)"
                ),
                url=reverse("workspace:documento", args=(documento.slug,)),
                etiqueta="vencido" if documento.vencido else "",
            )
        )
    return Bloco(
        chave="documentos_do_dono",
        titulo="Seus documentos precisam de revisão",
        icone="file",
        itens=itens,
        total=len(tudo),
        # Urgente só quando já venceu: POP vencido em vigor é risco de
        # conformidade, "vence em 28 dias" é planejamento.
        urgente=bool(vencidos),
    )


def _correspondencia(pessoa) -> Bloco | None:
    """O que chegou e espera retirada.

    Urgente quando há prazo legal: intimação parada é o caso que este módulo
    existe para evitar.
    """
    from workspace.models.correspondencia import Correspondencia

    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        return None

    esperando = list(
        Correspondencia.objects.de(pessoa).aguardando().select_related("unidade")
    )
    if not esperando:
        return None

    itens = [
        Item(
            titulo=c.get_tipo_display(),
            subtitulo=(
                f"de {c.remetente}" if c.remetente else "aguardando retirada"
            ) + (f" · {c.unidade}" if c.unidade_id else ""),
            url=reverse("workspace:correspondencias"),
            etiqueta="prazo legal" if c.urgente else "",
            dias=c.dias_esperando or None,
        )
        for c in esperando[:LIMITE_POR_BLOCO]
    ]
    return Bloco(
        chave="correspondencia",
        titulo="Correspondência para retirar",
        icone="jornal",
        itens=itens,
        url=reverse("workspace:correspondencias"),
        rotulo_url="Ver correspondências",
        urgente=any(c.urgente for c in esperando),
        total=len(esperando),
    )


def _reservas_de_hoje(pessoa) -> Bloco | None:
    """Reservas da pessoa que começam hoje.

    Não é urgente e não é pendência: é lembrete. Fica no fim dos blocos próprios,
    antes dos federados.
    """
    from workspace.services import reserva as res

    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        return None

    hoje = timezone.localdate()
    do_dia = [
        r
        for r in res.minhas(pessoa).confirmadas().futuras()
        if timezone.localtime(r.inicio).date() == hoje
    ]
    if not do_dia:
        return None

    do_dia.sort(key=lambda r: r.inicio)
    itens = [
        Item(
            titulo=r.recurso.nome,
            subtitulo=(
                f"{timezone.localtime(r.inicio):%H:%M}"
                f"–{timezone.localtime(r.fim):%H:%M}"
                + (f" · {r.motivo}" if r.motivo else "")
            ),
            url=reverse("workspace:minhas_reservas"),
            etiqueta="agora" if r.em_curso else "",
        )
        for r in do_dia[:LIMITE_POR_BLOCO]
    ]
    return Bloco(
        chave="reservas_hoje",
        titulo="Suas reservas de hoje",
        icone="pin",
        itens=itens,
        url=reverse("workspace:minhas_reservas"),
        rotulo_url="Ver minhas reservas",
        total=len(do_dia),
    )


# ── Blocos federados pelos domínios ─────────────────────────────────


def _dos_dominios(pessoa) -> list[Bloco]:
    """`pending_items()` de cada provider registrado.

    Um provider que estoura NÃO derruba a tela. O Workspace agrega domínios que
    ele não controla; se o iConnect estiver com problema, "meu dia" ainda mostra
    aprovação e pedido devolvido. Falha de agregador é degradação, não erro.
    """
    blocos: list[Bloco] = []
    for provider in registry.all():
        try:
            pendentes = list(provider.pending_items(pessoa))
        except Exception:  # noqa: BLE001 - degradação deliberada
            logger.warning(
                "provider %r falhou em pending_items; bloco omitido",
                getattr(provider, "key", provider),
                exc_info=True,
            )
            continue

        if not pendentes:
            continue

        pendentes.sort(key=lambda i: (-i.prioridade, i.prazo or timezone.now()))
        blocos.append(
            Bloco(
                chave=f"dominio:{provider.key}",
                titulo=provider.label or provider.key,
                icone=_icone_de(pendentes[0]),
                itens=[
                    Item(titulo=i.titulo, subtitulo=i.subtitulo, url=i.url)
                    for i in pendentes[:LIMITE_POR_BLOCO]
                ],
                total=len(pendentes),
            )
        )
    return blocos


def _icone_de(item: PendingItemDTO) -> str:
    return item.icone or "grid"


# ── Composição ──────────────────────────────────────────────────────


def para(pessoa, cache: dict | None = None) -> dict:
    """Tudo o que a tela precisa. Blocos vazios já vêm descartados.

    A ORDEM é a mensagem: primeiro o que bloqueia outra pessoa, depois o que
    bloqueia você, depois o que você deveria cobrar. Ordenar por data faria a
    aprovação de ontem aparecer abaixo do pedido atrasado de anteontem.
    """
    blocos = [
        _aprovacoes(pessoa, cache=cache),
        _leituras(pessoa, cache=cache),
        _correspondencia(pessoa),
        _devolvidas(pessoa),
        _atrasadas(pessoa),
        _documentos_a_vencer(pessoa),
        _reservas_de_hoje(pessoa),
        *_dos_dominios(pessoa),
    ]
    blocos = [b for b in blocos if b is not None]

    return {
        "blocos": blocos,
        "vazio": not blocos,
        "total": sum(b.total for b in blocos),
        "urgentes": sum(b.total for b in blocos if b.urgente),
    }
