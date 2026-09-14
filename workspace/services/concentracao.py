"""ECO — a concentração, e as três categorias da faixa de destaques. §E1.

## O que este módulo NÃO faz

**Não gera destaque nem ponto de atenção.** Esses saem de regra, em
`resultados.destaques`, e ninguém os edita. Misturar as duas coisas aqui faria
a tela deixar de refletir o espelho e passar a refletir quem mexeu por último.

**Não apaga.** Encerrar é o fim da vida de uma concentração, e o histórico é
justamente o que responde "a empresa resolve o que decide olhar?". Um botão de
excluir apagaria essa resposta uma decisão de cada vez.

## Quem pode marcar

`eco.concentrar` — permissão PRÓPRIA, e não `eco.ler`. Ler o resultado da
empresa é uma coisa; declarar onde ela vai se concentrar é outra, e a segunda é
de quem responde pelo período. Reusar `eco.ler` daria a marca a todo mundo que
abre a tela, e uma lista de foco que qualquer um edita deixa de ser foco.
"""

from __future__ import annotations

from django.db import IntegrityError, transaction
from django.utils import timezone

from identidade.services.autorizacao import pode
from workspace.models.concentracao import Concentracao, OrigemConcentracao

PERMISSAO = "eco.concentrar"

#: Quantas concentrações abertas cabem ao mesmo tempo.
#:
#: Cinco. Não é limite técnico — é o que "concentração" quer dizer: uma lista de
#: quinze focos é uma lista de tarefas, e a diretoria já tem uma. O sexto item
#: obriga a encerrar um, que é a conversa que a tela existe para forçar.
MAXIMO_ABERTAS = 5


class ConcentracaoError(Exception):
    """O pedido não pode ser atendido, e a mensagem vai para a tela."""


def pode_concentrar(pessoa, cache: dict | None = None) -> bool:
    return bool(pode(pessoa, PERMISSAO, cache=cache))


def atualizar_passo(concentracao, pessoa, proximo_passo, cache=None):
    if not pode_concentrar(pessoa, cache=cache):
        raise ConcentracaoError("Você não tem permissão para atualizar concentrações.")
    passo = (proximo_passo or "").strip()
    if not passo or len(passo) > 500:
        raise ConcentracaoError("Informe o próximo passo, com até 500 caracteres.")
    alteradas = Concentracao.objects.abertas().filter(pk=concentracao.pk).update(proximo_passo=passo)
    if not alteradas:
        raise ConcentracaoError("Esta concentração já foi encerrada.")


def abertas():
    """As concentrações em aberto, da de prazo mais próximo para a mais longe.

    `select_related` no responsável: a tela mostra o nome de cada um, e sem ele
    seriam cinco consultas para cinco linhas.
    """
    return list(
        Concentracao.objects.abertas().select_related("responsavel")
    )


def encerradas(limite: int = 12):
    """O HISTÓRICO — e ele é o produto, não o rascunho.

    Uma lista só de abertas responde "no que estamos". A lista fechada responde
    "as últimas doze viraram o quê", que é a pergunta que muda comportamento.

    Doze: um ano de reuniões mensais. Menos que isso não mostra padrão; mais
    vira arquivo, e arquivo se consulta noutro lugar.
    """
    return list(
        Concentracao.objects.encerradas()
        .select_related("responsavel")
        .order_by("-encerrada_em")[:limite]
    )


@transaction.atomic
def abrir(
    pessoa,
    *,
    origem_tipo: str,
    origem_ref: str,
    titulo: str,
    motivo: str,
    responsavel,
    prazo=None,
    proximo_passo: str = "",
    alerta_chave: str = "",
    cache: dict | None = None,
) -> Concentracao:
    """Marca um foco do período.

    O MOTIVO é obrigatório, e não é burocracia: uma concentração sem motivo é um
    item de lista, e listas de itens sem motivo é o que reuniões produzem quando
    ninguém decide nada. Em três meses ninguém lembra por que aquilo entrou.
    """
    if not pode_concentrar(pessoa, cache=cache):
        raise ConcentracaoError(
            "Marcar uma concentração é de quem responde pelo período."
        )

    titulo = (titulo or "").strip()
    motivo = (motivo or "").strip()
    if not titulo:
        raise ConcentracaoError("A concentração precisa de um título.")
    if not motivo:
        raise ConcentracaoError(
            "Diga POR QUE isto é foco. Em três meses ninguém lembra."
        )
    if origem_tipo not in OrigemConcentracao.values:
        raise ConcentracaoError("Escolha se o foco é um contrato, uma área ou um indicador.")
    if not (origem_ref or "").strip():
        raise ConcentracaoError("Diga QUAL contrato, área ou indicador.")
    if responsavel is None:
        raise ConcentracaoError("Toda concentração tem um responsável.")

    alerta_chave = (alerta_chave or "").strip()[:64]
    if alerta_chave:
        existente = Concentracao.objects.abertas().filter(alerta_chave=alerta_chave).first()
        if existente:
            return existente
    if Concentracao.objects.abertas().count() >= MAXIMO_ABERTAS:
        raise ConcentracaoError(
            f"Já há {MAXIMO_ABERTAS} concentrações abertas. Encerre uma antes "
            "de abrir outra — uma lista de quinze focos não é foco."
        )

    campos = dict(
        origem_tipo=origem_tipo,
        origem_ref=origem_ref.strip()[:60],
        titulo=titulo[:200],
        motivo=motivo,
        responsavel=responsavel,
        prazo=prazo,
        aberta_por=pessoa,
        proximo_passo=(proximo_passo or "").strip()[:500],
        alerta_chave=alerta_chave,
    )
    try:
        with transaction.atomic():
            return Concentracao.objects.create(**campos)
    except IntegrityError:
        if alerta_chave:
            existente = Concentracao.objects.abertas().filter(alerta_chave=alerta_chave).first()
            if existente:
                return existente
        raise


@transaction.atomic
def encerrar(
    concentracao: Concentracao, pessoa, resultado: str, cache: dict | None = None
) -> Concentracao:
    """Fecha, com o que aconteceu escrito.

    O RESULTADO é obrigatório pela mesma razão que o motivo: encerrar sem dizer
    o que aconteceu transformaria o histórico numa lista de datas, e a pergunta
    que ele existe para responder ficaria sem resposta.
    """
    if not pode_concentrar(pessoa, cache=cache):
        raise ConcentracaoError(
            "Encerrar uma concentração é de quem responde pelo período."
        )
    if not concentracao.aberta:
        # Não é erro de programação: duas pessoas na mesma reunião, dois
        # cliques. A segunda precisa de uma frase, e não de um 500.
        raise ConcentracaoError("Esta concentração já foi encerrada.")

    resultado = (resultado or "").strip()
    if not resultado:
        raise ConcentracaoError(
            "Diga o que aconteceu. É o histórico que mostra se a empresa "
            "resolve o que decide olhar."
        )

    concentracao.resultado = resultado
    concentracao.encerrada_em = timezone.now()
    concentracao.save(update_fields=["resultado", "encerrada_em"])
    return concentracao
