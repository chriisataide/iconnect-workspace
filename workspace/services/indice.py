"""Alimenta o índice de busca. Por sinal, não por rotina noturna.

Índice que atualiza de madrugada faz o autor publicar um POP e não achá-lo. E o
primeiro reflexo de quem não acha é publicar de novo — então o acervo ganha
duplicata antes de ganhar leitor.

## O que NÃO entra no índice

Os **aplicativos** do launcher. Eles vivem em memória, montados no `ready()`, e
`apps_disponiveis(pessoa)` já recorta por permissão sem tocar o banco. Indexá-los
criaria uma cópia que fica velha a cada deploy, para ganhar nada: são dez itens
numa lista já filtrada.

O índice existe para **conteúdo com público-alvo no banco**. `buscar()` junta as
duas fontes de forma explícita.
"""

from __future__ import annotations

import unicodedata

from django.db import transaction

from workspace.models.busca import EntradaIndice, OrigemIndice, SujeitoIndice


def normalizar(texto: str) -> str:
    """Minúsculas sem acento — 'ferias' encontra 'férias'.

    O Postgres faria com `unaccent`, mas o índice guarda o texto JÁ normalizado:
    normalizar na escrita custa uma vez por publicação, normalizar na leitura
    custaria a cada tecla digitada por cada pessoa.
    """
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    return "".join(
        c for c in sem_acento if not unicodedata.combining(c)
    ).casefold().strip()


@transaction.atomic
def indexar(
    *,
    dominio: str,
    origem_id: str,
    origem: str,
    titulo: str,
    url: str,
    subtitulo: str = "",
    corpo: str = "",
    icone: str = "",
    sujeitos=("*",),
) -> EntradaIndice:
    """Cria ou atualiza a entrada, e substitui os sujeitos dela.

    Substitui, não acrescenta: documento que deixa de ser público tem de PERDER
    o sujeito `*`. Acrescentar deixaria o antigo no lugar, e a mudança de
    público-alvo não teria efeito na busca — o pior tipo de falha de permissão,
    porque a tela do documento passa a dizer uma coisa e a busca outra.
    """
    entrada, _ = EntradaIndice.objects.update_or_create(
        dominio=dominio,
        origem_id=str(origem_id),
        defaults={
            "origem": origem,
            "titulo": titulo[:200],
            "subtitulo": subtitulo[:300],
            "texto": normalizar(" ".join(filter(None, (titulo, subtitulo, corpo)))),
            "url": url[:300],
            "icone": icone[:30],
        },
    )

    desejados = {str(s)[:60] for s in (sujeitos or ["*"])} or {"*"}
    atuais = set(entrada.sujeitos.values_list("sujeito", flat=True))

    entrada.sujeitos.filter(sujeito__in=atuais - desejados).delete()
    SujeitoIndice.objects.bulk_create(
        [SujeitoIndice(entrada=entrada, sujeito=s) for s in desejados - atuais]
    )
    return entrada


def remover(dominio: str, origem_id: str) -> int:
    """Tira do índice. Os sujeitos vão com a entrada, por `CASCADE`."""
    apagadas, _ = EntradaIndice.objects.filter(
        dominio=dominio, origem_id=str(origem_id)
    ).delete()
    return apagadas


# ── Adaptadores por origem ──────────────────────────────────────────
#
# Cada função sabe traduzir UM model para a entrada do índice. É aqui que mora a
# resposta a "quem vê isto", e é de propósito que a resposta não fique no model:
# o mesmo `Documento` tem público-alvo, e a `Publicacao` não — o índice unifica
# duas coisas com regras diferentes.


def indexar_documento(documento) -> None:
    """Documento normativo. Fora do índice quando não está vigente.

    Rascunho, vencido e revogado não aparecem em busca — a busca é a superfície
    onde o POP errado é encontrado por acidente.
    """
    if not documento.vigente:
        remover("cnt.documento", documento.pk)
        return

    indexar(
        dominio="cnt.documento",
        origem_id=documento.pk,
        origem=OrigemIndice.DOCUMENTO,
        titulo=documento.titulo,
        subtitulo=documento.resumo or documento.get_tipo_display(),
        corpo=documento.corpo,
        url=f"/workspace/documentacao/{documento.slug}/",
        icone="book",
        sujeitos=documento.publico_alvo or ["*"],
    )


