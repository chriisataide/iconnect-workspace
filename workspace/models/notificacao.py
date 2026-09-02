"""Notificação do Workspace.

## Por que não reusar `dashboard.Notification`

Aquele model existe e funciona, mas é do iConnect: os sete tipos são todos de
ticket e SLA, há uma FK para `Ticket`, e o vocabulário de cor é do Bootstrap
(`primary`, `danger`). Usá-lo significaria acrescentar tipos de Workspace a um
enum de operação e carregar uma FK morta em cada linha.

O que NÃO se faz é aceitar dois sinos. A `Central de Notificações` do Workspace
federa as duas origens pelo contrato de provider (`pending_items`,
`workspace/providers/base.py`) — uma tela, duas fontes, zero acoplamento. É a
mesma decisão de `Compromisso` vs. `MovimentacaoFinanceira`.

## Acoplamento frouxo, como no resto do Workspace

`dominio` + `origem_id` em vez de `GenericForeignKey`, igual a
`SolicitacaoAprovacao`. Uma notificação sobrevive ao objeto que a gerou: se o
pedido é apagado, o aviso "seu reembolso foi devolvido" continua fazendo sentido
no histórico, e uma FK com `CASCADE` o apagaria justamente quando ele importa
para entender o que aconteceu.
"""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class TipoNotificacao(models.TextChoices):
    """O que aconteceu. Um tipo por evento que tem UM destinatário claro.

    Fan-out (comunicado para a empresa inteira) fica fora de propósito: exige
    público-alvo, que é do domínio CNT/COM e entra na onda C.
    """

    VEZ_DE_APROVAR = "vez_de_aprovar", "Chegou sua vez de aprovar"
    PEDIDO_APROVADO = "pedido_aprovado", "Seu pedido foi aprovado"
    PEDIDO_DEVOLVIDO = "pedido_devolvido", "Seu pedido foi devolvido"
    PEDIDO_REJEITADO = "pedido_rejeitado", "Seu pedido foi reprovado"
    PEDIDO_CANCELADO = "pedido_cancelado", "Seu pedido foi cancelado"
    # O que faltava para o ciclo fechar: depois de aprovado, alguém ATENDE.
    PEDIDO_EM_ATENDIMENTO = "pedido_em_atendimento", "Seu pedido está sendo atendido"
    PEDIDO_CONCLUIDO = "pedido_concluido", "Seu pedido foi concluído"
    # O único aviso que vai para o ATENDENTE, e não para quem pediu: é a
    # resposta de quem recebeu a entrega dizendo que ela não resolveu.
    PEDIDO_REABERTO = "pedido_reaberto", "Um pedido que você atendeu foi reaberto"
    # Vai para a ÁREA QUE EXECUTA, e não para quem pediu: o pedido acabou de
    # cair na fila dela. Sem este aviso a área só descobre trabalho novo abrindo
    # a tela da fila, e o pedido aprovado numa sexta espera até alguém lembrar
    # de olhar — que foi como o produto passou a parecer que "aprovar devolve
    # para o solicitante".
    PEDIDO_NA_FILA = "pedido_na_fila", "Chegou um pedido para a sua área"
    # Vai para quem PODE CONSERTAR, e não para quem pediu: a etapa parou num
    # papel que ninguém ocupa, e só quem concede papel tira o pedido dali.
    APROVACAO_SEM_DONO = "aprovacao_sem_dono", "Um pedido parou num papel sem ninguém"
    # Alguém comentou no pedido — §45. Vai para o OUTRO LADO: se quem atende
    # comentou, avisa quem pediu, e vice-versa. Sem isto o comentário é um
    # bilhete deixado numa tela que a pessoa não vai abrir.
    COMENTARIO_NO_PEDIDO = "comentario_no_pedido", "Comentaram no seu pedido"
    # Habilitação vencendo — §28. Vai para a PESSOA e para quem responde por
    # ela: a pessoa agenda a reciclagem, e quem responde descobre que ela não
    # agendou. Um destinatário só quebra um dos dois lados.
    HABILITACAO_A_VENCER = "habilitacao_a_vencer", "Habilitação vencendo ou vencida"
    # Equipamento entregue no nome de alguém — §17. Vai para QUEM RECEBEU, e é
    # o que transforma o registro em termo de responsabilidade: sem o aviso, a
    # pessoa passa a responder por um equipamento sem nunca ter sido informada.
    EQUIPAMENTO_SOB_CUSTODIA = (
        "equipamento_sob_custodia",
        "Um equipamento está sob sua responsabilidade",
    )
    # §23 — prazo de decisão de uma oportunidade de marketing. Vai para quem
    # opera marketing, e não só para o responsável da linha: o responsável pode
    # estar de férias, e o prazo do edital não espera.
    PRAZO_DE_OPORTUNIDADE = (
        "prazo_de_oportunidade",
        "Prazo para decidir sobre uma oportunidade",
    )
    # §37 — leitura obrigatória pendente. Vai para CADA pessoa alcançada pelo
    # público-alvo, e é o que separa "a empresa publicou" de "a empresa
    # informou": sem o aviso, a confirmação de leitura só acontece para quem
    # abre o Meu dia por conta própria — e é justamente essa confirmação que se
    # leva para auditoria de ISO ou para defesa trabalhista.
    LEITURA_OBRIGATORIA = "leitura_obrigatoria", "Documento com leitura obrigatória"
    # §37 — documento normativo vencendo. Vai para o DONO: `publicados()` tira
    # o vencido da vitrine, então um POP que passa da vigência simplesmente
    # SOME do acervo sem ninguém ser avisado. As pessoas continuam precisando do
    # procedimento; ele deixou de existir na tela.
    DOCUMENTO_A_VENCER = "documento_a_vencer", "Documento vencendo ou vencido"
    # §Onda 4 — uma regra do painel de exceções encontrou coisa que exige ação.
    #
    # Um aviso por PESSOA e por REGRA, nunca por ocorrência: quarenta avisos
    # sobre a mesma regra transformam o sino num lugar que se aprende a ignorar,
    # e o aviso que importa some junto.
    EXCECAO_ABERTA = "excecao_aberta", "Uma regra de exceção exige atenção"
    # Documento de veículo vencendo — §18. Vai para quem OPERA a frota e não
    # para o último motorista: quem paga o IPVA e agenda a vistoria é
    # Suprimentos, e avisar quem dirigiu ontem transfere para a pessoa errada
    # uma responsabilidade que ela não pode cumprir.
    DOCUMENTO_DE_VEICULO = (
        "documento_de_veiculo",
        "Documento de veículo vencendo ou vencido",
    )
    CORRESPONDENCIA_RECEBIDA = (
        "correspondencia_recebida",
        "Chegou correspondência para você",
    )


