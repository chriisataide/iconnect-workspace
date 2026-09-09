"""A CONCENTRAÇÃO — o que a empresa decidiu olhar. §E1.

## As três categorias da faixa de destaques, e por que a terceira é diferente

    Destaque           o que foi bem         regra automática
    Ponto de atenção   o que exige cuidado   regra automática, por limiar
    Concentração       o que estamos focados em resolver   DECISÃO HUMANA

As duas primeiras são derivadas: elas dizem o que o número mostra, e ninguém as
edita. Se editássemos, a tela deixaria de refletir o espelho e passaria a
refletir quem mexeu por último.

A terceira é curadoria, e é a única coisa desta tela que uma pessoa escreve.
Ela responde outra pergunta: não "o que está ruim" — isso a regra já diz —, mas
**"o que decidimos atacar"**. Um contrato pode estar deficitário há seis meses e
não ser foco; outro pode estar bem e ser foco porque vai renovar.

## Por que ela vive no `workspace`, e não no espelho

Pelo mesmo motivo que `Oportunidade` não é `EditalPublico`: isto é registro
NOSSO. Alguém escreveu o motivo, alguém assumiu o prazo, e a carga da madrugada
não pode reescrever nem apagar isso. No espelho, a próxima sincronização
sobrescreveria o único texto que a tela guarda de verdade.

## O histórico é o produto, e não o rascunho

`encerrada_em` e `resultado` existem porque **é o histórico que mostra se a
empresa resolve o que decide olhar**. Uma lista só de concentrações abertas
responde "no que estamos"; a lista fechada responde "as últimas doze viraram o
quê" — que é a pergunta que muda comportamento.

Apagar uma concentração encerrada seria apagar essa resposta, e por isso não há
caminho de exclusão: encerrar é o fim da vida dela.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class OrigemConcentracao(models.TextChoices):
    """Sobre O QUE a empresa está concentrada.

    Três, e não texto livre: a origem é o que liga a concentração ao número na
    tela, e "o contrato do Bradesco" digitado à mão não casa com `CT-107`.
    """

    CONTRATO = "contrato", "Contrato"
    AREA = "area", "Área"
    INDICADOR = "indicador", "Indicador"


class ConcentracaoQuerySet(models.QuerySet):
    def abertas(self):
        return self.filter(encerrada_em__isnull=True)

    def encerradas(self):
        return self.filter(encerrada_em__isnull=False)

    def atrasadas(self, hoje=None):
        """Aberta e com prazo vencido.

        `prazo` nulo NÃO entra: concentração sem prazo é decisão em aberto, e
        chamá-la de atrasada faria a tela cobrar quem ainda não se comprometeu
        com data nenhuma.
        """
        return self.abertas().filter(
            prazo__isnull=False, prazo__lt=hoje or timezone.localdate()
        )


class Concentracao(models.Model):
    origem_tipo = models.CharField(
        max_length=20, choices=OrigemConcentracao.choices, db_index=True
    )
    #: O código do contrato, da área ou do indicador. Texto e não FK: os três
    #: vivem em apps diferentes — `Contrato` está no espelho, e o `workspace`
    #: não o conhece. A ligação é pelo código, como em todo o resto do produto.
    origem_ref = models.CharField(max_length=60, db_index=True)

    titulo = models.CharField(max_length=200)
    #: POR QUE estamos olhando isto. Obrigatório de propósito: uma concentração
    #: sem motivo é um item de lista, e listas de itens sem motivo é o que
    #: reuniões produzem quando ninguém decide nada.
    motivo = models.TextField()

    responsavel = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="concentracoes",
    )
    #: `null` é legítimo: nem toda decisão nasce com data. O que não é legítimo
    #: é a tela inventar uma.
    prazo = models.DateField(null=True, blank=True, db_index=True)

    aberta_em = models.DateTimeField(auto_now_add=True, db_index=True)
    aberta_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="concentracoes_abertas",
    )

    encerrada_em = models.DateTimeField(null=True, blank=True, db_index=True)
    #: O QUE ACONTECEU. Obrigatório ao encerrar — ver `services.concentracao`.
    #:
    #: Encerrar sem dizer o resultado transformaria o histórico numa lista de
    #: datas, e a pergunta que ele existe para responder ("a empresa resolve o
    #: que decide olhar?") não teria resposta.
    resultado = models.TextField(blank=True)

    objects = ConcentracaoQuerySet.as_manager()

    class Meta:
        # Abertas primeiro, e dentro delas a de prazo mais próximo. É a ordem
        # em que a reunião as percorre.
        ordering = ["encerrada_em", "prazo", "-aberta_em"]
        verbose_name = "concentração"
        verbose_name_plural = "concentrações"
        indexes = [
            models.Index(
                fields=["encerrada_em", "prazo"], name="wks_conc_abertas_idx"
            ),
            models.Index(
                fields=["origem_tipo", "origem_ref"], name="wks_conc_origem_idx"
            ),
        ]

    def __str__(self) -> str:
        return self.titulo

    @property
    def aberta(self) -> bool:
        return self.encerrada_em is None

    @property
    def atrasada(self) -> bool:
        return bool(self.aberta and self.prazo and self.prazo < timezone.localdate())

    @property
    def dias_para_o_prazo(self) -> int | None:
        """Negativo quando venceu. `None` sem prazo — e `None` não é zero."""
        if not self.prazo or not self.aberta:
            return None
        return (self.prazo - timezone.localdate()).days

    @property
    def dias_de_atraso(self) -> int:
        """Quantos dias VENCEU, sempre positivo. `0` quando não venceu.

        Existe para o template poder escrever "venceu há 3 dias" sem um filtro
        de valor absoluto: o número negativo é a verdade do domínio, e a frase
        precisa do módulo dele. Fazer a conta no template exigiria um filtro
        novo só para isto, e o produto formata em pt-BR num lugar só.
        """
        dias = self.dias_para_o_prazo
        return -dias if dias is not None and dias < 0 else 0
