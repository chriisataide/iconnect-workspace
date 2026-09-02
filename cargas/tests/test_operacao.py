"""O que o operador vê e toca: a saída do comando, o registro e o `/admin/`.

A tela de fontes só chega na Onda 3. Até lá, é isto que responde "a carga rodou?
trouxe o quê? por que parou?" — e por isso a saída do comando é interface de
produto, não conveniência de quem programa.
"""

from __future__ import annotations

from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.admin.sites import AdminSite
from django.core.management import call_command
from django.test import RequestFactory
from django.utils import timezone

from cargas import admin as adm
from cargas.conectores import Registro
from cargas.models import (
    Divergencia,
    ExecucaoCarga,
    FonteDados,
    RegraPrecedencia,
    StatusCarga,
)

pytestmark = pytest.mark.django_db


def _rodar(*args, **kwargs) -> str:
    saida = StringIO()
    call_command(*args, stdout=saida, stderr=saida, **kwargs)
    return saida.getvalue()


# ── A saída do comando ──────────────────────────────────────────────


def test_a_saida_destaca_o_que_foi_rejeitado(fontes, conector, contrato_bruto):
    """Rejeitado é o único contador que pede AÇÃO.

    Ele fica separado de `ignorados` justamente por isso: somá-los esconderia a
    linha que alguém precisa ir consertar na planilha.
    """
    conector("csv", [Registro("contrato", "", {"codigo": "X"}), contrato_bruto()])

    saida = _rodar("carregar_fonte", "csv", "--aplicar")

    assert "rejeitados 1" in saida
    assert "rejeitado contrato:" in saida, "e o motivo, linha a linha"


def test_a_saida_avisa_da_divergencia_e_manda_para_a_tela_de_fontes(
    fontes, conector, contrato_bruto
):
    conector("iconnect_platform", [contrato_bruto(valor_mensal=12000)])
    _rodar("carregar_fonte", "iconnect_platform", "--aplicar")
    conector("sankhya", [contrato_bruto(valor_mensal=11000)])

    saida = _rodar("carregar_fonte", "sankhya", "--aplicar")

    assert "divergências" in saida


def test_a_saida_diz_o_motivo_quando_a_carga_para(fontes, conector, contrato_bruto):
    conector("csv", [contrato_bruto("C-1"), contrato_bruto("C-2")], quebra_em=1)

    saida = _rodar("carregar_fonte", "csv", "--aplicar")

    assert "status   parcial" in saida
    assert "motivo" in saida


def test_a_saida_de_fonte_nao_configurada_nao_parece_defeito(fontes, conector):
    """Rodar sem o Sankhya configurado é estado normal em desenvolvimento.

    Se isso viesse como traceback, quem está subindo o ambiente concluiria que o
    produto está quebrado — e a primeira coisa que faria seria desistir da carga.
    """
    conector("sankhya", [], disponivel=False)

    saida = _rodar("carregar_fonte", "sankhya", "--aplicar")

    assert "não está configurada" in saida
    assert "Traceback" not in saida


def test_o_log_da_execucao_e_truncado_e_nao_ilimitado(fontes, conector):
    """Uma carga com dez mil rejeições não pode gravar um `TextField` de
    megabytes que ninguém vai ler e que trava o `/admin/`."""
    conector("csv", [Registro("contrato", "", {}) for _ in range(50)])

    _rodar("carregar_fonte", "csv", "--aplicar")
    execucao = ExecucaoCarga.objects.latest("iniciada_em")

    assert execucao.rejeitados == 50
    assert len(execucao.log) <= 20000


def test_semear_relata_o_que_atualizou(db):
    """Descrição muda — cadência, responsável, observação. A semeadora atualiza
    isso e diz que atualizou, para o operador saber que o deploy mexeu ali."""
    _rodar("semear_fontes", "--aplicar")
    FonteDados.objects.filter(chave="monday").update(cadencia_esperada="quando der")

    saida = _rodar("semear_fontes", "--aplicar")

    assert "~ fonte monday.com" in saida
    assert FonteDados.objects.get(chave="monday").cadencia_esperada == "a cada 15 minutos"


# ── O registro ──────────────────────────────────────────────────────


