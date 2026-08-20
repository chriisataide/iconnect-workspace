"""Validação de upload — extensão, MIME, magic bytes e conteúdo suspeito.

## Procedência

Copiada **verbatim** de `dashboard/utils/security.py::validate_file_upload`, do
repositório `controle_atendimento_iconnect`, na separação dos dois produtos
(agosto de 2026). Só a docstring é nova.

Copiada, e não reescrita, por uma razão específica: a checagem que dá valor a esta
função é a de **magic bytes** — a única que pega um `.pdf` que na verdade é
executável. Extensão e `Content-Type` vêm do cliente e são ambos falsificáveis
digitando. Toda reescrita de validador de upload que eu já vi mantém as duas
checagens fáceis e perde a difícil, porque as duas primeiras são óbvias no
requisito e a terceira só aparece quando alguém pensa no atacante.

Se algum dia divergir do original, que divirja por decisão registrada aqui.

## O comportamento que o chamador precisa conhecer

**Esta função MUTA `arquivo.name`**, prefixando um uuid de 8 caracteres para
evitar path traversal. É correto para quem grava o arquivo com o nome que o
usuário mandou; aqui é dano, porque o nome no disco já é um uuid nosso
(`workspace/models/anexo.py::caminho_do_anexo`).

E validamos duas vezes o mesmo arquivo — em `verificar()` e de novo em
`guardar()` —, então dois prefixos se empilham e `nome_original` chega ao usuário
como `c3599522_2036a287_cupom.jpg`. Já chegou. Por isso `anexos.validar()` faz
snapshot e restaura o nome em volta desta chamada.
"""

from __future__ import annotations

import logging
import os
import re
import uuid as _uuid

logger = logging.getLogger(__name__)


