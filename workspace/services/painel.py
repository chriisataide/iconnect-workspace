"""PNL — os contadores da pessoa, e os cards que a home mostra. §50 e §51.

## O que a auditoria encontrou

A home era a **única tela do produto sem o trilho**. Todos os contadores que o
Workspace já sabia calcular — pedidos esperando sua decisão, fila da sua área,
equipamento a confirmar, habilitação vencendo, documento de veículo estourado —
moravam no `_rail_servicos.html`, e o trilho não aparece na home.

O resultado: a tela em que a pessoa cai ao entrar era a que menos sabia sobre
ela. Havia exatamente um card condicional (aprovações) e o resto era navegação
fixa, igual para o estagiário e para o diretor.

## Contador é calculado UMA vez por requisição

Este módulo é a fonte única. `context.rail()` o consome para o trilho, e a home
o consome para os cards — e as duas leem o **mesmo** dicionário, memoizado na
requisição.

Sem isso, a home somaria oito consultas a cada carregamento para responder de
novo perguntas que o processador de contexto acabaria de responder. A ordem
importa: a view roda ANTES do processador de contexto (o `render()` do Django só
resolve os processadores na hora de montar o template), então quem chega
primeiro calcula e quem chega depois reaproveita.

## §51 — "perfil" aqui não é uma preferência, é o papel

A personalização não vem de uma tela de configuração onde a pessoa escolhe
widgets. Vem dos **papéis que ela tem**, que o produto já conhece.

A diferença é prática. Uma tela de preferências precisa ser descoberta, aberta e
mantida: quase ninguém a abre, e quem abre configura uma vez e nunca revisita —
então a home fica errada no dia em que a pessoa muda de área, e continua errada
até alguém lembrar. Derivada do papel, ela nasce certa e se corrige sozinha
quando o R.H. concede ou revoga.

## Nenhum card nasce vazio (ADR-012)

Card que aparece sempre e sempre zerado ensina a pessoa a ignorar a faixa
inteira — e depois a ignorar o card que finalmente tem algo. Só os cards de
NAVEGAÇÃO (`fixo=True`) aparecem sem número: eles respondem "onde eu vou", e
não "o que exige você".
"""

from __future__ import annotations

from dataclasses import dataclass

from django.http import HttpRequest
from django.urls import reverse

#: Quantos avisos o painel do sino traz. O painel tem rolagem própria
#: (`.au-sino-painel`), então o número é sobre RELEVÂNCIA e não sobre espaço: o
#: sino responde "o que aconteceu agora", e a lista inteira mora em
#: `/workspace/notificacoes/`.
LIMITE_DO_SINO = 5

#: Os contadores de quem não entrou. Tudo zero, e nenhum item pessoal aparece.
#:
#: O hub é aberto e `pessoa_da_requisicao()` devolve uma conta real para o
#: visitante anônimo — mas ela serve para calcular ALCANCE (quais tiles, quais
#: itens do catálogo), nunca para contar. Contando, o anônimo veria os números
#: de uma pessoa específica.
SEM_SESSAO = {
    "eu": None,
    "abertas": 0,
    "rascunhos": 0,
    "pendentes_aprovacao": 0,
    "nao_lidas": 0,
    "notificacoes_recentes": (),
    "na_fila": 0,
    "administra_papeis": False,
    "ve_aprovacoes": False,
    "ve_publicacoes": False,
    "ve_faq": False,
    "habilitacoes_pendentes": 0,
    "ve_indicadores": False,
    "ve_resultados": False,
    "ve_fontes": False,
    "ve_estoque": False,
    "custodias_a_aceitar": 0,
    "ve_frota": False,
    "prazos_de_veiculo": 0,
    "leituras_pendentes": 0,
    "ve_documentos": False,
    "documentos_a_vencer": 0,
    "ve_marketing": False,
    "prazos_de_marketing": 0,
    "ve_candidaturas": False,
    "chamados_abertos": 0,
}


def contadores(request: HttpRequest) -> dict:
    """Tudo o que o trilho e a home precisam saber sobre esta pessoa.

    Memoizado na requisição: chamado pela view da home e de novo pelo
    processador de contexto, e o segundo não pode custar as mesmas consultas.
    """
    guardado = getattr(request, "_painel_contadores", None)
    if guardado is not None:
        return guardado

    calculado = _calcular(request)
    request._painel_contadores = calculado
    return calculado


