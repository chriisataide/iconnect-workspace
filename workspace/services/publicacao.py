"""COM — publicar comunicado e notícia de dentro do portal.

## Por que existe

O modelo `Publicacao` existia desde a primeira onda e a única porta para ele era
o **Django admin**, que exige `is_staff`. Quem escreve comunicado da empresa é o
R.H. e a diretoria — nenhum dos dois tem `is_staff`, nem deveria ter: o admin
edita a base sem passar pelas regras nem pelo histórico do produto.

O resultado prático é que publicar significava pedir para outra pessoa. E o
efeito disso num portal corporativo é conhecido: a comunicação volta para o
e-mail, e o mural fica com três avisos de 2024.

## O que este módulo NÃO faz

Não decide quem lê. Isso é `Publicacao.objects.para(pessoa)`, no queryset, para
que a home, a busca e um futuro feed não divirjam sobre o que "é para mim"
significa.
"""

from __future__ import annotations

from django.utils import timezone

from identidade.services.autorizacao import pode
from workspace.models.comunicacao import Publicacao, TipoPublicacao

PERMISSAO_PUBLICAR = "com.publicar"


class PublicacaoError(Exception):
    """A publicação não pode ser gravada assim."""


def pode_publicar(pessoa, cache: dict | None = None) -> bool:
    return pode(pessoa, PERMISSAO_PUBLICAR, cache=cache)


def _garantir(pessoa, cache=None) -> None:
    if not pode_publicar(pessoa, cache=cache):
        raise PublicacaoError("Você não pode publicar comunicados.")


def redacao(pessoa, cache: dict | None = None):
    """Tudo que quem publica precisa ver — inclusive o que não está no ar.

    É o oposto de `publicadas()`: rascunho, agendado e expirado aparecem aqui e
    em lugar nenhum mais. Sem esta lista, um comunicado agendado para a semana
    que vem some da tela de quem o escreveu — e ele reescreve.
    """
    _garantir(pessoa, cache=cache)
    return (
        Publicacao.objects.nao_arquivadas()
        .select_related("autor")
        .prefetch_related("unidades", "departamentos")
    )


def arquivadas(pessoa, cache: dict | None = None):
    _garantir(pessoa, cache=cache)
    return Publicacao.objects.filter(arquivado=True).select_related("autor")


