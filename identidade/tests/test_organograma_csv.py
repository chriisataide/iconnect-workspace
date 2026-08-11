"""Exportar e importar o organograma por CSV.

É o caminho real de preenchimento: RH ordena por departamento no Excel, não por
hierarquia. Se a importação exigisse ordem topológica, não seria usada.
"""

from __future__ import annotations

import csv
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from identidade.models import Departamento, Lotacao, Situacao, Unidade
from identidade.tests import fabricas as f

CABECALHO = (
    "username,nome,email,matricula,cargo,unidade_codigo,unidade_nome,"
    "departamento_codigo,departamento_nome,gestor_username,centro_custo_codigo,situacao"
)


def csv_em(tmp_path, *linhas) -> str:
    caminho = tmp_path / "org.csv"
    caminho.write_text("\n".join([CABECALHO, *linhas]) + "\n", encoding="utf-8")
    return str(caminho)


def importar(caminho, **kwargs) -> str:
    saida = StringIO()
    call_command("importar_organograma", caminho, stdout=saida, stderr=saida, **kwargs)
    return saida.getvalue()


def exportar(**kwargs) -> str:
    saida = StringIO()
    call_command("exportar_organograma", stdout=saida, **kwargs)
    return saida.getvalue()


# ── Exportação ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_exporta_cabecalho_que_a_importacao_le():
    """O ciclo tem de fechar: o que sai entra de volta."""
    f.pessoa("ana")
    linhas = list(csv.DictReader(StringIO(exportar())))
    assert linhas[0]["username"] == "ana"
    assert "gestor_username" in linhas[0]


@pytest.mark.django_db
def test_exporta_valores_atuais_de_quem_ja_tem_lotacao():
    sp, ti = f.unidade("SP", "Matriz SP"), f.departamento("TI", "Tecnologia")
    gestor = f.pessoa("gestor")
    ana = f.pessoa("ana")
    f.lotar(gestor)
    f.lotar(ana, gestor=gestor, uni=sp, dep=ti, cargo="Analista", matricula="M-01")

    linha = next(linha for linha in csv.DictReader(StringIO(exportar())) if linha["username"] == "ana")
    assert linha["cargo"] == "Analista"
    assert linha["matricula"] == "M-01"
    assert linha["unidade_codigo"] == "SP"
    assert linha["departamento_codigo"] == "TI"
    assert linha["gestor_username"] == "gestor"


@pytest.mark.django_db
def test_exporta_so_ativos():
    f.pessoa("ativo")
    inativo = f.pessoa("inativo")
    inativo.is_active = False
    inativo.save()

    usernames = {linha["username"] for linha in csv.DictReader(StringIO(exportar(ativos=True)))}
    assert usernames == {"ativo"}


@pytest.mark.django_db
def test_exporta_a_fila_de_trabalho():
    """`--sem-lotacao` é a lista de quem ainda falta — o que RH quer receber."""
    com = f.pessoa("com_lotacao")
    f.lotar(com)
    f.pessoa("sem_lotacao")

    usernames = {linha["username"] for linha in csv.DictReader(StringIO(exportar(sem_lotacao=True)))}
    assert usernames == {"sem_lotacao"}


@pytest.mark.django_db
def test_exporta_cargo_legado_como_sugestao():
    """`PerfilUsuario.cargo` aparece preenchido, para não redigitar."""
    from dashboard.models import PerfilUsuario

    ana = f.pessoa("ana")
    PerfilUsuario.objects.update_or_create(
        user=ana, defaults={"cargo": "Coordenador", "departamento": "OPS"}
    )

    linha = next(linha for linha in csv.DictReader(StringIO(exportar())) if linha["username"] == "ana")
    assert linha["cargo"] == "Coordenador"
    assert linha["departamento_nome"] == "OPS"


# ── Importação ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_simulacao_nao_grava(tmp_path):
    f.pessoa("ana")
    texto = importar(csv_em(tmp_path, "ana,,,,Analista,,,,,,,"))
    assert "SIMULAÇÃO" in texto
    assert Lotacao.objects.count() == 0


