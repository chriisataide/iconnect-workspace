"""O espelho — o que veio de fora, normalizado, com procedência.

## O que este app NÃO tem

Nenhuma view de criação ou edição. Nenhum formulário. Nenhuma tela. Se alguém
pedir um, a resposta é: **o dado nasce onde é operado**. Um `Contrato` editável
aqui produziria duas verdades sobre a vigência — a do Platform e a nossa — e a
nossa venceria em silêncio na próxima carga, ou não venceria, dependendo do
conector. As duas hipóteses são ruins.

O `/admin/` expõe estes models em somente leitura pela mesma razão.

## Por que `fonte` e `carga` não são ForeignKey

`FonteDados` e `ExecucaoCarga` moram em `cargas`. Uma FK daqui para lá faria
`resultados` importar `cargas`, e a direção é a outra: `cargas` escreve aqui.
Duas FKs cruzadas entre dois apps é um ciclo, e ciclo entre apps é como o grafo
de migração vira um problema de fim de semana.

O acoplamento frouxo é o mesmo que `EntradaIndice` já usa com `dominio` +
`origem_id`, e pelo mesmo motivo: **o espelho sobrevive à origem**. Apagar o
registro de uma carga antiga não pode apagar o resultado de agosto junto.

O preço é não ter integridade referencial no `carga_id`. É um preço aceitável
para dado que só é escrito por um carregador, e que tem `test_carga_referencia_execucao_que_existe`
cobrindo o que o banco deixou de cobrir.

## `layer` não é campo — e isto é decisão, não esquecimento

Layer sai da ROB de 6 meses, e a ROB muda todo mês. Gravado, ele viraria a
resposta do dia da carga, e um contrato que cresceu em julho continuaria Layer 1
até alguém rodar de novo — sem nada na tela dizendo que o número está velho.
Ver `resultados/services.py::layer_de`.
"""

from __future__ import annotations

from django.db import models


class Fonte(models.TextChoices):
    """As fontes conhecidas. Espelho do `FonteDados.chave`, em vocabulário.

    Duplicado aqui de propósito — `resultados` não importa `cargas`. É uma lista
    curta e estável; se divergir, `test_as_duas_listas_de_fonte_batem` reprova.
    """

    SANKHYA = "sankhya", "Sankhya"
    MONDAY = "monday", "monday.com"
    PLATFORM = "iconnect_platform", "iConnect Platform"
    CSV = "csv", "Carga por arquivo"
    MANUAL = "manual", "Lançamento manual"
    #: O PNCP é a única fonte PÚBLICA da lista, e a única que não exige
    #: credencial: a Lei 14.133/2021 obriga a publicação, e a API de consulta é
    #: aberta. As outras três descrevem o que a empresa JÁ tem; esta descreve o
    #: que ela ainda pode buscar.
    PNCP = "pncp", "PNCP · contratações públicas"


class ProcedenciaMixin(models.Model):
    """Fonte, chave de origem e instante da carga. Em todo model deste app."""

    fonte = models.CharField(max_length=30, choices=Fonte.choices, db_index=True)
    #: O id no sistema de origem. É o que torna "de onde vem esse número" uma
    #: pergunta com resposta acionável: com ele dá para abrir o Sankhya e
    #: conferir a linha; sem ele sobra uma marca de fonte.
    chave_externa = models.CharField(max_length=120, db_index=True)
    #: `ExecucaoCarga.pk`. Inteiro e não FK — ver o cabeçalho do módulo.
    carga_id = models.PositiveBigIntegerField(null=True, blank=True, db_index=True)
    importado_em = models.DateTimeField(auto_now=True, db_index=True)
    #: SHA-256 do payload normalizado. É o que faz reprocessar a mesma janela
    #: não tocar em nada: conteúdo igual não escreve, e `importado_em` não
    #: avança. Sem isto, rodar a carga de novo por precaução marcaria o espelho
    #: inteiro como recém-atualizado e a idade do dado viraria ficção.
    hash_conteudo = models.CharField(max_length=64, blank=True)

    class Meta:
        abstract = True

    @property
    def procedencia(self):
        from workspace.providers.resultados import Procedencia

        return Procedencia(
            fonte=self.fonte,
            chave_externa=self.chave_externa,
            carregado_em=self.importado_em,
        )


class ServicoContrato(models.TextChoices):
    CFTV = "cftv", "CFTV"
    ALARME = "alarme", "Alarme"
    MONITORAMENTO = "monitoramento", "Monitoramento"
    INSTALACAO = "instalacao", "Instalação"
    MANUTENCAO = "manutencao", "Manutenção"


