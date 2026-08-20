"""Catálogo de serviços — pedir, validar e rotear.

Três coisas aqui não são óbvias e são as que decidem se o catálogo é usado:

1. **Prazo real medido, não prometido.** Depois de 5 conclusões, o card mostra o
   P50 do histórico. Prazo prometido que ninguém cumpre destrói a confiança mais
   rápido que prazo longo e honesto.
2. **Auto-aprovação dentro da política.** Se cabe no limite e no orçamento, não
   vai para fila humana. A maioria dos portais manda 100% dos pedidos para
   aprovação manual, e é por isso que parecem lentos.
3. **Validação antes do envio.** Bloquear com o motivo à vista, em vez de aceitar
   e recusar dois dias depois — que é o que treina o usuário a voltar para o
   e-mail.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from statistics import median

from django.db import models, transaction
from django.utils import timezone

from identidade.models import Lotacao
from identidade.services.autorizacao import pode
from workspace.models.catalogo import (
    ItemCatalogo,
    SituacaoServico,
    SolicitacaoServico,
    TipoCampo,
)
from workspace.services import aprovacao as apr
from workspace.services import orcamento as orc

# Abaixo disto, a mediana de duração é ruído — 2 conclusões rápidas fariam a tela
# prometer 1 dia para sempre.
MINIMO_PARA_PRAZO_MEDIDO = 5


class SolicitacaoError(Exception):
    """Pedido inválido — campo faltando, sem permissão, item inativo."""


@dataclass(frozen=True)
class Impedimento:
    """Algo que bloqueia o envio, com o motivo em texto para a tela."""

    campo: str
    motivo: str


# ── Catálogo ────────────────────────────────────────────────────────


def catalogo_para(pessoa, cache: dict | None = None) -> list[ItemCatalogo]:
    """Itens que esta pessoa pode pedir, já filtrados por permissão.

    Filtrar aqui e não no template: item que aparece e recusa no envio é pior
    que item que não aparece.
    """
    itens = list(ItemCatalogo.objects.filter(ativo=True))
    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        # Catálogo é área pessoal: pedir exige saber quem pede.
        return []
    return [
        item
        for item in itens
        if not item.permissao or pode(pessoa, item.permissao, cache=cache)
    ]


def agrupado_para(pessoa, cache: dict | None = None) -> dict[str, list[ItemCatalogo]]:
    """Catálogo por grupo de intenção, na ordem de declaração de `GrupoCatalogo`.

    Ordem de declaração e NÃO alfabética: a alfabética põe "Desenvolvimento"
    primeiro e "Equipamento e acesso" em quarto, quando equipamento é o que a
    maioria vem pedir. A ordem do enum é a ordem de frequência de uso.
    """
    from workspace.models.catalogo import GrupoCatalogo

    por_grupo: dict[str, list[ItemCatalogo]] = {}
    for item in catalogo_para(pessoa, cache=cache):
        por_grupo.setdefault(item.grupo, []).append(item)

    agrupado: dict[str, list[ItemCatalogo]] = {}
    for grupo in GrupoCatalogo:
        itens = por_grupo.get(grupo.value)
        if itens:
            agrupado[grupo.label] = itens
    return agrupado


def q_dominios(prefixos, campo: str = "dominio") -> models.Q:
    """`Q` que casa qualquer um dos prefixos de domínio.

    Prefixo e não igualdade: o domínio é hierárquico (`rh.ferias`,
    `rh.ausencia`), e casar valor exato faria cada item novo nascer órfão do
    seu módulo.

    `campo` permite atravessar a FK (`item__dominio`) sem duplicar a função.
    """
    consulta = models.Q()
    for prefixo in prefixos:
        consulta |= models.Q(**{f"{campo}__startswith": prefixo})
    return consulta


def do_modulo(prefixos) -> list[ItemCatalogo]:
    """A vitrine de um módulo — os serviços que aquele departamento atende.

    SEM filtro de permissão, de propósito, e é a diferença para
    `catalogo_para()`: o Workspace é aberto a quem está na rede da empresa, e
    listar o que um departamento atende é informação, não ação. Quem pode de
    fato PEDIR continua sendo decidido por `catalogo_para()` — a tela marca os
    itens fora do alcance em vez de escondê-los, porque saber que o serviço
    existe é justamente o que faz a pessoa parar de mandar e-mail.

    ## Um campo `modulos_extras` existiu aqui por uma tarde

    Ele permitia um item aparecer em outro módulo sem mudar de domínio, e nasceu
    para atender "mover Reembolso para o R.H." sem pôr o R.H. na fila de pagar
    despesa. A dúvida era real; a resposta não era essa.

    A decisão de negócio foi que **o R.H. faz a tratativa mesmo** — confere o
    comprovante e libera o pagamento. Com isso `dominio` volta a decidir uma
    coisa só, e o campo virou esquema que ninguém usa. Esquema morto é pior que
    esquema nenhum: ele está lá quando alguém finalmente precisar, e estará
    errado, porque foi desenhado para um caso que não aconteceu.
    """
    if not prefixos:
        return []
    return list(ItemCatalogo.objects.filter(q_dominios(prefixos), ativo=True))


# Por quanto tempo para trás o prazo medido olha.
#
# Existe por dois motivos, e o segundo é o que importa mais. O primeiro é
# custo: sem janela, a consulta cresce para sempre e o catálogo passa a ler o
# histórico inteiro da empresa a cada carregamento. O segundo é VERDADE — o
# prazo é uma promessa sobre o que a empresa faz HOJE, e uma entrega de 2023
# não diz nada sobre a equipe de agora. Média de todo o histórico envelhece
# junto com a empresa e nunca melhora, por melhor que o setor fique.
JANELA_PRAZO_DIAS = 180


def prazos_medidos(itens) -> dict[int, tuple[int, bool]]:
    """`{item_id: (dias, e_medido)}` para a lista inteira, em UMA consulta.

    Nasceu de uma medição: a tela de catálogo fazia 42 consultas, e 28 delas
    eram `prazo_medido()` — uma por item. Cada uma lia TODAS as conclusões
    daquele item para tirar a mediana em Python. Com 19 pedidos no banco isso é
    invisível; com vinte mil, o catálogo lê vinte mil linhas vinte e seis vezes
    a cada abertura da tela mais visitada do produto.

    A mediana continua em Python de propósito: `percentile_cont` existe no
    PostgreSQL e não no SQLite, e o projeto roda nos dois — uma consulta que só
    funciona em produção é uma consulta que ninguém testa.
    """
    itens = list(itens)
    if not itens:
        return {}

    corte = timezone.now() - timedelta(days=JANELA_PRAZO_DIAS)
    duracoes: dict[int, list[int]] = defaultdict(list)
    linhas = SolicitacaoServico.objects.filter(
        item_id__in=[i.pk for i in itens],
        situacao=SituacaoServico.CONCLUIDA,
        concluido_em__isnull=False,
        concluido_em__gte=corte,
    ).values_list("item_id", "criado_em", "concluido_em")

    for item_id, criado_em, concluido_em in linhas:
        duracoes[item_id].append((concluido_em - criado_em).days)

    resposta = {}
    for item in itens:
        medidas = duracoes.get(item.pk, [])
        if len(medidas) < MINIMO_PARA_PRAZO_MEDIDO:
            resposta[item.pk] = (item.prazo_prometido_dias, False)
        else:
            resposta[item.pk] = (int(median(medidas)), True)
    return resposta


def prazo_medido(item: ItemCatalogo) -> tuple[int, bool]:
    """`(dias, e_medido)` de UM item. Cai no prometido sem histórico bastante.

    Continua existindo para a tela de um item só e para o admin. Numa LISTA,
    use `prazos_medidos()` — chamar esta aqui em laço é exatamente o defeito
    que aquela função existe para não ter.
    """
    return prazos_medidos([item])[item.pk]


# ── Validação antes do envio ────────────────────────────────────────


def _centro_custo_de(pessoa) -> str:
    """Vem da identidade. O usuário não digita centro de custo."""
    return (
        Lotacao.objects.filter(user=pessoa)
        .values_list("centro_custo_codigo", flat=True)
        .first()
        or ""
    )


def verificar(
    item: ItemCatalogo,
    pessoa,
    dados: dict | None = None,
    valor: Decimal | None = None,
    cache: dict | None = None,
    arquivos: dict | None = None,
    linhas=None,
    rascunho: SolicitacaoServico | None = None,
) -> list[Impedimento]:
    """O que impede este pedido de ser enviado. Vazio = pode enviar.

    Chamado pela tela a cada mudança (HTMX) para bloquear com o motivo à vista,
    e de novo dentro de `solicitar()` — a tela não é a fonte de verdade.

    `rascunho` é o pedido guardado que está sendo enviado — §43. Sem ele, o
    comprovante anexado ONTEM não conta: a validação olha só o que veio neste
    POST, e quem retomasse o rascunho seria mandado anexar de novo um arquivo
    que já está no pedido. Um formulário que esquece o que ele mesmo guardou é
    pior que não ter rascunho nenhum.
    """
    from workspace.services import anexos as anx
    from workspace.services import formulario as frm
    from workspace.services import reembolso as rmb

    impedimentos: list[Impedimento] = []
    # Fora do ramo escolhido, o que foi digitado não conta — nem para exigir,
    # nem para gravar. Sem JS a tela mostra os dois ramos, e quem preencheu os
    # dois antes de decidir não pode acabar com um pedido que se contradiz.
    dados = frm.limpar_fora_do_ramo(item, dados or {})

    # Item que pede as compras uma a uma não tem valor digitado: o total é a
    # soma das linhas. Calcular aqui, e não confiar no que a tela mandou, é o
    # que impede o total de divergir dos comprovantes.
    if rmb.tem_despesas(item):
        for motivo in rmb.verificar_linhas(linhas or []):
            impedimentos.append(Impedimento("despesas", motivo))
        valor = rmb.total(linhas or [])
    # Campos de arquivo se satisfazem com arquivo, não com texto. Antes desta
    # distinção, `dados["comprovantes"] = "cupom.jpg"` passava a validação — o
    # usuário digitava o nome do arquivo e o pedido seguia sem comprovante.
    de_arquivo = {c["chave"] for c in item.campos if c.get("tipo") == TipoCampo.ARQUIVO}
    anexados = anx.campos_com_arquivo(arquivos)
    if rascunho is not None and rascunho.pk:
        anexados |= set(rascunho.anexos.values_list("campo", flat=True))

    if not item.ativo:
        impedimentos.append(Impedimento("item", "Este serviço não está disponível."))

    if item.permissao and not pode(pessoa, item.permissao, cache=cache):
        impedimentos.append(Impedimento("item", "Você não tem acesso a este serviço."))

    # Despesas e adiantamento não são caixas de digitar, e a checagem genérica
    # de "campo obrigatório vazio" não os alcança: quem valida a lista de
    # compras é `verificar_linhas()`, logo acima.
    de_secao = {
        c["chave"]
        for c in item.campos
        if c.get("tipo") in (TipoCampo.DESPESAS, TipoCampo.ADIANTAMENTO)
    }

    # Só os campos do ramo escolhido: exigir "qual a instituição" de quem
    # escolheu curso interno é pedir para inventar uma resposta.
    for campo in frm.campos_ativos(item, dados):
        chave = campo["chave"]
        rotulo = campo.get("rotulo", chave)

        if frm.escolha_invalida(campo, dados.get(chave)):
            # A lista fechada é fechada dos dois lados: o `<select>` guia, e
            # aqui é onde um valor forjado no POST para de valer.
            impedimentos.append(Impedimento(chave, f"Escolha uma opção de {rotulo.lower()}."))
            continue

        if not campo.get("obrigatorio") or chave in de_secao:
            continue

        if chave in de_arquivo:
            if chave not in anexados:
                impedimentos.append(Impedimento(chave, f"Anexe {rotulo.lower()}."))
            continue
        valor_campo = dados.get(chave)
        if valor_campo is None or (isinstance(valor_campo, str) and not valor_campo.strip()):
            impedimentos.append(Impedimento(chave, f"{rotulo} é obrigatório."))

    for recusa in anx.verificar_lote(arquivos):
        impedimentos.append(Impedimento("anexos", f"{recusa.nome}: {recusa.motivo}"))

    if frm.valor_e_exigido(item, dados) and (valor is None or valor <= 0):
        impedimentos.append(Impedimento("valor", "Informe o valor."))

    impedimentos.extend(_impedimentos_de_estoque(item, pessoa, dados))

    if item.exige_centro_custo and not _centro_custo_de(pessoa):
        impedimentos.append(
            Impedimento(
                "centro_custo",
                "Você não tem centro de custo na sua lotação. Peça ao RH para cadastrar.",
            )
        )

    return impedimentos


#: O campo que liga um item de catálogo ao cadastro de materiais. Item sem ele
#: não tem nada a ver com estoque, e a checagem inteira é pulada.
CAMPO_MATERIAL = "material"
CAMPO_QUANTIDADE = "quantidade"


def _impedimentos_de_estoque(item: ItemCatalogo, pessoa, dados: dict) -> list[Impedimento]:
    """§16 — não deixa pedir mais do que existe na unidade da pessoa.

    A checagem é aqui, ANTES do envio, e não na hora de atender. Deixar o pedido
    entrar e recusá-lo três dias depois na fila é o pior dos dois mundos: a
    pessoa esperou, Suprimentos gastou o atendimento, e a informação que faltava
    (o saldo) estava disponível no primeiro segundo.

    Não RESERVA nada — só confere. Reservar no envio criaria saldo preso por
    pedido que ninguém aprovou, e o material some do estoque de quem precisa
    hoje por causa de um pedido de daqui a duas semanas. A baixa acontece na
    entrega, e é lá que a corrida por concorrência é resolvida.
    """
    chaves = {c["chave"] for c in item.campos}
    if CAMPO_MATERIAL not in chaves or CAMPO_QUANTIDADE not in chaves:
        return []

    from workspace.models.estoque import Material
    from workspace.services import estoque as est

    codigo = (dados.get(CAMPO_MATERIAL) or "").strip()
    bruta = (dados.get(CAMPO_QUANTIDADE) or "").strip() if isinstance(
        dados.get(CAMPO_QUANTIDADE), str
    ) else dados.get(CAMPO_QUANTIDADE)
    if not codigo or bruta in (None, ""):
        # Campo vazio já é tratado pela regra de obrigatório logo acima. Repetir
        # a queixa aqui daria dois erros para o mesmo campo em branco.
        return []

    try:
        quantidade = int(bruta)
    except (TypeError, ValueError):
        return [Impedimento(CAMPO_QUANTIDADE, "A quantidade tem de ser um número.")]
    if quantidade <= 0:
        return [Impedimento(CAMPO_QUANTIDADE, "A quantidade tem de ser maior que zero.")]

    material = Material.objects.filter(codigo=codigo, ativo=True).first()
    if material is None:
        return [Impedimento(CAMPO_MATERIAL, "Este material não está no cadastro.")]

    unidade = _unidade_de(pessoa)
    if unidade is None:
        return [
            Impedimento(
                CAMPO_MATERIAL,
                "Você não tem unidade na sua lotação, e o estoque é por unidade. "
                "Peça ao RH para cadastrar.",
            )
        ]

    saldo = est.saldo_de(material, unidade)
    if quantidade > saldo:
        medida = material.get_unidade_medida_display().lower()
        return [
            Impedimento(
                CAMPO_QUANTIDADE,
                f"Há {saldo} {medida} de {material.nome} em {unidade.nome}. "
                f"Você pediu {quantidade}.",
            )
        ]
    return []


def campos_do_item(item: ItemCatalogo, pessoa) -> list[dict]:
    """Os campos do item com as listas DINÂMICAS já preenchidas.

    Existe porque `ItemCatalogo.campos` é estático e o estoque não é. Gravar a
    lista de materiais no item obrigaria uma migração de dados a cada material
    novo — e a lista estaria errada entre uma e outra, que é o pior estado
    possível: um `<select>` que oferece o que não existe.

    O rótulo traz o saldo junto ("Capacete G — 12 disponíveis") porque a
    pergunta seguinte a "qual material" é sempre "tem quanto?", e respondê-la no
    próprio option economiza a ida à tela de estoque.
    """
    if not any(c.get("dinamico") for c in item.campos):
        return list(item.campos)

    return [
        {**campo, "opcoes": _opcoes_de_estoque(pessoa)}
        if campo.get("chave") == CAMPO_MATERIAL and campo.get("dinamico")
        else campo
        for campo in item.campos
    ]


def _opcoes_de_estoque(pessoa) -> list[dict]:
    """O que existe na unidade da pessoa, com saldo maior que zero.

    Zerado fica FORA da lista. Mostrá-lo desabilitado ensinaria que o material
    existe no cadastro, o que não ajuda quem precisa dele hoje — e mostrá-lo
    habilitado produziria um pedido recusado no envio.
    """
    from workspace.services import estoque as est

    unidade = _unidade_de(pessoa)
    if unidade is None:
        return []

    return [
        {
            "valor": linha.material.codigo,
            "rotulo": (
                f"{linha.material.nome} — {linha.quantidade} "
                f"{linha.material.get_unidade_medida_display().lower()}"
            ),
        }
        for linha in est.disponivel_para(pessoa, unidade=unidade)
        if linha.quantidade > 0
    ]


def _unidade_de(pessoa):
    """Delegado a `estoque.unidade_de`. A conta é a mesma e o dono é o estoque.

    Estava duplicada aqui: o saldo é POR UNIDADE, e a pergunta "de qual
    prateleira" aparece na requisição, na custódia e na tela de estoque. Três
    cópias divergem na primeira vez que a lotação ganhar regra.
    """
    from workspace.services import estoque as est

    return est.unidade_de(pessoa)


def _cabe_no_orcamento(centro_custo: str, valor: Decimal | None) -> bool:
    if not centro_custo or valor is None:
        return True
    return orc.resumo(centro_custo).cabe(valor)


def pode_auto_aprovar(
    item: ItemCatalogo, valor: Decimal | None, centro_custo: str
) -> bool:
    """Dentro do limite E dentro do orçamento não vai para fila humana."""
    if item.limite_auto_aprovacao is None:
        return False
    if valor is None:
        return True
    if valor > item.limite_auto_aprovacao:
        return False
    return _cabe_no_orcamento(centro_custo, valor)


# ── Pedir ───────────────────────────────────────────────────────────


@transaction.atomic
def solicitar(
    item: ItemCatalogo,
    pessoa,
    dados: dict | None = None,
    valor: Decimal | None = None,
    cache: dict | None = None,
    arquivos: dict | None = None,
    linhas=None,
    adiantamento: SolicitacaoServico | None = None,
    rascunho: SolicitacaoServico | None = None,
) -> SolicitacaoServico:
    """Cria o pedido e o roteia — auto-aprovado ou para a cadeia de aprovação.

    Com `rascunho`, a MESMA linha é promovida em vez de uma nova ser criada —
    §43. Criar outra deixaria o rascunho para trás com os anexos dentro dele, e
    a pessoa teria dois registros do mesmo pedido: um enviado e sem
    comprovante, outro com o comprovante e nunca enviado.
    """
    from workspace.services import anexos as anx
    from workspace.services import formulario as frm
    from workspace.services import reembolso as rmb

    dados = frm.limpar_fora_do_ramo(item, dados or {})
    if item.exige_valor and not frm.valor_e_exigido(item, dados):
        # O ramo escolhido não tem valor — curso interno da empresa. Guardar o
        # que sobrou de um ramo abandonado faria o pedido comprometer orçamento
        # por um número que a tela nem mostrava.
        valor = None

    if rascunho is not None:
        _garantir_rascunho_de(rascunho, pessoa)

    impedimentos = verificar(
        item, pessoa, dados, valor, cache=cache, arquivos=arquivos, linhas=linhas,
        rascunho=rascunho,
    )
    if impedimentos:
        raise SolicitacaoError("; ".join(i.motivo for i in impedimentos))

    # O total do pedido item a item é a soma das compras, e é ele que segue
    # para o limite de auto-aprovação, para o orçamento e para a bandeja — o
    # que a tela mandou no campo `valor` não entra na conta.
    if rmb.tem_despesas(item):
        valor = rmb.total(linhas or [])

    centro_custo = _centro_custo_de(pessoa) if item.exige_centro_custo else ""
    auto = pode_auto_aprovar(item, valor, centro_custo)

    situacao = (
        SituacaoServico.APROVADA if auto else SituacaoServico.AGUARDANDO_APROVACAO
    )
    if rascunho is not None:
        solicitacao = rascunho
        solicitacao.item = item
        solicitacao.dados = dados or {}
        solicitacao.valor = valor
        solicitacao.centro_custo_codigo = centro_custo
        solicitacao.auto_aprovada = auto
        solicitacao.adiantamento = adiantamento
        solicitacao.situacao = situacao
        # `criado_em` é `auto_now_add` e NÃO é mexido: o pedido nasce agora para
        # efeito de prazo — o relógio do SLA começa no envio, não no dia em que
        # a pessoa abriu o formulário. Como `auto_now_add` só grava na inserção,
        # a data continuaria a do rascunho e o pedido nasceria já atrasado.
        solicitacao.criado_em = timezone.now()
        solicitacao.save()
    else:
        solicitacao = SolicitacaoServico.objects.create(
            item=item,
            solicitante=pessoa,
            dados=dados or {},
            valor=valor,
            centro_custo_codigo=centro_custo,
            auto_aprovada=auto,
            adiantamento=adiantamento,
            situacao=situacao,
        )

    # Antes de rotear: se o arquivo não gravar, a transação inteira volta e o
    # pedido não existe. Aprovador recebendo reembolso sem comprovante porque o
    # disco encheu é pior que o pedido não ter sido criado.
    anx.guardar(solicitacao, arquivos, pessoa)
    if linhas:
        rmb.gravar_linhas(solicitacao, linhas, pessoa)

    from workspace.services import historico as hst

    hst.registrar(solicitacao, hst.Acao.CRIADA, quem=pessoa)
    if auto:
        # Sem `quem`: ninguém decidiu — o pedido coube na política. Inventar um
        # autor aqui faria o histórico mentir sobre quem assinou.
        hst.registrar(
            solicitacao,
            hst.Acao.AUTO_APROVADA,
            observacao="Dentro do limite e do orçamento.",
        )

    if auto:
        # Automático não pode significar invisível: o compromisso é escriturado
        # do mesmo jeito, e o histórico registra que ninguém precisou decidir.
        if valor and centro_custo:
            from workspace.models.orcamento import Compromisso, competencia_de

            Compromisso.objects.create(
                dominio=item.dominio,
                origem_id=str(solicitacao.pk),
                descricao=item.nome[:200],
                centro_custo_codigo=centro_custo,
                valor=valor,
                competencia=competencia_de(),
                criado_por=pessoa,
            )
        # Auto-aprovado já NASCE na fila da área. Avisar aqui é o que impede o
        # caso mais silencioso do produto: o pedido que nunca passou por bandeja
        # nenhuma e por isso não gerou aviso para ninguém além de quem pediu.
        from workspace.services import atendimento as atd

        atd.avisar_a_fila(solicitacao, cache=cache)
        return solicitacao

    aprovacao = apr.criar(
        dominio=item.dominio,
        titulo=item.nome,
        solicitante=pessoa,
        origem_id=str(solicitacao.pk),
        resumo=item.descricao_curta,
        valor=valor,
        centro_custo_codigo=centro_custo,
        dados={"item": item.chave, "campos": dados or {}},
    )
    solicitacao.aprovacao = aprovacao
    solicitacao.save(update_fields=["aprovacao"])
    return solicitacao


# ── Rascunho — §43 ──────────────────────────────────────────────────


@transaction.atomic
def salvar_rascunho(
    item: ItemCatalogo,
    pessoa,
    dados: dict | None = None,
    valor: Decimal | None = None,
    arquivos: dict | None = None,
    rascunho: SolicitacaoServico | None = None,
) -> SolicitacaoServico:
    """Guarda o que já foi digitado. **Não valida nada** — esse é o ponto.

    O formulário longo era tudo-ou-nada: quem não tinha o comprovante à mão
    perdia o que já tinha escrito ao sair da tela. Validar o rascunho recriaria
    exatamente o problema, porque o rascunho é, por definição, o formulário
    ainda incompleto.

    O que ele NÃO faz, e cada omissão é deliberada: não cria aprovação, não
    escritura compromisso de orçamento, não avisa fila nenhuma e não começa
    prazo. Um rascunho é texto da pessoa, e mais nada.

    **Anexo é validado mesmo aqui.** Arquivo corrompido ou com magic byte errado
    não entra em disco nem como rascunho — a validação existe contra o conteúdo,
    e o conteúdo não fica menos perigoso por o formulário estar pela metade.
    """
    from workspace.services import anexos as anx
    from workspace.services import formulario as frm

    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        raise SolicitacaoError("Só quem está identificado pode guardar rascunho.")

    dados = frm.limpar_fora_do_ramo(item, dados or {})

    if rascunho is None:
        solicitacao = SolicitacaoServico.objects.create(
            item=item,
            solicitante=pessoa,
            dados=dados,
            valor=valor,
            situacao=SituacaoServico.RASCUNHO,
        )
        from workspace.services import historico as hst

        hst.registrar(solicitacao, hst.Acao.RASCUNHO_GUARDADO, quem=pessoa)
    else:
        _garantir_rascunho_de(rascunho, pessoa)
        solicitacao = rascunho
        solicitacao.item = item
        solicitacao.dados = dados
        solicitacao.valor = valor
        solicitacao.save(update_fields=["item", "dados", "valor"])

    anx.guardar(solicitacao, arquivos, pessoa)
    return solicitacao


def _garantir_rascunho_de(rascunho: SolicitacaoServico, pessoa) -> None:
    """Rascunho é da pessoa que o escreveu, e de mais ninguém.

    Checado por pk e não por `is`: a view recebe um número da URL, e sem esta
    conferência qualquer pessoa logada continuaria o rascunho de qualquer outra
    trocando um dígito — inclusive lendo o que ela digitou.
    """
    if rascunho.solicitante_id != getattr(pessoa, "pk", None):
        raise SolicitacaoError("Este rascunho não é seu.")
    if rascunho.situacao != SituacaoServico.RASCUNHO:
        raise SolicitacaoError("Esta solicitação já foi enviada.")


def rascunho_de(pessoa, pk) -> SolicitacaoServico | None:
    """O rascunho da pessoa, ou `None`. Nunca o de outra."""
    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        return None
    try:
        pk = int(pk)
    except (TypeError, ValueError):
        return None
    return (
        SolicitacaoServico.objects.de(pessoa)
        .rascunhos()
        .select_related("item")
        .filter(pk=pk)
        .first()
    )


@transaction.atomic
def descartar_rascunho(rascunho: SolicitacaoServico, quem) -> None:
    """Apaga de verdade. É a única exclusão do produto, e ela se justifica.

    A regra da casa é nunca apagar: pedido cancelado vira `CANCELADA` e fica,
    porque alguém pediu, alguém foi avisado, e os indicadores do período
    precisam continuar certos.

    Nada disso vale para um rascunho. Ele nunca foi enviado, ninguém foi
    notificado, nenhuma aprovação existiu, nenhum orçamento foi comprometido e
    nenhum prazo correu. Guardá-lo como "cancelada" faria a aba de cancelados —
    e a taxa de cancelamento do painel — contar pedidos que nunca foram feitos.

    Os anexos vão junto por `CASCADE`, que é o certo: eram arquivos de um
    formulário que deixou de existir.
    """
    _garantir_rascunho_de(rascunho, quem)
    rascunho.delete()


def minhas(pessoa):
    """As solicitações da pessoa, abertas primeiro."""
    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        return SolicitacaoServico.objects.none()
    return (
        SolicitacaoServico.objects.de(pessoa)
        .select_related("item", "aprovacao")
        # `prefetch` e não N+1: a tela lista os anexos de cada linha, e sem isto
        # uma pessoa com 30 pedidos faria 31 consultas só para os arquivos.
        #
        # As ETAPAS entram pelo mesmo motivo: a fase de um pedido aguardando
        # aprovação diz de quem é a vez, e `etapa_atual` consulta o banco
        # quando não encontra o prefetch — uma consulta por linha, na segunda
        # tela mais aberta do produto.
        .prefetch_related(
            "anexos",
            # As DESPESAS eram um N+1 puro e antigo: o modal de cada linha lista
            # a compra item a item, e sem o prefetch são dezesseis consultas
            # para dezesseis pedidos — na segunda tela mais aberta do produto,
            # crescendo com o histórico de cada pessoa. `despesa__anexo` junto
            # porque a lista mostra o comprovante de cada valor.
            "despesas__anexo",
            "eventos",
            # As ETAPAS: a fase de um pedido aguardando aprovação diz de quem é
            # a vez, e `etapa_atual` consulta o banco quando não encontra o
            # prefetch — de novo uma consulta por linha.
            "aprovacao__etapas__aprovador",
            "aprovacao__etapas__papel",
        )
        .order_by("-criado_em")
    )


def minhas_do_modulo(pessoa, prefixos):
    """Os pedidos da pessoa dentro da fatia de um módulo, abertos primeiro."""
    if not prefixos:
        return SolicitacaoServico.objects.none()
    return minhas(pessoa).filter(q_dominios(prefixos, campo="item__dominio"))


@transaction.atomic
def cancelar(solicitacao: SolicitacaoServico, quem) -> SolicitacaoServico:
    """Só o solicitante cancela o próprio pedido."""
    if solicitacao.solicitante_id != getattr(quem, "pk", None):
        raise SolicitacaoError("Só quem pediu pode cancelar.")
    if not solicitacao.em_aberto:
        raise SolicitacaoError(
            f"Solicitação já está {solicitacao.get_situacao_display().lower()}."
        )

    solicitacao.situacao = SituacaoServico.CANCELADA
    solicitacao.save(update_fields=["situacao"])

    from workspace.services import historico as hst

    hst.registrar(solicitacao, hst.Acao.CANCELADA, quem=quem)

    if solicitacao.aprovacao_id:
        try:
            apr.decidir(solicitacao.aprovacao, quem, apr.Decisao.CANCELAR)
        except apr.AprovacaoError:
            # A aprovação já foi decidida — o cancelamento do serviço vale, e o
            # orçamento é liberado abaixo de qualquer jeito.
            pass
        orc.cancelar(solicitacao.aprovacao)

    return solicitacao


# ── Reação à decisão de aprovação ───────────────────────────────────


def ao_decidir(sender, solicitacao, decisao, quem, **kwargs) -> None:
    """Ouvinte de `aprovacao_decidida` — reflete a decisão no pedido de serviço.

    O catálogo não é chamado pelo APR; ele ouve. Assim APR continua sem saber
    que catálogo existe.
    """
    servico = SolicitacaoServico.objects.filter(aprovacao=solicitacao).first()
    if servico is None:
        return

    from workspace.services import historico as hst

    if decisao == apr.Decisao.APROVAR:
        servico.situacao = SituacaoServico.APROVADA
        acao, observacao = hst.Acao.APROVADA, ""
    elif decisao == apr.Decisao.DEVOLVER:
        servico.situacao = SituacaoServico.DEVOLVIDA
        servico.motivo_devolucao = _ultima_justificativa(solicitacao)
        acao, observacao = hst.Acao.DEVOLVIDA, servico.motivo_devolucao
    elif decisao == apr.Decisao.REJEITAR:
        servico.situacao = SituacaoServico.REJEITADA
        # Reaproveita `motivo_devolucao`, e o nome do campo é que ficou estreito:
        # ele guarda "por que este pedido voltou para você", e o motivo da
        # reprovação é a mesma informação para quem lê a tela. Uma segunda
        # coluna com o mesmo conteúdo faria cada tela escolher qual das duas
        # mostrar — e alguma escolheria errado.
        servico.motivo_devolucao = _ultima_justificativa(solicitacao)
        acao, observacao = hst.Acao.REJEITADA, servico.motivo_devolucao
    elif decisao == apr.Decisao.CANCELAR:
        servico.situacao = SituacaoServico.CANCELADA
        acao, observacao = hst.Acao.CANCELADA, ""
    else:  # pragma: no cover - Decisao só tem três valores
        return

    servico.save(update_fields=["situacao", "motivo_devolucao"])
    # A decisão da APROVAÇÃO vira linha do histórico do PEDIDO: quem lê a
    # timeline não deveria precisar abrir a bandeja para saber quem assinou.
    hst.registrar(servico, acao, quem=quem, observacao=observacao)

    if decisao == apr.Decisao.APROVAR:
        # ESTE é o degrau que faltava no fluxo. A cadeia terminou, o pedido
        # entrou na fila da área que executa — e até aqui ninguém tinha contado
        # isso a ela. Do lado de quem pediu, o pedido dizia "Aprovada" e parava,
        # e a leitura óbvia era a de que aprovar devolve o pedido ao solicitante.
        from workspace.services import atendimento as atd

        atd.avisar_a_fila(servico)


def _ultima_justificativa(solicitacao) -> str:
    """O que o aprovador escreveu ao devolver ou reprovar."""
    etapa = solicitacao.etapas.exclude(justificativa="").order_by("-decidido_em").first()
    return etapa.justificativa if etapa else ""


def ao_aprovar_etapa(sender, solicitacao, etapa, quem, **kwargs) -> None:
    """Ouvinte de `etapa_aprovada` — o degrau vira linha, o pedido não muda.

    A situação do serviço continua "aguardando aprovação", e é assim que tem de
    ser: um degrau aprovado num pedido de três degraus não liberou nada. O que
    muda é só o que a pessoa consegue LER.

    Antes disto a linha do tempo mentia por omissão. Numa cadeia de gestor →
    área → diretoria, ela mostrava "Aprovado" com o nome do último e nada dos
    outros dois — e quem lesse concluiria que ninguém mais tinha assinado. A
    informação existia em `EtapaAprovacao` e não chegava a quem lê.
    """
    servico = SolicitacaoServico.objects.filter(aprovacao=solicitacao).first()
    if servico is None:
        return

    from workspace.services import historico as hst

    hst.registrar(
        servico,
        hst.Acao.ETAPA_APROVADA,
        quem=quem,
        observacao=_qual_degrau(etapa),
    )


def _qual_degrau(etapa) -> str:
    """"Degrau 2 · Compras". O nome de QUEM assinou já está na coluna do lado;
    o que falta é qual papel ele estava exercendo ao assinar — a mesma pessoa
    pode ser o gestor direto num pedido e a área no seguinte."""
    if etapa.papel_id:
        return f"Degrau {etapa.ordem} · {etapa.papel.nome}"
    return f"Degrau {etapa.ordem} · gestor direto"


def conectar() -> None:
    """Liga o ouvinte. Chamado no `ready()` do app."""
    apr.aprovacao_decidida.connect(
        ao_decidir, dispatch_uid="workspace.catalogo.ao_decidir"
    )
    apr.etapa_aprovada.connect(
        ao_aprovar_etapa, dispatch_uid="workspace.catalogo.ao_aprovar_etapa"
    )
