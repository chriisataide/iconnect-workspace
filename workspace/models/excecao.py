"""Gestão por exceção — o padrão mais aproveitável do benchmark.

O "Painel Gestão de Efetivo" do Portal GPS não é um dashboard: é uma **lista de
regras**, cada uma com uma contagem, que expande para a grade dos registros que
a violaram. E cada linha da grade traz o **responsável** — a exceção já nasce
endereçada.

## O que é dado e o que é código

`RegraExcecao` guarda **configuração**: se a regra está ligada, em que ordem
aparece, quão grave é, e qual janela ela usa. A **lógica** de cada regra mora em
`workspace/excecoes/`, num registro em memória.

A separação não é gosto. Se a lógica fosse dado, daria para "ativar" pelo
`/admin/` uma regra que ninguém escreveu — e o erro apareceria às três da manhã,
no cron. Se a configuração fosse código, mudar a severidade de uma regra
exigiria deploy, e severidade é decisão de quem opera, tomada no dia.

## Regra com zero NÃO some

Sumir esconde que a regra existe, e o efeito prático é alguém reabrir a
discussão sobre "deveríamos vigiar X" seis meses depois de já estarmos vigiando.

E "sem ocorrências" é **diferente** de "não avaliada": a segunda quer dizer que
a fonte da regra não está disponível, e as duas pedem ações opostas — uma é
tranquilidade, a outra é uma fonte para ligar.
"""

from __future__ import annotations

from django.db import models
from django.utils import timezone


class Severidade(models.TextChoices):
    """Três níveis, e não cinco.

    Cinco níveis produzem um empate permanente no meio: tudo vira "média", e a
    coluna deixa de significar coisa alguma — o mesmo defeito da urgência
    autodeclarada no catálogo de serviços.
    """

    ALTA = "alta", "Alta"
    MEDIA = "media", "Média"
    BAIXA = "baixa", "Baixa"


class RegraExcecaoQuerySet(models.QuerySet):
    def ativas(self):
        return self.filter(ativa=True)


class RegraExcecao(models.Model):
    """A configuração de uma regra. A lógica dela é código."""

    chave = models.SlugField(max_length=60, unique=True)
    titulo = models.CharField(max_length=160)
    descricao_curta = models.CharField(
        max_length=300,
        help_text="O que a regra procura, em uma frase. Aparece na lista.",
    )
    severidade = models.CharField(
        max_length=10, choices=Severidade.choices, default=Severidade.MEDIA,
        db_index=True,
    )
    #: Dias. O que "além do prazo" quer dizer para esta regra. Zero = não usa
    #: janela — a regra é sobre um estado, e não sobre tempo.
    janela = models.PositiveSmallIntegerField(default=0)

    #: A chave do `Papel` que responde por esta regra. É o que decide quem VÊ a
    #: regra no painel — e, na grade, quem aparece como responsável.
    #:
    #: Vazio = todo mundo que abre o painel vê. Usado só nas regras sobre a
    #: própria ingestão, que não são de departamento nenhum.
    escopo_papel = models.CharField(max_length=40, blank=True, db_index=True)

    #: A fonte de que a regra depende: `sankhya`, `monday`, `iconnect_platform`,
    #: `hris`… Vazio = a regra olha só para dado do próprio Workspace.
    #:
    #: Quando a fonte não está disponível, a regra aparece como **não avaliada**
    #: — que não é zero. Somá-las faria uma fonte caída parecer um mês tranquilo.
    fonte_requerida = models.CharField(max_length=30, blank=True)

    ativa = models.BooleanField(default=True, db_index=True)
    ordem = models.PositiveSmallIntegerField(default=100)

    objects = RegraExcecaoQuerySet.as_manager()

    class Meta:
        ordering = ["ordem", "titulo"]
        verbose_name = "regra de exceção"
        verbose_name_plural = "regras de exceção"

    def __str__(self) -> str:
        return f"{self.chave} · {self.titulo}"


class ResultadoExcecao(models.Model):
    """O retrato de uma avaliação. É daqui que sai a TENDÊNCIA.

    Uma regra que foi de 3 para 40 importa mais que uma que está em 40 há um ano
    — e a contagem sozinha não conta isso. Sem histórico, o painel mostra o
    estado e esconde o movimento, que é a metade acionável.

    ## O que NUNCA entra em `chaves`

    Nada que identifique pessoa. `chaves` guarda o identificador do REGISTRO que
    violou a regra — `lotacao:41`, `contrato:CT-100` —, e não o nome de quem
    responde por ele. O histórico é consultado por gente que não abriu a tela e
    não passou por permissão nenhuma.
    """

    regra = models.ForeignKey(
        RegraExcecao, on_delete=models.CASCADE, related_name="resultados"
    )
    executada_em = models.DateTimeField(default=timezone.now, db_index=True)
    total = models.PositiveIntegerField(default=0)
    #: As chaves das ocorrências, para a próxima avaliação saber o que é NOVO.
    #: Truncada — ver `LIMITE_DE_CHAVES`.
    chaves = models.JSONField(default=list, blank=True)
    #: `False` quando a fonte da regra não estava disponível. O total de uma
    #: avaliação não realizada é zero, e sem esta marca ele mentiria.
    avaliada = models.BooleanField(default=True)

    class Meta:
        ordering = ["-executada_em"]
        verbose_name = "resultado de exceção"
        verbose_name_plural = "resultados de exceção"
        indexes = [
            models.Index(fields=["regra", "-executada_em"],
                         name="wks_excecao_hist_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.regra.chave} · {self.total} em {self.executada_em:%d/%m %H:%M}"


#: Quantas chaves guardar por avaliação. Uma regra com 2.556 ocorrências — o
#: número real do "ASO vencido" do benchmark — geraria um JSON que ninguém lê e
#: que engorda cada leitura do histórico. O que interessa do diff é "apareceu
#: coisa nova", e para isso uma amostra basta.
LIMITE_DE_CHAVES = 200
