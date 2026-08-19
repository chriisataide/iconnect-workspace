"""EST — movimentar estoque sem que dois pedidos gastem a mesma peça.

## O problema que o `select_for_update` resolve

Ler o saldo, conferir que dá, e gravar é seguro exatamente até o segundo
usuário. Duas requisições simultâneas do último capacete leem "1", as duas
concluem que cabe, e as duas gravam — o razão fica com duas saídas e o saldo com
`-1`. Não é caso raro: é o que acontece no dia da entrega de EPI, quando três
pessoas de Suprimentos atendem a fila ao mesmo tempo.

A linha de saldo é travada antes da leitura, e liberada no fim da transação.

## Por que o saldo negativo é impossível em dois lugares

Aqui, com mensagem que a pessoa entende; e no banco, com `CheckConstraint`. O
serviço é a porta certa e a constraint é a que sobra quando alguém fizer um
`update()` distraído numa migração de dados — que é como estoque fica errado na
prática, não por concorrência.
"""

from __future__ import annotations

from django.db import transaction
from django.db.models import F, Sum

from workspace.models.estoque import (
    CondicaoMaterial,
    Material,
    MovimentoEstoque,
    SaldoEstoque,
    TipoMovimento,
)


class EstoqueError(Exception):
    """O movimento não pode acontecer. A mensagem é para a pessoa, não para o log."""


#: Os tipos que AUMENTAM o saldo. Em um lugar só porque a lista aparece em três
#: contas diferentes, e a versão que esquece `REVERSA` produz saldo que some.
ENTRADAS = (TipoMovimento.ENTRADA, TipoMovimento.REVERSA)


def saldo_de(material: Material, unidade) -> int:
    """Quanto existe deste material nesta unidade. Zero quando nunca houve."""
    linha = SaldoEstoque.objects.filter(material=material, unidade=unidade).first()
    return linha.quantidade if linha else 0


def disponivel_para(pessoa, unidade=None):
    """Os saldos que interessam a esta pessoa, com o material já carregado.

    Sem `unidade`, devolve tudo — é a visão de quem administra o estoque. Com
    `unidade`, só o que está ao alcance de quem vai retirar: "temos 40" é
    inútil para quem está em Campinas quando os 40 estão em São Paulo.
    """
    consulta = SaldoEstoque.objects.select_related("material", "unidade").filter(
        material__ativo=True
    )
    if unidade is not None:
        consulta = consulta.filter(unidade=unidade)
    return consulta.order_by("material__nome")


@transaction.atomic
def movimentar(
    material: Material,
    unidade,
    tipo: str,
    quantidade: int,
    quem=None,
    observacao: str = "",
    dominio: str = "",
    origem_id: str = "",
    **extras,
) -> MovimentoEstoque:
    """Uma linha no razão e o saldo atualizado, ou nada.

    `extras` carrega os campos que só a reversa usa (condição, procedência,
    cliente, patrimônio). Passados soltos e não num dicionário próprio porque
    quem chama já sabe qual tipo está criando.
    """
    if tipo == TipoMovimento.AJUSTE:
        # Ajuste aceita ZERO, e os outros tipos não. Não é exceção arbitrária:
        # em entrada e saída a quantidade é um MOVIMENTO, e movimento de zero
        # não é nada. No ajuste ela é o saldo CONTADO — e "a prateleira está
        # vazia" é a contagem mais importante que existe. Recusá-la deixava o
        # inventário sem como zerar um item, e o saldo fantasma ficava para
        # sempre.
        if quantidade < 0:
            raise EstoqueError("A contagem não pode ser negativa.")
    elif quantidade <= 0:
        # Zero não é movimento, e negativo é o sinal invertido — os dois
        # corrompem o razão de formas que só aparecem na conferência do mês.
        raise EstoqueError("A quantidade tem de ser maior que zero.")

    if tipo == TipoMovimento.REVERSA and not extras.get("condicao"):
        raise EstoqueError("Reversa exige a condição do material.")

    # `select_for_update` ANTES de ler o saldo: é a trava que impede duas
    # requisições simultâneas de gastarem a mesma peça.
    linha = (
        SaldoEstoque.objects.select_for_update()
        .filter(material=material, unidade=unidade)
        .first()
    )
    if linha is None:
        linha = SaldoEstoque.objects.create(
            material=material, unidade=unidade, quantidade=0
        )

    anterior = linha.quantidade
    if tipo in ENTRADAS:
        posterior = anterior + quantidade
    elif tipo == TipoMovimento.SAIDA:
        posterior = anterior - quantidade
        if posterior < 0:
            raise EstoqueError(
                f"Saldo insuficiente: há {anterior} {material.get_unidade_medida_display().lower()} "
                f"de {material.nome} nesta unidade."
            )
    elif tipo == TipoMovimento.AJUSTE:
        # O saldo CONTADO, não um delta: quem conta a prateleira sabe quantos
        # viu, não a diferença. Pedir o delta obrigaria a pessoa a fazer a
        # subtração de cabeça — e é aí que o inventário passa a errar.
        posterior = quantidade
    else:
        raise EstoqueError(f"Tipo de movimento desconhecido: {tipo!r}")

    linha.quantidade = posterior
    linha.save(update_fields=["quantidade", "atualizado_em"])

    return MovimentoEstoque.objects.create(
        material=material,
        unidade=unidade,
        tipo=tipo,
        quantidade=quantidade,
        saldo_anterior=anterior,
        saldo_posterior=posterior,
        quem=quem,
        observacao=observacao,
        dominio=dominio,
        origem_id=origem_id,
        **extras,
    )


