"""LST — filtrar e paginar as listas do produto.

## O que este módulo conserta

Nenhuma lista do Workspace paginava, e nenhuma filtrava. Isso funcionou o ano
inteiro porque o banco tinha dezenove pedidos. Medido:

    14 pedidos → 65 KB de HTML e 15 `<dialog>` na mesma página

O resumo em modal é montado no servidor, um por linha. O crescimento é linear e
não tem teto: com duzentos pedidos a página passa de novecentos KB e leva
duzentos modais que ninguém vai abrir. **Paginar conserta os dois de uma vez** —
vinte por página são vinte modais, e param de ser vinte e um no mês seguinte.

E sem filtro, achar "aquele reembolso de março" é rolar a tela. Numa lista que
só cresce, isso deixa de ser incômodo e vira impossível.

## Por que aqui, e não em cada view

Filtro é REGRA — o que "aberto" quer dizer, o que a busca procura. Espalhado
pelas views, cada tela responde uma coisa diferente para a mesma palavra, e é
assim que "aberto" passa a incluir cancelado numa tela e não na outra.

## O que este módulo NÃO faz

Não filtra por permissão. Quem pode ver o quê já foi decidido antes de a lista
chegar aqui — `svc.minhas()` devolve os pedidos de uma pessoa, `atd.fila_de()`
devolve as filas que ela atende. Refazer isso aqui criaria uma segunda fonte de
verdade sobre acesso, e a segunda é sempre a que esquece um caso.
"""

from __future__ import annotations

from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone

from workspace.models.catalogo import SituacaoServico

#: Quantas linhas por página. Vinte cabe numa tela sem rolar muito, e mantém a
#: página com vinte modais em vez de todos.
POR_PAGINA = 20

#: O que "em aberto" significa — em UM lugar. As telas contavam isso com uma
#: lista literal copiada em três arquivos.
ABERTAS = (
    SituacaoServico.AGUARDANDO_APROVACAO,
    SituacaoServico.APROVADA,
    SituacaoServico.EM_ATENDIMENTO,
    SituacaoServico.DEVOLVIDA,
)

#: Os filtros da tela "Minhas solicitações", na ordem em que aparecem.
#: `None` no valor significa "não filtra nada" — é o estado inicial.
FILTROS_MINHAS = (
    ("", "Todas", None),
    ("abertas", "Em aberto", ABERTAS),
    ("aguardando_aprovacao", "Aguardando aprovação", (SituacaoServico.AGUARDANDO_APROVACAO,)),
    ("devolvida", "Devolvidas", (SituacaoServico.DEVOLVIDA,)),
    ("concluida", "Concluídas", (SituacaoServico.CONCLUIDA,)),
    ("cancelada", "Canceladas", (SituacaoServico.CANCELADA,)),
)

_SITUACOES_DE = {chave: situacoes for chave, _, situacoes in FILTROS_MINHAS}


def filtrar_minhas(consulta, situacao: str = "", texto: str = ""):
    """Aplica o filtro de situação e a busca por texto.

    A busca olha o NOME DO SERVIÇO e o motivo da devolução. Não olha o conteúdo
    do formulário: ali moram atestado, dados bancários e motivo de afastamento,
    e uma busca que varre isso transforma a caixa de texto num vazador de dado
    sensível para quem espia a tela de alguém.
    """
    situacoes = _SITUACOES_DE.get(situacao)
    if situacoes:
        consulta = consulta.filter(situacao__in=situacoes)

    texto = (texto or "").strip()
    if texto:
        consulta = consulta.filter(
            Q(item__nome__icontains=texto) | Q(motivo_devolucao__icontains=texto)
        )
    return consulta


#: Os filtros da fila de atendimento.
FILTROS_FILA = (
    ("", "Tudo"),
    ("meus", "Assumidos por mim"),
    ("livres", "Sem dono"),
    ("atrasados", "Além do prazo"),
)


def filtrar_fila(fila, quem, filtro: str = ""):
    """Os três recortes que quem atende realmente usa.

    "Assumidos por mim" é o que começa o dia. "Sem dono" é o que ninguém pegou
    — e é onde a fila trava quando todo mundo acha que é do outro. "Além do
    prazo" é medido contra o prazo PROMETIDO de cada item, o mesmo número que a
    pessoa viu quando pediu: cobrar por outro seria mudar a régua depois do
    jogo.

    Recebe a LISTA já carregada, e não um queryset. A tela precisa dos KPIs da
    fila inteira e da lista filtrada ao mesmo tempo; com queryset, a view
    consultava o banco duas vezes para responder sobre o mesmo conjunto — a
    fila passou de 18 para 25 consultas quando o filtro foi acrescentado.
    Filtrar em memória custa nada: a fila é curta por natureza, e se um dia não
    for, é a fila que está doente, não a consulta.
    """
    if filtro == "meus":
        meu_id = getattr(quem, "pk", None)
        return [s for s in fila if s.atendente_id == meu_id]
    if filtro == "livres":
        return [s for s in fila if s.atendente_id is None]
    if filtro == "atrasados":
        agora = timezone.now()
        return [
            s for s in fila
            if (agora - s.criado_em).days > s.item.prazo_prometido_dias
        ]
    return list(fila)


# ── Paginação ───────────────────────────────────────────────────────


def paginar(consulta, numero, por_pagina: int = POR_PAGINA):
    """A página pedida, ou a primeira quando o número não faz sentido.

    Página inválida não é erro: quem chega com `?p=99` numa lista de duas
    páginas quase sempre veio de um link velho ou apagou um pedido. Devolver
    404 para isso é castigar a pessoa por uma URL que o próprio produto deu.
    """
    paginas = Paginator(consulta, por_pagina)
    try:
        return paginas.page(int(numero))
    except (TypeError, ValueError):
        return paginas.page(1)
    except Exception:  # EmptyPage, InvalidPage
        return paginas.page(paginas.num_pages)


def parametros_sem_pagina(request) -> str:
    """A querystring atual sem o `p`, para os links de página.

    Sem isto, clicar em "próxima" na página 2 de um filtro produziria
    `?situacao=abertas&p=2&p=3` — e o Django lê o primeiro `p`, então o botão
    de avançar não avançaria nunca.
    """
    parametros = request.GET.copy()
    parametros.pop("p", None)
    codificado = parametros.urlencode()
    return f"{codificado}&" if codificado else ""
