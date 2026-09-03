"""Metas, avaliação e PDI — o quadro de uma pessoa, e como ele vira nota.

## Três regras, e elas são o produto

1. **A fórmula está na tela.** `Fator 1 ÷ Fator 2`, com os fatores apontando
   para o espelho pelo catálogo de `services/fatores.py`. A meta é auditável
   porque a conta é pública.
2. **Quadro aprovado não muda mais.** Mover a trave no meio do ciclo é o defeito
   que a palavra "meta" existe para impedir. Reabrir continua possível — é um
   ato, com autor, motivo e registro.
3. **Fator sem amostra não vira zero.** A meta fica não apurada, com o motivo, e
   **fora do denominador da nota**. Contá-la como zero transformaria uma fonte
   fora do ar na nota de uma pessoa.

## Quem vê o quê

`met.ler.proprio` está no autoatendimento: **todo mundo vê o próprio quadro**. É
a diferença entre um sistema de metas e um sistema de avaliação secreta.

`met.ler.equipe` alcança os liderados — pelo organograma, com `pode()` fazendo o
trabalho, e não por uma segunda regra escrita aqui. `met.ler.global` é o R.H.

## O que esta tela NUNCA faz

Grade de pessoas com nota ao lado, e exportação de qualquer coisa. Restrição 8,
e ela vale aqui mais que em qualquer outra tela: o painel do R.H. mostra
**contagem por situação**, nunca uma lista de nomes com números. Uma planilha de
"quem tirou quanto" circulando por e-mail é o pior desfecho possível desta onda.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.utils import timezone

from identidade.services.autorizacao import (
    ESCOPO_EQUIPE,
    ESCOPO_GLOBAL,
    escopo_de as escopo_da_permissao,
    liderados_recursivos,
    pode,
)
from workspace.models.meta import (
    AcaoDesenvolvimento,
    CicloMetas,
    Meta,
    PlanoDesenvolvimento,
    QuadroMetas,
    SituacaoCiclo,
    SituacaoQuadro,
    TipoCalculo,
)
from workspace.providers import resultados as contrato
from workspace.services import fatores as cat

PERMISSAO = "met.ler"
PERMISSAO_DEFINIR = "met.definir"
PERMISSAO_APROVAR = "met.aprovar"

#: Teto de atingimento gravado. O benchmark descreve "lógica de pontuação
#: ilimitada", e ela existe — mas 400% numa meta de peso 3 dilui todas as outras
#: e transforma o quadro num jogo de escolher a meta fácil. O teto é alto o
#: bastante para premiar superação e baixo o bastante para não apagar o resto.
TETO_DE_ATINGIMENTO = Decimal("150")

#: Quantas metas cabem num quadro. Quinze metas não são um foco: são uma lista
#: de tarefas com peso.
MAXIMO_DE_METAS = 12


class SemMetas(Exception):
    """Esta pessoa não tem quadro nenhum para ver."""


class MetaError(Exception):
    """A ação pedida não pode acontecer, e a mensagem diz por quê."""


# ── Permissão ───────────────────────────────────────────────────────


def _alcanca(pessoa, permissao: str, alvo, cache: dict | None = None) -> bool:
    """`pode()` com alvo. É ele que traduz `.proprio`, `.equipe` e `.global`.

    Uma segunda regra de alcance escrita aqui divergiria do organograma na
    primeira mudança de gestor — e a divergência apareceria como "sumiu o quadro
    do meu liderado".
    """
    return pode(pessoa, permissao, alvo=alvo, cache=cache)


def pode_ver(quadro: QuadroMetas, pessoa, cache: dict | None = None) -> bool:
    return _alcanca(pessoa, PERMISSAO, quadro.pessoa, cache=cache)


def pode_definir(quadro: QuadroMetas, pessoa, cache: dict | None = None) -> bool:
    """Escrever a meta. Só em rascunho — o resto é o ADR-035."""
    return quadro.editavel and _alcanca(
        pessoa, PERMISSAO_DEFINIR, quadro.pessoa, cache=cache
    )


def pode_aprovar(quadro: QuadroMetas, pessoa, cache: dict | None = None) -> bool:
    """Homologar. SEPARADA de definir, e é a separação que faz o degrau existir.

    Quem escreve a própria meta não a homologa: `met.aprovar.proprio` não é
    concedido a papel nenhum, e o `alvo` aqui é a pessoa do quadro — o gestor
    alcança pelo `.equipe`, e a própria pessoa não se alcança.
    """
    if quadro.pessoa_id == getattr(pessoa, "pk", None):
        if escopo_da_permissao(pessoa, PERMISSAO_APROVAR, cache=cache) != ESCOPO_GLOBAL:
            return False
    return _alcanca(pessoa, PERMISSAO_APROVAR, quadro.pessoa, cache=cache)


def quadros_visiveis(pessoa, ciclo: CicloMetas | None = None, cache=None):
    """Os quadros que esta pessoa alcança, pelo escopo da permissão."""
    if not pode(pessoa, PERMISSAO, cache=cache):
        raise SemMetas("Metas são de quem tem quadro.")

    base = QuadroMetas.objects.select_related("ciclo", "pessoa", "aprovado_por")
    if ciclo is not None:
        base = base.filter(ciclo=ciclo)

    escopo = escopo_da_permissao(pessoa, PERMISSAO, cache=cache)
    if escopo == ESCOPO_GLOBAL:
        return base
    if escopo == ESCOPO_EQUIPE:
        alcance = liderados_recursivos(pessoa.pk, cache=cache) | {pessoa.pk}
        return base.filter(pessoa_id__in=alcance)
    return base.filter(pessoa=pessoa)


def ciclo_corrente() -> CicloMetas | None:
    """O ciclo que a tela abre por padrão.

    O ABERTO ou EM CURSO mais recente; na falta dos dois, o último fechado. Uma
    tela em branco em janeiro, entre um ciclo e o seguinte, faria a pessoa achar
    que perdeu o histórico.
    """
    corrente = (
        CicloMetas.objects.exclude(situacao=SituacaoCiclo.FECHADO)
        .order_by("-inicio")
        .first()
    )
    return corrente or CicloMetas.objects.order_by("-inicio").first()


def quadro_de(pessoa_alvo, ciclo: CicloMetas) -> QuadroMetas | None:
    return (
        QuadroMetas.objects.filter(pessoa=pessoa_alvo, ciclo=ciclo)
        .select_related("ciclo", "pessoa", "aprovado_por")
        .first()
    )


# ── Escrever ────────────────────────────────────────────────────────


@transaction.atomic
def abrir_quadro(pessoa_alvo, ciclo: CicloMetas, quem, cache=None) -> QuadroMetas:
    """Cria o quadro em rascunho. Idempotente."""
    existente = quadro_de(pessoa_alvo, ciclo)
    if existente is not None:
        return existente
    if ciclo.situacao == SituacaoCiclo.FECHADO:
        # Abrir quadro em ciclo fechado produziria uma meta que nasce sem prazo
        # de fazer nada — e ela entraria na contagem do R.H. como rascunho
        # pendente para sempre.
        raise MetaError("Este ciclo está fechado.")
    if not _alcanca(quem, PERMISSAO_DEFINIR, pessoa_alvo, cache=cache):
        raise MetaError("Definir metas de alguém exige liderar essa pessoa.")
    return QuadroMetas.objects.create(pessoa=pessoa_alvo, ciclo=ciclo)


def _decimal(valor, campo: str) -> Decimal | None:
    if valor in (None, ""):
        return None
    try:
        return Decimal(str(valor).replace(",", "."))
    except (InvalidOperation, ValueError):
        raise MetaError(f"{campo}: valor numérico inválido.")


@transaction.atomic
def salvar_meta(
    quadro: QuadroMetas,
    quem,
    meta: Meta | None,
    descricao: str,
    fator_1: str,
    fator_2: str = "",
    grupo: str = "",
    peso=1,
    alvo=None,
    tipo_calculo: str = TipoCalculo.DIRETO,
    detalhamento: str = "",
    cache=None,
) -> Meta:
    """Cria ou atualiza uma meta. Uma função para os dois, como na redação.

    Duas divergiriam na terceira semana, e a validação que existe só numa delas é
    a porta por onde entra a meta sem fator.
    """
    if not pode_definir(quadro, quem, cache=cache):
        if not quadro.editavel:
            # A mensagem diz QUAL das duas coisas faltou. "Sem permissão" para
            # quem tem permissão e esbarrou no ADR-035 manda a pessoa pedir
            # acesso que ela já tem.
            raise MetaError(
                "Este quadro já foi aprovado. Para mudar uma meta, reabra o "
                "quadro — o motivo fica registrado."
            )
        raise MetaError("Definir metas de alguém exige liderar essa pessoa.")

    descricao = (descricao or "").strip()
    if not descricao:
        raise MetaError("A meta precisa de uma descrição.")

    if cat.de(fator_1) is None:
        # Fator fora do catálogo é meta que nunca poderá ser apurada — e a
        # descoberta aconteceria no fim do ciclo, quando já não dá para trocar.
        raise MetaError(f"Fator desconhecido: {fator_1!r}.")
    if fator_2 and cat.de(fator_2) is None:
        raise MetaError(f"Fator desconhecido: {fator_2!r}.")

    try:
        peso = int(peso)
    except (TypeError, ValueError):
        raise MetaError("O peso precisa ser um número inteiro.")
    if peso < 1:
        raise MetaError("O peso precisa ser pelo menos 1.")

    alvo = _decimal(alvo, "Alvo")
    if not fator_2 and alvo is None:
        # Sem `fator_2` a meta é sobre o valor absoluto do `fator_1`, e sem alvo
        # ela não tem contra o que ser comparada. Aceitar produziria uma meta que
        # apura para sempre como "não apurada".
        raise MetaError("Meta de valor absoluto precisa de um alvo.")

    if meta is None:
        if quadro.metas.count() >= MAXIMO_DE_METAS:
            raise MetaError(
                f"Um quadro cabe {MAXIMO_DE_METAS} metas. Mais que isso não é "
                "foco: é uma lista de tarefas com peso."
            )
        meta = Meta(quadro=quadro)
    elif meta.quadro_id != quadro.pk:
        # `pk` de meta de OUTRO quadro — o IDOR pela porta do formulário.
        raise MetaError("Esta meta não é deste quadro.")

    meta.descricao = descricao[:200]
    meta.fator_1 = fator_1
    meta.fator_2 = fator_2
    meta.grupo = grupo or meta.grupo
    meta.peso = peso
    meta.alvo = alvo
    meta.tipo_calculo = tipo_calculo
    meta.detalhamento = detalhamento or ""
    meta.save()
    return meta


def remover_meta(meta: Meta, quem, cache=None) -> None:
    if not pode_definir(meta.quadro, quem, cache=cache):
        raise MetaError(
            "Metas de um quadro aprovado não se apagam. Reabra o quadro."
        )
    meta.delete()


# ── Aprovar, reabrir ────────────────────────────────────────────────


@transaction.atomic
def aprovar(quadro: QuadroMetas, quem, cache=None) -> QuadroMetas:
    """Homologa o quadro. Daqui em diante ele não muda — ADR-035."""
    if not pode_aprovar(quadro, quem, cache=cache):
        raise MetaError("Aprovar o quadro é de quem lidera a pessoa.")
    if quadro.situacao != SituacaoQuadro.RASCUNHO:
        return quadro
    if not quadro.metas.exists():
        # Quadro vazio aprovado é a forma mais silenciosa de não ter metas: ele
        # conta como aprovado no painel do R.H. e não cobra nada de ninguém.
        raise MetaError("Um quadro sem meta nenhuma não pode ser aprovado.")

    quadro.situacao = SituacaoQuadro.APROVADO
    quadro.aprovado_por = quem
    quadro.aprovado_em = timezone.now()
    quadro.save(update_fields=["situacao", "aprovado_por", "aprovado_em"])
    return quadro


@transaction.atomic
def reabrir(quadro: QuadroMetas, quem, motivo: str, cache=None) -> QuadroMetas:
    """Devolve o quadro ao rascunho — e o registro fica.

    Reabrir é legítimo: um alvo pode ter sido escrito errado, e uma
    reestruturação pode mudar o que a pessoa responde. O que não pode é
    acontecer em silêncio. Um quadro reaberto três vezes num ciclo é um achado
    sobre como as metas foram definidas.
    """
    if not pode_aprovar(quadro, quem, cache=cache):
        raise MetaError("Reabrir o quadro é de quem o aprovou.")
    motivo = (motivo or "").strip()
    if not motivo:
        raise MetaError("Reabrir exige o motivo. Ele fica no registro do quadro.")
    if quadro.situacao == SituacaoQuadro.APURADO:
        # Quadro apurado tem nota, e a nota foi para o comitê. Reabrir aqui
        # permitiria reescrever a meta depois de saber o resultado dela.
        raise MetaError("Quadro apurado não reabre. A nota já é registro.")

    quadro.reaberturas = list(quadro.reaberturas or []) + [
        {
            "quando": timezone.now().isoformat(timespec="minutes"),
            "quem": getattr(quem, "nome", "") or str(quem),
            "motivo": motivo[:300],
        }
    ]
    quadro.situacao = SituacaoQuadro.RASCUNHO
    quadro.aprovado_por = None
    quadro.aprovado_em = None
    quadro.save(
        update_fields=["situacao", "aprovado_por", "aprovado_em", "reaberturas"]
    )
    return quadro


# ── Apurar ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Leitura:
    """O que os fatores responderam para uma meta, agora."""

    realizado: Decimal | None = None
    atingimento: Decimal | None = None
    motivo: str = ""
    carimbo: str = ""


def escopo_da_pessoa(pessoa_alvo) -> contrato.Escopo:
    """O recorte que os fatores consultam: o centro de custo da pessoa.

    Escopo da PESSOA do quadro, e não de quem está olhando: a meta é sobre a
    operação dela. Sem lotação, `Escopo()` vazio seria a empresa inteira — e é
    por isso que a apuração recusa em vez de assumir.
    """
    from identidade.models import Lotacao

    lotacao = Lotacao.objects.filter(user=pessoa_alvo).select_related("unidade").first()
    if lotacao is None:
        return contrato.Escopo()
    centros = (lotacao.centro_custo_codigo,) if lotacao.centro_custo_codigo else ()
    regionais = (lotacao.unidade.nome,) if lotacao.unidade_id else ()
    return contrato.Escopo(regionais=regionais, centros_custo=centros)


def ler(meta: Meta, escopo: contrato.Escopo, competencia: date) -> Leitura:
    """Consulta os fatores. NUNCA levanta, e `None` nunca vira zero."""
    f1 = cat.de(meta.fator_1)
    f2 = cat.de(meta.fator_2) if meta.fator_2 else None
    if f1 is None or (meta.fator_2 and f2 is None):
        return Leitura(motivo="A meta aponta para um fator que não existe mais.")

    carimbo = cat.carimbo_de(meta.fator_1, competencia=competencia)
    texto = carimbo.texto if carimbo else ""

    try:
        v1 = f1.valor(escopo, competencia)
        v2 = f2.valor(escopo, competencia) if f2 else None
    except Exception as erro:  # noqa: BLE001 - a apuração roda em lote
        return Leitura(
            motivo=f"O espelho falhou ao responder: {type(erro).__name__}.",
            carimbo=texto,
        )

    if v1 is None:
        return Leitura(
            motivo=f"O espelho não tem {f1.rotulo.lower()} para este escopo.",
            carimbo=texto,
        )
    if f2 is not None and (v2 is None or v2 == 0):
        # Divisor zero e divisor ausente levam ao mesmo lugar — não dá para
        # medir — e a mensagem distingue os dois, porque as ações são outras.
        return Leitura(
            realizado=Decimal(v1),
            motivo=(
                f"{f2.rotulo} é zero — não há denominador."
                if v2 == 0
                else f"O espelho não tem {f2.rotulo.lower()} para este escopo."
            ),
            carimbo=texto,
        )

    realizado = Decimal(v1) / Decimal(v2) * 100 if f2 else Decimal(v1)
    alvo = meta.alvo if meta.alvo is not None else Decimal("100")
    if alvo == 0:
        return Leitura(realizado=realizado, motivo="O alvo é zero.", carimbo=texto)

    if meta.tipo_calculo == TipoCalculo.INVERSO:
        # Turnover, absenteísmo, custo: menor é melhor. Sem esta direção, quem
        # perdeu metade da equipe apareceria com 140% de desempenho.
        atingimento = (alvo / realizado * 100) if realizado else TETO_DE_ATINGIMENTO
    else:
        atingimento = realizado / alvo * 100

    atingimento = min(Decimal(atingimento), TETO_DE_ATINGIMENTO)
    return Leitura(
        realizado=realizado.quantize(Decimal("0.01")),
        atingimento=atingimento.quantize(Decimal("0.1")),
        carimbo=texto,
    )


@transaction.atomic
def apurar(quadro: QuadroMetas, quem, cache=None) -> QuadroMetas:
    """Congela o realizado de cada meta. Só de quadro APROVADO.

    Apurar rascunho permitiria escrever a meta depois de ver o número — e é a
    mesma família de defeito que o ADR-035 fecha do outro lado.
    """
    if not pode_aprovar(quadro, quem, cache=cache):
        raise MetaError("Apurar o quadro é de quem lidera a pessoa.")
    if quadro.situacao == SituacaoQuadro.RASCUNHO:
        raise MetaError("Só quadro aprovado é apurado. Aprove primeiro.")

    escopo = escopo_da_pessoa(quadro.pessoa)
    competencia = quadro.ciclo.competencia_de_apuracao
    agora = timezone.now()

    for meta in quadro.metas.all():
        leitura = ler(meta, escopo, competencia)
        meta.realizado = leitura.realizado
        meta.atingimento_pct = leitura.atingimento
        meta.motivo_sem_apuracao = leitura.motivo[:200]
        meta.carimbo_texto = leitura.carimbo[:200]
        meta.apurado_em = agora
        meta.save(
            update_fields=[
                "realizado", "atingimento_pct", "motivo_sem_apuracao",
                "carimbo_texto", "apurado_em",
            ]
        )

    quadro.situacao = SituacaoQuadro.APURADO
    quadro.apurado_em = agora
    quadro.save(update_fields=["situacao", "apurado_em"])
    return quadro


# ── PDI ─────────────────────────────────────────────────────────────


def pdi_de(pessoa_alvo, ciclo: CicloMetas) -> PlanoDesenvolvimento | None:
    return PlanoDesenvolvimento.objects.filter(
        pessoa=pessoa_alvo, ciclo=ciclo
    ).first()


@transaction.atomic
def salvar_pdi(pessoa_alvo, ciclo: CicloMetas, quem, cache=None, **campos):
    """O PDI é da PESSOA, e ela escreve o dela.

    Diferente das metas de propósito: a meta é combinada com quem lidera, e o
    plano de desenvolvimento é a conversa de carreira de quem o vive. Um PDI que
    só o gestor edita é um PDI que a pessoa não reconhece.
    """
    if not _alcanca(quem, PERMISSAO, pessoa_alvo, cache=cache):
        raise MetaError("Este plano de desenvolvimento não é seu.")
    if ciclo.situacao == SituacaoCiclo.FECHADO:
        raise MetaError("Este ciclo está fechado.")

    plano, _ = PlanoDesenvolvimento.objects.get_or_create(
        pessoa=pessoa_alvo, ciclo=ciclo
    )
    for campo in ("responsabilidades", "interesses", "aspiracao_curta",
                  "aspiracao_longa"):
        if campo in campos:
            setattr(plano, campo, (campos[campo] or "").strip())
    plano.save()
    return plano


@transaction.atomic
def acrescentar_acao(
    plano: PlanoDesenvolvimento, quem, descricao: str, mes, ano, cache=None
):
    if not _alcanca(quem, PERMISSAO, plano.pessoa, cache=cache):
        raise MetaError("Este plano de desenvolvimento não é seu.")
    descricao = (descricao or "").strip()
    if not descricao:
        raise MetaError("A ação precisa de uma descrição.")
    try:
        mes, ano = int(mes), int(ano)
    except (TypeError, ValueError):
        raise MetaError("Mês e ano precisam ser números.")
    if not 1 <= mes <= 12:
        raise MetaError("Mês fora do calendário.")

    return AcaoDesenvolvimento.objects.create(
        plano=plano, descricao=descricao[:300], mes=mes, ano=ano
    )


def concluir_acao(acao: AcaoDesenvolvimento, quem, cache=None):
    if not _alcanca(quem, PERMISSAO, acao.plano.pessoa, cache=cache):
        raise MetaError("Esta ação não é sua.")
    if acao.concluida:
        return acao
    acao.concluida_em = timezone.localdate()
    acao.save(update_fields=["concluida_em"])
    return acao


# ── O que a tela recebe ─────────────────────────────────────────────


def tela_do_quadro(pessoa_alvo, ciclo: CicloMetas, quem, cache=None) -> dict:
    """O quadro de uma pessoa, pronto para a tela."""
    quadro = quadro_de(pessoa_alvo, ciclo)
    if quadro is not None and not pode_ver(quadro, quem, cache=cache):
        raise SemMetas("Este quadro não é seu nem de quem você lidera.")
    if quadro is None and not _alcanca(quem, PERMISSAO, pessoa_alvo, cache=cache):
        raise SemMetas("Este quadro não é seu nem de quem você lidera.")

    metas = list(quadro.metas.all()) if quadro else []
    return {
        "alvo": pessoa_alvo,
        "ciclo": ciclo,
        "ciclos": list(CicloMetas.objects.all()[:12]),
        "quadro": quadro,
        "metas": metas,
        "nota": quadro.nota if quadro else None,
        "nao_apuradas": quadro.nao_apuradas if quadro else [],
        "pdi": pdi_de(pessoa_alvo, ciclo),
        "fatores": cat.todos(),
        "pode_definir": bool(quadro and pode_definir(quadro, quem, cache=cache)),
        "pode_aprovar": bool(quadro and pode_aprovar(quadro, quem, cache=cache)),
        "sou_eu": pessoa_alvo.pk == getattr(quem, "pk", None),
        "pode_abrir": _alcanca(quem, PERMISSAO_DEFINIR, pessoa_alvo, cache=cache),
    }


def equipe_de(pessoa, ciclo: CicloMetas, cache=None) -> list[dict]:
    """A lista de quem esta pessoa lidera, com a SITUAÇÃO do quadro.

    Situação, e **nunca a nota**. É a restrição 8 no lugar em que ela é mais
    fácil de violar sem perceber: uma coluna de nota ao lado de uma lista de
    nomes é uma planilha de desempenho, e ela circula.
    """
    escopo = escopo_da_permissao(pessoa, PERMISSAO, cache=cache)
    if escopo not in (ESCOPO_GLOBAL, ESCOPO_EQUIPE):
        # Escopo `proprio` não lidera ninguém, e a seção nem aparece.
        return []

    # O recorte vem de `quadros_visiveis`, e não de uma consulta escrita aqui.
    # Eram duas implementações do mesmo alcance, e a segunda divergiria da
    # primeira na primeira mudança de organograma — foi o teste de função morta
    # que apontou a duplicação, o que é uma sorte: ele reprova por outro motivo.
    quadros = quadros_visiveis(pessoa, ciclo, cache=cache)
    if escopo == ESCOPO_EQUIPE:
        # O quadro da própria pessoa não entra na lista de "quem você lidera":
        # ele já está na tela inteira, acima.
        quadros = quadros.exclude(pessoa=pessoa)

    return [
        {
            "pessoa": q.pessoa,
            "situacao": q.situacao,
            "rotulo": q.get_situacao_display(),
            "metas": q.metas.count(),
            "url": q.pessoa_id,
        }
        for q in quadros
    ]


def resumo_por_situacao(ciclo: CicloMetas) -> dict:
    """A CONTAGEM por situação — o painel do R.H., sem nome nenhum.

    É a única visão agregada que esta onda entrega, e é deliberadamente pobre:
    quantos rascunhos, quantos aprovados, quantos apurados. Qualquer coisa a
    mais viraria um ranking.
    """
    base = QuadroMetas.objects.filter(ciclo=ciclo)
    return {
        "total": base.count(),
        "rascunho": base.filter(situacao=SituacaoQuadro.RASCUNHO).count(),
        "aprovado": base.filter(situacao=SituacaoQuadro.APROVADO).count(),
        "apurado": base.filter(situacao=SituacaoQuadro.APURADO).count(),
    }