def entrada_de_reversa(
    material: Material,
    unidade,
    quantidade: int,
    condicao: str,
    quem=None,
    unidade_origem=None,
    cliente: str = "",
    patrimonio: str = "",
    observacao: str = "",
) -> MovimentoEstoque:
    """Material que voltou de unidade desativada — §15.

    Sucata entra no razão e NÃO no saldo disponível. Isso não é detalhe: o §15
    existe para responder "o que dá para reaproveitar", e contar sucata nessa
    resposta faria alguém programar a entrega de um equipamento imprestável.
    O registro fica, porque o que voltou precisa ser rastreável até o descarte.
    """
    if condicao == CondicaoMaterial.SUCATA:
        return MovimentoEstoque.objects.create(
            material=material, unidade=unidade, tipo=TipoMovimento.REVERSA,
            quantidade=quantidade, saldo_anterior=saldo_de(material, unidade),
            saldo_posterior=saldo_de(material, unidade), quem=quem,
            condicao=condicao, unidade_origem=unidade_origem, cliente=cliente,
            patrimonio=patrimonio,
            observacao=observacao or "Sucata — fora do saldo disponível.",
        )

    return movimentar(
        material, unidade, TipoMovimento.REVERSA, quantidade, quem=quem,
        observacao=observacao, condicao=condicao, unidade_origem=unidade_origem,
        cliente=cliente, patrimonio=patrimonio,
    )


def baixar_por_pedido(material: Material, unidade, quantidade: int, solicitacao, quem=None):
    """A saída que fecha uma requisição atendida — §16.

    Amarrada ao pedido por `dominio` + `origem_id`: sem isso, a saída fica no
    razão sem dizer para quem foi, e a pergunta "quem levou os dez capacetes de
    março" volta a ser respondida por memória.
    """
    return movimentar(
        material, unidade, TipoMovimento.SAIDA, quantidade, quem=quem,
        dominio="log.requisicao",
        origem_id=str(solicitacao.pk),
        observacao=f"Requisição de {solicitacao.solicitante.get_full_name()}.",
    )


def razao_de(material: Material, unidade=None, limite: int | None = None):
    """O histórico do material, mais recente primeiro."""
    consulta = MovimentoEstoque.objects.filter(material=material).select_related(
        "quem", "unidade", "unidade_origem"
    )
    if unidade is not None:
        consulta = consulta.filter(unidade=unidade)
    return consulta[:limite] if limite else consulta


def conferir_razao(material: Material, unidade) -> tuple[int, int]:
    """`(saldo_gravado, saldo_somado_do_razão)`.

    Existe para que a divergência seja DETECTÁVEL. O saldo é atalho e o razão é
    a verdade; sem uma conta que compare os dois, uma diferença criada por
    `update()` fora do serviço só apareceria na contagem física do ano seguinte.
    """
    movimentos = MovimentoEstoque.objects.filter(material=material, unidade=unidade)
    ultimo_ajuste = movimentos.filter(tipo=TipoMovimento.AJUSTE).order_by("-quando").first()
    if ultimo_ajuste is not None:
        # Depois de um ajuste, o razão anterior não soma mais: a contagem física
        # SUBSTITUIU o histórico. Somar tudo desde o começo daria a diferença
        # que o ajuste existiu para corrigir.
        movimentos = movimentos.filter(quando__gt=ultimo_ajuste.quando)
        base = ultimo_ajuste.saldo_posterior
    else:
        base = 0

    entradas = movimentos.filter(tipo__in=ENTRADAS).aggregate(t=Sum("quantidade"))["t"] or 0
    saidas = movimentos.filter(tipo=TipoMovimento.SAIDA).aggregate(t=Sum("quantidade"))["t"] or 0
    # Sucata entra no razão sem mexer no saldo — precisa sair da soma também.
    sucata = (
        movimentos.filter(tipo=TipoMovimento.REVERSA, condicao=CondicaoMaterial.SUCATA)
        .aggregate(t=Sum("quantidade"))["t"]
        or 0
    )
    return saldo_de(material, unidade), base + entradas - sucata - saidas