def sujeitos_da_publicacao(publicacao) -> list[str]:
    """O público-alvo da publicação no vocabulário do índice — §48.

    Esta função nasceu de um vazamento. `indexar_publicacao` dizia "publicação
    não tem público-alvo ainda" e gravava `["*"]`; o campo tinha nascido no §9 e
    o comentário ficou para trás. A home filtrava certo com `.para()`, e a BUSCA
    devolvia a todo mundo — inclusive a quem nunca entrou — o comunicado
    endereçado a um departamento.

    VAZIO significa a empresa inteira, e não ninguém: é a mesma regra de
    `PublicacaoQuerySet.para()`, e as duas precisam concordar.
    """
    sujeitos = [f"unidade:{pk}" for pk in publicacao.unidades.values_list("pk", flat=True)]
    sujeitos += [
        f"depto:{pk}" for pk in publicacao.departamentos.values_list("pk", flat=True)
    ]
    return sujeitos or ["*"]


def indexar_publicacao(publicacao) -> None:
    """Comunicado ou notícia. Só o que está no ar, e só para quem alcança."""
    from workspace.models.comunicacao import TipoPublicacao

    if not publicacao.no_ar:
        remover("com.publicacao", publicacao.pk)
        return

    e_comunicado = publicacao.tipo == TipoPublicacao.COMUNICADO
    indexar(
        dominio="com.publicacao",
        origem_id=publicacao.pk,
        origem=OrigemIndice.COMUNICADO if e_comunicado else OrigemIndice.NOTICIA,
        titulo=publicacao.titulo,
        subtitulo=publicacao.resumo,
        corpo=publicacao.corpo,
        url=f"/workspace/publicacao/{publicacao.pk}/",
        icone="megafone" if e_comunicado else "jornal",
        sujeitos=sujeitos_da_publicacao(publicacao),
    )


def indexar_item(item) -> None:
    """Item do catálogo. Entra como `*`, mesmo quando exige permissão.

    Não é descuido: o catálogo **mostra** o item fora do alcance e o marca "Sem
    acesso", porque saber que o serviço existe é o que faz a pessoa parar de
    mandar e-mail para descobrir. Esconder na busca contradiria a tela — a pessoa
    veria o item no catálogo e não o acharia buscando.
    """
    if not item.ativo:
        remover("svc.item", item.pk)
        return

    indexar(
        dominio="svc.item",
        origem_id=item.pk,
        origem=OrigemIndice.SERVICO,
        titulo=item.nome,
        subtitulo=item.descricao_curta,
        # Os termos entram no texto buscável, não no subtítulo: quem digita
        # "uber" precisa achar Reembolso, e não precisa ver a palavra "uber" na
        # linha do resultado.
        corpo=" ".join(item.termos or []),
        url=f"/workspace/servicos/{item.chave}/",
        icone=item.icone or "grid",
        sujeitos=["*"],
    )


def indexar_faq(pergunta) -> None:
    """Pergunta frequente — §57. Institucional, entra como `*`.

    A base do assistente já era buscável POR ELE, e não pela busca do portal:
    quem digitava "como peço férias" no ⌘K não achava a resposta que o painel
    do canto responderia na hora.
    """
    if not pergunta.ativo:
        remover("faq.pergunta", pergunta.pk)
        return

    indexar(
        dominio="faq.pergunta",
        origem_id=pergunta.pk,
        origem=OrigemIndice.FAQ,
        titulo=pergunta.pergunta,
        subtitulo=pergunta.get_area_display(),
        # A resposta E as palavras-chave entram no texto buscável: é o mesmo
        # casamento que o assistente faz, e duas buscas que discordam sobre a
        # mesma base são piores que uma busca só.
        corpo=f"{pergunta.resposta} {' '.join(pergunta.palavras_chave or [])}",
        url=f"/workspace/ajuda/?p={pergunta.pk}",
        icone="spark",
        sujeitos=["*"],
    )


def indexar_curso(curso) -> None:
    """Curso da Universidade — §57. O catálogo de cursos é institucional."""
    if not curso.ativo:
        remover("hab.curso", curso.pk)
        return

    indexar(
        dominio="hab.curso",
        origem_id=curso.pk,
        origem=OrigemIndice.CURSO,
        titulo=curso.nome,
        subtitulo=curso.get_tipo_display(),
        corpo=curso.descricao or "",
        url="/workspace/universidade/",
        icone="book",
        sujeitos=["*"],
    )