class StatusContrato(models.TextChoices):
    ATIVO = "ativo", "Ativo"
    ENCERRADO = "encerrado", "Encerrado"
    EM_RENOVACAO = "em_renovacao", "Em renovação"


class Contrato(ProcedenciaMixin):
    codigo = models.CharField(max_length=40, unique=True)
    nome_cliente = models.CharField(max_length=160)
    servico = models.CharField(max_length=20, choices=ServicoContrato.choices)
    #: CÓDIGO e não FK para `financas.CentroCusto`. `resultados` não conhece o
    #: domínio financeiro, e a conciliação entre os dois lados é justamente o
    #: que a regra de exceção 19 existe para vigiar — uma FK esconderia a
    #: divergência ao recusar a carga em vez de registrá-la.
    centro_custo = models.CharField(max_length=20, db_index=True)
    regional = models.CharField(max_length=60, blank=True, db_index=True)
    inicio_vigencia = models.DateField(null=True, blank=True)
    fim_vigencia = models.DateField(null=True, blank=True, db_index=True)
    valor_mensal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    status = models.CharField(
        max_length=20, choices=StatusContrato.choices,
        default=StatusContrato.ATIVO, db_index=True,
    )

    class Meta:
        ordering = ["nome_cliente", "codigo"]
        verbose_name = "contrato"
        verbose_name_plural = "contratos"
        constraints = [
            models.UniqueConstraint(
                fields=["fonte", "chave_externa"], name="res_contrato_origem_unica"
            )
        ]
        indexes = [
            models.Index(fields=["status", "fim_vigencia"], name="res_contrato_venc_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.nome_cliente}"


class CompetenciaResultado(ProcedenciaMixin):
    """Um mês de um contrato — ou de um centro de custo, quando `contrato` é nulo.

    As duas granularidades no mesmo model de propósito: a faixa financeira soma
    por centro de custo e detalha por contrato, e separá-las em duas tabelas
    obrigaria toda consulta a unir as duas para responder qualquer coisa.
    """

    contrato = models.ForeignKey(
        Contrato, on_delete=models.CASCADE, null=True, blank=True,
        related_name="competencias",
    )
    centro_custo = models.CharField(max_length=20, db_index=True)
    ano = models.PositiveSmallIntegerField(db_index=True)
    mes = models.PositiveSmallIntegerField(db_index=True)

    receita_bruta = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    impostos = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    custo_direto = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    custo_indireto = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    margem_contribuicao = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    ebitda = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    #: A COLUNA DO MEIO do benchmark: o que a operação declara que já aconteceu
    #: e ainda não bateu na contabilidade. Sem ela, a reunião vira briga sobre o
    #: número em vez de decisão sobre o que fazer.
    ajuste_potencial = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    #: NULO quando não há orçamento para este centro de custo nesta competência.
    #: `null` e não zero: "sem orçado" e "orçado zero" produzem leituras opostas
    #: — a primeira é uma conciliação a resolver, a segunda é um teto de fato.
    receita_orcada = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
    custo_orcado = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
    margem_orcada = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )

    class Meta:
        ordering = ["-ano", "-mes", "centro_custo"]
        verbose_name = "competência de resultado"
        verbose_name_plural = "competências de resultado"
        constraints = [
            models.UniqueConstraint(
                fields=["fonte", "chave_externa"], name="res_competencia_origem_unica"
            ),
            # Competência duplicada é o defeito que mais suja relatório
            # executivo: a receita do mês simplesmente dobra, e ninguém percebe
            # porque o número continua plausível.
            models.UniqueConstraint(
                fields=["contrato", "ano", "mes"],
                condition=models.Q(contrato__isnull=False),
                name="res_competencia_contrato_unica",
            ),
            models.UniqueConstraint(
                fields=["centro_custo", "ano", "mes"],
                condition=models.Q(contrato__isnull=True),
                name="res_competencia_cc_unica",
            ),
        ]

    def __str__(self) -> str:
        alvo = self.contrato.codigo if self.contrato_id else self.centro_custo
        return f"{alvo} · {self.mes:02d}/{self.ano}"

    @property
    def tem_orcado(self) -> bool:
        return self.receita_orcada is not None


class SituacaoProjeto(models.TextChoices):
    NAO_INICIADO = "nao_iniciado", "Não iniciado"
    EM_ANDAMENTO = "em_andamento", "Em andamento"
    CONCLUIDO = "concluido", "Concluído"
    CANCELADO = "cancelado", "Cancelado"


class Projeto(ProcedenciaMixin):
    codigo = models.CharField(max_length=40, unique=True)
    nome = models.CharField(max_length=200)
    cliente = models.CharField(max_length=160, blank=True)
    contrato = models.ForeignKey(
        Contrato, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="projetos",
    )
    #: NOME e não FK para `Pessoa`. O responsável vem do monday, onde ele é um
    #: usuário do monday — casar isso com o organograma exige o SSO (ADR-013), e
    #: até lá uma FK produziria projeto órfão a cada pessoa que existe lá e não
    #: existe aqui.
    responsavel = models.CharField(max_length=160, blank=True)
    situacao = models.CharField(
        max_length=20, choices=SituacaoProjeto.choices,
        default=SituacaoProjeto.EM_ANDAMENTO, db_index=True,
    )
    inicio = models.DateField(null=True, blank=True)
    prazo = models.DateField(null=True, blank=True, db_index=True)
    percentual_concluido = models.PositiveSmallIntegerField(default=0)
    bloqueado = models.BooleanField(default=False, db_index=True)
    motivo_bloqueio = models.CharField(max_length=300, blank=True)
    #: Última mexida no projeto do lado de lá. É o que responde "projeto sem
    #: movimento há N dias" sem confundir com a idade da nossa carga.
    movimentado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["prazo", "nome"]
        verbose_name = "projeto"
        verbose_name_plural = "projetos"
        constraints = [
            models.UniqueConstraint(
                fields=["fonte", "chave_externa"], name="res_projeto_origem_unica"
            )
        ]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.nome}"


