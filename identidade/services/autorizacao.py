"""A única porta de autorização do Workspace.

Nenhuma view checa permissão por conta própria. Tudo passa por `pode()`. É isso
que torna a matriz de permissões executável e testável em vez de aspiracional.

## Formato da permissão

    <dominio>.<acao>.<escopo>        rh.aprovar.equipe · cnt.publicar.departamento

O **papel** declara com escopo (`rh.ler.equipe`). Quem **chama** pergunta pela
ação, sem escopo (`pode(user, "rh.ler", alvo=outra_pessoa)`) — porque o chamador
não sabe, nem deve saber, por qual escopo o acesso será concedido. O serviço
resolve.

## Custo

Uma home chama isto ~40 vezes. O contrato é: no máximo 2 queries por
requisição, independentemente do número de chamadas, via cache em
`request.perm_cache`. O cache vive **só naquela requisição** — mudança de papel
vale na requisição seguinte, e nunca há permissão obsoleta em cache
compartilhado.
"""

from __future__ import annotations

from django.db import connection
from django.utils import timezone

from identidade.models import (
    ESCOPO_DEPARTAMENTO,
    ESCOPO_EQUIPE,
    ESCOPO_GLOBAL,
    ESCOPO_PROPRIO,
    ESCOPO_UNIDADE,
    AtribuicaoPapel,
    Delegacao,
    Lotacao,
    abrangencia,
)

PROFUNDIDADE_MAXIMA = 32


# ── Concessões ──────────────────────────────────────────────────────


def _concessoes_diretas(user) -> list[tuple[str, str, int | None, int | None]]:
    """`(permissao, escopo, unidade_id, departamento_id)` das atribuições vigentes."""
    atribuicoes = (
        AtribuicaoPapel.objects.vigentes()
        .filter(user=user, papel__ativo=True)
        .select_related("papel")
        .values_list("papel__permissoes", "escopo", "unidade_id", "departamento_id")
    )
    saida = []
    for permissoes, escopo, uni, dep in atribuicoes:
        for permissao in permissoes or []:
            saida.append((permissao, escopo, uni, dep))
    return saida


def _concessoes_delegadas(user) -> list[tuple[str, str, int | None, int | None]]:
    """O que chega por delegação vigente — sempre a interseção, nunca a soma.

    Só entra permissão que o **delegante** de fato possui hoje. Se ele perdeu o
    papel depois de delegar, o delegado perde junto.
    """
    delegacoes = (
        Delegacao.objects.vigentes()
        .filter(para_user=user)
        .prefetch_related("papeis")
    )

    saida = []
    for delegacao in delegacoes:
        chaves_permitidas = {p.chave for p in delegacao.papeis.all()}
        atribuicoes = (
            AtribuicaoPapel.objects.vigentes()
            .filter(user_id=delegacao.de_user_id, papel__ativo=True)
            .select_related("papel")
            .values_list("papel__chave", "papel__permissoes", "escopo", "unidade_id", "departamento_id")
        )
        for chave, permissoes, escopo, uni, dep in atribuicoes:
            # `papeis` vazio significa "todos os papéis vigentes do delegante".
            if chaves_permitidas and chave not in chaves_permitidas:
                continue
            for permissao in permissoes or []:
                saida.append((permissao, escopo, uni, dep))
    return saida


def _todas_concessoes(user) -> list[tuple[str, str, int | None, int | None]]:
    return _concessoes_diretas(user) + _concessoes_delegadas(user)


# ── Casamento de permissão ──────────────────────────────────────────


def _casa_permissao(concedida: str, pedida: str) -> str | None:
    """Devolve o escopo embutido na permissão concedida, se ela cobre a pedida.

    `concedida` vem do papel e pode ter escopo no fim (`rh.ler.equipe`) e/ou
    curinga (`rh.*`, `*`). `pedida` é a ação, sem escopo (`rh.ler`).

    Devolve `None` quando não cobre, ou o escopo (string vazia quando a
    concessão não declara escopo — aí vale o da atribuição).
    """
    if concedida == "*":
        return ESCOPO_GLOBAL

    partes = concedida.split(".")
    escopo_embutido = ""
    if partes and abrangencia(partes[-1]) >= 0:
        escopo_embutido = partes[-1]
        partes = partes[:-1]
    base = ".".join(partes)

    if base.endswith(".*"):
        prefixo = base[:-1]  # mantém o ponto final: "rh."
        return escopo_embutido or ESCOPO_GLOBAL if pedida.startswith(prefixo) else None

    if base == pedida or pedida.startswith(base + "."):
        return escopo_embutido
    return None


