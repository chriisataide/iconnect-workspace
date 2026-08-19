"""EST — entregar, aceitar e devolver equipamento. §17.

## As três regras que este módulo existe para garantir

1. **Entregar baixa o estoque.** A custódia não é um cadastro paralelo: o
   capacete que está com alguém não está mais na prateleira, e um sistema que
   registra a entrega sem baixar o saldo passa a mentir sobre as duas coisas.

2. **Devolver devolve ao saldo — pela condição.** Material que volta bom volta
   para o estoque; material que volta como sucata entra no razão e **não** no
   saldo. É a mesma regra do §15, e é a mesma função: `entrada_de_reversa`.

3. **Ninguém entrega para si mesmo.** Segregação de função, o controle mais
   básico de patrimônio. Quem opera o estoque também recebe equipamento — e
   nesse dia quem assina a entrega é outra pessoa.

## Por que a devolução não pede permissão da pessoa que devolve

Quem dá baixa é Suprimentos, sempre — a pessoa entrega o objeto na mão de
alguém, e é esse alguém que registra. Deixar a própria pessoa fechar a custódia
faria o registro dizer "devolvido" sem que nada tenha voltado, que é exatamente
o buraco que o §17 fecha.
"""

from __future__ import annotations

from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from identidade.services.autorizacao import pode
from workspace.models.custodia import Custodia
from workspace.models.estoque import CondicaoMaterial, Material, TipoMovimento
from workspace.models.notificacao import TipoNotificacao
from workspace.services import estoque as est

PERMISSAO_LER = "log.custodia.ler"
PERMISSAO_ATRIBUIR = "log.custodia.atribuir"


class CustodiaError(Exception):
    """A entrega ou a devolução não pode acontecer."""


def pode_ler(pessoa, cache: dict | None = None) -> bool:
    """Ver o que está com os outros. Quem ATRIBUI também lê.

    Sem a soma, o papel que entrega equipamento não enxergaria o que acabou de
    entregar — e teria de declarar as duas permissões para fazer uma coisa só.
    """
    return pode(pessoa, PERMISSAO_LER, cache=cache) or pode(
        pessoa, PERMISSAO_ATRIBUIR, cache=cache
    )


def pode_atribuir(pessoa, cache: dict | None = None) -> bool:
    return pode(pessoa, PERMISSAO_ATRIBUIR, cache=cache)


# ── Consulta ────────────────────────────────────────────────────────


def minhas(pessoa):
    """O que está com esta pessoa, em uso primeiro.

    Sem permissão nenhuma: é a resposta a "o que eu tenho da empresa", e negá-la
    à própria pessoa seria pedir que ela assine um termo que não pode ler.
    """
    return (
        Custodia.objects.de(pessoa)
        .select_related("material", "unidade", "entregue_por")
        .order_by("devolvido_em", "-entregue_em")
    )


def a_aceitar(pessoa):
    """O que foi entregue no nome da pessoa e ainda espera a palavra dela."""
    return (
        Custodia.objects.de(pessoa)
        .a_aceitar()
        .select_related("material", "unidade", "entregue_por")
    )


def em_poder_de_terceiros(pessoa, unidade=None, cache: dict | None = None):
    """Quem está com o quê — a tela de quem controla o patrimônio.

    Exige permissão: a lista diz o que cada colega levou para casa, e isso é
    informação sobre pessoas, não sobre material.
    """
    if not pode_ler(pessoa, cache=cache):
        return Custodia.objects.none()
    consulta = (
        Custodia.objects.em_uso()
        .select_related("material", "pessoa", "unidade", "entregue_por")
        .order_by("pessoa__nome", "material__nome")
    )
    if unidade is not None:
        consulta = consulta.filter(unidade=unidade)
    return consulta


# ── Entregar ────────────────────────────────────────────────────────


