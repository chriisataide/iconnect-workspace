"""O painel de exceções — a lista de regras, e o que cada uma achou.

## Não é um dashboard

É uma **lista de regras**, cada uma com uma contagem, que expande para a grade
dos registros que a violaram. E cada linha traz o responsável — a exceção nasce
endereçada, como no benchmark, onde a grade traz o e-mail do gestor em cada
linha.

## Três estados, e eles não são dois

- **com ocorrências** — o número, e a grade;
- **sem ocorrências** — a regra rodou e não achou nada. **Não some da lista:**
  sumir esconderia que a regra existe, e o efeito prático é alguém reabrir a
  discussão sobre "deveríamos vigiar X" seis meses depois de já estarmos
  vigiando;
- **não avaliada** — a fonte da regra não está no ar. **Não é zero.** Zero é
  tranquilidade; não avaliada é uma fonte para ligar, e somá-las faria uma fonte
  caída parecer um mês sem problema.

## Quem vê o quê

Cada regra declara o papel que responde por ela, e a pessoa vê as regras do seu
papel. Quem tem `exc.ler.global` vê todas — é a diretoria olhando o painel
inteiro.

Quem não tem papel nenhum das regras recebe **403**, e não uma lista vazia.
Lista vazia para quem nunca vai ter regra é a mesma mentira de um painel de
zeros: faz a pessoa achar que está tudo em ordem.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from django.utils import timezone

from identidade.services.autorizacao import ESCOPO_GLOBAL, escopo_de, pode
from workspace import excecoes as reg
from workspace.models.excecao import (
    LIMITE_DE_CHAVES,
    RegraExcecao,
    ResultadoExcecao,
)

PERMISSAO = "exc.ler"

#: Quantas ocorrências a grade mostra por vez. O benchmark tem regra com 2.556
#: registros; despejá-los numa página trava o navegador e não ajuda ninguém.
POR_PAGINA = 50


class SemExcecoes(Exception):
    """Esta pessoa não responde por regra nenhuma."""


@dataclass
class Avaliacao:
    """Uma regra e o que ela achou agora."""

    regra: RegraExcecao
    ocorrencias: list = field(default_factory=list)
    avaliada: bool = True
    motivo: str = ""
    #: O total da última avaliação PERSISTIDA, para a tendência. `None` quando
    #: nunca houve — e aí a tela não inventa uma seta.
    anterior: int | None = None

    @property
    def total(self) -> int:
        return len(self.ocorrencias)

    @property
    def variacao(self) -> int | None:
        """Quanto mudou desde a última avaliação registrada.

        Uma regra que foi de 3 para 40 importa mais que uma que está em 40 há um
        ano — e a contagem sozinha não conta isso. `None` sem histórico: uma
        seta inventada é pior que seta nenhuma.
        """
        if self.anterior is None:
            return None
        return self.total - self.anterior

    @property
    def situacao(self) -> str:
        if not self.avaliada:
            return "nao_avaliada"
        return "com_ocorrencias" if self.ocorrencias else "sem_ocorrencias"


# ── Permissão ───────────────────────────────────────────────────────


def papeis_de(pessoa, cache: dict | None = None) -> set[str]:
    """As chaves de papel que esta pessoa ocupa hoje."""
    if pessoa is None or not getattr(pessoa, "is_authenticated", False):
        return set()
    from identidade.models import AtribuicaoPapel

    return set(
        AtribuicaoPapel.objects.vigentes()
        .filter(user=pessoa, papel__ativo=True)
        .values_list("papel__chave", flat=True)
    )


def regras_de(pessoa, cache: dict | None = None):
    """As regras ATIVAS que esta pessoa vê.

    Regra sem `escopo_papel` é de todo mundo que abre o painel: são as que
    vigiam o mecanismo — fonte atrasada, divergência entre fontes —, e elas não
    pertencem a departamento nenhum.
    """
    todas = RegraExcecao.objects.ativas()
    if escopo_de(pessoa, PERMISSAO, cache=cache) == ESCOPO_GLOBAL:
        return list(todas)

    meus = papeis_de(pessoa, cache=cache)
    visiveis = [r for r in todas if not r.escopo_papel or r.escopo_papel in meus]
    if not any(r.escopo_papel for r in visiveis):
        # Só sobraram as regras "de todo mundo". Elas existem para quem já está
        # no painel por outro motivo — mostrá-las sozinhas transformaria o painel
        # numa tela de infraestrutura para quem não opera infraestrutura.
        raise SemExcecoes("Você não responde por nenhuma regra de exceção.")
    return visiveis


def tem_painel(pessoa, cache: dict | None = None) -> bool:
    try:
        regras_de(pessoa, cache=cache)
    except SemExcecoes:
        return False
    return True


# ── Avaliação ───────────────────────────────────────────────────────


def avaliar(regra: RegraExcecao) -> Avaliacao:
    """Roda uma regra. Nunca levanta.

    Uma regra que estoura não pode derrubar as outras dezoito — o painel existe
    justamente para ser aberto quando algo está errado. A exceção vira o motivo
    de "não avaliada", que é a verdade sobre aquela regra e sobre mais nenhuma.
    """
    avaliador = reg.regra_de(regra.chave)
    if avaliador is None:
        return Avaliacao(
            regra=regra,
            avaliada=False,
            motivo=(
                "Regra declarada e ainda sem avaliador escrito."
                + (f" Depende de: {regra.fonte_requerida}." if regra.fonte_requerida else "")
            ),
            anterior=_anterior(regra),
        )

    if not avaliador.disponivel():
        return Avaliacao(
            regra=regra,
            avaliada=False,
            motivo=(
                f"A fonte {regra.fonte_requerida or avaliador.fonte} não está "
                "disponível neste ambiente — a regra não foi avaliada."
            ),
            anterior=_anterior(regra),
        )

    try:
        ocorrencias = list(avaliador.avaliar(regra.janela))
    except Exception as erro:  # noqa: BLE001 - ver o docstring
        return Avaliacao(
            regra=regra,
            avaliada=False,
            motivo=f"A regra falhou ao ser avaliada: {type(erro).__name__}.",
            anterior=_anterior(regra),
        )

    return Avaliacao(regra=regra, ocorrencias=ocorrencias, anterior=_anterior(regra))


def _anterior(regra: RegraExcecao) -> int | None:
    ultimo = regra.resultados.filter(avaliada=True).first()
    return ultimo.total if ultimo else None


def painel(pessoa, cache: dict | None = None) -> dict:
    """Tudo o que a tela mostra. Levanta `SemExcecoes` para quem não responde nada."""
    regras = regras_de(pessoa, cache=cache)
    avaliacoes = [avaliar(regra) for regra in regras]

    return {
        "avaliacoes": avaliacoes,
        "total_de_ocorrencias": sum(a.total for a in avaliacoes if a.avaliada),
        "nao_avaliadas": [a for a in avaliacoes if not a.avaliada],
        # As desligadas aparecem numa seção própria, com a fonte anotada. É o
        # que responde "por que não vigiamos ASO?" sem ninguém precisar
        # perguntar — e o que impede a mesma discussão de voltar em seis meses.
        "desligadas": list(RegraExcecao.objects.filter(ativa=False).order_by("ordem")),
        "avaliado_em": timezone.now(),
    }


def registrar_resultado(avaliacao: Avaliacao) -> ResultadoExcecao:
    """Grava o retrato. É daqui que sai a tendência da próxima vez.

    `chaves` guarda o identificador do REGISTRO, nunca de pessoa: o histórico é
    consultado por quem não abriu a tela e não passou por permissão nenhuma.
    """
    return ResultadoExcecao.objects.create(
        regra=avaliacao.regra,
        total=avaliacao.total,
        avaliada=avaliacao.avaliada,
        chaves=[o.chave for o in avaliacao.ocorrencias][:LIMITE_DE_CHAVES],
    )


# ── Notificar ───────────────────────────────────────────────────────


#: Quantas ocorrências citar no aviso. O resto fica na tela — um aviso com
#: quarenta linhas não é aviso, é relatório, e ninguém lê relatório no sino.
NO_AVISO = 3


def notificar(avaliacao: Avaliacao, quem=None) -> int:
    """Avisa quem responde pela regra. Devolve quantas pessoas foram avisadas.

    Uma notificação por PESSOA e não uma por ocorrência: quarenta avisos sobre a
    mesma regra transformam o sino num lugar que se aprende a ignorar — e o
    aviso que importa some junto.

    Zero é resposta legítima: ninguém ocupa o papel. Isso é um achado, e não um
    erro de operação — é a regra 2 aparecendo por outro caminho.
    """
    from django.urls import reverse

    from workspace.models.notificacao import TipoNotificacao
    from workspace.services import notificacoes as nt

    destinatarios = reg.titulares(avaliacao.regra.escopo_papel)
    if not destinatarios:
        return 0

    amostra = ", ".join(o.titulo for o in avaliacao.ocorrencias[:NO_AVISO])
    resto = max(avaliacao.total - NO_AVISO, 0)
    corpo = amostra + (f" e mais {resto}" if resto else "")

    for pessoa in destinatarios:
        nt.criar(
            pessoa,
            TipoNotificacao.EXCECAO_ABERTA,
            titulo=f"{avaliacao.regra.titulo}: {avaliacao.total}",
            corpo=corpo,
            url=reverse("workspace:excecoes"),
            # `dominio` + `origem_id` alimentam o dedupe de `criar()`: avisar
            # duas vezes sobre a mesma regra enquanto a primeira não foi lida é
            # o caminho mais curto para o sino virar ruído.
            dominio="exc.regra",
            origem_id=avaliacao.regra.chave,
        )
    return len(destinatarios)
