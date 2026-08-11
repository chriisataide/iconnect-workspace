"""SVC — Catálogo de serviços. Uma fila de pedido, não cinco.

Este é o módulo que impede o erro nº 1 de portal corporativo: RH com a sua fila,
Financeiro com a sua, Compras com a sua, TI com a sua. Cinco lugares para pedir
garantem que o usuário erre — e depois de errar duas vezes ele volta para o
WhatsApp.

## A regra de ouro da navegação

O usuário navega por **problema**, nunca por departamento.

    ✅  "meu notebook quebrou"        → Equipamento e acesso
    ❌  TI → Hardware → Manutenção

Departamento é dado de **roteamento** (`dominio`), não taxonomia de navegação.
É por isso que `GrupoCatalogo` é por intenção e não tem "RH", "TI", "Financeiro".

## Nome do modelo

`SolicitacaoServico`, não `Solicitacao` como na Etapa 5 §5.2 — já existe
`SolicitacaoAprovacao` no APR, e duas classes com nome quase igual no mesmo app
é como se importa a errada.
"""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class GrupoCatalogo(models.TextChoices):
    """Agrupamento por INTENÇÃO. Nenhum nome de departamento aqui."""

    EQUIPAMENTO = "equipamento", "Equipamento e acesso"
    TRABALHO = "trabalho", "Trabalho e ausência"
    DINHEIRO = "dinheiro", "Dinheiro"
    VIAGEM = "viagem", "Viagem"
    ESPACO = "espaco", "Espaço e material"
    DESENVOLVIMENTO = "desenvolvimento", "Desenvolvimento"
    JURIDICO = "juridico", "Jurídico"


class TipoCampo(models.TextChoices):
    TEXTO = "texto", "Texto curto"
    TEXTO_LONGO = "texto_longo", "Texto longo"
    NUMERO = "numero", "Número"
    DATA = "data", "Data"
    ESCOLHA = "escolha", "Escolha"
    ARQUIVO = "arquivo", "Arquivo"


class ItemCatalogo(models.Model):
    """Um serviço que se pode pedir."""

    chave = models.SlugField(max_length=50, unique=True)
    nome = models.CharField(max_length=120)
    descricao_curta = models.CharField(
        max_length=200, blank=True, help_text="Uma linha, exibida no card do catálogo."
    )
    grupo = models.CharField(max_length=20, choices=GrupoCatalogo.choices, db_index=True)
    icone = models.CharField(max_length=30, default="grid")

    # Para onde o pedido vai. É dado de roteamento, não de navegação.
    dominio = models.CharField(
        max_length=40,
        help_text="Domínio de destino: fin.reembolso, rh.ferias, com.requisicao…",
    )

    prazo_prometido_dias = models.PositiveSmallIntegerField(
        default=5,
        help_text=(
            "Usado só enquanto não há histórico. Depois de 5 conclusões o card "
            "mostra o prazo REAL medido (P50) — é o que constrói confiança."
        ),
    )

    exige_valor = models.BooleanField(default=False)
    exige_centro_custo = models.BooleanField(default=False)

    # Lista de {chave, rotulo, tipo, obrigatorio, ajuda, opcoes}. JSON e não
    # modelo próprio porque campo de formulário é configuração, não entidade:
    # ninguém consulta "todos os campos do tipo data do catálogo".
    campos = models.JSONField(default=list, blank=True)

    permissao = models.CharField(
        max_length=60,
        blank=True,
        help_text="Vazio = qualquer funcionário pode pedir.",
    )

    # Abaixo deste valor e dentro do orçamento, não vai para fila humana.
    # `None` = sempre exige aprovação.
    limite_auto_aprovacao = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True
    )

    ativo = models.BooleanField(default=True, db_index=True)
    ordem = models.PositiveSmallIntegerField(default=100)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["grupo", "ordem", "nome"]
        verbose_name = "item do catálogo"
        verbose_name_plural = "itens do catálogo"
        indexes = [
            models.Index(fields=["ativo", "grupo", "ordem"], name="wks_item_cat_idx"),
        ]

    def __str__(self) -> str:
        return self.nome

    def clean(self) -> None:
        if not isinstance(self.campos, list):
            raise ValidationError({"campos": "Deve ser uma lista."})

        tipos = {t.value for t in TipoCampo}
        vistas: set[str] = set()
        for campo in self.campos:
            if not isinstance(campo, dict):
                raise ValidationError({"campos": f"Campo inválido: {campo!r}"})
            chave = campo.get("chave")
            if not chave:
                raise ValidationError({"campos": "Todo campo precisa de `chave`."})
            if chave in vistas:
                raise ValidationError({"campos": f"Chave repetida: {chave!r}"})
            vistas.add(chave)
            if campo.get("tipo", TipoCampo.TEXTO) not in tipos:
                raise ValidationError(
                    {"campos": f"Tipo desconhecido em {chave!r}: {campo.get('tipo')!r}"}
                )

        # Não é validação de dado, é de PRODUTO: formulário com muitos campos
        # livres é o que faz o usuário desistir e mandar e-mail. O resto tem de
        # vir da identidade.
        livres = [c for c in self.campos if c.get("obrigatorio")]
        if len(livres) > 3:
            raise ValidationError(
                {
                    "campos": (
                        f"{len(livres)} campos obrigatórios. O máximo é 3 — o resto "
                        "deve vir da identidade da pessoa."
                    )
                }
            )

        if self.limite_auto_aprovacao is not None and self.limite_auto_aprovacao < 0:
            raise ValidationError({"limite_auto_aprovacao": "Não pode ser negativo."})

    @property
    def campos_obrigatorios(self) -> list[str]:
        return [c["chave"] for c in self.campos if c.get("obrigatorio")]


