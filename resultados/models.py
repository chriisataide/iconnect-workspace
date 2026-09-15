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

from decimal import Decimal

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


#: O código reservado de "contrato sem área". Nenhuma `Area` pode usá-lo.
#:
#: Ele existe para que "sem área" seja uma OPÇÃO do filtro, e não um `NULL`
#: escondido. Número que some ao filtrar é a forma mais rápida de perder a
#: confiança da diretoria: quem soma as cinco áreas e não chega no total da
#: empresa para de acreditar na tela inteira, e com razão.
SEM_AREA = "sem-area"


class Area(models.Model):
    """Um conglomerado COMERCIAL de contratos. Não é divisão geográfica.

    ## Por que não herda `ProcedenciaMixin`, e isso não é esquecimento

    Todo o resto deste módulo é ESPELHO: veio de fora, tem fonte, chave externa
    e instante de carga. `Area` é o contrário — ela é registro NOSSO, cadastrado
    por quem administra, e nenhuma fonte externa a conhece.

    É a mesma distinção que separou `EditalPublico` de `Oportunidade`: o que a
    empresa escreve à mão não pode viver numa tabela que a carga da madrugada
    reescreve. Aqui a garantia é dupla — `Area` não está em `ENTIDADES`, e
    `Contrato.area` não vai no `dados` de nenhum conector, então o `_gravar` do
    carregador nunca a toca. Há teste afirmando isso.

    ## `Area` NÃO substitui `Contrato.regional`

    As duas parecem a mesma coisa e não são, e confundi-las quebra a permissão:

        regional   o nome da UNIDADE do organograma. É por ele que
                   `Escopo.regionais` recorta o que um gerente pode ver — ele
                   vem de `lotacao.unidade.nome`. É infraestrutura de
                   autorização, e não aparece em nenhum filtro da tela.

        area       o agrupamento comercial da carteira. É filtro de LEITURA,
                   nunca de permissão: ninguém é "lotado na Área 03".

    Trocar um pelo outro faria o gerente da unidade Sudeste não encontrar
    contrato nenhum, porque nenhuma área se chama "Sudeste".

    ## Editável sem migration, de propósito

    Contrato novo entra numa área por cadastro. O agrupamento comercial muda com
    a estratégia de vendas, e migração de dado a cada mudança de carteira é como
    o cadastro para de ser atualizado.
    """

    #: `"area-01"`. Slug e não inteiro: ele aparece na query string, e
    #: `?area=area-01` é legível no link que alguém cola num e-mail.
    codigo = models.SlugField(max_length=20, unique=True)
    nome = models.CharField(max_length=80)
    #: Os clientes que a área agrupa, em texto. Aparece no seletor porque
    #: ninguém sabe o que é "Área 03" sem ver o que tem dentro — e um filtro que
    #: exige conhecimento prévio é um filtro que só o autor usa.
    descricao = models.CharField(max_length=200, blank=True)
    ordem = models.PositiveSmallIntegerField(default=0)
    #: Área desativada some do SELETOR e não dos números. Os contratos dela
    #: continuam no total — desativar é dizer "não vendemos mais assim", não
    #: "esqueça o faturamento".
    ativa = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["ordem", "codigo"]
        verbose_name = "área"
        verbose_name_plural = "áreas"
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(codigo=SEM_AREA),
                name="res_area_codigo_reservado",
            )
        ]

    def __str__(self) -> str:
        return f"{self.nome} · {self.descricao}" if self.descricao else self.nome


class NaturezaConta(models.TextChoices):
    """O que a conta faz com o dinheiro. Decide o SINAL e o degrau da DRE."""

    RECEITA = "receita", "Receita"
    IMPOSTO = "imposto", "Imposto sobre faturamento"
    CUSTO = "custo", "Custo"
    FINANCEIRO = "financeiro", "Resultado financeiro"
    NAO_OPERACIONAL = "nao_operacional", "Não operacional"

    # NÃO EXISTE "custo indireto" AQUI, e a ausência é a correção de um erro
    # meu de 09/09/2026.
    #
    # Havia `INDIRETO`, e ele estava em `41601` DESPESAS GERAIS, `41602`
    # COMUNICAÇÕES, `41701` TRIBUTOS e `41801` DEPRECIAÇÕES. A cascata da DRE
    # somava só esses grupos no degrau "Indireto" e dava 88 mil, enquanto a
    # faixa do dinheiro logo acima mostrava 234 mil.
    #
    # A causa: o MESMO grupo carrega as duas coisas. A telefonia de um contrato
    # é custo direto dele; a telefonia da administração é rateio. O que faz um
    # custo ser indireto é a LINHA não ter contrato — e não a conta em que ela
    # foi lançada. Ver `cascata_da_dre`, que deriva o degrau daí.


