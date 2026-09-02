"""Plano de ação com limiar — o que a exceção cobra, e como ela cobra de volta.

## O que a Onda 4 deixou faltando

O painel de exceções encontra os registros que violaram uma regra. Ele não tem
onde guardar a **resposta**: por que aconteceu, o que será feito, quem faz e até
quando. Sem isso, uma regra que dispara todo mês dispara todo mês para sempre, e
a lista vira um relatório que alguém aprende a rolar até o fim.

## Limiar gera obrigação

`RegraExcecao.exige_plano` marca as regras em que a ocorrência **deve** uma
resposta. Ocorrência dessas sem plano é uma **dívida** — palavra escolhida de
propósito: ela aparece na tela com esse nome, e não como "pendência", que é o
que se diz de coisa que talvez alguém faça.

## O desfecho é reverificado, e nunca declarado

Quando o prazo vence, `verificar()` roda **a mesma regra** e procura **a mesma
chave de ocorrência**. Se ela ainda está lá, o plano fecha como *não resolvido*
— mesmo que o responsável tenha escrito que resolveu.

Isso não é desconfiança do responsável: é o único jeito de o número da tela
significar alguma coisa. Um painel em que o próprio interessado declara o
sucesso mede quem preenche formulário.

E há um caso que precisa ser tratado à parte: **fonte fora do ar não é
sucesso**. Se a regra não pôde ser avaliada, a verificação fica registrada como
não avaliada e o plano **continua aberto**. Sem isso, um conector caído fecharia
como resolvido todo plano que dependesse dele — um mês inteiro de metas batidas
por causa de uma credencial vencida.

## Quem lê e quem responde

Ler não ganha permissão nova: **quem vê a regra vê os planos dela**. É a
resposta que a Onda 4 já deu, e uma segunda regra de visibilidade para a mesma
lista divergiria da primeira.

Responder — abrir, editar, fechar — exige `pla.responder` **e** o papel da
regra. Assinar o que a empresa vai fazer sobre um contrato deficitário é ato de
quem responde por ele.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from identidade.services.autorizacao import ESCOPO_GLOBAL, escopo_de, pode
from workspace import excecoes as reg
from workspace.models.excecao import RegraExcecao
from workspace.models.plano import (
    PRAZO_PADRAO_DO_PLANO,
    PlanoAcao,
    SituacaoPlano,
    VerificacaoPlano,
)
from workspace.services import excecoes as exc

PERMISSAO_RESPONDER = "pla.responder"

#: Quantos planos a tela lista por estado. Um contrato-a-contrato de uma
#: carteira grande encheria a página com o que ninguém lê — e o que importa numa
#: lista de planos é o que está fora do prazo, que vem primeiro.
POR_ESTADO = 100

#: Quantos dias DEPOIS do prazo o comando ainda tenta reverificar antes de
#: desistir e fechar pelo que encontrar. Existe porque o cron pode ter ficado
#: fora do ar: fechar um plano no primeiro dia em que a máquina voltou, com a
#: fonte ainda subindo, produziria um desfecho aleatório.
CARENCIA_DE_VERIFICACAO = 2


class PlanoError(Exception):
    """A ação pedida não pode acontecer, e a mensagem diz por quê."""


class SemPlanos(Exception):
    """Esta pessoa não responde por regra nenhuma com limiar."""


# ── Permissão ───────────────────────────────────────────────────────


def regras_com_limiar(pessoa=None, cache: dict | None = None) -> list[RegraExcecao]:
    """As regras ATIVAS que geram obrigação — recortadas por quem pergunta.

    Sem `pessoa`, devolve todas: é o que o comando de verificação usa, e ele não
    tem sessão. Com pessoa, passa pelo mesmo recorte do painel de exceções.
    """
    if pessoa is None:
        return list(RegraExcecao.objects.ativas().filter(exige_plano=True))
    try:
        visiveis = exc.regras_de(pessoa, cache=cache)
    except exc.SemExcecoes:
        return []
    # Filtra em PYTHON sobre a lista que o painel de exceções já recortou, em vez
    # de repetir a consulta com `exige_plano=True`. O trilho chama isto em toda
    # requisição, e uma consulta a mais por página é o tipo de custo que se
    # acumula sem ninguém notar — foi um teste de contagem de queries que cobrou.
    return [r for r in visiveis if r.exige_plano]


def pode_ler(pessoa, cache: dict | None = None) -> bool:
    """Quem vê alguma regra com limiar vê a tela de planos.

    Sem permissão nova: uma segunda regra de visibilidade para a mesma lista
    divergiria da primeira, e a divergência apareceria como "sumiu um plano".
    """
    return bool(regras_com_limiar(pessoa, cache=cache))


def pode_responder(regra: RegraExcecao, pessoa, cache: dict | None = None) -> bool:
    """Abrir, editar e fechar planos desta regra."""
    if not pode(pessoa, PERMISSAO_RESPONDER, cache=cache):
        return False
    if escopo_de(pessoa, PERMISSAO_RESPONDER, cache=cache) == ESCOPO_GLOBAL:
        return True
    if not regra.escopo_papel:
        # Regra sem papel é de todo mundo que abre o painel — são as que vigiam
        # o mecanismo. Responder por elas exige o escopo global: um plano sobre
        # "fonte atrasada" é da operação de dados, e não de quem passou pela
        # tela.
        return False
    return regra.escopo_papel in exc.papeis_de(pessoa, cache=cache)


def titulares_da_regra(regra: RegraExcecao) -> list:
    """Quem pode ser responsável por um plano desta regra.

    Os titulares do papel que a atende, e não a empresa inteira: o responsável
    por um plano de margem é quem responde por margem, e um `select` com todo
    mundo faz a escolha cair em quem estiver mais perto no alfabeto.

    Lista vazia é resposta legítima — papel sem ocupante é um achado, e a tela
    diz isso em vez de oferecer uma caixa em branco.
    """
    return reg.titulares(regra.escopo_papel)


def regra_visivel(chave: str, pessoa, cache: dict | None = None) -> RegraExcecao | None:
    """A regra com limiar de chave `chave`, se esta pessoa a vê."""
    for regra in regras_com_limiar(pessoa, cache=cache):
        if regra.chave == chave:
            return regra
    return None


# ── A dívida ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Divida:
    """Uma ocorrência que DEVE um plano e não tem."""

    regra: RegraExcecao
    ocorrencia: object
    #: Se QUEM ESTÁ OLHANDO pode responder por ela. Resolvido aqui e não no
    #: template: um `{% if %}` precisaria indexar um dicionário por variável, o
    #: que a linguagem de template não faz sem um filtro — e um filtro para
    #: isso viraria o jeito de esconder permissão dentro de HTML.
    pode_responder: bool = False

    @property
    def chave(self) -> str:
        return self.ocorrencia.chave


def dividas_de(pessoa, cache: dict | None = None) -> list[Divida]:
    """Ocorrências de regras com limiar que ainda não têm plano aberto.

    Chamada "dívida" na tela de propósito. "Pendência" é o que se diz de coisa
    que talvez alguém faça; aqui a obrigação já existe, e o que falta é a
    resposta.
    """
    dividas: list[Divida] = []
    for regra in regras_com_limiar(pessoa, cache=cache):
        responde = pode_responder(regra, pessoa, cache=cache)
        avaliacao = exc.avaliar(regra)
        if not avaliacao.avaliada:
            # Regra não avaliada não gera dívida. Cobrar plano por uma ocorrência
            # que ninguém conseguiu verificar seria cobrar do responsável a queda
            # de um conector.
            continue
        respondidas = set(
            PlanoAcao.objects.abertos()
            .filter(regra_chave=regra.chave)
            .values_list("ocorrencia_chave", flat=True)
        )
        dividas += [
            Divida(regra=regra, ocorrencia=o, pode_responder=responde)
            for o in avaliacao.ocorrencias
            if o.chave not in respondidas
        ]
    return dividas


# ── Abrir e fechar ──────────────────────────────────────────────────


def prazo_de(regra: RegraExcecao, a_partir_de: date | None = None) -> date:
    dias = regra.prazo_do_plano or PRAZO_PADRAO_DO_PLANO
    return (a_partir_de or timezone.localdate()) + timedelta(days=dias)


def ocorrencia_de(regra: RegraExcecao, chave: str):
    """A ocorrência de chave `chave`, se a regra ainda a encontra.

    `None` quando a regra parou de disparar por ela — e aí abrir um plano seria
    registrar uma obrigação sobre um problema que já não existe.
    """
    avaliacao = exc.avaliar(regra)
    if not avaliacao.avaliada:
        return None
    return next((o for o in avaliacao.ocorrencias if o.chave == chave), None)


@transaction.atomic
def abrir(
    regra: RegraExcecao,
    chave: str,
    pessoa,
    justificativa: str,
    acao: str,
    responsavel,
    prazo: date | None = None,
    cache: dict | None = None,
) -> PlanoAcao:
    """Registra a resposta a uma ocorrência."""
    if not pode_responder(regra, pessoa, cache=cache):
        raise PlanoError("Responder por esta regra exige o papel que a atende.")
    if not regra.exige_plano:
        # Plano em regra que não gera obrigação viraria uma segunda lista de
        # tarefas, ao lado do catálogo de serviços — que já existe e é onde
        # trabalho pedido mora.
        raise PlanoError("Esta regra não exige plano de ação.")

    justificativa = (justificativa or "").strip()
    acao = (acao or "").strip()
    if not justificativa:
        raise PlanoError("O plano precisa da justificativa: por que aconteceu.")
    if not acao:
        # As duas metades da exigência do benchmark. Ação sem justificativa é
        # tarefa sem diagnóstico, e a próxima vez que a regra disparar ninguém
        # saberá se é a mesma causa.
        raise PlanoError("O plano precisa da ação: o que será feito.")
    if responsavel is None:
        raise PlanoError("O plano precisa de um responsável.")

    ocorrencia = ocorrencia_de(regra, chave)
    if ocorrencia is None:
        raise PlanoError(
            "A regra não encontra mais esta ocorrência. Nada a planejar."
        )
    if PlanoAcao.objects.abertos().filter(
        regra_chave=regra.chave, ocorrencia_chave=chave
    ).exists():
        raise PlanoError("Já existe um plano aberto para esta ocorrência.")

    prazo = prazo or prazo_de(regra)
    if prazo <= timezone.localdate():
        # Prazo no passado fecharia o plano na primeira verificação, antes de
        # alguém ter tido um dia para agir.
        raise PlanoError("O prazo precisa ser uma data futura.")

    return PlanoAcao.objects.create(
        regra_chave=regra.chave,
        ocorrencia_chave=chave,
        titulo=ocorrencia.titulo[:200],
        detalhe=ocorrencia.detalhe[:300],
        justificativa=justificativa,
        acao=acao,
        responsavel=responsavel,
        prazo=prazo,
        aberto_por=pessoa,
    )


@transaction.atomic
def fechar(plano: PlanoAcao, pessoa, desfecho: str = "", cache: dict | None = None):
    """Fecha o plano — e o desfecho vem da REGRA, não de quem fecha.

    Quem fecha escreve o que aconteceu; quem decide se resolveu é a regra,
    rodando de novo sobre a mesma chave. Se ela ainda encontra a ocorrência, o
    plano fecha como *não resolvido*, e o texto de quem fechou fica junto.

    É o que impede a tela de medir preenchimento de formulário.
    """
    regra = RegraExcecao.objects.filter(chave=plano.regra_chave).first()
    if regra is None:
        raise PlanoError("A regra deste plano não está mais no catálogo.")
    if not pode_responder(regra, pessoa, cache=cache):
        raise PlanoError("Fechar este plano exige o papel que atende a regra.")
    if not plano.aberto:
        return plano

    verificacao = verificar(plano, regra=regra)
    if not verificacao.avaliada:
        # Fonte fora do ar. O plano continua aberto — fechá-lo agora fecharia
        # pelo que ninguém conseguiu conferir.
        raise PlanoError(
            f"A fonte de {regra.titulo.lower()} não está disponível — o "
            "desfecho não pôde ser conferido. O plano continua aberto."
        )

    plano.situacao = (
        SituacaoPlano.NAO_RESOLVIDO if verificacao.ainda_ocorre
        else SituacaoPlano.RESOLVIDO
    )
    plano.desfecho = (desfecho or "").strip()[:300] or verificacao.observacao
    plano.fechado_em = timezone.now()
    plano.save(update_fields=["situacao", "desfecho", "fechado_em"])
    return plano


def verificar(plano: PlanoAcao, regra: RegraExcecao | None = None) -> VerificacaoPlano:
    """Roda a regra de novo e registra o que ela respondeu. NUNCA levanta.

    Uma regra que estoura não pode derrubar a verificação das outras — é a mesma
    garantia de `excecoes.avaliar()`, e pelo mesmo motivo: o comando roda no
    cron, sem ninguém olhando.
    """
    regra = regra or RegraExcecao.objects.filter(chave=plano.regra_chave).first()
    if regra is None:
        return VerificacaoPlano.objects.create(
            plano=plano,
            ainda_ocorre=True,
            avaliada=False,
            observacao="A regra não está mais no catálogo.",
        )

    avaliador = reg.regra_de(regra.chave)
    if avaliador is None or not avaliador.disponivel():
        return VerificacaoPlano.objects.create(
            plano=plano,
            ainda_ocorre=True,
            avaliada=False,
            observacao=(
                f"A fonte {regra.fonte_requerida or 'da regra'} não estava "
                "disponível na verificação."
            ),
        )

    try:
        chaves = {o.chave for o in avaliador.avaliar(regra.janela)}
    except Exception as erro:  # noqa: BLE001 - ver o docstring
        return VerificacaoPlano.objects.create(
            plano=plano,
            ainda_ocorre=True,
            avaliada=False,
            observacao=f"A regra falhou ao ser avaliada: {type(erro).__name__}.",
        )

    ainda = plano.ocorrencia_chave in chaves
    return VerificacaoPlano.objects.create(
        plano=plano,
        ainda_ocorre=ainda,
        observacao=(
            "A regra ainda encontra esta ocorrência."
            if ainda
            else "A regra não encontra mais esta ocorrência."
        ),
    )


def vencidos_para_verificar(ate: date | None = None) -> list[PlanoAcao]:
    """Planos abertos cujo prazo já passou da carência."""
    limite = (ate or timezone.localdate()) - timedelta(days=CARENCIA_DE_VERIFICACAO)
    return list(PlanoAcao.objects.abertos().filter(prazo__lt=limite))


@transaction.atomic
def concluir_pelo_prazo(plano: PlanoAcao) -> PlanoAcao:
    """O fechamento automático do vencimento. Sem pessoa, e sem opinião.

    Fonte fora do ar NÃO fecha: a verificação fica registrada como não avaliada,
    e o plano espera a próxima rodada. Sem isso, um conector caído fecharia como
    resolvido todo plano que dependesse dele.
    """
    verificacao = verificar(plano)
    if not verificacao.avaliada:
        return plano

    plano.situacao = (
        SituacaoPlano.NAO_RESOLVIDO if verificacao.ainda_ocorre
        else SituacaoPlano.RESOLVIDO
    )
    plano.desfecho = f"Conferido no vencimento: {verificacao.observacao}"[:300]
    plano.fechado_em = timezone.now()
    plano.save(update_fields=["situacao", "desfecho", "fechado_em"])
    return plano


# ── O que a tela recebe ─────────────────────────────────────────────


@dataclass
class Painel:
    no_prazo: list = field(default_factory=list)
    fora_do_prazo: list = field(default_factory=list)
    resolvidos: list = field(default_factory=list)
    nao_resolvidos: list = field(default_factory=list)
    dividas: list = field(default_factory=list)


def planos_visiveis(pessoa, cache: dict | None = None):
    chaves = [r.chave for r in regras_com_limiar(pessoa, cache=cache)]
    return PlanoAcao.objects.filter(regra_chave__in=chaves).select_related(
        "responsavel", "aberto_por"
    )


def painel(pessoa, cache: dict | None = None) -> dict:
    """Os quatro estados do benchmark, mais a dívida. Levanta `SemPlanos`."""
    regras = regras_com_limiar(pessoa, cache=cache)
    if not regras:
        # 403, e não uma tela de zeros. Quem não responde por regra nenhuma com
        # limiar não tem plano para ver, e uma lista vazia diria que a empresa
        # não cobra nada.
        raise SemPlanos("Você não responde por nenhuma regra que exige plano.")

    todos = planos_visiveis(pessoa, cache=cache)
    hoje = timezone.localdate()
    abertos = [p for p in todos if p.aberto]

    fora = [p for p in abertos if p.prazo < hoje][:POR_ESTADO]
    dentro = [p for p in abertos if p.prazo >= hoje][:POR_ESTADO]
    resolvidos = [p for p in todos if p.situacao == SituacaoPlano.RESOLVIDO][:POR_ESTADO]
    nao = [p for p in todos if p.situacao == SituacaoPlano.NAO_RESOLVIDO][:POR_ESTADO]

    dividas = dividas_de(pessoa, cache=cache)
    return {
        "regras": regras,
        # Fora do prazo PRIMEIRO. A ordem da tela é a ordem de agir, como no
        # trilho: o que venceu vale mais que o que está por vencer.
        "fora_do_prazo": fora,
        "no_prazo": dentro,
        "resolvidos": resolvidos,
        "nao_resolvidos": nao,
        "dividas": dividas,
        "total_aberto": len(abertos),
        # A efetividade, que é o que o painel de Tratativas do benchmark mede.
        # `None` sem nenhum plano fechado: uma porcentagem sobre zero seria 0%,
        # e 0% de efetividade é uma afirmação sobre um trabalho que não houve.
        "efetividade": _efetividade(resolvidos, nao),
        "pode_responder": {
            r.chave: pode_responder(r, pessoa, cache=cache) for r in regras
        },
    }



def _efetividade(resolvidos, nao_resolvidos) -> int | None:
    fechados = len(resolvidos) + len(nao_resolvidos)
    if not fechados:
        return None
    return round(len(resolvidos) * 100 / fechados)
