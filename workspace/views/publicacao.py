"""Leitura de um comunicado ou notícia."""

from __future__ import annotations

from pathlib import Path

from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from workspace.models import Publicacao, TipoPublicacao
from workspace.services import listagem as lst
from workspace.services import publicacao as pub


def _visivel(request: HttpRequest, pk: int) -> Publicacao:
    """A publicação, se esta pessoa pode lê-la — senão 404.

    Quem publica enxerga também o que não está no ar: é a prévia do rascunho,
    e sem ela a pessoa só descobre como o texto ficou depois de publicar.
    """
    publicacao = Publicacao.objects.para(request.user).filter(pk=pk).first()
    if publicacao is None and pub.pode_publicar(request.user):
        publicacao = Publicacao.objects.filter(pk=pk).first()
    if publicacao is None:
        raise Http404("Publicação não encontrada ou fora do seu alcance.")
    return publicacao


def detalhe(request: HttpRequest, pk: int) -> HttpResponse:
    """Uma publicação. 404 quando não está no ar OU não é para esta pessoa.

    `publicadas()` não basta, e a diferença é o §48. Ela responde "está no ar?"
    e ignora o público-alvo, que nasceu no §9 — então o comunicado endereçado ao
    Financeiro era lido por qualquer pessoa que tivesse o número na URL, e o
    número saía da própria busca.

    `para(request.user)` é o mesmo filtro da home, e é de propósito que seja o
    MESMO: duas definições de "quem vê isto" divergem, e a que diverge é sempre
    a que esquece um caso.

    `request.user` e não `pessoa_da_requisicao()`: aquela devolve uma pessoa de
    REFERÊNCIA para o visitante anônimo, e usá-la aqui entregaria a ele o
    comunicado do departamento dela. Anônimo cai no ramo sem lotação e recebe só
    o que é geral.

    404 e não 403: dizer "existe, mas não é para você" já conta que existe um
    comunicado dirigido a outra área — e o título costuma ser a informação.
    """
    publicacao = _visivel(request, pk)
    return render(
        request,
        "workspace/publicacao.html",
        {
            "publicacao": publicacao,
            "anexo_nome": Path(publicacao.anexo.name).name if publicacao.anexo else "",
        },
    )


def arquivo(request: HttpRequest, pk: int, campo: str) -> HttpResponse:
    """A imagem ou o anexo — mesma regra de quem lê o texto.

    O armazenamento é privado e sem URL: esta é a única porta. A imagem sai
    inline com o tipo que o Pillow reconheceu no upload, e `nosniff` impede o
    navegador de reinterpretar o conteúdo como HTML.
    """
    publicacao = _visivel(request, pk)
    if campo == "imagem" and publicacao.imagem:
        from PIL import Image

        with publicacao.imagem.open("rb") as bruto, Image.open(bruto) as img:
            tipo = pub.FORMATOS_IMAGEM.get(img.format)
        if tipo is None:
            raise Http404("Imagem em formato não suportado.")
        resposta = FileResponse(publicacao.imagem.open("rb"), content_type=tipo)
    elif campo == "anexo" and publicacao.anexo:
        resposta = FileResponse(
            publicacao.anexo.open("rb"),
            as_attachment=True,
            filename=Path(publicacao.anexo.name).name,
        )
    else:
        raise Http404("Arquivo não encontrado.")
    resposta["X-Content-Type-Options"] = "nosniff"
    resposta["Cache-Control"] = "private, max-age=3600"
    return resposta


#: O "Ver todos" de cada card da home.
MURAIS = {
    "comunicados": (TipoPublicacao.COMUNICADO, "Comunicados",
                    "Fique por dentro das informações importantes da empresa."),
    "noticias": (TipoPublicacao.NOTICIA, "Notícias",
                 "Acompanhe as novidades da nossa empresa e do mercado."),
}


def mural(request: HttpRequest, tipo: str) -> HttpResponse:
    """Tudo o que está no ar de um tipo, para esta pessoa, paginado."""
    if tipo not in MURAIS:
        raise Http404
    tipo_pub, titulo, descricao = MURAIS[tipo]
    pagina = lst.paginar(
        Publicacao.objects.para(request.user).do_tipo(tipo_pub), request.GET.get("p"), 12
    )
    return render(
        request,
        "workspace/publicacoes/mural.html",
        {
            "tipo": tipo,
            "titulo": titulo,
            "descricao": descricao,
            "pagina": pagina,
            "itens": pagina.object_list,
            "params": lst.parametros_sem_pagina(request),
        },
    )
