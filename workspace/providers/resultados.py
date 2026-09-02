"""Contrato de resultados — o Workspace pergunta, o espelho responde.

## A direção, que não inverte

    cargas ──escreve──► resultados ──implementa──► workspace.providers ◄── workspace

O app `workspace` conhece **este arquivo** e mais nada. Ele não sabe que existe
Sankhya, monday ou Platform; não sabe que existe um app `cargas`; não sabe sequer
que existe um app `resultados`. Trocar o ERP mexe num conector — nenhuma view
muda. É a mesma fronteira de `orcamento.py`, aplicada a um problema maior.

## Por que DTO e não o model do espelho

Devolver `resultados.models.Contrato` faria a tela de resultados depender do
schema do app de espelho, e a primeira mudança de coluna viraria uma mudança de
template. Pior: o model tem `hash_conteudo`, `carga_id` e `chave_externa` —
mecânica de ingestão que a tela não tem o que fazer com, e que apareceria em
`dir()` para quem estivesse escrevendo a view.

## Procedência não é o mesmo que frescor

São duas perguntas, e é fácil confundi-las:

- **Procedência** (`Procedencia`, aqui) responde *de onde veio ESTA linha* —
  qual fonte, qual carga, quão completa. É por registro.
- **Frescor** (`workspace.providers.frescor`, Onda 1) responde *quando a FONTE
  carregou pela última vez*. É por fonte, e é o que vira carimbo na tela.

Uma linha pode ser velha numa fonte fresca (não veio na última carga) e nova
numa fonte velha (a carga falhou depois de gravá-la). Um campo só não diria as
duas coisas.

## Um registro para seis contratos

Seis pares `registrar_x`/`obter_x` seriam doze funções para uma implementação
só — `resultados` responde por todos. O registro aqui aceita qualquer um dos
contratos e despacha por tipo: quem implementa três interfaces se registra uma
vez e atende às três.
"""

from __future__ import annotations

import threading
from abc import ABC
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

# ── Procedência ─────────────────────────────────────────────────────

#: Quanto do que se esperava chegou. `None` = a fonte não sabe dizer, que é
#: diferente de 100%: uma carga sem contagem esperada não pode afirmar que veio
#: tudo.
Completude = float | None


@dataclass(frozen=True)
class Procedencia:
    """De onde veio esta linha. Espelho sem isto é boato com cara de relatório."""

    fonte: str
    #: O id no sistema de origem. É o que permite a uma pessoa abrir o Sankhya e
    #: conferir a linha — sem ele, "de onde vem esse número" não tem resposta
    #: acionável, só uma marca de fonte.
    chave_externa: str = ""
    carregado_em: datetime | None = None
    competencia: date | None = None
    completude: Completude = None

    def __str__(self) -> str:
        return f"{self.fonte}:{self.chave_externa}" if self.chave_externa else self.fonte


@dataclass(frozen=True)
class ComProcedencia:
    """Base dos DTOs. Todo número que sai daqui sabe dizer de onde veio."""

    procedencia: Procedencia


# ── Os DTOs ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CompetenciaDTO(ComProcedencia):
    """Um mês de resultado, realizado contra orçado.

    As seis colunas do benchmark estão todas aqui, e a do meio é a que evita que
    a reunião vire briga sobre o número: `ajuste_potencial` é o que a operação
    declara que já aconteceu e ainda não bateu na contabilidade.
    """

    centro_custo: str = ""
    ano: int = 0
    mes: int = 0
    receita_bruta: Decimal = Decimal("0")
    impostos: Decimal = Decimal("0")
    custo_direto: Decimal = Decimal("0")
    custo_indireto: Decimal = Decimal("0")
    margem_contribuicao: Decimal = Decimal("0")
    ebitda: Decimal = Decimal("0")
    ajuste_potencial: Decimal = Decimal("0")
    #: `None` e não `Decimal("0")`: sem orçado é diferente de orçado zero. A
    #: faixa 2 marca a linha como "sem orçado" em vez de mostrar variação de
    #: 100% — que é o que uma conciliação de centro de custo quebrada produz.
    receita_orcada: Decimal | None = None
    custo_orcado: Decimal | None = None
    margem_orcada: Decimal | None = None
    contrato: str = ""

    @property
    def tem_orcado(self) -> bool:
        return self.receita_orcada is not None


