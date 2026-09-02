"""O carimbo de frescor — de quando é este número, bloco a bloco.

## Por que POR BLOCO e não por tela

Um carimbo no topo da tela funciona enquanto a tela tem uma fonte só. Ele deixa
de funcionar no dia em que a mesma tela mostra o resultado financeiro do Sankhya
em D-1 ao lado do andamento dos projetos do monday em minutos: um "atualizado
às 08:45" no cabeçalho estaria certo sobre metade do conteúdo e errado sobre a
outra, sem nada na tela dizendo qual metade.

Carimbar por bloco custa mais espaço e resolve isso de vez. E o custo é menor do
que parece, porque bloco aqui não é "cada número": é **cada conjunto de números
que compartilha fonte e janela**. Hoje o Workspace tem uma fonte só — ele mesmo
—, e a tela de Indicadores tem exatamente um bloco. A estrutura é que já está
certa para quando forem três.

## O carimbo NUNCA sai de `timezone.now()`

Ler a hora no momento de renderizar produz um carimbo que diz "agora" para todo
dado, inclusive para o que chegou ontem. É a forma mais silenciosa de mentir
numa tela executiva: ninguém confere, porque o carimbo está lá.

Para dado nativo, "agora" é a verdade — e mesmo aí o texto é "em tempo real", e
não um relógio, porque relógio convida a comparar com dado que tem carga. Para
qualquer outra fonte, o instante vem do registro de carga, pelo contrato
`workspace.providers.frescor`. Sem provedor registrado, o carimbo diz **"sem
registro de carga"** — que é a informação honesta, e não um vazio.

## Fonte que falhou não zera o bloco

Se a última carga falhou, o bloco continua mostrando o último dado bom, com a
idade em destaque e o motivo ao lado. Zerar seria dizer que a empresa parou.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from workspace.providers import frescor as contrato
from workspace.providers.frescor import FALHA, NATIVO, PARCIAL, SUCESSO  # noqa: F401


@dataclass(frozen=True)
class BlocoAgregado:
    """Um conjunto de números que compartilha fonte e janela.

    `titulo` não é renderizado hoje — nenhuma faixa desta onda tem cabeçalho
    próprio. Ele existe para quem lê `BLOCOS`: "panorama" e "bandeja" não dizem
    que tela é, e um registro que só o programador entende deixa de ser
    consultado.

    NÃO há um campo para "janela no nome". Quando a janela muda a leitura do
    número — `Contas a Receber (D-10)` —, ela entra no **título da faixa no
    template**, e não num rótulo montado aqui: quem abre a tela precisa saber de
    quando é o número antes de lê-lo, e um carimbo em letra miúda chega tarde
    demais. Ver EXEC 15 § 15.3.
    """

    chave: str
    titulo: str
    fonte: str = NATIVO


#: Toda tela com número agregado declara aqui os seus blocos.
#:
#: É esta declaração que o teste lê para exigir carimbo — não uma varredura de
#: template. A diferença importa: varredura acha o que está escrito, e o defeito
#: que interessa é o bloco que alguém acrescentou e ESQUECEU de carimbar.
#:
#: A convenção que torna isto mecânico: **uma linha de números agregados usa
#: `au-kpi-linha` no template**, e `test_frescor.py` exige que toda tela com essa
#: classe apareça aqui. Quem construir a próxima faixa de números descobre a
#: obrigação na suíte, e não na reunião em que alguém perguntar de quando é o
#: número.
BLOCOS: dict[str, tuple[BlocoAgregado, ...]] = {
    "workspace:indicadores": (
        BlocoAgregado("panorama", "Indicadores", fonte=NATIVO),
    ),
    "workspace:aprovacoes": (
        BlocoAgregado("bandeja", "O que espera você", fonte=NATIVO),
    ),
    "workspace:fila": (
        BlocoAgregado("fila", "A fila da sua área", fonte=NATIVO),
    ),
    "workspace:universidade_painel": (
        BlocoAgregado("habilitacoes", "Habilitações", fonte=NATIVO),
    ),
}


@dataclass(frozen=True)
class Carimbo:
    """O carimbo pronto para a tela."""

    fonte: str
    rotulo: str
    janela: str = ""
    idade: str = ""
    alerta: bool = False
    motivo: str = ""
    #: `False` quando ninguém sabe responder por esta fonte. A tela diz isso em
    #: vez de inventar um instante.
    conhecido: bool = True

    @property
    def texto(self) -> str:
        """A linha do carimbo: fonte · janela · idade."""
        partes = [self.rotulo]
        if self.janela:
            partes.append(self.janela)
        if self.idade:
            partes.append(self.idade)
        return " · ".join(partes)


def blocos_de(url_name: str) -> tuple[BlocoAgregado, ...]:
    """Os blocos agregados desta tela. Vazio quando ela não tem nenhum."""
    return BLOCOS.get(url_name, ())


def carimbos_de(url_name: str, competencia=None) -> dict[str, Carimbo]:
    """Os carimbos da tela, por chave de bloco — o que a view põe no contexto."""
    return {
        bloco.chave: de(bloco.fonte, competencia=competencia)
        for bloco in blocos_de(url_name)
    }


def de(fonte: str = NATIVO, competencia=None) -> Carimbo:
    """O carimbo desta fonte, agora."""
    if fonte == NATIVO:
        # Sem provedor e sem relógio: o dado é lido quando a tela abre, e
        # "em tempo real" é literalmente verdade. Pôr um horário aqui faria o
        # número nativo parecer ter carga, e convidaria a comparar a idade dele
        # com a de uma fonte que tem.
        return Carimbo(
            fonte=NATIVO, rotulo=str(_("Workspace")), janela=str(_("em tempo real"))
        )

    provedor = contrato.obter()
    dto = provedor.carimbo(fonte, competencia=competencia) if provedor else None
    if dto is None:
        return Carimbo(
            fonte=fonte,
            rotulo=fonte,
            janela=str(_("sem registro de carga")),
            alerta=True,
            conhecido=False,
        )

    return Carimbo(
        fonte=dto.fonte,
        rotulo=dto.rotulo or dto.fonte,
        janela=dto.janela,
        idade=_idade(dto.carregado_em),
        alerta=_alerta(dto),
        motivo=dto.motivo,
    )


def _alerta(dto) -> bool:
    """Carimbo vira alerta quando a última tentativa falhou ou o dado passou da
    idade que a própria fonte declarou aceitável."""
    if dto.status != SUCESSO:
        return True
    if dto.idade_maxima is None or dto.carregado_em is None:
        return False
    return timezone.now() - dto.carregado_em > dto.idade_maxima


def _idade(quando) -> str:
    """"há 4 min", "há 6 h", "há 2 dias" — a idade, não o relógio.

    Idade e não `18/08/2026 08:45`, porque a pergunta que a pessoa faz diante do
    número é "isso está velho?", e a data obriga cada leitor a fazer a subtração
    de cabeça — na reunião, com o número na tela.
    """
    if quando is None:
        return ""
    decorrido = timezone.now() - quando
    if decorrido < timedelta(0):
        # Relógio do servidor de carga adiantado. Melhor não afirmar nada do que
        # afirmar "há -3 min".
        return ""
    minutos = int(decorrido.total_seconds() // 60)
    if minutos < 1:
        return str(_("agora há pouco"))
    if minutos < 60:
        return str(_("há %(n)d min") % {"n": minutos})
    horas = minutos // 60
    if horas < 48:
        return str(_("há %(n)d h") % {"n": horas})
    return str(_("há %(n)d dias") % {"n": horas // 24})
