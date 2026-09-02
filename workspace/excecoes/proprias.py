"""As dez regras sobre o dado do próprio Workspace.

Nenhuma depende de fonte externa: elas olham organograma, catálogo, acervo e
reservas. São as que funcionam num ambiente recém-instalado, e por isso são as
que provam que o painel funciona antes de qualquer conector existir.
"""

from __future__ import annotations

from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from .base import Ocorrencia, RegraBase, quem_responde


class LotacaoSemCentroDeCusto(RegraBase):
    """Regra 1 — pessoa no organograma sem centro de custo.

    `Lotacao.centro_custo_codigo` decide dinheiro em três lugares: o pedido do
    catálogo o copia ao nascer, a bandeja monta a barra de orçamento com ele, e
    o compromisso é baixado por ele. Sem código, o primeiro pedido que exigir um
    é recusado — e quem descobre é a pessoa, no meio de pedir alguma coisa.
    """

    chave = "lotacao-sem-cc"

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        from identidade.models import Lotacao

        responsavel = quem_responde("rh")
        return [
            Ocorrencia(
                chave=f"lotacao:{lotacao.pk}",
                titulo=lotacao.user.get_full_name() or lotacao.user.get_short_name(),
                detalhe=lotacao.cargo or "",
                url=reverse("workspace:pessoas"),
                responsavel=responsavel,
                papel="rh",
            )
            for lotacao in Lotacao.objects.select_related("user").filter(
                centro_custo_codigo=""
            )
        ]


class PessoaSemPapelVigente(RegraBase):
    """Regra 2 — está no organograma e não tem papel nenhum vigente.

    Sem papel, a pessoa é colaborador comum: nenhuma fila abre, nenhuma bandeja
    recebe. É o estado em que o ambiente fica quando `semear_acessos` não roda —
    e é invisível até alguém reclamar que um pedido não chegou em ninguém.
    """

    chave = "pessoa-sem-papel"

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        from identidade.models import AtribuicaoPapel, Lotacao

        com_papel = set(
            AtribuicaoPapel.objects.vigentes()
            .filter(papel__ativo=True)
            .values_list("user_id", flat=True)
        )
        responsavel = quem_responde("rh")
        return [
            Ocorrencia(
                chave=f"pessoa:{lotacao.user_id}",
                titulo=lotacao.user.get_full_name() or lotacao.user.get_short_name(),
                detalhe=lotacao.cargo or "",
                url=reverse("workspace:pessoas"),
                responsavel=responsavel,
                papel="rh",
            )
            for lotacao in Lotacao.objects.select_related("user").exclude(
                user_id__in=com_papel
            )
        ]


class PapelVencendo(RegraBase):
    """Regra 3 — papel com vigência terminando dentro da janela.

    Papel que vence sem ninguém renovar tira a pessoa da fila em silêncio. O
    sintoma aparece do outro lado: um pedido que para de ser atendido, e ninguém
    liga uma coisa à outra.
    """

    chave = "papel-vencendo"

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        from identidade.models import AtribuicaoPapel

        hoje = timezone.localdate()
        limite = hoje + timedelta(days=janela or 30)
        responsavel = quem_responde("rh")
        return [
            Ocorrencia(
                chave=f"atribuicao:{a.pk}",
                titulo=f"{a.user.get_full_name() or a.user.get_short_name()} · {a.papel.nome}",
                detalhe=f"vence em {a.vigencia_fim:%d/%m/%Y}",
                url=reverse("workspace:pessoas"),
                responsavel=responsavel,
                papel="rh",
                desde=a.vigencia_fim,
            )
            for a in AtribuicaoPapel.objects.select_related("user", "papel")
            .vigentes()
            .filter(vigencia_fim__isnull=False, vigencia_fim__lte=limite)
        ]


class SolicitacaoParada(RegraBase):
    """Regra 4 — pedido em aberto além do prazo que a pessoa VIU ao pedir.

    A régua é o prazo prometido do item, e não um número escolhido aqui. Cobrar
    por outro seria mudar a medida depois do jogo — é a mesma decisão de
    `SolicitacaoServico.prioridade`.
    """

    chave = "solicitacao-parada"

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        from workspace.models.catalogo import SolicitacaoServico
        from workspace.services import atendimento as atd
        from workspace.services import listagem as lst

        atrasadas = [
            s
            for s in SolicitacaoServico.objects.select_related("item", "solicitante")
            .filter(situacao__in=lst.ABERTAS)
            if s.prioridade == "atrasado"
        ]
        return [
            Ocorrencia(
                chave=f"solicitacao:{s.pk}",
                titulo=f"#{s.pk} · {s.item.nome}",
                detalhe=f"aberta em {s.criado_em:%d/%m/%Y}",
                url=reverse("workspace:fila"),
                responsavel=quem_responde(_papel_da_area(s.item.dominio)),
                papel=atd.area_de(s.item.dominio),
                desde=s.criado_em.date(),
            )
            for s in atrasadas
        ]