class SituacaoServico(models.TextChoices):
    AGUARDANDO_APROVACAO = "aguardando_aprovacao", "Aguardando aprovação"
    APROVADA = "aprovada", "Aprovada"
    EM_ATENDIMENTO = "em_atendimento", "Em atendimento"
    CONCLUIDA = "concluida", "Concluída"
    DEVOLVIDA = "devolvida", "Devolvida"
    CANCELADA = "cancelada", "Cancelada"


class SolicitacaoServicoQuerySet(models.QuerySet):
    def de(self, pessoa):
        return self.filter(solicitante=pessoa)

    def abertas(self):
        return self.exclude(
            situacao__in=[
                SituacaoServico.CONCLUIDA,
                SituacaoServico.CANCELADA,
            ]
        )

    def concluidas(self):
        return self.filter(situacao=SituacaoServico.CONCLUIDA)


class SolicitacaoServico(models.Model):
    """Um pedido feito a partir do catálogo."""

    item = models.ForeignKey(
        ItemCatalogo, on_delete=models.PROTECT, related_name="solicitacoes"
    )
    solicitante = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="solicitacoes_servico"
    )

    dados = models.JSONField(default=dict, blank=True)
    valor = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    centro_custo_codigo = models.CharField(max_length=20, blank=True, db_index=True)

    situacao = models.CharField(
        max_length=25,
        choices=SituacaoServico.choices,
        default=SituacaoServico.AGUARDANDO_APROVACAO,
        db_index=True,
    )
    # Ligação com o motor de aprovação. Nula quando auto-aprovada.
    aprovacao = models.OneToOneField(
        "workspace.SolicitacaoAprovacao",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="servico",
    )
    auto_aprovada = models.BooleanField(default=False)
    motivo_devolucao = models.TextField(blank=True)

    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)
    concluido_em = models.DateTimeField(null=True, blank=True)

    objects = SolicitacaoServicoQuerySet.as_manager()

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "solicitação de serviço"
        verbose_name_plural = "solicitações de serviço"
        indexes = [
            models.Index(fields=["solicitante", "situacao"], name="wks_svc_minhas_idx"),
            models.Index(fields=["item", "situacao"], name="wks_svc_item_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.item.nome} · {self.solicitante.get_username()}"

    @property
    def dias_para_concluir(self) -> int | None:
        """Dias entre pedido e conclusão. É o que alimenta o prazo REAL medido."""
        if self.concluido_em is None:
            return None
        return (self.concluido_em - self.criado_em).days

    @property
    def em_aberto(self) -> bool:
        return self.situacao not in (SituacaoServico.CONCLUIDA, SituacaoServico.CANCELADA)

    def concluir(self) -> None:
        self.situacao = SituacaoServico.CONCLUIDA
        self.concluido_em = timezone.now()
        self.save(update_fields=["situacao", "concluido_em"])
