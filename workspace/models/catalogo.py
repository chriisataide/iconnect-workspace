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

from datetime import timedelta

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
    # `<input type="time">`: o navegador entrega os dois-pontos, o formato local
    # e o teclado certo no celular. Texto livre virava "das 14 as 16", "14h-16h"
    # e "2 da tarde" para a mesma ausência — e o R.H. lança hora, não frase.
    HORA = "hora", "Hora"
    ESCOLHA = "escolha", "Escolha"
    ARQUIVO = "arquivo", "Arquivo"

    # Os dois abaixo não são caixas de digitar: são pedaços de tela que o item
    # LIGA. Ficam aqui, e não numa flag booleana do item, porque a ordem deles
    # no formulário é a ordem da lista `campos` — e "onde aparece" é justamente
    # o que uma flag não consegue dizer.
    DESPESAS = "despesas", "Despesas item a item"
    ADIANTAMENTO = "adiantamento", "Adiantamento a prestar contas"


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

    termos = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Como as pessoas CHAMAM isto. `laptop`, `computador`, `máquina` "
            "levam a Notebook. É o que faz o assistente de ação funcionar sem "
            "IA — e cada termo aqui é um e-mail que ninguém precisou mandar."
        ),
    )

    # Os passos do formulário, na ordem. Vazio = uma tela só, que continua
    # sendo o certo para quase todo item: stepper em formulário de 2 campos é
    # cerimônia. Ele ganha o seu lugar quando há RAMO — "curso interno ou
    # externo?" muda o resto das perguntas — ou quando uma etapa só existe
    # depois do envio, como o acerto do adiantamento.
    #
    # Lista de {titulo, apos_envio?}. `apos_envio` marca o passo que acontece
    # em OUTRA tela, depois de enviar: ele aparece na trilha em cinza, porque
    # esconder que ainda falta uma etapa é o que faz a pessoa achar que
    # terminou.
    passos = models.JSONField(default=list, blank=True)

    # Quando o campo de valor aparece. `None` = sempre que `exige_valor`.
    # Existe por causa do treinamento: curso interno da empresa não tem preço a
    # informar, e um campo "Valor *" obrigatório num ramo que não tem valor
    # trava o pedido inteiro num campo que não faz sentido responder.
    valor_quando = models.JSONField(null=True, blank=True)

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
        #
        # Campo CONDICIONAL (`quando`) não entra na conta, e a razão é a mesma
        # que criou a regra: o teto existe para limitar o que a pessoa vê de uma
        # vez. Os dados do técnico terceiro só aparecem para quem responde
        # "é para um terceiro" — para todo mundo mais eles não existem, e
        # contá-los faria a regra proibir justamente a pergunta que evita o
        # formulário genérico com tudo à mostra.
        livres = [
            c for c in self.campos if c.get("obrigatorio") and not c.get("quando")
        ]
        if len(livres) > 3:
            raise ValidationError(
                {
                    "campos": (
                        f"{len(livres)} campos obrigatórios sem condição. O máximo "
                        "é 3 — o resto deve vir da identidade da pessoa, ou "
                        "aparecer só no ramo em que faz sentido."
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


# Por quantos dias depois de concluído o pedido ainda aceita "não resolveu".
#
# Prazo e não "para sempre": reabrir um pedido fechado há oito meses ressuscita
# trabalho que já morreu, e o atendente que recebe não tem como reconstruir o
# que aconteceu. Sete dias é o tempo de usar o que foi entregue e descobrir que
# não serve — a senha que não funciona, o notebook que volta a travar.
#
# Passado o prazo, o caminho é abrir outro pedido, que é o certo: aquilo já é
# problema novo.
PRAZO_REABERTURA_DIAS = 7


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

    # Quem ASSUMIU o atendimento depois da aprovação. Sem dono, o pedido fica
    # esperando "o setor" — e setor nenhum atende nada. `SET_NULL` porque a
    # pessoa pode sair da empresa sem que o histórico do pedido se perca.
    atendente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="atendimentos",
    )

    # Quantas vezes quem pediu disse "não resolveu" depois de concluído.
    #
    # Contador denormalizado, e o histórico continua sendo a verdade: a taxa de
    # reabertura é O indicador de que "concluído" significa alguma coisa, e ela
    # precisa ser contável sem varrer a linha do tempo de todos os pedidos.
    # Também é o que a fila lê para marcar a linha — sem o contador, cada tela
    # de fila carregaria os eventos de cada pedido só para saber se voltou.
    reaberturas = models.PositiveSmallIntegerField(default=0)

    # O adiantamento do qual ESTE pedido presta contas. FK para a própria
    # tabela porque adiantamento e reembolso são o mesmo tipo de coisa — um
    # pedido do catálogo — e um campo de texto "adiantamento nº 12" não fecha
    # conta nenhuma. `PROTECT` para não apagar o adiantamento por baixo de uma
    # prestação de contas já feita.
    adiantamento = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="prestacoes",
        help_text="Preenchido quando este reembolso presta contas de um adiantamento.",
    )

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
        return f"{self.item.nome} · {self.solicitante.get_full_name()}"

    @property
    def dias_para_concluir(self) -> int | None:
        """Dias entre pedido e conclusão. É o que alimenta o prazo REAL medido."""
        if self.concluido_em is None:
            return None
        return (self.concluido_em - self.criado_em).days

    @property
    def em_aberto(self) -> bool:
        return self.situacao not in (SituacaoServico.CONCLUIDA, SituacaoServico.CANCELADA)

    @property
    def prazo_reabertura(self):
        """Até quando este pedido aceita "não resolveu". `None` fora do caso.

        A data existe na tela por um motivo: sem ela, o botão simplesmente some
        um dia e a pessoa acha que o sistema quebrou.
        """
        if self.situacao != SituacaoServico.CONCLUIDA or self.concluido_em is None:
            return None
        return self.concluido_em + timedelta(days=PRAZO_REABERTURA_DIAS)

    @property
    def motivo_reabertura(self) -> str:
        """O que quem pediu disse que continua sem resolver.

        Vem do histórico e não de um campo próprio: o motivo já é escrito lá, e
        uma segunda cópia seria mais uma coisa para as duas ficarem diferentes.

        Sai pelo atalho quando o pedido nunca voltou — que é o caso de quase
        toda linha de fila —, então a consulta aos eventos só acontece nas
        poucas que interessam.
        """
        if not self.reaberturas:
            return ""

        from workspace.models.evento import AcaoSolicitacao

        for evento in reversed(list(self.eventos.all())):
            if evento.acao == AcaoSolicitacao.REABERTA:
                return evento.observacao
        return ""

    @property
    def pode_reabrir(self) -> bool:
        """Só o que foi CONCLUÍDO, e dentro do prazo.

        Cancelado não entra: cancelar é ato de quem pediu, e não há entrega
        para contestar. Devolvido também não — já está de volta com a pessoa.
        """
        limite = self.prazo_reabertura
        return limite is not None and timezone.now() < limite

    @property
    def total_despesas(self):
        """A soma das compras. `None` quando o pedido não é item a item.

        `None` e não zero: zero diria "somei e deu nada", quando a verdade é
        que não há o que somar — e é essa diferença que a tela usa para decidir
        entre mostrar a lista de compras e mostrar o campo de valor.
        """
        from decimal import Decimal

        linhas = list(self.despesas.all())
        if not linhas:
            return None
        return sum((linha.valor for linha in linhas), Decimal("0"))

    def concluir(self) -> None:
        self.situacao = SituacaoServico.CONCLUIDA
        self.concluido_em = timezone.now()
        self.save(update_fields=["situacao", "concluido_em"])
