"""O carregador de `.env` — e a regra de que o ambiente de verdade vence.

Existe porque a mesma pessoa bateu duas vezes em "a integração não está
configurada" com o arquivo de configuração ao lado do `manage.py`: as
variáveis só valiam se exportadas antes do `runserver`.
"""

from __future__ import annotations

import os

from iconnect_workspace.settings.base import _carregar_env


def test_le_chave_valor(tmp_path, monkeypatch):
    arquivo = tmp_path / ".env"
    arquivo.write_text("N8N_PONTO_WEBHOOK_URL=http://localhost:5678/webhook/x\n")
    monkeypatch.delenv("N8N_PONTO_WEBHOOK_URL", raising=False)

    _carregar_env(arquivo)

    assert os.environ["N8N_PONTO_WEBHOOK_URL"] == "http://localhost:5678/webhook/x"


def test_o_ambiente_de_verdade_sempre_vence(tmp_path, monkeypatch):
    """Em produção quem manda é o systemd ou o Docker. Um `.env` esquecido no
    servidor não pode sobrescrever o segredo que veio de lá."""
    arquivo = tmp_path / ".env"
    arquivo.write_text("PONTO_TESTE_CHAVE=do-arquivo\n")
    monkeypatch.setenv("PONTO_TESTE_CHAVE", "do-ambiente")

    _carregar_env(arquivo)

    assert os.environ["PONTO_TESTE_CHAVE"] == "do-ambiente"


def test_ignora_comentario_linha_vazia_e_lixo(tmp_path, monkeypatch):
    arquivo = tmp_path / ".env"
    arquivo.write_text(
        "# um comentário\n"
        "\n"
        "   \n"
        "linha sem igual\n"
        "PONTO_TESTE_OK=valor\n"
    )
    monkeypatch.delenv("PONTO_TESTE_OK", raising=False)

    _carregar_env(arquivo)

    assert os.environ["PONTO_TESTE_OK"] == "valor"


def test_aceita_export_e_aspas(tmp_path, monkeypatch):
    """Os arquivos deste projeto são escritos para poderem ir ao `source`."""
    arquivo = tmp_path / ".env"
    arquivo.write_text('export PONTO_TESTE_ASPAS="com espaco"\n')
    monkeypatch.delenv("PONTO_TESTE_ASPAS", raising=False)

    _carregar_env(arquivo)

    assert os.environ["PONTO_TESTE_ASPAS"] == "com espaco"


def test_arquivo_ausente_nao_quebra(tmp_path):
    """Produção não tem `.env`, e isso é o normal — não um erro."""
    _carregar_env(tmp_path / "nao-existe")


def test_o_env_real_do_projeto_alimenta_as_settings():
    """O caminho completo: se há `.env` na raiz, as settings o enxergam."""
    from pathlib import Path

    from django.conf import settings

    if not (Path(settings.BASE_DIR) / ".env").exists():
        import pytest

        pytest.skip("este checkout não tem .env — é o esperado em CI")

    assert settings.PONTO_N8N_WEBHOOK_URL, "com .env na raiz, o webhook não pode estar vazio"
