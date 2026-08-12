"""Busca do Workspace.

Versão honesta do V1.0: procura no que o Workspace realmente tem — aplicativos do
launcher e publicações no ar. **Não** é a busca federada da Onda 5; aquela
precisa do índice `SearchDocument` com `tsvector` e `acl_subjects`, que exige
IDN para o security trimming.

O que aqui já respeita, para não ter de ser refeito depois:

- Recorte por permissão vem do launcher (`apps_disponiveis`), não de um filtro
  aplicado depois sobre o resultado — filtrar no fim vaza contagem.
- Só publicação `no ar` entra. Rascunho e agendado nunca aparecem em busca.
- O formato de saída já é o do resultado agrupado por origem, que é como a
  Onda 5 vai devolver.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from workspace.launcher import apps_disponiveis
from workspace.models import Publicacao, TipoPublicacao

LIMITE_POR_GRUPO = 6
MIN_CARACTERES = 2


@dataclass(frozen=True)
class Resultado:
    origem: str  # "app" | "comunicado" | "noticia"
    titulo: str
    subtitulo: str
    url: str
    icone: str
    disponivel: bool = True


def normalizar(texto: str) -> str:
    """Minúsculas sem acento — 'ferias' encontra 'férias'.

    O Postgres faria isto com `unaccent` (spike S5). Em Python, resolve
    enquanto a busca é sobre dezenas de registros, não dezenas de milhares.
    """
    sem_acento = unicodedata.normalize("NFKD", texto or "")
    return "".join(c for c in sem_acento if not unicodedata.combining(c)).casefold().strip()


def _casa(termo: str, *campos: str) -> bool:
    return any(termo in normalizar(campo) for campo in campos if campo)


def buscar(consulta: str, pessoa=None) -> dict[str, list[Resultado]]:
    """Resultados agrupados por origem. Consulta curta devolve vazio."""
    termo = normalizar(consulta)
    if len(termo) < MIN_CARACTERES:
        return {}

    grupos: dict[str, list[Resultado]] = {}

    apps = [
        Resultado(
            origem="app",
            titulo=spec.nome,
            subtitulo=spec.descricao,
            url=_url_do_app(spec),
            icone=spec.icone,
            disponivel=spec.disponivel,
        )
        for spec in apps_disponiveis(pessoa)
        if _casa(termo, spec.nome, spec.descricao, spec.chave)
    ]
    if apps:
        grupos["Aplicativos"] = apps[:LIMITE_POR_GRUPO]

    for tipo, rotulo in ((TipoPublicacao.COMUNICADO, "Comunicados"), (TipoPublicacao.NOTICIA, "Notícias")):
        achados = [
            Resultado(
                origem=tipo,
                titulo=pub.titulo,
                subtitulo=pub.resumo,
                url=f"/workspace/publicacao/{pub.pk}/",
                icone="megafone" if tipo == TipoPublicacao.COMUNICADO else "jornal",
            )
            # Carrega só o que está no ar e filtra em Python: a base é pequena
            # e `unaccent` no banco é decisão da Onda 5 (spike S5), não daqui.
            for pub in Publicacao.objects.publicadas().do_tipo(tipo)[:100]
            if _casa(termo, pub.titulo, pub.resumo, pub.corpo)
        ]
        if achados:
            grupos[rotulo] = achados[:LIMITE_POR_GRUPO]

    return grupos


def _url_do_app(spec) -> str:
    if spec.url_direta:
        return spec.url_direta
    if spec.url_name:
        from django.urls import reverse

        # `args` porque a página de módulo é uma rota parametrizada pela chave.
        # Sem eles, buscar "RH" estourava NoReverseMatch e derrubava a busca
        # inteira — não só o resultado do módulo.
        return reverse(spec.url_name, args=spec.url_args)
    return ""
