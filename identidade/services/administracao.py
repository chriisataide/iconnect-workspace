"""Conceder e revogar papel — as regras por trás da tela de aprovadores.

## Por que uma tela, e não o `/admin/`

O `/admin/` do Django faz isso desde o primeiro dia, e continua fazendo. O que
ele não faz é ser usável por quem precisa: o R.H. que vai cadastrar o aprovador
de Compras não sabe o que é `AtribuicaoPapel`, não entende por que há um campo
`escopo` com quatro valores, e não tem como saber que conceder escopo `global`
por engano dá à pessoa acesso a todos os pedidos da empresa.

Esta camada existe para que a tela possa ser burra: ela mostra pessoa, área e
período; as regras que impedem estrago moram aqui.

## O estrago que ela impede

**Escopo global concedido sem querer.** É a diferença entre "aprova a própria
equipe" e "aprova a empresa inteira", e no admin os dois são uma opção num
`<select>` idêntico. Aqui, escopo global exige justificativa escrita.

**Papel sem fim para quem está de saída.** `vigencia_fim` existia e quase nunca
era preenchida — a tela sugere data de término e o serviço aceita, porque papel
que expira sozinho é a única forma de acesso temporário que não depende de
alguém lembrar.

**Auditoria vazia.** `concedido_por` é obrigatório aqui. No admin ele era
opcional, e uma concessão sem autor não responde à única pergunta que importa
depois de um incidente: quem deu esse acesso?
"""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from identidade.models import AtribuicaoPapel, Lotacao, Papel

# Escopos que alcançam gente além de quem recebe o papel. Conceder um destes é
# decisão, não configuração — por isso exigem justificativa.
ESCOPOS_AMPLOS = ("global", "unidade")


class AdministracaoError(Exception):
    """A concessão não pode ser feita assim."""


def pode_administrar(pessoa, cache: dict | None = None) -> bool:
    """Quem cadastra aprovador.

    `rh.admin` e não um papel novo: quem mantém o organograma é o R.H., e criar
    um papel "administrador de papéis" só para esta tela produziria mais uma
    lista de gente para manter em dia.
    """
    from identidade.services.autorizacao import pode

    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        return False
    if getattr(pessoa, "is_superuser", False):
        return True
    return pode(pessoa, "rh.admin", cache=cache)


def quem_administra():
    """Quem pode consertar um papel sem dono.

    Existe para que o produto tenha a quem RECLAMAR. Uma etapa de aprovação por
    papel que ninguém ocupa não aparece na bandeja de ninguém — ela não tem
    destinatário —, e o pedido fica parado sem que uma única pessoa saiba.
    Avisar quem pode conceder o papel é o que fecha esse silêncio.

    Só quem já tem alguma atribuição vigente entra na conta, mais os
    superusuários: `rh.admin` chega por papel, e varrer a tabela inteira de
    gente para perguntar o mesmo a cada uma custaria uma consulta por
    colaborador da empresa.
    """
    from django.contrib.auth import get_user_model
    from django.db.models import Q

    from identidade.services.autorizacao import pode

    com_papel = AtribuicaoPapel.objects.vigentes().values_list("user_id", flat=True)
    candidatos = (
        get_user_model()
        .objects.filter(Q(pk__in=com_papel) | Q(is_superuser=True), is_active=True)
        .distinct()
    )
    return [pessoa for pessoa in candidatos if pode(pessoa, "rh.admin")]


def papeis_concedíveis():
    """Todos os papéis ativos, em ordem de nome."""
    return Papel.objects.filter(ativo=True).order_by("nome")


def pessoas_administraveis():
    """Quem pode receber papel: gente com lotação.

    Sem lotação, a pessoa não está no organograma — e papel de aprovador para
    quem não tem unidade, departamento nem gestor é exatamente a origem das 881
    lotações vazias que fizeram este produto existir separado.
    """
    return (
        Lotacao.objects.select_related("user", "unidade", "departamento")
        .order_by("user__nome", "user__email")
    )


