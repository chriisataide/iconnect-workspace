"""O ciclo de planejamento — a pauta como objeto do produto.

## O que o benchmark tem que nós não tínhamos

No Portal GPS a pasta `01.01 – Ciclo de Planejamento Mensal` tem dezesseis itens
numerados **na ordem em que serão apresentados**: CP01, CP02, … CP16. A pauta da
reunião não é um documento no e-mail de alguém: ela é uma pasta do produto, e o
ciclo trimestral é um subconjunto de nove itens da mesma biblioteca de telas,
para uma plateia mais sênior.

O que isso resolve, e que uma pauta em apresentação de slides não resolve:

- a ordem de olhar é **decisão registrada**, e não improviso de quem conduz;
- cada item aponta para a **tela viva**, e não para uma imagem colada na véspera;
- o que se disse diante de cada item fica **junto do item**, e não numa ATA que
  ninguém consegue cruzar com a tela seis meses depois.

## Por que a etapa guarda um CÓDIGO de tela, e não uma URL

`EtapaCiclo.tela` guarda `"10"`, e não `/workspace/resultados/`. Um endereço
é estável por decisão (ADR-015) e uma URL não é: no dia em que a rota mudar,
uma pauta com URL vira uma lista de links quebrados — e o pior é que ela vira
isso *durante a reunião*, que é o único momento em que ninguém tem tempo de
consertar.

Código que deixou de existir também não quebra: a etapa continua legível, e a
tela diz "endereço desconhecido" em vez de oferecer um link para lugar nenhum.
Ver ADR-029.

## Pauta e reunião são coisas diferentes

`CicloPlanejamento` + `EtapaCiclo` são a **pauta**: mudam raramente, e mudar é
decisão de quem governa o ciclo. `OcorrenciaCiclo` + `AnotacaoEtapa` são a
**reunião de setembro**: nascem e morrem uma vez por competência.

Juntar as duas num model só faria a edição da pauta reescrever a história —
mexer na ordem em janeiro mudaria a ATA de outubro.

## O carimbo congelado

`AnotacaoEtapa` copia o carimbo de frescor do destino **no instante em que a
anotação é feita**, e a ATA copia o texto no instante em que a reunião fecha.
Nunca se recalcula. Uma ATA que recalcula o frescor reescreve o que a sala viu:
a decisão foi tomada diante de um número de três dias atrás, e é isso que o
registro tem de dizer para sempre. Ver ADR-030.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class Cadencia(models.TextChoices):
    MENSAL = "mensal", "Mensal"
    TRIMESTRAL = "trimestral", "Trimestral"


class SituacaoOcorrencia(models.TextChoices):
    """Dois estados, e não três.

    Não existe "prevista": a ocorrência nasce quando alguém abre a reunião. Uma
    fila de reuniões futuras em rascunho seria um calendário — e calendário de
    reunião é do M365, não daqui.
    """

    ABERTA = "aberta", "Aberta"
    FECHADA = "fechada", "Fechada"


class CicloPlanejamento(models.Model):
    """A pauta de um ciclo. Muda raramente, e mudar é decisão de quem governa."""

    chave = models.SlugField(max_length=40, unique=True)
    nome = models.CharField(max_length=120)
    cadencia = models.CharField(
        max_length=12, choices=Cadencia.choices, default=Cadencia.MENSAL
    )
    #: Quem senta na sala, em texto. É o que o benchmark distingue entre o ciclo
    #: mensal (Dir. Executivo + Diretores + Gerentes + coordenadores) e o
    #: trimestral (Presidente/VP + Diretores + Gerentes). Não é permissão: é a
    #: informação que faz quem conduz saber para quem está falando.
    publico = models.CharField(max_length=200, blank=True)

    #: As chaves de `Papel` que LEEM este ciclo — e que recebem a ATA.
    #:
    #: LISTA e não um campo só, diferente de `RegraExcecao.escopo_papel`. Uma
    #: regra de exceção tem um dono; uma reunião tem uma plateia, e o benchmark
    #: lista quatro papéis na mensal. Espremer isso num campo produziria a
    #: vírgula dentro do `CharField`, que é a pior estrutura possível: parece
    #: texto e é lista.
    #:
    #: Vazio = ninguém além de quem tem `cic.ler.global`. NÃO é "todo mundo":
    #: a ATA de uma reunião de diretoria com público vazio seria pública.
    papeis_leitores = models.JSONField(default=list, blank=True)

    #: A chave do `Papel` que CONDUZ: abre, anota e fecha. Um só, porque conduzir
    #: é responsabilidade e responsabilidade dividida não é de ninguém.
    papel_condutor = models.CharField(max_length=40, blank=True, db_index=True)

    ativo = models.BooleanField(default=True, db_index=True)
    ordem = models.PositiveSmallIntegerField(default=100)

    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["ordem", "nome"]
        verbose_name = "ciclo de planejamento"
        verbose_name_plural = "ciclos de planejamento"

    def __str__(self) -> str:
        return f"{self.chave} · {self.nome}"

    @property
    def alvo_da_ata(self) -> list[str]:
        """Os *subjects* de ACL que a ATA deste ciclo carrega.

        `papel:<chave>` é sujeito reconhecido por `subjects_de()` — o mesmo que
        o índice de busca usa no `WHERE`. Com isso a ATA entra no acervo sem
        nenhuma exceção no app de conteúdo: a vitrine, a leitura direta e a
        busca respeitam a plateia da reunião pelo caminho que já existia.

        NUNCA `["*"]`. Um documento sem alvo é público, e público inclui o
        anônimo do hub.
        """
        papeis = [p for p in (self.papeis_leitores or []) if p]
        if self.papel_condutor and self.papel_condutor not in papeis:
            papeis.append(self.papel_condutor)
        return [f"papel:{chave}" for chave in papeis]


class EtapaCiclo(models.Model):
    """Um item da pauta: CP05, e a tela que ele abre."""

    ciclo = models.ForeignKey(
        CicloPlanejamento, on_delete=models.CASCADE, related_name="etapas"
    )
    #: `CP01`. É por este código que a empresa conversa — "a CP05 travou de novo".
    codigo = models.CharField(max_length=8)
    ordem = models.PositiveSmallIntegerField(default=100)
    titulo = models.CharField(max_length=160)

    #: O CÓDIGO da tela no endereçamento — `"10"`, `"02.3"`. Nunca uma URL.
    #: Vazio = etapa sem tela (abertura, encerramento, um ponto de fala).
    tela = models.CharField(max_length=8, blank=True)

    #: O que se pergunta diante desta tela. É a diferença entre uma pauta e uma
    #: lista de links: sem isto, cada condutor inventa a própria pergunta, e a
    #: reunião muda de assunto quando muda de condutor.
    pergunta = models.CharField(max_length=300, blank=True)

    #: Obrigatória entra na conferência de frescor da abertura. As opcionais não
    #: seguram nada — e nenhuma etapa segura a reunião, ver `services/ciclos.py`.
    obrigatoria = models.BooleanField(default=True)

    class Meta:
        ordering = ["ordem", "codigo"]
        verbose_name = "etapa de ciclo"
        verbose_name_plural = "etapas de ciclo"
        constraints = [
            models.UniqueConstraint(
                fields=["ciclo", "codigo"], name="wks_etapa_codigo_unico"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.titulo}"


class OcorrenciaCiclo(models.Model):
    """A reunião de uma competência. Uma por ciclo e por mês."""

    ciclo = models.ForeignKey(
        CicloPlanejamento, on_delete=models.CASCADE, related_name="ocorrencias"
    )
    ano = models.PositiveSmallIntegerField()
    mes = models.PositiveSmallIntegerField()

    situacao = models.CharField(
        max_length=10,
        choices=SituacaoOcorrencia.choices,
        default=SituacaoOcorrencia.ABERTA,
        db_index=True,
    )
    conduzida_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ciclos_conduzidos",
    )
    aberta_em = models.DateTimeField(auto_now_add=True)
    fechada_em = models.DateTimeField(null=True, blank=True)

    #: As fontes que estavam atrasadas ou caídas QUANDO A REUNIÃO ABRIU.
    #:
    #: Congelado de propósito: recalcular na hora de ler faria a ATA de um mês
    #: ruim parecer limpa depois que a carga voltou. Cada item é
    #: `{"etapa", "titulo", "carimbo", "motivo"}` — texto, sem chave estrangeira,
    #: porque isto é registro histórico e não estado.
    impedimentos = models.JSONField(default=list, blank=True)

    #: A ATA, quando a reunião fecha. `SET_NULL` e não `CASCADE`: apagar o
    #: documento não pode apagar o registro de que a reunião aconteceu.
    ata = models.ForeignKey(
        "workspace.Documento",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ata_de",
    )

    class Meta:
        ordering = ["-ano", "-mes"]
        verbose_name = "ocorrência de ciclo"
        verbose_name_plural = "ocorrências de ciclo"
        constraints = [
            models.UniqueConstraint(
                fields=["ciclo", "ano", "mes"], name="wks_ocorrencia_competencia_unica"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.ciclo.chave} {self.mes:02d}/{self.ano}"

    @property
    def competencia(self) -> str:
        return f"{self.mes:02d}/{self.ano}"

    @property
    def fechada(self) -> bool:
        return self.situacao == SituacaoOcorrencia.FECHADA


class AnotacaoEtapa(models.Model):
    """O que se disse diante da CP05 naquele dia — com o carimbo que a tela tinha."""

    ocorrencia = models.ForeignKey(
        OcorrenciaCiclo, on_delete=models.CASCADE, related_name="anotacoes"
    )
    etapa = models.ForeignKey(
        EtapaCiclo, on_delete=models.CASCADE, related_name="anotacoes"
    )
    texto = models.TextField()

    #: O encaminhamento, quando existe. Campo separado do texto porque é o que
    #: alguém vai procurar depois — "o que ficou de fazer" é a única parte da
    #: ATA que gera trabalho, e enterrá-la no parágrafo é como se perde.
    encaminhamento = models.CharField(max_length=300, blank=True)
    prazo = models.DateField(null=True, blank=True)

    autor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="anotacoes_de_ciclo",
    )
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    #: O CARIMBO CONGELADO — o texto que estava na tela quando isto foi escrito.
    #:
    #: Texto e não uma referência à execução de carga: a execução é apagável, e
    #: este registro precisa sobreviver a ela. É o mesmo motivo pelo qual
    #: `Notificacao.url` guarda caminho e não nome de rota.
    carimbo_fonte = models.CharField(max_length=40, blank=True)
    carimbo_texto = models.CharField(max_length=200, blank=True)
    carimbo_alerta = models.BooleanField(default=False)

    class Meta:
        ordering = ["criado_em"]
        verbose_name = "anotação de etapa"
        verbose_name_plural = "anotações de etapa"

    def __str__(self) -> str:
        return f"{self.ocorrencia} · {self.etapa.codigo}"