# ── Resolução de escopo ─────────────────────────────────────────────


def _user_id_do_alvo(alvo) -> int | None:
    """Extrai o id de User de um alvo, que pode vir em várias formas.

    Aceita User, Lotacao, qualquer objeto com `user_id`/`user`, e int. Views
    passam o que têm em mão; forçar o chamador a converter só produz conversão
    errada espalhada.
    """
    if alvo is None:
        return None
    if isinstance(alvo, int):
        return alvo
    for atributo in ("pk", "user_id"):
        if hasattr(alvo, atributo) and alvo.__class__.__name__ == "User":
            return alvo.pk
    if hasattr(alvo, "user_id"):
        return alvo.user_id
    if hasattr(alvo, "user"):
        return alvo.user.pk
    return getattr(alvo, "pk", None)


def _lotacao(user_id: int) -> Lotacao | None:
    return Lotacao.objects.filter(user_id=user_id).first()


def _escopo_alcanca(escopo, pessoa_id, alvo_id, unidade_id, departamento_id, cache) -> bool:
    """O escopo concedido cobre este alvo?"""
    if escopo == ESCOPO_GLOBAL:
        return True

    if alvo_id is None:
        # "posso fazer isso em geral?" — pergunta de tela de listagem.
        # Qualquer escopo responde sim; o recorte dos dados é da consulta.
        return True

    if escopo == ESCOPO_PROPRIO:
        return alvo_id == pessoa_id

    if escopo == ESCOPO_EQUIPE:
        return alvo_id == pessoa_id or alvo_id in liderados_recursivos(pessoa_id, cache=cache)

    if escopo == ESCOPO_UNIDADE:
        alvo = cache.setdefault("lotacoes", {}).setdefault(alvo_id, _lotacao(alvo_id))
        if alvo is None or alvo.unidade_id is None:
            return False
        # Atribuição sem unidade explícita vale para a unidade da própria pessoa.
        if unidade_id is None:
            propria = cache["lotacoes"].setdefault(pessoa_id, _lotacao(pessoa_id))
            return propria is not None and propria.unidade_id == alvo.unidade_id
        return alvo.unidade_id == unidade_id

    if escopo == ESCOPO_DEPARTAMENTO:
        alvo = cache.setdefault("lotacoes", {}).setdefault(alvo_id, _lotacao(alvo_id))
        if alvo is None or alvo.departamento_id is None:
            return False
        if departamento_id is None:
            propria = cache["lotacoes"].setdefault(pessoa_id, _lotacao(pessoa_id))
            return propria is not None and propria.departamento_id == alvo.departamento_id
        return alvo.departamento_id == departamento_id

    return False


# ── Organograma ─────────────────────────────────────────────────────