def _calcular(request: HttpRequest) -> dict:
    pessoa = getattr(request, "user", None)
    if pessoa is None or not getattr(pessoa, "is_authenticated", False):
        # Sai antes de tocar no banco. Além de não vazar, é o caminho mais
        # comum do hub aberto — e ele deixa de custar oito consultas.
        return dict(SEM_SESSAO)

    from identidade.services import administracao as adm
    from workspace.models.catalogo import SolicitacaoServico
    from workspace.services import aprovacao as apr
    from workspace.services import assistente as asst
    from workspace.services import atendimento as atd
    from workspace.services import conteudo as cnt
    from workspace.services import custodia as cst
    from workspace.services import estoque as est
    from workspace.services import frota as frt
    from workspace.integracoes import iconnect as ic
    from workspace.services import habilitacao as hab
    from workspace.services import indicadores as ind
    from workspace.services import listagem as lst
    from workspace.services import marketing as mkt
    from workspace.services import notificacoes as nt
    from workspace.services import recrutamento as rec
    from workspace.services import resultados as res
    from workspace.services import publicacao as pub

    if not hasattr(request, "perm_cache"):
        request.perm_cache = {}
    cache = request.perm_cache

    meus = SolicitacaoServico.objects.de(pessoa)
    ve_frota = frt.pode_ler(pessoa, cache=cache)
    ve_documentos = cnt.pode_publicar(pessoa, cache=cache)
    ve_marketing = mkt.pode_ler(pessoa, cache=cache)

    return {
        "eu": _quem_sou(pessoa),
        "abertas": meus.filter(situacao__in=lst.ABERTAS).count(),
        # §43 — o rascunho tem contador PRÓPRIO e não entra em `abertas`.
        # "Em aberto" quer dizer que o pedido está vivo na esteira; um
        # formulário que ninguém enviou não tem prazo correndo nem dono, e
        # somá-los faria um número significar duas coisas.
        "rascunhos": meus.rascunhos().count(),
        "pendentes_aprovacao": apr.pendentes_para(pessoa, cache=cache).count(),
        "nao_lidas": nt.quantas_nao_lidas(pessoa),
        # O painel do sino. Recorte curto e não a lista inteira: o sino responde
        # "o que aconteceu enquanto eu não estava", e a resposta cabe em cinco
        # linhas — o histórico completo é a tela de Notificações.
        "notificacoes_recentes": nt.para(pessoa, limite=LIMITE_DO_SINO),
        # `count()` numa consulta que já é filtrada por permissão: para quem
        # não atende nada dá 0, e o item do trilho nem aparece.
        "na_fila": atd.fila_de(pessoa, cache=cache).count(),
        "administra_papeis": adm.pode_administrar(pessoa, cache=cache),
        # SEPARADO de `pendentes_aprovacao`, e é a razão de existir da chave:
        # o trilho escondia Aprovações quando a conta era zero, então o item
        # sumia exatamente ao ser usado — a pessoa aprovava o último pedido e a
        # porta desaparecia. Quem PODE aprovar sempre vê a entrada; o número ao
        # lado é que varia, e "0" é informação, não motivo para esconder.
        "ve_aprovacoes": apr.tem_bandeja(pessoa, cache=cache),
        "ve_indicadores": ind.tem_painel(pessoa, cache=cache),
        # §Onda 3 — a tela de resultados e a tela irmã de fontes. Duas chaves e
        # não uma: ver a procedência NÃO dá acesso aos números, e quem opera a
        # carga não vê o resultado financeiro.
        "ve_resultados": res.tem_acesso(pessoa, cache=cache),
        "ve_fontes": res.pode_ver_fontes(pessoa, cache=cache),
        "ve_publicacoes": pub.pode_publicar(pessoa, cache=cache),
        "ve_faq": asst.pode_manter(pessoa, cache=cache),
        # Habilitação vencida bloqueia despacho — o contador é o que faz a
        # pessoa descobrir antes da portaria da obra.
        "habilitacoes_pendentes": len(hab.pendencias_de(pessoa)),
        "ve_estoque": est.pode_ler(pessoa, cache=cache),
        "custodias_a_aceitar": cst.a_aceitar(pessoa).count(),
        "ve_frota": ve_frota,
        # A conta varre os prazos de todos os veículos. Cobrá-la de cada
        # requisição de quem não pode nem abrir a tela seria pagar por um número
        # que ninguém lê.
        "prazos_de_veiculo": len(frt.com_prazo_estourando()) if ve_frota else 0,
        # §37 — leitura obrigatória que esta pessoa ainda deve. O número no
        # trilho é o que faz a confirmação acontecer sem depender de a pessoa
        # abrir o Meu dia por conta própria.
        "leituras_pendentes": len(cnt.pendentes_de_leitura(pessoa, cache=cache)),
        "ve_documentos": ve_documentos,
        # Só para quem mantém o acervo: a conta varre a vigência de todos os
        # documentos, e quem só lê não tem o que fazer com o número.
        "documentos_a_vencer": (
            cnt.vencidos().count() + cnt.a_vencer().count() if ve_documentos else 0
        ),
        "ve_marketing": ve_marketing,
        # §23 — só para quem cuida de marketing: a conta varre o prazo de
        # decisão de toda oportunidade aberta, e quem não decide nada não tem o
        # que fazer com o número.
        "prazos_de_marketing": (
            len(mkt.com_prazo_estourando()) if ve_marketing else 0
        ),
        # §10 — sem contador: candidatura não é pendência com prazo, e um número
        # sempre presente ao lado dela ensinaria a ignorar o trilho.
        "ve_candidaturas": rec.pode_recrutar(pessoa, cache=cache),
        # §21 — os chamados abertos desta pessoa no iConnect.
        #
        # `quantos_abertos()` NUNCA levanta: devolve zero em qualquer falha. O
        # trilho está em toda tela do portal, e um contador que estoura
        # derrubaria o produto inteiro por causa de um sistema que é de outro
        # deploy. Sem integração configurada, nem sai da memória.
        "chamados_abertos": ic.quantos_abertos(request),
    }


