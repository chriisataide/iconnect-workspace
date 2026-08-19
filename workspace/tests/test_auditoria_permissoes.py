"""§48 — a auditoria de permissões, executável.

Uma auditoria que vira documento envelhece na primeira semana. Esta é um teste:
ela roda no CI e falha quando alguém abre uma porta.

## A classe de defeito que ela existe para pegar

`AUTOATENDIMENTO` dá a TODO colaborador um punhado de permissões com escopo
`proprio` — `rh.ler.proprio`, `log.ler.proprio`, `hab.ler.proprio`. Elas estão
certas: são o que permite alguém ver as próprias férias, os próprios pedidos, as
próprias habilitações.

E `pode(pessoa, "log.ler")` **sem alvo** significa "posso em geral?", que é
verdadeiro para quem tem `log.ler.proprio`. Também está certo: é assim que a
tela "minhas solicitações" decide que pode ser aberta.

O defeito nasce ao juntar as duas coisas: usar `log.ler` ou `hab.ler` para
guardar uma tela que mostra dado de OUTRAS pessoas. A permissão parece
específica da área, o teste manual passa (quem testa tem o papel), e a tela fica
aberta para a empresa inteira.

Foi assim que dois vazamentos existiram ao mesmo tempo:

* **o estoque** (`log.ler`) — saldo de todas as unidades, razão e reversa;
* **o painel de conformidade da Universidade** (`hab.ler`) — a lista nominal de
  quem está com certificado vencido.

Os dois foram corrigidos. Este arquivo é o que impede o terceiro.
"""

from __future__ import annotations

import pytest

from identidade.papeis import AUTOATENDIMENTO, PAPEIS_V1
from identidade.services.autorizacao import pode
from identidade.tests import fabricas as f
from workspace.services import assistente as asst
from workspace.services import conteudo as cnt
from workspace.services import correspondencia as cor
from workspace.services import custodia as cst
from workspace.services import estoque as est
from workspace.services import frota as frt
from workspace.services import habilitacao as hab
from workspace.services import indicadores as ind
from workspace.services import marketing as mkt
from workspace.services import publicacao as pub

pytestmark = pytest.mark.django_db


#: Toda porta que mostra dado de TERCEIRO. `(nome, função de guarda)`.
#:
#: A lista é escrita à mão de propósito: descobri-la por introspecção acharia
#: também as portas de autoatendimento, e o teste passaria dizendo que está
#: tudo certo justamente por não ter olhado onde importa.
PORTAS_DE_TERCEIROS = (
    ("estoque · ler", est.pode_ler),
    ("estoque · movimentar", est.pode_movimentar),
    ("estoque · contar inventário", est.pode_contar),
    ("custódia · ler", cst.pode_ler),
    ("custódia · atribuir", cst.pode_atribuir),
    ("frota · ler", frt.pode_ler),
    ("frota · operar", frt.pode_operar),
    ("marketing · ler", mkt.pode_ler),
    ("marketing · operar", mkt.pode_operar),
    ("acervo · publicar", cnt.pode_publicar),
    ("comunicados · publicar", pub.pode_publicar),
    ("FAQ · manter", asst.pode_manter),
    ("indicadores", ind.tem_painel),
    ("universidade · painel", lambda p, cache=None: pode(p, hab.PERMISSAO_GERIR, cache=cache)),
    ("correspondência · fila", lambda p, cache=None: pode(p, cor.PERMISSAO_REGISTRAR, cache=cache)),
)

#: As permissões que cada porta consulta, na mesma ordem.
PERMISSOES_DE_PORTA = (
    est.PERMISSAO_LER,
    est.PERMISSAO_MOVIMENTAR,
    est.PERMISSAO_CONTAR,
    cst.PERMISSAO_LER,
    cst.PERMISSAO_ATRIBUIR,
    frt.PERMISSAO_LER,
    frt.PERMISSAO_OPERAR,
    mkt.PERMISSAO_LER,
    mkt.PERMISSAO_OPERAR,
    cnt.PERMISSAO_PUBLICAR,
    pub.PERMISSAO_PUBLICAR,
    asst.PERMISSAO_MANTER,
    ind.VER_TUDO,
    hab.PERMISSAO_GERIR,
    cor.PERMISSAO_REGISTRAR,
)


@pytest.fixture
def colaborador():
    """Uma pessoa com o papel padrão e nada mais.

    É o perfil da maioria absoluta da empresa, e o único que interessa aqui:
    se ele passa por uma porta de terceiros, todo mundo passa.
    """
    pessoa = f.pessoa("colaborador")
    f.lotar(pessoa)
    f.atribuir(
        pessoa, f.papel("colaborador", AUTOATENDIMENTO, escopo="proprio")
    )
    return pessoa


# ── A porta ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("nome,porta", PORTAS_DE_TERCEIROS, ids=[n for n, _ in PORTAS_DE_TERCEIROS])
def test_o_colaborador_comum_nao_passa_por_porta_de_terceiros(colaborador, nome, porta):
    """O teste que pegou os dois vazamentos. Ver o cabeçalho do arquivo."""
    assert not porta(colaborador), (
        f"{nome} está aberta para o colaborador comum — a permissão que ela "
        "consulta é satisfeita por AUTOATENDIMENTO."
    )