class NotificacaoQuerySet(models.QuerySet):
    def de(self, pessoa):
        if pessoa is None or getattr(pessoa, "is_authenticated", False) is False:
            return self.none()
        return self.filter(destinatario=pessoa)

    def nao_lidas(self):
        return self.filter(lida_em__isnull=True)

    def recentes(self):
        return self.order_by("-criado_em")


class Notificacao(models.Model):
    """Um aviso para uma pessoa. Nunca para um grupo."""

    destinatario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notificacoes_workspace",
    )
    tipo = models.CharField(max_length=30, choices=TipoNotificacao.choices, db_index=True)
    titulo = models.CharField(max_length=200)
    corpo = models.CharField(max_length=300, blank=True)

    # Para onde o clique leva. Guardada como caminho e não como nome de rota:
    # a notificação é um registro histórico, e nome de rota muda.
    url = models.CharField(max_length=300, blank=True)

    dominio = models.CharField(max_length=40, blank=True, db_index=True)
    origem_id = models.CharField(max_length=64, blank=True, db_index=True)

    lida_em = models.DateTimeField(null=True, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True, db_index=True)

    objects = NotificacaoQuerySet.as_manager()

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "notificação"
        verbose_name_plural = "notificações"
        indexes = [
            # O acesso mais quente é o contador do sino:
            # WHERE destinatario=? AND lida_em IS NULL.
            models.Index(
                fields=["destinatario", "lida_em", "-criado_em"],
                name="wks_notif_sino_idx",
            ),
        ]
        # SEM constraint de unicidade, de propósito.
        #
        # A tentação é `UNIQUE(destinatario, tipo, dominio, origem_id)` para não
        # repetir aviso. Mas isso bloquearia repetição LEGÍTIMA: pedido devolvido
        # e reenviado chega de novo ao mesmo aprovador, e é um evento novo.
        #
        # E o modo de falha escolhe a si mesmo: constraint em aviso falha
        # SILENCIANDO a pessoa, que é pior que avisar duas vezes. O dedupe vive
        # em `services/notificacoes.py` e olha só o que está NÃO LIDO — se a
        # pessoa já leu e o evento voltou, ela merece saber.

    def __str__(self) -> str:
        return f"{self.get_tipo_display()} · {self.destinatario}"

    @property
    def lida(self) -> bool:
        return self.lida_em is not None

    def marcar_lida(self) -> None:
        if self.lida_em is None:
            self.lida_em = timezone.now()
            self.save(update_fields=["lida_em"])
