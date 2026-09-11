"""O PLANO DE CONTAS da ADB — a estrutura, num lugar só.

## Por que módulo, e não uma lista dentro do seeder

Três coisas leem esta estrutura: o comando que a semeia, a tela que a mostra e
os testes que conferem se a soma fecha. Duas cópias divergiriam no dia em que
alguém acrescentasse uma conta em uma delas.

## Os códigos vieram da referência, e duas famílias são da ADB

`31101` a `44101` são do plano de referência. As duas últimas — `41504`
EQUIPAMENTOS E MATERIAIS DE SEGURANÇA ELETRÔNICA e `41505` GARANTIA E
RETRABALHO — não existem lá porque o benchmark é de outro ramo, e são
justamente as que fazem o detalhamento ensinar alguma coisa nesta empresa: é em
`41504` que um projeto turnkey estoura, e é `41505` que mostra o contrato que
parece rentável e não é.

## O degrau da DRE mora no GRUPO

A conta analítica herda. Repetir o degrau nas vinte contas de pessoal seria
vinte lugares para divergir — e a vigésima primeira nasceria sem nenhum.

## Sobre "Demais"

Não é uma lixeira: é o degrau das despesas que existem e não pertencem a nenhum
dos anteriores — seguros, viagens, comunicações, tributos. Chamá-las de
"Outros" numa cascata faria a maior barra da tela não dizer nada. "Demais" ao
menos declara que é um agrupamento e não uma conta.
"""

from __future__ import annotations

from resultados.models import DegrauDRE as D
from resultados.models import NaturezaConta as N

