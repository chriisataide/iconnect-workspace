"""O CSV de organograma que vai para produção, exercitado de verdade.

`docs/exemplos/organograma-inicial.csv` é o arquivo que o RH vai copiar e
preencher com nomes reais. Testar o importador com um CSV inventado no teste
deixaria o arquivo real sem verificação nenhuma — e um erro de coluna só
apareceria na hora de usar.

Seis pessoas, escolhidas para cobrir os quatro degraus da cadeia de aprovação e
as duas formas de escopo que `pode()` resolve.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command

from identidade.models import Departamento, Lotacao, Unidade
from identidade.services.autorizacao import liderados_recursivos

CSV = Path(settings.BASE_DIR) / "docs/exemplos/organograma-inicial.csv"

pytestmark = pytest.mark.django_db


@pytest.fixture
def importado():
    saida = StringIO()
    call_command(
        "importar_organograma", str(CSV), "--aplicar", "--criar-usuarios", stdout=saida
    )
    return saida.getvalue()


def test_o_arquivo_existe_e_esta_no_repositorio():
    """Se alguém mover o exemplo, o README que o cita deixa de funcionar."""
    assert CSV.is_file(), f"{CSV} não existe"


def test_importa_as_seis_pessoas(importado):
    assert Lotacao.objects.count() == 6
    assert "contas criadas     6" in importado


def test_contas_criadas_nao_autenticam_por_senha(importado):
    """A empresa usa Microsoft 365: a conta entra por SSO.

    Conta semeada com senha conhecida é a porta que fica aberta depois que todos
    esqueceram que ela existe.
    """
    for user in get_user_model().objects.filter(email__contains="@"):
        assert not user.has_usable_password(), user.email


def test_o_topo_nao_tem_gestor(importado):
    socio = Lotacao.objects.get(user__email="socio.fundador@icodev.com.br")

    assert socio.gestor is None
    assert socio.cargo == "Sócio"


def test_a_hierarquia_tem_quatro_niveis(importado):
    """Quatro níveis porque a cadeia tem quatro degraus. Com três, o teste de
    R$ 300.000 não teria quem assinar."""
    caminho = []
    atual = Lotacao.objects.get(user__email="tecnico.campo@icodev.com.br")
    while atual is not None:
        caminho.append(atual.user.email)
        atual = Lotacao.objects.filter(user=atual.gestor).first() if atual.gestor else None

    assert caminho == [
        "tecnico.campo@icodev.com.br",
        "gerente.campo@icodev.com.br",
        "diretor.operacoes@icodev.com.br",
        "socio.fundador@icodev.com.br",
    ]


def test_escopo_de_equipe_atravessa_dois_niveis(importado):
    """`liderados_recursivos` é o que faz `apr.aprovar.equipe` significar algo.

    O diretor lidera os dois gerentes DIRETAMENTE e as duas pontas
    INDIRETAMENTE — se a consulta recursiva parasse no primeiro nível, ele não
    aprovaria o pedido do técnico, que é o caso mais comum.
    """
    diretor = get_user_model().objects.get(email="diretor.operacoes@icodev.com.br")
    liderados = set(liderados_recursivos(diretor.pk))

    assert {
        get_user_model().objects.get(email=f"{u}@icodev.com.br").pk
        for u in ("gerente.suporte", "gerente.campo", "analista.suporte", "tecnico.campo")
    } == liderados


def test_duas_unidades_para_exercitar_escopo_de_unidade(importado):
    assert {u.codigo for u in Unidade.objects.all()} == {"MTZ", "BA1"}
    tecnico = Lotacao.objects.get(user__email="tecnico.campo@icodev.com.br")
    assert tecnico.unidade.codigo == "BA1", "a ponta de campo não fica na matriz"


def test_centros_de_custo_distintos(importado):
    """Orçamento por centro de custo só se prova com mais de um."""
    centros = set(
        Lotacao.objects.exclude(centro_custo_codigo="").values_list(
            "centro_custo_codigo", flat=True
        )
    )
    assert len(centros) >= 3, centros


def test_departamentos_criados_a_partir_do_csv(importado):
    assert {d.codigo for d in Departamento.objects.all()} == {"DIR", "OPS"}


def test_reimportar_nao_duplica(importado):
    call_command(
        "importar_organograma", str(CSV), "--aplicar", "--criar-usuarios", stdout=StringIO()
    )

    assert Lotacao.objects.count() == 6
    assert get_user_model().objects.filter(email="socio.fundador@icodev.com.br").count() == 1


def test_sem_a_flag_nao_cria_conta():
    """O padrão é não criar: e-mail digitado errado geraria conta fantasma."""
    saida = StringIO()
    call_command("importar_organograma", str(CSV), "--aplicar", stdout=saida)

    assert Lotacao.objects.count() == 0
    assert "E-MAIL INEXISTENTE" in saida.getvalue()


def test_simulacao_nao_grava_nada():
    call_command("importar_organograma", str(CSV), "--criar-usuarios", stdout=StringIO())

    assert Lotacao.objects.count() == 0
    assert not get_user_model().objects.filter(email="socio.fundador@icodev.com.br").exists()


def test_nome_composto_vai_inteiro_para_um_campo(importado):
    """O nome não é partido — e essa é a mudança que `contas.Pessoa` trouxe.

    O `User` do Django tem `first_name` e `last_name`, e o CSV tem uma coluna. A
    importação resolvia partindo no primeiro espaço: "Diretor" e "de Operações".
    A heurística servia ao modelo, não à realidade — em português não há divisão
    útil entre primeiro nome e sobrenome de "Maria Clara Souza Lima".

    `Pessoa.nome` é um campo só, e a exibição decide o recorte: `get_short_name()`
    devolve o primeiro token para a saudação, e o nome inteiro fica intacto.
    """
    diretor = get_user_model().objects.get(email="diretor.operacoes@icodev.com.br")

    assert diretor.nome == "Diretor de Operações"
    assert diretor.get_full_name() == "Diretor de Operações"
    assert diretor.get_short_name() == "Diretor", "a saudação usa só o primeiro"


def test_o_exemplo_nao_carrega_dado_pessoal_real():
    """O arquivo vai para o git. Planilha de RH com gente real num repositório
    é vazamento esperando um clone."""
    import csv as csvlib

    texto = CSV.read_text(encoding="utf-8")
    colunas = next(csvlib.reader(texto.splitlines()))

    # Colunas por nome exato, não substring: "rg" casa dentro de "cargo", e um
    # teste que reprova o arquivo certo é pior que nenhum teste.
    for sensivel in ("cpf", "rg", "salario", "telefone", "endereco", "data_nascimento"):
        assert sensivel not in colunas, f"o exemplo tem coluna {sensivel}"

    # E-mail pessoal denuncia gente real. O do domínio é endereço de trabalho.
    for provedor in ("@gmail", "@hotmail", "@outlook", "@yahoo"):
        assert provedor not in texto.lower(), f"o exemplo tem e-mail {provedor}"
    assert "@icodev.com.br" in texto