@dataclass(frozen=True)
class ConsolidadoDTO(ComProcedencia):
    """A soma de um escopo numa competência."""

    competencia: date | None = None
    receita_bruta: Decimal = Decimal("0")
    margem_contribuicao: Decimal = Decimal("0")
    ebitda: Decimal = Decimal("0")
    #: Quantas linhas entraram na soma. Zero linhas e soma zero são a mesma
    #: aparência e coisas diferentes — a tela precisa distinguir "deu zero" de
    #: "não tem dado".
    linhas: int = 0


@dataclass(frozen=True)
class ContratoDTO(ComProcedencia):
    codigo: str = ""
    nome_cliente: str = ""
    servico: str = ""
    centro_custo: str = ""
    regional: str = ""
    inicio_vigencia: date | None = None
    fim_vigencia: date | None = None
    valor_mensal: Decimal = Decimal("0")
    status: str = ""
    #: `"1"`, `"2"`, `"3"` ou `SEM_AMOSTRA`. String e não inteiro porque
    #: "sem amostra" é uma resposta legítima e não um número.
    layer: str = ""
    margem_contribuicao_pct: Decimal | None = None

    @property
    def deficitario(self) -> bool:
        mc = self.margem_contribuicao_pct
        return mc is not None and mc < 0


@dataclass(frozen=True)
class ProjetoDTO(ComProcedencia):
    codigo: str = ""
    nome: str = ""
    cliente: str = ""
    contrato: str = ""
    responsavel: str = ""
    situacao: str = ""
    inicio: date | None = None
    prazo: date | None = None
    percentual_concluido: int = 0
    bloqueado: bool = False
    motivo_bloqueio: str = ""


@dataclass(frozen=True)
class MarcoDTO(ComProcedencia):
    projeto: str = ""
    titulo: str = ""
    prazo: date | None = None
    concluido_em: date | None = None
    responsavel: str = ""

    @property
    def vencido(self) -> bool:
        from django.utils import timezone

        return bool(
            self.prazo and not self.concluido_em and self.prazo < timezone.localdate()
        )


@dataclass(frozen=True)
class QuadroDTO(ComProcedencia):
    centro_custo: str = ""
    ano: int = 0
    mes: int = 0
    efetivo_ativo: int = 0
    admissoes: int = 0
    rescisoes: int = 0
    turnover_pct: Decimal = Decimal("0")
    absenteismo_pct: Decimal = Decimal("0")
    vagas_abertas: int = 0
    vagas_fechadas_no_prazo: int = 0
    em_ferias: int = 0
    afastados: int = 0


@dataclass(frozen=True)
class ApontamentoDTO(ComProcedencia):
    centro_custo: str = ""
    ano: int = 0
    mes: int = 0
    horas_normais: Decimal = Decimal("0")
    he_total: Decimal = Decimal("0")
    he_ineficiencia: Decimal = Decimal("0")
    he_servico_extra: Decimal = Decimal("0")
    he_sem_classificacao: Decimal = Decimal("0")
    hora_escala: Decimal = Decimal("0")
    hora_abono: Decimal = Decimal("0")
    hora_desconto: Decimal = Decimal("0")
    hora_noturna: Decimal = Decimal("0")
    banco_horas_saldo: Decimal = Decimal("0")
    folhas_ponto_pendentes: int = 0
    contratos_pendentes_assinatura: int = 0


@dataclass(frozen=True)
class AvaliacaoDTO(ComProcedencia):
    contrato: str = ""
    data: date | None = None
    nota: int = 0
    classificacao: str = ""
    comentario: str = ""
    tratativa_aberta: bool = False
    tratativa_prazo: date | None = None
    tratativa_status: str = ""

    @property
    def detrator_sem_tratativa(self) -> bool:
        return self.classificacao == "detrator" and not self.tratativa_aberta


@dataclass(frozen=True)
class MovimentacaoDTO:
    """Conquistas, renovações e perdas de um período."""

    conquistas: list[ContratoDTO] = field(default_factory=list)
    renovacoes: list[ContratoDTO] = field(default_factory=list)
    perdas: list[ContratoDTO] = field(default_factory=list)


@dataclass(frozen=True)
class MovimentacaoPessoasDTO:
    admissoes: int = 0
    rescisoes: int = 0
    em_ferias: int = 0