def _quem_sou(pessoa) -> dict:
    """Quem está logado, para a topbar e para a saudação da home."""
    from identidade.models import Lotacao

    lotacao = (
        Lotacao.objects.filter(user=pessoa)
        .select_related("departamento", "unidade")
        .first()
    )
    return {
        "nome": pessoa.get_short_name() or pessoa.get_full_name(),
        "nome_completo": pessoa.get_full_name(),
        "cargo": lotacao.cargo if lotacao else "",
        # A ÁREA, que é o que a pessoa reconhece como "onde eu trabalho". O
        # código do departamento fica de fora: "OPS" não diz nada para quem não
        # convive com a tabela.
        "area": lotacao.departamento.nome if lotacao and lotacao.departamento else "",
        "unidade": lotacao.unidade.nome if lotacao and lotacao.unidade else "",
    }


# ── Os cards da home — §50 ──────────────────────────────────────────


@dataclass(frozen=True)
class Card:
    """Uma porta na home. Deliberadamente pobre — a tela não decide nada."""

    chave: str
    titulo: str
    descricao: str
    icone: str
    destino: str
    contagem: int = 0
    #: Inação aqui trava OUTRA pessoa, ou trava a própria de trabalhar.
    urgente: bool = False
    #: Navegação: aparece mesmo sem número, porque responde "onde eu vou".
    fixo: bool = False


#: Os cards que dependem de um número, na ordem em que a inação custa caro.
#:
#: Uma tabela e não uma sequência de `if`: a ordem É a mensagem do §51, e
#: espalhada em condicionais ela vira acidente do último `if` acrescentado.
#: `(chave, contador, titulo, descricao, icone, rota, urgente)`
_COM_CONTAGEM = (
    (
        "aprovacoes", "pendentes_aprovacao",
        "Esperando sua decisão",
        "Enquanto você não decide, o pedido de outra pessoa não anda.",
        "check", "workspace:aprovacoes", True,
    ),
    (
        "fila", "na_fila",
        "Fila da sua área",
        "Pedidos aprovados esperando alguém executar.",
        "activity", "workspace:fila", True,
    ),
    (
        "habilitacoes", "habilitacoes_pendentes",
        "Habilitação vencendo",
        "Certificado vencido barra despacho — resolva antes da portaria da obra.",
        "book", "workspace:universidade", True,
    ),
    (
        "frota", "prazos_de_veiculo",
        "Documento de veículo",
        "Licenciamento, seguro ou IPVA vencido ou perto de vencer.",
        "truck", "workspace:frota", True,
    ),
    (
        "custodia", "custodias_a_aceitar",
        "Confirme o que recebeu",
        "Equipamento registrado no seu nome, esperando o seu aceite.",
        "cube", "workspace:custodia", False,
    ),
    (
        "rascunhos", "rascunhos",
        "Rascunhos guardados",
        "Formulários que você começou e ainda não enviou.",
        "file", "workspace:minhas_solicitacoes", False,
    ),
    (
        "marketing", "prazos_de_marketing",
        "Oportunidade com prazo",
        "Feira ou edital que precisa de resposta antes de a inscrição fechar.",
        "megafone", "workspace:marketing", True,
    ),
    (
        "leituras", "leituras_pendentes",
        "Leitura obrigatória",
        "Norma que a empresa exige que você leia e confirme.",
        "book", "workspace:documentacao", True,
    ),
    (
        "documentos", "documentos_a_vencer",
        "Documento vencendo",
        "Norma que você mantém e vai sair da vitrine.",
        "book", "workspace:documentos", False,
    ),
    (
        "notificacoes", "nao_lidas",
        "Avisos não lidos",
        "O que aconteceu enquanto você não estava.",
        "sino", "workspace:notificacoes", False,
    ),
)