def indexar_recurso(recurso) -> None:
    """Sala, veículo ou equipamento reservável — §57.

    Quem digita "auditório" quer marcar o auditório, e antes disto a busca só
    achava a palavra se ela aparecesse num comunicado.
    """
    if not recurso.ativo:
        remover("res.recurso", recurso.pk)
        return

    indexar(
        dominio="res.recurso",
        origem_id=recurso.pk,
        origem=OrigemIndice.RECURSO,
        titulo=recurso.nome,
        subtitulo=recurso.get_tipo_display(),
        corpo=recurso.descricao or "",
        url=f"/workspace/reservas/{recurso.codigo}/",
        icone="pin",
        sujeitos=["*"],
    )


def indexar_solicitacao(solicitacao) -> None:
    """O pedido da pessoa — §57, e o único caso de conteúdo PESSOAL no índice.

    Sujeito `pessoa:N` e nunca `*`: o recorte acontece no `WHERE`, então o
    pedido de reembolso de alguém não aparece na contagem de resultado de mais
    ninguém. É o mesmo mecanismo do público-alvo do documento — o vocabulário
    de sujeitos foi desenhado exatamente para isto.

    Só o NOME do serviço vai para o texto buscável. **O formulário não entra**:
    ali moram atestado, dados bancários e motivo de afastamento, e um índice que
    varre isso transforma a caixa de busca num vazador de dado sensível para
    quem espia a tela de alguém. É a mesma regra de `listagem.filtrar_minhas`.
    """
    from workspace.models.catalogo import SITUACOES_NAO_ENVIADAS

    if solicitacao.situacao in SITUACOES_NAO_ENVIADAS:
        # Rascunho não é pedido: ele está no formulário, não na esteira.
        remover("svc.solicitacao", solicitacao.pk)
        return

    indexar(
        dominio="svc.solicitacao",
        origem_id=solicitacao.pk,
        origem=OrigemIndice.SOLICITACAO,
        titulo=f"{solicitacao.item.nome} · #{solicitacao.pk}",
        subtitulo=solicitacao.fase,
        corpo="",
        url="/workspace/minhas-solicitacoes/",
        icone="file",
        sujeitos=[f"pessoa:{solicitacao.solicitante_id}"],
    )


def indexar_correspondencia(correspondencia) -> None:
    """A correspondência da pessoa — §57. Pessoal, como a solicitação.

    Sem destinatário identificado não entra: não há sujeito a quem endereçar, e
    `*` entregaria à empresa inteira o que chegou para alguém.
    """
    if correspondencia.destinatario_id is None:
        remover("cor.correspondencia", correspondencia.pk)
        return

    indexar(
        dominio="cor.correspondencia",
        origem_id=correspondencia.pk,
        origem=OrigemIndice.CORRESPONDENCIA,
        titulo=correspondencia.get_tipo_display(),
        subtitulo=correspondencia.remetente or correspondencia.descricao,
        corpo=f"{correspondencia.numero_rastreio} {correspondencia.empresa}",
        url="/workspace/correspondencias/",
        icone="jornal",
        sujeitos=[f"pessoa:{correspondencia.destinatario_id}"],
    )


# ── Reindexação completa ────────────────────────────────────────────


#: `(model, função, precisa estar ativo?)` — as origens do índice em UM lugar.
#:
#: Uma tabela e não uma sequência de laços: cada origem nova precisa entrar na
#: reindexação E nos sinais, e a versão que esquece um dos dois produz índice
#: que só conserta com `reindexar_busca` rodado à mão.
def _origens():
    from workspace.models.catalogo import ItemCatalogo, SolicitacaoServico
    from workspace.models.comunicacao import Publicacao
    from workspace.models.conteudo import Documento
    from workspace.models.correspondencia import Correspondencia
    from workspace.models.faq import PerguntaFrequente
    from workspace.models.habilitacao import Curso
    from workspace.models.reserva import Recurso

    return (
        ("documentos", Documento, indexar_documento, "cnt.documento"),
        ("publicacoes", Publicacao, indexar_publicacao, "com.publicacao"),
        ("servicos", ItemCatalogo, indexar_item, "svc.item"),
        ("faq", PerguntaFrequente, indexar_faq, "faq.pergunta"),
        ("cursos", Curso, indexar_curso, "hab.curso"),
        ("recursos", Recurso, indexar_recurso, "res.recurso"),
        ("solicitacoes", SolicitacaoServico, indexar_solicitacao, "svc.solicitacao"),
        (
            "correspondencias",
            Correspondencia,
            indexar_correspondencia,
            "cor.correspondencia",
        ),
    )


