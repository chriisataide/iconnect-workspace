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


# ── O radar externo: editais do PNCP ────────────────────────────────


#: Quantos editais a tela mostra de uma vez.
#:
#: Havia um `limite=40` aqui que cortava em silêncio, e ele nasceu quando o
#: espelho tinha dois registros. A primeira carga real trouxe 466 editais
#: abertos — e um corte silencioso de 466 para 40 é pior que não ter lista: a
#: pessoa lê os quarenta, conclui que viu tudo, e os outros 426 não existem para
#: ela. O corte continua (rolar 466 linhas não é ler), mas agora ele APARECE, e
#: o caminho para estreitar é o filtro.
TETO_DA_LISTA = 60


class RadarDeEditais:
    """O bloco de editais inteiro: as linhas, o total e as opções do filtro."""

    def __init__(self, editais, total, no_espelho, ufs, termos, filtros):
        self.editais = editais
        self.total = total
        #: Quantos editais abertos existem, ANTES do filtro. É o que separa as
        #: duas mensagens de vazio — "a carga não rodou" pede olhar a tela 99,
        #: "o filtro não achou" pede afrouxar o filtro. Uma frase só para as
        #: duas mandaria a pessoa conferir a fonte quando o problema era ela ter
        #: escolhido "RR" e "cftv" juntos.
        self.no_espelho = no_espelho
        self.ufs = ufs
        self.termos = termos
        self.filtros = filtros

    def __bool__(self) -> bool:
        return bool(self.editais)

    @property
    def cortada(self) -> bool:
        return self.total > len(self.editais)

    @property
    def filtrando(self) -> bool:
        return any(self.filtros.values())


def editais_publicos(uf: str = "", termo: str = "", busca: str = "") -> RadarDeEditais:
    """Os editais espelhados do PNCP, do que encerra antes para o que vem depois.

    Lista SEPARADA das oportunidades, e não misturada com elas — a razão é a
    mesma que pôs os editais no espelho em vez de em `Oportunidade`:

      - uma `Oportunidade` é registro NOSSO: alguém cadastrou, alguém decidiu, e
        o motivo do descarte fica guardado;
      - um edital é registro do GOVERNO: ele muda por conta dele e some quando a
        proposta encerra.

    Misturá-los numa lista só faria a próxima carga sobrescrever o texto que
    alguém escreveu à mão — que é a única coisa que o radar guarda de verdade.

    ## Por que o filtro é aplicado AQUI, e não no provedor

    `ProvedorEditais.editais()` continua sem parâmetro de UF ou de termo. Pôr
    filtro de tela no contrato faria o `workspace` ditar como a fonte consulta —
    e a fonte pode ser o espelho local hoje e outra coisa amanhã. São algumas
    centenas de objetos em memória; o custo é um laço, e o que se compra com ele
    é a fronteira intacta.

    ## As opções do filtro saem do que EXISTE no espelho

    Oferecer as 27 UFs quando a carga trouxe 16 produz um filtro que devolve
    vazio e parece quebrado. A lista de UFs e de termos é a do espelho, sempre —
    e ela encolhe e cresce junto com a carga.

    Sem provedor registrado devolve um radar vazio, e a tela diz que a fonte não
    está no ar. Não levanta: o radar tem vida própria sem o PNCP, e derrubá-lo
    porque uma fonte externa não respondeu seria trocar uma faixa vazia por uma
    tela de erro.
    """
    from workspace.providers import resultados as contrato

    filtros = {
        "uf": (uf or "").strip().upper()[:2],
        "termo": (termo or "").strip().lower()[:80],
        "busca": (busca or "").strip()[:120],
    }

    provedor = contrato.obter(contrato.ProvedorEditais)
    if provedor is None:
        return RadarDeEditais([], 0, 0, [], [], filtros)

    todos = list(provedor.editais())
    # As opções saem de TODOS, e não do resultado filtrado: senão escolher "BA"
    # apagaria as outras UFs da caixa e não haveria como voltar.
    ufs = sorted({e.uf for e in todos if e.uf})
    termos = sorted({e.termo_casado for e in todos if e.termo_casado})

    casaram = [e for e in todos if _casa(e, filtros)]
    return RadarDeEditais(
        casaram[:TETO_DA_LISTA], len(casaram), len(todos), ufs, termos, filtros
    )


def _casa(edital, filtros: dict) -> bool:
    """Os três filtros são um E, e a busca varre objeto E órgão.

    Varrer os dois porque as duas perguntas aparecem: "o que compram de CFTV" é
    sobre o objeto, e "o que a Petrobras abriu" é sobre o órgão. Uma caixa só
    para as duas evita o erro de digitar o órgão no campo do objeto e concluir
    que não há nada.
    """
    if filtros["uf"] and edital.uf != filtros["uf"]:
        return False
    if filtros["termo"] and edital.termo_casado != filtros["termo"]:
        return False
    if filtros["busca"]:
        # `indice.normalizar` e não `.lower()`: é o mesmo "ferias encontra
        # férias" que a busca do portal já faz, e escrever um segundo
        # normalizador aqui garantiria que os dois divergissem.
        from workspace.services.indice import normalizar

        alvo = normalizar(
            f"{edital.objeto} {edital.orgao} {edital.unidade} {edital.municipio}"
        )
        if normalizar(filtros["busca"]) not in alvo:
            return False
    return True


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