def definir_centro_de_custo(pessoa, codigo: str, quem) -> Lotacao:
    """Grava em que centro de custo a pessoa é debitada.

    ## Por que isto não existia, e o que custava

    `Lotacao.centro_custo_codigo` é lido em três lugares que decidem dinheiro: o
    pedido do catálogo o copia na hora de nascer, a bandeja de aprovação monta
    a barra de orçamento com ele, e o compromisso é baixado por ele. O campo era
    populado por um `semear` e por mais nada — a única porta para corrigi-lo era
    o `/admin/`, que pede `is_staff`.

    O efeito prático: pessoa admitida depois da carga entra sem centro de custo,
    o primeiro pedido dela que exige um é recusado com "sua lotação não tem
    centro de custo", e quem pode resolver (o R.H.) não tem onde.

    ## Vazio é resposta válida

    Limpar o campo é diferente de apontá-lo para o lugar errado, e o produto já
    sabe dizer o primeiro: o catálogo recusa o pedido explicando o que falta. É
    por isso que string vazia passa em vez de virar erro.
    """
    if not pode_administrar(quem):
        raise AdministracaoError("Você não administra lotações.")

    lotacao = Lotacao.objects.filter(user=pessoa).first()
    if lotacao is None:
        # Sem lotação a pessoa não está no organograma, e centro de custo solto
        # não tem onde morar. Dizer isso é melhor que criar uma lotação vazia
        # pelas costas de quem clicou.
        raise AdministracaoError(
            f"{pessoa} não tem lotação. Cadastre a lotação antes do centro de custo."
        )

    lotacao.centro_custo_codigo = (codigo or "").strip()[:20]
    lotacao.save(update_fields=["centro_custo_codigo", "atualizado_em"])
    return lotacao


def atribuicoes_de(pessoa):
    return (
        AtribuicaoPapel.objects.filter(user=pessoa)
        .select_related("papel", "unidade", "departamento", "concedido_por")
        .order_by("-vigencia_inicio", "papel__nome")
    )


@transaction.atomic
def conceder(
    *,
    pessoa,
    papel: Papel,
    escopo: str,
    quem,
    justificativa: str = "",
    vigencia_fim=None,
    unidade=None,
    departamento=None,
) -> AtribuicaoPapel:
    """Dá um papel a alguém, com escopo e prazo."""
    if not pode_administrar(quem):
        raise AdministracaoError("Você não pode conceder papéis.")

    if not Lotacao.objects.filter(user=pessoa).exists():
        raise AdministracaoError(
            "Esta pessoa não tem lotação. Cadastre a lotação antes do papel — "
            "aprovador sem unidade e sem gestor não tem escopo que signifique algo."
        )

    justificativa = (justificativa or "").strip()
    if escopo in ESCOPOS_AMPLOS and not justificativa:
        raise AdministracaoError(
            f"Escopo {escopo} alcança gente além da própria pessoa. "
            "Escreva por que este acesso é necessário."
        )

    if vigencia_fim and vigencia_fim < timezone.localdate():
        raise AdministracaoError("A data de término já passou.")

    ja_tem = AtribuicaoPapel.objects.vigentes().filter(
        user=pessoa, papel=papel, escopo=escopo
    ).exists()
    if ja_tem:
        raise AdministracaoError(f"{pessoa} já tem {papel} com escopo {escopo}.")

    return AtribuicaoPapel.objects.create(
        user=pessoa,
        papel=papel,
        escopo=escopo,
        unidade=unidade,
        departamento=departamento,
        vigencia_fim=vigencia_fim,
        concedido_por=quem,
        justificativa=justificativa,
    )


@transaction.atomic
def revogar(atribuicao: AtribuicaoPapel, quem, motivo: str = "") -> AtribuicaoPapel:
    """Encerra o papel AGORA, sem apagar a linha.

    Encerrar e não deletar: a pergunta "quem aprovava isso em março?" tem de
    continuar respondível depois que a pessoa muda de área.

    **Por que a data de fim é ONTEM, e não hoje.** A vigência tem granularidade
    de DIA, e `vigentes()` inclui o dia de fim — `fim = hoje` deixaria o papel
    valendo até a meia-noite. Quem aperta "encerrar" quase sempre está
    encerrando por um motivo que não espera até meia-noite: a pessoa saiu, ou o
    acesso foi concedido errado. Então o corte é imediato, e a data que sobra na
    linha é a do último dia em que o papel de fato valeu.

    O `max()` cobre a borda: papel concedido e revogado no MESMO dia não pode
    terminar antes de começar. Nesse caso ele vale até a meia-noite — é um
    acesso de minutos, dado e tirado pela mesma pessoa.
    """
    if not pode_administrar(quem):
        raise AdministracaoError("Você não pode revogar papéis.")

    hoje = timezone.localdate()
    if atribuicao.vigencia_fim and atribuicao.vigencia_fim <= hoje:
        raise AdministracaoError("Este papel já estava encerrado.")

    atribuicao.vigencia_fim = max(
        hoje - timedelta(days=1), atribuicao.vigencia_inicio
    )
    if motivo:
        separador = "\n" if atribuicao.justificativa else ""
        atribuicao.justificativa = (
            f"{atribuicao.justificativa}{separador}Revogado em {hoje}: {motivo.strip()}"
        )
    atribuicao.save(update_fields=["vigencia_fim", "justificativa"])
    return atribuicao
