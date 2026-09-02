"""A tela 99 — "de onde vem esse número" com um link como resposta.

Ela é o equivalente do "Manutenção · Monitoramento" do benchmark, e existe pelo
mesmo motivo: as telas que consertam o dado são um módulo DECLARADO, e não um
back-office escondido.

A permissão é `eco.carga`, e é SEPARADA de `eco.ler`. Esse é o teste que mais
importa aqui: ver a procedência não pode dar acesso aos números.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from cargas.models import Divergencia, ExecucaoCarga, FonteDados, StatusCarga
from identidade.tests import fabricas as f

pytestmark = pytest.mark.django_db


@pytest.fixture
def fontes_cadastradas(db):
    from django.core.management import call_command

    call_command("semear_fontes", "--aplicar", verbosity=0)
    return {f.chave: f for f in FonteDados.objects.all()}


def _com(apelido, permissoes):
    pessoa = f.pessoa(apelido, nome=apelido.title())
    f.lotar(pessoa)
    f.atribuir(pessoa, f.papel(apelido, permissoes, escopo="global"), escopo="global")
    return pessoa


# ── Quem entra ──────────────────────────────────────────────────────


def test_anonimo_nao_entra(client, fontes_cadastradas):
    resposta = client.get(reverse("workspace:fontes"))

    assert resposta.status_code in (302, 403)


def test_colaborador_comum_recebe_403(client, fontes_cadastradas):
    ana = f.pessoa("ana")
    f.lotar(ana)
    client.force_login(ana)

    assert client.get(reverse("workspace:fontes")).status_code == 403


def test_ver_a_procedencia_nao_da_acesso_aos_numeros(client, fontes_cadastradas):
    """O teste que mais importa desta tela.

    O T.I. precisa consertar uma carga sem enxergar o resultado financeiro. Se
    `eco.carga` implicasse `eco.ler`, ligar alguém no suporte às cargas seria
    dar a ele a margem de todo contrato da empresa.
    """
    operador = _com("ti", ["eco.carga.global"])
    client.force_login(operador)

    assert client.get(reverse("workspace:fontes")).status_code == 200
    assert client.get(reverse("workspace:resultados")).status_code == 403


def test_quem_ve_os_numeros_nao_ve_a_tela_de_fontes_por_tabela(
    client, fontes_cadastradas
):
    """O inverso também vale, e é o que mantém as duas permissões separadas de
    verdade em vez de uma ser um apelido da outra."""
    gerente = _com("gerente", ["eco.ler.global"])
    client.force_login(gerente)

    assert client.get(reverse("workspace:resultados")).status_code == 200
    assert client.get(reverse("workspace:fontes")).status_code == 403


# ── O que a tela diz ────────────────────────────────────────────────


def test_a_tela_distingue_desativada_de_nao_configurada_de_atrasada(
    client, fontes_cadastradas
):
    """Três estados, e eles NÃO são o mesmo.

    Juntá-los num "com problema" faria alguém procurar defeito onde não há: em
    desenvolvimento, nenhuma fonte tem credencial, e isso é normal.
    """
    fontes_cadastradas["monday"].ativa = False
    fontes_cadastradas["monday"].save()
    client.force_login(_com("ti", ["eco.carga.global"]))

    conteudo = client.get(reverse("workspace:fontes")).content.decode()

    assert "desativada" in conteudo
    assert "não configurada" in conteudo


def test_o_mapa_diz_qual_faixa_vem_de_qual_fonte(client, fontes_cadastradas):
    """É o que responde "de onde vem esse número" sem ninguém abrir código."""
    client.force_login(_com("ti", ["eco.carga.global"]))

    mapa = client.get(reverse("workspace:fontes")).context["mapa"]

    por_chave = {item["chave"]: item["fonte"] for item in mapa}
    assert por_chave["dinheiro"] == "sankhya"
    assert por_chave["projetos"] == "monday"
    assert por_chave["satisfacao"] == "iconnect_platform"


def test_a_divergencia_mostra_OS_DOIS_valores(client, fontes_cadastradas):
    """Mostrar só o vencedor esconderia a pergunta que a tela existe para fazer."""
    Divergencia.objects.create(
        entidade="contrato", chave_externa="CT-100", campo="valor_mensal",
        fonte_a="sankhya", valor_a="11000", fonte_b="iconnect_platform",
        valor_b="12000", fonte_vencedora="sankhya",
    )
    client.force_login(_com("ti", ["eco.carga.global"]))

    conteudo = client.get(reverse("workspace:fontes")).content.decode()

    assert "11000" in conteudo and "12000" in conteudo


def test_o_historico_mostra_os_ignorados(client, fontes_cadastradas):
    """`ignorados` é a resposta para "rodei de novo, estraguei alguma coisa?".

    Escondê-lo faria a resposta ser "abra o log do servidor".
    """
    agora = timezone.now()
    ExecucaoCarga.objects.create(
        fonte=fontes_cadastradas["csv"], iniciada_em=agora, terminada_em=agora,
        status=StatusCarga.SUCESSO, lidos=30, ignorados=30,
    )
    client.force_login(_com("ti", ["eco.carga.global"]))

    historico = client.get(reverse("workspace:fontes")).context["historico"]

    assert historico[0].ignorados == 30


def test_sem_provedor_registrado_a_tela_nao_some(client, monkeypatch):
    """Ela existe justamente para quando algo está errado.

    Sumir esconderia que a tela existe — e o "algo está errado" mais provável é
    exatamente o app de cargas não ter subido.
    """
    from workspace.providers import frescor as contrato

    monkeypatch.setattr(contrato, "obter", lambda: None)
    client.force_login(_com("ti", ["eco.carga.global"]))

    resposta = client.get(reverse("workspace:fontes"))

    assert resposta.status_code == 200
    assert "Nenhuma fonte se registrou" in resposta.context["motivo"]
    assert resposta.context["mapa"], "o mapa faixa → fonte não depende de carga"


# ── Recarregar ──────────────────────────────────────────────────────


def test_recarregar_e_POST_e_nunca_GET(client, fontes_cadastradas):
    """Um `GET` faria um prefetch do navegador disparar uma carga — e o
    histórico encheria de linhas que ninguém pediu."""
    client.force_login(_com("ti", ["eco.carga.global"]))

    resposta = client.get(
        reverse("workspace:recarregar_fonte", args=("csv",))
    )

    assert resposta.status_code == 405


def test_quem_nao_opera_nao_recarrega(client, fontes_cadastradas):
    ana = f.pessoa("ana")
    f.lotar(ana)
    client.force_login(ana)

    resposta = client.post(reverse("workspace:recarregar_fonte", args=("csv",)))

    assert resposta.status_code == 403


def test_recarregar_fonte_sem_conector_avisa_em_vez_de_estourar(
    client, fontes_cadastradas
):
    """Fonte cadastrada e sem credencial é o estado normal em desenvolvimento."""
    client.force_login(_com("ti", ["eco.carga.global"]))

    resposta = client.post(
        reverse("workspace:recarregar_fonte", args=("sankhya",)), follow=True
    )

    assert resposta.status_code == 200
    assert any("não foi concluída" in str(m) for m in resposta.context["messages"])


def test_recarregar_dispara_a_carga_de_verdade(client, fontes_cadastradas, tmp_path):
    """O botão roda o MESMO carregador do cron. Um caminho especial aqui seria
    um segundo lugar de escrita — e o primeiro a divergir."""
    from django.test import override_settings

    (tmp_path / "contrato.csv").write_text(
        "chave_externa,codigo,nome_cliente,servico,centro_custo\n"
        "ext-1,C-1,Cliente Fictício,cftv,1042\n",
        encoding="utf-8",
    )
    client.force_login(_com("ti", ["eco.carga.global"]))

    with override_settings(CARGAS_CSV_DIR=str(tmp_path)):
        resposta = client.post(
            reverse("workspace:recarregar_fonte", args=("csv",)), follow=True
        )

    from resultados.models import Contrato

    assert Contrato.objects.filter(codigo="C-1").exists()
    assert any("concluída" in str(m) for m in resposta.context["messages"])
