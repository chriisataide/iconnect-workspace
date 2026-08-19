"""O vocabulário — o que o Workspace pergunta ao iConnect. §20, §21, §38, §52.

Cada função aqui é uma pergunta de negócio, não um endpoint. É o que permite a
tela dizer `ic.chamados_de(request)` sem saber que existe paginação DRF, que o
campo se chama `agente_nome` ou que o status vem em inglês.

## O que este módulo NÃO faz

**Não escreve.** Abrir chamado é no iConnect, que é onde ele é atendido — o §38
pede exatamente isso, e recriar a abertura aqui seria a duplicação que o §1
proíbe. O Workspace direciona, integra, exibe status e histórico.

## O status vem de lá, e o rótulo é nosso

O iConnect tem os seus valores; o §21 lista os cinco que a empresa usa. O
`de-para` mora aqui e em nenhum outro lugar: espalhado pelas telas, o dia em que
o iConnect acrescentar um status produziria três telas discordando sobre o que
ele significa.

Status desconhecido **não vira "erro"** — vira o próprio valor, capitalizado.
Inventar um rótulo para o que não se conhece é como uma tela passa a mentir
sobre o estado de um chamado.
"""

from __future__ import annotations

from workspace.integracoes import cliente, sessao

#: Os cinco estados que o §21 lista, na ordem do ciclo. O valor é o que o
#: iConnect devolve; o rótulo é o que a empresa fala.
ROTULO_DO_STATUS = {
    "aberto": "Aberto",
    "open": "Aberto",
    "em_andamento": "Em andamento",
    "in_progress": "Em andamento",
    "aguardando": "Aguardando solução",
    "pending": "Aguardando solução",
    "waiting": "Aguardando solução",
    "resolvido": "Resolvido",
    "resolved": "Resolvido",
    "encerrado": "Encerrado",
    "closed": "Encerrado",
    "fechado": "Encerrado",
}

#: Os que ainda pedem alguma coisa de alguém. Alimenta o contador do trilho.
ABERTOS = frozenset({"aberto", "open", "em_andamento", "in_progress",
                     "aguardando", "pending", "waiting"})


def rotulo_do_status(bruto: str) -> str:
    """O que a tela mostra. Desconhecido vira o próprio valor, capitalizado."""
    chave = (bruto or "").strip().lower()
    return ROTULO_DO_STATUS.get(chave) or (bruto or "—").replace("_", " ").capitalize()


def _pagina(resposta: dict) -> list[dict]:
    """A lista, venha ela paginada ou não.

    `StandardPagination` do DRF devolve `{results: [...]}`; alguns endpoints
    ad-hoc devolvem a lista crua. Tratar os dois aqui evita que cada chamador
    descubra a diferença do próprio jeito.
    """
    if isinstance(resposta, list):
        return resposta
    for chave in ("results", "items", "data", "points"):
        valor = resposta.get(chave)
        if isinstance(valor, list):
            return valor
    return []


def _com_token(request, caminho: str, **kwargs) -> dict:
    """Chama em nome da pessoa, renovando o token uma vez se ele expirou.

    Uma vez, e não em laço: se a renovação não resolveu, insistir só transforma
    uma sessão expirada numa espera. A tela pede para entrar de novo.
    """
    token = sessao.token_de(request)
    if not token:
        raise cliente.IntegracaoError(
            "Você ainda não está conectado ao iConnect nesta sessão."
        )
    try:
        return cliente.chamar(caminho, token=token, **kwargs)
    except cliente.IntegracaoError as erro:
        if "sessão" not in str(erro).lower() or not sessao.renovar(request):
            raise
        return cliente.chamar(caminho, token=sessao.token_de(request), **kwargs)


# ── Chamados — §21 e §38 ────────────────────────────────────────────


def chamados_de(request, limite: int = 20) -> list[dict]:
    """Os chamados desta pessoa, já normalizados para a tela.

    O RBAC é do outro lado: `TicketListCreateAPIView` filtra por papel — cliente
    vê os seus, analista vê os atribuídos. Refiltrar aqui criaria uma segunda
    regra de acesso sobre o mesmo dado, e a segunda é sempre a que esquece um
    caso.
    """
    resposta = _com_token(
        request, "/api/v1/tickets/", parametros={"ordering": "-atualizado_em"}
    )
    return [_chamado(bruto) for bruto in _pagina(resposta)[:limite]]


def _chamado(bruto: dict) -> dict:
    """Um ticket do iConnect no vocabulário do §21.

    Campos vindos de `TicketSerializer`. Os nomes ficam traduzidos aqui e não no
    template: template que conhece `agente_nome` é template que quebra quando o
    outro lado renomeia um campo.
    """
    status = (bruto.get("status") or "").strip().lower()
    return {
        "numero": bruto.get("id"),
        "assunto": bruto.get("titulo") or "—",
        "categoria": bruto.get("categoria") or "—",
        "status": status,
        "status_rotulo": rotulo_do_status(status),
        "aberto": status in ABERTOS,
        "prioridade": bruto.get("prioridade") or "",
        "responsavel": bruto.get("agente_nome") or "",
        "abertura": bruto.get("criado_em") or "",
        "atualizacao": bruto.get("atualizado_em") or "",
        "resolvido_em": bruto.get("resolvido_em") or "",
    }


