"""§27–31 — Universidade Corporativa: o que vence, e quem precisa saber antes.

## O que este módulo resolve

A empresa sabe quem fez o curso. Não sabe quem está prestes a **perder** a
habilitação — e é essa a pergunta cara: NR-35 vencida bloqueia despacho, e a
descoberta acontece hoje na portaria da obra, com o técnico já lá.

## As decisões que os testes travam

1. **Estado é derivado, nunca gravado.** Três dos cinco estados dependem do
   calendário: um estado guardado fica errado sozinho à meia-noite e só volta a
   acertar quando alguém roda alguma coisa.
2. **A validade é congelada na conclusão.** Se a empresa mudar a NR-35 de 2 para
   3 anos, quem concluiu antes continua vencendo pela regra do certificado dele.
3. **Três degraus e um crítico.** Um alerta só é fácil de perder num dia de
   folga; um por dia vira ruído e ensina a ignorar.
4. **Dois destinatários.** A pessoa agenda a reciclagem; quem responde descobre
   que ela não agendou. Avisar só a primeira faz o vencimento virar surpresa do
   time; só o segundo transforma o R.H. em secretária de agenda.
5. **Rodar todo dia sem virar spam.** É a exigência difícil — e a trava é o
   degrau em `origem_id`, que faz 30, 15, 7 e vencido serem quatro eventos
   distintos do mesmo vencimento.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from identidade.tests import fabricas as f
from workspace.models import Notificacao, TipoNotificacao
from workspace.models.habilitacao import (
    Curso,
    Matricula,
    SituacaoMatricula,
    TipoCurso,
)
from workspace.services import habilitacao as hab

pytestmark = pytest.mark.django_db


def hoje():
    return timezone.localdate()


@pytest.fixture
def cenario():
    gestor, ana = f.pessoa("gestor"), f.pessoa("ana")
    f.lotar(gestor)
    f.lotar(ana, gestor=gestor)
    nr35 = Curso.objects.create(
        codigo="nr-35", nome="NR-35", tipo=TipoCurso.NR,
        validade_meses=24, obrigatorio=True,
    )
    integracao = Curso.objects.create(
        codigo="integracao", nome="Integração", tipo=TipoCurso.INTEGRACAO,
        validade_meses=0,
    )
    return {"gestor": gestor, "ana": ana, "nr35": nr35, "integracao": integracao}


def matricular(cenario, curso="nr35", **extras):
    return Matricula.objects.create(pessoa=cenario["ana"], curso=cenario[curso], **extras)


def com_vencimento(cenario, dias, curso="nr35"):
    """Uma matrícula concluída que vence daqui a `dias` (negativo = venceu)."""
    m = matricular(cenario, curso)
    hab.concluir(m, em=hoje() - timedelta(days=30))
    Matricula.objects.filter(pk=m.pk).update(vence_em=hoje() + timedelta(days=dias))
    m.refresh_from_db()
    return m


# ── A validade e o vencimento ───────────────────────────────────────


def test_concluir_calcula_o_vencimento(cenario):
    m = matricular(cenario)

    hab.concluir(m, em=date(2026, 3, 10))

    assert m.vence_em == date(2028, 3, 10)
    assert m.percentual == 100


def test_curso_que_nao_vence_fica_sem_data(cenario):
    m = matricular(cenario, "integracao")

    hab.concluir(m, em=date(2026, 3, 10))

    assert m.vence_em is None
    assert m.dias_para_vencer is None


def test_o_vencimento_usa_aritmetica_de_mes(cenario):
    """24 meses a partir de 29/02 tem de cair em 28/02 — `timedelta(days=30*n)`
    acumularia erro e cairia em algum dia de janeiro."""
    m = matricular(cenario)

    hab.concluir(m, em=date(2028, 2, 29))

    assert m.vence_em == date(2030, 2, 28)


def test_mudar_a_validade_do_curso_nao_move_quem_ja_concluiu(cenario):
    """O certificado dele diz dois anos. Recalcular na leitura faria a empresa
    reescrever o passado toda vez que a política mudasse."""
    m = matricular(cenario)
    hab.concluir(m, em=date(2026, 3, 10))

    Curso.objects.filter(pk=cenario["nr35"].pk).update(validade_meses=36)
    m.refresh_from_db()

    assert m.vence_em == date(2028, 3, 10)


# ── Os cinco estados do §27 ─────────────────────────────────────────


def test_pendente(cenario):
    assert matricular(cenario).estado == "pendente"


def test_em_andamento(cenario):
    m = matricular(cenario, situacao=SituacaoMatricula.EM_ANDAMENTO, percentual=40)

    assert m.estado == "em_andamento"


def test_atrasado_quando_passou_do_prazo_sem_concluir(cenario):
    """Prazo é ANTES de fazer; validade é DEPOIS de feito. Confundir os dois é o
    erro clássico deste domínio."""
    m = matricular(cenario, prazo=hoje() - timedelta(days=3))

    assert m.estado == "atrasado"
    assert m.dias_de_atraso == 3


def test_concluido_dentro_da_validade(cenario):
    assert com_vencimento(cenario, 200).estado == "concluido"


def test_a_vencer_no_primeiro_degrau(cenario):
    """O limite da tela é o MESMO do primeiro alerta. Com dois números, a tela
    mostraria verde para quem já recebeu aviso amarelo."""
    assert com_vencimento(cenario, hab.PRIMEIRO_ALERTA).estado == "a_vencer"
    assert com_vencimento(cenario, hab.PRIMEIRO_ALERTA + 1, "integracao").estado != "a_vencer"


def test_vencido(cenario):
    m = com_vencimento(cenario, -12)

    assert m.estado == "vencido"
    assert m.vencido
    assert m.dias_vencido == 12


def test_dias_vencido_e_positivo(cenario):
    """"venceu há -12 dias" é o tipo de texto que passa em revisão e só é visto
    por quem está vencido."""
    assert com_vencimento(cenario, -12).dias_vencido == 12
    assert com_vencimento(cenario, 30, "integracao").dias_vencido == 0


def test_dispensado_nao_entra_em_pendencia(cenario):
    m = matricular(cenario, situacao=SituacaoMatricula.DISPENSADO)

    assert m.estado == "dispensado"
    assert m not in hab.pendencias_de(cenario["ana"])


def test_o_que_esta_em_dia_fica_fora_das_pendencias(cenario):
    """A diferença entre uma lista de tarefas e um extrato."""
    com_vencimento(cenario, 200)

    assert hab.pendencias_de(cenario["ana"]) == []


# ── Os degraus de alerta (§28) ──────────────────────────────────────


@pytest.mark.parametrize("dias,degrau", [(30, 30), (25, 30), (15, 15), (10, 15), (7, 7), (1, 7)])
def test_o_degrau_e_o_menor_prazo_que_ainda_alcanca(dias, degrau):
    """Quem está a 20 dias cai no degrau de 30, e só recebe o de 15 quando
    chegar lá. Sem isso, cada dia entre 30 e 0 seria um alerta."""
    assert hab._degrau(dias) == degrau


def test_alem_do_primeiro_degrau_nao_ha_alerta():
    assert hab._degrau(31) is None


def test_avisa_quem_esta_dentro_do_primeiro_degrau(cenario):
    com_vencimento(cenario, 20)

    avisos = hab.avisos_a_enviar()

    assert len(avisos) == 1
    assert not avisos[0].critico


def test_vencido_e_critico(cenario):
    com_vencimento(cenario, -5)

    aviso = hab.avisos_a_enviar()[0]

    assert aviso.critico
    assert aviso.dias == -5


def test_nao_avisa_quem_esta_longe_do_vencimento(cenario):
    com_vencimento(cenario, 200)

    assert hab.avisos_a_enviar() == []


def test_nao_avisa_curso_que_nao_vence(cenario):
    m = matricular(cenario, "integracao")
    hab.concluir(m)

    assert hab.avisos_a_enviar() == []


def test_nao_avisa_quem_nao_concluiu(cenario):
    """Quem não concluiu não tem habilitação para perder — a cobrança dele é
    pelo PRAZO, que é outra conversa."""
    matricular(cenario, prazo=hoje() - timedelta(days=30))

    assert hab.avisos_a_enviar() == []


# ── Os dois destinatários (§28, §31) ────────────────────────────────


def test_avisa_a_pessoa_e_quem_responde(cenario):
    com_vencimento(cenario, 5)

    pessoas, gestores = hab.enviar_avisos()

    assert (pessoas, gestores) == (1, 1)
    assert Notificacao.objects.filter(
        destinatario=cenario["ana"], tipo=TipoNotificacao.HABILITACAO_A_VENCER
    ).exists()
    assert Notificacao.objects.filter(
        destinatario=cenario["gestor"], tipo=TipoNotificacao.HABILITACAO_A_VENCER
    ).exists()


def test_o_aviso_ao_responsavel_diz_a_acao_recomendada(cenario):
    """"Fulano vence em 7 dias" sem dizer o que fazer é informação que o gestor
    arquiva. O §31 pede a ação, e ela muda quando já venceu."""
    com_vencimento(cenario, -3)
    hab.enviar_avisos()

    aviso = Notificacao.objects.get(destinatario=cenario["gestor"])
    assert "Retire a pessoa das atividades" in aviso.corpo


def test_a_acao_recomendada_de_quem_vai_vencer_e_agendar(cenario):
    com_vencimento(cenario, 7)
    hab.enviar_avisos()

    aviso = Notificacao.objects.get(destinatario=cenario["gestor"])
    assert "Reciclagem de NR" in aviso.corpo


def test_o_responsavel_explicito_vence_o_gestor_do_organograma(cenario):
    """NR de terceirizado responde a outro nome que não o gestor da lotação."""
    sesmt = f.pessoa("sesmt")
    f.lotar(sesmt)
    m = com_vencimento(cenario, 5)
    Matricula.objects.filter(pk=m.pk).update(responsavel=sesmt)

    hab.enviar_avisos()

    assert Notificacao.objects.filter(destinatario=sesmt).exists()
    assert not Notificacao.objects.filter(destinatario=cenario["gestor"]).exists()


def test_quem_e_o_proprio_responsavel_nao_recebe_duas_vezes(cenario):
    m = com_vencimento(cenario, 5)
    Matricula.objects.filter(pk=m.pk).update(responsavel=cenario["ana"])

    pessoas, gestores = hab.enviar_avisos()

    assert (pessoas, gestores) == (1, 0)


# ── Rodar todo dia sem virar spam ───────────────────────────────────


def test_rodar_duas_vezes_no_mesmo_dia_nao_repete(cenario):
    """A trava é a Central, que deduplica o NÃO LIDO. Sem ela, quem tem NR
    vencendo em 30 dias receberia o mesmo aviso trinta vezes — e a trigésima
    seria ignorada como as anteriores."""
    com_vencimento(cenario, 20)

    hab.enviar_avisos()
    hab.enviar_avisos()

    assert Notificacao.objects.filter(destinatario=cenario["ana"]).count() == 1


def test_o_degrau_seguinte_e_evento_novo(cenario):
    """Se a pessoa leu o aviso de 30 e o vencimento chegou a 7, o novo aviso TEM
    de chegar — é a outra metade da regra de dedupe."""
    m = com_vencimento(cenario, 20)
    hab.enviar_avisos()

    Matricula.objects.filter(pk=m.pk).update(vence_em=hoje() + timedelta(days=5))
    hab.enviar_avisos()

    assert Notificacao.objects.filter(destinatario=cenario["ana"]).count() == 2


def test_o_comando_simula_sem_enviar(cenario):
    from io import StringIO

    from django.core.management import call_command

    com_vencimento(cenario, -5)
    saida = StringIO()

    call_command("avisar_habilitacoes", stdout=saida)

    assert "SIMULAÇÃO" in saida.getvalue()
    assert not Notificacao.objects.exists()


def test_o_comando_envia_com_aplicar(cenario):
    from io import StringIO

    from django.core.management import call_command

    com_vencimento(cenario, -5)

    call_command("avisar_habilitacoes", "--aplicar", stdout=StringIO())

    assert Notificacao.objects.filter(destinatario=cenario["ana"]).exists()


# ── O painel (§30) ──────────────────────────────────────────────────


def test_o_panorama_conta_cada_estado(cenario):
    com_vencimento(cenario, -5)
    com_vencimento(cenario, 200, "integracao")
    outra = f.pessoa("bruno")
    f.lotar(outra)
    Matricula.objects.create(pessoa=outra, curso=cenario["nr35"])

    panorama = hab.panorama()

    assert panorama["total"] == 3
    assert panorama["contagem"]["vencido"] == 1
    assert panorama["contagem"]["concluido"] == 1
    assert panorama["contagem"]["pendente"] == 1


def test_a_conformidade_e_none_sem_matricula():
    """0% numa empresa sem cursos cadastrados é um número que faz alguém agir
    sobre nada."""
    assert hab.panorama()["conformidade"] is None


def test_a_conformidade_conta_dispensado_como_em_dia(cenario):
    com_vencimento(cenario, 200)
    outra = f.pessoa("bruno")
    f.lotar(outra)
    Matricula.objects.create(
        pessoa=outra, curso=cenario["nr35"], situacao=SituacaoMatricula.DISPENSADO
    )

    assert hab.panorama()["conformidade"] == 100


def test_por_pessoa_poe_quem_tem_problema_na_frente(cenario):
    """Uma lista alfabética de oitocentas pessoas esconde as seis que
    importam."""
    em_dia = f.pessoa("aaa")
    f.lotar(em_dia)
    m = Matricula.objects.create(pessoa=em_dia, curso=cenario["integracao"])
    hab.concluir(m)
    com_vencimento(cenario, -5)

    linhas = hab.por_pessoa()

    assert linhas[0]["pessoa"] == cenario["ana"]
    assert linhas[0]["vencidas"] == 1


# ── As telas ────────────────────────────────────────────────────────


def test_a_tela_do_colaborador_mostra_as_minhas(client, cenario):
    com_vencimento(cenario, -5)
    client.force_login(cenario["ana"])

    corpo = client.get(reverse("workspace:universidade")).content.decode()

    assert "NR-35" in corpo
    assert "Vencido" in corpo


def test_a_tela_do_colaborador_exige_sessao(client):
    resposta = client.get(reverse("workspace:universidade"))

    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/entrar/")


def test_o_painel_e_de_quem_responde_pela_conformidade(client, cenario):
    """403 e não painel zerado: uma tela de conformidade toda em zero para quem
    nunca vai ter dado faz a pessoa achar que a empresa está em dia."""
    client.force_login(cenario["ana"])

    assert client.get(reverse("workspace:universidade_painel")).status_code == 403


def test_quem_responde_pela_conformidade_ve_o_painel(client, cenario):
    """`hab.auditoria.ler` e não `hab.ler` — §48.

    O teste pedia `hab.ler.global` e passava, e o painel estava aberto para a
    empresa inteira: `hab.ler.proprio` está em AUTOATENDIMENTO, e "posso em
    geral?" é verdadeiro com escopo próprio. A permissão parecia específica do
    SESMT e não era.
    """
    f.atribuir(
        cenario["gestor"], f.papel("sesmt", ["hab.auditoria.ler"], escopo="global")
    )
    com_vencimento(cenario, -5)
    client.force_login(cenario["gestor"])

    resposta = client.get(reverse("workspace:universidade_painel"))

    assert resposta.status_code == 200
    assert "NR-35" in resposta.content.decode()


def test_o_trilho_conta_as_pendencias(client, cenario):
    com_vencimento(cenario, -5)
    client.force_login(cenario["ana"])

    corpo = client.get(reverse("workspace:servicos")).content.decode()

    assert reverse("workspace:universidade") in corpo


def test_uma_matricula_por_pessoa_e_curso(cenario):
    """A reciclagem ATUALIZA a mesma linha. Criar uma nova a cada ciclo faria a
    pessoa aparecer com três NR-35, duas vencidas, e o painel diria que ela está
    irregular quando está em dia."""
    from django.db import IntegrityError, transaction

    matricular(cenario)

    with pytest.raises(IntegrityError), transaction.atomic():
        matricular(cenario)


# ── As consultas do queryset ────────────────────────────────────────


def test_de_anonimo_nao_traz_nada(cenario):
    """Mesma regra do resto do produto: sem sessão, nada pessoal."""
    from django.contrib.auth.models import AnonymousUser

    matricular(cenario)

    assert not Matricula.objects.de(AnonymousUser()).exists()
    assert not Matricula.objects.de(None).exists()


def test_em_aberto_traz_pendente_e_em_andamento(cenario):
    matricular(cenario)
    outra = f.pessoa("bruno")
    f.lotar(outra)
    Matricula.objects.create(
        pessoa=outra, curso=cenario["nr35"], situacao=SituacaoMatricula.EM_ANDAMENTO
    )
    com_vencimento(cenario, 200, "integracao")

    assert Matricula.objects.em_aberto().count() == 2


def test_vencidas_e_a_vencer_como_consulta(cenario):
    """As duas existem como QUERYSET além da propriedade `estado`: o painel
    precisa contar sem carregar a empresa inteira."""
    com_vencimento(cenario, -5)
    outra = f.pessoa("bruno")
    f.lotar(outra)
    m = Matricula.objects.create(pessoa=outra, curso=cenario["nr35"])
    hab.concluir(m, em=hoje() - timedelta(days=30))
    Matricula.objects.filter(pk=m.pk).update(vence_em=hoje() + timedelta(days=10))

    assert Matricula.objects.vencidas().count() == 1
    assert Matricula.objects.a_vencer(30).count() == 1
    assert Matricula.objects.a_vencer(5).count() == 0


def test_concluido_exige_a_data(cenario):
    """Sem a data não há como calcular vencimento — e a matrícula ficaria
    "concluída" para sempre, sem nunca vencer."""
    from django.core.exceptions import ValidationError

    m = matricular(cenario, situacao=SituacaoMatricula.CONCLUIDO)

    with pytest.raises(ValidationError, match="data da conclusão"):
        m.full_clean(exclude=["responsavel"])


def test_os_modelos_se_descrevem_no_admin(cenario):
    m = matricular(cenario)

    assert str(cenario["nr35"]) == "NR-35"
    assert "NR-35" in str(m)


def test_curso_sabe_se_vence(cenario):
    assert cenario["nr35"].vence
    assert not cenario["integracao"].vence


# ── A semente de cursos ─────────────────────────────────────────────


def test_semear_cursos_cria_as_nrs():
    from io import StringIO

    from django.core.management import call_command

    call_command("semear_cursos", "--aplicar", stdout=StringIO())

    assert Curso.objects.filter(tipo=TipoCurso.NR).count() >= 3
    assert Curso.objects.get(codigo="integracao").validade_meses == 0


def test_semear_cursos_e_reexecutavel():
    from io import StringIO

    from django.core.management import call_command

    call_command("semear_cursos", "--aplicar", stdout=StringIO())
    antes = Curso.objects.count()
    saida = StringIO()

    call_command("semear_cursos", "--aplicar", stdout=saida)

    assert Curso.objects.count() == antes
    assert f"já existiam  {antes}" in saida.getvalue()


def test_semear_cursos_simula_sem_gravar():
    from io import StringIO

    from django.core.management import call_command

    saida = StringIO()
    call_command("semear_cursos", stdout=saida)

    assert "SIMULAÇÃO" in saida.getvalue()
    assert not Curso.objects.exists()


def test_matricular_sem_ninguem_lotado_avisa():
    from io import StringIO

    from django.core.management import call_command

    saida = StringIO()
    call_command("semear_cursos", "--aplicar", "--matricular", stdout=saida)

    assert "semear_perfis" in saida.getvalue()
    assert not Matricula.objects.exists()


def test_a_demonstracao_espalha_os_estados(cenario):
    """Saldos iguais esconderiam o que a tela precisa mostrar. As matrículas de
    demonstração cobrem vencido, a vencer e em dia de propósito."""
    from io import StringIO

    from django.core.management import call_command

    call_command("semear_cursos", "--aplicar", "--matricular", stdout=StringIO())

    estados = {m.estado for m in Matricula.objects.all()}
    assert "vencido" in estados
    assert "a_vencer" in estados
