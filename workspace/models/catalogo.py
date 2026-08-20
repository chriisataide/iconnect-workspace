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

    # Quando preenchido, o card LEVA PARA FORA em vez de abrir formulário.
    #
    # É o §11 do pedido: o chamado predial é aberto no iConnect Platform, e o
    # Workspace não deve recriar o sistema de chamados. Sem este campo, a única
    # forma de atender isso seria um item de catálogo que finge ser formulário e
    # redireciona no POST — pior de todas as formas, porque a pessoa preenche
    # antes de descobrir que vai para outro sistema.
    #
    # O card marca visivelmente que sai daqui: link que muda de produto sem
    # avisar é o que faz alguém perder o que digitou.
    url_externa = models.URLField(
        max_length=300, blank=True,
        help_text="Preenchido, o card abre este endereço em vez do formulário.",
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
    def leva_para_fora(self) -> bool:
        """O card sai do Workspace em vez de abrir formulário."""
        return bool(self.url_externa)

    @property
    def campos_obrigatorios(self) -> list[str]:
        return [c["chave"] for c in self.campos if c.get("obrigatorio")]


class SituacaoServico(models.TextChoices):
    # O começo da vida do pedido, e o estado que faltava — §43.
    #
    # Sem ele, o formulário longo (prestação de contas, compra com anexo,
    # requisição com dez campos) era tudo-ou-nada: quem não tinha o comprovante
    # à mão perdia o que já tinha digitado ao sair da tela. Na prática as
    # pessoas resolviam isso digitando tudo no bloco de notas primeiro, e o
    # produto virava a segunda etapa de um processo que começava fora dele.
    #
    # Rascunho NÃO é "em aberto": nada foi enviado, ninguém foi avisado, nenhum
    # prazo começou a correr e nenhum orçamento foi comprometido. Confundir os
    # dois faria o painel da área contar como trabalho atrasado um formulário
    # que ninguém nunca mandou.
    RASCUNHO = "rascunho", "Rascunho"
    AGUARDANDO_APROVACAO = "aguardando_aprovacao", "Aguardando aprovação"
    APROVADA = "aprovada", "Aprovada"
    EM_ATENDIMENTO = "em_atendimento", "Em atendimento"
    CONCLUIDA = "concluida", "Concluída"
    DEVOLVIDA = "devolvida", "Devolvida"
    # O "não" definitivo, que o produto não sabia dizer.
    #
    # Devolver e reprovar pareciam a mesma coisa e não são: devolver diz
    # "corrija e reenvie" — é um pedido vivo esperando ação de quem pediu.
    # Reprovar diz "não vai acontecer". Sem os dois, o gestor que quer negar só
    # tinha a devolução, e o pedido que deveria morrer voltava em ciclo até
    # alguém desistir por cansaço. Um pedido reprovado é TERMINAL, como
    # cancelado — e ao contrário de cancelado, ele teve um autor e um motivo.
    REJEITADA = "rejeitada", "Reprovada"
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


#: Fim de linha — nada mais acontece com o pedido, e ninguém precisa agir.
#: Em UM lugar porque a lista estava copiada em `abertas()`, em LST.ABERTAS e
#: na conta do trilho, e as três discordariam no dia em que um estado novo
#: aparecesse. Foi o que aconteceu com `REJEITADA`.
SITUACOES_TERMINAIS = (
    SituacaoServico.CONCLUIDA,
    SituacaoServico.REJEITADA,
    SituacaoServico.CANCELADA,
)


#: Ainda não entrou na esteira — §43. Nada foi enviado, ninguém foi avisado,
#: nenhum prazo corre.
#:
#: Separado dos terminais porque não é fim: é antes do começo. As duas listas
#: existem para a mesma pergunta ("isto conta como trabalho?"), e a resposta é
#: não pelos dois motivos opostos.
SITUACOES_NAO_ENVIADAS = (SituacaoServico.RASCUNHO,)


#: O que NÃO é trabalho em andamento: já acabou, ou nunca começou.
#: Em um lugar porque a soma aparece no filtro da tela, no contador do trilho e
#: no painel de indicadores — e a cópia que esquece uma das duas é a que faz o
#: painel contar rascunho como pedido atrasado.
SITUACOES_FORA_DA_ESTEIRA = SITUACOES_TERMINAIS + SITUACOES_NAO_ENVIADAS


class SolicitacaoServicoQuerySet(models.QuerySet):
    def de(self, pessoa):
        return self.filter(solicitante=pessoa)

    def abertas(self):
        return self.exclude(situacao__in=SITUACOES_FORA_DA_ESTEIRA)

    def rascunhos(self):
        return self.filter(situacao=SituacaoServico.RASCUNHO)

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
    def esperando_decisao_de(self) -> str:
        """De quem é a etapa da vez — pessoa ou papel —, ou `""`.

        Etapa NOMINAL devolve o nome curto de quem decide; etapa por PAPEL
        devolve o nome do papel, porque ela não é de ninguém em particular: é
        de quem tiver o crachá. Chamá-la pelo papel é o certo — "Financeiro" é
        a resposta útil, e listar as três pessoas que o ocupam hoje seria uma
        etiqueta que muda quando alguém sai de férias.

        Barato em lista: `etapa_atual` usa o `prefetch` quando ele existe, e
        `catalogo.minhas()` e `atendimento.fila_de()` o trazem.
        """
        aprovacao = self.aprovacao
        if aprovacao is None:
            return ""
        etapa = aprovacao.etapa_atual
        if etapa is None:
            return ""
        if etapa.aprovador_id:
            return etapa.aprovador.get_short_name() or etapa.aprovador.get_full_name()
        return etapa.papel.nome if etapa.papel_id else ""

    @property
    def area_responsavel(self) -> str:
        """A área que executa este pedido, pelo nome — ou `""` quando não há.

        Sai do papel que declara `<raiz>.atender`, que é a MESMA fonte do
        roteamento da fila. Uma tabela de nomes escrita à parte diria o que
        alguém achava que era verdade, e a primeira divergência apareceria
        justamente quando alguém criasse uma área nova.
        """
        from workspace.services.atendimento import area_de

        return area_de(self.item.dominio)

    @property
    def fase(self) -> str:
        """O que a tela diz, e não só o nome do estado — §43.

        "Aprovada" é tecnicamente certo e produziu a queixa: a pessoa lê
        "Aprovada", não encontra o pedido em "Concluídas", vê que ele continua em
        "Em aberto", e conclui que a máquina de estados está quebrada.

        A máquina está certa; a palavra é que não diz a fase. Aprovado é MEIO DO
        CAMINHO — significa "liberado, esperando a área executar" —, e é isso
        que a frase precisa dizer.

        Derivada e não gravada: uma coluna com este texto ao lado de `situacao`
        seria uma segunda fonte de verdade sobre a mesma coisa, e a primeira a
        divergir.
        """
        from workspace.models.catalogo import SituacaoServico as S

        if self.situacao == S.RASCUNHO:
            # "Rascunho" sozinho deixa a dúvida que importa: já mandei ou não?
            return "Rascunho · não enviado"
        if self.situacao == S.APROVADA:
            # A ÁREA TEM NOME. "aguardando a área" resolveu metade do §43 e
            # deixou a outra metade: quem pediu adiantamento, viu o gestor
            # aprovar e leu isto foi procurar no Financeiro sem saber se era ali.
            # Sem área nenhuma a frase muda de assunto — o pedido está numa fila
            # que ninguém pode abrir, e isso é o que a tela precisa contar.
            area = self.area_responsavel
            return f"Aprovada · aguardando {area}" if area else "Aprovada · sem área responsável"
        if self.situacao == S.EM_ATENDIMENTO:
            if self.atendente_id:
                return f"Em andamento · {self.atendente.get_short_name() or self.atendente.get_full_name()}"
            area = self.area_responsavel
            return f"Em andamento · {area}" if area else "Em andamento"
        if self.situacao == S.DEVOLVIDA:
            return "Devolvida · esperando você corrigir"
        if self.situacao == S.AGUARDANDO_APROVACAO:
            # QUEM está segurando, e não só "alguém". Sem o nome, o pedido de
            # adiantamento cujo gestor já aprovou continua dizendo a mesma frase
            # de antes de ele aprovar — e quem pediu conclui que o clique do
            # gestor não fez nada. Fez: a cadeia andou um degrau, e o degrau
            # seguinte é de outra pessoa.
            quem = self.esperando_decisao_de
            return f"Aguardando aprovação · {quem}" if quem else "Aguardando aprovação"
        return self.get_situacao_display()

    @property
    def dias_para_concluir(self) -> int | None:
        """Dias entre pedido e conclusão. É o que alimenta o prazo REAL medido."""
        if self.concluido_em is None:
            return None
        return (self.concluido_em - self.criado_em).days

    @property
    def prioridade(self) -> str:
        """`atrasado`, `no_limite` ou `normal` — §7.

        DERIVADA do prazo prometido, e nunca declarada por quem pede. Prioridade
        declarada é sempre a mesma história: no primeiro mês todo mundo marca
        "normal", no terceiro todo mundo marca "urgente", e a coluna deixa de
        significar qualquer coisa — sem que ninguém tenha feito nada errado.

        A régua é o prazo que a pessoa VIU quando pediu. Cobrar por outro seria
        mudar a medida depois do jogo.
        """
        if not self.em_aberto:
            return "normal"
        prometido = self.item.prazo_prometido_dias or 0
        corridos = (timezone.now() - self.criado_em).days
        if corridos > prometido:
            return "atrasado"
        if corridos >= prometido - 1:
            return "no_limite"
        return "normal"

    @property
    def prioridade_rotulo(self) -> str:
        return {
            "atrasado": "Atrasado",
            "no_limite": "Vence hoje",
            "normal": "No prazo",
        }[self.prioridade]

    @property
    def e_rascunho(self) -> bool:
        """A tela não compara string de estado — a regra do design system é que
        a view (ou o model) resolve e o template desenha."""
        return self.situacao == SituacaoServico.RASCUNHO

    @property
    def pode_reenviar(self) -> bool:
        """Voltou para quem pediu e está esperando correção.

        Propriedade e não comparação de string no template: a regra do design
        system é que o model (ou a view) resolve e o template desenha. E é uma
        pergunta que três telas fazem — a lista, o formulário e o resumo.
        """
        from workspace.models.catalogo import SituacaoServico as S

        return self.situacao == S.DEVOLVIDA

    @property
    def em_aberto(self) -> bool:
        """Vivo na esteira: já foi enviado e ainda não terminou.

        Derivado de `SITUACOES_FORA_DA_ESTEIRA`, e não de uma lista escrita à
        mão. Era escrita à mão — `(CONCLUIDA, CANCELADA)` — e por isso um pedido
        REPROVADO continuava "em aberto" meses depois de o gestor ter dito não:
        exatamente o defeito que o comentário de `SITUACOES_TERMINAIS` avisa que
        acontece quando a mesma lista mora em dois lugares.
        """
        return self.situacao not in SITUACOES_FORA_DA_ESTEIRA

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
