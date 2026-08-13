#!/usr/bin/env python
"""Ponto de entrada administrativo do iConnect Workspace."""

import os
import sys


def main() -> None:
    os.environ.setdefault(
        "DJANGO_SETTINGS_MODULE", "iconnect_workspace.settings.dev"
    )
    try:
        from django.core.management import execute_from_command_line
    except ImportError as erro:  # pragma: no cover - ambiente sem Django
        raise ImportError(
            "Django não foi encontrado. Ative o virtualenv e instale "
            "as dependências: pip install -r requirements.txt"
        ) from erro
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