@dataclass(frozen=True)
class Escopo:
    """O recorte da pergunta — e o lugar onde a permissão vira consulta.

    Vazio quer dizer "a empresa inteira", e quem monta o escopo é a VIEW, a
    partir do que `pode()` responde. O provedor não decide alcance: se
    decidisse, existiriam dois lugares onde "quem vê o quê" está escrito, e o
    espelho passaria a ter opinião sobre organograma.

    Tuplas e não listas porque o DTO é `frozen` e o escopo entra em chave de
    cache na Onda 3.
    """

    regionais: tuple[str, ...] = ()
    centros_custo: tuple[str, ...] = ()
    contratos: tuple[str, ...] = ()

    @property
    def tudo(self) -> bool:
        return not (self.regionais or self.centros_custo or self.contratos)


# ── Os contratos ────────────────────────────────────────────────────
#
# Seis, e não um com vinte métodos. Cada um é uma PERGUNTA que a tela faz, e
# separá-los deixa visível quem responde o quê: no dia em que a carteira passar
# a vir do Sankhya em vez do Platform, só `ProvedorCarteira` muda de dono.
#
# Todos com implementação padrão vazia, pela mesma razão do `WorkspaceProvider`:
# quem responde só sobre projetos não deve ser obrigado a escrever `return []`
# cinco vezes.


class ProvedorResultadoFinanceiro(ABC):
    def serie_competencia(self, escopo, de: date, ate: date) -> list[CompetenciaDTO]:
        return []

    def consolidado(self, escopo, competencia: date) -> ConsolidadoDTO | None:
        return None


class ProvedorCarteira(ABC):
    def contratos(self, escopo, competencia: date | None = None) -> list[ContratoDTO]:
        return []

    def vencimentos(self, escopo, dias: int) -> list[ContratoDTO]:
        return []

    def movimentacoes(self, escopo, de: date, ate: date) -> MovimentacaoDTO:
        return MovimentacaoDTO()


class ProvedorProjetos(ABC):
    def projetos(self, escopo, situacao: str = "") -> list[ProjetoDTO]:
        return []

    def marcos_em_risco(self, escopo, dias: int) -> list[MarcoDTO]:
        return []


class ProvedorPessoas(ABC):
    def quadro(self, escopo, competencia: date) -> QuadroDTO | None:
        return None

    def movimentacao(self, escopo, de: date, ate: date) -> MovimentacaoPessoasDTO:
        return MovimentacaoPessoasDTO()


class ProvedorJornada(ABC):
    def apontamentos(self, escopo, competencia: date) -> ApontamentoDTO | None:
        return None


class ProvedorSatisfacao(ABC):
    def avaliacoes(self, escopo, de: date, ate: date) -> list[AvaliacaoDTO]:
        return []


CONTRATOS: tuple[type, ...] = (
    ProvedorResultadoFinanceiro,
    ProvedorCarteira,
    ProvedorProjetos,
    ProvedorPessoas,
    ProvedorJornada,
    ProvedorSatisfacao,
)


# ── O registro ──────────────────────────────────────────────────────

_provedores: dict[type, object] = {}
_lock = threading.Lock()


def registrar(provedor) -> object:
    """Registra um provedor em todos os contratos que ele implementa.

    Um objeto que herda de três ABCs se registra uma vez e atende às três. Não
    implementar nenhuma é erro: quase sempre é herança esquecida, e o sintoma
    sem esta checagem seria "a faixa está vazia" numa tela, semanas depois.
    """
    tipos = [c for c in CONTRATOS if isinstance(provedor, c)]
    if not tipos:
        raise TypeError(
            f"{provedor!r} não implementa nenhum contrato de resultados. "
            "Herde de um dos de `workspace.providers.resultados`."
        )
    with _lock:
        for tipo in tipos:
            _provedores[tipo] = provedor
    return provedor


def obter(contrato: type):
    """Quem responde por este contrato, ou None enquanto ninguém se registrou.

    `None` é estado normal: sem o app de espelho instalado, a tela diz que a
    fonte não está conectada em vez de quebrar. É a mesma degradação do
    `orcamento`.
    """
    with _lock:
        return _provedores.get(contrato)


def limpar() -> None:
    """Só para teste."""
    with _lock:
        _provedores.clear()