# ── Quem pode o quê ─────────────────────────────────────────────────
#
# As quatro permissões estão declaradas em `identidade/papeis.py` desde a
# primeira onda e nunca tinham sido perguntadas por ninguém: o vocabulário
# existia e não havia porta que o consultasse. Ficam aqui, em constantes, e não
# escritas à mão em cada view — permissão digitada em string solta é a que
# ninguém percebe que virou `log.movimenta` num commit de sexta.

#: `log.estoque.ler` e NÃO `log.ler` — §48.
#:
#: `log.ler.proprio` está em `AUTOATENDIMENTO`, e "posso em geral?" é verdadeiro
#: para quem tem escopo próprio. Isso está certo para a tela "minhas
#: solicitações"; usado aqui, abria o saldo de TODAS as unidades, o razão e a
#: reversa para a empresa inteira. A permissão parecia específica de Suprimentos
#: e não era, e o teste manual passava porque quem testa tem o papel.
PERMISSAO_LER = "log.estoque.ler"
PERMISSAO_MOVIMENTAR = "log.movimentar"
PERMISSAO_CONTAR = "log.inventario.contar"


def pode_ler(pessoa, cache: dict | None = None) -> bool:
    """Ver saldo e razão. Quem MOVIMENTA também lê, sem precisar das duas.

    Sem esta soma, o papel de Suprimentos precisaria declarar `log.ler` ao lado
    de `log.movimentar` para enxergar aquilo que ele mesmo acabou de gravar — e
    é o tipo de dependência entre permissões que se descobre com a tela vazia.
    """
    from identidade.services.autorizacao import pode

    return (
        pode(pessoa, PERMISSAO_LER, cache=cache)
        or pode(pessoa, PERMISSAO_MOVIMENTAR, cache=cache)
        or pode(pessoa, PERMISSAO_CONTAR, cache=cache)
    )


def pode_movimentar(pessoa, cache: dict | None = None) -> bool:
    from identidade.services.autorizacao import pode

    return pode(pessoa, PERMISSAO_MOVIMENTAR, cache=cache)


def pode_contar(pessoa, cache: dict | None = None) -> bool:
    """Contar o inventário. Separado de movimentar POR SEGREGAÇÃO DE FUNÇÃO.

    Quem tira material da prateleira não deveria ser quem declara quanto sobrou
    — é o controle interno mais básico de patrimônio, e o papel de Suprimentos
    já foi desenhado assim: ele conta, mas não FECHA o inventário.
    """
    from identidade.services.autorizacao import pode

    return pode(pessoa, PERMISSAO_CONTAR, cache=cache)


def unidade_de(pessoa):
    """A unidade onde a pessoa está lotada, ou `None`.

    Aqui e não em cada chamador: o saldo é POR UNIDADE, e a pergunta "de qual
    prateleira estamos falando" aparece na requisição, na custódia e na tela de
    estoque. Três cópias divergem na primeira vez que a lotação ganhar regra.
    """
    from identidade.models import Lotacao

    lotacao = Lotacao.objects.filter(user=pessoa).select_related("unidade").first()
    return lotacao.unidade if lotacao else None


# ── Reversa — a pergunta do §15 ─────────────────────────────────────


def reversas(unidade=None, condicao: str | None = None, limite: int | None = None):
    """O que voltou de campo, mais recente primeiro.

    Sai do razão e não de tabela própria: reversa é uma ENTRADA com procedência,
    e uma tabela separada criaria a pergunta "o saldo soma as duas?" — o tipo de
    pergunta que se responde errado uma vez e ninguém percebe.
    """
    consulta = MovimentoEstoque.objects.filter(tipo=TipoMovimento.REVERSA).select_related(
        "material", "unidade", "unidade_origem", "quem"
    )
    if unidade is not None:
        consulta = consulta.filter(unidade=unidade)
    if condicao:
        consulta = consulta.filter(condicao=condicao)
    return consulta[:limite] if limite else consulta


def resumo_de_reversa(unidade=None) -> list[dict]:
    """Quanto voltou em cada condição — a resposta a "o que dá para reaproveitar".

    Uma linha por condição, e SEMPRE as quatro, mesmo zeradas. Omitir a condição
    sem movimento faria "0 em sucata" desaparecer da tela, e é exatamente esse
    número que alguém precisa ler para acreditar que a coluna existe.
    """
    consulta = MovimentoEstoque.objects.filter(tipo=TipoMovimento.REVERSA)
    if unidade is not None:
        consulta = consulta.filter(unidade=unidade)

    somas = dict(
        consulta.values_list("condicao").annotate(total=Sum("quantidade")).values_list(
            "condicao", "total"
        )
    )
    return [
        {
            "condicao": valor,
            "rotulo": rotulo,
            "total": somas.get(valor, 0) or 0,
            # A sucata entra no razão e NÃO no saldo. A tela precisa dizer isso,
            # senão alguém programa a entrega de um equipamento imprestável.
            "no_saldo": valor != CondicaoMaterial.SUCATA,
        }
        for valor, rotulo in CondicaoMaterial.choices
    ]
