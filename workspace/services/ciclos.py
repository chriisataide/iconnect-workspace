"""O ciclo de planejamento: a pauta, a reunião e a ATA.

## O que a tela é

Uma **pasta ordenada**, como no benchmark: CP01, CP02, … cada uma apontando para
uma tela viva do produto, com o carimbo de frescor do destino ao lado. Não é um
dashboard e não é um calendário — é a ordem de olhar, registrada.

## A fronteira passa entre o GET e o POST

Ler a pauta é consulta: quem tem `cic.ler` e o papel da plateia abre e lê. Abrir
a reunião, anotar o que se disse e fechar a ATA é **assinar em nome da empresa**,
e exige `cic.conduzir`. É a restrição 7 do produto, literal.

## Fonte atrasada NÃO impede a reunião

A conferência de frescor roda na abertura e devolve uma lista de impedimentos.
Ela **não trava**: travar a reunião de setembro porque a carga do monday falhou
às três da manhã seria transformar um problema de infraestrutura em um problema
de governança. O que ela faz é pior para quem esconde e melhor para quem decide:
os impedimentos ficam congelados na ocorrência, aparecem no topo da tela e vão
inteiros para a ATA. Quem decidiu com número velho decidiu sabendo.

O preço é um segundo POST — quem abre confirma que viu a lista. Um clique, e um
registro de que ele existiu.

## O carimbo é congelado, nunca recalculado

`AnotacaoEtapa` copia o texto do carimbo no instante da anotação; a ATA copia os
carimbos no instante do fechamento. Reler não recalcula.

Uma ATA que recalculasse o frescor diria, seis meses depois, que a decisão foi
tomada diante de um dado de hoje. Ela foi tomada diante de um dado de três dias
atrás — e é exatamente essa a informação que uma auditoria procura. Ver ADR-030.

## Nenhuma chamada de rede

Como em toda tela do `workspace`: o carimbo vem do contrato `providers.frescor`,
que lê o espelho local. A pauta abre numa reunião, e uma tela que depende de uma
API de terceiro é uma tela que cai no meio da reunião.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from django.db import transaction
from django.utils import timezone

from identidade.services.autorizacao import ESCOPO_GLOBAL, escopo_de, pode
from workspace import enderecamento
from workspace.models.ciclo import (
    AnotacaoEtapa,
    CicloPlanejamento,
    EtapaCiclo,
    OcorrenciaCiclo,
    SituacaoOcorrencia,
)
from workspace.models.conteudo import (
    Documento,
    SituacaoDocumento,
    TipoDocumento,
)
from workspace.services import frescor as fr

PERMISSAO = "cic.ler"
PERMISSAO_CONDUZIR = "cic.conduzir"

#: Quantas ocorrências fechadas a tela de um ciclo lista. O histórico inteiro
#: mora no acervo, em ATA — repetí-lo aqui faria duas listas do mesmo fato, e a
#: segunda envelheceria.
HISTORICO = 12


class SemCiclos(Exception):
    """Esta pessoa não participa de ciclo nenhum."""


class CicloError(Exception):
    """A ação pedida não pode acontecer, e a mensagem diz por quê."""


# ── Permissão ───────────────────────────────────────────────────────


def papeis_de(pessoa, cache: dict | None = None) -> set[str]:
    """As chaves de papel que esta pessoa ocupa hoje."""
    if pessoa is None or not getattr(pessoa, "is_authenticated", False):
        return set()
    from identidade.models import AtribuicaoPapel

    cache = cache if cache is not None else {}
    guardado = cache.setdefault("papeis_de_ciclo", {})
    if pessoa.pk in guardado:
        return guardado[pessoa.pk]

    chaves = set(
        AtribuicaoPapel.objects.vigentes()
        .filter(user=pessoa, papel__ativo=True)
        .values_list("papel__chave", flat=True)
    )
    guardado[pessoa.pk] = chaves
    return chaves


def _global(pessoa, permissao: str, cache: dict | None = None) -> bool:
    return escopo_de(pessoa, permissao, cache=cache) == ESCOPO_GLOBAL


def pode_ler(ciclo: CicloPlanejamento, pessoa, cache: dict | None = None) -> bool:
    """Vê a pauta e as ocorrências deste ciclo.

    Quem tem `cic.ler.global` vê todos — é a diretoria olhando o calendário
    inteiro. Os demais veem os ciclos cuja plateia eles integram.

    Ciclo sem `papeis_leitores` é de ninguém além do escopo global. NÃO é "de
    todo mundo": a pauta de uma reunião de diretoria com plateia vazia ficaria
    aberta, e o padrão errado num campo em branco é o defeito que ninguém vê.
    """
    if not pode(pessoa, PERMISSAO, cache=cache):
        return False
    if _global(pessoa, PERMISSAO, cache=cache):
        return True
    plateia = {p for p in (ciclo.papeis_leitores or []) if p}
    if ciclo.papel_condutor:
        plateia.add(ciclo.papel_condutor)
    return bool(plateia & papeis_de(pessoa, cache=cache))


def pode_conduzir(ciclo: CicloPlanejamento, pessoa, cache: dict | None = None) -> bool:
    """Abre, anota e fecha. É o lado de lá da fronteira do POST."""
    if not pode(pessoa, PERMISSAO_CONDUZIR, cache=cache):
        return False
    if _global(pessoa, PERMISSAO_CONDUZIR, cache=cache):
        return True
    if not ciclo.papel_condutor:
        # Ciclo que não declara condutor não é conduzido por quem passou perto.
        return False
    return ciclo.papel_condutor in papeis_de(pessoa, cache=cache)


def ciclos_de(pessoa, cache: dict | None = None) -> list[CicloPlanejamento]:
    """Os ciclos ATIVOS que esta pessoa vê. Levanta `SemCiclos` quando é nenhum."""
    if not pode(pessoa, PERMISSAO, cache=cache):
        raise SemCiclos("Ciclo de planejamento é de quem participa dele.")

    visiveis = [
        c
        for c in CicloPlanejamento.objects.filter(ativo=True)
        if pode_ler(c, pessoa, cache=cache)
    ]
    if not visiveis:
        # 403, e não lista vazia. Lista vazia diria "a empresa não tem ciclo de
        # planejamento" para quem apenas não está na sala — e é uma frase que
        # alguém repete numa reunião.
        raise SemCiclos("Você não participa de nenhum ciclo de planejamento.")
    return visiveis


def tem_acesso(pessoa, cache: dict | None = None) -> bool:
    try:
        ciclos_de(pessoa, cache=cache)
    except SemCiclos:
        return False
    return True


def pode_ler_ata(documento: Documento, pessoa, cache: dict | None = None) -> bool:
    """A ATA é do ciclo de onde ela saiu.

    Chamada pelo app de conteúdo por importação preguiçosa — o `publico_alvo`
    do documento já carrega `papel:<chave>` e resolve vitrine, leitura e busca
    sozinho; isto é a segunda tranca, para o caso de alguém publicar uma ATA por
    outro caminho.
    """
    ocorrencia = (
        OcorrenciaCiclo.objects.filter(ata=documento).select_related("ciclo").first()
    )
    if ocorrencia is None:
        # ATA órfã: o ciclo foi apagado e a ocorrência foi junto. O
        # `publico_alvo` do documento continua valendo — e quem chama já o
        # conferiu. Negar aqui trancaria no acervo uma ATA que ninguém mais
        # poderia reabrir, o que é pior do que o risco que a segunda tranca
        # cobre.
        return True
    return pode_ler(ocorrencia.ciclo, pessoa, cache=cache)


# ── A pauta ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Passo:
    """Uma etapa pronta para a tela: o endereço, o carimbo e o que se disse."""

    etapa: EtapaCiclo
    tela: object | None
    carimbos: tuple = ()
    anotacoes: tuple = ()

    @property
    def codigo(self) -> str:
        return self.etapa.codigo

    @property
    def url(self) -> str:
        return self.tela.url if self.tela else ""

    @property
    def endereco_conhecido(self) -> bool:
        """`False` quando a etapa aponta para um código que não existe mais.

        A etapa continua legível — a pauta não some porque uma tela foi
        removida. O que a tela diz é "endereço desconhecido", que é a verdade e
        é acionável, em vez de um link para lugar nenhum.
        """
        return bool(self.etapa.tela) and self.tela is not None

    @property
    def carimbo(self):
        """O carimbo que representa a etapa — o primeiro em alerta, se houver.

        Uma etapa pode apontar para uma tela com dois blocos de fontes
        diferentes. Na pauta cabe um; e o que interessa a quem vai apresentar é
        o pior deles, não o primeiro da lista.
        """
        if not self.carimbos:
            return None
        for c in self.carimbos:
            if c.alerta:
                return c
        return self.carimbos[0]

    @property
    def em_alerta(self) -> bool:
        c = self.carimbo
        return bool(c and c.alerta)


def tela_de(etapa: EtapaCiclo):
    """A `Tela` do endereçamento, ou `None`. Nunca levanta."""
    if not etapa.tela:
        return None
    return enderecamento.por_codigo(etapa.tela)


def carimbos_de(etapa: EtapaCiclo) -> tuple:
    """Os carimbos dos blocos agregados do destino desta etapa.

    Tela sem bloco agregado não ganha carimbo. É deliberado: inventar um "em
    tempo real" para a tela de Reservas ensinaria a ler o carimbo como enfeite,
    e o carimbo existe justamente para ser lido nas telas em que ele muda a
    decisão.
    """
    tela = tela_de(etapa)
    if tela is None:
        return ()
    return tuple(fr.carimbos_de(tela.url_name).values())


def pauta(ciclo: CicloPlanejamento, ocorrencia: OcorrenciaCiclo | None = None) -> list[Passo]:
    """Os passos do ciclo, na ordem de apresentar."""
    por_etapa: dict[int, list] = {}
    if ocorrencia is not None:
        for anotacao in ocorrencia.anotacoes.select_related("autor", "etapa"):
            por_etapa.setdefault(anotacao.etapa_id, []).append(anotacao)

    return [
        Passo(
            etapa=etapa,
            tela=tela_de(etapa),
            carimbos=carimbos_de(etapa),
            anotacoes=tuple(por_etapa.get(etapa.pk, ())),
        )
        for etapa in ciclo.etapas.all()
    ]


# ── A conferência de frescor ────────────────────────────────────────


def conferir(ciclo: CicloPlanejamento) -> list[dict]:
    """As fontes atrasadas ou caídas das etapas OBRIGATÓRIAS.

    Devolve dicionários de texto e não objetos: o resultado é congelado na
    ocorrência, e um objeto congelado envelhece junto com o código que o define.
    """
    impedimentos = []
    for passo in pauta(ciclo):
        if not passo.etapa.obrigatoria:
            continue
        for carimbo in passo.carimbos:
            if not carimbo.alerta and carimbo.conhecido:
                continue
            impedimentos.append(
                {
                    "etapa": passo.etapa.codigo,
                    "titulo": passo.etapa.titulo,
                    "carimbo": carimbo.texto,
                    "motivo": carimbo.motivo
                    or ("Nenhuma carga registrada." if not carimbo.conhecido else ""),
                }
            )
    return impedimentos


# ── Abrir, anotar, fechar ───────────────────────────────────────────


def ocorrencia_de(ciclo: CicloPlanejamento, ano: int, mes: int) -> OcorrenciaCiclo | None:
    return ciclo.ocorrencias.filter(ano=ano, mes=mes).select_related("ata").first()


@transaction.atomic
def abrir(
    ciclo: CicloPlanejamento,
    pessoa,
    ano: int,
    mes: int,
    confirmado: bool = False,
    cache: dict | None = None,
) -> OcorrenciaCiclo:
    """Abre a reunião da competência. Idempotente: reabrir devolve a que existe.

    Levanta `CicloError` com a lista de impedimentos quando há fonte atrasada e
    `confirmado` é falso. NÃO é um bloqueio: o segundo POST abre. O que o
    primeiro faz é garantir que ninguém abriu sem ver.
    """
    if not pode_conduzir(ciclo, pessoa, cache=cache):
        raise CicloError("Conduzir um ciclo exige o papel que responde por ele.")
    if not 1 <= mes <= 12:
        raise CicloError("Competência inválida.")

    existente = ocorrencia_de(ciclo, ano, mes)
    if existente is not None:
        return existente

    impedimentos = conferir(ciclo)
    if impedimentos and not confirmado:
        erro = CicloError(
            f"{len(impedimentos)} fonte(s) com atraso nesta pauta. "
            "Confirme para abrir mesmo assim."
        )
        # A lista viaja com a exceção: a view a mostra, e o botão seguinte
        # confirma. Repetir a conferência na view custaria a varredura duas
        # vezes e — pior — poderia dar outra resposta.
        erro.impedimentos = impedimentos
        raise erro

    return OcorrenciaCiclo.objects.create(
        ciclo=ciclo,
        ano=ano,
        mes=mes,
        conduzida_por=pessoa,
        impedimentos=impedimentos,
    )


def anotar(
    ocorrencia: OcorrenciaCiclo,
    etapa: EtapaCiclo,
    pessoa,
    texto: str,
    encaminhamento: str = "",
    prazo: date | None = None,
    cache: dict | None = None,
) -> AnotacaoEtapa:
    """Registra o que se disse diante desta etapa, com o carimbo do momento."""
    if not pode_conduzir(ocorrencia.ciclo, pessoa, cache=cache):
        raise CicloError("Anotar em nome da reunião exige conduzi-la.")
    if ocorrencia.fechada:
        # Reunião fechada tem ATA, e ATA não recebe emenda silenciosa. Corrigir
        # o registro é assunto da reunião seguinte, onde fica visível.
        raise CicloError("Esta reunião está fechada. A ATA já foi gerada.")
    if etapa.ciclo_id != ocorrencia.ciclo_id:
        # Sem isto, um POST com o id de uma etapa de OUTRO ciclo escreveria numa
        # pauta alheia — o IDOR clássico, pela porta do formulário.
        raise CicloError("Esta etapa não é deste ciclo.")
    texto = (texto or "").strip()
    if not texto:
        raise CicloError("A anotação está vazia.")

    carimbos = carimbos_de(etapa)
    carimbo = next((c for c in carimbos if c.alerta), carimbos[0] if carimbos else None)

    return AnotacaoEtapa.objects.create(
        ocorrencia=ocorrencia,
        etapa=etapa,
        texto=texto,
        encaminhamento=(encaminhamento or "").strip()[:300],
        prazo=prazo,
        autor=pessoa,
        carimbo_fonte=carimbo.fonte if carimbo else "",
        carimbo_texto=carimbo.texto if carimbo else "",
        carimbo_alerta=bool(carimbo and carimbo.alerta),
    )


@transaction.atomic
def fechar(ocorrencia: OcorrenciaCiclo, pessoa, cache: dict | None = None) -> Documento:
    """Fecha a reunião e gera a ATA no acervo. Idempotente."""
    if not pode_conduzir(ocorrencia.ciclo, pessoa, cache=cache):
        raise CicloError("Fechar a reunião exige conduzi-la.")
    if ocorrencia.fechada and ocorrencia.ata_id:
        # Fechar duas vezes não gera duas ATAs. Duas ATAs da mesma reunião no
        # acervo é a pior forma de ambiguidade: as duas parecem oficiais.
        return ocorrencia.ata
    if not ocorrencia.ciclo.alvo_da_ata:
        raise CicloError(
            "Este ciclo não declara quem lê a ATA. Sem plateia, o documento "
            "nasceria público."
        )

    agora = timezone.now()
    documento = Documento.objects.create(
        slug=_slug_da_ata(ocorrencia),
        tipo=TipoDocumento.ATA,
        titulo=f"ATA · {ocorrencia.ciclo.nome} · {ocorrencia.competencia}",
        categoria="Ciclo de planejamento",
        resumo=(
            f"O que foi apresentado e o que ficou encaminhado na reunião de "
            f"{ocorrencia.competencia}."
        )[:300],
        corpo=corpo_da_ata(ocorrencia, fechada_em=agora),
        dono=pessoa,
        versao="1",
        publico_alvo=ocorrencia.ciclo.alvo_da_ata,
        # ATA NÃO é leitura obrigatória. Obrigar a confirmação transformaria a
        # bandeja de leitura de toda a plateia num contador mensal que ninguém
        # zera — e a leitura obrigatória perde o sentido quando vira rotina.
        leitura_obrigatoria=False,
        vigencia_inicio=timezone.localdate(),
        situacao=SituacaoDocumento.VIGENTE,
    )

    ocorrencia.situacao = SituacaoOcorrencia.FECHADA
    ocorrencia.fechada_em = agora
    ocorrencia.ata = documento
    ocorrencia.save(update_fields=["situacao", "fechada_em", "ata"])
    return documento


def _slug_da_ata(ocorrencia: OcorrenciaCiclo) -> str:
    base = f"ata-{ocorrencia.ciclo.chave}-{ocorrencia.ano}-{ocorrencia.mes:02d}"[:80]
    if not Documento.objects.filter(slug=base).exists():
        return base
    # Só acontece quando um ciclo foi apagado e recriado com a mesma chave. Vale
    # um sufixo em vez de uma exceção: a reunião aconteceu, e recusar a ATA
    # perderia o registro dela por causa de um endereço.
    for sufixo in range(2, 100):
        tentativa = f"{base[:76]}-{sufixo}"
        if not Documento.objects.filter(slug=tentativa).exists():
            return tentativa
    raise CicloError("Não foi possível gerar um endereço para esta ATA.")


def corpo_da_ata(ocorrencia: OcorrenciaCiclo, fechada_em=None) -> str:
    """O texto da ATA. Congelado: nada aqui é recalculado na leitura.

    A ordem é a da pauta, e cada item traz o carimbo que a tela tinha. Um
    parágrafo de texto e não uma tabela: a ATA é lida por gente, inclusive fora
    do produto, colada num e-mail.
    """
    ciclo = ocorrencia.ciclo
    fechada_em = fechada_em or timezone.now()
    linhas = [
        f"# {ciclo.nome} — {ocorrencia.competencia}",
        "",
        f"Aberta em {timezone.localtime(ocorrencia.aberta_em):%d/%m/%Y %H:%M}, "
        f"fechada em {timezone.localtime(fechada_em):%d/%m/%Y %H:%M}.",
    ]
    if ocorrencia.conduzida_por_id:
        linhas.append(f"Conduzida por {ocorrencia.conduzida_por.nome}.")
    if ciclo.publico:
        linhas.append(f"Plateia: {ciclo.publico}.")

    if ocorrencia.impedimentos:
        # Os impedimentos vêm ANTES da pauta na ATA, e é deliberado: quem lê
        # precisa saber com que dado a sala decidiu antes de ler o que ela
        # decidiu. Depois, viraria rodapé.
        linhas += ["", "## Fontes com atraso na abertura", ""]
        for imp in ocorrencia.impedimentos:
            motivo = f" — {imp['motivo']}" if imp.get("motivo") else ""
            linhas.append(f"- {imp['etapa']} · {imp['titulo']}: {imp['carimbo']}{motivo}")

    linhas += ["", "## Pauta", ""]
    for passo in pauta(ciclo, ocorrencia):
        endereco = f" (tela {passo.etapa.tela})" if passo.etapa.tela else ""
        linhas.append(f"### {passo.etapa.codigo} · {passo.etapa.titulo}{endereco}")
        if passo.etapa.pergunta:
            linhas.append(f"*{passo.etapa.pergunta}*")
        if not passo.anotacoes:
            # "Sem anotação" é escrito, e não omitido. Etapa que some da ATA
            # deixa a dúvida entre "não foi apresentada" e "não teve registro",
            # e as duas pedem coisas diferentes na reunião seguinte.
            linhas += ["", "Sem anotação.", ""]
            continue
        for anotacao in passo.anotacoes:
            carimbo = f" [{anotacao.carimbo_texto}]" if anotacao.carimbo_texto else ""
            linhas.append("")
            linhas.append(f"{anotacao.texto}{carimbo}")
            if anotacao.encaminhamento:
                prazo = f" (até {anotacao.prazo:%d/%m/%Y})" if anotacao.prazo else ""
                linhas.append(f"**Encaminhamento:** {anotacao.encaminhamento}{prazo}")
        linhas.append("")

    return "\n".join(linhas).strip()


# ── O que a tela recebe ─────────────────────────────────────────────


@dataclass
class Painel:
    ciclos: list = field(default_factory=list)
    abertas: list = field(default_factory=list)


def painel(pessoa, cache: dict | None = None) -> dict:
    """A lista de ciclos e as reuniões abertas. Levanta `SemCiclos`."""
    ciclos = ciclos_de(pessoa, cache=cache)
    abertas = list(
        OcorrenciaCiclo.objects.filter(
            ciclo__in=ciclos, situacao=SituacaoOcorrencia.ABERTA
        ).select_related("ciclo", "conduzida_por")
    )
    return {
        "ciclos": [
            {
                "ciclo": c,
                "etapas": c.etapas.count(),
                "conduzo": pode_conduzir(c, pessoa, cache=cache),
                "ultima": c.ocorrencias.first(),
            }
            for c in ciclos
        ],
        "abertas": abertas,
    }


def competencia_corrente() -> tuple[int, int]:
    hoje = timezone.localdate()
    return hoje.year, hoje.month


def tela_do_ciclo(
    ciclo: CicloPlanejamento,
    pessoa,
    ano: int | None = None,
    mes: int | None = None,
    codigo_da_etapa: str = "",
    cache: dict | None = None,
) -> dict:
    """Tudo o que a tela de um ciclo mostra — com ou sem reunião aberta."""
    if ano is None or mes is None:
        ano, mes = competencia_corrente()

    ocorrencia = ocorrencia_de(ciclo, ano, mes)
    passos = pauta(ciclo, ocorrencia)

    # A etapa escolhida — o "uma de cada vez" da apresentação. Código
    # desconhecido cai no primeiro passo em vez de dar 404: no meio de uma
    # reunião, um erro de digitação na barra de endereço não pode virar uma
    # tela de erro projetada na parede.
    atual = None
    if codigo_da_etapa:
        atual = next((p for p in passos if p.codigo == codigo_da_etapa), None)
        if atual is None and passos:
            atual = passos[0]

    indice = passos.index(atual) if atual is not None else -1
    return {
        "ciclo": ciclo,
        "ano": ano,
        "mes": mes,
        "competencia": f"{mes:02d}/{ano}",
        "ocorrencia": ocorrencia,
        "passos": passos,
        "passo": atual,
        "anterior": passos[indice - 1] if indice > 0 else None,
        "proximo": passos[indice + 1] if 0 <= indice < len(passos) - 1 else None,
        "posicao": indice + 1,
        "total_de_passos": len(passos),
        "conduzo": pode_conduzir(ciclo, pessoa, cache=cache),
        "historico": list(
            ciclo.ocorrencias.filter(situacao=SituacaoOcorrencia.FECHADA)
            .select_related("ata")[:HISTORICO]
        ),
        # A conferência de frescor de AGORA, para quem ainda não abriu. Depois de
        # aberta, o que vale é a lista congelada na ocorrência — recalcular faria
        # o mês ruim parecer limpo assim que a carga voltasse.
        "impedimentos": (
            ocorrencia.impedimentos if ocorrencia else conferir(ciclo)
        ),
        "impedimentos_congelados": ocorrencia is not None,
    }
