"""Anexos — guardar com validação e decidir quem pode baixar.

Duas decisões que valem explicação.

**A validação é reusada, não reescrita.** `dashboard.utils.security.
validate_file_upload` já confere extensão, `Content-Type` e *magic bytes*.
Escrever um segundo validador aqui produziria dois caminhos de upload no mesmo
sistema com regras diferentes — e é sempre o mais novo que esquece os magic
bytes. `dashboard` não está na lista de apps proibidos do teste de isolamento
(só `fsm`, `km_audit` e `calculo_vigilante` estão), e o que se importa aqui é
utilitário de segurança, não model de domínio.

**A autorização é do Workspace, não do iConnect.** `dashboard/views/
media_protegida.py` autoriza por `get_user_role`, que são os papéis do iConnect.
Um colaborador do Workspace não tem papel de iConnect, então aquela regra negaria
a ele o próprio comprovante. Quem decide aqui é a identidade do Workspace.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from identidade.services.autorizacao import pode
from workspace.models.anexo import Anexo
from workspace.models.catalogo import SolicitacaoServico


class AnexoError(Exception):
    """Arquivo recusado — tipo, tamanho ou conteúdo que não bate."""


# Teto por solicitação. Não é limite técnico: é que uma fila de aprovação com
# 40 arquivos por pedido não é revisada, é carimbada.
MAXIMO_POR_CAMPO = 5


@dataclass(frozen=True)
class Recusa:
    """Um arquivo que não entrou, com o motivo em português."""

    nome: str
    motivo: str


def validar(arquivo) -> str:
    """`""` quando o arquivo passa; o motivo quando não.

    Delega para o validador do `dashboard`, que confere magic bytes — a única
    checagem que pega `.pdf` que na verdade é executável.

    **Restaura `arquivo.name` depois.** `validate_file_upload` muta o nome,
    prefixando um uuid para evitar path traversal. Isso é correto para quem
    salva o arquivo com o nome que o usuário mandou; aqui é dano:

    - o nome no disco já é um uuid nosso (`caminho_do_anexo`), então o prefixo
      não protege nada que já não esteja protegido;
    - validar duas vezes o mesmo arquivo — e validamos, em `verificar()` e de
      novo em `guardar()` — empilha DOIS prefixos, e `nome_original` chega ao
      usuário como `c3599522_2036a287_cupom.jpg`. Cada revalidação faria o nome
      crescer 9 caracteres até truncar em 255.
    """
    from dashboard.utils.security import validate_file_upload

    nome = getattr(arquivo, "name", "")
    try:
        valido, erro = validate_file_upload(arquivo)
    finally:
        if nome:
            arquivo.name = nome
    return "" if valido else (erro or "Arquivo inválido.")


def verificar_lote(arquivos: dict | None) -> list[Recusa]:
    """Confere todos antes de gravar qualquer um.

    Tudo-ou-nada: gravar os dois primeiros e recusar o terceiro deixaria a
    solicitação num meio-estado que o usuário não entende — ele reenviaria os
    três e ficaria com cinco.
    """
    recusas: list[Recusa] = []
    for chave, lista in (arquivos or {}).items():
        enviados = [f for f in (lista or []) if f]
        if len(enviados) > MAXIMO_POR_CAMPO:
            recusas.append(
                Recusa(chave, f"No máximo {MAXIMO_POR_CAMPO} arquivos por campo.")
            )
            continue
        for arquivo in enviados:
            motivo = validar(arquivo)
            if motivo:
                recusas.append(Recusa(getattr(arquivo, "name", chave), motivo))
    return recusas


@transaction.atomic
def guardar(
    solicitacao: SolicitacaoServico, arquivos: dict | None, quem
) -> list[Anexo]:
    """Persiste os arquivos já validados. Levanta se algum não passar."""
    recusas = verificar_lote(arquivos)
    if recusas:
        raise AnexoError("; ".join(f"{r.nome}: {r.motivo}" for r in recusas))

    criados: list[Anexo] = []
    for chave, lista in (arquivos or {}).items():
        for arquivo in [f for f in (lista or []) if f]:
            criados.append(
                Anexo.objects.create(
                    solicitacao=solicitacao,
                    campo=chave,
                    arquivo=arquivo,
                    nome_original=arquivo.name[:255],
                    tamanho=arquivo.size,
                    tipo_mime=getattr(arquivo, "content_type", "") or "",
                    criado_por=quem,
                )
            )
    return criados


def campos_com_arquivo(arquivos: dict | None) -> set[str]:
    """Quais campos de arquivo vieram preenchidos — para `verificar()` do SVC."""
    return {
        chave
        for chave, lista in (arquivos or {}).items()
        if any(f for f in (lista or []))
    }


# ── Quem pode baixar ────────────────────────────────────────────────


def pode_baixar(pessoa, anexo: Anexo, cache: dict | None = None) -> bool:
    """Solicitante, quem decide a aprovação dele, ou quem aprova sobre ele.

    Ordem deliberada: o teste barato e mais comum primeiro, e a consulta ao
    organograma só se os anteriores falharem.
    """
    if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
        return False

    solicitacao = anexo.solicitacao
    if solicitacao.solicitante_id == pessoa.pk:
        return True

    aprovacao = solicitacao.aprovacao
    if aprovacao is not None:
        # Quem é (ou foi) etapa desta aprovação vê o anexo: aprovar reembolso
        # sem poder abrir o comprovante é carimbar.
        if aprovacao.etapas.filter(aprovador=pessoa).exists():
            return True
        if aprovacao.etapas.filter(decidido_por=pessoa).exists():
            return True

    # `alvo=` obrigatório. Sem alvo, `pode()` responde "posso em geral?" e
    # QUALQUER escopo satisfaz — um gestor com escopo de equipe passaria a ler
    # anexo de toda a empresa. É o mesmo furo que foi corrigido no motor de
    # aprovação; não vou reabri-lo aqui.
    return pode(pessoa, "apr.aprovar", alvo=solicitacao.solicitante, cache=cache)