@pytest.mark.django_db
def test_cria_lotacao(tmp_path):
    f.pessoa("ana")
    importar(csv_em(tmp_path, "ana,,,M-01,Analista,,,,,,CC-10,ativo"), aplicar=True)

    lot = Lotacao.objects.get()
    assert lot.matricula == "M-01"
    assert lot.cargo == "Analista"
    assert lot.centro_custo_codigo == "CC-10"


@pytest.mark.django_db
def test_cria_unidade_e_departamento_que_nao_existem(tmp_path):
    f.pessoa("ana")
    importar(
        csv_em(tmp_path, "ana,,,,,SP,Matriz SP,TI,Tecnologia,,,"), aplicar=True
    )

    assert Unidade.objects.get(codigo="SP").nome == "Matriz SP"
    assert Departamento.objects.get(codigo="TI").nome == "Tecnologia"
    lot = Lotacao.objects.get()
    assert lot.unidade.codigo == "SP"
    assert lot.departamento.codigo == "TI"


@pytest.mark.django_db
def test_deriva_codigo_do_nome_quando_falta(tmp_path):
    """RH costuma preencher só o nome. Exigir código faria a planilha voltar."""
    f.pessoa("ana")
    importar(csv_em(tmp_path, "ana,,,,,,Campinas,,Financeiro,,,"), aplicar=True)

    assert Unidade.objects.filter(codigo="CAMPINAS").exists()
    assert Departamento.objects.filter(codigo="FINANCEIRO").exists()


@pytest.mark.django_db
def test_reusa_estrutura_existente(tmp_path):
    f.unidade("SP", "Matriz SP")
    f.pessoa("ana")
    importar(csv_em(tmp_path, "ana,,,,,SP,Outro nome,,,,,"), aplicar=True)

    assert Unidade.objects.count() == 1
    assert Unidade.objects.get().nome == "Matriz SP", "não sobrescreve o cadastrado"


@pytest.mark.django_db
def test_atualiza_quem_ja_tem_lotacao(tmp_path):
    ana = f.pessoa("ana")
    f.lotar(ana, cargo="Antigo")
    importar(csv_em(tmp_path, "ana,,,,Novo,,,,,,,"), aplicar=True)

    assert Lotacao.objects.get().cargo == "Novo"
    assert Lotacao.objects.count() == 1, "atualiza, não duplica"


@pytest.mark.django_db
def test_reexecutavel_sem_duplicar(tmp_path):
    f.pessoa("ana")
    caminho = csv_em(tmp_path, "ana,,,,Analista,,,,,,,")
    importar(caminho, aplicar=True)
    importar(caminho, aplicar=True)
    assert Lotacao.objects.count() == 1


# ── A ordem das linhas não importa ──────────────────────────────────


@pytest.mark.django_db
def test_gestor_pode_vir_depois_no_arquivo(tmp_path):
    """Duas passadas existem para isto: RH ordena por departamento."""
    f.pessoa("ana")
    f.pessoa("gestor")
    importar(
        csv_em(
            tmp_path,
            "ana,,,,,,,,,gestor,,",       # referencia o gestor ANTES de ele existir na planilha
            "gestor,,,,,,,,,,,",
        ),
        aplicar=True,
    )

    assert Lotacao.objects.get(user__username="ana").gestor.get_username() == "gestor"


@pytest.mark.django_db
def test_hierarquia_de_tres_niveis_em_ordem_invertida(tmp_path):
    for n in ("base", "meio", "topo"):
        f.pessoa(n)
    importar(
        csv_em(
            tmp_path,
            "base,,,,,,,,,meio,,",
            "meio,,,,,,,,,topo,,",
            "topo,,,,,,,,,,,",
        ),
        aplicar=True,
    )

    from identidade.services import liderados_recursivos

    topo = Lotacao.objects.get(user__username="topo").user
    assert len(liderados_recursivos(topo.pk)) == 2


# ── Erros ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_arquivo_inexistente():
    with pytest.raises(CommandError, match="não encontrado"):
        importar("/tmp/nao_existe_zzz.csv")