def salvar(
    pessoa,
    publicacao: Publicacao | None = None,
    *,
    titulo: str,
    tipo: str,
    resumo: str = "",
    corpo: str = "",
    prioridade: int = 0,
    fixado: bool = False,
    publicar: bool = False,
    publicar_em=None,
    expira_em=None,
    unidades=(),
    departamentos=(),
    imagem=None,
    anexo=None,
    cache: dict | None = None,
) -> Publicacao:
    """Cria ou atualiza. `publicar=False` grava rascunho.

    Um caminho só para criar e editar de propósito: com dois, a validação do
    título vazio acaba em um e não no outro — e o comunicado sem título entra
    pela porta que esqueceram.
    """
    _garantir(pessoa, cache=cache)

    titulo = (titulo or "").strip()
    if not titulo:
        raise PublicacaoError("O título é obrigatório.")
    if tipo not in TipoPublicacao.values:
        raise PublicacaoError("Tipo de publicação inválido.")

    # A EXPIRAÇÃO É COMPARADA COM A DATA QUE VAI VALER, e não só com a que veio
    # do formulário.
    #
    # A checagem antiga exigia as duas datas preenchidas — e no formulário de
    # publicação NOVA o campo "Publicar em" nasce vazio, porque não há objeto
    # para preenchê-lo. Quem escrevia um comunicado, preenchia só "Expira em" e
    # errava o ano caía num buraco silencioso: a validação era pulada, a
    # publicação era gravada, a tela dizia "Comunicado publicado." e ele não
    # aparecia para ninguém — nem para quem escreveu. A conclusão de quem via
    # isso é exatamente "publicar comunicado não funciona".
    efetivo = publicar_em or (publicacao.publicar_em if publicacao else timezone.now())
    if expira_em and expira_em <= efetivo:
        raise PublicacaoError(
            "A expiração tem de ser depois da publicação — do jeito que está, "
            "isto sairia do ar antes de aparecer para alguém."
        )

    novo = publicacao is None
    publicacao = publicacao or Publicacao(autor=pessoa)
    publicacao.titulo = titulo[:200]
    publicacao.tipo = tipo
    publicacao.resumo = (resumo or "").strip()[:300]
    publicacao.corpo = corpo or ""
    # `try` e não `int()` cru: o formulário é `novalidate`, e o valor chega da
    # requisição sem passar por form do Django. Um `prioridade=normal` — que é o
    # que um formulário desatualizado em outra aba manda — virava `ValueError`
    # dentro da view, ou seja, TELA DE ERRO 500 no lugar de uma mensagem.
    #
    # A view já se defendia disso ao REEXIBIR o formulário (`_inteiro`), e não
    # ao gravar. Metade da defesa é a que dá a falsa sensação de que existe.
    try:
        publicacao.prioridade = int(prioridade or 0)
    except (TypeError, ValueError):
        publicacao.prioridade = 0
    publicacao.fixado = bool(fixado)
    publicacao.publicado = bool(publicar)
    if publicar_em:
        publicacao.publicar_em = publicar_em
    publicacao.expira_em = expira_em
    if imagem is not None:
        publicacao.imagem = imagem
    if anexo is not None:
        publicacao.anexo = anexo
    # O autor NÃO é reescrito na edição: quem corrigiu uma vírgula não passa a
    # assinar o comunicado de outra pessoa.
    if novo:
        publicacao.autor = pessoa
    publicacao.save()

    # `set` e não `add`: editar tirando um departamento do alvo tem de TIRAR.
    # Com `add`, o alvo só cresceria, e a publicação restrita ao Financeiro
    # continuaria alcançando quem foi marcado por engano na primeira gravação.
    publicacao.unidades.set(unidades or [])
    publicacao.departamentos.set(departamentos or [])
    return publicacao


def publicar(publicacao: Publicacao, pessoa, cache=None) -> Publicacao:
    """Tira do rascunho e põe no ar."""
    _garantir(pessoa, cache=cache)
    publicacao.publicado = True
    publicacao.arquivado = False
    if publicacao.publicar_em > timezone.now():
        # Quem clica "publicar" quer que apareça AGORA. Manter a data futura
        # faria o botão não fazer nada visível, e a pessoa clicaria de novo.
        publicacao.publicar_em = timezone.now()
    publicacao.save(update_fields=["publicado", "arquivado", "publicar_em"])
    return publicacao


def despublicar(publicacao: Publicacao, pessoa, cache=None) -> Publicacao:
    """Tira do ar e devolve para rascunho. O texto continua editável."""
    _garantir(pessoa, cache=cache)
    publicacao.publicado = False
    publicacao.save(update_fields=["publicado"])
    return publicacao


def arquivar(publicacao: Publicacao, pessoa, cache=None) -> Publicacao:
    """Isto acabou — sai da lista de trabalho e não volta sozinho.

    Diferente de despublicar, que é "por enquanto". Sem os dois, a lista de
    rascunhos enche de comunicado de 2019 que ninguém tem coragem de apagar, e
    o rascunho de verdade se perde no meio.
    """
    _garantir(pessoa, cache=cache)
    publicacao.arquivado = True
    publicacao.publicado = False
    publicacao.save(update_fields=["arquivado", "publicado"])
    return publicacao


def excluir(publicacao: Publicacao, pessoa, cache=None) -> None:
    """Apaga de vez. Só rascunho que nunca foi ao ar.

    O que já foi publicado não se apaga: alguém leu, alguém agiu, e a pergunta
    "o que a empresa comunicou em março" precisa de resposta. Para isso existe
    arquivar.
    """
    _garantir(pessoa, cache=cache)
    if publicacao.publicado or publicacao.arquivado:
        raise PublicacaoError(
            "Isto já foi ao ar. Use arquivar — o que a empresa comunicou não se apaga."
        )
    publicacao.delete()