class MarcoProjeto(ProcedenciaMixin):
    projeto = models.ForeignKey(
        Projeto, on_delete=models.CASCADE, related_name="marcos"
    )
    titulo = models.CharField(max_length=200)
    prazo = models.DateField(null=True, blank=True, db_index=True)
    concluido_em = models.DateField(null=True, blank=True)
    responsavel = models.CharField(max_length=160, blank=True)

    class Meta:
        ordering = ["prazo", "titulo"]
        verbose_name = "marco de projeto"
        verbose_name_plural = "marcos de projeto"
        constraints = [
            models.UniqueConstraint(
                fields=["fonte", "chave_externa"], name="res_marco_origem_unica"
            )
        ]

    def __str__(self) -> str:
        return f"{self.projeto.codigo} · {self.titulo}"


class QuadroPessoas(ProcedenciaMixin):
    centro_custo = models.CharField(max_length=20, db_index=True)
    ano = models.PositiveSmallIntegerField(db_index=True)
    mes = models.PositiveSmallIntegerField(db_index=True)
    efetivo_ativo = models.PositiveIntegerField(default=0)
    admissoes = models.PositiveIntegerField(default=0)
    rescisoes = models.PositiveIntegerField(default=0)
    turnover_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    absenteismo_pct = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    vagas_abertas = models.PositiveIntegerField(default=0)
    vagas_fechadas_no_prazo = models.PositiveIntegerField(default=0)
    em_ferias = models.PositiveIntegerField(default=0)
    afastados = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-ano", "-mes", "centro_custo"]
        verbose_name = "quadro de pessoas"
        verbose_name_plural = "quadros de pessoas"
        constraints = [
            models.UniqueConstraint(
                fields=["fonte", "chave_externa"], name="res_quadro_origem_unica"
            ),
            models.UniqueConstraint(
                fields=["centro_custo", "ano", "mes"], name="res_quadro_cc_unico"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.centro_custo} · {self.mes:02d}/{self.ano}"


class Apontamento(ProcedenciaMixin):
    centro_custo = models.CharField(max_length=20, db_index=True)
    ano = models.PositiveSmallIntegerField(db_index=True)
    mes = models.PositiveSmallIntegerField(db_index=True)
    horas_normais = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    he_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    he_ineficiencia = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    he_servico_extra = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    he_sem_classificacao = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    hora_escala = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    hora_abono = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    hora_desconto = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    hora_noturna = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    banco_horas_saldo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    folhas_ponto_pendentes = models.PositiveIntegerField(default=0)
    contratos_pendentes_assinatura = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["-ano", "-mes", "centro_custo"]
        verbose_name = "apontamento"
        verbose_name_plural = "apontamentos"
        constraints = [
            models.UniqueConstraint(
                fields=["fonte", "chave_externa"], name="res_apontamento_origem_unica"
            ),
            models.UniqueConstraint(
                fields=["centro_custo", "ano", "mes"], name="res_apontamento_cc_unico"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.centro_custo} · {self.mes:02d}/{self.ano}"


class Classificacao(models.TextChoices):
    PROMOTOR = "promotor", "Promotor"
    NEUTRO = "neutro", "Neutro"
    DETRATOR = "detrator", "Detrator"


class AvaliacaoCliente(ProcedenciaMixin):
    """A pesquisa de satisfação, consolidada por contrato.

    O COMENTÁRIO entra; o autor não. Quem respondeu é pessoa do cliente, e o
    Workspace não é dono desse cadastro — trazer nome e e-mail para cá seria
    exatamente o detalhe operacional que a fronteira dos dois produtos existe
    para não atravessar.
    """

    contrato = models.ForeignKey(
        Contrato, on_delete=models.CASCADE, related_name="avaliacoes"
    )
    data = models.DateField(db_index=True)
    nota = models.PositiveSmallIntegerField()
    classificacao = models.CharField(
        max_length=12, choices=Classificacao.choices, db_index=True
    )
    comentario = models.TextField(blank=True)
    tratativa_aberta = models.BooleanField(default=False, db_index=True)
    tratativa_prazo = models.DateField(null=True, blank=True)
    tratativa_status = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["-data"]
        verbose_name = "avaliação de cliente"
        verbose_name_plural = "avaliações de cliente"
        constraints = [
            models.UniqueConstraint(
                fields=["fonte", "chave_externa"], name="res_avaliacao_origem_unica"
            )
        ]

    def __str__(self) -> str:
        return f"{self.contrato.codigo} · {self.get_classificacao_display()}"


class EditalPublico(ProcedenciaMixin):
    """Um edital com proposta aberta, espelhado do PNCP.

    ## Por que no espelho, e não direto em `workspace.models.marketing`

    `Oportunidade` é o radar da empresa: alguém cadastra, alguém decide, e o
    motivo do descarte fica guardado. É um registro NOSSO.

    Um edital não é nosso. Ele é publicado por um órgão, muda por conta dele, e
    some quando a proposta encerra. Gravá-lo em `Oportunidade` misturaria o que
    a empresa decidiu com o que o governo publicou — e, na primeira recarga,
    sobrescreveria o motivo que alguém escreveu à mão.

    Além disso, a direção da dependência não permite: `cargas` grava no espelho,
    e o app `workspace` nunca é escrito de fora. Espelhar aqui é a mesma regra
    dos outros seis modelos deste arquivo, com o mesmo carimbo e a mesma
    procedência.

    ## O elo com o radar

    Quando alguém decide disputar, o edital vira uma `Oportunidade` — copiada
    UMA vez, e a partir dali com vida própria. É o mesmo desenho do
    `Oportunidade.solicitacao`: o registro que decide é outro do que registra.

    ## `termo_casado` é o campo que permite ajustar o filtro

    A API do PNCP não filtra por palavra: a triagem é nossa, e ela é a única
    regra de negócio deste conector. Guardar QUAL termo casou é o que deixa o
    comercial ver o ruído e podar a lista — sem ele, "por que este edital de
    merenda entrou?" não tem resposta, e a lista de termos nunca melhora.
    """

    numero_controle = models.CharField(max_length=60, db_index=True)
    objeto = models.TextField()
    orgao = models.CharField(max_length=200, blank=True)
    unidade = models.CharField(max_length=200, blank=True)
    uf = models.CharField(max_length=2, db_index=True)
    municipio = models.CharField(max_length=120, blank=True)
    modalidade = models.CharField(max_length=80, blank=True)
    valor_estimado = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
    abertura_proposta = models.DateTimeField(null=True, blank=True)
    #: A RAZÃO DE O RADAR EXISTIR: a data em que a decisão precisa acontecer.
    #: `db_index` porque toda consulta da tela ordena ou filtra por ela.
    encerramento_proposta = models.DateTimeField(null=True, blank=True, db_index=True)
    #: Qual termo da triagem casou. Ver o cabeçalho.
    termo_casado = models.CharField(max_length=80, blank=True, db_index=True)
    link = models.URLField(max_length=500, blank=True)

    class Meta:
        ordering = ["encerramento_proposta"]
        verbose_name = "edital público"
        verbose_name_plural = "editais públicos"
        constraints = [
            models.UniqueConstraint(
                fields=["fonte", "chave_externa"], name="res_edital_origem_unica"
            )
        ]

    def __str__(self) -> str:
        return f"{self.numero_controle} · {self.objeto[:40]}"