@pytest.mark.django_db
def test_csv_sem_coluna_username(tmp_path):
    caminho = tmp_path / "ruim.csv"
    caminho.write_text("nome,cargo\nAna,Analista\n", encoding="utf-8")
    with pytest.raises(CommandError, match="vazio ou sem coluna"):
        importar(str(caminho))


@pytest.mark.django_db
def test_username_inexistente_e_relatado_nao_silenciado(tmp_path):
    texto = importar(csv_em(tmp_path, "fantasma,,,,,,,,,,,"), aplicar=True)
    assert "USERNAME INEXISTENTE" in texto
    assert "fantasma" in texto
    assert Lotacao.objects.count() == 0


@pytest.mark.django_db
def test_gestor_inexistente_cria_lotacao_sem_gestor(tmp_path):
    """Melhor a lotação sem gestor que nenhuma lotação — e o relatório avisa."""
    f.pessoa("ana")
    texto = importar(csv_em(tmp_path, "ana,,,,,,,,,fantasma,,"), aplicar=True)

    assert "GESTOR INEXISTENTE" in texto
    assert Lotacao.objects.get().gestor is None


@pytest.mark.django_db
def test_situacao_invalida_cai_para_ativo_e_avisa(tmp_path):
    f.pessoa("ana")
    texto = importar(csv_em(tmp_path, "ana,,,,,,,,,,,aposentado"), aplicar=True)

    assert "SITUAÇÃO INVÁLIDA" in texto
    assert Lotacao.objects.get().situacao == Situacao.ATIVO


@pytest.mark.django_db
def test_situacao_valida_e_aceita(tmp_path):
    f.pessoa("ana")
    importar(csv_em(tmp_path, "ana,,,,,,,,,,,ferias"), aplicar=True)
    assert Lotacao.objects.get().situacao == Situacao.FERIAS


@pytest.mark.django_db
def test_ciclo_reprova_a_importacao_toda(tmp_path):
    """Gravar metade e deixar o grafo inconsistente é pior que não gravar."""
    f.pessoa("a")
    f.pessoa("b")
    with pytest.raises(CommandError, match="reprovada"):
        importar(
            csv_em(tmp_path, "a,,,,,,,,,b,,", "b,,,,,,,,,a,,"),
            aplicar=True,
        )
    assert Lotacao.objects.exclude(gestor=None).count() == 0


@pytest.mark.django_db
def test_bom_de_verdade_com_bom_e_aceito(tmp_path):
    """CSV do Excel vem com BOM. Sem `utf-8-sig`, a primeira coluna vira
    `\\ufeffusername` e nada é encontrado."""
    caminho = tmp_path / "bom.csv"
    caminho.write_text(CABECALHO + "\nana,,,,Analista,,,,,,,\n", encoding="utf-8-sig")
    f.pessoa("ana")
    importar(str(caminho), aplicar=True)
    assert Lotacao.objects.get().cargo == "Analista"


@pytest.mark.django_db
def test_linha_em_branco_e_ignorada(tmp_path):
    f.pessoa("ana")
    importar(csv_em(tmp_path, "ana,,,,,,,,,,,", ",,,,,,,,,,,"), aplicar=True)
    assert Lotacao.objects.count() == 1


@pytest.mark.django_db
def test_espacos_sao_removidos(tmp_path):
    f.pessoa("ana")
    importar(csv_em(tmp_path, "  ana  ,,,, Analista ,,,,,,,"), aplicar=True)
    assert Lotacao.objects.get().cargo == "Analista"


@pytest.mark.django_db
def test_sem_criar_estrutura_nao_inventa_unidade(tmp_path):
    f.pessoa("ana")
    importar(
        csv_em(tmp_path, "ana,,,,,SP,Matriz,,,,,"), aplicar=True, criar_estrutura=False
    )
    assert Unidade.objects.count() == 0
    assert Lotacao.objects.get().unidade is None


# ── O ciclo completo ────────────────────────────────────────────────