def test_a_fonte_sabe_qual_foi_a_ultima_carga_BOA(fontes):
    """A última bem-sucedida data o dado; a última tentativa diz se está de pé.

    São perguntas diferentes e o carimbo precisa das duas — é o caso de dado bom
    de seis horas com a carga das 3h falhada.
    """
    fonte = fontes["sankhya"]
    agora = timezone.now()
    boa = ExecucaoCarga.objects.create(
        fonte=fonte, iniciada_em=agora - timedelta(hours=6),
        terminada_em=agora - timedelta(hours=6), status=StatusCarga.SUCESSO,
    )
    falha = ExecucaoCarga.objects.create(
        fonte=fonte, iniciada_em=agora, terminada_em=agora, status=StatusCarga.FALHA,
    )

    assert fonte.ultima_boa == boa
    assert fonte.ultima_tentativa == falha


def test_execucao_em_andamento_nao_tem_duracao(fontes):
    execucao = ExecucaoCarga.objects.create(fonte=fontes["csv"])

    assert execucao.duracao is None

    execucao.terminada_em = execucao.iniciada_em + timedelta(seconds=90)
    assert execucao.duracao == timedelta(seconds=90)


def test_os_registros_se_apresentam_em_portugues(fontes):
    """Aparecem no seletor do `/admin/` e na lista de divergências."""
    execucao = ExecucaoCarga.objects.create(fonte=fontes["monday"])
    regra = RegraPrecedencia.objects.get(entidade="contrato", campo="fim_vigencia")
    divergencia = Divergencia.objects.create(
        entidade="contrato", chave_externa="C-1", campo="valor_mensal",
        fonte_a="sankhya", valor_a="1", fonte_b="monday", valor_b="2",
    )

    assert str(fontes["monday"]) == "monday.com"
    assert "monday" in str(execucao) and "em_andamento" in str(execucao)
    assert str(regra) == "contrato.fim_vigencia → iconnect_platform"
    assert str(divergencia) == "contrato.valor_mensal · sankhya ≠ monday"


# ── O `/admin/` das cargas ──────────────────────────────────────────


def test_execucao_de_carga_e_registro_e_nao_se_edita(django_user_model):
    """Registro editável não é registro.

    `ExecucaoCarga` é a prova de o que aconteceu — inclusive numa apuração de
    por que um número da reunião estava errado.
    """
    requisicao = RequestFactory().get("/admin/")
    requisicao.user = django_user_model.objects.create_superuser(
        "chefe@icodev.com.br", password="x"
    )
    instancia = adm.ExecucaoAdmin(ExecucaoCarga, AdminSite())

    assert instancia.has_add_permission(requisicao) is False
    assert instancia.has_change_permission(requisicao) is False


def test_divergencia_nao_se_cria_a_mao_mas_se_marca_resolvida(django_user_model):
    """Resolver uma divergência É uma ação de gente — a única escrita permitida.

    Criar uma à mão, não: divergência é um fato observado entre duas fontes, e
    inventar uma faria a tela de fontes apontar um conflito que não existe.
    """
    requisicao = RequestFactory().get("/admin/")
    requisicao.user = django_user_model.objects.create_superuser(
        "chefe@icodev.com.br", password="x"
    )
    instancia = adm.DivergenciaAdmin(Divergencia, AdminSite())

    assert instancia.has_add_permission(requisicao) is False
    assert instancia.has_change_permission(requisicao) is True
    assert "fonte_a" in instancia.readonly_fields, "os valores observados são fato"


def test_fonte_e_precedencia_sao_configuracao_e_continuam_editaveis(django_user_model):
    """Mudar a cadência de uma fonte ou a precedência de um campo não pode
    exigir deploy — são decisões de operação e de negócio, tomadas no dia."""
    requisicao = RequestFactory().get("/admin/")
    requisicao.user = django_user_model.objects.create_superuser(
        "chefe@icodev.com.br", password="x"
    )
    site = AdminSite()

    assert adm.FonteAdmin(FonteDados, site).has_change_permission(requisicao) is True
    assert adm.PrecedenciaAdmin(RegraPrecedencia, site).has_add_permission(requisicao) is True
