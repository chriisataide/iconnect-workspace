"""As regras que a ingestão destravou — contratos, projetos e satisfação.

Todas perguntam ao contrato (`workspace.providers.resultados`), e nenhuma
conhece Sankhya, monday ou Platform. `disponivel()` responde `False` quando o
provedor não está registrado, e a regra aparece como **não avaliada** — não como
zero. Zero seria tranquilidade; não avaliada é uma fonte para ligar.
"""

from __future__ import annotations

from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from workspace.providers import resultados as contrato

from .base import Ocorrencia, RegraBase, quem_responde

#: Abaixo disto o contrato exige justificativa — a regra dos 10% do benchmark.
#: Ela não é alerta: é obrigação.
MARGEM_MINIMA = Decimal("10")


def _carteira():
    return contrato.obter(contrato.ProvedorCarteira)


class MargemAbaixoDoMinimo(RegraBase):
    """Regra 11 — contrato com margem abaixo de 10%, sem justificativa.

    "Sem justificativa" é, hoje, todo contrato abaixo do limiar: o registro da
    justificativa é a Onda 6, e inventar um campo agora criaria um lugar para
    guardar texto que nada leria.

    Contrato **sem amostra** fica de fora. Cobrar justificativa de quem faturou
    uma vez é cobrar de quem ainda não tem o que explicar.
    """

    chave = "margem-abaixo-de-10"
    fonte = "iconnect_platform"

    def disponivel(self) -> bool:
        return _carteira() is not None

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        from workspace.services.resultados import SEM_AMOSTRA

        limite = Decimal(janela) if janela else MARGEM_MINIMA
        responsavel = quem_responde("financeiro")
        return [
            Ocorrencia(
                chave=f"contrato:{c.codigo}",
                titulo=f"{c.codigo} · {c.nome_cliente}",
                detalhe=f"margem de {c.margem_contribuicao_pct}%"
                        + (" · deficitário" if c.deficitario else ""),
                url=f"{reverse('workspace:resultados')}#contratos",
                responsavel=responsavel,
                papel="financeiro",
            )
            for c in _carteira().contratos(contrato.Escopo())
            if c.layer != SEM_AMOSTRA
            and c.margem_contribuicao_pct is not None
            and c.margem_contribuicao_pct < limite
        ]


class ContratoVencendoSemVisita(RegraBase):
    """Regra 12 — contrato vencendo na janela, sem registro de visita.

    O Workspace ainda **não** registra visita: isso mora no Platform, e a
    integração de hoje traz consolidado, não agenda. Por isso a regra nasce
    contando os que vencem — e o texto diz que a visita não é verificável.

    É diferente de fingir que verificou. Uma regra que promete o que não cumpre
    ensina a desconfiar das outras dezoito.
    """

    chave = "contrato-vencendo-sem-visita"
    fonte = "iconnect_platform"

    def disponivel(self) -> bool:
        return _carteira() is not None

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        responsavel = quem_responde("vendas")
        return [
            Ocorrencia(
                chave=f"contrato:{c.codigo}",
                titulo=f"{c.codigo} · {c.nome_cliente}",
                detalhe=f"vence em {c.fim_vigencia:%d/%m/%Y}"
                        + (f" · Layer {c.layer}" if c.layer.isdigit() else ""),
                url=f"{reverse('workspace:resultados')}#vencimentos",
                responsavel=responsavel,
                papel="vendas",
                desde=c.fim_vigencia,
            )
            for c in _carteira().vencimentos(contrato.Escopo(), janela or 60)
        ]