def cards(contagens: dict, total_servicos: int = 0) -> list[Card]:
    """Os cards desta pessoa, do mais caro de ignorar ao mais barato.

    Função PURA — recebe os números já calculados e não toca no banco. É o que
    permite a home mostrar sete cards sem custar uma consulta a mais do que a
    home que mostrava três.

    A ORDEM é a personalização do §51. Primeiro o que trava outra pessoa, depois
    o que trava você, depois o que você só precisa saber, e por último a
    navegação. Ordenar por qualquer outro critério — alfabético, ordem de
    cadastro — faria "3 avisos não lidos" aparecer acima de "7 pedidos
    esperando sua decisão", que é a inversão exata do que importa.
    """
    achados = [
        Card(
            chave=chave,
            titulo=titulo,
            descricao=descricao,
            icone=icone,
            destino=_destino(chave, rota),
            contagem=contagens.get(contador, 0),
            urgente=urgente,
        )
        for chave, contador, titulo, descricao, icone, rota, urgente in _COM_CONTAGEM
        if contagens.get(contador, 0)
    ]
    # Urgentes primeiro; dentro de cada grupo, o maior número na frente. A
    # ordenação é estável, então empate mantém a ordem de `_COM_CONTAGEM` — que
    # é a ordem pensada, e não a ordem do acaso.
    achados.sort(key=lambda c: (not c.urgente, -c.contagem))

    return achados + _navegacao(contagens, total_servicos)


def _destino(chave: str, rota: str) -> str:
    url = reverse(rota)
    # O card de rascunho abre a aba de rascunhos, e não a lista inteira: mandar
    # para "Minhas solicitações" faria a pessoa procurar, numa lista de tudo, o
    # que o card acabou de dizer que existe.
    return f"{url}?situacao=rascunho" if chave == "rascunhos" else url


def _navegacao(contagens: dict, total_servicos: int) -> list[Card]:
    """As portas que aparecem sempre — e as que dependem só do papel.

    Estoque e frota entram aqui sem número: eles não são pendência, são a área
    de trabalho de quem tem o papel. Um contador de "quantos materiais existem"
    não pede ação nenhuma, e transformá-lo em selo vermelho seria alarme falso.
    """
    fixos = [
        Card(
            chave="meu_dia",
            titulo="Meu dia",
            descricao="Tudo o que exige você hoje, num lugar.",
            icone="spark",
            destino=reverse("workspace:meu_dia"),
            fixo=True,
        ),
        Card(
            chave="minhas",
            titulo="Minhas solicitações",
            descricao="O que você pediu, e em que fase cada pedido está.",
            icone="file",
            destino=reverse("workspace:minhas_solicitacoes"),
            contagem=contagens.get("abertas", 0),
            fixo=True,
        ),
        Card(
            chave="servicos",
            titulo="Pedir um serviço",
            descricao=(
                f"{total_servicos} serviços no catálogo — escolha pelo problema, "
                "não pelo departamento."
                if total_servicos
                else "Escolha pelo problema, não pelo departamento."
            ),
            icone="grid",
            destino=reverse("workspace:servicos"),
            fixo=True,
        ),
    ]

    if contagens.get("ve_estoque"):
        fixos.append(
            Card(
                chave="estoque",
                titulo="Estoque",
                descricao="Saldo por unidade, reversa e contagem de inventário.",
                icone="truck",
                destino=reverse("workspace:estoque"),
                fixo=True,
            )
        )
    if contagens.get("ve_frota") and not contagens.get("prazos_de_veiculo"):
        # Só quando NÃO há prazo estourando: com prazo, o card urgente lá em
        # cima já leva ao mesmo lugar, e dois cards para a mesma tela na mesma
        # faixa fazem a pessoa duvidar se são a mesma coisa.
        fixos.append(
            Card(
                chave="frota",
                titulo="Frota",
                descricao="Consumo, gasto e documentos de cada veículo.",
                icone="truck",
                destino=reverse("workspace:frota"),
                fixo=True,
            )
        )
    if contagens.get("ve_indicadores"):
        fixos.append(
            Card(
                chave="indicadores",
                titulo="Indicadores",
                descricao="Prazo, volume e taxa de reabertura por área.",
                icone="activity",
                destino=reverse("workspace:indicadores"),
                fixo=True,
            )
        )
    return fixos