def _papel_da_area(dominio: str) -> str:
    """A chave do papel que atende este domínio.

    Sai do papel que declara `<raiz>.atender`, que é a mesma fonte que a fila
    usa para se recortar — e não de uma segunda lista. Duas listas divergem, e a
    que divergiria seria a daqui, porque ninguém a olha.

    Em PYTHON e não em `permissoes__contains`: `permissoes` é `JSONField`, e o
    `contains` de JSON não existe no SQLite. A consulta funcionava em produção e
    estourava `NotSupportedError` em desenvolvimento — que é a pior forma de um
    defeito existir, porque só aparece para quem está desenvolvendo.

    São quinze linhas de `Papel`, e a lista inteira cabe numa consulta.
    """
    from identidade.models import Papel

    raiz = dominio.split(".", 1)[0]
    alvo = f"{raiz}.atender"
    for papel in Papel.objects.filter(ativo=True).only("chave", "permissoes").order_by("chave"):
        if any((p or "").startswith(alvo) for p in papel.permissoes or []):
            return papel.chave
    return ""


class AprovacaoPendente(RegraBase):
    """Regra 5 — etapa de aprovação esperando decisão além da janela.

    Diferente da regra 4: lá o pedido está parado em alguma coisa; aqui ele está
    parado em ALGUÉM. As duas separadas porque as ações são opostas — a primeira
    pede gente na fila, a segunda pede uma decisão.
    """

    chave = "aprovacao-pendente"

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        from workspace.models.aprovacao import EtapaAprovacao, SituacaoEtapa

        limite = timezone.now() - timedelta(days=janela or 3)
        ocorrencias = []
        # O relógio é o da SOLICITAÇÃO DE APROVAÇÃO, e não o da etapa: `Etapa`
        # não guarda quando virou a vez dela, e inventar esse instante daria um
        # número que ninguém consegue conferir.
        #
        # O que a diretoria pergunta é "há quanto tempo este pedido está parado
        # esperando alguém decidir" — e essa é exatamente a data de quando ele
        # entrou na cadeia.
        for etapa in (
            EtapaAprovacao.objects.select_related(
                "solicitacao", "aprovador", "papel"
            )
            .filter(
                situacao=SituacaoEtapa.PENDENTE,
                solicitacao__criado_em__lte=limite,
            )
        ):
            if etapa.aprovador_id:
                nome = etapa.aprovador.get_full_name() or etapa.aprovador.get_short_name()
                papel = ""
            else:
                papel = etapa.papel.chave if etapa.papel_id else ""
                nome = quem_responde(papel)
            quando = etapa.solicitacao.criado_em
            ocorrencias.append(
                Ocorrencia(
                    chave=f"etapa:{etapa.pk}",
                    titulo=etapa.solicitacao.titulo or f"aprovação #{etapa.solicitacao_id}",
                    detalhe=f"na cadeia desde {quando:%d/%m/%Y}",
                    url=reverse("workspace:aprovacoes"),
                    responsavel=nome,
                    papel=papel,
                    desde=quando.date(),
                )
            )
        return ocorrencias


class LeituraObrigatoriaNaoConfirmada(RegraBase):
    """Regra 6 — documento obrigatório sem confirmação da versão atual.

    Por DOCUMENTO e não por pessoa. A grade nomearia todo mundo que não leu, e a
    lista de quem não leu uma política é dado sobre gente — vira uma tela de
    vigilância. Aqui a linha é o documento, e o número ao lado é quantos faltam.
    """

    chave = "leitura-nao-confirmada"

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        from django.db.models import Count, Q

        from workspace.models.conteudo import ConfirmacaoLeitura, Documento

        responsavel = quem_responde("rh")
        ocorrencias = []
        for documento in Documento.objects.publicados().filter(leitura_obrigatoria=True):
            confirmadas = ConfirmacaoLeitura.objects.filter(
                documento=documento, versao=documento.versao
            ).count()
            esperadas = _quantos_alcancados(documento)
            faltam = max(esperadas - confirmadas, 0)
            if not faltam:
                continue
            ocorrencias.append(
                Ocorrencia(
                    chave=f"documento:{documento.pk}",
                    titulo=documento.titulo,
                    detalhe=f"{faltam} de {esperadas} ainda não confirmaram "
                            f"a versão {documento.versao}",
                    url=reverse("workspace:documento", args=(documento.slug,)),
                    responsavel=responsavel,
                    papel="rh",
                )
            )
        return ocorrencias


def _quantos_alcancados(documento) -> int:
    """Quantas pessoas o documento alcança.

    Aproximação por LOTAÇÃO: quem está no organograma. O público-alvo real é
    resolvido por `subjects_de` pessoa a pessoa, e fazer isso aqui custaria uma
    consulta por pessoa por documento. O número serve para dimensionar a
    pendência, e não para cobrar de alguém — quem cobra é a tela do documento.
    """
    from identidade.models import Lotacao

    return Lotacao.objects.count()


