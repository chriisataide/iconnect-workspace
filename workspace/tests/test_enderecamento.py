"""O código da tela — o endereço que a empresa usa para conversar.

Três coisas são protegidas aqui, e a ordem é a da gravidade:

1. **Unicidade.** Dois lugares com o mesmo endereço deixam um deles
   inalcançável, em silêncio. A árvore do próprio benchmark tem `08.2.4` e
   `05.6` duas vezes — é o defeito natural desta ideia, e ele tem de reprovar
   na subida do processo, não em produção.
2. **A rota não decide permissão.** `/ir/` resolve e manda; quem decide é a
   tela. Um redirecionador que checasse acesso seria um segundo lugar onde
   "quem vê o quê" está escrito, ao lado de `pode()`.
3. **O cabeçalho não diverge do registro.** O código na tela é derivado, não
   escrito — e este arquivo é quem garante que continue assim.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from identidade.tests import fabricas as f
from workspace import enderecamento as end
from workspace.modulos import MODULOS

# ── Unicidade e formato ─────────────────────────────────────────────


@pytest.fixture
def registro_limpo():
    """Um registro isolado, devolvido ao fim.

    O registro é estado de PROCESSO, montado no `ready()`. Sem devolver, uma
    tela inventada aqui sobreviveria para os testes seguintes — e o próximo a
    falhar culparia a busca.
    """
    guardado = dict(end._telas)
    end.limpar()
    yield
    end.limpar()
    for tela in guardado.values():
        end.registrar_tela(tela)


def test_codigo_duplicado_explode_no_registro(registro_limpo):
    """O defeito do benchmark, reprovado antes de nascer.

    Não é `UNIQUE` de banco de propósito: um `UNIQUE` só reprova no `INSERT`, e
    aqui o código está no fonte — ele passaria pelo deploy inteiro. Reprovar no
    registro é reprovar na subida do processo.
    """
    end.registrar_tela(end.Tela("42", "Primeira", "workspace:home"))

    with pytest.raises(end.CodigoInvalido) as erro:
        end.registrar_tela(end.Tela("42", "Segunda", "workspace:meu_dia"))

    # A mensagem nomeia quem já ocupa o código: sem isso, quem recebe o erro
    # tem um número e nenhuma pista de onde procurar o outro.
    assert "Primeira" in str(erro.value)


def test_registrar_a_mesma_tela_duas_vezes_e_silencio(registro_limpo):
    """`ready()` pode rodar mais de uma vez conforme o servidor.

    Se a segunda passada reprovasse, o produto não subiria por causa de um
    código que ele mesmo acabou de gravar. O que reprova é código igual
    apontando para tela DIFERENTE, que é o defeito de verdade.
    """
    tela = end.Tela("42", "Primeira", "workspace:home")
    end.registrar_tela(tela)
    end.registrar_tela(end.Tela("42", "Primeira", "workspace:home"))

    assert end.por_codigo("42") == tela


def test_registrar_o_que_nao_e_tela_e_erro_de_tipo(registro_limpo):
    """Uma tupla ou um dicionário passariam pelas outras validações e quebrariam
    depois, no `reverse()` — longe de quem escreveu o registro."""
    with pytest.raises(TypeError):
        end.registrar_tela(("42", "Qualquer", "workspace:home"))


@pytest.mark.parametrize(
    ("tela", "faltando"),
    [
        (end.Tela("42", "", "workspace:home"), "nome"),
        (end.Tela("42", "Sem rota", ""), "url_name"),
    ],
)
def test_tela_sem_nome_ou_sem_rota_e_recusada(registro_limpo, tela, faltando):
    """Endereço sem nome é um número que ninguém sabe pronunciar; endereço sem
    rota é um número que não leva a lugar nenhum."""
    with pytest.raises(end.CodigoInvalido) as erro:
        end.registrar_tela(tela)

    assert faltando in str(erro.value)


def test_a_tela_se_apresenta_pelo_codigo_e_pelo_nome():
    """`str(tela)` aparece em mensagem de erro e em `shell` — "02.2 · Aprovações"
    responde as duas perguntas de quem está lendo."""
    assert str(end.Tela("02.2", "Aprovações", "workspace:aprovacoes")) == (
        "02.2 · Aprovações"
    )


@pytest.mark.parametrize("codigo", ["1", "002", "abc", "02.", ".02", "02.1.2.3", ""])
def test_codigo_fora_do_formato_e_recusado(registro_limpo, codigo):
    """Dois dígitos no primeiro nível, até dois níveis abaixo.

    `1` seria aceito hoje e obrigaria a renumerar os nove primeiros assuntos no
    dia em que existisse um décimo — e código que renumera deixa de ser
    endereço.
    """
    with pytest.raises(end.CodigoInvalido):
        end.registrar_tela(end.Tela(codigo, "Qualquer", "workspace:home"))


# ── O registro real, tal como o `ready()` monta ─────────────────────


def test_todo_codigo_registrado_resolve_para_uma_rota():
    """Código que aponta para rota inexistente é pior do que código nenhum.

    `Tela.url` engole `NoReverseMatch` de propósito — a busca faz `reverse()` a
    cada tecla digitada e não pode cair por causa de uma rota removida. O preço
    desse silêncio é este teste: é aqui que a inconsistência tem de aparecer.
    """
    orfas = [t.codigo for t in end.todas() if not t.url]
    assert not orfas, f"Códigos sem rota: {orfas}"


def test_nenhuma_tela_tem_dois_codigos():
    """O inverso da unicidade, e igualmente ruim.

    Dois códigos para o mesmo lugar fazem duas pessoas combinarem a mesma tela
    por números diferentes — e `por_caminho()`, que alimenta o cabeçalho,
    devolveria um deles sem critério.
    """
    caminhos = [t.url for t in end.todas()]
    repetidos = {c for c in caminhos if caminhos.count(c) > 1}
    assert not repetidos, f"Mais de um código para: {repetidos}"


def test_todo_modulo_com_porta_tem_codigo():
    """O tile da home e o endereço têm de ser a mesma verdade.

    O launcher já deriva os tiles de `MODULOS`. Um módulo que ganhasse página e
    não ganhasse código teria porta na home e nenhum endereço — e o
    `/ir/` não o alcançaria.
    """
    sem_codigo = [m.chave for m in MODULOS if m.url_name and not m.codigo]
    assert not sem_codigo, f"Módulos com página e sem código: {sem_codigo}"


def test_modulo_em_breve_nao_ganha_endereco(registro_limpo, monkeypatch):
    """Módulo sem página não tem lugar para onde mandar ninguém.

    Dar-lhe endereço produziria um `/ir/` que leva a lugar nenhum com cara de
    erro — pior do que o "em breve" honesto que a home já mostra. E não pode
    virar exceção na subida: um módulo marcado "em breve" é estado normal do
    produto, não defeito.
    """
    import workspace.modulos as mod
    from workspace.modulos import Modulo

    fantasma = Modulo(chave="futuro", codigo="88", nome="Futuro", descricao="", icone="grid")
    assert fantasma.url_name == "", "sem `dominios` e sem `rota` não há para onde ir"
    monkeypatch.setattr(mod, "MODULOS", (*mod.MODULOS, fantasma))

    end.semear()

    assert end.por_codigo("88") is None
    assert end.por_codigo("20") is not None, "os módulos de verdade continuam"


# ── `/ir/` ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_ir_para_o_codigo_leva_a_tela(client):
    resposta = client.get("/workspace/ir/02/")

    assert resposta.status_code == 302
    assert resposta.headers["Location"] == reverse("workspace:servicos")


@pytest.mark.django_db
def test_codigo_inexistente_e_404(client):
    """404 sobre o CÓDIGO, e responde igual para todo mundo.

    Não há o que inferir: a lista de códigos é vocabulário da empresa, como o
    organograma de departamentos. O que é privado é o conteúdo de cada tela, e
    disso quem cuida é a tela.
    """
    assert client.get("/workspace/ir/77/").status_code == 404
    assert client.get("/workspace/ir/nada/").status_code == 404


@pytest.mark.django_db
def test_ir_nao_decide_permissao_a_tela_decide(client):
    """O teste que mais protege esta onda.

    Quem não tem escopo em Indicadores recebe **403 da tela**, e não 404 aqui.
    A diferença é a garantia de que `/ir/` não virou um segundo lugar onde a
    autorização mora: se ele checasse acesso, o dia em que os dois discordassem
    o produto teria duas respostas para a mesma pergunta.

    E o 403 não pode carregar nada do conteúdo — redirecionar para uma tela e
    vazar um pedaço dela no erro seria trocar um problema por outro.
    """
    ana = f.pessoa("ana")
    f.lotar(ana)
    client.force_login(ana)

    redirecionamento = client.get("/workspace/ir/08/")
    assert redirecionamento.status_code == 302

    tela = client.get(redirecionamento.headers["Location"])
    assert tela.status_code == 403
    assert b"Por \xc3\xa1rea" not in tela.content


# ── O código no cabeçalho ───────────────────────────────────────────


@pytest.mark.django_db
def test_a_tela_mostra_o_proprio_codigo(client):
    conteudo = client.get(reverse("workspace:servicos")).content.decode()

    assert 'class="au-codigo"' in conteudo
    assert ">02</span>" in conteudo


@pytest.mark.django_db
def test_a_pagina_de_modulo_mostra_o_codigo_do_modulo(client):
    """A rota é parametrizada (`workspace:modulo` + `("rh",)`), e o código sai
    do caminho — que é o motivo de `por_caminho()` não casar por `url_name`."""
    conteudo = client.get(reverse("workspace:modulo", args=("rh",))).content.decode()

    assert ">20</span>" in conteudo


@pytest.mark.django_db
def test_rota_que_nao_e_lugar_nao_mostra_codigo(client):
    """Formulário de um item do catálogo é conteúdo, não destino.

    Dar endereço a ele encheria o registro de uma linha por item de catálogo, e
    o código deixaria de ser algo que se decora.
    """
    from workspace.models import GrupoCatalogo, ItemCatalogo

    ItemCatalogo.objects.create(
        chave="ferias", nome="Férias", grupo=GrupoCatalogo.TRABALHO,
        dominio="rh.ferias", prazo_prometido_dias=5,
        campos=[{"chave": "quando", "rotulo": "Quando", "obrigatorio": True}],
    )

    conteudo = client.get(reverse("workspace:pedir", args=("ferias",))).content.decode()

    assert 'class="au-codigo"' not in conteudo
