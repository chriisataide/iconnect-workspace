"""PNCP — editais públicos com proposta aberta.

## O que ele traz, e por que só isto

O **Portal Nacional de Contratações Públicas** é o repositório oficial das
contratações regidas pela Lei 14.133/2021. A API de consulta tem doze endpoints;
este conector usa **um**:

    GET /api/consulta/v1/contratacoes/proposta

"Contratações com proposta ainda aberta". Os outros onze descrevem o passado —
contrato assinado, ata, plano de contratação — e o radar não é sobre o passado:
ele é sobre o que ainda dá para disputar. Trazer os doze encheria o espelho com
onze entidades que nenhuma tela lê.

## Três coisas medidas contra a API de produção, em 08/09/2026

**Não precisa de credencial.** A especificação DECLARA um `bearerAuth`, e por
isso a dúvida existia. Declarar não é exigir: uma chamada sem cabeçalho nenhum
volta 400 de validação de PARÂMETRO — não 401. O `bearerAuth` é das APIs de
manutenção, que os órgãos usam para publicar. Este é o único conector do
produto que não depende de terceiro para começar.

**A API não filtra por palavra.** Nem por CNAE, nem por código de item. Os
filtros são data, UF, município, CNPJ e modalidade — todos estruturados. A
triagem por "vigilância" é NOSSA, depois de baixar, e é a única regra de negócio
que este arquivo tem. Medido na Bahia: 2.164 editais abertos, e cerca de 1% cita
segurança. Sem a triagem o radar recebe merenda escolar e obra de praça.

**Há limite de requisição.** Sete chamadas em treze segundos devolvem 429. Uma
por segundo passou em seis de seis. Por isso `PAUSA_ENTRE_PAGINAS`: não é
gentileza, é a diferença entre uma carga que roda de madrugada inteira e uma que
é bloqueada na terceira página todo dia.

**E, além do limite, a fonte é instável** — medido no mesmo dia, mais tarde:
seis chamadas espaçadas de 2 a 5 s em 200, depois um `500` que levou 30 s e um
`503` imediato, sem nenhum cabeçalho de limite em nenhuma resposta. Não é o
freio da API: é o serviço oscilando. Numa varredura de 27 estados isso deixa de
ser azar e vira rotina, e é por isso que `coletar` isola a falha por UF.

## `dataFinal` é o horizonte, e não a janela da carga

Todo conector recebe `Janela(de, ate)` e a repassa à fonte. Aqui `de` não tem
uso: o endpoint devolve o que está aberto AGORA, e "aberto desde" não é uma
pergunta que ele responda. `ate` vira `dataFinal` — até quando aceitar
encerramento de proposta. Sem janela, o horizonte é `HORIZONTE_PADRAO_DIAS`.

## Este conector não escreve `Oportunidade`

Ele grava `EditalPublico`, no espelho. A `Oportunidade` é o registro da EMPRESA
— quem decidiu, por quê, e o motivo do descarte —, e uma recarga noturna que
sobrescrevesse esse texto apagaria a única coisa que o radar guarda de verdade.
Ver o cabeçalho de `resultados.models.EditalPublico`.
"""

from __future__ import annotations

import logging
import time
import unicodedata
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.conf import settings

from ..transporte import PAGINAS_MAXIMAS, TransporteError, pedir
from .base import ConectorBase, Janela, Registro

logger = logging.getLogger("cargas")

BASE = "https://pncp.gov.br/api/consulta"
CAMINHO = "/v1/contratacoes/proposta"

#: A API aceita de 10 a 50 por página, e recusa fora disso com 400. Cinquenta
#: para fazer o menor número de requisições possível — ver a pausa abaixo.
TAMANHO_PAGINA = 50

#: Segundos entre páginas. Medido: 7 requisições em 13 s → 429; 1 por segundo
#: passa. Um segundo e meio é o mesmo número com folga, porque a carga roda de
#: madrugada e ninguém está esperando por ela.
PAUSA_ENTRE_PAGINAS = 1.5

#: Até quando olhar, quando a janela vem aberta.
#:
#: Medido em 08/09/2026, em SP+MG+BA somados: 30 dias trazem 9.887 editais,
#: 180 trazem 12.168, 365 trazem 13.771. Ou seja — encurtar o horizonte de seis
#: meses para um mês economiza 19% do volume e custa TODO o aviso antecipado.
#: Não é a alavanca; a maioria do que está aberto encerra em semanas de qualquer
#: jeito.
HORIZONTE_PADRAO_DIAS = 180

#: A espera longa, depois que o recuo curto do transporte (1 s, 2 s) não bastou.
#:
#: Medido na primeira varredura real: as 12 ÚLTIMAS UFs caíram em sequência,
#: quase todas em 429 — e minutos depois as MESMAS consultas responderam 200 sem
#: nada ter mudado do nosso lado. A janela do limite é de minuto, não de
#: segundo, e por isso o recuo do transporte não a alcança: três tentativas
#: somam três segundos.
PAUSA_APOS_LIMITE = 60.0

