"""FAQ — a base de conhecimento que o assistente consulta antes de encaminhar.

## O problema

Cada setor responde as mesmas dez perguntas toda semana. "Como peço férias",
"quem aprova reembolso", "onde vejo meu holerite". A resposta existe, está certa,
e mora na cabeça de três pessoas — que param o que estão fazendo para digitá-la
de novo.

## Por que não é o `intencao`

`intencao.interpretar()` responde **"quero férias"** abrindo o formulário de
férias. Este modelo responde **"como funciona minha férias"** com um texto. São
perguntas diferentes: uma quer AGIR, a outra quer SABER, e o mesmo motor
respondendo as duas produz o pior erro possível — abrir um pedido para quem só
queria entender a regra.

O `intencao` já barra isso com os verbos de leitura ("preciso VER a política").
Este modelo é o que passa a ter o que dizer quando a barreira dispara.

## Palavras-chave são curadoria, não busca

O casamento não tenta compreender a frase: procura os termos que alguém
cadastrou de propósito. É a mesma decisão de `ItemCatalogo.termos`, e pelo mesmo
motivo — quem escreve a FAQ sabe como a empresa pergunta, e um sinônimo
cadastrado vale mais que qualquer heurística.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models


class AreaFAQ(models.TextChoices):
    """As áreas do §3, na ordem em que a empresa pergunta.

    Valor = o PREFIXO de domínio quando existe (`rh.`, `fin.`), para que a FAQ
    e o catálogo falem a mesma língua: a pergunta de R.H. leva ao item de R.H.
    sem tabela de conversão no meio.

    As três últimas não têm domínio de catálogo porque não são coisas que se
    PEDEM — são coisas que se consultam.
    """

    RH = "rh", "RH"
    OPERACOES = "ops", "Operações"
    SUPRIMENTOS = "log", "Suprimentos"
    COMPRAS = "com", "Compras"
    FINANCEIRO = "fin", "Financeiro"
    TI = "ti", "TI e Redes"
    MARKETING = "mkt", "Marketing"
    JURIDICO = "jur", "Jurídico"
    UNIVERSIDADE = "hab", "Universidade"
    VENDAS = "ven", "Vendas"
    DOCUMENTOS = "doc", "Documentos"
    RESERVAS = "res", "Reservas"
    PROCESSOS = "proc", "Processos internos"


class PerguntaFrequenteQuerySet(models.QuerySet):
    def ativas(self):
        return self.filter(ativo=True)

    def da_area(self, area: str):
        return self.filter(area=area)


class PerguntaFrequente(models.Model):
    """Uma pergunta que o setor responde toda semana, respondida uma vez."""

    area = models.CharField(max_length=10, choices=AreaFAQ.choices, db_index=True)
    pergunta = models.CharField(max_length=200)
    resposta = models.TextField()

    # Os termos que alguém CADASTROU. Guardados normalizados na escrita — ver
    # `indice.normalizar()`: normalizar na leitura custaria a cada tecla
    # digitada por cada pessoa.
    palavras_chave = models.JSONField(
        default=list, blank=True,
        help_text="Como as pessoas perguntam isto. Um por linha.",
    )

    # Para onde levar depois de responder. É o que transforma a FAQ de texto em
    # primeira camada de atendimento: responde E oferece o caminho.
    url_acao = models.CharField(
        max_length=300, blank=True, help_text="Caminho interno. Ex.: /workspace/servicos/ferias/"
    )
    rotulo_acao = models.CharField(max_length=60, blank=True)

    # Desempate quando duas perguntas casam com a mesma frase. Maior primeiro.
    prioridade = models.PositiveSmallIntegerField(default=0)
    ativo = models.BooleanField(default=True, db_index=True)

    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True, blank=True, on_delete=models.SET_NULL,
        related_name="faqs_criadas",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = PerguntaFrequenteQuerySet.as_manager()

    class Meta:
        # Área, depois prioridade decrescente, depois a pergunta. A listagem por
        # área é como a tela mostra, e a prioridade é o que o setor usa para pôr
        # a pergunta mais frequente no topo.
        ordering = ["area", "-prioridade", "pergunta"]
        verbose_name = "pergunta frequente"
        verbose_name_plural = "perguntas frequentes"
        indexes = [
            models.Index(fields=["ativo", "area", "-prioridade"], name="wks_faq_area_idx"),
        ]

    def __str__(self) -> str:
        return f"[{self.get_area_display()}] {self.pergunta}"

    @property
    def termos_curados(self) -> list[str]:
        """Só o que alguém cadastrou de propósito — o sinal forte."""
        from workspace.services.indice import normalizar

        return [normalizar(t) for t in self.palavras_chave if t]

    @property
    def termos_do_titulo(self) -> list[str]:
        """As palavras da própria pergunta — sinal fraco.

        Entram na conta porque quem cadastra esquece de repetir na lista o que já
        escreveu no título. Mas valem MENOS: título de FAQ é escrito em
        português corrente, e "Como pedir acesso a um sistema?" empresta "pedir"
        para qualquer frase que contenha o verbo — foi assim que "como faço para
        pedir um notebook" respondeu sobre acesso a sistema.
        """
        from workspace.services.indice import normalizar

        return [normalizar(self.pergunta)] if self.pergunta else []

    @property
    def termos(self) -> list[str]:
        """Tudo junto. Para quem só quer saber se um termo existe."""
        return [*self.termos_curados, *self.termos_do_titulo]