#: `(código, nome, natureza, degrau, [contas analíticas])`.
#:
#: A ordem é a da leitura contábil — receita, imposto, custo, despesa —, e é
#: ela que a cascata e a tabela usam. Ordenar por código daria quase o mesmo
#: resultado e quebraria no dia em que um grupo novo entrar fora de sequência.
PLANO: tuple[tuple[str, str, str, str, tuple[str, ...]], ...] = (
    # ── RECEITA ─────────────────────────────────────────────────────
    (
        "31101", "RECEITAS DE VENDAS E SERVIÇOS", N.RECEITA, D.RECEITA_BRUTA,
        (
            "Receita de serviços",
            "Receita de vendas",
            "Receita de locação",
            "Receita de direitos a faturar",
            "Receita de monitoramento",
            "Provisão/cancelamento de notas",
            "Receita a faturar — monitoramento",
            "Receita a faturar — locação",
        ),
    ),
    (
        "31201", "IMPOSTOS S/ FATURAMENTO", N.IMPOSTO, D.IMPOSTOS,
        (
            "ISS",
            "PIS",
            "COFINS",
            "ICMS sobre vendas",
            "Créditos de impostos",
            "Provisões de impostos",
            "Ajuste de regime fiscal",
        ),
    ),
    # ── PESSOAL E ENCARGOS ──────────────────────────────────────────
    (
        "41101", "PESSOAL", N.CUSTO, D.PESSOAL,
        (
            "Salários",
            "Adicional de periculosidade",
            "Adicional de insalubridade",
            "Adicional noturno",
            "Hora noturna reduzida",
            "Horas extras 60%",
            "Horas extras 100%",
            "DSR",
            "Gratificações",
            "Prêmios",
            "Aviso prévio trabalhado",
            "Falta descontada",
            "Falta abonada",
            "Atestado médico",
            "Hora extra — serviço extra",
            "Hora extra — escala",
            "Hora extra — intrajornada",
            "Hora extra — ineficiência",
            "Insuficiência de saldo",
            "Folga trabalhada",
            "Movimentação operacional",
        ),
    ),
    ("41103", "PARTICIPAÇÃO NOS RESULTADOS", N.CUSTO, D.ENCARGOS, ()),
    (
        "41104", "ENCARGOS SOCIAIS E TRABALHISTAS", N.CUSTO, D.ENCARGOS,
        (
            "FGTS",
            "INSS",
            "Rescisões e indenizações",
            "Multa de FGTS",
            "Aviso prévio indenizado",
        ),
    ),
    (
        "41105", "PROVISÕES TRABALHISTAS", N.CUSTO, D.ENCARGOS,
        (
            "Provisão de férias",
            "INSS e FGTS sobre férias",
            "Provisão de 13º",
            "INSS e FGTS sobre 13º",
        ),
    ),
    (
        "41106", "BENEFÍCIOS", N.CUSTO, D.BENEFICIOS,
        (
            "Vale alimentação",
            "Vale refeição / PAT",
            "Vale transporte",
            "Transporte fretado",
            "Auxílio creche",
            "Assistência médica",
            "Assistência odontológica",
            "Medicamentos",
            "Seguro de vida",
            "Cartão multibenefício",
            "Bolsa de estudo",
            "Cursos e treinamentos",
            "Descontos e coparticipações",
        ),
    ),
    (
        "41201", "MEDICINA E SEGURANÇA DO TRABALHO", N.CUSTO, D.BENEFICIOS,
        ("EPI, fardamento e acessórios", "Exames", "Lavagem e higienização"),
    ),
    # ── TRANSPORTES E TERCEIROS ─────────────────────────────────────
    (
        "41301", "TRANSPORTES", N.CUSTO, D.TRANSPORTES,
        (
            "Locação de veículos",
            "Táxi, pedágio e estacionamento",
            "Combustível",
            "Manutenção de veículos",
            "Quilometragem",
            "IPVA, licenciamento e multas",
        ),
    ),
    (
        "41401", "SERVIÇOS CONTRATADOS — PJ", N.CUSTO, D.SERVICOS_PJ,
        (
            "Empreiteria e manutenção",
            "Consultoria jurídica",
            "Consultoria contábil",
            "Consultoria de RH",
            "Consultoria de TI",
            "Manutenção de software e hardware",
            "Destinação de resíduos",
            "Manutenção de máquinas e equipamentos",
            "Limpeza especializada",
        ),
    ),
    (
        "41403", "LOCAÇÕES E LEASING", N.CUSTO, D.DEMAIS,
        ("Locação de imóveis", "Locação de equipamentos"),
    ),
    # ── MATERIAIS E INSUMOS ─────────────────────────────────────────
    (
        "41501", "MATERIAIS DE CONSERVAÇÃO E APOIO", N.CUSTO, D.MATERIAIS,
        (
            "Limpeza",
            "Construção e manutenção",
            "Uniformes",
            "Ferramentas",
            "Materiais elétricos",
            "Materiais para manutenção de equipamentos",
        ),
    ),
    (
        "41502", "MATERIAL DE CONSUMO GERAL", N.CUSTO, D.MATERIAIS,
        (
            "Gráfico e escritório",
            "Informática",
            "Copa e cozinha",
            "Móveis de baixo valor",
        ),
    ),
    ("41503", "INSUMOS / CUSTO DE REVENDA", N.CUSTO, D.MATERIAIS, ()),
    # ── AS DUAS DA ADB ──────────────────────────────────────────────
    (
        "41504", "EQUIPAMENTOS E MATERIAIS DE SEGURANÇA ELETRÔNICA",
        N.CUSTO, D.MATERIAIS,
        (
            "Câmeras e ópticas",
            "Gravadores e armazenamento",
            "Sensores e centrais",
            "Controle de acesso",
            "Geradores de neblina e recargas",
            "Infraestrutura de rede",
            "Cabeamento e conectorização",
            "Energia e no-break",
            "Licenças de VMS e de controle de acesso",
        ),
    ),
    (
        "41505", "GARANTIA E RETRABALHO", N.CUSTO, D.MATERIAIS,
        ("Substituição em garantia", "Retorno técnico não faturável"),
    ),
    # ── DESPESAS ────────────────────────────────────────────────────
    (
        "41601", "DESPESAS GERAIS", N.CUSTO, D.DEMAIS,
        (
            "Seguros",
            "Refeições e lanches",
            "Acordos e execuções judiciais",
            "Confraternizações",
            "Ressarcimentos",
            "Juros de atraso de cliente",
            "Retenção contratual",
            "Custas cartoriais",
            "Taxas com fornecedores",
            "Desconto comercial",
            "Despesa de operadora de cartões",
        ),
    ),
    (
        "41602", "COMUNICAÇÕES", N.CUSTO, D.DEMAIS,
        ("Telefonia fixa", "Telefonia móvel", "Internet e link de dados"),
    ),
    ("41603", "VIAGENS E ESTADIAS", N.CUSTO, D.DEMAIS, ()),
    ("41604", "EXECUÇÕES JUDICIAIS TRABALHISTAS", N.CUSTO, D.DEMAIS, ()),
    ("41606", "PROVISÕES CONTRATUAIS (PCO)", N.CUSTO, D.DEMAIS, ()),
    (
        "41701", "IMPOSTOS, EMOLUMENTOS E LICENÇAS", N.CUSTO, D.DEMAIS,
        (
            "Licenças de software",
            "Contribuição sindical patronal",
            "Taxas e licenças governamentais",
            # Relevante para segurança: a autorização de funcionamento é
            # federal, e o custo dela é recorrente.
            "Taxas de polícia federal",
        ),
    ),
    # `D.DEMAIS` e não `D.INDIRETO`: a depreciação do equipamento de um
    # contrato de locação é custo DIRETO dele. O degrau "Indireto" da cascata
    # não sai de conta nenhuma — ele é a soma das linhas sem contrato.
    ("41801", "DEPRECIAÇÕES E AMORTIZAÇÕES", N.CUSTO, D.DEMAIS, ()),
    # ── FINANCEIRO E NÃO OPERACIONAL ────────────────────────────────
    ("41901", "RECEITAS FINANCEIRAS", N.FINANCEIRO, "", ("Juros ativos",)),
    (
        "41902", "DESPESAS FINANCEIRAS", N.FINANCEIRO, "",
        ("Juros e multas", "Descontos concedidos"),
    ),
    ("43101", "RECEITA NÃO OPERACIONAL", N.NAO_OPERACIONAL, "", ()),
    ("43102", "DESPESA NÃO OPERACIONAL", N.NAO_OPERACIONAL, "", ()),
    (
        "44101", "DESPESAS NÃO DEDUTÍVEIS", N.NAO_OPERACIONAL, "",
        ("Multas de trânsito",),
    ),
)


def codigo_analitico(grupo: str, indice: int) -> str:
    """`("41101", 0)` → `"41101001"`.

    Três dígitos e sequencial dentro do grupo, como na referência. A numeração
    real do ERP tem buracos — contas desativadas ao longo dos anos —, e
    reproduzi-los aqui seria imitar a aparência de um dado que não temos.
    """
    return f"{grupo}{indice + 1:03d}"


def total_de_contas() -> int:
    """Quantas contas o plano tem, grupos incluídos. Usado pelos testes."""
    return sum(1 + len(analiticas) for *_, analiticas in PLANO)
