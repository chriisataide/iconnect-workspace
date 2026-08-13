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
    "email,nome,matricula,cargo,unidade_codigo,unidade_nome,"
    "departamento_codigo,departamento_nome,gestor_email,centro_custo_codigo,situacao"
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
    assert linhas[0]["email"] == "ana@icodev.com.br"
    assert "gestor_email" in linhas[0]


@pytest.mark.django_db
def test_exporta_valores_atuais_de_quem_ja_tem_lotacao():
    sp, ti = f.unidade("SP", "Matriz SP"), f.departamento("TI", "Tecnologia")
    gestor = f.pessoa("gestor")
    ana = f.pessoa("ana")
    f.lotar(gestor)
    f.lotar(ana, gestor=gestor, uni=sp, dep=ti, cargo="Analista", matricula="M-01")

    linha = next(linha for linha in csv.DictReader(StringIO(exportar())) if linha["email"] == "ana@icodev.com.br")
    assert linha["cargo"] == "Analista"
    assert linha["matricula"] == "M-01"
    assert linha["unidade_codigo"] == "SP"
    assert linha["departamento_codigo"] == "TI"
    assert linha["gestor_email"] == "gestor@icodev.com.br"


@pytest.mark.django_db
def test_exporta_so_ativos():
    f.pessoa("ativo")
    inativo = f.pessoa("inativo")
    inativo.is_active = False
    inativo.save()

    emails = {linha["email"] for linha in csv.DictReader(StringIO(exportar(ativos=True)))}
    assert emails == {"ativo@icodev.com.br"}


@pytest.mark.django_db
def test_exporta_a_fila_de_trabalho():
    """`--sem-lotacao` é a lista de quem ainda falta — o que RH quer receber."""
    com = f.pessoa("com_lotacao")
    f.lotar(com)
    f.pessoa("sem_lotacao")

    emails = {linha["email"] for linha in csv.DictReader(StringIO(exportar(sem_lotacao=True)))}
    assert emails == {"sem_lotacao@icodev.com.br"}


# `test_exporta_cargo_legado_como_sugestao` saiu na separação dos produtos.
#
# Ele verificava que o exportador pré-preenchia `cargo` a partir de
# `dashboard.PerfilUsuario`, para o RH não redigitar. Aquele model ficou no
# iConnect. A sugestão volta pelo SSO, de `jobTitle` do Entra ID — fonte melhor,
# porque é mantida no diretório e não digitada uma vez.


# ── Importação ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_simulacao_nao_grava(tmp_path):
    f.pessoa("ana")
    texto = importar(csv_em(tmp_path, "ana@icodev.com.br,,,Analista,,,,,,,"))
    assert "SIMULAÇÃO" in texto
    assert Lotacao.objects.count() == 0


@pytest.mark.django_db
def test_cria_lotacao(tmp_path):
    f.pessoa("ana")
    importar(csv_em(tmp_path, "ana@icodev.com.br,,M-01,Analista,,,,,,CC-10,ativo"), aplicar=True)

    lot = Lotacao.objects.get()
    assert lot.matricula == "M-01"
    assert lot.cargo == "Analista"
    assert lot.centro_custo_codigo == "CC-10"


@pytest.mark.django_db
def test_cria_unidade_e_departamento_que_nao_existem(tmp_path):
    f.pessoa("ana")
    importar(
        csv_em(tmp_path, "ana@icodev.com.br,,,,SP,Matriz SP,TI,Tecnologia,,,"), aplicar=True
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
    importar(csv_em(tmp_path, "ana@icodev.com.br,,,,,Campinas,,Financeiro,,,"), aplicar=True)

    assert Unidade.objects.filter(codigo="CAMPINAS").exists()
    assert Departamento.objects.filter(codigo="FINANCEIRO").exists()


@pytest.mark.django_db
def test_reusa_estrutura_existente(tmp_path):
    f.unidade("SP", "Matriz SP")
    f.pessoa("ana")
    importar(csv_em(tmp_path, "ana@icodev.com.br,,,,SP,Outro nome,,,,,"), aplicar=True)

    assert Unidade.objects.count() == 1
    assert Unidade.objects.get().nome == "Matriz SP", "não sobrescreve o cadastrado"


@pytest.mark.django_db
def test_atualiza_quem_ja_tem_lotacao(tmp_path):
    ana = f.pessoa("ana")
    f.lotar(ana, cargo="Antigo")
    importar(csv_em(tmp_path, "ana@icodev.com.br,,,Novo,,,,,,,"), aplicar=True)

    assert Lotacao.objects.get().cargo == "Novo"
    assert Lotacao.objects.count() == 1, "atualiza, não duplica"


@pytest.mark.django_db
def test_reexecutavel_sem_duplicar(tmp_path):
    f.pessoa("ana")
    caminho = csv_em(tmp_path, "ana@icodev.com.br,,,Analista,,,,,,,")
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
            "ana@icodev.com.br,,,,,,,,gestor@icodev.com.br,,",       # referencia o gestor ANTES de ele existir na planilha
            "gestor@icodev.com.br,,,,,,,,,,",
        ),
        aplicar=True,
    )

    assert Lotacao.objects.get(user__email="ana@icodev.com.br").gestor.email == "gestor@icodev.com.br"


