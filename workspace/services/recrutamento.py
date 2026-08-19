"""RH — as candidaturas, vistas de quem recruta. §10.

## Por que NÃO existe um model `Candidatura`

A inscrição em vaga interna já é um pedido do catálogo: `rh.vaga`, com currículo
anexado, cadeia de aprovação, histórico e estado. Criar uma tabela paralela
seria a duplicação que o §1 proíbe — duas verdades sobre a mesma inscrição, e a
que diverge é sempre a que alguém esqueceu de atualizar.

O que faltava não era um modelo: era a **pergunta invertida**. O produto sabia
responder *"quais pedidos a Ana fez"* e não sabia responder *"quem se candidatou
a esta vaga"* nem *"a que vagas a Ana já se candidatou"* — que são as duas
perguntas de quem recruta.

## O resultado sai da máquina de estados, e não de um campo novo

Aprovado é `CONCLUIDA`; reprovado é `REJEITADA`; em análise é qualquer coisa
viva. Um campo `status_candidatura` ao lado seria a segunda fonte de verdade
sobre o mesmo fato, e a primeira a divergir — é a mesma regra de
`SolicitacaoServico.fase`.

## A busca é positiva E negativa

O §10 pede as duas. "Quem já se candidatou" é a fácil; **"quem NUNCA se
candidatou"** é a que ninguém constrói e é a que responde perguntas reais — quem
da equipe nunca se moveu, quem nunca foi considerado. Sem ela, a resposta vem de
alguém varrendo a lista à mão e concluindo pela ausência.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model

from identidade.services.autorizacao import pode
from workspace.models.catalogo import SituacaoServico, SolicitacaoServico

#: O domínio das duas coisas de vaga — inscrição e abertura. Prefixo e não valor
#: exato pela mesma razão do resto do produto: o domínio é hierárquico.
DOMINIO = "rh.vaga"

#: Ver a lista de candidaturas é ver dado de terceiros: quem se candidatou a
#: quê, e quem foi reprovado. É informação que muda a relação de uma pessoa com
#: o gestor dela, e por isso não é `rh.ler` — cuja forma `.proprio` está em
#: AUTOATENDIMENTO e abriria a lista para a empresa inteira (§48).
PERMISSAO = "rh.recrutar"


class RecrutamentoError(Exception):
    """A consulta não é sua."""


def pode_recrutar(pessoa, cache: dict | None = None) -> bool:
    return pode(pessoa, PERMISSAO, cache=cache)


def _resultado(solicitacao: SolicitacaoServico) -> str:
    """`aprovado`, `reprovado` ou `em_analise` — derivado do estado do pedido."""
    if solicitacao.situacao == SituacaoServico.CONCLUIDA:
        return "aprovado"
    if solicitacao.situacao in (SituacaoServico.REJEITADA, SituacaoServico.CANCELADA):
        return "reprovado"
    return "em_analise"


ROTULO_DO_RESULTADO = {
    "aprovado": "Aprovado",
    "reprovado": "Não seguiu",
    "em_analise": "Em análise",
}


def candidaturas(quem, vaga: str = "", pessoa=None, cache: dict | None = None):
    """As inscrições em vaga interna, mais recentes primeiro.

    `vaga` filtra pelo texto digitado no pedido; `pessoa` filtra por candidato.
    Os dois são opcionais e combinam — é o que permite responder tanto "quem se
    candidatou a esta vaga" quanto "a que vagas esta pessoa já se candidatou".
    """
    if not pode_recrutar(quem, cache=cache):
        raise RecrutamentoError("Esta tela é de quem cuida de recrutamento.")

    consulta = (
        SolicitacaoServico.objects.filter(item__chave="vaga-interna")
        .exclude(situacao__in=(SituacaoServico.RASCUNHO,))
        .select_related("item", "solicitante")
        .prefetch_related("anexos")
        .order_by("-criado_em")
    )
    if pessoa is not None:
        consulta = consulta.filter(solicitante=pessoa)

    linhas = [
        {
            "solicitacao": s,
            "candidato": s.solicitante,
            # A vaga é texto livre no formulário. Normalizado só na comparação:
            # gravar normalizado faria a tela mostrar "analista de suporte" onde
            # a pessoa escreveu "Analista de Suporte".
            "vaga": (s.dados or {}).get("vaga", ""),
            "motivo": (s.dados or {}).get("motivo", ""),
            "curriculos": [a for a in s.anexos.all() if a.campo == "curriculo"],
            "resultado": _resultado(s),
            "rotulo": ROTULO_DO_RESULTADO[_resultado(s)],
        }
        for s in consulta
    ]

    alvo = (vaga or "").strip().casefold()
    if alvo:
        linhas = [linha for linha in linhas if alvo in linha["vaga"].casefold()]
    return linhas


def nunca_se_candidataram(quem, cache: dict | None = None):
    """A busca NEGATIVA do §10 — quem nunca se inscreveu em vaga nenhuma.

    É a metade que ninguém constrói, e é a que responde pergunta real: quem da
    equipe nunca se moveu, quem nunca foi considerado para nada. Sem ela, a
    resposta vem de alguém varrendo a lista à mão e concluindo pela ausência —
    que é como se conclui errado.

    Só quem tem lotação: a lista é o organograma, e não a tabela de contas.
    """
    if not pode_recrutar(quem, cache=cache):
        raise RecrutamentoError("Esta tela é de quem cuida de recrutamento.")

    inscritos = set(
        SolicitacaoServico.objects.filter(item__chave="vaga-interna").values_list(
            "solicitante_id", flat=True
        )
    )
    return (
        get_user_model()
        .objects.filter(is_active=True, lotacao__isnull=False)
        .exclude(pk__in=inscritos)
        .select_related("lotacao__departamento", "lotacao__unidade")
        .order_by("nome", "email")
    )


def resumo(quem, cache: dict | None = None) -> dict:
    """Os números do topo: candidaturas, pessoas distintas, e o resultado."""
    linhas = candidaturas(quem, cache=cache)
    return {
        "total": len(linhas),
        "pessoas": len({linha["candidato"].pk for linha in linhas}),
        "aprovados": len([l for l in linhas if l["resultado"] == "aprovado"]),
        "em_analise": len([l for l in linhas if l["resultado"] == "em_analise"]),
    }
