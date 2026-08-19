"""HAB — o que vence, quem precisa saber, e quando avisar.

## O alerta é o produto

O cadastro de cursos é a parte fácil e a menos útil. O que a empresa não tem é a
resposta para "quem perde habilitação nos próximos 30 dias" — e a descoberta
acontece hoje na portaria da obra, com o técnico já lá.

## Três avisos e um crítico (§28)

30, 15 e 7 dias antes, e um quando vence. Os números são configuráveis em
`PRAZOS_DE_ALERTA`, e a escolha de TRÊS tem razão: um só é fácil de perder num
dia de folga; um por semana vira ruído e ensina a ignorar. Trinta dias é o tempo
de agendar uma reciclagem; sete é o tempo de correr.

## Idempotência é o requisito difícil

O alerta roda todo dia. Sem uma trava, quem tem NR vencendo em 30 dias receberia
o mesmo aviso trinta vezes — e a trigésima seria ignorada como as anteriores.

A trava é a Central de Notificações, que já deduplica o NÃO LIDO
(`notificacoes.criar`): o mesmo tipo, domínio e origem não repete enquanto a
pessoa não tiver lido. Isso resolve o repique diário sem tabela de controle
nova, e mantém a propriedade certa — se a pessoa LEU e o vencimento se aproximou
mais, o aviso do degrau seguinte é evento novo e deve chegar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.urls import reverse
from django.utils import timezone

from workspace.models.habilitacao import Curso, Matricula, SituacaoMatricula
from workspace.models.notificacao import TipoNotificacao

#: Quantos dias antes do vencimento cada aviso sai. Do mais distante ao mais
#: próximo — a ordem importa em `_degrau()`.
PRAZOS_DE_ALERTA = (30, 15, 7)

#: O primeiro degrau também define o que a tela chama de "próximo do
#: vencimento". Um número só para as duas coisas: com dois, a tela mostraria
#: verde para quem já recebeu aviso amarelo.
PRIMEIRO_ALERTA = PRAZOS_DE_ALERTA[0]

#: `hab.auditoria.ler` e NÃO `hab.ler` — §48.
#:
#: `hab.ler.proprio` está em `AUTOATENDIMENTO` para que cada pessoa veja as
#: PRÓPRIAS habilitações, e "posso em geral?" é verdadeiro com escopo próprio.
#: Guardando o painel de conformidade com ela, a lista NOMINAL de quem está com
#: certificado vencido ficava aberta para todo colaborador.
PERMISSAO_GERIR = "hab.auditoria.ler"


class HabilitacaoError(Exception):
    """A matrícula não pode ser gravada assim."""


# ── O que cada pessoa tem ───────────────────────────────────────────


def minhas(pessoa):
    """As matrículas de uma pessoa, o que vence primeiro na frente."""
    return Matricula.objects.de(pessoa).select_related("curso")


def pendencias_de(pessoa) -> list[Matricula]:
    """O que exige ação DESTA pessoa: em aberto, atrasado, vencido ou a vencer.

    O que está simplesmente em dia fica fora — é a diferença entre uma lista de
    tarefas e um extrato.
    """
    return [
        m
        for m in minhas(pessoa)
        if m.estado in ("pendente", "em_andamento", "atrasado", "vencido", "a_vencer")
    ]


# ── Concluir e reciclar ─────────────────────────────────────────────


def concluir(
    matricula: Matricula, em=None, certificado: str = "", quem=None
) -> Matricula:
    """Registra a conclusão e calcula o vencimento.

    O vencimento é calculado AQUI e gravado, em vez de derivado na leitura. Duas
    razões: responder "o que vence em 30 dias" vira uma consulta em vez de um
    laço sobre a empresa inteira; e a validade fica congelada na regra que valia
    no dia — se a empresa mudar a NR-35 de 2 para 3 anos, quem concluiu antes
    continua vencendo pela regra do certificado dele.
    """
    em = em or timezone.localdate()
    matricula.situacao = SituacaoMatricula.CONCLUIDO
    matricula.concluido_em = em
    matricula.percentual = 100
    matricula.certificado = certificado[:120] or matricula.certificado
    matricula.vence_em = _vencimento(matricula.curso, em)
    matricula.save(
        update_fields=[
            "situacao", "concluido_em", "percentual", "certificado", "vence_em",
            "atualizado_em",
        ]
    )
    return matricula


def _vencimento(curso: Curso, concluido_em):
    """A data em que a habilitação perde validade, ou `None`.

    Meses somados por aritmética de mês e não por `timedelta(days=30*n)`: 24
    meses a partir de 29/02 tem de cair em 28/02, não em algum dia de janeiro
    acumulado por arredondamento.
    """
    if not curso.vence:
        return None

    total = concluido_em.month - 1 + curso.validade_meses
    ano = concluido_em.year + total // 12
    mes = total % 12 + 1
    dia = min(concluido_em.day, _ultimo_dia(ano, mes))
    return concluido_em.replace(year=ano, month=mes, day=dia)


def _ultimo_dia(ano: int, mes: int) -> int:
    from calendar import monthrange

    return monthrange(ano, mes)[1]


# ── Os alertas (§28, §29, §31) ──────────────────────────────────────


@dataclass
class Aviso:
    """Um alerta a enviar. Separado do envio para poder ser TESTADO sem
    escrever notificação — e para o comando poder relatar antes de gravar."""

    matricula: Matricula
    dias: int
    critico: bool


def _degrau(dias: int) -> int | None:
    """Em qual degrau de alerta este vencimento cai, ou `None`.

    O degrau é o MENOR prazo que ainda alcança — quem está a 20 dias cai no
    degrau de 30, não no de 15, e só recebe o de 15 quando chegar lá. Sem isso,
    cada dia entre 30 e 0 seria um alerta.
    """
    for prazo in sorted(PRAZOS_DE_ALERTA):
        if dias <= prazo:
            return prazo
    return None


def avisos_a_enviar(em=None) -> list[Aviso]:
    """Tudo que merece alerta hoje — vencido e a vencer."""
    hoje = em or timezone.localdate()
    avisos = []

    for matricula in (
        Matricula.objects.concluidas()
        .filter(vence_em__isnull=False, vence_em__lte=hoje + timedelta(days=max(PRAZOS_DE_ALERTA)))
        .select_related("curso", "pessoa", "responsavel")
    ):
        dias = (matricula.vence_em - hoje).days
        if dias < 0:
            avisos.append(Aviso(matricula, dias, critico=True))
        elif _degrau(dias) is not None:
            avisos.append(Aviso(matricula, dias, critico=False))

    return avisos


def enviar_avisos(em=None) -> tuple[int, int]:
    """Avisa a PESSOA e quem responde por ela. Devolve `(pessoas, gestores)`.

    Dois destinatários e não um: a pessoa é quem agenda a reciclagem, e quem
    responde é quem descobre que ela não agendou. Avisar só a primeira faz o
    vencimento virar surpresa do time; avisar só o segundo transforma o R.H. em
    secretária de agenda de oitocentas pessoas.
    """
    from workspace.services import notificacoes as nt

    pessoas = gestores = 0
    for aviso in avisos_a_enviar(em):
        matricula = aviso.matricula
        titulo, corpo = _texto(aviso)

        nt.criar(
            destinatario=matricula.pessoa,
            tipo=TipoNotificacao.HABILITACAO_A_VENCER,
            titulo=titulo,
            corpo=corpo,
            url=reverse("workspace:universidade"),
            dominio="hab.matricula",
            # O DEGRAU entra na origem, e é o que faz o dedupe funcionar do
            # jeito certo: o aviso de 30 dias e o de 7 são eventos diferentes
            # do mesmo vencimento, e o segundo tem de chegar mesmo que o
            # primeiro ainda esteja por ler.
            origem_id=f"{matricula.pk}:{_degrau(aviso.dias) or 'vencido'}",
        )
        pessoas += 1

        responsavel = matricula.responsavel or _gestor_de(matricula.pessoa)
        if responsavel and responsavel.pk != matricula.pessoa_id:
            nt.criar(
                destinatario=responsavel,
                tipo=TipoNotificacao.HABILITACAO_A_VENCER,
                titulo=f"{matricula.pessoa.get_full_name()}: {titulo.lower()}",
                corpo=_texto_do_responsavel(aviso),
                url=reverse("workspace:universidade_painel"),
                dominio="hab.matricula",
                origem_id=f"{matricula.pk}:{_degrau(aviso.dias) or 'vencido'}:resp",
            )
            gestores += 1

    return pessoas, gestores


def _texto(aviso: Aviso) -> tuple[str, str]:
    curso = aviso.matricula.curso.nome
    if aviso.critico:
        return (
            f"{curso} está VENCIDO",
            f"Venceu há {abs(aviso.dias)} dia(s). Habilitação vencida bloqueia "
            "despacho — peça a reciclagem hoje.",
        )
    return (
        f"{curso} vence em {aviso.dias} dia(s)",
        "Peça a reciclagem antes do vencimento para não ficar sem habilitação.",
    )


def _texto_do_responsavel(aviso: Aviso) -> str:
    """A ação recomendada, que é o §31 inteiro.

    "Fulano vence em 7 dias" sem dizer o que fazer é informação que o gestor
    arquiva. A frase seguinte é a que transforma o aviso em ação.
    """
    quando = (
        f"venceu há {abs(aviso.dias)} dia(s)"
        if aviso.critico
        else f"vence em {aviso.dias} dia(s)"
    )
    acao = (
        "Retire a pessoa das atividades que exigem esta habilitação até a reciclagem."
        if aviso.critico
        else "Abra “Reciclagem de NR” no catálogo — o prazo prometido é de 10 dias."
    )
    return f"{aviso.matricula.curso.nome} {quando}. {acao}"


def _gestor_de(pessoa):
    from identidade.models import Lotacao

    lotacao = Lotacao.objects.filter(user=pessoa).select_related("gestor").first()
    return lotacao.gestor if lotacao else None


# ── O painel (§30) ──────────────────────────────────────────────────


def panorama(em=None) -> dict:
    """Os números do §30, numa passada por matrícula.

    Uma varredura em Python e não seis `count()`: os estados são derivados do
    calendário, e derivá-los em SQL exigiria repetir a regra de negócio dentro
    de cada consulta — seis lugares onde ela pode divergir da propriedade
    `estado`, que é a única que a tela mostra.
    """
    hoje = em or timezone.localdate()
    matriculas = list(
        Matricula.objects.select_related("curso", "pessoa").filter(curso__ativo=True)
    )

    contagem = {
        "concluido": 0, "a_vencer": 0, "vencido": 0,
        "pendente": 0, "em_andamento": 0, "atrasado": 0, "dispensado": 0,
    }
    for matricula in matriculas:
        contagem[matricula.estado] = contagem.get(matricula.estado, 0) + 1

    total = len(matriculas)
    em_dia = contagem["concluido"] + contagem["dispensado"]
    return {
        "total": total,
        "contagem": contagem,
        # A taxa que a diretoria pergunta. `None` e não 0 quando não há
        # matrícula: 0% de conformidade numa empresa sem cursos cadastrados é
        # um número que faz alguém agir sobre nada.
        "conformidade": round(em_dia * 100 / total) if total else None,
        "criticas": [m for m in matriculas if m.estado == "vencido"],
        "proximas": sorted(
            (m for m in matriculas if m.estado == "a_vencer"),
            key=lambda m: m.vence_em,
        ),
        "hoje": hoje,
    }


def por_pessoa(em=None) -> list[dict]:
    """O painel do R.H.: uma linha por pessoa, com o que está fora do prazo."""
    agrupado: dict[int, dict] = {}
    for matricula in (
        Matricula.objects.select_related("curso", "pessoa")
        .filter(curso__ativo=True)
        .order_by("pessoa__nome", "vence_em")
    ):
        linha = agrupado.setdefault(
            matricula.pessoa_id,
            {"pessoa": matricula.pessoa, "matriculas": [], "vencidas": 0, "a_vencer": 0},
        )
        linha["matriculas"].append(matricula)
        if matricula.estado == "vencido":
            linha["vencidas"] += 1
        elif matricula.estado == "a_vencer":
            linha["a_vencer"] += 1

    # Quem tem problema primeiro. Ordem alfabética faria a lista de oitocentas
    # pessoas esconder as seis que importam.
    return sorted(
        agrupado.values(), key=lambda l: (-l["vencidas"], -l["a_vencer"], l["pessoa"].nome)
    )