class DegrauDRE(models.TextChoices):
    """O degrau da cascata a que o grupo pertence — C6.

    A ordem aqui É a ordem da cascata, e é por ela que o gráfico é montado.
    Guardá-la no banco em vez de numa lista no serviço tem um motivo: quando o
    plano de contas ganhar um grupo novo, ele precisa cair num degrau — e um
    grupo sem degrau tem de APARECER, não sumir da DRE em silêncio.
    """

    RECEITA_BRUTA = "receita_bruta", "Receita Bruta"
    IMPOSTOS = "impostos", "Impostos"
    PESSOAL = "pessoal", "Pessoal"
    ENCARGOS = "encargos", "Encargos e Provisões"
    BENEFICIOS = "beneficios", "Benefícios"
    MATERIAIS = "materiais", "Materiais e Insumos"
    SERVICOS_PJ = "servicos_pj", "Serviços PJ"
    TRANSPORTES = "transportes", "Transportes"
    DEMAIS = "demais", "Demais"
    INDIRETO = "indireto", "Indireto"


class ContaContabil(models.Model):
    """O plano de contas — dois níveis, e o pai é o grupo sintético.

    ## Cadastro, e não espelho

    Como `Area`, não herda `ProcedenciaMixin`: o plano é estrutura, não
    movimento. Ele muda por decisão da contabilidade, algumas vezes por ano, e
    não por carga noturna.

    Isso tem uma consequência que decide o desenho do bloco D: quando o razão do
    Sankhya trouxer um código que não existe aqui, a linha **não pode ser
    descartada**. Uma despesa que some porque a conta é nova faria o total do
    contrato ficar menor que a soma dos lançamentos dele — e ninguém procuraria
    o erro no plano de contas. Ver `ResultadoPorConta.conta`, que é opcional
    justamente por isso.

    ## Dois níveis, com o pai apontando para si mesmo

    `41101 PESSOAL` é grupo; `41101001 SALÁRIOS` é conta analítica e aponta para
    ele. Uma tabela só, com auto-relação, em vez de duas: os dois têm código,
    nome e ordem, e duas tabelas fariam toda consulta virar união.

    O `degrau_dre` fica no GRUPO. A analítica herda — repetir o degrau em cada
    uma das vinte contas de pessoal seria vinte lugares para divergir.
    """

    codigo = models.CharField(max_length=20, unique=True)
    nome = models.CharField(max_length=120)
    #: `null` no grupo sintético. A analítica aponta para o grupo dela.
    pai = models.ForeignKey(
        "self", null=True, blank=True,
        on_delete=models.PROTECT, related_name="filhas",
    )
    natureza = models.CharField(
        max_length=20, choices=NaturezaConta.choices, db_index=True
    )
    #: Só no grupo. A analítica lê o do pai — ver `degrau`.
    degrau_dre = models.CharField(
        max_length=20, choices=DegrauDRE.choices, blank=True, db_index=True
    )
    ordem = models.PositiveSmallIntegerField(default=0)
    ativa = models.BooleanField(default=True)

    class Meta:
        ordering = ["codigo"]
        verbose_name = "conta contábil"
        verbose_name_plural = "contas contábeis"
        indexes = [
            models.Index(fields=["pai", "ordem"], name="res_conta_grupo_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.codigo} · {self.nome}"

    @property
    def sintetica(self) -> bool:
        """Grupo, e não conta analítica. É o nível 1 da tabela do bloco D."""
        return self.pai_id is None

    @property
    def degrau(self) -> str:
        """O degrau da DRE, herdado do grupo quando esta é analítica."""
        if self.degrau_dre:
            return self.degrau_dre
        return self.pai.degrau_dre if self.pai_id else ""


class ResultadoPorConta(ProcedenciaMixin):
    """O razão por conta, mês e contrato — o que responde "com o que gastei".

    ## Por que não é uma coluna a mais em `CompetenciaResultado`

    Porque a cardinalidade é outra. `CompetenciaResultado` é UMA linha por
    contrato e mês, com seis totais; aqui são dezenas de linhas para o mesmo
    contrato e mês, uma por conta. Empilhar as duas coisas na mesma tabela faria
    toda consulta de agregado ter de saber distinguir "a linha do total" da "a
    linha da conta" — e a primeira soma errada apareceria como receita dobrada.

    As duas convivem, e `CompetenciaResultado` continua sendo a verdade do
    agregado. Há teste conferindo que a soma daqui bate com ela: detalhe que não
    fecha com o total destrói a confiança na tela inteira, e é a única coisa que
    o bloco D não pode errar.

    ## `contrato` é opcional, e `conta` também — por razões diferentes

    Sem CONTRATO é o rateio de centro de custo, que não pertence a cliente
    nenhum. É a mesma linha que `CompetenciaResultado` já guarda assim.

    Sem CONTA é o código que o Sankhya mandou e o plano não conhece. Descartar a
    linha faria a despesa sumir do total sem deixar rastro; guardá-la com
    `codigo_origem` preenchido põe o problema na tela, onde alguém conserta o
    plano de contas.
    """

    #: `null` = rateio do centro de custo, sem cliente.
    contrato = models.ForeignKey(
        "resultados.Contrato", null=True, blank=True,
        on_delete=models.CASCADE, related_name="contas",
    )
    centro_custo = models.CharField(max_length=20, db_index=True)
    ano = models.PositiveSmallIntegerField(db_index=True)
    mes = models.PositiveSmallIntegerField(db_index=True)

    #: `null` = conta desconhecida. Ver `codigo_origem`.
    conta = models.ForeignKey(
        ContaContabil, null=True, blank=True,
        on_delete=models.PROTECT, related_name="lancamentos",
    )
    #: O código que a FONTE mandou, sempre — inclusive quando `conta` resolveu.
    #: Guardado mesmo no caso feliz porque é ele que prova de onde a linha veio
    #: no dia em que o plano de contas for reorganizado.
    codigo_origem = models.CharField(max_length=20, db_index=True)

    valor_realizado = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    #: A COLUNA DO MEIO — o que a operação declara que já aconteceu e ainda não
    #: bateu na contabilidade. Sem ela a reunião vira briga sobre o número em vez
    #: de decisão sobre o que fazer. É a mesma que a faixa do dinheiro já tem.
    ajustes = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    #: `None` e não zero: sem orçado é diferente de orçado zero, e a diferença
    #: aparece na tela como "sem orçado" em vez de uma variação de 100%.
    valor_orcado = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )

    class Meta:
        ordering = ["ano", "mes", "codigo_origem"]
        verbose_name = "resultado por conta"
        verbose_name_plural = "resultados por conta"
        constraints = [
            models.UniqueConstraint(
                fields=["fonte", "chave_externa"], name="res_conta_origem_unica"
            )
        ]
        indexes = [
            models.Index(
                fields=["ano", "mes", "centro_custo"], name="res_conta_comp_idx"
            ),
            models.Index(fields=["contrato", "ano", "mes"], name="res_conta_ctr_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.codigo_origem} · {self.mes:02d}/{self.ano}"

    @property
    def realizado_ajustado(self) -> Decimal:
        """`VL REALIZADO + AJUSTES` — a terceira coluna da tabela do bloco D."""
        return (self.valor_realizado or Decimal("0")) + (self.ajustes or Decimal("0"))


class ServicoContrato(models.TextChoices):
    """COMO o contrato foi vendido, e não O QUE ele entrega.

    Até 09/09/2026 esta lista era `cftv · alarme · monitoramento · instalacao ·
    manutencao` — uma mistura de duas perguntas. "CFTV" e "alarme" são
    EQUIPAMENTO: dizem o que está instalado, e o mesmo cliente pode ter os dois
    sob um contrato de manutenção, de locação ou de projeto. Como tipo de
    serviço eles respondiam à pergunta errada, e por isso o filtro por serviço
    não separava nada que a diretoria quisesse comparar.

    O equipamento passou a ser ESCOPO do contrato. O que fica aqui é a forma de
    contratação, que é o que muda o peso das contas: monitoramento pesa em
    pessoal e comunicações; manutenção, em transportes e equipamento; locação,
    em depreciação; turnkey, em equipamento e serviços de terceiro.

    O `projeto_turnkey` é separado de `projeto` porque a diferença é de risco:
    no turnkey a empresa responde pelo resultado inteiro, e o estouro de
    equipamento é dela.
    """

    PROJETO = "projeto", "Projeto"
    MONITORAMENTO = "monitoramento", "Monitoramento"
    MANUTENCAO = "manutencao", "Manutenção"
    LOCACAO = "locacao", "Locação"
    PROJETO_TURNKEY = "projeto_turnkey", "Projeto turnkey"


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
    #: O nome da UNIDADE do organograma, e é por ele que a permissão recorta —
    #: ver `Area` para por que ele não é a área comercial e não pode virar uma.
    #: Não aparece em filtro de tela.
    regional = models.CharField(max_length=60, blank=True, db_index=True)
    #: O agrupamento comercial. `null` quer dizer "sem área", que é uma resposta
    #: legítima e visível no filtro — nunca um contrato escondido.
    #:
    #: `SET_NULL` e não `PROTECT`: apagar uma área é decisão de cadastro, e ela
    #: não deve levar contratos junto nem travar por causa deles. Os que ficarem
    #: órfãos aparecem em "Sem área", que é exatamente onde alguém os encontra
    #: para reagrupar.
    area = models.ForeignKey(
        "resultados.Area", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="contratos",
    )
    #: O QUE está instalado, em texto — §H1. "800 câmeras, 30 switches PoE".
    #:
    #: Texto e não FK para um catálogo: nada consulta equipamento hoje — não há
    #: filtro por câmera nem relatório por item —, e um modelo com FK por item
    #: seria uma tabela que só a semeadora escreve. Quando existir a pergunta
    #: ("quantas câmeras a empresa mantém?"), vira modelo.
    escopo = models.TextField(blank=True)
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
    #: ANULÁVEL desde 10/09/2026, e a mudança é sobre o que o espelho consegue
    #: DIZER.
    #:
    #: Com `default=0` ele não sabia dizer "desconhecido": o defeito 10 da massa
    #: — receita lançada e custo ausente — chegava gravado como `0,00`, e a
    #: cascata da DRE o tratava como "não gastou nada", inflando a margem de
    #: contribuição pela receita líquida inteira do contrato.
    #:
    #: Os campos ORÇADOS ao lado já eram anuláveis exatamente por essa razão. A
    #: regra valia para metade dos campos.
    custo_direto = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
    custo_indireto = models.DecimalField(max_digits=16, decimal_places=2, default=0)
    #: Anulável pela mesma razão do custo: ela é derivada dele, e uma margem de
    #: `0,00` calculada sobre custo desconhecido é um número inventado.
    margem_contribuicao = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
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
    #: As TRÊS que faltavam — sem elas, C2 e C3 não tinham par para comparar e
    #: os gráficos de imposto, indireto e EBITDA saíam sem a barra do orçado.
    #: Anuláveis como as outras: sem orçado é diferente de orçado zero.
    impostos_orcado = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
    custo_indireto_orcado = models.DecimalField(
        max_digits=16, decimal_places=2, null=True, blank=True
    )
    ebitda_orcado = models.DecimalField(
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
    contrato = models.ForeignKey("Contrato", null=True, blank=True, on_delete=models.PROTECT, related_name="apontamentos")
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
                fields=["centro_custo", "ano", "mes"], name="res_apontamento_cc_unico",
                condition=models.Q(contrato__isnull=True)
            ),
            models.UniqueConstraint(
                fields=["contrato", "centro_custo", "ano", "mes"], name="res_apontamento_contrato_unico",
                condition=models.Q(contrato__isnull=False)
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
