"""A implementação dos contratos de resultado — o espelho respondendo.

Somente leitura, como todo provider deste repositório. Escrita é do carregador,
em `cargas`.

## Onde o escopo é aplicado

Aqui, no `WHERE`. O `Escopo` chega montado pela view a partir do que `pode()`
respondeu, e vira `filter()` antes de qualquer soma. Recortar depois de somar
faria o total da empresa vazar para quem só pode ver a própria regional — e
vazaria no número, que é justamente onde ninguém procura vazamento.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from workspace.providers.resultados import (
    ApontamentoDTO,
    AvaliacaoDTO,
    CompetenciaDTO,
    ConsolidadoDTO,
    ContratoDTO,
    Escopo,
    MarcoDTO,
    MovimentacaoDTO,
    MovimentacaoPessoasDTO,
    Procedencia,
    ProjetoDTO,
    ProvedorCarteira,
    ProvedorJornada,
    ProvedorPessoas,
    ProvedorProjetos,
    ProvedorResultadoFinanceiro,
    ProvedorSatisfacao,
    QuadroDTO,
)

from . import services as svc
from .models import (
    Apontamento,
    AvaliacaoCliente,
    CompetenciaResultado,
    Contrato,
    MarcoProjeto,
    Projeto,
    QuadroPessoas,
    StatusContrato,
)


def _recortar(consulta, escopo: Escopo | None, *, ate_o_contrato: str = ""):
    """Aplica o recorte. `None` ou vazio = a empresa inteira.

    `ate_o_contrato` é o caminho da FK até `Contrato` a partir do model
    consultado: `""` quando o próprio model É o contrato, `"contrato__"` quando
    ele aponta para um, `"projeto__contrato__"` quando aponta para quem aponta.

    Um parâmetro só, e não um por campo, porque regional, centro de custo e
    código moram TODOS no contrato — quem sabe chegar até ele sabe filtrar pelos
    três. Três parâmetros deixariam possível passar dois caminhos incoerentes.
    """
    if escopo is None or escopo.tudo:
        return consulta
    condicao = Q()
    if escopo.regionais:
        condicao |= Q(**{f"{ate_o_contrato}regional__in": escopo.regionais})
    if escopo.centros_custo:
        condicao |= Q(**{f"{ate_o_contrato}centro_custo__in": escopo.centros_custo})
    if escopo.contratos:
        condicao |= Q(**{f"{ate_o_contrato}codigo__in": escopo.contratos})
    return consulta.filter(condicao)


def _proc(registro) -> Procedencia:
    return registro.procedencia


class EspelhoLocal(
    ProvedorResultadoFinanceiro,
    ProvedorCarteira,
    ProvedorProjetos,
    ProvedorPessoas,
    ProvedorJornada,
    ProvedorSatisfacao,
):
    """Uma classe para os seis contratos.

    Seis classes seriam seis arquivos com o mesmo import e o mesmo `_escopo`.
    O que justifica separar os CONTRATOS — cada um é uma pergunta com dono
    possivelmente diferente — não justifica separar a implementação enquanto o
    dono é o mesmo espelho.
    """

    key = "espelho"

    # ── Financeiro ──────────────────────────────────────────────────

    def serie_competencia(self, escopo, de: date, ate: date) -> list[CompetenciaDTO]:
        consulta = CompetenciaResultado.objects.select_related("contrato").filter(
            Q(ano__gt=de.year) | Q(ano=de.year, mes__gte=de.month),
            Q(ano__lt=ate.year) | Q(ano=ate.year, mes__lte=ate.month),
        )
        # `regional` não existe em `CompetenciaResultado` — ela mora no
        # contrato. Recortar por regional aqui exige atravessar a FK, e a linha
        # de centro de custo (sem contrato) não tem regional nenhuma: ela fica
        # de fora do recorte regional, e é o certo — ela é da empresa.
        consulta = self._competencias_no_escopo(consulta, escopo)
        return [self._competencia_dto(linha) for linha in consulta.order_by("ano", "mes")]

    def consolidado(self, escopo, competencia: date) -> ConsolidadoDTO | None:
        consulta = self._competencias_no_escopo(
            CompetenciaResultado.objects.all(), escopo
        )
        soma = svc.consolidar(consulta, competencia)
        if not soma["linhas"]:
            # `None` e não um DTO zerado: a faixa precisa dizer "—" e o motivo,
            # e um zero seria lido como "a empresa não faturou".
            return None
        return ConsolidadoDTO(
            procedencia=self._procedencia_do_conjunto(consulta),
            competencia=competencia,
            receita_bruta=soma["receita_bruta"],
            margem_contribuicao=soma["margem_contribuicao"],
            ebitda=soma["ebitda"],
            linhas=soma["linhas"],
        )

    def _competencias_no_escopo(self, consulta, escopo: Escopo | None):
        """O único recorte que NÃO usa `_recortar`, e por um motivo real.

        `CompetenciaResultado` tem `centro_custo` próprio, porque a linha de
        centro de custo não tem contrato nenhum — ela é o rateio que não pertence
        a cliente algum. Filtrar por `contrato__centro_custo` a deixaria de fora
        de todo recorte, e o total do centro de custo passaria a ser menor que a
        soma dos seus contratos.
        """
        if escopo is None or escopo.tudo:
            return consulta
        condicao = Q()
        if escopo.regionais:
            condicao |= Q(contrato__regional__in=escopo.regionais)
        if escopo.centros_custo:
            condicao |= Q(centro_custo__in=escopo.centros_custo)
        if escopo.contratos:
            condicao |= Q(contrato__codigo__in=escopo.contratos)
        return consulta.filter(condicao)

    def _competencia_dto(self, linha) -> CompetenciaDTO:
        return CompetenciaDTO(
            procedencia=_proc(linha),
            centro_custo=linha.centro_custo,
            ano=linha.ano,
            mes=linha.mes,
            receita_bruta=linha.receita_bruta,
            impostos=linha.impostos,
            custo_direto=linha.custo_direto,
            custo_indireto=linha.custo_indireto,
            margem_contribuicao=linha.margem_contribuicao,
            ebitda=linha.ebitda,
            ajuste_potencial=linha.ajuste_potencial,
            receita_orcada=linha.receita_orcada,
            custo_orcado=linha.custo_orcado,
            margem_orcada=linha.margem_orcada,
            contrato=linha.contrato.codigo if linha.contrato_id else "",
        )

    def _procedencia_do_conjunto(self, consulta) -> Procedencia:
        """A procedência de uma SOMA.

        Uma soma pode juntar linhas de fontes diferentes, e aí não há uma chave
        externa para citar. O que sobra de verdadeiro é a fonte — quando é uma
        só — e o instante da carga mais ANTIGA, que é a que limita a confiança
        no total. Citar a mais recente faria um consolidado com uma linha de
        ontem parecer inteiro de hoje.
        """
        fontes = set(consulta.values_list("fonte", flat=True).distinct())
        mais_antiga = consulta.order_by("importado_em").values_list(
            "importado_em", flat=True
        ).first()
        return Procedencia(
            fonte=next(iter(fontes)) if len(fontes) == 1 else "múltiplas",
            carregado_em=mais_antiga,
        )

    # ── Carteira ────────────────────────────────────────────────────

    def contratos(self, escopo, competencia: date | None = None) -> list[ContratoDTO]:
        consulta = _recortar(Contrato.objects.all(), escopo)
        return [self._contrato_dto(c, competencia) for c in consulta]

    def vencimentos(self, escopo, dias: int) -> list[ContratoDTO]:
        hoje = timezone.localdate()
        consulta = _recortar(
            Contrato.objects.filter(
                status__in=(StatusContrato.ATIVO, StatusContrato.EM_RENOVACAO),
                fim_vigencia__isnull=False,
                fim_vigencia__gte=hoje,
                fim_vigencia__lte=hoje + timedelta(days=dias),
            ),
            escopo,
        )
        return [self._contrato_dto(c) for c in consulta.order_by("fim_vigencia")]

    def movimentacoes(self, escopo, de: date, ate: date) -> MovimentacaoDTO:
        base = _recortar(Contrato.objects.all(), escopo)
        conquistas = base.filter(inicio_vigencia__gte=de, inicio_vigencia__lte=ate)
        perdas = base.filter(
            status=StatusContrato.ENCERRADO,
            fim_vigencia__gte=de,
            fim_vigencia__lte=ate,
        )
        renovacoes = base.filter(
            status=StatusContrato.EM_RENOVACAO,
            fim_vigencia__gte=de,
            fim_vigencia__lte=ate,
        )
        return MovimentacaoDTO(
            conquistas=[self._contrato_dto(c) for c in conquistas],
            renovacoes=[self._contrato_dto(c) for c in renovacoes],
            perdas=[self._contrato_dto(c) for c in perdas],
        )

    def _contrato_dto(self, contrato, competencia: date | None = None) -> ContratoDTO:
        layer = svc.layer_de(contrato, ate=competencia)
        linhas = list(contrato.competencias.order_by("-ano", "-mes")[:svc.MESES_DA_ROB])
        return ContratoDTO(
            procedencia=_proc(contrato),
            codigo=contrato.codigo,
            nome_cliente=contrato.nome_cliente,
            servico=contrato.servico,
            centro_custo=contrato.centro_custo,
            regional=contrato.regional,
            inicio_vigencia=contrato.inicio_vigencia,
            fim_vigencia=contrato.fim_vigencia,
            valor_mensal=contrato.valor_mensal,
            status=contrato.status,
            layer=layer.valor,
            # `None` quando não há receita na janela: 0% seria lido como
            # contrato no zero, e ele apareceria entre os deficitários.
            margem_contribuicao_pct=svc.margem_pct(linhas),
        )

    # ── Projetos ────────────────────────────────────────────────────

    def projetos(self, escopo, situacao: str = "") -> list[ProjetoDTO]:
        consulta = Projeto.objects.select_related("contrato")
        if situacao:
            consulta = consulta.filter(situacao=situacao)
        consulta = _recortar(consulta, escopo, ate_o_contrato="contrato__")
        return [self._projeto_dto(p) for p in consulta]

    def marcos_em_risco(self, escopo, dias: int) -> list[MarcoDTO]:
        hoje = timezone.localdate()
        consulta = MarcoProjeto.objects.select_related("projeto").filter(
            concluido_em__isnull=True,
            prazo__isnull=False,
            prazo__lte=hoje + timedelta(days=dias),
        )
        consulta = _recortar(consulta, escopo, ate_o_contrato="projeto__contrato__")
        return [
            MarcoDTO(
                procedencia=_proc(m),
                projeto=m.projeto.codigo,
                titulo=m.titulo,
                prazo=m.prazo,
                concluido_em=m.concluido_em,
                responsavel=m.responsavel,
            )
            for m in consulta.order_by("prazo")
        ]

    def _projeto_dto(self, projeto) -> ProjetoDTO:
        return ProjetoDTO(
            procedencia=_proc(projeto),
            codigo=projeto.codigo,
            nome=projeto.nome,
            cliente=projeto.cliente,
            contrato=projeto.contrato.codigo if projeto.contrato_id else "",
            responsavel=projeto.responsavel,
            situacao=projeto.situacao,
            inicio=projeto.inicio,
            prazo=projeto.prazo,
            percentual_concluido=projeto.percentual_concluido,
            bloqueado=projeto.bloqueado,
            motivo_bloqueio=projeto.motivo_bloqueio,
            movimentado_em=projeto.movimentado_em,
        )

    # ── Pessoas e jornada ───────────────────────────────────────────

    def quadro(self, escopo, competencia: date) -> QuadroDTO | None:
        """O agregado do escopo, e não a primeira linha que aparecer.

        Turnover e absenteísmo são somados PONDERADOS pelo efetivo: a média
        simples daria a um centro de cinco pessoas o mesmo peso de um de
        duzentas, e o indicador da empresa passaria a ser decidido pelo menor
        centro de custo.
        """
        linhas = self._quadros(escopo, competencia)
        if not linhas:
            return None
        efetivo = sum(l.efetivo_ativo for l in linhas)
        return QuadroDTO(
            procedencia=self._procedencia_do_conjunto(
                QuadroPessoas.objects.filter(pk__in=[l.pk for l in linhas])
            ),
            centro_custo="" if len(linhas) > 1 else linhas[0].centro_custo,
            ano=competencia.year,
            mes=competencia.month,
            efetivo_ativo=efetivo,
            admissoes=sum(l.admissoes for l in linhas),
            rescisoes=sum(l.rescisoes for l in linhas),
            turnover_pct=_ponderado(linhas, "turnover_pct", efetivo),
            absenteismo_pct=_ponderado(linhas, "absenteismo_pct", efetivo),
            vagas_abertas=sum(l.vagas_abertas for l in linhas),
            vagas_fechadas_no_prazo=sum(l.vagas_fechadas_no_prazo for l in linhas),
            em_ferias=sum(l.em_ferias for l in linhas),
            afastados=sum(l.afastados for l in linhas),
        )

    def quadros(self, escopo, competencia: date) -> list[QuadroDTO]:
        return [
            QuadroDTO(
                procedencia=_proc(l),
                centro_custo=l.centro_custo,
                ano=l.ano,
                mes=l.mes,
                efetivo_ativo=l.efetivo_ativo,
                admissoes=l.admissoes,
                rescisoes=l.rescisoes,
                turnover_pct=l.turnover_pct,
                absenteismo_pct=l.absenteismo_pct,
                vagas_abertas=l.vagas_abertas,
                vagas_fechadas_no_prazo=l.vagas_fechadas_no_prazo,
                em_ferias=l.em_ferias,
                afastados=l.afastados,
            )
            for l in self._quadros(escopo, competencia)
        ]

    def _quadros(self, escopo, competencia: date):
        consulta = QuadroPessoas.objects.filter(
            ano=competencia.year, mes=competencia.month
        )
        if escopo is not None and escopo.centros_custo:
            consulta = consulta.filter(centro_custo__in=escopo.centros_custo)
        return list(consulta.order_by("centro_custo"))

    def movimentacao(self, escopo, de: date, ate: date) -> MovimentacaoPessoasDTO:
        consulta = QuadroPessoas.objects.filter(
            Q(ano__gt=de.year) | Q(ano=de.year, mes__gte=de.month),
            Q(ano__lt=ate.year) | Q(ano=ate.year, mes__lte=ate.month),
        )
        if escopo is not None and escopo.centros_custo:
            consulta = consulta.filter(centro_custo__in=escopo.centros_custo)
        return MovimentacaoPessoasDTO(
            admissoes=sum(l.admissoes for l in consulta),
            rescisoes=sum(l.rescisoes for l in consulta),
            em_ferias=sum(l.em_ferias for l in consulta),
        )

    def apontamentos(self, escopo, competencia: date) -> ApontamentoDTO | None:
        consulta = Apontamento.objects.filter(
            ano=competencia.year, mes=competencia.month
        )
        if escopo is not None and escopo.centros_custo:
            consulta = consulta.filter(centro_custo__in=escopo.centros_custo)
        linhas = list(consulta)
        if not linhas:
            return None
        linha = _somar_apontamentos(linhas)
        campos = (
            "centro_custo", "ano", "mes", "horas_normais", "he_total",
            "he_ineficiencia", "he_servico_extra", "he_sem_classificacao",
            "hora_escala", "hora_abono", "hora_desconto", "hora_noturna",
            "banco_horas_saldo", "folhas_ponto_pendentes",
            "contratos_pendentes_assinatura",
        )
        return ApontamentoDTO(
            procedencia=_proc(linha),
            **{campo: getattr(linha, campo) for campo in campos},
        )

    # ── Satisfação ──────────────────────────────────────────────────

    def avaliacoes(self, escopo, de: date, ate: date) -> list[AvaliacaoDTO]:
        consulta = AvaliacaoCliente.objects.select_related("contrato").filter(
            data__gte=de, data__lte=ate
        )
        consulta = _recortar(consulta, escopo, ate_o_contrato="contrato__")
        return [
            AvaliacaoDTO(
                procedencia=_proc(a),
                contrato=a.contrato.codigo,
                data=a.data,
                nota=a.nota,
                classificacao=a.classificacao,
                comentario=a.comentario,
                tratativa_aberta=a.tratativa_aberta,
                tratativa_prazo=a.tratativa_prazo,
                tratativa_status=a.tratativa_status,
            )
            for a in consulta.order_by("-data")
        ]


def _ponderado(linhas, campo: str, efetivo: int) -> Decimal:
    """Média ponderada pelo efetivo, com uma casa.

    Sem efetivo não há ponderação possível e o resultado é zero — que é honesto:
    um percentual de pessoas sobre zero pessoas não é um número.
    """
    if not efetivo:
        return Decimal("0")
    total = sum(getattr(l, campo) * l.efetivo_ativo for l in linhas)
    return (Decimal(total) / Decimal(efetivo)).quantize(Decimal("0.01"))


class _Somado:
    """Um apontamento agregado, com a mesma cara de um do banco.

    Objeto solto e não um `QuerySet.aggregate()` porque o chamador lê quinze
    campos por nome — e um dicionário obrigaria a trocar quinze `getattr` por
    quinze `[...]` no provider, sem ganhar nada.
    """

    def __init__(self, valores: dict):
        for nome, valor in valores.items():
            setattr(self, nome, valor)


#: Somáveis. `centro_custo` NÃO está aqui: somar códigos de centro de custo é
#: literalmente concatenar identificadores, e o resultado seria um código que
#: não existe.
SOMAVEIS = (
    "horas_normais", "he_total", "he_ineficiencia", "he_servico_extra",
    "he_sem_classificacao", "hora_escala", "hora_abono", "hora_desconto",
    "hora_noturna", "banco_horas_saldo", "folhas_ponto_pendentes",
    "contratos_pendentes_assinatura",
)


def _somar_apontamentos(linhas):
    valores = {campo: sum(getattr(l, campo) for l in linhas) for campo in SOMAVEIS}
    valores["centro_custo"] = "" if len(linhas) > 1 else linhas[0].centro_custo
    valores["ano"] = linhas[0].ano
    valores["mes"] = linhas[0].mes
    valores["procedencia"] = linhas[0].procedencia
    return _Somado(valores)
