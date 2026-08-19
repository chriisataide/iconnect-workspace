"""COM — Comunicação. O que alimenta os cards de Comunicados e Notícias.

Onde se publica: **`/workspace/publicacoes/`**, dentro do portal, para quem tem
`com.publicar`. O Django admin continua funcionando como retaguarda — mas ele
exige `is_staff`, e quem escreve comunicado da empresa é o R.H. e a diretoria,
não quem administra o banco. Enquanto a única porta era o admin, publicar
significava pedir para outra pessoa.

Escolha de modelagem: **um** modelo com `tipo`, não dois. Comunicado e notícia
compartilham 100% dos campos e diferem só em intenção editorial. Dois modelos
custariam duas migrações, dois admins, duas queries e duas telas para sempre.

**Público-alvo** entrou: `unidades` e `departamentos`, os dois opcionais, os dois
significando "todo mundo" quando vazios. Estava adiado por depender do modelo de
identidade — que existe desde a onda seguinte, e o adiamento tinha sobrevivido a
ele.

Continua fora, de propósito: confirmação de leitura e classe "crítico" que
bloqueia navegação. As duas transformam comunicado em obrigação, e obrigação sem
política escrita vira tela que as pessoas fecham no reflexo.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from workspace.storage import ArmazenamentoPrivado, caminho_da_imagem


class TipoPublicacao(models.TextChoices):
    COMUNICADO = "comunicado", "Comunicado"
    NOTICIA = "noticia", "Notícia"


class Prioridade(models.IntegerChoices):
    NORMAL = 0, "Normal"
    ATENCAO = 1, "Atenção"
    URGENTE = 2, "Urgente"


class PublicacaoQuerySet(models.QuerySet):
    def nao_arquivadas(self):
        return self.filter(arquivado=False)

    def rascunhos(self):
        return self.filter(publicado=False, arquivado=False)

    def para(self, pessoa, agora=None):
        """O que está no ar E é para esta pessoa.

        Público-alvo VAZIO significa "para todo mundo", e não "para ninguém".
        O contrário faria toda publicação já existente sumir no dia em que o
        campo nasceu — e o comunicado que a empresa inteira precisava ler seria
        o primeiro a desaparecer.

        Sem lotação a pessoa recebe só o que é geral. É o certo: um comunicado
        endereçado ao Financeiro não deve alcançar quem o RH ainda não lotou em
        lugar nenhum.
        """
        from identidade.models import Lotacao

        consulta = self.publicadas(agora)
        lotacao = (
            Lotacao.objects.filter(user=pessoa)
            .values_list("unidade_id", "departamento_id")
            .first()
            if getattr(pessoa, "is_authenticated", False)
            else None
        )
        unidade_id, departamento_id = lotacao or (None, None)

        sem_alvo_unidade = models.Q(unidades__isnull=True)
        sem_alvo_departamento = models.Q(departamentos__isnull=True)
        alcanca_unidade = sem_alvo_unidade | models.Q(unidades=unidade_id)
        alcanca_departamento = sem_alvo_departamento | models.Q(
            departamentos=departamento_id
        )
        # `distinct` porque o M2M multiplica linhas: publicação com três
        # departamentos-alvo apareceria três vezes na lista.
        return consulta.filter(alcanca_unidade, alcanca_departamento).distinct()

    def publicadas(self, agora=None):
        """Só o que está no ar agora: publicado, dentro da vigência.

        Feito como queryset e não como filtro na view para que a home, a busca
        e um futuro feed não divirjam sobre o que "estar no ar" significa.
        """
        agora = agora or timezone.now()
        return (
            self.filter(publicado=True, arquivado=False, publicar_em__lte=agora)
            .filter(models.Q(expira_em__isnull=True) | models.Q(expira_em__gt=agora))
        )

    def do_tipo(self, tipo: str):
        return self.filter(tipo=tipo)


class Publicacao(models.Model):
    """Um comunicado ou uma notícia no Workspace."""

    tipo = models.CharField(
        max_length=20, choices=TipoPublicacao.choices, default=TipoPublicacao.COMUNICADO, db_index=True
    )
    titulo = models.CharField(max_length=200)
    resumo = models.CharField(
        max_length=300, blank=True, help_text="Uma linha, exibida no card do Workspace."
    )
    corpo = models.TextField(blank=True)

    prioridade = models.IntegerField(choices=Prioridade.choices, default=Prioridade.NORMAL)
    fixado = models.BooleanField(default=False, help_text="Fixa no topo da lista.")

    publicado = models.BooleanField(default=False, db_index=True)
    # ARQUIVADO é diferente de despublicado, e a diferença é editorial.
    #
    # Despublicar é "tirar do ar por enquanto" — o texto volta. Arquivar é "isto
    # acabou": sai da lista de trabalho de quem publica e não volta sozinho.
    # Com um campo só, a lista de rascunhos encheria de comunicado de 2019 que
    # ninguém tem coragem de apagar, e o rascunho de verdade se perderia no meio.
    arquivado = models.BooleanField(default=False, db_index=True)
    publicar_em = models.DateTimeField(
        default=timezone.now, help_text="Data futura agenda a publicação."
    )
    expira_em = models.DateTimeField(
        null=True, blank=True, help_text="Em branco, não expira."
    )

    # ── Público-alvo ─────────────────────────────────────────────────
    #
    # VAZIO = todo mundo. Ver `PublicacaoQuerySet.para()`.
    #
    # Duas dimensões e não uma: "Base Salvador" e "Financeiro" respondem
    # perguntas diferentes, e a empresa usa as duas — aviso de obra é por
    # unidade, mudança de política de despesa é por departamento. As duas juntas
    # se combinam por E: marcar Salvador + Financeiro alcança o Financeiro DE
    # Salvador, que é o que quem publica espera ao marcar as duas.
    unidades = models.ManyToManyField(
        "identidade.Unidade", blank=True, related_name="publicacoes",
        help_text="Em branco, alcança todas as unidades.",
    )
    departamentos = models.ManyToManyField(
        "identidade.Departamento", blank=True, related_name="publicacoes",
        help_text="Em branco, alcança todos os departamentos.",
    )

    # A imagem do card. Armazenamento privado como todo arquivo daqui: um
    # comunicado interno com foto de obra, de crachá ou de documento não deve
    # ficar num caminho que o nginx serve sem perguntar quem é.
    imagem = models.FileField(
        upload_to=caminho_da_imagem,
        storage=ArmazenamentoPrivado(),
        max_length=255,
        blank=True,
    )
    anexo = models.FileField(
        upload_to=caminho_da_imagem,
        storage=ArmazenamentoPrivado(),
        max_length=255,
        blank=True,
        help_text="PDF da política, ata, planilha.",
    )

    autor = models.ForeignKey(
        # `settings.AUTH_USER_MODEL` e não `"auth.User"` literal. Era literal, e
        # passava porque as duas coisas coincidiam — o dia em que o projeto ganhou
        # modelo de usuário próprio, este campo foi o único do repositório a
        # quebrar o `check`. FK para usuário nunca deve nomear o model direto.
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="publicacoes_workspace",
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = PublicacaoQuerySet.as_manager()

    class Meta:
        verbose_name = "publicação"
        verbose_name_plural = "publicações"
        # Fixado primeiro, depois mais recente. `-publicar_em` e não
        # `-criado_em`: o que vale para o leitor é a data de publicação.
        ordering = ["-fixado", "-publicar_em"]
        indexes = [
            models.Index(fields=["tipo", "publicado", "-publicar_em"], name="wks_pub_listagem_idx"),
        ]

    def __str__(self) -> str:
        return f"[{self.get_tipo_display()}] {self.titulo}"

    @property
    def no_ar(self) -> bool:
        agora = timezone.now()
        if not self.publicado or self.arquivado or self.publicar_em > agora:
            return False
        return self.expira_em is None or self.expira_em > agora

    @property
    def situacao(self) -> str:
        """A palavra que a tela de quem publica mostra.

        Derivada e não gravada: um campo `situacao` ao lado de `publicado`,
        `arquivado`, `publicar_em` e `expira_em` seria uma quinta fonte de
        verdade sobre a mesma coisa, e a primeira a discordar das outras quatro.
        """
        if self.arquivado:
            return "arquivado"
        if not self.publicado:
            return "rascunho"
        if self.publicar_em > timezone.now():
            return "agendado"
        if self.expira_em and self.expira_em <= timezone.now():
            return "expirado"
        return "no_ar"

    @property
    def situacao_rotulo(self) -> str:
        return {
            "arquivado": "Arquivado",
            "rascunho": "Rascunho",
            "agendado": "Agendado",
            "expirado": "Expirado",
            "no_ar": "No ar",
        }[self.situacao]

    @property
    def classe_prioridade(self) -> str:
        """Sufixo de classe CSS do ponto de prioridade.

        Classe e não token inline: a CSP de produção traz nonce em `style-src`,
        e navegador moderno ignora `unsafe-inline` quando há nonce — o que
        bloqueia atributo `style=""`. Cor via classe é a única forma segura.
        """
        return {
            Prioridade.URGENTE: "urgente",
            Prioridade.ATENCAO: "atencao",
        }.get(self.prioridade, "normal")