def liderados_recursivos(user_id: int, cache: dict | None = None) -> set[int]:
    """Liderados diretos e indiretos, numa CTE recursiva.

    Uma query, não uma por nível. Com organograma de 500 pessoas e 6 níveis, a
    versão ingênua faz 6 round-trips; esta faz 1.

    A CTE recursiva funciona em PostgreSQL e em SQLite (3.8.3+), então o teste
    roda nos dois. `UNION` (não `UNION ALL`) já corta ciclo pré-existente, e o
    teto de profundidade é a rede.
    """
    cache = cache if cache is not None else {}
    memo = cache.setdefault("liderados", {})
    if user_id in memo:
        return memo[user_id]

    sql = """
        WITH RECURSIVE equipe(user_id, nivel) AS (
            SELECT user_id, 1
              FROM identidade_lotacao
             WHERE gestor_id = %s
            UNION
            SELECT l.user_id, e.nivel + 1
              FROM identidade_lotacao l
              JOIN equipe e ON l.gestor_id = e.user_id
             WHERE e.nivel < %s
        )
        SELECT user_id FROM equipe
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [user_id, PROFUNDIDADE_MAXIMA])
        resultado = {linha[0] for linha in cursor.fetchall()}

    memo[user_id] = resultado
    return resultado


def cadeia_de_gestores(user_id: int) -> list[int]:
    """Do gestor direto até o topo. Usado por cadeia de aprovação."""
    cadeia: list[int] = []
    visto = {user_id}
    atual = user_id
    for _ in range(PROFUNDIDADE_MAXIMA):
        gestor = (
            Lotacao.objects.filter(user_id=atual).values_list("gestor_id", flat=True).first()
        )
        if gestor is None or gestor in visto:
            break
        cadeia.append(gestor)
        visto.add(gestor)
        atual = gestor
    return cadeia


# ── API pública ─────────────────────────────────────────────────────


def pode(pessoa, permissao: str, alvo=None, cache: dict | None = None) -> bool:
    """Esta pessoa pode executar `permissao` sobre `alvo`?

    `pessoa` — User (ou objeto com `.pk`). Anônimo nunca pode.
    `permissao` — a ação, sem escopo: `"rh.ler"`, `"apr.aprovar"`.
    `alvo` — sobre quem/o quê. `None` = "posso em geral?" (telas de listagem).
    `cache` — dicionário por requisição. Em view, use `request.perm_cache`.

    Superusuário passa direto: é a saída de emergência do Django e retirá-la
    quebraria o admin.
    """
    if pessoa is None:
        return False
    if getattr(pessoa, "is_authenticated", False) is False:
        return False
    if getattr(pessoa, "is_superuser", False):
        return True

    pessoa_id = getattr(pessoa, "pk", None)
    if pessoa_id is None:
        return False

    cache = cache if cache is not None else {}
    concessoes = cache.setdefault("concessoes", {})
    if pessoa_id not in concessoes:
        concessoes[pessoa_id] = _todas_concessoes(pessoa)

    alvo_id = _user_id_do_alvo(alvo)

    for concedida, escopo_atribuicao, unidade_id, departamento_id in concessoes[pessoa_id]:
        escopo_embutido = _casa_permissao(concedida, permissao)
        if escopo_embutido is None:
            continue
        # Escopo declarado na permissão vence o da atribuição — é mais
        # específico. Sem ele, vale o da atribuição.
        escopo = escopo_embutido or escopo_atribuicao
        if _escopo_alcanca(
            escopo, pessoa_id, alvo_id, unidade_id, departamento_id, cache
        ):
            return True
    return False


def escopo_de(pessoa, permissao: str, cache: dict | None = None) -> str | None:
    """O escopo mais amplo com que a pessoa tem esta permissão, ou None.

    Serve para a consulta se recortar sozinha: em vez de chamar `pode()` linha
    por linha (N+1 de autorização), a view pergunta o escopo uma vez e filtra o
    queryset de acordo.
    """
    if getattr(pessoa, "is_superuser", False):
        return ESCOPO_GLOBAL
    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        return None

    cache = cache if cache is not None else {}
    concessoes = cache.setdefault("concessoes", {})
    pessoa_id = getattr(pessoa, "pk", None)
    if pessoa_id is None:
        return None
    if pessoa_id not in concessoes:
        concessoes[pessoa_id] = _todas_concessoes(pessoa)

    melhor = None
    for concedida, escopo_atribuicao, _uni, _dep in concessoes[pessoa_id]:
        embutido = _casa_permissao(concedida, permissao)
        if embutido is None:
            continue
        escopo = embutido or escopo_atribuicao
        if melhor is None or abrangencia(escopo) > abrangencia(melhor):
            melhor = escopo
    return melhor


def subjects_de(pessoa, cache: dict | None = None) -> list[str]:
    """Sujeitos de ACL para *security trimming* no índice de busca.

    Devolve a lista que vai no `WHERE acl_subjects && %s`. É o que permite
    filtrar no índice em vez de pós-processar — filtrar depois de recuperar vaza
    contagem total, ordenação e, no pior caso, trecho de snippet.
    """
    subjects = ["*"]
    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        return subjects

    pessoa_id = getattr(pessoa, "pk", None)
    subjects.append(f"pessoa:{pessoa_id}")

    cache = cache if cache is not None else {}
    lotacao = cache.setdefault("lotacoes", {}).setdefault(pessoa_id, _lotacao(pessoa_id))
    if lotacao:
        if lotacao.unidade_id:
            subjects.append(f"unidade:{lotacao.unidade_id}")
        if lotacao.departamento_id:
            subjects.append(f"depto:{lotacao.departamento_id}")

    for chave in (
        AtribuicaoPapel.objects.vigentes()
        .filter(user_id=pessoa_id, papel__ativo=True)
        .values_list("papel__chave", flat=True)
        .distinct()
    ):
        subjects.append(f"papel:{chave}")

    return subjects


def situacao_de(user_id: int) -> str | None:
    """Situação da lotação — `ativo`, `ferias`, `afastado`, `desligado`."""
    return (
        Lotacao.objects.filter(user_id=user_id).values_list("situacao", flat=True).first()
    )


def hoje():
    """Ponto único de "agora" para o módulo. Facilita congelar em teste."""
    return timezone.localdate()
