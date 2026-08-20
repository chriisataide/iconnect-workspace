"""Fixtures do iConnect Workspace.

Enxuto de propósito. O conftest do projeto anterior trazia fixtures de ticket,
cliente e DRF, além de desligar Axes, MFA e cifra de campo — nada disso existe
aqui. Sobrou o que é do Workspace, e é uma coisa só.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _anexos_em_diretorio_temporario(tmp_path, settings):
    """Anexos nunca escrevem no repositório.

    `ARQUIVOS_PRIVADOS_ROOT` aponta para `BASE_DIR/arquivos_privados` em
    produção. Sem este autouse, qualquer teste que crie um `Anexo` — inclusive um
    teste de outro app, que nem sabe que anexo existe — deixa comprovantes de
    mentira dentro do projeto. Aconteceu na primeira execução: 34 JPEGs.

    Autouse e não fixture opt-in de propósito: quem esquece de pedir a fixture é
    exatamente quem não sabia que precisava dela.
    """
    settings.ARQUIVOS_PRIVADOS_ROOT = tmp_path / "arquivos_privados"
    return settings.ARQUIVOS_PRIVADOS_ROOT


@pytest.fixture(autouse=True)
def _esquecer_areas_entre_testes():
    """O nome da área que executa cada domínio é memoizado no processo.

    Em produção o memo é invalidado pelos sinais de `Papel`. No teste isso não
    basta: o rollback da transação desfaz o papel sem disparar sinal nenhum, e
    o teste seguinte leria um nome de área que já não existe em lugar nenhum.
    """
    from workspace.services.atendimento import esquecer_areas

    esquecer_areas()
    yield
    esquecer_areas()


@pytest.fixture
def user(db, django_user_model):
    """Alias de `pessoa`. Mantido porque um teste da suíte pede por este nome, e
    renomear fixture é churn sem ganho."""
    return django_user_model.objects.create_user(
        "ana.souza@icodev.com.br", password="senha-de-teste-123", nome="Ana Souza"
    )


@pytest.fixture
def pessoa(db, django_user_model):
    """Uma conta comum. E-mail é o identificador — não há `username`."""
    return django_user_model.objects.create_user(
        "ana.souza@icodev.com.br", password="senha-de-teste-123", nome="Ana Souza"
    )