@pytest.mark.django_db
def test_exporta_edita_importa(tmp_path):
    """O fluxo que o RH vai fazer de verdade."""
    for n in ("diretor", "gestor", "ana"):
        f.pessoa(n)

    # 1 · exporta o esqueleto
    linhas = list(csv.DictReader(StringIO(exportar())))
    assert len(linhas) == 3

    # 2 · "preenche no Excel"
    hierarquia = {"ana": "gestor", "gestor": "diretor", "diretor": ""}
    for linha in linhas:
        linha["gestor_username"] = hierarquia[linha["username"]]
        linha["unidade_codigo"] = "SP"
        linha["unidade_nome"] = "Matriz SP"

    caminho = tmp_path / "preenchido.csv"
    with caminho.open("w", encoding="utf-8", newline="") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=linhas[0].keys())
        escritor.writeheader()
        escritor.writerows(linhas)

    # 3 · importa
    importar(str(caminho), aplicar=True)

    from identidade.services import cadeia_de_gestores, liderados_recursivos

    ana = Lotacao.objects.get(user__username="ana").user
    diretor = Lotacao.objects.get(user__username="diretor").user
    assert len(cadeia_de_gestores(ana.pk)) == 2
    assert len(liderados_recursivos(diretor.pk)) == 2
    assert Lotacao.objects.filter(unidade__codigo="SP").count() == 3


# ── Cobertura dos ramos restantes ───────────────────────────────────


@pytest.mark.django_db
def test_exporta_so_quem_ja_tem_lotacao():
    """`--com-lotacao` serve para conferir o que está cadastrado."""
    com = f.pessoa("com_lotacao")
    f.lotar(com)
    f.pessoa("sem_lotacao")

    usernames = {linha["username"] for linha in csv.DictReader(StringIO(exportar(com_lotacao=True)))}
    assert usernames == {"com_lotacao"}


@pytest.mark.django_db
def test_simulacao_resolve_estrutura_sem_criar(tmp_path):
    """Na simulação a unidade é só consultada — o relatório mostra quais
    apareceriam, sem gravar nenhuma."""
    f.pessoa("ana")
    texto = importar(csv_em(tmp_path, "ana,,,,,SP,Matriz,TI,Tecnologia,,,"))

    assert "unidades           1" in texto
    assert "departamentos      1" in texto
    assert Unidade.objects.count() == 0
    assert Departamento.objects.count() == 0


@pytest.mark.django_db
def test_simulacao_aproveita_estrutura_que_ja_existe(tmp_path):
    f.unidade("SP", "Matriz SP")
    f.departamento("TI", "Tecnologia")
    f.pessoa("ana")
    importar(csv_em(tmp_path, "ana,,,,,SP,Matriz SP,TI,Tecnologia,,,"))
    assert Lotacao.objects.count() == 0


@pytest.mark.django_db
def test_sem_criar_estrutura_nao_inventa_departamento(tmp_path):
    f.pessoa("ana")
    importar(
        csv_em(tmp_path, "ana,,,,,,,FIN,Financeiro,,,"),
        aplicar=True,
        criar_estrutura=False,
    )
    assert Departamento.objects.count() == 0
    assert Lotacao.objects.get().departamento is None


@pytest.mark.django_db
def test_gestor_de_linha_com_username_inexistente_e_ignorado(tmp_path):
    """A linha já foi relatada na passada 1; a passada 2 não pode explodir."""
    f.pessoa("gestor")
    texto = importar(
        csv_em(tmp_path, "fantasma,,,,,,,,,gestor,,", "gestor,,,,,,,,,,,"), aplicar=True
    )
    assert "USERNAME INEXISTENTE" in texto
    assert Lotacao.objects.count() == 1


@pytest.mark.django_db
def test_relatorio_trunca_lista_longa_de_problemas(tmp_path):
    """Despejar 400 usernames inexistentes no terminal esconde o resto do
    relatório — a informação útil sai da tela."""
    linhas = [f"fantasma{i},,,,,,,,,,," for i in range(14)]
    texto = importar(csv_em(tmp_path, *linhas), aplicar=True)

    assert "USERNAME INEXISTENTE · 14" in texto
    assert "e 4 outros" in texto
