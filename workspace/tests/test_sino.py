"""O sino do header — §4.

Ele era citado num comentário desta casca desde a primeira versão e **nunca
existiu**. Notificação só era alcançável pelo trilho lateral, que não aparece na
home nem em tela de módulo: a pessoa recebia o aviso de que o pedido dela foi
aprovado e não tinha por onde vê-lo sem digitar a URL.

O que estes testes guardam:

1. **Só para quem entrou.** Notificação é de UMA pessoa e o hub é aberto — um
   sino para visitante anônimo mostraria aviso de alguém.
2. **O contador é o de quem está logado**, não o de qualquer um.
3. **Limpar o contador devolve à tela de origem.** O sino é clicável de
   qualquer lugar; mandar todo mundo para a Central quebraria o fluxo de quem
   só quis zerar o número.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace.context import LIMITE_DO_SINO
from workspace.models import Notificacao, TipoNotificacao

pytestmark = pytest.mark.django_db


def avisar(pessoa, titulo, lida=False):
    from django.utils import timezone

    return Notificacao.objects.create(
        destinatario=pessoa,
        tipo=TipoNotificacao.PEDIDO_APROVADO,
        titulo=titulo,
        url=reverse("workspace:minhas_solicitacoes"),
        lida_em=timezone.now() if lida else None,
    )


@pytest.fixture
def ana():
    pessoa = f.pessoa("ana")
    f.lotar(pessoa)
    return pessoa


def test_o_sino_aparece_para_quem_entrou(client, ana):
    client.force_login(ana)

    assert 'class="au-sino"' in client.get(reverse("workspace:home")).content.decode()


def test_o_sino_nao_existe_para_anonimo(client, ana):
    """O hub é aberto. Um sino sem sessão mostraria o que não é de ninguém."""
    avisar(ana, "Seu pedido foi aprovado")

    corpo = client.get(reverse("workspace:home")).content.decode()

    assert "au-sino-painel" not in corpo
    assert "Seu pedido foi aprovado" not in corpo


def test_o_contador_conta_so_as_nao_lidas(client, ana):
    client.force_login(ana)
    avisar(ana, "Nova 1")
    avisar(ana, "Nova 2")
    avisar(ana, "Velha", lida=True)

    assert client.get(reverse("workspace:home")).context["nao_lidas"] == 2


def test_o_contador_e_de_quem_esta_logado(client, ana):
    """O mesmo defeito que já vazou uma vez neste produto: contador de área
    pessoal calculado para a pessoa errada."""
    outra = f.pessoa("bruno")
    f.lotar(outra)
    avisar(outra, "Pedido do Bruno")

    client.force_login(ana)
    resposta = client.get(reverse("workspace:home"))

    assert resposta.context["nao_lidas"] == 0
    assert "Pedido do Bruno" not in resposta.content.decode()


def test_o_painel_mostra_um_recorte_e_nao_o_historico(client, ana):
    """Cinco linhas respondem "o que aconteceu enquanto eu não estava". O
    histórico completo é a tela de Notificações, e carregá-lo no header sairia
    caro em TODA página do portal."""
    for i in range(LIMITE_DO_SINO + 3):
        avisar(ana, f"Aviso {i}")

    client.force_login(ana)
    recentes = client.get(reverse("workspace:home")).context["notificacoes_recentes"]

    assert len(recentes) == LIMITE_DO_SINO


def test_o_painel_leva_a_tela_cheia(client, ana):
    client.force_login(ana)

    corpo = client.get(reverse("workspace:home")).content.decode()

    assert reverse("workspace:notificacoes") in corpo


def test_marcar_lidas_pelo_sino_volta_para_a_tela_de_origem(client, ana):
    avisar(ana, "Seu pedido foi aprovado")
    client.force_login(ana)

    resposta = client.post(
        reverse("workspace:marcar_lidas"), {"voltar": reverse("workspace:servicos")}
    )

    assert resposta["Location"] == reverse("workspace:servicos")
    assert Notificacao.objects.de(ana).nao_lidas().count() == 0


def test_marcar_lidas_recusa_destino_de_fora(client, ana):
    """`voltar` vem do formulário, e formulário é campo de entrada. Sem a
    checagem, um link montado de fora usaria o POST desta pessoa para
    redirecioná-la para qualquer lugar."""
    client.force_login(ana)

    resposta = client.post(
        reverse("workspace:marcar_lidas"), {"voltar": "https://exemplo.invalido/"}
    )

    assert resposta["Location"] == reverse("workspace:notificacoes")
