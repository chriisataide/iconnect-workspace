"""Acervo de documentos — quem vê, quem precisa confirmar, o que está vencendo.

## A regra que sustenta o resto

Documento vencido **não é apresentado como vigente**. Ele não desaparece — quem
tem o link ainda abre, e a tela diz que está vencido — mas sai da vitrine e sai
da busca. Acervo que apresenta POP vencido junto com POP em vigor é pior que não
ter acervo: a pessoa segue o procedimento errado achando que seguiu o certo.

## Por que a confirmação de leitura importa mais do que parece

Comunicado corporativo por e-mail não tem retorno. Documento com leitura
obrigatória e trilha por versão é requisito direto de ISO 9001/27001 e peça de
defesa trabalhista — e é a única métrica do acervo que vale dinheiro.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import models, transaction
from django.utils import timezone

from identidade.services.autorizacao import subjects_de
from workspace.models.conteudo import (
    ConfirmacaoLeitura,
    Documento,
    SituacaoDocumento,
    TipoDocumento,
)

# Janela de aviso para o dono. 30 dias é o mínimo para reunir quem revisa,
# revisar e republicar sem virar urgência.
DIAS_DE_AVISO = 30


class ConteudoError(Exception):
    """Operação inválida sobre o acervo."""


# ── Leitura ─────────────────────────────────────────────────────────


def visiveis_para(pessoa, cache: dict | None = None):
    """Documentos vigentes que esta pessoa pode ver.

    Anônimo recebe só o que é público (`["*"]`) — o Workspace é aberto na rede da
    empresa, e uma política geral não é segredo. Documento de departamento exige
    saber a quem a pessoa pertence, e isso exige login.
    """
    subjects = subjects_de(pessoa, cache=cache)
    return Documento.objects.publicados().para_subjects(subjects)


def agrupado_para(
    pessoa,
    cache: dict | None = None,
    categoria: str = "",
    texto: str = "",
) -> dict[str, list[Documento]]:
    """Por tipo, na ordem de declaração do enum — que é ordem de busca.

    Alfabética poria "Instrução de trabalho" antes de "POP", quando POP é o que a
    maioria vem procurar. Mesmo raciocínio do catálogo de serviços.

    `categoria` e `texto` são os filtros do §37. O texto olha **título e
    resumo**, e não o corpo: o corpo de um POP tem centenas de palavras e
    casaria com quase tudo — um filtro que devolve o acervo inteiro é o mesmo
    que nenhum filtro.
    """
    consulta = visiveis_para(pessoa, cache=cache).select_related("dono")
    if categoria:
        consulta = consulta.filter(categoria=categoria)
    if texto.strip():
        consulta = consulta.filter(
            models.Q(titulo__icontains=texto.strip())
            | models.Q(resumo__icontains=texto.strip())
        )

    por_tipo: dict[str, list[Documento]] = {}
    for documento in consulta:
        por_tipo.setdefault(documento.tipo, []).append(documento)

    agrupado: dict[str, list[Documento]] = {}
    for tipo in TipoDocumento:
        itens = por_tipo.get(tipo.value)
        if itens:
            agrupado[tipo.label] = itens
    return agrupado


def categorias_de(pessoa, cache: dict | None = None) -> list[str]:
    """As categorias que ESTA pessoa alcança — §33 e §37.

    Do alcance dela e não da tabela inteira: uma lista de filtros que oferece
    "Jurídico" a quem não tem nenhum documento jurídico é um filtro que sempre
    devolve vazio, e filtro que devolve vazio ensina a não usar filtro.
    """
    return sorted(
        {
            categoria
            for categoria in visiveis_para(pessoa, cache=cache)
            .exclude(categoria="")
            .values_list("categoria", flat=True)
            if categoria
        }
    )


#: Quantos documentos cabem em "vistos por último". Seis é o que cabe numa
#: faixa sem rolar; mais que isso deixa de ser atalho e vira uma segunda lista.
LIMITE_RECENTES = 6


def recentes_para(pessoa, cache: dict | None = None) -> list[Documento]:
    """Os últimos publicados ou revisados — §37.

    **Por `atualizado_em`, e não por `criado_em`.** A pergunta que esta faixa
    responde é *"o que mudou desde a última vez que olhei"*, e a revisão de uma
    norma antiga é justamente a mudança que importa — ordenar por criação
    esconderia a v2 do POP de 2023 embaixo de um manual novo que ninguém espera.

    Sem "favoritos" ao lado, e é decisão: favorito exige uma tabela por pessoa,
    uma tela para gerenciar, e depende de a pessoa lembrar de marcar. Num acervo
    de dezenas de documentos, "os últimos que mudaram" responde a mesma pergunta
    sem pedir nada a ninguém.
    """
    return list(
        visiveis_para(pessoa, cache=cache)
        .select_related("dono")
        .order_by("-atualizado_em")[:LIMITE_RECENTES]
    )


def pode_ver(documento: Documento, pessoa, cache: dict | None = None) -> bool:
    """Autorização de UM documento, para a tela de leitura.

    Vencido e revogado seguem acessíveis por link direto, de propósito: quem
    precisa saber o que dizia o POP anterior a uma ocorrência precisa poder abrir.
    O que muda é que a tela avisa, e a vitrine não lista.
    """
    if documento.situacao == SituacaoDocumento.RASCUNHO:
        # Rascunho é só do dono. Rascunho visível é meio-documento tratado como
        # norma, e alguém vai seguir.
        return getattr(pessoa, "pk", None) == documento.dono_id

    alvo = set(documento.publico_alvo or ["*"])
    return bool(alvo & set(subjects_de(pessoa, cache=cache)))


# ── Leitura obrigatória ─────────────────────────────────────────────


def pendentes_de_leitura(pessoa, cache: dict | None = None) -> list[Documento]:
    """Obrigatórios, visíveis, sem confirmação DA VERSÃO ATUAL.

    Uma consulta para as confirmações, não uma por documento: a lista aparece no
    Meu dia de toda pessoa, em toda visita.
    """
    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        return []

    # O filtro de OBRIGATÓRIO vem antes do de público-alvo, e a ordem é a
    # diferença entre duas consultas e três.
    #
    # `visiveis_para()` chama `para_subjects()`, que avalia o queryset inteiro
    # em Python e devolve outro `filter(pk__in=...)` — duas idas ao banco. Com
    # `obrigatorios()` primeiro, o conjunto que sai do banco já é o pequeno (a
    # empresa tem dezenas de documentos e um punhado de leituras obrigatórias),
    # e o recorte por sujeito acontece na lista que já está na memória.
    #
    # Isto não é micro-otimização: esta função roda no trilho, em TODA tela do
    # Workspace. Uma consulta a mais aqui é uma consulta a mais em cada
    # carregamento de cada página.
    obrigatorios = list(
        Documento.objects.publicados().obrigatorios().select_related("dono")
    )
    if not obrigatorios:
        return []

    alvo = set(subjects_de(pessoa, cache=cache))
    obrigatorios = [
        d for d in obrigatorios if alvo & set(d.publico_alvo or ["*"])
    ]
    if not obrigatorios:
        return []

    confirmadas = set(
        ConfirmacaoLeitura.objects.filter(
            pessoa=pessoa, documento__in=obrigatorios
        ).values_list("documento_id", "versao")
    )
    return [d for d in obrigatorios if (d.pk, d.versao) not in confirmadas]


@transaction.atomic
def confirmar(documento: Documento, pessoa) -> ConfirmacaoLeitura:
    """Registra a leitura da versão atual. Idempotente."""
    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        raise ConteudoError("Confirmação exige saber quem confirmou.")
    if not documento.vigente:
        # Confirmar leitura de documento vencido registraria conformidade com um
        # texto que não vale mais.
        raise ConteudoError("Este documento não está vigente.")

    # `get_or_create` e NÃO try/except IntegrityError.
    #
    # Capturar `IntegrityError` dentro de um `atomic` deixa a transação
    # QUEBRADA: a consulta seguinte estoura `TransactionManagementError`, e o
    # duplo clique em "Confirmo que li" viraria erro 500 em vez de idempotência.
    # `get_or_create` põe um savepoint em volta do insert, então a colisão
    # desfaz só o savepoint e a transação segue viva.
    confirmacao, _ = ConfirmacaoLeitura.objects.get_or_create(
        documento=documento, pessoa=pessoa, versao=documento.versao
    )
    return confirmacao


def ja_confirmou(documento: Documento, pessoa) -> bool:
    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        return False
    return ConfirmacaoLeitura.objects.filter(
        documento=documento, pessoa=pessoa, versao=documento.versao
    ).exists()


def cobertura_de_leitura(documento: Documento) -> dict:
    """Quantos confirmaram a versão atual. O número que vai para a auditoria.

    Sem denominador ainda: "quantas pessoas o público-alvo alcança" exige resolver
    sujeito → pessoas, que é consulta reversa do organograma e entra com o
    relatório de conformidade. Prometer um percentual agora seria inventar o
    denominador.
    """
    confirmadas = ConfirmacaoLeitura.objects.filter(
        documento=documento, versao=documento.versao
    ).count()
    return {"versao": documento.versao, "confirmadas": confirmadas}


# ── Para o dono ─────────────────────────────────────────────────────


PERMISSAO_PUBLICAR = "doc.publicar"


class DocumentoError(Exception):
    """O arquivo não pode ser anexado assim."""


def pode_publicar(pessoa, cache: dict | None = None) -> bool:
    from identidade.services.autorizacao import pode

    return pode(pessoa, PERMISSAO_PUBLICAR, cache=cache)


def anexar_arquivo(documento: Documento, arquivo, pessoa, cache=None) -> Documento:
    """O upload do §33.

    Substitui o anterior quando já havia um, e é o certo: a versão do documento
    é `Documento.versao`, não a contagem de arquivos. Guardar os dois faria a
    tela ter de escolher qual mostrar — e escolheria errado uma vez.

    O NOME ORIGINAL é guardado à parte porque o nome no disco é um UUID: sem
    ele, quem baixa recebe `a3f9c1....pdf` e não reconhece o que pediu.
    """
    if not pode_publicar(pessoa, cache=cache):
        raise DocumentoError("Você não pode publicar documentos.")

    # Reusa o validador dos anexos — extensão, MIME e magic bytes. Ver o
    # docstring de `anexos.validar`.
    from workspace.services import anexos as anx

    motivo = anx.validar(arquivo)
    if motivo:
        raise DocumentoError(f"{getattr(arquivo, 'name', 'arquivo')}: {motivo}")

    documento.arquivo = arquivo
    documento.arquivo_nome = getattr(arquivo, "name", "")[:255]
    documento.arquivo_tamanho = getattr(arquivo, "size", 0) or 0
    documento.save(update_fields=["arquivo", "arquivo_nome", "arquivo_tamanho"])
    return documento


def a_vencer(dono=None, dias: int = DIAS_DE_AVISO):
    """Documentos vigentes que vencem na janela. Filtra por dono se informado."""
    hoje = timezone.localdate()
    consulta = Documento.objects.publicados().filter(
        vigencia_fim__isnull=False, vigencia_fim__lte=hoje + timedelta(days=dias)
    )
    return consulta.filter(dono=dono) if dono is not None else consulta


def vencidos(dono=None):
    """Já vencidos e ainda marcados como vigentes — a fila de trabalho do dono."""
    consulta = Documento.objects.vencidos()
    return consulta.filter(dono=dono) if dono is not None else consulta


# ── Escrever — §37 ──────────────────────────────────────────────────
#
# O acervo podia ser LIDO e não podia ser MANTIDO. Criar um POP exigia o
# `/admin/` do Django, que pede `is_staff` — e quem escreve procedimento é a
# área que o executa, não quem administra o banco. Na prática, publicar norma
# significava pedir para outra pessoa; é o mesmo defeito que a redação de
# comunicados corrigiu, no módulo ao lado.


#: Os sujeitos que o público-alvo aceita, e o vocabulário é o MESMO do
#: *security trimming* da busca. Um segundo vocabulário para dizer "quem vê"
#: divergiria do primeiro na terceira semana — e aí o documento aparece na busca
#: de quem não pode abri-lo.
PUBLICO_TODOS = "*"


def alvo_de(unidades=None, departamentos=None) -> list[str]:
    """Converte a escolha da tela em sujeitos. Vazio = a empresa inteira.

    VAZIO significa "todo mundo", e não "ninguém". O contrário faria todo
    documento já existente sumir no dia em que o campo ganhasse tela — e o POP
    que a empresa inteira precisa ler seria o primeiro a desaparecer.
    """
    sujeitos = [f"unidade:{u}" for u in (unidades or []) if str(u).isdigit()]
    sujeitos += [f"depto:{d}" for d in (departamentos or []) if str(d).isdigit()]
    return sujeitos or [PUBLICO_TODOS]


def alvo_para_tela(documento: Documento | None) -> tuple[set[int], set[int]]:
    """`(unidades, departamentos)` marcados, para o formulário reabrir igual."""
    if documento is None:
        return set(), set()
    unidades, departamentos = set(), set()
    for sujeito in documento.publico_alvo or []:
        prefixo, _, valor = str(sujeito).partition(":")
        if not valor.isdigit():
            continue
        if prefixo == "unidade":
            unidades.add(int(valor))
        elif prefixo == "depto":
            departamentos.add(int(valor))
    return unidades, departamentos


def redacao(pessoa, cache: dict | None = None):
    """O acervo de quem escreve — inclusive rascunho, vencido e revogado.

    Diferente de `visiveis_para()`, que é a vitrine: quem mantém a norma precisa
    ver justamente o que saiu do ar, porque é isso que dá trabalho a ele.
    """
    if not pode_publicar(pessoa, cache=cache):
        return Documento.objects.none()
    return Documento.objects.select_related("dono").order_by(
        "situacao", "tipo", "titulo"
    )


@transaction.atomic
def salvar(
    pessoa,
    documento: Documento | None,
    slug: str,
    titulo: str,
    tipo: str,
    categoria: str = "",
    resumo: str = "",
    corpo: str = "",
    versao: str = "",
    unidades=None,
    departamentos=None,
    leitura_obrigatoria: bool = False,
    vigencia_inicio=None,
    vigencia_fim=None,
    publicar: bool = False,
    arquivo=None,
    cache: dict | None = None,
) -> Documento:
    """Cria ou atualiza. Uma função para os dois, como na redação de comunicados.

    Duas divergiriam na terceira semana — e a validação que existe só numa delas
    é a porta por onde entra o documento sem título.
    """
    from django.utils.text import slugify

    if not pode_publicar(pessoa, cache=cache):
        raise DocumentoError("Você não pode publicar documentos.")
    if not titulo.strip():
        raise DocumentoError("O documento precisa de um título.")
    if tipo not in TipoDocumento.values:
        raise DocumentoError("Tipo de documento inválido.")

    if vigencia_fim and vigencia_inicio and vigencia_fim < vigencia_inicio:
        # Vigência invertida produz documento que nasce vencido: some da vitrine
        # no mesmo instante em que é publicado, e ninguém entende por quê.
        raise DocumentoError("A vigência termina antes de começar.")

    if documento is None:
        base = slugify(slug or titulo)[:80] or "documento"
        documento = Documento(slug=_slug_livre(base), dono=pessoa)
    elif documento.dono_id is None:
        documento.dono = pessoa

    documento.titulo = titulo.strip()[:200]
    documento.tipo = tipo
    documento.categoria = categoria.strip()[:60]
    documento.resumo = resumo.strip()[:300]
    documento.corpo = corpo
    # A versão é do AUTOR e não um contador automático. "2.1" quer dizer algo
    # para quem mantém a norma; um número que sobe sozinho a cada salvamento
    # invalidaria toda confirmação de leitura por causa de um erro de digitação
    # corrigido — e é a confirmação que vai para a auditoria.
    documento.versao = (versao.strip() or documento.versao or "1")[:12]
    documento.publico_alvo = alvo_de(unidades, departamentos)
    documento.leitura_obrigatoria = bool(leitura_obrigatoria)
    if vigencia_inicio:
        documento.vigencia_inicio = vigencia_inicio
    documento.vigencia_fim = vigencia_fim
    documento.situacao = (
        SituacaoDocumento.VIGENTE if publicar else SituacaoDocumento.RASCUNHO
    )
    documento.save()

    if arquivo is not None:
        anexar_arquivo(documento, arquivo, pessoa, cache=cache)
    return documento


def _slug_livre(base: str) -> str:
    """`base`, `base-2`, `base-3`… O slug é único e vai na URL.

    Recusar o documento porque já existe outro com título parecido faria quem
    escreve inventar um título pior para caber na regra.
    """
    if not Documento.objects.filter(slug=base).exists():
        return base
    for sufixo in range(2, 100):
        tentativa = f"{base[:76]}-{sufixo}"
        if not Documento.objects.filter(slug=tentativa).exists():
            return tentativa
    raise DocumentoError("Não foi possível gerar um endereço para este documento.")


@transaction.atomic
def revogar(documento: Documento, pessoa, cache: dict | None = None) -> Documento:
    """Tira da vitrine sem apagar.

    Revogado continua acessível por link direto, de propósito: quem investiga
    uma ocorrência precisa poder abrir o POP que valia na época. O que muda é
    que a vitrine não lista e a tela avisa.
    """
    if not pode_publicar(pessoa, cache=cache):
        raise DocumentoError("Você não pode revogar documentos.")
    documento.situacao = SituacaoDocumento.REVOGADO
    documento.save(update_fields=["situacao"])
    return documento


# ── Cobrar — §37 ────────────────────────────────────────────────────


def avisar_leituras_obrigatorias() -> int:
    """Um aviso por pessoa que deve leitura obrigatória. Devolve quantos foram.

    É o que separa "a empresa publicou" de "a empresa informou". Sem ele, a
    confirmação só acontece para quem abre o Meu dia por conta própria — e é
    justamente essa confirmação que se leva para auditoria de ISO ou para defesa
    trabalhista.

    O dedupe do `criar()` usa `origem_id`, e aqui ele inclui a VERSÃO: publicar
    a v2 de um POP volta a cobrar todo mundo, mesmo quem já tinha lido a v1 —
    que é exatamente o comportamento que a confirmação por versão existe para
    garantir.

    Custo: duas consultas por pessoa, e o `cache` compartilhado guarda as
    lotações entre elas. É comando diário sobre quem tem lotação, não laço em
    requisição — e a alternativa (resolver sujeito → pessoas no banco) é a
    consulta reversa do organograma, que ainda não existe.
    """
    from django.contrib.auth import get_user_model
    from django.urls import reverse

    from workspace.models.notificacao import TipoNotificacao
    from workspace.services import notificacoes as nt

    if not Documento.objects.publicados().obrigatorios().exists():
        return 0

    cache: dict = {}
    enviados = 0
    pessoas = (
        get_user_model()
        .objects.filter(is_active=True, lotacao__isnull=False)
        .order_by("pk")
    )
    for pessoa in pessoas:
        for documento in pendentes_de_leitura(pessoa, cache=cache):
            if nt.criar(
                pessoa,
                TipoNotificacao.LEITURA_OBRIGATORIA,
                f"Leitura obrigatória: {documento.titulo}",
                f"{documento.get_tipo_display()} · versão {documento.versao}. "
                "Confirme depois de ler.",
                url=reverse("workspace:documento", args=[documento.slug]),
                dominio="cnt.leitura",
                origem_id=f"{documento.pk}:{documento.versao}",
            ):
                enviados += 1
    return enviados


def avisar_vencimentos(dias: int = DIAS_DE_AVISO) -> int:
    """Avisa o DONO do documento que a vigência está acabando ou acabou.

    Vai para o dono e não para quem lê: `publicados()` tira o vencido da
    vitrine, então um POP que passa da vigência simplesmente SOME do acervo. As
    pessoas continuam precisando do procedimento; ele deixou de existir na tela,
    e só quem o mantém pode republicá-lo.
    """
    from django.urls import reverse

    from workspace.models.notificacao import TipoNotificacao
    from workspace.services import notificacoes as nt

    hoje = timezone.localdate()
    enviados = 0
    # Vencidos primeiro: um documento pode estar nas duas listas conforme a
    # janela, e o aviso de "vence em N dias" para algo que já venceu seria
    # informação errada.
    for documento in list(vencidos()) + [
        d for d in a_vencer(dias=dias) if not d.vencido
    ]:
        restam = (documento.vigencia_fim - hoje).days
        titulo = (
            f"{documento.titulo} venceu"
            if documento.vencido
            else f"{documento.titulo} vence em {restam} dias"
        )
        if nt.criar(
            documento.dono,
            TipoNotificacao.DOCUMENTO_A_VENCER,
            titulo,
            f"{documento.get_tipo_display()} · vigência até "
            f"{documento.vigencia_fim.strftime('%d/%m/%Y')}.",
            url=reverse("workspace:documento", args=[documento.slug]),
            dominio="cnt.vigencia",
            origem_id=f"{documento.pk}:{documento.vigencia_fim.isoformat()}",
        ):
            enviados += 1
    return enviados
