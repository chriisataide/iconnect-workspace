"""O conector canônico — um diretório de CSVs, um por entidade.

## Por que este vem primeiro

Porque é ele que torna os outros testáveis. O formato daqui é o **vocabulário
alvo** dos três conectores de API: o que o Sankhya devolve é traduzido para
estas colunas, e o que o monday devolve também. Um `Registro` produzido pelo CSV
e um produzido pelo Sankhya são indistinguíveis para o carregador — e é assim
que a semeadora de massa entra pelo mesmo caminho de toda carga, em vez de
gravar direto no model.

Se a semeadora precisar de um caminho especial para gravar, o carregador está
errado.

## O formato

Um arquivo por entidade, dentro de `CARGAS_CSV_DIR`:

    contrato.csv  competencia.csv  projeto.csv  marco.csv
    quadro.csv    apontamento.csv  avaliacao.csv

Primeira linha é o cabeçalho, e cada nome de coluna é o nome do campo no
espelho. Uma coluna a mais é ignorada com aviso; uma coluna obrigatória a menos
rejeita a LINHA, não o arquivo — planilha feita à mão tem linha ruim no meio, e
descartar as outras trezentas por causa dela seria o pior atendimento possível a
quem preencheu.

`chave_externa` é coluna do arquivo. Sem ela a linha é rejeitada: sem chave de
origem não há idempotência, e a carga seguinte criaria uma segunda linha.
"""

from __future__ import annotations

import csv
import logging
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings

from .base import ConectorBase, Janela, Registro

logger = logging.getLogger("cargas")

ENTIDADES = (
    "contrato", "competencia", "projeto", "marco",
    "quadro", "apontamento", "avaliacao",
)

#: Campos que precisam virar outro tipo. O CSV é todo string; gravar "1200.50"
#: num `DecimalField` funciona por acidente do Django e quebra na comparação de
#: hash — `"1200.50" != Decimal("1200.50")` faria toda carga achar que tudo
#: mudou, e `ignorados` seria sempre zero.
DECIMAIS = frozenset({
    "valor_mensal", "receita_bruta", "impostos", "custo_direto", "custo_indireto",
    "margem_contribuicao", "ebitda", "ajuste_potencial", "receita_orcada",
    "custo_orcado", "margem_orcada", "turnover_pct", "absenteismo_pct",
    "horas_normais", "he_total", "he_ineficiencia", "he_servico_extra",
    "he_sem_classificacao", "hora_escala", "hora_abono", "hora_desconto",
    "hora_noturna", "banco_horas_saldo",
})
INTEIROS = frozenset({
    "ano", "mes", "nota", "percentual_concluido", "efetivo_ativo", "admissoes",
    "rescisoes", "vagas_abertas", "vagas_fechadas_no_prazo", "em_ferias",
    "afastados", "folhas_ponto_pendentes", "contratos_pendentes_assinatura",
})
DATAS = frozenset({
    "inicio_vigencia", "fim_vigencia", "inicio", "prazo", "concluido_em",
    "data", "tratativa_prazo",
})
BOOLEANOS = frozenset({"bloqueado", "tratativa_aberta"})

#: Campos que apontam para outro registro do espelho. O CSV traz o CÓDIGO, e o
#: carregador precisa da instância — resolver aqui mantém o carregador ignorante
#: de que existe um formato de arquivo.
REFERENCIAS = {"contrato": "codigo", "projeto": "codigo"}

VERDADEIROS = frozenset({"1", "true", "sim", "s", "y", "yes", "verdadeiro"})


class ConectorCSV(ConectorBase):
    chave = "csv"

    def __init__(self, diretorio: str | Path | None = None):
        self._diretorio = Path(diretorio) if diretorio else None

    @property
    def diretorio(self) -> Path | None:
        if self._diretorio is not None:
            return self._diretorio
        configurado = getattr(settings, "CARGAS_CSV_DIR", "")
        return Path(configurado) if configurado else None

    def disponivel(self) -> bool:
        diretorio = self.diretorio
        return bool(diretorio and diretorio.is_dir())

    def coletar(self, janela: Janela) -> Iterable[dict]:
        """Lê os arquivos que existem. Entidade sem arquivo é silêncio, não erro.

        Uma carga de projetos não tem por que reclamar da ausência de
        `avaliacao.csv` — quem manda o que existe é quem preencheu.
        """
        diretorio = self.diretorio
        for entidade in ENTIDADES:
            caminho = diretorio / f"{entidade}.csv"
            if not caminho.exists():
                continue
            with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
                for numero, linha in enumerate(csv.DictReader(arquivo), start=2):
                    yield {"_entidade": entidade, "_linha": numero, **linha}

    def normalizar(self, bruto: Iterable[dict]) -> Iterable[Registro]:
        for item in bruto:
            registro = self._converter(item)
            if registro is not None:
                yield registro

    def _converter(self, item: dict) -> Registro | None:
        entidade = item.get("_entidade", "")
        chave = (item.get("chave_externa") or "").strip()
        if not entidade or not chave:
            return None

        dados: dict = {}
        for coluna, valor in item.items():
            if coluna.startswith("_") or coluna in ("chave_externa",):
                continue
            convertido = _converter_valor(coluna, valor)
            if convertido is not _IGNORAR:
                dados[coluna] = convertido

        return Registro(entidade=entidade, chave_externa=chave, dados=dados)


class _Ignorar:
    """Sentinela: esta coluna não entra. Distinta de `None`, que É um valor —
    `fim_vigencia` vazio significa "sem fim de vigência", e não "não informado"."""


_IGNORAR = _Ignorar()


def _converter_valor(coluna: str, bruto):
    texto = (bruto or "").strip() if isinstance(bruto, str) else bruto
    if texto == "" or texto is None:
        # Coluna vazia vira `None` para campo que aceita nulo e some para o
        # resto. Quem decide é o model, e quem descobre é o carregador ao
        # gravar — aqui só não podemos inventar zero: "sem orçado" e "orçado
        # zero" são leituras opostas.
        return None if coluna in DATAS or coluna.endswith("_orcada") or coluna.endswith("_orcado") else _IGNORAR

    if coluna in REFERENCIAS:
        return _resolver_referencia(coluna, texto)
    if coluna in DECIMAIS:
        try:
            return Decimal(str(texto).replace(",", "."))
        except (InvalidOperation, ValueError):
            return _IGNORAR
    if coluna in INTEIROS:
        try:
            return int(float(str(texto).replace(",", ".")))
        except (TypeError, ValueError):
            return _IGNORAR
    if coluna in DATAS:
        return _data(texto)
    if coluna in BOOLEANOS:
        return str(texto).strip().casefold() in VERDADEIROS
    return texto


def _resolver_referencia(coluna: str, codigo: str):
    """Código → instância. `None` quando não existe.

    Não rejeita a linha: um marco cujo projeto ainda não chegou nesta carga é
    caso normal quando os arquivos vêm em ordem qualquer. O carregador recusa
    depois, se a chave de negócio exigir — e aí a rejeição diz o que falta.
    """
    from resultados.models import Contrato, Projeto

    modelo = {"contrato": Contrato, "projeto": Projeto}[coluna]
    return modelo.objects.filter(codigo=codigo).first()


def _data(texto):
    """Aceita ISO e o formato brasileiro. Nada mais.

    Adivinhar entre `03/04/2026` e `04/03/2026` é como um relatório de abril
    vira um de março sem ninguém notar — por isso o formato com barra é lido
    como dia/mês, que é o que se digita no Brasil, e mais nenhum é tentado.
    """
    texto = str(texto).strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(texto, formato).date()
        except ValueError:
            continue
    return None