def reindexar() -> dict[str, int]:
    """Reconstrói o índice a partir das origens. Idempotente.

    Percorre a tabela `_origens()` em vez de repetir um laço por model: cada
    origem nova precisa entrar aqui E nos sinais, e a versão que esquece um dos
    dois produz índice que só conserta com o comando rodado à mão.

    Quem decide se a linha ENTRA é o próprio adaptador — documento vencido,
    curso inativo e rascunho se removem sozinhos. A contagem é feita depois,
    pelo que sobrou no índice: contar aqui exigiria repetir cada uma dessas
    regras, e a cópia diverge.
    """
    contagem: dict[str, int] = {"removidas": 0}

    vistos: set[tuple[str, str]] = set()
    for rotulo, model, adaptador, dominio in _origens():
        for objeto in model.objects.all():
            adaptador(objeto)
        # `vistos` sai da ORIGEM e nunca do índice. Do índice, a entrada órfã —
        # a que sobrou de um objeto apagado sem passar pelo sinal — se
        # declararia vista e nunca seria removida, que é justamente o caso que a
        # reindexação existe para consertar.
        vistos |= {
            (dominio, str(pk)) for pk in model.objects.values_list("pk", flat=True)
        }
        contagem[rotulo] = EntradaIndice.objects.filter(dominio=dominio).count()

    # Órfãs: entrada cuja origem foi apagada direto no banco, sem passar pelo
    # sinal. Reindexação é o único lugar que pode limpar isso.
    for entrada in EntradaIndice.objects.all():
        if (entrada.dominio, entrada.origem_id) not in vistos:
            entrada.delete()
            contagem["removidas"] += 1

    return contagem


# ── Sinais ──────────────────────────────────────────────────────────


def _ao_salvar(adaptador):
    """Fecha o adaptador num receptor. `weak=False` no `connect` é obrigatório:
    a função nasce aqui e morreria antes do primeiro `save()`."""

    def receptor(sender, instance, **kwargs) -> None:
        adaptador(instance)

    return receptor


def _ao_apagar(dominio: str):
    def receptor(sender, instance, **kwargs) -> None:
        remover(dominio, instance.pk)

    return receptor


def _ao_mudar_alvo(sender, instance, action, **kwargs) -> None:
    """Reindexa quando o público-alvo muda — §48.

    `post_save` não basta e a diferença é um vazamento: o M2M é gravado DEPOIS
    do `save()`, então o índice guardaria o alcance anterior. Na criação, o
    anterior é "nenhum alvo" — ou seja, a empresa inteira —, e a segmentação que
    quem publica acabou de escolher não valeria na busca.
    """
    if action in ("post_add", "post_remove", "post_clear"):
        indexar_publicacao(instance)


def conectar() -> None:
    """Liga os sinais. Chamado no `ready()` do app.

    Sai da MESMA tabela `_origens()` que a reindexação: sinal e reindexação que
    conhecem listas diferentes é como uma origem passa a existir só depois de
    alguém rodar o comando à mão.
    """
    from django.db.models.signals import m2m_changed, post_delete, post_save

    from workspace.models.comunicacao import Publicacao

    for _rotulo, model, adaptador, dominio in _origens():
        nome = model.__name__.lower()
        post_save.connect(
            _ao_salvar(adaptador),
            sender=model,
            dispatch_uid=f"wks.indice.save.{nome}",
            weak=False,
        )
        post_delete.connect(
            _ao_apagar(dominio),
            sender=model,
            dispatch_uid=f"wks.indice.delete.{nome}",
            weak=False,
        )

    # O público-alvo da publicação é M2M, e M2M não dispara `post_save`.
    for atributo in ("unidades", "departamentos"):
        m2m_changed.connect(
            _ao_mudar_alvo,
            sender=getattr(Publicacao, atributo).through,
            dispatch_uid=f"wks.indice.alvo.{atributo}",
        )
