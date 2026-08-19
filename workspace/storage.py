"""Armazenamento privado dos anexos do Workspace.

Um `FileSystemStorage` deliberadamente **sem `base_url`**. Isso faz
`anexo.arquivo.url` levantar `ValueError` em vez de devolver um endereço
público — e é o ponto central deste arquivo.

O modo normal de vazar arquivo sensível não é um ataque; é um `{{ obj.arquivo.url }}`
escrito por distração num template, seis meses depois, por alguém que não sabia
que aquele campo era atestado médico. Storage sem `base_url` transforma esse
descuido em erro na hora do desenvolvimento, em vez de num incidente silencioso.

O único caminho até o arquivo é `workspace:baixar_anexo`, que autoriza antes de
entregar.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class ArmazenamentoPrivado(FileSystemStorage):
    """Grava em `ARQUIVOS_PRIVADOS_ROOT`, que o nginx não serve.

    `deconstructible` porque o storage vai dentro de um `FileField` e portanto
    precisa ser serializável em migração. Sem isso, `makemigrations` falha.
    """

    @property
    def base_location(self):
        """Lido a cada acesso, não no `__init__`.

        O storage é instanciado na DEFINIÇÃO do campo (`storage=Armazenamento
        Privado()`), que roda no import do model. Congelar o caminho ali faz
        `settings.ARQUIVOS_PRIVADOS_ROOT` sobrescrito em teste não ter efeito —
        e a suíte passa a gravar anexo dentro do repositório. Aconteceu.
        """
        return str(settings.ARQUIVOS_PRIVADOS_ROOT)

    @property
    def location(self):
        return str(Path(self.base_location).resolve())

    def url(self, name: str) -> str:
        """Não existe URL pública. Sempre levanta.

        `FileSystemStorage.url()` cai em `settings.MEDIA_URL` quando `base_url`
        é `None` — passar `base_url=None` no `__init__` produzia exatamente o
        contrário do pretendido: um endereço `/media/...` que o nginx serve sem
        autenticação, para um arquivo que nem está lá. O teste
        `test_arquivo_nao_tem_url_publica` existe por causa disso.
        """
        raise ValueError(
            "Anexo do Workspace não tem URL pública — use "
            "reverse('workspace:baixar_anexo', args=[anexo.pk])."
        )


def caminho_do_documento(instance, filename: str) -> str:
    """`documentos/<uuid>.<ext>` — o arquivo do acervo normativo.

    Privado como todo o resto: política interna, procedimento operacional e
    contrato-modelo não são conteúdo público, e um deles vazado é o tipo de
    coisa que a empresa descobre por terceiro.
    """
    extensao = Path(filename).suffix.lower()[:10]
    return f"documentos/{uuid.uuid4().hex}{extensao}"


def caminho_da_imagem(instance, filename: str) -> str:
    """`publicacoes/<uuid>.<ext>` — mesma regra de nome do anexo.

    UUID e não o nome enviado pela mesma razão de sempre, e aqui com um motivo a
    mais: imagem de comunicado costuma vir de um celular com nome que diz onde e
    quando a foto foi tirada.
    """
    extensao = Path(filename).suffix.lower()[:10]
    return f"publicacoes/{uuid.uuid4().hex}{extensao}"


def caminho_da_correspondencia(instance, filename: str) -> str:
    """`correspondencias/<uuid>.<ext>` — a foto do envelope ou do lacre.

    Privado como o resto: um envelope fotografado mostra nome, endereço e às
    vezes o conteúdo.
    """
    extensao = Path(filename).suffix.lower()[:10]
    return f"correspondencias/{uuid.uuid4().hex}{extensao}"


def caminho_do_anexo(instance, filename: str) -> str:
    """`<solicitacao>/<uuid>.<ext>` — nome original NÃO vai para o disco.

    Duas razões. A primeira é colisão: dois "comprovante.pdf" no mesmo mês.
    A segunda é que nome de arquivo carrega informação — "atestado-depressao.pdf"
    conta sobre a pessoa antes de alguém abrir o arquivo. O nome que o usuário
    reconhece fica em `nome_original`, na tabela, sob a mesma autorização do
    conteúdo.
    """
    extensao = Path(filename).suffix.lower()[:10]
    return f"anexos/{instance.solicitacao_id or 'orfao'}/{uuid.uuid4().hex}{extensao}"