class LayerTresSemApresentacao(RegraBase):
    """Regra 13 — contrato Layer 3 sem apresentação de resultado no período.

    Layer converte porte em OBRIGAÇÃO: só a 3 deve apresentação. Como a
    apresentação ainda não é registrada aqui, a regra lista os Layer 3 e diz
    isso — o mesmo cuidado da regra 12.
    """

    chave = "layer3-sem-apresentacao"
    fonte = "iconnect_platform"

    def disponivel(self) -> bool:
        return _carteira() is not None

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        responsavel = quem_responde("diretoria")
        return [
            Ocorrencia(
                chave=f"contrato:{c.codigo}",
                titulo=f"{c.codigo} · {c.nome_cliente}",
                detalhe=f"R$ {c.valor_mensal:,.2f}/mês · sem apresentação registrada"
                        .replace(",", "·").replace(".", ",").replace("·", "."),
                url=f"{reverse('workspace:resultados')}#contratos",
                responsavel=responsavel,
                papel="diretoria",
            )
            for c in _carteira().contratos(contrato.Escopo())
            if c.layer == "3"
        ]


class DetratorSemTratativa(RegraBase):
    """Regra 14 — cliente detrator sem tratativa aberta.

    Com tratativa é trabalho em andamento; sem, é uma pessoa esperando. O
    comentário entra na linha; **quem escreveu, não**: é pessoa do cliente, e o
    Workspace não é dono desse cadastro.
    """

    chave = "detrator-sem-tratativa"
    fonte = "iconnect_platform"

    def disponivel(self) -> bool:
        return contrato.obter(contrato.ProvedorSatisfacao) is not None

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        from datetime import timedelta

        provedor = contrato.obter(contrato.ProvedorSatisfacao)
        hoje = timezone.localdate()
        responsavel = quem_responde("operacao")
        return [
            Ocorrencia(
                chave=f"avaliacao:{a.contrato}:{a.data}",
                titulo=f"{a.contrato} · nota {a.nota}",
                detalhe=a.comentario or "sem comentário",
                url=f"{reverse('workspace:resultados')}#satisfacao",
                responsavel=responsavel,
                papel="operacao",
                desde=a.data,
            )
            for a in provedor.avaliacoes(
                contrato.Escopo(), hoje - timedelta(days=janela or 90), hoje
            )
            if a.detrator_sem_tratativa
        ]


class ProjetoBloqueadoHaMuito(RegraBase):
    """Regra 15 — projeto bloqueado há mais de N dias.

    O motivo vem junto. Bloqueio sem motivo é uma bandeira vermelha que ninguém
    sabe o que fazer com — e a próxima pergunta seria exatamente essa.
    """

    chave = "projeto-bloqueado"
    fonte = "monday"

    def disponivel(self) -> bool:
        return contrato.obter(contrato.ProvedorProjetos) is not None

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        from datetime import timedelta

        provedor = contrato.obter(contrato.ProvedorProjetos)
        limite = timezone.now() - timedelta(days=janela or 15)
        return [
            Ocorrencia(
                chave=f"projeto:{p.codigo}",
                titulo=f"{p.codigo} · {p.nome}",
                detalhe=p.motivo_bloqueio or "sem motivo declarado",
                url=f"{reverse('workspace:resultados')}#projetos",
                responsavel=p.responsavel or quem_responde("operacao"),
                papel="operacao",
                desde=p.movimentado_em.date() if p.movimentado_em else None,
            )
            for p in provedor.projetos(contrato.Escopo())
            if p.bloqueado
            and (p.movimentado_em is None or p.movimentado_em <= limite)
        ]


class MarcoVencidoSemReplanejamento(RegraBase):
    """Regra 16 — marco vencido e ainda não concluído.

    "Sem replanejamento" é o que o prazo vencido significa: se alguém tivesse
    replanejado, o prazo seria outro. Não há campo separado para isso, e criar
    um seria inventar um lugar para guardar o que a data já diz.
    """

    chave = "marco-vencido"
    fonte = "monday"

    def disponivel(self) -> bool:
        return contrato.obter(contrato.ProvedorProjetos) is not None

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        provedor = contrato.obter(contrato.ProvedorProjetos)
        return [
            Ocorrencia(
                chave=f"marco:{m.projeto}:{m.titulo}",
                titulo=f"{m.projeto} · {m.titulo}",
                detalhe=f"prazo era {m.prazo:%d/%m/%Y}",
                url=f"{reverse('workspace:resultados')}#projetos",
                responsavel=m.responsavel or quem_responde("operacao"),
                papel="operacao",
                desde=m.prazo,
            )
            # `dias=0` porque marcos VENCIDOS já passaram: pedir uma janela para
            # o futuro devolveria os que ainda vão vencer, que é outra regra.
            for m in provedor.marcos_em_risco(contrato.Escopo(), 0)
            if m.vencido
        ]


