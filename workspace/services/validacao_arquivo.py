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

    # Magic bytes para validação de conteúdo real
    MAGIC_BYTES = {
        ".jpg": [b"\xff\xd8\xff"],
        ".jpeg": [b"\xff\xd8\xff"],
        ".png": [b"\x89PNG\r\n\x1a\n"],
        ".gif": [b"GIF87a", b"GIF89a"],
        ".pdf": [b"%PDF"],
    }

    file_extension = os.path.splitext(uploaded_file.name.lower())[1]

    if file_extension not in ALLOWED_TYPES:
        return False, f"Tipo de arquivo não permitido: {file_extension}"

    # Verificar MIME type (Content-Type header)
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

    # Verificar conteúdo malicioso
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