@pytest.mark.django_db
def test_hierarquia_de_tres_niveis_em_ordem_invertida(tmp_path):
    for n in ("base", "meio", "topo"):
        f.pessoa(n)
    importar(
        csv_em(
            tmp_path,
            "base@icodev.com.br,,,,,,,,meio@icodev.com.br,,",
            "meio@icodev.com.br,,,,,,,,topo@icodev.com.br,,",
            "topo@icodev.com.br,,,,,,,,,,",
        ),
        aplicar=True,
    )

    from identidade.services import liderados_recursivos

    topo = Lotacao.objects.get(user__email="topo@icodev.com.br").user
    assert len(liderados_recursivos(topo.pk)) == 2


# ── Erros ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_arquivo_inexistente():
    with pytest.raises(CommandError, match="não encontrado"):
        importar("/tmp/nao_existe_zzz.csv")


@pytest.mark.django_db
def test_csv_sem_coluna_email(tmp_path):
    caminho = tmp_path / "ruim.csv"
    caminho.write_text("nome,cargo\nAna,Analista\n", encoding="utf-8")
    with pytest.raises(CommandError, match="vazio ou sem coluna"):
        importar(str(caminho))


@pytest.mark.django_db
def test_email_inexistente_e_relatado_nao_silenciado(tmp_path):
    texto = importar(csv_em(tmp_path, "fantasma@icodev.com.br,,,,,,,,,,"), aplicar=True)
    assert "E-MAIL INEXISTENTE" in texto
    assert "fantasma" in texto
    assert Lotacao.objects.count() == 0


@pytest.mark.django_db
def test_gestor_inexistente_cria_lotacao_sem_gestor(tmp_path):
    """Melhor a lotação sem gestor que nenhuma lotação — e o relatório avisa."""
    f.pessoa("ana")
    texto = importar(csv_em(tmp_path, "ana@icodev.com.br,,,,,,,,fantasma@icodev.com.br,,"), aplicar=True)

    assert "GESTOR INEXISTENTE" in texto
    assert Lotacao.objects.get().gestor is None


@pytest.mark.django_db
def test_situacao_invalida_cai_para_ativo_e_avisa(tmp_path):
    f.pessoa("ana")
    texto = importar(csv_em(tmp_path, "ana@icodev.com.br,,,,,,,,,,aposentado"), aplicar=True)

    assert "SITUAÇÃO INVÁLIDA" in texto
    assert Lotacao.objects.get().situacao == Situacao.ATIVO


@pytest.mark.django_db
def test_situacao_valida_e_aceita(tmp_path):
    f.pessoa("ana")
    importar(csv_em(tmp_path, "ana@icodev.com.br,,,,,,,,,,ferias"), aplicar=True)
    assert Lotacao.objects.get().situacao == Situacao.FERIAS


@pytest.mark.django_db
def test_ciclo_reprova_a_importacao_toda(tmp_path):
    """Gravar metade e deixar o grafo inconsistente é pior que não gravar."""
    f.pessoa("a")
    f.pessoa("b")
    with pytest.raises(CommandError, match="reprovada"):
        importar(
            csv_em(tmp_path, "a@icodev.com.br,,,,,,,,b@icodev.com.br,,", "b@icodev.com.br,,,,,,,,a@icodev.com.br,,"),
            aplicar=True,
        )
    assert Lotacao.objects.exclude(gestor=None).count() == 0


