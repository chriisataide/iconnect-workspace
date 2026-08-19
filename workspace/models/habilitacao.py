"""HAB — Universidade Corporativa: o que cada pessoa precisa ter em dia.

## O que este módulo resolve

A empresa sabe quem fez o curso. Não sabe quem está prestes a **perder** a
habilitação — e é essa a pergunta cara: NR-35 vencida bloqueia despacho, e a
descoberta acontece na portaria da obra, com o técnico já lá.

Hoje o catálogo tem "Treinamento ou curso" e "Reciclagem de NR": os dois abrem
PEDIDO. Pedido é o que a pessoa faz quando já sabe que precisa. Este módulo é o
que faz alguém saber.

## Curso e matrícula, e por que dois modelos

`Curso` é o catálogo: existe uma vez, vale para a empresa. `Matricula` é a
relação de UMA pessoa com ele — quando fez, quando vence, em que pé está.

Um modelo só (curso com colunas de pessoa) obrigaria a duplicar nome, carga e
validade para cada colaborador, e a correção de um erro de digitação teria de
alcançar oitocentas linhas.

## A validade é do CURSO, o vencimento é da MATRÍCULA

`Curso.validade_meses` diz quanto tempo a habilitação dura; `Matricula.vence_em`
é a data concreta, calculada na conclusão. Guardar a data e não recalculá-la a
cada leitura é o que permite responder "o que vence em 30 dias" com uma
consulta em vez de um laço sobre a empresa inteira.

E é o que mantém a verdade histórica: se a empresa mudar a NR-35 de 2 para 3
anos, quem concluiu antes continua vencendo pela regra que valia — o certificado
dele diz aquilo.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class TipoCurso(models.TextChoices):
    NR = "nr", "Norma regulamentadora"
    TECNICO = "tecnico", "Técnico"
    INSTITUCIONAL = "institucional", "Institucional"
    INTEGRACAO = "integracao", "Integração"


class SituacaoMatricula(models.TextChoices):
    """Os cinco estados do §27.

    `VENCIDO` e `A_VENCER` são DERIVADOS da data, não gravados: um estado
    guardado que depende do calendário fica errado sozinho todo dia à
    meia-noite, e só volta a acertar quando alguém roda alguma coisa.
    """

    PENDENTE = "pendente", "Pendente"
    EM_ANDAMENTO = "em_andamento", "Em andamento"
    CONCLUIDO = "concluido", "Concluído"
    DISPENSADO = "dispensado", "Dispensado"


class Curso(models.Model):
    """Um curso do catálogo da Universidade."""

    codigo = models.SlugField(max_length=40, unique=True)
    nome = models.CharField(max_length=160)
    descricao = models.CharField(max_length=300, blank=True)
    tipo = models.CharField(
        max_length=20, choices=TipoCurso.choices, default=TipoCurso.TECNICO,
        db_index=True,
    )

    carga_horaria = models.PositiveSmallIntegerField(null=True, blank=True)

    # ZERO = não vence. Não `null`, porque `null` num campo numérico convida a
    # comparação `if curso.validade_meses` funcionar por acidente para os dois
    # casos e quebrar quando alguém trocar o operador.
    validade_meses = models.PositiveSmallIntegerField(
        default=0, help_text="0 = não vence."
    )

    # Obrigatório para QUEM? A resposta honesta hoje é "para quem o R.H.
    # matricular". Um campo de público-alvo aqui (por cargo, por papel) seria
    # inventar regra que a empresa ainda não escreveu — e regra inventada em
    # obrigatoriedade de NR é o tipo de coisa que passa a bloquear despacho de
    # gente que não precisava do curso.
    obrigatorio = models.BooleanField(
        default=False, help_text="Aparece como pendência de quem for matriculado."
    )

    ativo = models.BooleanField(default=True, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["tipo", "nome"]
        verbose_name = "curso"
        verbose_name_plural = "cursos"
        indexes = [models.Index(fields=["ativo", "tipo"], name="wks_curso_idx")]

    def __str__(self) -> str:
        return self.nome

    @property
    def vence(self) -> bool:
        return self.validade_meses > 0


class MatriculaQuerySet(models.QuerySet):
    def de(self, pessoa):
        if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
            return self.none()
        return self.filter(pessoa=pessoa)

    def concluidas(self):
        return self.filter(situacao=SituacaoMatricula.CONCLUIDO)

    def em_aberto(self):
        return self.filter(
            situacao__in=[SituacaoMatricula.PENDENTE, SituacaoMatricula.EM_ANDAMENTO]
        )

    def vencidas(self, em=None):
        """Concluídas cuja validade já passou."""
        return self.concluidas().filter(vence_em__lt=em or timezone.localdate())

    def a_vencer(self, dias: int, em=None):
        """Concluídas que vencem nos próximos `dias` — e ainda não venceram."""
        hoje = em or timezone.localdate()
        return self.concluidas().filter(
            vence_em__gte=hoje, vence_em__lte=hoje + timedelta(days=dias)
        )


class Matricula(models.Model):
    """A relação de uma pessoa com um curso."""

    pessoa = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="matriculas"
    )
    curso = models.ForeignKey(Curso, on_delete=models.PROTECT, related_name="matriculas")

    situacao = models.CharField(
        max_length=20, choices=SituacaoMatricula.choices,
        default=SituacaoMatricula.PENDENTE, db_index=True,
    )

    # 0 a 100. Existe porque "em andamento" sem número não diz se falta uma aula
    # ou o curso inteiro — e é a diferença entre cobrar e ajudar.
    percentual = models.PositiveSmallIntegerField(default=0)

    # Quando a pessoa PRECISA concluir. Diferente de `vence_em`, que é quando a
    # conclusão perde validade. Confundir os dois é o erro clássico deste
    # domínio: "prazo" antes de fazer, "validade" depois de feito.
    prazo = models.DateField(null=True, blank=True)

    concluido_em = models.DateField(null=True, blank=True)
    vence_em = models.DateField(null=True, blank=True, db_index=True)

    certificado = models.CharField(
        max_length=120, blank=True, help_text="Número ou identificação do certificado."
    )
    observacao = models.CharField(max_length=300, blank=True)

    # Quem responde pela habilitação desta pessoa. Vazio = o gestor da lotação.
    # Campo próprio porque NR de terceirizado responde a outro nome que não o
    # gestor do organograma.
    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name="matriculas_sob_responsabilidade",
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = MatriculaQuerySet.as_manager()

    class Meta:
        # Vencimento mais próximo primeiro: numa lista de habilitação, o que
        # vence antes é o que corre risco.
        ordering = ["vence_em", "prazo", "curso__nome"]
        verbose_name = "matrícula"
        verbose_name_plural = "matrículas"
        constraints = [
            # Uma matrícula por pessoa e curso. A reciclagem ATUALIZA a mesma
            # linha — criar uma nova a cada ciclo faria a pessoa aparecer com
            # três NR-35, duas delas vencidas, e o painel diria que ela está
            # irregular quando está em dia.
            models.UniqueConstraint(
                fields=["pessoa", "curso"], name="wks_matricula_unica"
            ),
        ]
        indexes = [
            models.Index(fields=["situacao", "vence_em"], name="wks_matricula_venc_idx"),
            models.Index(fields=["pessoa", "situacao"], name="wks_matricula_pessoa_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.pessoa} · {self.curso}"

    def clean(self) -> None:
        if self.situacao == SituacaoMatricula.CONCLUIDO and not self.concluido_em:
            raise ValidationError(
                {"concluido_em": "Concluído exige a data da conclusão."}
            )

    @property
    def dias_para_vencer(self) -> int | None:
        """Negativo quando já venceu. `None` quando não vence."""
        if not self.vence_em:
            return None
        return (self.vence_em - timezone.localdate()).days

    @property
    def vencido(self) -> bool:
        dias = self.dias_para_vencer
        return dias is not None and dias < 0

    @property
    def dias_vencido(self) -> int:
        """Há quantos dias venceu, POSITIVO. Zero quando não venceu.

        Existe para o template não precisar de um filtro de valor absoluto:
        "venceu há -12 dias" é o tipo de texto que passa em revisão e só é visto
        por quem está vencido.
        """
        dias = self.dias_para_vencer
        return abs(dias) if dias is not None and dias < 0 else 0

    @property
    def dias_de_atraso(self) -> int | None:
        """Quantos dias passaram do PRAZO sem concluir."""
        if self.prazo is None or self.situacao == SituacaoMatricula.CONCLUIDO:
            return None
        atraso = (timezone.localdate() - self.prazo).days
        return atraso if atraso > 0 else None

    @property
    def estado(self) -> str:
        """Os cinco estados do §27, derivados.

        Derivados e não gravados porque três deles dependem do CALENDÁRIO: um
        estado guardado fica errado sozinho à meia-noite e só volta a acertar
        quando alguém roda alguma coisa. É o mesmo motivo de `Publicacao.situacao`
        ser propriedade.
        """
        from workspace.services import habilitacao as hab

        if self.situacao == SituacaoMatricula.DISPENSADO:
            return "dispensado"
        if self.situacao != SituacaoMatricula.CONCLUIDO:
            return "atrasado" if self.dias_de_atraso else self.situacao
        dias = self.dias_para_vencer
        if dias is None:
            return "concluido"
        if dias < 0:
            return "vencido"
        return "a_vencer" if dias <= hab.PRIMEIRO_ALERTA else "concluido"

    @property
    def estado_rotulo(self) -> str:
        return {
            "pendente": "Pendente",
            "em_andamento": "Em andamento",
            "atrasado": "Atrasado",
            "concluido": "Em dia",
            "a_vencer": "Próximo do vencimento",
            "vencido": "Vencido",
            "dispensado": "Dispensado",
        }[self.estado]