@pytest.mark.parametrize("permissao", PERMISSOES_DE_PORTA, ids=list(PERMISSOES_DE_PORTA))
def test_nenhuma_porta_de_terceiros_e_satisfeita_por_autoatendimento(permissao):
    """A versão ESTRUTURAL do teste acima, e a que explica o porquê.

    A de cima falha quando a porta abre; esta falha quando a permissão escolhida
    é do tipo errado — mesmo que, naquele instante, nenhum papel a conceda por
    acaso. É a que pega o defeito no commit em que ele é introduzido.
    """
    proibidas = {p.rsplit(".", 1)[0] for p in AUTOATENDIMENTO if p.endswith(".proprio")}

    assert permissao not in proibidas, (
        f"{permissao!r} tem forma `.proprio` em AUTOATENDIMENTO: usá-la para "
        "guardar uma tela de terceiros abre a tela para a empresa inteira."
    )


# ── A matriz ────────────────────────────────────────────────────────


def test_toda_permissao_pedida_existe_em_algum_papel():
    """Permissão que nenhum papel concede é uma tela que ninguém abre.

    Não dá erro em lugar nenhum: a pessoa certa clica, leva 403, e o suporte
    procura o defeito no código — quando o que falta é a permissão nunca ter
    entrado em papel nenhum.
    """
    concedidas = [p for papel in PAPEIS_V1 for p in papel["permissoes"]]

    orfas = [
        pedida
        for pedida in PERMISSOES_DE_PORTA
        if not any(
            c == pedida or c.startswith(f"{pedida}.") for c in concedidas
        )
    ]

    assert orfas == [], f"permissões que nenhum papel concede: {orfas}"


def test_nenhum_papel_usa_curinga():
    """`*` seria um admin paralelo, sem trilha."""
    for papel in PAPEIS_V1:
        assert "*" not in papel["permissoes"], papel["chave"]


def test_o_colaborador_padrao_so_tem_escopo_proprio():
    """O papel base não enxerga ninguém além de si — é o que faz o resto da
    matriz significar alguma coisa."""
    colaborador = next(p for p in PAPEIS_V1 if p["chave"] == "colaborador")

    fora_do_proprio = [
        p
        for p in colaborador["permissoes"]
        if not p.endswith(".proprio")
        # `ti.status.ler`, `doc.ler.publico` e `doc.sugerir` são informação
        # institucional: status de serviço, política publicada e o formulário de
        # sugestão. Nenhum deles é dado de outra pessoa.
        and p not in ("ti.status.ler", "doc.ler.publico", "doc.sugerir")
    ]

    assert fora_do_proprio == []


# ── O que a porta certa deixa passar ────────────────────────────────


def test_suprimentos_continua_entrando_no_estoque():
    """Fechar a porta errada não pode fechar a porta para quem trabalha nela."""
    almox = f.pessoa("almoxarife")
    f.lotar(almox)
    papel = next(p for p in PAPEIS_V1 if p["chave"] == "logistica")
    f.atribuir(almox, f.papel("logistica", papel["permissoes"], escopo="unidade"))

    assert est.pode_ler(almox)
    assert est.pode_movimentar(almox)
    assert cst.pode_ler(almox)
    assert frt.pode_ler(almox)


def test_compras_ve_o_estoque_sem_movimentar():
    """Comprar sem ver o saldo é comprar o que já existe na prateleira."""
    comprador = f.pessoa("comprador")
    f.lotar(comprador)
    papel = next(p for p in PAPEIS_V1 if p["chave"] == "compras")
    f.atribuir(comprador, f.papel("compras", papel["permissoes"], escopo="unidade"))

    assert est.pode_ler(comprador)
    assert not est.pode_movimentar(comprador)


def test_o_sesmt_continua_vendo_a_conformidade():
    sesmt = f.pessoa("sesmt")
    f.lotar(sesmt)
    papel = next(p for p in PAPEIS_V1 if p["chave"] == "sesmt")
    f.atribuir(sesmt, f.papel("sesmt", papel["permissoes"], escopo="global"))

    assert pode(sesmt, hab.PERMISSAO_GERIR)


def test_quem_responde_pela_empresa_ve_a_conformidade():
    """R.H. e Diretoria respondem pela conformidade numa auditoria — e a
    Diretoria é a única que libera exceção de certificação."""
    for chave in ("rh", "diretoria"):
        pessoa = f.pessoa(chave)
        f.lotar(pessoa)
        papel = next(p for p in PAPEIS_V1 if p["chave"] == chave)
        f.atribuir(pessoa, f.papel(chave, papel["permissoes"], escopo="global"))

        assert pode(pessoa, hab.PERMISSAO_GERIR), chave


# ── Segregação de função ────────────────────────────────────────────


def test_quem_conta_o_inventario_nao_movimenta_por_isso():
    """O controle interno mais básico de patrimônio: quem tira material da
    prateleira não deveria ser quem declara quanto sobrou."""
    contador = f.pessoa("contador")
    f.lotar(contador)
    f.atribuir(
        contador, f.papel("inv", ["log.inventario.contar.unidade"], escopo="unidade")
    )

    assert est.pode_contar(contador)
    assert not est.pode_movimentar(contador)


def test_ninguem_aprova_o_que_pede():
    """Quem pede não aprova, quem aprova não compra, quem compra não recebe."""
    compras = next(p for p in PAPEIS_V1 if p["chave"] == "compras")

    assert not any(p.startswith("com.aprovar") for p in compras["permissoes"])


def test_a_auditoria_e_somente_leitura():
    """O auditor pode ser externo — cliente auditando fornecedor."""
    papel = next(p for p in PAPEIS_V1 if p["chave"] == "auditoria")
    escrita = [
        p
        for p in papel["permissoes"]
        if any(
            verbo in p
            for verbo in ("aprovar", "publicar", "admin", "movimentar", "editar", "operar")
        )
    ]

    assert escrita == []