@transaction.atomic
def entregar(
    material: Material,
    pessoa,
    quem,
    unidade=None,
    quantidade: int = 1,
    patrimonio: str = "",
    numero_serie: str = "",
    observacao: str = "",
    cache: dict | None = None,
) -> Custodia:
    """Baixa do estoque e registra o responsável, ou nada.

    A ordem importa: a saída vem ANTES da custódia, e é ela que dá o "ou nada"
    da transação. Registrar a custódia primeiro deixaria, num saldo insuficiente,
    um termo de responsabilidade por um material que não existe.
    """
    if not pode_atribuir(quem, cache=cache):
        raise CustodiaError("Você não pode entregar material sob custódia.")
    if pessoa is None or getattr(pessoa, "pk", None) is None:
        raise CustodiaError("Escolha para quem o material está sendo entregue.")
    if pessoa.pk == getattr(quem, "pk", None):
        # Segregação de função. Quem opera o estoque também recebe equipamento —
        # e nesse dia quem assina a entrega é outra pessoa.
        raise CustodiaError(
            "Você não pode registrar uma entrega para si mesmo — peça a um colega."
        )
    if quantidade <= 0:
        raise CustodiaError("A quantidade tem de ser maior que zero.")

    unidade = unidade or est.unidade_de(pessoa)
    if unidade is None:
        # Sem unidade não há de qual prateleira baixar, e a devolução não teria
        # para onde voltar. Falhar aqui é melhor que escolher uma unidade
        # qualquer e descobrir na conferência.
        raise CustodiaError(
            "Esta pessoa não tem unidade de lotação — a baixa não teria de onde sair."
        )

    est.movimentar(
        material,
        unidade,
        TipoMovimento.SAIDA,
        quantidade,
        quem=quem,
        dominio="log.custodia",
        observacao=f"Custódia de {pessoa.get_full_name()}.",
    )

    custodia = Custodia.objects.create(
        material=material,
        pessoa=pessoa,
        unidade=unidade,
        quantidade=quantidade,
        patrimonio=patrimonio.strip()[:40],
        numero_serie=numero_serie.strip()[:60],
        entregue_por=quem,
        observacao=observacao.strip()[:300],
    )
    _avisar_da_entrega(custodia)
    return custodia


def _avisar_da_entrega(custodia: Custodia) -> None:
    """O aviso é o que transforma o registro em termo.

    Sem ele a pessoa passa a responder por um equipamento sem nunca ter sido
    informada — e o aceite do §17, que é o ponto do módulo, nunca acontece.
    """
    from workspace.services import notificacoes as nt

    etiqueta = f" ({custodia.identificacao})" if custodia.identificacao else ""
    nt.criar(
        custodia.pessoa,
        TipoNotificacao.EQUIPAMENTO_SOB_CUSTODIA,
        f"{custodia.material.nome}{etiqueta} está no seu nome",
        "Confirme o recebimento para registrar que o equipamento chegou até você.",
        url=reverse("workspace:custodia"),
        dominio="log.custodia",
        origem_id=str(custodia.pk),
    )


@transaction.atomic
def aceitar(custodia: Custodia, pessoa) -> Custodia:
    """A pessoa diz que recebeu. Só ela pode dizer isso."""
    if custodia.pessoa_id != getattr(pessoa, "pk", None):
        raise CustodiaError("Só quem está com o material pode confirmar o recebimento.")
    if not custodia.em_uso:
        raise CustodiaError("Esta custódia já foi encerrada.")
    if custodia.aceita:
        return custodia

    custodia.aceito_em = timezone.now()
    custodia.save(update_fields=["aceito_em"])
    return custodia


# ── Devolver ────────────────────────────────────────────────────────


@transaction.atomic
def devolver(
    custodia: Custodia,
    quem,
    condicao: str,
    observacao: str = "",
    cache: dict | None = None,
) -> Custodia:
    """Fecha a custódia e devolve ao razão — pela condição.

    Bom volta para o saldo; sucata entra no razão e fica fora dele. É a mesma
    `entrada_de_reversa()` do §15, e de propósito: material devolvido É material
    que voltou de campo, e a pergunta "o que dá para reaproveitar" não pode ter
    duas respostas conforme o caminho de volta.
    """
    if not pode_atribuir(quem, cache=cache):
        raise CustodiaError("Você não pode dar baixa em custódia.")
    if not custodia.em_uso:
        raise CustodiaError("Esta custódia já foi encerrada.")
    if condicao not in CondicaoMaterial.values:
        raise CustodiaError("Informe em que condição o material voltou.")

    est.entrada_de_reversa(
        custodia.material,
        custodia.unidade,
        custodia.quantidade,
        condicao,
        quem=quem,
        patrimonio=custodia.patrimonio,
        observacao=f"Devolução de {custodia.pessoa.get_full_name()}.",
    )

    custodia.devolvido_em = timezone.now()
    custodia.devolvido_por = quem
    custodia.condicao_devolucao = condicao
    if observacao.strip():
        custodia.observacao = observacao.strip()[:300]
    custodia.save(
        update_fields=[
            "devolvido_em",
            "devolvido_por",
            "condicao_devolucao",
            "observacao",
        ]
    )
    return custodia


def pendencias_de(pessoa) -> list[Custodia]:
    """O que esta pessoa ainda tem para devolver — a pergunta do desligamento.

    Lista e não `count()`: quem faz a conferência precisa dos itens, e um número
    sozinho obriga a segunda consulta na tela seguinte.
    """
    return list(
        Custodia.objects.de(pessoa).em_uso().select_related("material", "unidade")
    )