#: Quantas esperas longas por UF. Duas: a primeira cobre a janela que acabou de
#: fechar, a segunda cobre a de quem chegou junto. A terceira só atrasaria as
#: UFs seguintes — e a UF perdida já não derruba a carga.
RESPIROS_POR_UF = 2

#: As 27 unidades da federação. A lista fica aqui, e não em `settings`, porque
#: ela não muda — o que muda é quais delas interessam, e isso é `PNCP_UFS`.
TODAS_AS_UFS: tuple[str, ...] = (
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS",
    "MG", "PA", "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC",
    "SP", "SE", "TO",
)

#: A TRIAGEM. Definida pelo comercial em 08/09/2026, e sobrescritível por
#: `PNCP_TERMOS` no settings.
#:
#: Em `settings` e não só aqui porque esta lista É o produto deste conector: ela
#: decide o que aparece no radar, ela vai errar nas primeiras semanas, e ajustá-la
#: não pode exigir um deploy. `EditalPublico.termo_casado` guarda qual termo
#: trouxe cada linha — é com ele que se vê o ruído e se poda a lista.
#:
#: Sem acento e em minúscula: a comparação normaliza os dois lados, e um termo
#: acentuado aqui simplesmente nunca casaria.
TERMOS_PADRAO: tuple[str, ...] = (
    "vigilancia",
    "seguranca patrimonial",
    "vigia",
    "portaria",
    "monitoramento eletronico",
    "controle de acesso",
    "cftv",
    "cameras",
    "alarme",
    "gerador de neblina",
    "seguranca privada",
    "automacao",
    "desenvolvimento de software para seguranca eletronica",
    "seguranca eletronica",
)


def sem_acento(texto: str) -> str:
    """Minúscula e sem diacrítico, para a triagem casar "vigilância"."""
    decomposto = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn")