@pytest.mark.django_db
def test_bom_de_verdade_com_bom_e_aceito(tmp_path):
    """CSV do Excel vem com BOM. Sem `utf-8-sig`, a primeira coluna vira
    `\\ufeffemail` e nada é encontrado."""
    caminho = tmp_path / "bom.csv"
    caminho.write_text(CABECALHO + "\nana@icodev.com.br,,,Analista,,,,,,,\n", encoding="utf-8-sig")
    f.pessoa("ana")
    importar(str(caminho), aplicar=True)
    assert Lotacao.objects.get().cargo == "Analista"


@pytest.mark.django_db
def test_linha_em_branco_e_ignorada(tmp_path):
    f.pessoa("ana")
    importar(csv_em(tmp_path, "ana@icodev.com.br,,,,,,,,,,", ",,,,,,,,,,"), aplicar=True)
    assert Lotacao.objects.count() == 1


@pytest.mark.django_db
def test_espacos_sao_removidos(tmp_path):
    f.pessoa("ana")
    importar(csv_em(tmp_path, "  ana@icodev.com.br  ,,, Analista ,,,,,,,"), aplicar=True)
    assert Lotacao.objects.get().cargo == "Analista"


@pytest.mark.django_db
def test_sem_criar_estrutura_nao_inventa_unidade(tmp_path):
    f.pessoa("ana")
    importar(
        csv_em(tmp_path, "ana@icodev.com.br,,,,SP,Matriz,,,,,"), aplicar=True, criar_estrutura=False
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
    def e(apelido):
        return f"{apelido}@icodev.com.br" if apelido else ""

    hierarquia = {e("ana"): e("gestor"), e("gestor"): e("diretor"), e("diretor"): ""}
    for linha in linhas:
        linha["gestor_email"] = hierarquia[linha["email"]]
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

    ana = Lotacao.objects.get(user__email="ana@icodev.com.br").user
    diretor = Lotacao.objects.get(user__email="diretor@icodev.com.br").user
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

    emails = {linha["email"] for linha in csv.DictReader(StringIO(exportar(com_lotacao=True)))}
    assert emails == {"com_lotacao@icodev.com.br"}


@pytest.mark.django_db
def test_simulacao_resolve_estrutura_sem_criar(tmp_path):
    """Na simulação a unidade é só consultada — o relatório mostra quais
    apareceriam, sem gravar nenhuma."""
    f.pessoa("ana")
    texto = importar(csv_em(tmp_path, "ana@icodev.com.br,,,,SP,Matriz,TI,Tecnologia,,,"))

    assert "unidades           1" in texto
    assert "departamentos      1" in texto
    assert Unidade.objects.count() == 0
    assert Departamento.objects.count() == 0


@pytest.mark.django_db
def test_simulacao_aproveita_estrutura_que_ja_existe(tmp_path):
    f.unidade("SP", "Matriz SP")
    f.departamento("TI", "Tecnologia")
    f.pessoa("ana")
    importar(csv_em(tmp_path, "ana@icodev.com.br,,,,SP,Matriz SP,TI,Tecnologia,,,"))
    assert Lotacao.objects.count() == 0


@pytest.mark.django_db
def test_sem_criar_estrutura_nao_inventa_departamento(tmp_path):
    f.pessoa("ana")
    importar(
        csv_em(tmp_path, "ana@icodev.com.br,,,,,,FIN,Financeiro,,,"),
        aplicar=True,
        criar_estrutura=False,
    )
    assert Departamento.objects.count() == 0
    assert Lotacao.objects.get().departamento is None


@pytest.mark.django_db
def test_gestor_de_linha_com_email_inexistente_e_ignorado(tmp_path):
    """A linha já foi relatada na passada 1; a passada 2 não pode explodir."""
    f.pessoa("gestor")
    texto = importar(
        csv_em(tmp_path, "fantasma@icodev.com.br,,,,,,,,gestor@icodev.com.br,,", "gestor@icodev.com.br,,,,,,,,,,"), aplicar=True
    )
    assert "E-MAIL INEXISTENTE" in texto
    assert Lotacao.objects.count() == 1


@pytest.mark.django_db
def test_relatorio_trunca_lista_longa_de_problemas(tmp_path):
    """Despejar 400 e-mails inexistentes no terminal esconde o resto do
    relatório — a informação útil sai da tela."""
    linhas = [f"fantasma{i}@icodev.com.br,,,,,,,,,," for i in range(14)]
    texto = importar(csv_em(tmp_path, *linhas), aplicar=True)

    assert "E-MAIL INEXISTENTE · 14" in texto
    assert "e 4 outros" in texto