def quantos_abertos(request) -> int:
    """O contador do trilho. Zero em qualquer falha — nunca uma exceção.

    Um contador de trilho que levanta derruba TODA tela do portal, porque o
    trilho está em todas. É o caso mais claro de degradar em silêncio: o número
    some, o resto continua.
    """
    try:
        return len([c for c in chamados_de(request) if c["aberto"]])
    except (cliente.IntegracaoError, cliente.IntegracaoIndisponivel):
        return 0


# ── Meu dia — §5 ────────────────────────────────────────────────────


def pendencias_de(request) -> list[dict]:
    """O que o iConnect diz que espera esta pessoa.

    `GET /api/v1/workspace/pending-items/` é a serialização do MESMO
    `PendingItemDTO` que os providers devolviam quando os dois produtos rodavam
    no mesmo processo. O contrato não mudou; o transporte mudou.
    """
    resposta = _com_token(request, "/api/v1/workspace/pending-items/")
    return _pagina(resposta)


# ── Campo e frota — §18 ─────────────────────────────────────────────


def posicoes_dos_tecnicos(request, so_ativos: bool = True) -> list[dict]:
    """Onde cada técnico está agora, do FSM do iConnect.

    O GPS vem do **app do técnico**, que já alimenta
    `POST /fsm/api/tracking/batch/`. O Workspace não coleta posição, não fala
    com o dispositivo e não guarda ponto: ele LÊ o que já existe.

    Isso não é economia de trabalho — é a regra do §1. Um segundo rastreamento
    produziria duas verdades sobre onde a mesma pessoa está, e a que diverge
    seria a que alguém usou para despachar.
    """
    resposta = _com_token(
        request,
        "/fsm/api/tracking/snapshot/",
        parametros={"ativo": "true"} if so_ativos else None,
    )
    return [_posicao(bruto) for bruto in _pagina(resposta)]


def _posicao(bruto: dict) -> dict:
    return {
        "tecnico": bruto.get("tecnico_nome") or bruto.get("nome") or "—",
        "tecnico_id": bruto.get("tecnico") or bruto.get("tecnico_id"),
        "latitude": bruto.get("lat") or bruto.get("latitude"),
        "longitude": bruto.get("lng") or bruto.get("longitude"),
        "quando": bruto.get("captured_at") or bruto.get("atualizado_em") or "",
        "velocidade": bruto.get("speed_kmh"),
        "em_movimento": bruto.get("is_moving"),
        "bateria": bruto.get("battery"),
    }


def ordens_do_dia(request) -> list[dict]:
    """As ordens de serviço em campo, com a sequência de rota que o FSM calculou.

    `sequencia_rota` já vem do `OrdemServicoListSerializer`: a **otimização de
    rota existe no iConnect** (`POST /fsm/api/tecnicos/<id>/otimizar-rota/`).
    Reimplementá-la aqui seria escrever um segundo otimizador que discorda do
    primeiro na ordem das paradas.
    """
    resposta = _com_token(request, "/fsm/api/ordens-servico/", parametros={"ordering": "sequencia_rota"})
    return [_ordem(bruto) for bruto in _pagina(resposta)]


def _ordem(bruto: dict) -> dict:
    return {
        "codigo": bruto.get("codigo") or bruto.get("id"),
        "titulo": bruto.get("titulo") or "—",
        "cliente": bruto.get("cliente_nome") or "",
        "tecnico": bruto.get("tecnico_nome") or "",
        "cidade": bruto.get("cidade") or "",
        "uf": bruto.get("uf") or "",
        "status": bruto.get("status_label") or rotulo_do_status(bruto.get("status", "")),
        "agendada": bruto.get("data_agendada") or "",
        "sequencia": bruto.get("sequencia_rota"),
        "duracao_min": bruto.get("duracao_estimada_min"),
        "sla_violado": bool(bruto.get("sla_violado")),
        "latitude": bruto.get("latitude"),
        "longitude": bruto.get("longitude"),
    }


def rotas_auditadas(request, limite: int = 20) -> list[dict]:
    """A quilometragem já auditada, do módulo KM Audit do iConnect.

    É a resposta ao "acompanhar KM" do §18 — e ela já existe lá, com auditoria,
    lançamento e aprovação financeira. O Workspace mostra; quem audita continua
    auditando no iConnect.
    """
    resposta = _com_token(request, "/api/v1/km-audit/rotas/")
    return [_rota(bruto) for bruto in _pagina(resposta)[:limite]]


def _rota(bruto: dict) -> dict:
    """Normaliza como todas as outras leituras — e não é preciosismo.

    O template chegou a ler o dicionário cru, com `|default:` encadeado por
    chave que às vezes não vem. Uma chave ausente numa expressão de filtro
    levanta `VariableDoesNotExist` e derruba a renderização inteira: a tela
    quebrava por causa de um campo opcional do outro lado.

    Normalizar aqui é a regra do produto — a view agrega, o template desenha —,
    e aqui ela é também o que impede o outro lado de quebrar esta tela ao
    renomear um campo.
    """
    return {
        "data": bruto.get("data") or bruto.get("dia") or "",
        "tecnico": bruto.get("tecnico_nome") or bruto.get("usuario") or "",
        "km": bruto.get("km_total") or bruto.get("km") or "",
        "situacao": bruto.get("status") or bruto.get("situacao") or "",
    }
