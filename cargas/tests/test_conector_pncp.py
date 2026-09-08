"""O conector do PNCP — editais públicos com proposta aberta.

## Por que estes testes não tocam a rede

`coletar` e `normalizar` são separados justamente para isto: a fixture é a saída
de `coletar`, capturada de uma resposta REAL da API em 08/09/2026, e
`normalizar` é função pura em cima dela. Um teste que dependesse do portal
falharia por indisponibilidade do governo — e falharia sem dizer que foi por
isso.

## O que eles guardam

1. **A triagem.** É a única regra de negócio deste conector, e a que decide se o
   radar serve ou vira uma lista de merenda escolar. Medido: cerca de 1% dos
   editais abertos cita segurança.
2. **A pausa entre páginas.** Sete requisições em treze segundos devolvem 429.
   Um conector sem pausa é bloqueado na terceira página todo dia.
3. **Que ele não precisa de credencial.** É o único assim, e a tela 99 tem de
   dizer isso em vez de "não configurada".
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cargas.conectores.base import Janela
from cargas.conectores.pncp import ConectorPNCP, sem_acento

pytestmark = pytest.mark.django_db


def item(objeto: str, **extra) -> dict:
    """Um item no formato REAL da API, conferido contra a resposta de produção."""
    base = {
        "numeroControlePNCP": "00509968000148-1-004225/2025",
        "objetoCompra": objeto,
        "valorTotalEstimado": 5871050.16,
        "dataAberturaProposta": "2025-05-08T08:00:00",
        "dataEncerramentoProposta": "2026-09-23T09:00:00",
        "modalidadeNome": "Pregão - Eletrônico",
        "orgaoEntidade": {"razaoSocial": "Ministério da Fazenda"},
        "unidadeOrgao": {
            "ufSigla": "BA",
            "municipioNome": "Salvador",
            "nomeUnidade": "Superintendência Regional",
        },
        "linkSistemaOrigem": None,
    }
    base.update(extra)
    return {"uf": "BA", "item": base}


def normalizar(*objetos, **conf):
    conector = ConectorPNCP()
    for chave, valor in conf.items():
        setattr(type(conector), chave, property(lambda self, v=valor: v))
    return list(conector.normalizar(item(o) for o in objetos))


# ── A triagem ───────────────────────────────────────────────────────


def test_o_que_e_da_empresa_entra(settings):
    regs = list(
        ConectorPNCP().normalizar(
            [item("Contratação de empresa especializada em serviços de VIGILÂNCIA armada")]
        )
    )

    assert len(regs) == 1
    assert regs[0].entidade == "edital"
    assert regs[0].dados["termo_casado"] == "vigilancia"


def test_o_que_nao_e_da_empresa_fica_de_fora(settings):
    """Descartado na triagem NÃO é rejeitado.

    Rejeitado é linha que chegou torta e pede conserto na origem. Isto aqui é
    edital de merenda escolar, que está perfeito e não é da empresa — contá-lo
    como rejeitado encheria a tela 99 de um alarme que não pede ação nenhuma.
    """
    regs = list(
        ConectorPNCP().normalizar(
            [item("Registro de preço para aquisição de gêneros alimentícios")]
        )
    )

    assert regs == []


def test_a_triagem_ignora_acento_e_caixa(settings):
    """O objeto vem como o órgão escreveu — e órgão escreve em CAIXA ALTA."""
    assert sem_acento("VIGILÂNCIA Eletrônica") == "vigilancia eletronica"

    regs = list(ConectorPNCP().normalizar([item("SEGURANÇA PATRIMONIAL E VIGILÂNCIA")]))

    assert len(regs) == 1


def test_guarda_QUAL_termo_casou(settings):
    """`termo_casado` é o que permite podar a lista.

    A API não filtra por palavra, então a triagem é nossa e vai errar nas
    primeiras semanas. Sem este campo, "por que este edital entrou?" não tem
    resposta e a lista de termos nunca melhora.
    """
    settings.PNCP_TERMOS = ["cftv", "vigilancia"]

    regs = list(ConectorPNCP().normalizar([item("Instalação de sistema de CFTV")]))

    assert regs[0].dados["termo_casado"] == "cftv"


def test_o_termo_mais_especifico_vence(settings):
    """O PRIMEIRO que casa, e a ordem da lista é a ordem de especificidade.

    "Casou com quatro termos" não ajuda ninguém a podar a lista.
    """
    settings.PNCP_TERMOS = ["seguranca eletronica", "seguranca"]

    regs = list(ConectorPNCP().normalizar([item("Serviços de segurança eletrônica")]))

    assert regs[0].dados["termo_casado"] == "seguranca eletronica"


def test_a_lista_de_termos_sai_do_settings(settings):
    """Ela É o produto deste conector: decide o que aparece no radar, vai errar
    no começo, e ajustá-la não pode exigir um deploy."""
    settings.PNCP_TERMOS = ["drone"]

    assert list(ConectorPNCP().normalizar([item("Vigilância armada")])) == []
    assert len(list(ConectorPNCP().normalizar([item("Aquisição de drone")]))) == 1


# ── Os campos, contra a resposta real ───────────────────────────────


def test_os_campos_batem_com_o_que_a_api_devolve(settings):
    regs = list(ConectorPNCP().normalizar([item("Serviços de vigilância")]))
    dados = regs[0].dados

    assert regs[0].chave_externa == "00509968000148-1-004225/2025"
    assert dados["numero_controle"] == "00509968000148-1-004225/2025"
    assert dados["valor_estimado"] == Decimal("5871050.16")
    assert dados["uf"] == "BA"
    assert dados["municipio"] == "Salvador"
    assert dados["orgao"] == "Ministério da Fazenda"
    assert dados["modalidade"] == "Pregão - Eletrônico"
    # A razão de o radar existir.
    assert dados["encerramento_proposta"].date() == date(2026, 9, 23)


def test_a_data_vem_com_fuso(settings):
    """O PNCP não manda fuso. Um `datetime` ingênuo com `USE_TZ` ligado vira
    aviso do Django e, pior, hora errada num prazo contado em horas."""
    regs = list(ConectorPNCP().normalizar([item("Vigilância")]))

    assert regs[0].dados["encerramento_proposta"].tzinfo is not None


def test_item_sem_numero_de_controle_e_ignorado_e_nao_estoura(settings):
    """Sem chave externa não há idempotência: a linha entraria de novo a cada
    carga, e o radar acumularia o mesmo edital toda madrugada."""
    regs = list(
        ConectorPNCP().normalizar([item("Vigilância", numeroControlePNCP=None)])
    )

    assert regs == []


# ── O link ──────────────────────────────────────────────────────────


def test_usa_o_link_da_origem_quando_ele_vem(settings):
    regs = list(
        ConectorPNCP().normalizar(
            [item("Vigilância", linkSistemaOrigem="https://comprasnet.gov.br/x")]
        )
    )

    assert regs[0].dados["link"] == "https://comprasnet.gov.br/x"


def test_monta_o_link_quando_a_origem_vem_nula(settings):
    """`linkSistemaOrigem` veio NULO no primeiro item conferido."""
    regs = list(ConectorPNCP().normalizar([item("Vigilância")]))

    assert regs[0].dados["link"] == (
        "https://pncp.gov.br/app/editais/00509968000148/2025/4225"
    )


def test_numero_em_formato_estranho_nao_vira_link_quebrado(settings):
    """Link quebrado numa tela de oportunidade é PIOR que a ausência dele: a
    pessoa clica, cai em 404 e conclui que o edital não existe mais."""
    regs = list(
        ConectorPNCP().normalizar([item("Vigilância", numeroControlePNCP="ABC-XYZ")])
    )

    assert regs[0].dados["link"] == ""


# ── Rede: a pausa e a paginação ─────────────────────────────────────


def test_descansa_entre_as_paginas(monkeypatch, settings):
    """Sete requisições em treze segundos → HTTP 429, medido contra a API de
    produção. Sem pausa, a carga é bloqueada na terceira página todo dia."""
    settings.PNCP_UFS = ["BA"]
    conector = ConectorPNCP()
    pausas, pedidos = [], []

    def falso_pedir(url, **kwargs):
        pedidos.append(url)
        return {"data": [item("Vigilância")["item"]], "totalPaginas": 3}

    monkeypatch.setattr("cargas.conectores.pncp.pedir", falso_pedir)
    monkeypatch.setattr(
        ConectorPNCP, "_descansar", lambda self: pausas.append(1)
    )

    list(conector.coletar(Janela()))

    assert len(pedidos) == 3
    assert len(pausas) == 2, "uma pausa entre páginas, e não depois da última"


def test_percorre_todas_as_ufs(monkeypatch, settings):
    settings.PNCP_UFS = None  # o padrão: as 27
    conector = ConectorPNCP()
    ufs = []

    def falso_pedir(url, **kwargs):
        ufs.append(url.split("uf=")[1].split("&")[0])
        return {"data": [], "totalPaginas": 1}

    monkeypatch.setattr("cargas.conectores.pncp.pedir", falso_pedir)
    monkeypatch.setattr(ConectorPNCP, "_descansar", lambda self: None)

    list(conector.coletar(Janela()))

    assert len(ufs) == 27
    assert set(ufs) == set(conector.ufs)


def test_a_janela_vira_o_horizonte_da_consulta(monkeypatch, settings):
    """`ate` vira `dataFinal`. `de` não tem uso: o endpoint devolve o que está
    aberto AGORA, e "aberto desde" não é pergunta que ele responda."""
    settings.PNCP_UFS = ["BA"]
    urls = []

    def falso_pedir(url, **kwargs):
        urls.append(url)
        return {"data": [], "totalPaginas": 1}

    monkeypatch.setattr("cargas.conectores.pncp.pedir", falso_pedir)
    monkeypatch.setattr(ConectorPNCP, "_descansar", lambda self: None)

    list(ConectorPNCP().coletar(Janela(de=date(2026, 1, 1), ate=date(2026, 12, 31))))

    assert "dataFinal=20261231" in urls[0]


# ── A fonte pública ─────────────────────────────────────────────────


def test_esta_sempre_disponivel_porque_nao_exige_nada(settings):
    """O único conector assim, e a razão é a fonte ser pública.

    Conferido contra a API em 08/09/2026: a especificação DECLARA um
    `bearerAuth`, mas uma chamada sem cabeçalho nenhum responde 400 de validação
    de parâmetro — e não 401. O `bearerAuth` é das APIs de manutenção.

    `disponivel()` responde "este ambiente tem o que a fonte exige". Devolver
    `False` por precaução faria a tela 99 dizer "não configurada" sobre a única
    fonte que não tem o que configurar.
    """
    assert ConectorPNCP().disponivel() is True


# ── Do bruto ao espelho, e do espelho à tela ────────────────────────


def test_a_carga_grava_no_espelho_com_procedencia(monkeypatch, settings, fontes):
    """O caminho inteiro, sem rede: `coletar` falso → carregador → espelho.

    O que este teste prova é que o conector NOVO ganha de graça tudo o que os
    quatro anteriores já tinham — idempotência, contagem, carimbo e
    procedência. Se ele precisasse de código próprio para isso, o desenho do
    carregador estaria errado.
    """
    from cargas.carregador import carregar
    from resultados.models import EditalPublico

    settings.PNCP_UFS = ["BA"]
    monkeypatch.setattr(ConectorPNCP, "_descansar", lambda self: None)
    monkeypatch.setattr(
        "cargas.conectores.pncp.pedir",
        lambda url, **k: {
            "data": [
                item("Serviços de vigilância armada")["item"],
                item("Aquisição de merenda escolar")["item"],
            ],
            "totalPaginas": 1,
        },
    )

    resultado = carregar("pncp", aplicar=True)

    assert resultado.status == "sucesso"
    edital = EditalPublico.objects.get()
    assert edital.fonte == "pncp"
    assert edital.chave_externa == "00509968000148-1-004225/2025"
    assert edital.termo_casado == "vigilancia"
    # A merenda entrou na coleta e NÃO virou linha: descartar na triagem não é
    # rejeitar. `rejeitados` conta linha torta, e essa estava perfeita.
    assert resultado.rejeitados == 0


def test_rodar_de_novo_nao_duplica(monkeypatch, settings, fontes):
    """Idempotência de graça — a mesma que os outros quatro têm."""
    from cargas.carregador import carregar
    from resultados.models import EditalPublico

    settings.PNCP_UFS = ["BA"]
    monkeypatch.setattr(ConectorPNCP, "_descansar", lambda self: None)
    monkeypatch.setattr(
        "cargas.conectores.pncp.pedir",
        lambda url, **k: {"data": [item("Vigilância")["item"]], "totalPaginas": 1},
    )

    carregar("pncp", aplicar=True)
    segunda = carregar("pncp", aplicar=True)

    assert EditalPublico.objects.count() == 1
    assert segunda.criados == 0
    assert segunda.ignorados == 1, "conteúdo idêntico não escreve"


def test_a_fonte_fora_do_ar_nao_derruba_nada(monkeypatch, settings, fontes):
    """Medido de verdade: durante esta implementação o PNCP ficou horas fora do
    ar, e a carga respondeu exatamente assim — falha limpa, frase para gente,
    zero linhas escritas."""
    from cargas.carregador import carregar
    from cargas.transporte import TransporteError
    from resultados.models import EditalPublico

    settings.PNCP_UFS = ["BA"]

    def cai(url, **k):
        raise TransporteError("pncp.gov.br não respondeu")

    monkeypatch.setattr("cargas.conectores.pncp.pedir", cai)

    resultado = carregar("pncp", aplicar=True)

    assert resultado.status == "falha"
    assert resultado.erro_resumo == "pncp.gov.br não respondeu"
    assert EditalPublico.objects.count() == 0