class NormativoSemRevisao(RegraBase):
    """Regra 7 — POP ou política vigente sem revisão há mais de 12 meses.

    Normativo velho é pior que normativo ausente: ele tem autoridade e está
    errado, e quem o segue faz a coisa errada com respaldo.
    """

    chave = "normativo-sem-revisao"

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        from workspace.models.conteudo import Documento

        limite = timezone.now() - timedelta(days=janela or 365)
        responsavel = quem_responde("rh")
        return [
            Ocorrencia(
                chave=f"documento:{d.pk}",
                titulo=d.titulo,
                detalhe=f"última alteração em {d.atualizado_em:%d/%m/%Y}",
                url=reverse("workspace:documento", args=(d.slug,)),
                responsavel=d.dono.get_full_name() if d.dono_id else responsavel,
                papel="rh",
                desde=d.atualizado_em.date(),
            )
            for d in Documento.objects.publicados()
            .select_related("dono")
            .filter(atualizado_em__lte=limite)
        ]


class CentroDeCustoSemOrcamento(RegraBase):
    """Regra 8 — centro de custo existe e não tem teto mensal.

    A bandeja de aprovação diz "CC sem orçamento definido — não consigo calcular
    o impacto". Quem lê isso conclui que a barra está quebrada; ela não está,
    não havia o que ler.
    """

    chave = "cc-sem-orcamento"
    fonte = "financas"

    def disponivel(self) -> bool:
        """Sem domínio financeiro instalado, a regra não é avaliada.

        `centros_de_custo()` devolve lista vazia nesse caso — e lista vazia
        aqui seria lida como "todos os CCs têm orçamento", que é o oposto da
        verdade.
        """
        from workspace.services import orcamento as orc

        return orc.provedor.obter() is not None

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        from workspace.services import orcamento as orc

        responsavel = quem_responde("financeiro")
        return [
            Ocorrencia(
                chave=f"cc:{centro.codigo}",
                titulo=f"{centro.codigo} · {centro.nome}",
                detalhe="sem teto mensal definido",
                url=reverse("workspace:pessoas"),
                responsavel=responsavel,
                papel="financeiro",
            )
            for centro in orc.centros_de_custo()
            if centro.ativo and centro.orcamento_mensal is None
        ]


class CentroDeCustoComprometido(RegraBase):
    """Regra 9 — comprometido acima de 90% do teto do mês.

    Noventa e não cem: em cem já estourou, e a exceção existe para aparecer
    ANTES. Uma regra que só acusa o que já aconteceu é um relatório.
    """

    chave = "cc-comprometido"
    fonte = "financas"

    def disponivel(self) -> bool:
        from workspace.services import orcamento as orc

        return orc.provedor.obter() is not None

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        from decimal import Decimal

        from workspace.services import orcamento as orc

        # A janela aqui é PERCENTUAL, e não dias — é a única regra em que ela
        # muda de unidade, e por isso o valor padrão vem escrito.
        teto = Decimal(janela or 90)
        responsavel = quem_responde("financeiro")
        ocorrencias = []
        for centro in orc.centros_de_custo():
            if not centro.ativo:
                continue
            resumo = orc.resumo(centro.codigo)
            percentual = resumo.percentual()
            # `None` quer dizer "sem orçamento definido", e essa é a regra 8.
            # Contá-la aqui também faria o mesmo centro de custo aparecer em
            # duas linhas do painel por dois motivos que são um só.
            if percentual is None or percentual < teto:
                continue
            ocorrencias.append(
                Ocorrencia(
                    chave=f"cc:{centro.codigo}",
                    titulo=f"{centro.codigo} · {centro.nome}",
                    detalhe=f"{percentual}% do teto do mês",
                    url=reverse("workspace:aprovacoes"),
                    responsavel=responsavel,
                    papel="financeiro",
                )
            )
        return ocorrencias


class ReservaSemUso(RegraBase):
    """Regra 10 — reserva confirmada cuja janela passou sem ninguém aparecer.

    O Workspace não sabe se a sala foi usada; ele sabe que a reserva não foi
    cancelada e que a hora passou. É uma regra sobre COMPORTAMENTO, e ela vale
    porque sala reservada e vazia é sala que faltou para outra equipe.
    """

    chave = "reserva-sem-uso"

    def avaliar(self, janela: int) -> list[Ocorrencia]:
        from workspace.models.reserva import Reserva, SituacaoReserva

        agora = timezone.now()
        limite = agora - timedelta(days=janela or 7)
        return [
            Ocorrencia(
                chave=f"reserva:{r.pk}",
                titulo=f"{r.recurso.nome} · {r.inicio:%d/%m %H:%M}",
                detalhe=r.motivo or "",
                url=reverse("workspace:minhas_reservas"),
                responsavel=r.solicitante.get_full_name()
                or r.solicitante.get_short_name(),
                papel="",
                desde=r.inicio.date(),
            )
            for r in Reserva.objects.select_related("recurso", "solicitante").filter(
                situacao=SituacaoReserva.CONFIRMADA, fim__lte=agora, fim__gte=limite
            )
        ]
