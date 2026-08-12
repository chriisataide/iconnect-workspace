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


def indexar_publicacao(publicacao) -> None:
    """Comunicado ou notícia. Só o que está no ar.

    Publicação não tem público-alvo ainda (é COM, onda seguinte), então entra
    como `*`. Quando ganhar segmentação, muda só esta função.
    """
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
        sujeitos=["*"],
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
        url=f"/workspace/servicos/{item.chave}/",
        icone=item.icone or "grid",
        sujeitos=["*"],
    )


# ── Reindexação completa ────────────────────────────────────────────


def reindexar() -> dict[str, int]:
    """Reconstrói o índice a partir das origens. Idempotente."""
    from workspace.models.catalogo import ItemCatalogo
    from workspace.models.comunicacao import Publicacao
    from workspace.models.conteudo import Documento

    contagem = {"documentos": 0, "publicacoes": 0, "servicos": 0, "removidas": 0}

    vistos: set[tuple[str, str]] = set()
    for documento in Documento.objects.all():
        indexar_documento(documento)
        if documento.vigente:
            vistos.add(("cnt.documento", str(documento.pk)))
            contagem["documentos"] += 1
    for publicacao in Publicacao.objects.all():
        indexar_publicacao(publicacao)
        if publicacao.no_ar:
            vistos.add(("com.publicacao", str(publicacao.pk)))
            contagem["publicacoes"] += 1
    for item in ItemCatalogo.objects.all():
        indexar_item(item)
        if item.ativo:
            vistos.add(("svc.item", str(item.pk)))
            contagem["servicos"] += 1

    # Órfãs: entrada cuja origem foi apagada direto no banco, sem passar pelo
    # sinal. Reindexação é o único lugar que pode limpar isso.
    for entrada in EntradaIndice.objects.all():
        if (entrada.dominio, entrada.origem_id) not in vistos:
            entrada.delete()
            contagem["removidas"] += 1

    return contagem


# ── Sinais ──────────────────────────────────────────────────────────


def _ao_salvar_documento(sender, instance, **kwargs) -> None:
    indexar_documento(instance)


def _ao_apagar_documento(sender, instance, **kwargs) -> None:
    remover("cnt.documento", instance.pk)


def _ao_salvar_publicacao(sender, instance, **kwargs) -> None:
    indexar_publicacao(instance)


def _ao_apagar_publicacao(sender, instance, **kwargs) -> None:
    remover("com.publicacao", instance.pk)


def _ao_salvar_item(sender, instance, **kwargs) -> None:
    indexar_item(instance)


def _ao_apagar_item(sender, instance, **kwargs) -> None:
    remover("svc.item", instance.pk)


def conectar() -> None:
    """Liga os sinais. Chamado no `ready()` do app."""
    from django.db.models.signals import post_delete, post_save

    from workspace.models.catalogo import ItemCatalogo
    from workspace.models.comunicacao import Publicacao
    from workspace.models.conteudo import Documento

    for model, salvar, apagar in (
        (Documento, _ao_salvar_documento, _ao_apagar_documento),
        (Publicacao, _ao_salvar_publicacao, _ao_apagar_publicacao),
        (ItemCatalogo, _ao_salvar_item, _ao_apagar_item),
    ):
        nome = model.__name__.lower()
        post_save.connect(salvar, sender=model, dispatch_uid=f"wks.indice.save.{nome}")
        post_delete.connect(
            apagar, sender=model, dispatch_uid=f"wks.indice.delete.{nome}"
        )
