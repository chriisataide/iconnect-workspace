"""Os públicos da marca — três públicos, três produtos, uma marca.

Os três que mais protegem esta onda:

1. **Destino não configurado não aparece — e não aparece como "em breve".**
   "Em breve" é uma promessa, e ninguém decidiu que o ADB Cliente vai existir.
2. **Público externo não aponta para dentro deste produto.** Um
   `ADB_CLIENTE_URL=/workspace/` mandaria clientes para o portal do funcionário,
   com a tela de entrar confirmando a eles que é o lugar certo.
3. **Quem errou a porta encontra a certa na tela de entrar.** É o único ponto do
   produto onde cliente e fornecedor aparecem.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from workspace import launcher, publicos

pytestmark = pytest.mark.django_db


@pytest.fixture
def registro_limpo():
    """O registro isolado, devolvido ao fim.

    É estado de PROCESSO: `publicos.semear()` roda no `ready()`, e sem devolver
    o que estava lá, todo teste seguinte leria um registro vazio — e culparia o
    código errado.
    """
    guardados = dict(publicos._publicos)
    publicos.limpar()
    yield
    publicos.limpar()
    publicos._publicos.update(guardados)


def _externo(chave="cliente", url="https://cliente.autodefesabrasil.com.br/"):
    return publicos.Publico(
        chave=chave, nome=f"ADB {chave.title()}", descricao="…", url=url
    )


# ── 1. Vazio quer dizer ausente ─────────────────────────────────────


def test_destino_nao_configurado_nao_aparece_nem_como_em_breve(registro_limpo):
    """O teste que separa esta onda de um módulo de roadmap.

    `AppSpec` sem rota vira "em breve", e está certo para um módulo que alguém
    decidiu construir. Para o ADB Cliente está errado: ninguém decidiu.
    """
    publicos.registrar(publicos.Publico(chave="cliente", nome="ADB Cliente",
                                        descricao="…", url=""))

    assert publicos.de("cliente").disponivel is False
    assert publicos.externos() == []
    assert publicos.disponiveis() == []
    # E o registro guarda o público mesmo assim: a decisão de NÃO existir é
    # informação, e some se ele não estiver em lugar nenhum.
    assert [p.chave for p in publicos.todos()] == ["cliente"]


def test_o_publico_deste_produto_esta_sempre_disponivel(registro_limpo):
    publicos.semear()

    interno = publicos.de(publicos.INTERNO)
    assert interno.interno is True
    assert interno.disponivel is True
    assert interno.nome == "Portal ADB"


def test_o_interno_nao_tem_url_propria(registro_limpo):
    """Uma URL aqui criaria um link do produto para si mesmo numa lista cujo
    propósito é dizer "sua entrada é outra"."""
    with pytest.raises(publicos.PublicoInvalido, match="não tem URL própria"):
        publicos.registrar(
            publicos.Publico(
                chave="colaborador", nome="Portal ADB", descricao="…",
                url="https://portal.autodefesabrasil.com.br/", interno=True,
            )
        )


def test_o_estado_de_hoje_e_nenhum_externo(registro_limpo, settings):
    """Nem o ADB Cliente nem o ADB Fornecedor existem. O produto não promete que
    vão existir."""
    settings.ADB_CLIENTE_URL = ""
    settings.ADB_FORNECEDOR_URL = ""

    publicos.semear()

    assert publicos.externos() == []
    assert len(publicos.todos()) == 3, "os três estão registrados"


# ── 2. Externo não aponta para dentro ───────────────────────────────


def test_publico_externo_nao_aponta_para_dentro_deste_produto(
    registro_limpo, settings
):
    """O guard que vale mais que o resto do módulo.

    Um endereço que caia num host de `ALLOWED_HOSTS` manda cliente para o portal
    do funcionário — e a tela de entrar confirma a ele que é o lugar certo.
    """
    settings.ALLOWED_HOSTS = ["portal.autodefesabrasil.com.br", "localhost"]

    with pytest.raises(publicos.PublicoInvalido, match="aponta para este próprio"):
        publicos.registrar(_externo(url="https://portal.autodefesabrasil.com.br/x/"))


def test_caminho_relativo_e_recusado(registro_limpo):
    """`/workspace/` não sai de lugar nenhum — é o erro de configuração que este
    módulo existe para pegar."""
    for url in ("/workspace/", "workspace/", "//evil.example.com/"):
        with pytest.raises(publicos.PublicoInvalido, match="não é um endereço absoluto"):
            publicos.registrar(_externo(url=url))


def test_esquema_estranho_e_recusado(registro_limpo):
    """`javascript:` e `file:` num `href` renderizado na tela de login são o pior
    lugar possível para um endereço não conferido."""
    for url in ("javascript:alert(1)", "file:///etc/passwd", "ftp://x.example.com/"):
        with pytest.raises(publicos.PublicoInvalido):
            publicos.registrar(_externo(url=url))


def test_o_curinga_de_allowed_hosts_nao_torna_tudo_interno(registro_limpo, settings):
    """`*` é de desenvolvimento. Se ele casasse, nenhum público externo poderia
    ser configurado numa máquina de desenvolvimento — e o defeito só apareceria
    em produção, ao contrário."""
    settings.ALLOWED_HOSTS = ["*"]

    publicos.registrar(_externo())

    assert publicos.de("cliente").disponivel is True


def test_subdominio_de_allowed_hosts_com_ponto_tambem_e_interno(
    registro_limpo, settings
):
    """`.exemplo.com` em `ALLOWED_HOSTS` quer dizer o domínio e os filhos."""
    settings.ALLOWED_HOSTS = ["portal.adb.com.br"]

    with pytest.raises(publicos.PublicoInvalido):
        publicos.registrar(_externo(url="https://portal.adb.com.br/"))

    publicos.registrar(_externo(chave="fornecedor", url="https://fornecedor.adb.com.br/"))
    assert publicos.de("fornecedor").disponivel is True


def test_quem_nao_e_publico_e_recusado(registro_limpo):
    with pytest.raises(TypeError, match="não é um Publico"):
        publicos.registrar({"chave": "cliente"})


def test_publico_sem_chave_e_recusado(registro_limpo):
    with pytest.raises(publicos.PublicoInvalido, match="precisa de `chave`"):
        publicos.registrar(publicos.Publico(chave="", nome="x", descricao="y"))


def test_a_configuracao_errada_derruba_a_subida_do_processo(registro_limpo, settings):
    """Recusar na subida e não no clique: erro de configuração é barato enquanto
    o processo não subiu, e caro quando um cliente já está na tela."""
    settings.ADB_CLIENTE_URL = "/workspace/"

    with pytest.raises(publicos.PublicoInvalido):
        publicos.semear()


# ── 3. O roteamento na tela de entrar ───────────────────────────────


def test_quem_errou_a_porta_encontra_a_certa_na_tela_de_entrar(
    registro_limpo, client
):
    """É o único ponto do produto onde cliente e fornecedor aparecem. Sem estas
    linhas, a pessoa tenta a senha três vezes e abre um chamado."""
    publicos.registrar(publicos.Publico(chave="colaborador", nome="Portal ADB",
                                        descricao="…", interno=True))
    publicos.registrar(_externo())

    conteudo = client.get(reverse("entrar")).content.decode()

    assert "Você é cliente ou fornecedor?" in conteudo
    assert "https://cliente.autodefesabrasil.com.br/" in conteudo
    assert "Sua entrada é outra" in conteudo


def test_sem_destino_configurado_a_tela_de_entrar_nao_desenha_a_secao(
    registro_limpo, client
):
    """Uma lista vazia não vira uma seção vazia — restrição 6, pelo avesso: o
    estado vazio aqui é a ausência, e não um texto explicando o vazio."""
    publicos.semear()

    conteudo = client.get(reverse("entrar")).content.decode()

    assert "Você é cliente ou fornecedor?" not in conteudo
    assert "au-porta-publicos" not in conteudo


def test_o_portal_do_colaborador_nao_se_lista_na_propria_porta(
    registro_limpo, client
):
    """Dizer a quem já está aqui que a entrada dele é aqui não ajuda ninguém."""
    publicos.semear()
    publicos.registrar(_externo())

    conteudo = client.get(reverse("entrar")).content.decode()

    assert "ADB Cliente" in conteudo
    assert "Portal ADB" not in conteudo


# ── O tile ──────────────────────────────────────────────────────────


def test_o_publico_configurado_vira_tile_no_launcher(registro_limpo):
    """Um tile e não um módulo — foi o que o benchmark previu."""
    publicos.registrar(_externo())

    tiles = {spec.chave: spec for spec in launcher.catalogo_semente()}

    assert "publico-cliente" in tiles
    assert tiles["publico-cliente"].url_direta == "https://cliente.autodefesabrasil.com.br/"
    assert tiles["publico-cliente"].disponivel is True


def test_publico_sem_endereco_nao_vira_tile(registro_limpo):
    publicos.semear()

    chaves = {spec.chave for spec in launcher.catalogo_semente()}

    assert not any(c.startswith("publico-") for c in chaves)


def test_o_publico_interno_nao_vira_tile(registro_limpo):
    """Um tile para este produto, dentro deste produto, é um link para onde a
    pessoa já está."""
    publicos.semear()
    publicos.registrar(_externo())

    chaves = {spec.chave for spec in launcher.catalogo_semente()}

    assert "publico-cliente" in chaves
    assert "publico-colaborador" not in chaves


def test_o_tile_de_publico_sai_deste_produto(registro_limpo):
    """`url_direta` e nunca `url_name`: a rota deste produto não leva ao produto
    de outro público — é o mesmo cuidado do tile do iConnect."""
    publicos.registrar(_externo())

    tile = next(
        s for s in launcher.catalogo_semente() if s.chave == "publico-cliente"
    )

    assert tile.url_name is None
    assert tile.url_direta.startswith("https://")


# ── A ordenação e as bordas ─────────────────────────────────────────


def test_o_interno_vem_primeiro_na_listagem(registro_limpo):
    publicos.semear()

    assert publicos.todos()[0].chave == publicos.INTERNO


def test_de_devolve_none_para_chave_desconhecida(registro_limpo):
    publicos.semear()

    assert publicos.de("investidor") is None


def test_o_registro_aceita_substituicao_pela_mesma_chave(registro_limpo):
    """Semear duas vezes não pode duplicar — e a segunda vence, como em todo
    registro em memória deste produto."""
    publicos.registrar(_externo(url="https://um.example.com/"))
    publicos.registrar(_externo(url="https://dois.example.com/"))

    assert len(publicos.todos()) == 1
    assert publicos.de("cliente").url == "https://dois.example.com/"


def test_semear_e_idempotente(registro_limpo, settings):
    settings.ADB_CLIENTE_URL = "https://cliente.example.com/"
    publicos.semear()
    publicos.semear()

    assert len(publicos.todos()) == 3
    assert len(publicos.externos()) == 1


def test_o_str_do_publico_e_o_nome(registro_limpo):
    """`__str__` aparece em mensagem de erro de configuração — e "Publico object"
    não diz a ninguém qual das duas variáveis está errada."""
    assert str(_externo()) == "ADB Cliente"


def test_url_sem_host_nao_e_considerada_interna(registro_limpo, settings):
    """`_aponta_para_dentro` só responde sobre endereço que TEM host. Sem isso,
    a checagem de "é absoluta?" e a de "aponta para dentro?" dariam respostas
    contraditórias sobre a mesma string."""
    settings.ALLOWED_HOSTS = ["portal.adb.com.br"]

    assert publicos._aponta_para_dentro("/workspace/") is False
    assert publicos._aponta_para_dentro("") is False
