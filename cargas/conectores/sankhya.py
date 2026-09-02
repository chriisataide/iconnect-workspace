"""Sankhya Om — financeiro, contábil, folha e ponto.

## A API, conferida em 01/09/2026

Documentação vigente: <https://developer.sankhya.com.br/>.

**Autenticação** é OAuth2 `client_credentials` no Gateway, e **não** o fluxo
antigo de `username`/`password` em cabeçalho que ainda circula em exemplos:

    POST {base}/authenticate
    X-Token: <token gerado em Configurações Gateway do Sankhya Om>
    Content-Type: application/x-www-form-urlencoded
    client_id=…&client_secret=…&grant_type=client_credentials

    → {"access_token": "<jwt>", "expires_in": 300, "token_type": "Bearer"}

O token vale ~300 s. Isso é curto para uma carga de competência inteira, então
ele é renovado sob demanda aqui dentro — e é a razão de `_token()` existir em vez
de o token ser passado no construtor.

**Consulta** é `loadRecords`, `POST`, com o serviço no *query string*:

    POST {base}/gateway/v1/mge/service.sbr
         ?serviceName=CRUDServiceProvider.loadRecords&outputType=json
    Authorization: Bearer <access_token>

A paginação é por `offsetPage` (começa em 0), e a resposta traz `hasMoreResult`.

## O que este arquivo NÃO pode saber

**Quais entidades e campos a ADB usa.** `rootEntity` é o nome da tabela ou view
no Sankhya daquela instalação, e ele varia por implantação — não existe resposta
certa que eu possa escrever aqui sem ver o ambiente.

Por isso o mapa está em `CONSULTAS`, sobrescritível por `settings.SANKHYA_CONSULTAS`,
e o conector **falha alto e claro** quando ele não bate: uma consulta que devolve
zero linhas em silêncio produziria um espelho vazio com carga "sucesso", que é o
pior resultado possível.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.conf import settings

from ..transporte import PAGINAS_MAXIMAS, FonteNaoConfigurada, TransporteError, pedir
from .base import ConectorBase, Janela, Registro

logger = logging.getLogger("cargas")

SERVICO = "CRUDServiceProvider.loadRecords"

#: O mapa que depende da implantação. Sobrescreva por `SANKHYA_CONSULTAS` no
#: settings em vez de editar este arquivo — assim a atualização do produto não
#: apaga a configuração do cliente.
#:
#: `campos` é a ordem em que o Sankhya devolve os valores: a resposta do
#: `loadRecords` é posicional, e não nomeada. Trocar a ordem aqui sem trocar no
#: `fieldset` desloca todas as colunas — por isso as duas listas saem da MESMA
#: tupla.
CONSULTAS: dict[str, dict] = {
    "competencia": {
        "rootEntity": "VW_RESULTADO_CC",
        "campos": (
            "CHAVE", "CODCENCUS", "ANO", "MES", "RECEITABRUTA", "IMPOSTOS",
            "CUSTODIRETO", "CUSTOINDIRETO", "MARGEMCONTRIB", "EBITDA",
            "AJUSTEPOTENCIAL",
        ),
        "campo_data": "DTREF",
    },
    "quadro": {
        "rootEntity": "VW_QUADRO_PESSOAS",
        "campos": (
            "CHAVE", "CODCENCUS", "ANO", "MES", "EFETIVOATIVO", "ADMISSOES",
            "RESCISOES", "TURNOVER", "ABSENTEISMO", "VAGASABERTAS",
            "VAGASNOPRAZO", "EMFERIAS", "AFASTADOS",
        ),
        "campo_data": "DTREF",
    },
    "apontamento": {
        "rootEntity": "VW_APONTAMENTO",
        "campos": (
            "CHAVE", "CODCENCUS", "ANO", "MES", "HORASNORMAIS", "HETOTAL",
            "HEINEFICIENCIA", "HESERVICOEXTRA", "HESEMCLASSIF", "HORAESCALA",
            "HORAABONO", "HORADESCONTO", "HORANOTURNA", "BANCOHORAS",
            "FOLHASPENDENTES", "CONTRATOSPENDENTES",
        ),
        "campo_data": "DTREF",
    },
}

#: Coluna do Sankhya → campo do espelho, por entidade. Separado de `CONSULTAS`
#: porque a lista de campos muda com a implantação e a tradução não: `EBITDA`
#: sempre vira `ebitda`.
TRADUCAO: dict[str, dict[str, str]] = {
    "competencia": {
        "CODCENCUS": "centro_custo", "ANO": "ano", "MES": "mes",
        "RECEITABRUTA": "receita_bruta", "IMPOSTOS": "impostos",
        "CUSTODIRETO": "custo_direto", "CUSTOINDIRETO": "custo_indireto",
        "MARGEMCONTRIB": "margem_contribuicao", "EBITDA": "ebitda",
        "AJUSTEPOTENCIAL": "ajuste_potencial",
    },
    "quadro": {
        "CODCENCUS": "centro_custo", "ANO": "ano", "MES": "mes",
        "EFETIVOATIVO": "efetivo_ativo", "ADMISSOES": "admissoes",
        "RESCISOES": "rescisoes", "TURNOVER": "turnover_pct",
        "ABSENTEISMO": "absenteismo_pct", "VAGASABERTAS": "vagas_abertas",
        "VAGASNOPRAZO": "vagas_fechadas_no_prazo", "EMFERIAS": "em_ferias",
        "AFASTADOS": "afastados",
    },
    "apontamento": {
        "CODCENCUS": "centro_custo", "ANO": "ano", "MES": "mes",
        "HORASNORMAIS": "horas_normais", "HETOTAL": "he_total",
        "HEINEFICIENCIA": "he_ineficiencia", "HESERVICOEXTRA": "he_servico_extra",
        "HESEMCLASSIF": "he_sem_classificacao", "HORAESCALA": "hora_escala",
        "HORAABONO": "hora_abono", "HORADESCONTO": "hora_desconto",
        "HORANOTURNA": "hora_noturna", "BANCOHORAS": "banco_horas_saldo",
        "FOLHASPENDENTES": "folhas_ponto_pendentes",
        "CONTRATOSPENDENTES": "contratos_pendentes_assinatura",
    },
}

INTEIROS = frozenset({
    "ano", "mes", "efetivo_ativo", "admissoes", "rescisoes", "vagas_abertas",
    "vagas_fechadas_no_prazo", "em_ferias", "afastados",
    "folhas_ponto_pendentes", "contratos_pendentes_assinatura",
})


class ConectorSankhya(ConectorBase):
    chave = "sankhya"

    def __init__(self):
        self._token = ""
        self._expira_em: datetime | None = None

    # ── Configuração ────────────────────────────────────────────────

    @property
    def base(self) -> str:
        return (getattr(settings, "SANKHYA_BASE_URL", "") or "").rstrip("/")

    def disponivel(self) -> bool:
        return bool(
            self.base
            and getattr(settings, "SANKHYA_CLIENT_ID", "")
            and getattr(settings, "SANKHYA_CLIENT_SECRET", "")
            and getattr(settings, "SANKHYA_TOKEN", "")
        )

    def consultas(self) -> dict:
        return getattr(settings, "SANKHYA_CONSULTAS", None) or CONSULTAS

    # ── Coleta ──────────────────────────────────────────────────────

    def coletar(self, janela: Janela) -> Iterable[dict]:
        for entidade, consulta in self.consultas().items():
            yield from self._paginar(entidade, consulta, janela)

    def _paginar(self, entidade: str, consulta: dict, janela: Janela) -> Iterable[dict]:
        pagina = 0
        while pagina < PAGINAS_MAXIMAS:
            corpo = self._corpo(consulta, janela, pagina)
            resposta = pedir(
                f"{self.base}/gateway/v1/mge/service.sbr"
                f"?serviceName={SERVICO}&outputType=json",
                metodo="POST",
                cabecalhos={"Authorization": f"Bearer {self._token_valido()}"},
                corpo=corpo,
            )
            dados = (resposta.get("responseBody") or {}).get("entities") or {}
            linhas = _lista(dados.get("entity"))
            for linha in linhas:
                yield {"_entidade": entidade, "_campos": consulta["campos"], **linha}

            if str(dados.get("hasMoreResult", "false")).lower() != "true":
                return
            pagina += 1

        # Chegou ao teto. NÃO é sucesso silencioso: a carga fica parcial e o
        # operador vê o motivo, em vez de o espelho ficar com metade dos meses.
        raise TransporteError(
            f"{entidade}: passou de {PAGINAS_MAXIMAS} páginas no Sankhya. "
            "Estreite a janela da carga."
        )

    def _corpo(self, consulta: dict, janela: Janela, pagina: int) -> dict:
        campos = ", ".join(consulta["campos"])
        dataset = {
            "rootEntity": consulta["rootEntity"],
            "includePresentationFields": "N",
            # Campos calculados custam caro no Sankhya e nós não usamos nenhum.
            "ignoreCalculatedFields": True,
            "offsetPage": str(pagina),
            "entity": {"fieldset": {"list": campos}},
        }
        if not janela.aberta and consulta.get("campo_data"):
            # Placeholders `?` com `parameter`, e nunca interpolação: é a mesma
            # regra de SQL parametrizado, e o `criteria` do Sankhya é SQL.
            dataset["criteria"] = {
                "expression": {
                    "$": f"this.{consulta['campo_data']} BETWEEN ? AND ?"
                },
                "parameter": [
                    {"$": _iso(janela.de), "type": "D"},
                    {"$": _iso(janela.ate), "type": "D"},
                ],
            }
        return {"serviceName": SERVICO, "requestBody": {"dataSet": dataset}}

    # ── Autenticação ────────────────────────────────────────────────

    def _token_valido(self) -> str:
        """O token do Gateway, renovado quando perto de vencer.

        Ele dura cerca de 300 s, e uma carga de competência passa disso. Renovar
        com folga de 30 s evita o `401` no meio da paginação — que custaria a
        página inteira e apareceria como carga parcial sem motivo aparente.
        """
        from django.utils import timezone

        agora = timezone.now()
        if self._token and self._expira_em and agora < self._expira_em:
            return self._token

        if not self.disponivel():
            raise FonteNaoConfigurada(
                "Faltam SANKHYA_BASE_URL, SANKHYA_CLIENT_ID, "
                "SANKHYA_CLIENT_SECRET ou SANKHYA_TOKEN."
            )

        resposta = pedir(
            f"{self.base}/authenticate",
            metodo="POST",
            cabecalhos={"X-Token": settings.SANKHYA_TOKEN},
            corpo={
                "client_id": settings.SANKHYA_CLIENT_ID,
                "client_secret": settings.SANKHYA_CLIENT_SECRET,
                "grant_type": "client_credentials",
            },
            forma="form",
        )
        token = resposta.get("access_token") or ""
        if not token:
            # Sem `str(resposta)` na mensagem: o corpo de uma resposta de
            # autenticação é o último lugar de onde copiar texto para uma tela.
            raise TransporteError("O Sankhya não devolveu access_token.")

        from datetime import timedelta

        segundos = int(resposta.get("expires_in") or 300)
        self._token = token
        self._expira_em = agora + timedelta(seconds=max(segundos - 30, 30))
        return token

    # ── Normalização ────────────────────────────────────────────────

    def normalizar(self, bruto: Iterable[dict]) -> Iterable[Registro]:
        for item in bruto:
            registro = self._converter(item)
            if registro is not None:
                yield registro

    def _converter(self, item: dict) -> Registro | None:
        entidade = item.get("_entidade", "")
        traducao = TRADUCAO.get(entidade)
        if not traducao:
            return None

        # A resposta do `loadRecords` é POSICIONAL: `{"f0": {...}, "f1": {...}}`.
        # A ordem é a do `fieldset`, e é por isso que `campos` e `fieldset` saem
        # da mesma tupla — desencontrar as duas desloca todas as colunas e
        # grava receita na coluna de imposto, sem erro nenhum.
        campos = item.get("_campos") or ()
        valores = {
            campo: _valor(item.get(f"f{i}"))
            for i, campo in enumerate(campos)
        }

        chave = valores.get("CHAVE") or ""
        if not chave:
            return None

        dados = {}
        for coluna, destino in traducao.items():
            if coluna not in valores:
                continue
            dados[destino] = _tipar(destino, valores[coluna])
        return Registro(entidade=entidade, chave_externa=str(chave), dados=dados)


def _lista(valor) -> list:
    """O Sankhya devolve objeto quando há um registro e lista quando há vários.

    Sem isto, uma carga de UMA competência iteraria as chaves do dicionário e
    produziria lixo — e só na virada do mês, que é quando ninguém está olhando.
    """
    if valor is None:
        return []
    return valor if isinstance(valor, list) else [valor]


def _valor(campo):
    """`{"$": "1200.50"}` → `"1200.50"`. É o embrulho do XML que sobreviveu ao JSON."""
    if isinstance(campo, dict):
        return campo.get("$")
    return campo


def _tipar(destino: str, bruto):
    if bruto in (None, ""):
        return None
    if destino in INTEIROS:
        try:
            return int(float(str(bruto).replace(",", ".")))
        except (TypeError, ValueError):
            return None
    if destino in ("centro_custo",):
        return str(bruto).strip()
    try:
        return Decimal(str(bruto).replace(",", "."))
    except (InvalidOperation, ValueError):
        return str(bruto).strip()


def _iso(dia) -> str:
    return dia.strftime("%d/%m/%Y") if dia else ""