class CentroDeCustoSemConciliacao(RegraBase):
    """Regra 19 — centro de custo no ERP e fora do orçamento, e o inverso.

    Registrada e **desligada** desde a Onda 4, com a nota "só passa a valer
    quando o orçamento existir aqui dentro". A Onda 8 criou o orçamento anual, e
    a regra ligou.

    ## Por que ela é uma regra, e não um cuidado

    O benchmark é explícito: *"Código divergente não dá erro: produz uma linha
    com realizado e sem orçado, que parece estouro de orçamento e não é. A
    conciliação de códigos precisa ser uma regra de exceção, não um cuidado."*

    Um cuidado é uma coisa que alguém lembra na primeira semana. Uma regra roda
    todo dia e cobra plano de ação.

    ## As duas direções

    - **no ERP e fora do orçamento** — o Sankhya lançou realizado num centro de
      custo que ninguém orçou aqui. A linha parece estouro e não é;
    - **no orçamento e fora do ERP** — orçamos um centro de custo que o ERP não
      conhece. O teto existe e nunca será consumido, e a folga é falsa.

    As duas na mesma regra porque são o **mesmo defeito** — um cadastro que não
    bate — e separá-las faria alguém corrigir metade.
    """

    chave = "cc-sem-orcado-e-o-inverso"
    fonte = "sankhya"

    def disponivel(self) -> bool:
        from workspace.providers import orcamento as orcamento_contrato

        # Precisa das DUAS pontas: sem o espelho não há o lado do ERP, e sem o
        # domínio financeiro não há o lado do orçamento. Uma ponta só produziria
        # uma lista em que tudo é divergente.
        return (
            contrato.obter(contrato.ProvedorResultadoFinanceiro) is not None
            and orcamento_contrato.obter() is not None
        )

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        from datetime import date

        from workspace.providers import orcamento as orcamento_contrato

        espelho = contrato.obter(contrato.ProvedorResultadoFinanceiro)
        financeiro = orcamento_contrato.obter()
        hoje = timezone.localdate()
        responsavel = quem_responde("financeiro")

        no_erp = {
            c.centro_custo
            for c in espelho.serie_competencia(
                contrato.Escopo(), date(hoje.year, 1, 1), date(hoje.year, 12, 1)
            )
            if c.centro_custo
        }
        no_orcamento = {
            c.codigo
            for c in financeiro.centros()
            if c.ativo and financeiro.orcamento_do_ano(c.codigo, hoje.year)
        }

        ocorrencias = [
            Ocorrencia(
                chave=f"cc-erp:{codigo}",
                titulo=f"{codigo} · no ERP e sem orçamento aqui",
                detalhe="realizado sem teto: a linha parece estouro e não é",
                url=reverse("workspace:orcamento"),
                responsavel=responsavel,
                papel="financeiro",
            )
            for codigo in sorted(no_erp - no_orcamento)
        ]
        ocorrencias += [
            Ocorrencia(
                chave=f"cc-orcamento:{codigo}",
                titulo=f"{codigo} · orçado aqui e desconhecido no ERP",
                detalhe="teto que nunca será consumido: a folga é falsa",
                url=reverse("workspace:orcamento"),
                responsavel=responsavel,
                papel="financeiro",
            )
            for codigo in sorted(no_orcamento - no_erp)
        ]
        return ocorrencias