class ConectorPNCP(ConectorBase):
    chave = "pncp"

    def disponivel(self) -> bool:
        """SEMPRE disponível — é o único assim, e a razão é a fonte ser pública.

        `disponivel()` responde "este ambiente tem o que a fonte exige". Aqui a
        fonte não exige nada: sem credencial, sem dicionário de ids, sem host
        para configurar. Devolver `False` por precaução faria a tela 99 dizer
        "não configurada" sobre a única fonte que não tem o que configurar.
        """
        return True

    # ── Coleta ──────────────────────────────────────────────────────

    @property
    def ufs(self) -> tuple[str, ...]:
        return tuple(getattr(settings, "PNCP_UFS", None) or TODAS_AS_UFS)

    @property
    def termos(self) -> tuple[str, ...]:
        crus = getattr(settings, "PNCP_TERMOS", None) or TERMOS_PADRAO
        return tuple(sem_acento(t) for t in crus if t and t.strip())

    def coletar(self, janela: Janela) -> Iterable[dict]:
        """As 27 UFs, e uma que cai NÃO leva as outras junto.

        Cada UF é uma consulta independente, e o PNCP responde 500 ou 503 de vez
        em quando sem aviso (medido em 08/09/2026: seis chamadas seguidas em
        200, depois um 500 que demorou 30 s e um 503 imediato). Numa varredura
        de 27 estados, a chance de nenhum tropeço é baixa — e do jeito ingênuo,
        o tropeço no terceiro estado descartaria os outros vinte e quatro.

        Por isso a falha de UF é anotada e a varredura segue. No fim, se houve
        falha, este método LEVANTA: o carregador já sabe o que fazer com isso —
        com linhas gravadas a carga fica `parcial`, sem nenhuma fica `falha`, e
        os dois casos aparecem na tela 99 com o motivo. O que não pode acontecer
        é a carga se declarar completa tendo pulado sete estados.
        """
        limite = janela.ate or (
            date.today() + timedelta(days=HORIZONTE_PADRAO_DIAS)
        )
        falharam: list[str] = []
        for indice, uf in enumerate(self.ufs):
            if indice:
                self._descansar()
            try:
                yield from self._paginar(uf, limite)
            except TransporteError as erro:
                logger.warning("pncp: %s não veio (%s)", uf, erro)
                falharam.append(uf)

        if falharam:
            raise TransporteError(
                f"O PNCP não respondeu por {len(falharam)} de "
                f"{len(self.ufs)} UF(s): {', '.join(falharam)}."
            )

    def _paginar(self, uf: str, limite: date) -> Iterable[dict]:
        """As páginas de uma UF, com respiro quando o limite fecha a porta.

        O respiro repete a MESMA página, e não a UF inteira: o carregador é
        idempotente e não duplicaria nada, mas reler 60 páginas de São Paulo
        para chegar onde já estávamos gastaria justamente o que está em falta.
        """
        pagina = 1
        respiros = 0
        while True:
            if pagina > PAGINAS_MAXIMAS:
                raise TransporteError(
                    f"{uf}: passou de {PAGINAS_MAXIMAS} páginas no PNCP."
                )
            url = (
                f"{BASE}{CAMINHO}?dataFinal={limite:%Y%m%d}"
                f"&uf={uf}&pagina={pagina}&tamanhoPagina={TAMANHO_PAGINA}"
            )
            try:
                corpo = pedir(url)
            except TransporteError as erro:
                if respiros >= RESPIROS_POR_UF:
                    raise
                respiros += 1
                logger.warning(
                    "pncp: %s pág. %s → %s; respirando (%s de %s)",
                    uf, pagina, erro, respiros, RESPIROS_POR_UF,
                )
                self._respirar()
                continue
            itens = corpo.get("data") or []
            for item in itens:
                # A UF vai junto porque a resposta a traz aninhada em
                # `unidadeOrgao`, e um item sem órgão perderia o estado — que é
                # justamente o recorte que o comercial usa.
                yield {"uf": uf, "item": item}

            total = corpo.get("totalPaginas") or 0
            if pagina >= total or not itens:
                return
            pagina += 1
            self._descansar()

    def _descansar(self) -> None:
        """Isolado para o teste não esperar de verdade."""
        time.sleep(PAUSA_ENTRE_PAGINAS)

    def _respirar(self) -> None:
        """A espera longa. Separada de `_descansar` porque são coisas
        diferentes: uma é o ritmo normal, a outra é reação a uma recusa."""
        time.sleep(PAUSA_APOS_LIMITE)

    # ── Normalização ────────────────────────────────────────────────

    def normalizar(self, bruto: Iterable[dict]) -> Iterable[Registro]:
        termos = self.termos
        for envelope in bruto:
            item = envelope.get("item") or {}
            objeto = item.get("objetoCompra") or ""
            termo = self._triar(objeto, termos)
            if termo is None:
                # Descartado na triagem NÃO é rejeitado: rejeitado é linha que
                # chegou torta e pede conserto na origem. Isto aqui é edital de
                # merenda escolar, que está perfeito e não é da empresa.
                continue

            numero = (item.get("numeroControlePNCP") or "").strip()
            if not numero:
                logger.warning("pncp: item sem numeroControlePNCP, ignorado")
                continue

            orgao = item.get("orgaoEntidade") or {}
            unidade = item.get("unidadeOrgao") or {}
            yield Registro(
                entidade="edital",
                chave_externa=numero,
                dados={
                    "numero_controle": numero,
                    "objeto": objeto.strip(),
                    "orgao": (orgao.get("razaoSocial") or "")[:200],
                    "unidade": (unidade.get("nomeUnidade") or "")[:200],
                    "uf": (unidade.get("ufSigla") or envelope.get("uf") or "")[:2],
                    "municipio": (unidade.get("municipioNome") or "")[:120],
                    "modalidade": (item.get("modalidadeNome") or "")[:80],
                    "valor_estimado": _decimal(item.get("valorTotalEstimado")),
                    "abertura_proposta": _instante(item.get("dataAberturaProposta")),
                    "encerramento_proposta": _instante(
                        item.get("dataEncerramentoProposta")
                    ),
                    "termo_casado": termo[:80],
                    "link": _link(item, numero),
                },
            )

    @staticmethod
    def _triar(objeto: str, termos: tuple[str, ...]) -> str | None:
        """O primeiro termo que casa, ou `None`.

        O PRIMEIRO e não todos: `termo_casado` existe para o comercial saber por
        que a linha entrou, e "casou com quatro termos" não ajuda a podar a
        lista. A ordem de `TERMOS_PADRAO` é a ordem de especificidade — o termo
        mais preciso vem antes do mais genérico.
        """
        alvo = sem_acento(objeto)
        for termo in termos:
            if termo in alvo:
                return termo
        return None


def _decimal(valor) -> Decimal | None:
    if valor in (None, ""):
        return None
    try:
        return Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _instante(texto) -> datetime | None:
    """`2026-09-23T17:00:00` → `datetime`. Sem fuso: o PNCP não manda um.

    Django avisa sobre datetime ingênuo quando `USE_TZ` está ligado, e por isso
    o valor é ancorado no fuso do projeto — que é o de Brasília, o mesmo em que
    o prazo do edital é contado.
    """
    if not texto:
        return None
    try:
        bruto = datetime.fromisoformat(str(texto))
    except (TypeError, ValueError):
        return None
    if bruto.tzinfo is not None:
        return bruto
    from django.utils import timezone

    return timezone.make_aware(bruto)


def _link(item: dict, numero: str) -> str:
    """O endereço do edital.

    `linkSistemaOrigem` veio NULO no item conferido, então não dá para contar
    com ele. O caminho público do PNCP é montável a partir do número de
    controle, que tem a forma `<cnpj>-1-<sequencial>/<ano>`.

    Se o formato não for o esperado, devolve vazio — um link quebrado numa tela
    de oportunidade é pior que a ausência dele: a pessoa clica, cai em 404 e
    conclui que o edital não existe mais.
    """
    origem = (item.get("linkSistemaOrigem") or "").strip()
    if origem.startswith("http"):
        return origem[:500]
    try:
        esquerda, ano = numero.split("/")
        cnpj, _, sequencial = esquerda.split("-")
        return (
            f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{int(sequencial)}"
        )
    except (ValueError, AttributeError):
        return ""
