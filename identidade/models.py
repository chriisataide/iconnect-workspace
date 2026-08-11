"""IDN — Identidade & Organização.

É a fundação de todo o Workspace: sem organograma e papel com escopo, "minha
equipe" é inexpressável e toda permissão vira `if user.role == "gerente"`
espalhado por views.

## Direção da dependência

Este app faz FK **apenas** para `auth.User`. Não importa `dashboard`, `fsm` nem
`km_audit` — a Etapa 5 §5.3 põe IDN como a raiz: ninguém depende de nada para
chegar aqui, e todos dependem dele.

Consequência prática: o grafo organizacional (unidade, departamento, gestor)
mora em `Lotacao`, aqui, e não em `dashboard.PerfilUsuario`. Se morasse lá,
`pode()` precisaria importar `dashboard` e a direção inverteria.

A divisão é por responsabilidade, não duplicação:

    dashboard.PerfilUsuario   dados PESSOAIS  — CPF, telefone, avatar, MFA
    identidade.Lotacao        posição na EMPRESA — unidade, depto, gestor, matrícula

## Duplicação transitória conhecida

`PerfilUsuario.departamento` é `CharField` de texto livre e continua existindo.
Até o comando de reconciliação (ST-010) casar texto → FK, os dois coexistem, e
**`Lotacao.departamento` é a fonte de verdade** para autorização. O campo de
texto fica como espelho legado, para não quebrar views e templates atuais.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.utils import timezone

# ── Escopos ─────────────────────────────────────────────────────────
# Ordem = abrangência crescente. `global` satisfaz qualquer escopo menor.
# A hierarquia é dado, não `if` encadeado: acrescentar escopo novo no meio
# não deve exigir reescrever a resolução.

ESCOPO_PROPRIO = "proprio"
ESCOPO_EQUIPE = "equipe"
ESCOPO_DEPARTAMENTO = "departamento"
ESCOPO_UNIDADE = "unidade"
ESCOPO_GLOBAL = "global"

HIERARQUIA_ESCOPO = [
    ESCOPO_PROPRIO,
    ESCOPO_EQUIPE,
    ESCOPO_DEPARTAMENTO,
    ESCOPO_UNIDADE,
    ESCOPO_GLOBAL,
]

ESCOPO_CHOICES = [
    (ESCOPO_PROPRIO, "Próprio"),
    (ESCOPO_EQUIPE, "Equipe (liderados diretos e indiretos)"),
    (ESCOPO_DEPARTAMENTO, "Departamento"),
    (ESCOPO_UNIDADE, "Unidade"),
    (ESCOPO_GLOBAL, "Global"),
]


def abrangencia(escopo: str) -> int:
    """Posição do escopo na hierarquia. Desconhecido é o mais restrito."""
    try:
        return HIERARQUIA_ESCOPO.index(escopo)
    except ValueError:
        return -1


# ── Estrutura organizacional ────────────────────────────────────────


class Unidade(models.Model):
    """Filial, base operacional ou matriz."""

    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=120)
    sigla = models.CharField(max_length=10, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=2, blank=True)
    ativa = models.BooleanField(default=True, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "unidade"
        verbose_name_plural = "unidades"

    def __str__(self) -> str:
        return f"{self.codigo} · {self.nome}"


class Departamento(models.Model):
    """Área organizacional. Atravessa unidades de propósito.

    Um departamento (ex. Financeiro) existe na empresa, não numa filial. Quem
    amarra pessoa a filial é a `Lotacao`.
    """

    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=120)
    ativo = models.BooleanField(default=True, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "departamento"
        verbose_name_plural = "departamentos"

    def __str__(self) -> str:
        return f"{self.codigo} · {self.nome}"


class Situacao(models.TextChoices):
    ATIVO = "ativo", "Ativo"
    FERIAS = "ferias", "Em férias"
    AFASTADO = "afastado", "Afastado"
    DESLIGADO = "desligado", "Desligado"


class LotacaoQuerySet(models.QuerySet):
    def ativas(self):
        """Exclui desligados. Desligado não tem escopo nem recebe delegação."""
        return self.exclude(situacao=Situacao.DESLIGADO)


class Lotacao(models.Model):
    """Onde a pessoa está na empresa. É o nó do organograma.

    1:1 com User porque toda pessoa do sistema tem exatamente uma posição
    vigente. Histórico de movimentação é outro problema (V2) e não deve poluir
    a leitura de escopo, que roda dezenas de vezes por requisição.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lotacao"
    )
    matricula = models.CharField(max_length=30, blank=True, db_index=True)
    unidade = models.ForeignKey(
        Unidade, null=True, blank=True, on_delete=models.PROTECT, related_name="lotacoes"
    )
    departamento = models.ForeignKey(
        Departamento, null=True, blank=True, on_delete=models.PROTECT, related_name="lotacoes"
    )
    gestor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="liderados",
        help_text="Quem esta pessoa reporta. Define o escopo `equipe`.",
    )
    # Código textual em vez de FK: `CentroCusto` mora em `dashboard`, e IDN não
    # importa app de domínio. A resolução do código para o objeto é feita por
    # quem precisa do objeto, não aqui.
    centro_custo_codigo = models.CharField(max_length=20, blank=True, db_index=True)
    cargo = models.CharField(max_length=100, blank=True)
    situacao = models.CharField(
        max_length=20, choices=Situacao.choices, default=Situacao.ATIVO, db_index=True
    )
    data_admissao = models.DateField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    objects = LotacaoQuerySet.as_manager()

    class Meta:
        verbose_name = "lotação"
        verbose_name_plural = "lotações"
        indexes = [
            # A CTE de liderados percorre gestor_id. Sem índice, organograma de
            # 500 pessoas faz varredura completa por nível.
            models.Index(fields=["gestor"], name="idn_lotacao_gestor_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.user.get_username()} · {self.cargo or 'sem cargo'}"

    def clean(self) -> None:
        if self.gestor_id and self.gestor_id == self.user_id:
            raise ValidationError({"gestor": "Uma pessoa não pode ser gestora de si mesma."})
        if self.gestor_id and self._cria_ciclo():
            raise ValidationError(
                {"gestor": "Este vínculo cria um ciclo no organograma (A → B → A)."}
            )

    def _cria_ciclo(self) -> bool:
        """Sobe a cadeia do gestor procurando voltar a esta pessoa.

        Teto de profundidade porque um ciclo já existente no banco (inserido
        antes desta validação) faria o laço rodar para sempre.
        """
        visto: set[int] = set()
        atual = self.gestor_id
        for _ in range(64):
            if atual is None or atual in visto:
                return False
            if atual == self.user_id:
                return True
            visto.add(atual)
            atual = (
                Lotacao.objects.filter(user_id=atual)
                .values_list("gestor_id", flat=True)
                .first()
            )
        return False


# ── Papéis e atribuição ─────────────────────────────────────────────


class Papel(models.Model):
    """Conjunto nomeado de permissões.

    `permissoes` é lista declarativa em JSON, não M2M com Permission do Django.
    Motivo: as permissões do Workspace têm a forma `<dominio>.<acao>.<escopo>`,
    que não corresponde a `app_label.codename` — e forçar o encaixe produziria
    centenas de Permission sintéticas só para expressar escopo.

    Curinga aceito no fim: `rh.*` cobre toda ação de RH; `*` cobre tudo.
    """

    chave = models.SlugField(max_length=40, unique=True)
    nome = models.CharField(max_length=80)
    descricao = models.TextField(blank=True)
    permissoes = models.JSONField(default=list, blank=True)
    escopo_padrao = models.CharField(
        max_length=20, choices=ESCOPO_CHOICES, default=ESCOPO_PROPRIO
    )
    ativo = models.BooleanField(default=True, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]
        verbose_name = "papel"
        verbose_name_plural = "papéis"

    def __str__(self) -> str:
        return self.nome

    def clean(self) -> None:
        if not isinstance(self.permissoes, list):
            raise ValidationError({"permissoes": "Deve ser uma lista de strings."})
        for p in self.permissoes:
            if not isinstance(p, str) or not p.strip():
                raise ValidationError({"permissoes": f"Permissão inválida: {p!r}"})


class AtribuicaoPapelQuerySet(models.QuerySet):
    def vigentes(self, em=None):
        """Só o que vale agora. Vigência aberta (`fim=NULL`) nunca expira.

        Existe como queryset e não como filtro na view para que `pode()`, o
        admin e um futuro relatório não divirjam sobre o que "vigente" significa.
        """
        em = em or timezone.localdate()
        return self.filter(vigencia_inicio__lte=em).filter(
            Q(vigencia_fim__isnull=True) | Q(vigencia_fim__gte=em)
        )


class AtribuicaoPapel(models.Model):
    """Pessoa × Papel × escopo × vigência.

    O escopo aqui é o que permite dizer "gerente financeiro DA UNIDADE SP até
    31/12". Sem escopo, "gerente" vê tudo de todas as unidades — inviável para
    RH e Financeiro. Sem vigência, férias do aprovador travam a empresa.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="atribuicoes_papel"
    )
    papel = models.ForeignKey(Papel, on_delete=models.PROTECT, related_name="atribuicoes")
    escopo = models.CharField(max_length=20, choices=ESCOPO_CHOICES)

    # Alvo do escopo, quando ele for territorial. `unidade` sem esta FK
    # significaria "a unidade da própria pessoa", que é ambíguo para quem
    # responde por duas filiais.
    unidade = models.ForeignKey(
        Unidade, null=True, blank=True, on_delete=models.CASCADE, related_name="atribuicoes"
    )
    departamento = models.ForeignKey(
        Departamento, null=True, blank=True, on_delete=models.CASCADE, related_name="atribuicoes"
    )

    vigencia_inicio = models.DateField(default=timezone.localdate)
    vigencia_fim = models.DateField(null=True, blank=True)

    concedido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="atribuicoes_concedidas",
    )
    justificativa = models.TextField(blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    objects = AtribuicaoPapelQuerySet.as_manager()

    class Meta:
        ordering = ["-vigencia_inicio"]
        verbose_name = "atribuição de papel"
        verbose_name_plural = "atribuições de papel"
        constraints = [
            # `Coalesce` nas FKs anuláveis, e não `fields=[...]`, porque em SQL
            # `NULL != NULL`: uma UNIQUE sobre coluna anulável NÃO dedupe quando
            # ela é nula — e nula é justamente o caso mais comum aqui (escopo
            # `proprio` e `global` não têm unidade nem departamento). Com
            # `fields`, a constraint existiria e não protegeria nada.
            #
            # Expressão em vez de `nulls_distinct=False` para funcionar também em
            # SQLite, onde a suíte roda localmente.
            models.UniqueConstraint(
                models.F("user"),
                models.F("papel"),
                models.F("escopo"),
                Coalesce("unidade", models.Value(0)),
                Coalesce("departamento", models.Value(0)),
                models.F("vigencia_inicio"),
                name="idn_atribuicao_unica",
            )
        ]
        indexes = [
            models.Index(
                fields=["user", "vigencia_inicio", "vigencia_fim"],
                name="idn_atrib_vigencia_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user.get_username()} · {self.papel.chave} · {self.escopo}"

    def clean(self) -> None:
        if self.vigencia_fim and self.vigencia_fim < self.vigencia_inicio:
            raise ValidationError({"vigencia_fim": "Fim da vigência é antes do início."})
        if self.escopo == ESCOPO_UNIDADE and not self.unidade_id:
            raise ValidationError({"unidade": "Escopo `unidade` exige a unidade."})
        if self.escopo == ESCOPO_DEPARTAMENTO and not self.departamento_id:
            raise ValidationError({"departamento": "Escopo `departamento` exige o departamento."})

    @property
    def vigente(self) -> bool:
        hoje = timezone.localdate()
        if self.vigencia_inicio > hoje:
            return False
        return self.vigencia_fim is None or self.vigencia_fim >= hoje


class DelegacaoQuerySet(models.QuerySet):
    def vigentes(self, em=None):
        em = em or timezone.localdate()
        return self.filter(inicio__lte=em, fim__gte=em, ativa=True)


class Delegacao(models.Model):
    """Transferência temporária de papéis — férias, afastamento, viagem.

    **Nunca amplia.** O que o delegado recebe é a interseção entre o que o
    delegante tinha e o que a delegação declara. Delegação que amplia é o
    caminho mais silencioso para escalonamento de privilégio.
    """

    de_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="delegacoes_feitas"
    )
    para_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="delegacoes_recebidas"
    )
    papeis = models.ManyToManyField(
        Papel,
        blank=True,
        related_name="delegacoes",
        help_text="Vazio = delega todos os papéis vigentes do delegante.",
    )
    inicio = models.DateField()
    fim = models.DateField()
    motivo = models.CharField(max_length=200, blank=True)
    ativa = models.BooleanField(default=True, db_index=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    objects = DelegacaoQuerySet.as_manager()

    class Meta:
        ordering = ["-inicio"]
        verbose_name = "delegação"
        verbose_name_plural = "delegações"
        indexes = [
            models.Index(fields=["para_user", "inicio", "fim"], name="idn_deleg_para_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.de_user.get_username()} → {self.para_user.get_username()}"

    def clean(self) -> None:
        if self.de_user_id == self.para_user_id:
            raise ValidationError({"para_user": "Não é possível delegar para si mesmo."})
        if self.fim < self.inicio:
            raise ValidationError({"fim": "Fim da delegação é antes do início."})

    @property
    def vigente(self) -> bool:
        hoje = timezone.localdate()
        return self.ativa and self.inicio <= hoje <= self.fim
