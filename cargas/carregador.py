"""O carregador — coleta, normaliza, grava e registra. Um só, para todas as fontes.

## Por que o conector não grava

Porque gravar direito é difícil e sempre igual: upsert idempotente, contagem
honesta de criado/atualizado/ignorado/rejeitado, precedência entre fontes,
registro de divergência, e uma execução que sobrevive à falha no meio. Cada
conector reimplementando isso produziria quatro comportamentos diferentes, e o
terceiro esqueceria o `ignorados`.

Aqui, um conector novo escreve `coletar` e `normalizar` e herda tudo.

## Idempotência: `hash_conteudo`

Cada registro carrega o SHA-256 do que a fonte disse. Se o hash bate com o que
está no banco, **nada é escrito** — nem `importado_em`. Sem isso, rodar a mesma
carga de novo por precaução marcaria o espelho inteiro como recém-atualizado, e
a idade do dado na tela viraria ficção: tudo "há 2 min", nada realmente novo.

O contador `ignorados` é o que prova isso ao operador, e é o número que ele olha
depois de rodar duas vezes.

## Falha no meio NÃO desfaz o que já entrou

Cada registro é sua própria transação. Uma exceção na linha 400 deixa as 399
primeiras gravadas e a execução marcada `parcial` — com o motivo. O espelho fica
íntegro até onde chegou, e o carimbo da tela mostra o último dado bom com a
idade em destaque.

Envolver a carga inteira numa transação faria o oposto: uma linha ruim na quinta
hora descartaria cinco horas de dado bom, e a tela ficaria com a carga de
ontem sem ninguém entender por quê.

## Precedência é por CAMPO, e a procedência da linha é do último que escreveu

`RegraPrecedencia` diz, por `(entidade, campo)`, qual fonte vence. Uma linha pode
ter `valor_mensal` do Sankhya e `fim_vigencia` do Platform.

O que a linha guarda é a fonte da última escrita EFETIVA. Procedência por campo
exigiria uma tabela de escritas, e a pergunta que ela responderia — "por que
esses dois sistemas discordam?" — já é respondida melhor pela lista de
divergências, que mostra os dois valores lado a lado em vez de só o vencedor.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import date

from django.db import transaction
from django.utils import timezone

from resultados.models import (
    Apontamento,
    AvaliacaoCliente,
    CompetenciaResultado,
    Contrato,
    MarcoProjeto,
    Projeto,
    QuadroPessoas,
)

from .conectores import Janela, Registro, conector_de
from .models import Divergencia, ExecucaoCarga, FonteDados, RegraPrecedencia, StatusCarga
from .transporte import FonteNaoConfigurada, TransporteError

logger = logging.getLogger("cargas")

#: Nome curto → model do espelho. É o ÚNICO lugar que conhece os dois lados: o
#: conector fala em strings, o espelho em classes.
ENTIDADES = {
    "contrato": Contrato,
    "competencia": CompetenciaResultado,
    "projeto": Projeto,
    "marco": MarcoProjeto,
    "quadro": QuadroPessoas,
    "apontamento": Apontamento,
    "avaliacao": AvaliacaoCliente,
}

#: Como achar a linha que já existe, por entidade. É a chave de NEGÓCIO, e não
#: `(fonte, chave_externa)`: duas fontes descrevendo o mesmo contrato têm de
#: encontrar a MESMA linha, senão a precedência nunca é exercida e a carteira
#: aparece com o dobro dos contratos.
CHAVE_DE_NEGOCIO = {
    "contrato": ("codigo",),
    "competencia": ("contrato", "centro_custo", "ano", "mes"),
    "projeto": ("codigo",),
    "marco": ("projeto", "titulo"),
    "quadro": ("centro_custo", "ano", "mes"),
    "apontamento": ("centro_custo", "ano", "mes"),
    "avaliacao": ("contrato", "data"),
}

#: Campos de mecânica. Nunca vêm do conector e nunca entram no hash — se
#: entrassem, `importado_em` mudaria o hash a cada carga e nada seria ignorado.
MECANICA = frozenset(
    {"fonte", "chave_externa", "carga_id", "importado_em", "hash_conteudo"}
)


class CargaError(Exception):
    """A carga não pôde nem começar."""


@dataclass
class Resultado:
    """O que aconteceu. É o que vira `ExecucaoCarga` e a saída do comando."""

    fonte: str
    janela: Janela
    lidos: int = 0
    criados: int = 0
    atualizados: int = 0
    ignorados: int = 0
    rejeitados: int = 0
    divergencias: int = 0
    status: str = StatusCarga.SUCESSO
    erro_resumo: str = ""
    linhas_de_log: list[str] = field(default_factory=list)
    execucao: ExecucaoCarga | None = None

    def anotar(self, texto: str) -> None:
        self.linhas_de_log.append(texto)

    @property
    def log(self) -> str:
        return "\n".join(self.linhas_de_log)


def carregar(
    chave_fonte: str,
    janela: Janela | None = None,
    *,
    aplicar: bool = False,
) -> Resultado:
    """Roda a carga de uma fonte. Simulação por padrão.

    Em simulação nada é gravado no espelho, e a `ExecucaoCarga` nasce marcada
    `simulacao=True` — uma simulação que virasse carimbo faria a tela dizer que
    o dado chegou quando nada foi escrito.
    """
    janela = janela or Janela()
    fonte = FonteDados.objects.filter(chave=chave_fonte).first()
    if fonte is None:
        raise CargaError(
            f"Fonte {chave_fonte!r} não está cadastrada. "
            "Rode `semear_fontes --aplicar` antes."
        )
    if not fonte.ativa:
        raise CargaError(f"A fonte {fonte.nome} está desativada.")

    conector = conector_de(chave_fonte)
    if conector is None:
        raise CargaError(f"Não há conector escrito para {chave_fonte!r}.")

    resultado = Resultado(fonte=chave_fonte, janela=janela)
    execucao = ExecucaoCarga.objects.create(
        fonte=fonte,
        janela_de=janela.de,
        janela_ate=janela.ate,
        status=StatusCarga.EM_ANDAMENTO,
        simulacao=not aplicar,
    )
    resultado.execucao = execucao

    try:
        if not conector.disponivel():
            # NÃO é falha: rodar sem o Sankhya configurado é estado normal em
            # desenvolvimento. A execução fica registrada para a tela de fontes
            # poder dizer "não configurada" em vez de "nunca carregou".
            raise FonteNaoConfigurada(
                f"{fonte.nome} não está configurada neste ambiente."
            )
        _processar(conector, janela, execucao, resultado, aplicar=aplicar)
    except FonteNaoConfigurada as erro:
        resultado.status = StatusCarga.FALHA
        resultado.erro_resumo = str(erro)
    except (TransporteError, Exception) as erro:  # noqa: B014 - ver abaixo
        # `Exception` de propósito, e não só `TransporteError`: um `KeyError` no
        # `normalizar` de um conector tem de virar uma carga PARCIAL com motivo,
        # e não um traceback que derruba o cron e deixa a tela sem explicação.
        #
        # Parcial e não falha quando ALGO entrou: o que entrou é bom e fica.
        resultado.status = (
            StatusCarga.PARCIAL
            if (resultado.criados or resultado.atualizados)
            else StatusCarga.FALHA
        )
        resultado.erro_resumo = _resumo(erro)
        logger.warning(
            "carga %s → %s: %s", chave_fonte, resultado.status, type(erro).__name__
        )

    _fechar(execucao, resultado)
    return resultado


def _processar(conector, janela, execucao, resultado: Resultado, *, aplicar: bool) -> None:
    for bruto in _em_lotes(conector, janela):
        for registro in conector.normalizar([bruto]):
            resultado.lidos += 1
            try:
                _gravar(registro, conector.chave, execucao, resultado, aplicar=aplicar)
            except _Rejeitado as recusa:
                resultado.rejeitados += 1
                resultado.anotar(f"rejeitado {registro}: {recusa}")


def _em_lotes(conector, janela: Janela):
    """Itera o bruto. Existe para o `for` acima não ter dois níveis de exceção."""
    return conector.coletar(janela)


class _Rejeitado(Exception):
    """Este registro não entra, e a carga continua. Ver `rejeitados`."""


def _gravar(
    registro: Registro,
    fonte: str,
    execucao: ExecucaoCarga,
    resultado: Resultado,
    *,
    aplicar: bool,
) -> None:
    modelo = ENTIDADES.get(registro.entidade)
    if modelo is None:
        raise _Rejeitado(f"entidade desconhecida {registro.entidade!r}")

    if not registro.chave_externa:
        # Sem chave de origem não há idempotência: a próxima carga criaria uma
        # segunda linha, e a receita do mês dobraria em silêncio.
        raise _Rejeitado("sem chave externa")

    dados = {k: v for k, v in registro.dados.items() if k not in MECANICA}
    filtro = _filtro_de_negocio(registro.entidade, dados)
    if filtro is None:
        raise _Rejeitado("faltam campos da chave de negócio")

    existente = modelo.objects.filter(**filtro).first()
    assinatura = _hash(dados)

    if existente is None:
        if aplicar:
            with transaction.atomic():
                modelo.objects.create(
                    fonte=fonte,
                    chave_externa=registro.chave_externa,
                    carga_id=execucao.pk,
                    hash_conteudo=assinatura,
                    **dados,
                )
        resultado.criados += 1
        return

    if existente.hash_conteudo == assinatura and existente.fonte == fonte:
        # Nada mudou e é a mesma fonte. Não escreve — nem `importado_em`.
        resultado.ignorados += 1
        return

    mudancas, bloqueados = _aplicar_precedencia(
        registro.entidade, dados, existente, fonte, execucao, resultado, aplicar=aplicar
    )
    if not mudancas:
        resultado.ignorados += 1
        return

    if aplicar:
        with transaction.atomic():
            for campo, valor in mudancas.items():
                setattr(existente, campo, valor)
            existente.fonte = fonte
            existente.chave_externa = registro.chave_externa
            existente.carga_id = execucao.pk
            # O hash guarda o que a FONTE disse, e não o que ficou gravado. Se
            # guardasse o gravado, um campo bloqueado pela precedência faria o
            # hash nunca bater e a mesma carga escreveria de novo, para sempre.
            existente.hash_conteudo = assinatura
            existente.save()
    resultado.atualizados += 1
    if bloqueados:
        resultado.anotar(
            f"{registro}: {', '.join(bloqueados)} mantido(s) por precedência"
        )


def _aplicar_precedencia(
    entidade: str,
    dados: dict,
    existente,
    fonte: str,
    execucao: ExecucaoCarga,
    resultado: Resultado,
    *,
    aplicar: bool,
) -> tuple[dict, list[str]]:
    """Decide, campo a campo, o que esta fonte pode sobrescrever.

    Divergência é registrada MESMO quando a regra resolveu. Resolver não é
    concordar: o número entra na tela pela regra, e a divergência aparece na
    tela de fontes com os dois valores lado a lado, para alguém ir descobrir
    por que os dois sistemas discordam.
    """
    regras = _regras_de(entidade)
    mudancas: dict = {}
    bloqueados: list[str] = []

    for campo, novo in dados.items():
        atual = getattr(existente, campo, None)
        if _igual(atual, novo):
            continue

        vencedora = regras.get(campo)
        conflito = existente.fonte and existente.fonte != fonte
        if conflito:
            _registrar_divergencia(
                entidade, existente, campo, atual, novo, fonte, vencedora,
                execucao, resultado, aplicar=aplicar,
            )
        if conflito and vencedora and vencedora != fonte:
            # A outra fonte manda neste campo. Mantém o que está.
            bloqueados.append(campo)
            continue

        mudancas[campo] = novo

    return mudancas, bloqueados


def _registrar_divergencia(
    entidade, existente, campo, atual, novo, fonte, vencedora,
    execucao, resultado, *, aplicar: bool,
) -> None:
    resultado.divergencias += 1
    if not aplicar:
        return
    Divergencia.objects.create(
        entidade=entidade,
        chave_externa=str(getattr(existente, "codigo", existente.pk)),
        campo=campo,
        fonte_a=existente.fonte,
        valor_a=str(atual)[:200],
        fonte_b=fonte,
        valor_b=str(novo)[:200],
        fonte_vencedora=vencedora or "",
        carga=execucao,
    )


def _regras_de(entidade: str) -> dict[str, str]:
    return {
        regra.campo: regra.fonte_vencedora
        for regra in RegraPrecedencia.objects.filter(
            entidade=entidade, ativa=True
        ).order_by("ordem")
    }


def _filtro_de_negocio(entidade: str, dados: dict) -> dict | None:
    campos = CHAVE_DE_NEGOCIO.get(entidade, ())
    filtro = {}
    for campo in campos:
        if campo not in dados:
            # `contrato` é opcional em `competencia` — a linha de centro de
            # custo não tem contrato nenhum, e exigi-lo deixaria o rateio de
            # fora do espelho.
            if entidade == "competencia" and campo == "contrato":
                filtro["contrato"] = None
                continue
            return None
        filtro[campo] = dados[campo]
    return filtro or None


def _igual(atual, novo) -> bool:
    """Compara valor gravado com valor da fonte, tolerando tipos.

    `Decimal("10.00")` e `Decimal("10")` são o mesmo dinheiro; comparar por
    `==` de string faria toda carga achar que tudo mudou, e `ignorados` seria
    sempre zero.
    """
    if atual is None or novo is None:
        return atual is novo
    if hasattr(atual, "pk") or hasattr(novo, "pk"):
        return getattr(atual, "pk", atual) == getattr(novo, "pk", novo)
    try:
        return atual == novo or float(atual) == float(novo)
    except (TypeError, ValueError):
        return atual == novo


def _hash(dados: dict) -> str:
    """SHA-256 do que a fonte disse, estável entre execuções.

    `sort_keys` porque a ordem de um dicionário não é conteúdo; `default=str`
    porque `Decimal` e `date` não são JSON e viram texto determinístico.
    """
    bruto = json.dumps(dados, sort_keys=True, default=str, ensure_ascii=False)
    return hashlib.sha256(bruto.encode("utf-8")).hexdigest()


def _resumo(erro: Exception) -> str:
    """Uma linha, sem segredo e sem traceback.

    A tela de fontes é visível à diretoria, e uma URL com token no
    `erro_resumo` seria um vazamento numa tela que ninguém audita.
    """
    texto = str(erro).strip() or type(erro).__name__
    return texto.splitlines()[0][:300]


def _fechar(execucao: ExecucaoCarga, resultado: Resultado) -> None:
    execucao.terminada_em = timezone.now()
    execucao.status = resultado.status
    execucao.lidos = resultado.lidos
    execucao.criados = resultado.criados
    execucao.atualizados = resultado.atualizados
    execucao.ignorados = resultado.ignorados
    execucao.rejeitados = resultado.rejeitados
    execucao.erro_resumo = resultado.erro_resumo
    execucao.log = resultado.log[:20000]
    execucao.save()
