"""O contrato de resultados, visto do lado do Workspace.

Este arquivo mora em `workspace/tests/` e não em `resultados/tests/` de
propósito: o que ele protege é a **superfície do contrato** — o que o Workspace
pode assumir sobre quem responde. Do lado do espelho, o teste é sobre a
implementação; daqui, é sobre a promessa.

A promessa tem três partes, e todas são decisões que já custaram caro em outros
lugares deste repositório:

1. **Sem provedor, degrada.** `obter()` devolve `None`, e a tela diz que a fonte
   não está conectada em vez de quebrar. É a mesma regra do `orcamento`.
2. **Implementação padrão vazia.** Quem responde só sobre projetos não escreve
   cinco `return []` para as perguntas que não são dele.
3. **DTO, e não model.** O que atravessa é dado, e não `objects`.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from workspace.providers import resultados as contrato


@pytest.fixture
def registro_limpo():
    """O registro isolado, devolvido ao fim.

    É estado de PROCESSO: `resultados` se registra no `ready()`, e sem devolver
    o que estava lá, todo teste seguinte que consultasse o espelho encontraria o
    contrato vazio — e culparia o app errado.
    """
    guardados = dict(contrato._provedores)
    contrato.limpar()
    yield
    contrato.limpar()
    contrato._provedores.update(guardados)


# ── O registro ──────────────────────────────────────────────────────


def test_sem_provedor_registrado_a_resposta_e_none(registro_limpo):
    """`None` é estado NORMAL, e não erro.

    Sem o app de espelho instalado, a tela diz "a fonte não está conectada" em
    vez de estourar. É a degradação que o `orcamento` já pratica, e a razão de a
    instalação sem integração continuar sendo uma instalação válida.
    """
    assert contrato.obter(contrato.ProvedorCarteira) is None


def test_um_provedor_atende_a_todos_os_contratos_que_implementa(registro_limpo):
    """Seis pares `registrar_x`/`obter_x` seriam doze funções para uma
    implementação só. Quem herda de três ABCs se registra uma vez."""

    class Tres(contrato.ProvedorCarteira, contrato.ProvedorProjetos):
        pass

    provedor = Tres()
    contrato.registrar(provedor)

    assert contrato.obter(contrato.ProvedorCarteira) is provedor
    assert contrato.obter(contrato.ProvedorProjetos) is provedor
    assert contrato.obter(contrato.ProvedorJornada) is None


def test_quem_nao_implementa_nada_e_recusado_na_hora(registro_limpo):
    """Quase sempre é herança esquecida.

    Sem esta checagem, o sintoma seria "a faixa está vazia" numa tela, semanas
    depois — e ninguém liga uma coisa à outra.
    """
    with pytest.raises(TypeError, match="não implementa nenhum contrato"):
        contrato.registrar(object())


# ── As implementações padrão ────────────────────────────────────────


def test_os_contratos_nascem_respondendo_vazio():
    """Um domínio implementa só o que oferece.

    Se todos os métodos fossem abstratos, quem só responde sobre projetos seria
    obrigado a escrever cinco `return []` — e o quinto viraria `return None` por
    descuido, num método que a tela itera.
    """
    hoje = timezone.localdate()

    class Mudo(
        contrato.ProvedorResultadoFinanceiro,
        contrato.ProvedorCarteira,
        contrato.ProvedorProjetos,
        contrato.ProvedorPessoas,
        contrato.ProvedorJornada,
        contrato.ProvedorSatisfacao,
    ):
        pass

    m = Mudo()

    assert m.serie_competencia(None, hoje, hoje) == []
    assert m.consolidado(None, hoje) is None
    assert m.contratos(None) == []
    assert m.vencimentos(None, 30) == []
    assert m.movimentacoes(None, hoje, hoje).conquistas == []
    assert m.projetos(None) == []
    assert m.marcos_em_risco(None, 15) == []
    assert m.quadro(None, hoje) is None
    assert m.movimentacao(None, hoje, hoje).admissoes == 0
    assert m.apontamentos(None, hoje) is None
    assert m.avaliacoes(None, hoje, hoje) == []


# ── Os DTOs ─────────────────────────────────────────────────────────


def test_a_procedencia_se_apresenta_com_a_chave_de_origem():
    """`sankhya:K-1042-08` é o que torna "de onde vem esse número" acionável:
    com a chave dá para abrir o ERP e conferir a linha."""
    com_chave = contrato.Procedencia(fonte="sankhya", chave_externa="K-1042-08")
    sem_chave = contrato.Procedencia(fonte="monday")

    assert str(com_chave) == "sankhya:K-1042-08"
    assert str(sem_chave) == "monday"


def test_sem_orcado_e_diferente_de_orcado_zero():
    """A faixa financeira marca a linha como "sem orçado" em vez de mostrar
    variação de 100% — que é o que uma conciliação de centro de custo quebrada
    produz, e parece estouro de orçamento sem ser."""
    proc = contrato.Procedencia(fonte="sankhya")
    sem = contrato.CompetenciaDTO(procedencia=proc)
    com_zero = contrato.CompetenciaDTO(procedencia=proc, receita_orcada=Decimal("0"))

    assert sem.tem_orcado is False
    assert com_zero.tem_orcado is True


def test_deficitario_e_margem_negativa_e_nao_margem_desconhecida():
    """`None` quer dizer "não dá para saber" — contrato sem receita na janela.

    Tratá-lo como deficitário poria no bloco mais visível da tela justamente
    quem ainda não tem número.
    """
    proc = contrato.Procedencia(fonte="sankhya")

    assert contrato.ContratoDTO(procedencia=proc, margem_contribuicao_pct=None).deficitario is False
    assert contrato.ContratoDTO(procedencia=proc, margem_contribuicao_pct=Decimal("0")).deficitario is False
    assert contrato.ContratoDTO(procedencia=proc, margem_contribuicao_pct=Decimal("-1")).deficitario is True


def test_marco_vencido_olha_o_relogio_e_nao_um_campo():
    proc = contrato.Procedencia(fonte="monday")
    hoje = timezone.localdate()

    vencido = contrato.MarcoDTO(procedencia=proc, prazo=hoje - timedelta(days=1))
    no_prazo = contrato.MarcoDTO(procedencia=proc, prazo=hoje + timedelta(days=1))
    entregue = contrato.MarcoDTO(
        procedencia=proc, prazo=hoje - timedelta(days=1), concluido_em=hoje
    )
    sem_prazo = contrato.MarcoDTO(procedencia=proc)

    assert vencido.vencido is True
    assert no_prazo.vencido is False
    assert entregue.vencido is False
    assert sem_prazo.vencido is False


def test_detrator_sem_tratativa_e_o_que_vira_destaque():
    """Detrator COM tratativa é trabalho em andamento; sem, é uma pessoa
    esperando. Só o segundo vira destaque na faixa de satisfação."""
    proc = contrato.Procedencia(fonte="iconnect_platform")

    solto = contrato.AvaliacaoDTO(procedencia=proc, classificacao="detrator")
    tratado = contrato.AvaliacaoDTO(
        procedencia=proc, classificacao="detrator", tratativa_aberta=True
    )
    promotor = contrato.AvaliacaoDTO(procedencia=proc, classificacao="promotor")

    assert solto.detrator_sem_tratativa is True
    assert tratado.detrator_sem_tratativa is False
    assert promotor.detrator_sem_tratativa is False


def test_escopo_vazio_quer_dizer_a_empresa_inteira():
    """E quem monta o escopo é a VIEW, a partir do que `pode()` responde.

    Se o provedor decidisse alcance, existiriam dois lugares onde "quem vê o
    quê" está escrito — e o espelho passaria a ter opinião sobre organograma.
    """
    assert contrato.Escopo().tudo is True
    assert contrato.Escopo(regionais=("Sul",)).tudo is False


def test_o_contrato_nao_expoe_model_nenhum():
    """O que atravessa é DTO.

    Devolver o model faria a tela depender do schema do espelho — e traria
    junto `hash_conteudo`, `carga_id` e `chave_externa`, mecânica de ingestão
    que apareceria no `dir()` de quem estivesse escrevendo a view.
    """
    import dataclasses

    for nome in dir(contrato):
        objeto = getattr(contrato, nome)
        if dataclasses.is_dataclass(objeto) and isinstance(objeto, type):
            assert not hasattr(objeto, "objects"), f"{nome} parece um model"