def validate_file_upload(uploaded_file):
    """
    Valida arquivos enviados pelo usuário com verificação de extensão,
    MIME type e magic bytes.

    Args:
        uploaded_file: Arquivo enviado

    Returns:
        tuple: (is_valid, error_message)
    """
    # Tamanho máximo (10MB)
    max_size = 10 * 1024 * 1024
    if uploaded_file.size > max_size:
        return False, "Arquivo muito grande. Máximo 10MB."

    # Extensões permitidas e seus MIME types esperados
    ALLOWED_TYPES = {
        ".jpg": ["image/jpeg"],
        ".jpeg": ["image/jpeg"],
        ".png": ["image/png"],
        ".gif": ["image/gif"],
        ".pdf": ["application/pdf"],
        ".doc": ["application/msword"],
        ".docx": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
        ".xlsx": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
        ".xls": ["application/vnd.ms-excel"],
        ".csv": ["text/csv", "application/csv"],
        ".txt": ["text/plain"],
    }

    # Magic bytes para validação de conteúdo real.
    #
    # DIVERGÊNCIA REGISTRADA do original (ver o topo do arquivo): as cinco
    # primeiras vieram de lá; as quatro de Office foram acrescentadas pela
    # auditoria de segurança de agosto de 2026.
    #
    # O buraco era este: `.docx`, `.xlsx`, `.doc` e `.xls` estavam na lista de
    # extensões permitidas e NÃO tinham assinatura. Como o teste de MIME só
    # rodava quando o cliente mandava `Content-Type` — e o cliente decide se
    # manda —, um arquivo com qualquer conteúdo entrava no produto com nome de
    # planilha. Ele não é executado em lugar nenhum (armazenamento privado,
    # download sempre como anexo, `nosniff`), mas entra no acervo e é baixado
    # depois por outra pessoa, na máquina dela.
    #
    # Office moderno é ZIP (`PK\x03\x04`); Office antigo é OLE2 — o mesmo
    # contêiner do `.msi` e do `.doc` com macro. Nenhum dos dois prova ausência
    # de macro: o que a assinatura garante é que o arquivo É do tipo que diz
    # ser, e é isso que a extensão sozinha nunca garantiu.
    MAGIC_BYTES = {
        ".jpg": [b"\xff\xd8\xff"],
        ".jpeg": [b"\xff\xd8\xff"],
        ".png": [b"\x89PNG\r\n\x1a\n"],
        ".gif": [b"GIF87a", b"GIF89a"],
        ".pdf": [b"%PDF"],
        ".docx": [b"PK\x03\x04"],
        ".xlsx": [b"PK\x03\x04"],
        ".doc": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
        ".xls": [b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"],
    }

    # Extensões que são TEXTO por definição e não têm assinatura possível.
    # Para elas a prova é a ausência de byte nulo nos primeiros 4 KB: nenhum
    # texto legítimo tem `\x00`, e todo executável e contêiner binário tem.
    # Sem isto, `.txt` e `.csv` seriam a porta que as extensões de Office
    # deixaram de ser.
    SO_TEXTO = (".txt", ".csv")

    file_extension = os.path.splitext(uploaded_file.name.lower())[1]

    if file_extension not in ALLOWED_TYPES:
        return False, f"Tipo de arquivo não permitido: {file_extension}"

    # Verificar MIME type (Content-Type header).
    #
    # Continua sendo verificado SÓ quando vem, e continua não sendo prova de
    # nada: o cabeçalho é escrito pelo cliente. O que mudou é que ele deixou de
    # ser a única checagem para as extensões de Office — o `MAGIC_BYTES` acima
    # agora cobre todas elas, e é ele que responde por conteúdo.
    content_type = getattr(uploaded_file, "content_type", "")
    if content_type and content_type not in ALLOWED_TYPES[file_extension]:
        logger.warning(
            f"Upload rejeitado: extensão {file_extension} com MIME type {content_type}"
        )
        return False, "Tipo de arquivo não corresponde à extensão."

    # Verificar magic bytes se disponíveis
    if file_extension in MAGIC_BYTES and hasattr(uploaded_file, "read"):
        header = uploaded_file.read(16)
        uploaded_file.seek(0)

        expected_magics = MAGIC_BYTES[file_extension]
        if not any(header.startswith(magic) for magic in expected_magics):
            logger.warning(
                f"Upload rejeitado: {uploaded_file.name} falhou verificação de magic bytes"
            )
            return False, "Conteúdo do arquivo não corresponde ao tipo declarado."

    # Texto que não é texto. Ver `SO_TEXTO` acima.
    if file_extension in SO_TEXTO and hasattr(uploaded_file, "read"):
        amostra = uploaded_file.read(4096)
        uploaded_file.seek(0)
        if b"\x00" in amostra:
            logger.warning(
                "Upload rejeitado: %s tem byte nulo e diz ser texto",
                uploaded_file.name,
            )
            return False, "Conteúdo do arquivo não corresponde ao tipo declarado."

    # Verificar conteúdo malicioso.
    #
    # Defesa em PROFUNDIDADE e não controle: lê 4 KB, e quem quiser passar
    # preenche os primeiros 4 KB com espaço. Fica porque pega o caso
    # desatento — e some do raciocínio de quem confia nela.
    if hasattr(uploaded_file, "read"):
        content = uploaded_file.read(4096)  # Ler primeiros 4KB
        uploaded_file.seek(0)

        # Padrões perigosos em qualquer tipo de arquivo
        suspicious_patterns = [
            b"<script",
            b"javascript:",
            b"<?php",
            b"<%",
            b"eval(",
            b"exec(",
            b"import os",
            b"subprocess",
            b"__import__",
        ]
        content_lower = content.lower()
        for pattern in suspicious_patterns:
            if pattern in content_lower:
                logger.warning(
                    f"Upload rejeitado: conteúdo malicioso detectado em {uploaded_file.name}"
                )
                return False, "Conteúdo malicioso detectado no arquivo."

    # Sanitizar nome do arquivo (prevenir path traversal)
    basename = os.path.basename(uploaded_file.name)  # Remove ../
    safe_name = re.sub(r"[^\w\-.]", "_", basename)
    name_part, ext = os.path.splitext(safe_name)
    uploaded_file.name = f"{_uuid.uuid4().hex[:8]}_{name_part}{ext}"

    return True, ""
