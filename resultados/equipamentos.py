"""O CATÁLOGO DE EQUIPAMENTOS da ADB, e os arquétipos de contrato. §H1.

## Por que constantes e não um modelo

Nada consulta equipamento hoje: não há filtro por câmera, nem tela de acervo,
nem relatório por item. O que a tela precisa é o ESCOPO do contrato em texto —
"800 câmeras, 30 switches PoE" —, e um modelo com FK para cada item seria uma
tabela que só a semeadora escreve e ninguém lê.

Quando existir a pergunta ("quantas câmeras a empresa mantém?"), isto vira
modelo. Até lá, é uma lista.

## Os dois arquétipos, e por que dois

Conferido com o dono do produto em 09/09/2026, com números reais:

    PREDIAL       um endereço grande. 800 câmeras, 30 switches PoE de 24
                  portas, R$ 35 mil de cabeamento, R$ 15 mil de infraestrutura.

    REDE          muitas unidades pequenas. Numa rede de 1.400 agências: ~43
                  câmeras por unidade, 1 a 2 DVR por unidade, e 3 kits de
                  neblina por unidade.

A diferença não é de tamanho — é de FORMATO. O predial concentra tudo num
endereço e pesa em infraestrutura; a rede multiplica um kit pequeno por centenas
de unidades e pesa em deslocamento. É por isso que um contrato de manutenção de
rede tem transporte alto e um predial não, e é essa diferença que faz o
detalhamento por conta contábil ensinar alguma coisa.

## O kit de neblina é um conjunto, e não um item

Também conferido: cada ponto de neblina instalado é
`2 painéis · 15 sensores sísmicos · 5 sensores de presença · 1 magnético ·
4 câmeras · 2 neutralizadores`. Tratá-lo como "1 gerador de neblina" esconderia
vinte e nove itens que existem, são comprados e quebram.
"""

from __future__ import annotations

#: O catálogo, por família. Conferido com o dono do produto em 09/09/2026:
#: LPR e térmica ENTRAM (a ADB vende as duas), cerca elétrica é escopo da
#: empresa, e eclusa e torniquete são itens diferentes.
CATALOGO: dict[str, tuple[str, ...]] = {
    "CFTV": (
        "Câmera bullet", "Câmera dome", "Speed dome / PTZ", "Câmera térmica",
        "LPR — leitura de placas", "NVR", "DVR", "Storage",
        "Switch PoE", "Rack", "No-break", "VMS", "Analítico de vídeo",
        "Licença por canal",
    ),
    "Alarme e perimetral": (
        "Central de alarme", "Sensor infravermelho passivo",
        "Barreira infravermelha ativa", "Sensor magnético",
        "Sensor de quebra de vidro", "Cerca elétrica", "Sirene", "Teclado",
        "Botão de pânico", "Comunicador GPRS/IP",
    ),
    "Controle de acesso": (
        "Catraca", "Torniquete", "Biometria digital", "Biometria facial",
        "RFID e proximidade", "Fechadura eletromagnética", "Cancela veicular",
        "Eclusa", "Videoporteiro", "Software de acesso",
    ),
    "Neblina": (
        "Central geradora de neblina", "Cartucho e fluido",
        "Módulo de acionamento", "Neutralizador",
    ),
    "Monitoramento": (
        # CENTRAL PRÓPRIA, conferido. Isso põe o custo em `41101 Pessoal` e não
        # em `41401 Serviços PJ` — e é a diferença entre um contrato de
        # monitoramento que parece caro em gente e um que parece caro em
        # terceiro.
        "Central 24h própria", "Link primário", "Link redundante",
        "Rastreamento", "Atendimento de ocorrência", "Verificação por vídeo",
    ),
    "Infraestrutura": (
        "Cabeamento estruturado", "Cabeamento óptico", "Conectorização",
        "Eletrocalha e duto", "Poste e suporte", "Aterramento e SPDA",
        "Gerador", "No-break",
    ),
}

#: O KIT de neblina, item a item. Conferido: é isto que vai numa unidade.
KIT_DE_NEBLINA: tuple[tuple[int, str], ...] = (
    (2, "painéis"),
    (15, "sensores sísmicos"),
    (5, "sensores de presença"),
    (1, "magnético"),
    (4, "câmeras"),
    (2, "neutralizadores"),
)

#: `(câmeras, switches PoE 24p, cabeamento R$, infraestrutura R$)` de um
#: PREDIAL de porte farol. Números reais de um contrato existente.
PREDIAL_FAROL = (800, 30, 35_000, 15_000)

#: Por UNIDADE de uma rede de agências. Também reais: ~43 câmeras (60 mil em
#: 1.400 agências), 1 a 2 DVR e 3 kits de neblina.
POR_AGENCIA = {"cameras": 43, "dvr": 2, "kits_neblina": 3}


def _br(numero: int) -> str:
    """Milhar com ponto. Local e não `graficos.formato`: `resultados` não
    conhece o `workspace`, e a dependência é de mão única."""
    return f"{numero:,}".replace(",", ".")


def escopo_predial(fator: float = 1.0) -> str:
    """O escopo de um contrato predial, em uma frase."""
    cameras, switches, cabo, infra = PREDIAL_FAROL
    return (
        f"{_br(round(cameras * fator))} câmeras, {round(switches * fator)} "
        f"switches PoE de 24 portas, R$ {_br(round(cabo * fator))} de "
        f"cabeamento e R$ {_br(round(infra * fator))} de infraestrutura"
    )


def escopo_de_rede(unidades: int) -> str:
    """O escopo de uma rede de agências — e o kit de neblina aberto.

    Aberto porque cada ponto são vinte e nove itens que existem, são comprados
    e quebram. "3 pontos de neblina" esconderia todos eles.
    """
    kit = " + ".join(f"{q} {nome}" for q, nome in KIT_DE_NEBLINA)
    return (
        f"{_br(unidades * POR_AGENCIA['cameras'])} câmeras e "
        f"{_br(unidades * POR_AGENCIA['dvr'])} DVR em {_br(unidades)} unidades, "
        f"{_br(unidades * POR_AGENCIA['kits_neblina'])} pontos de neblina "
        f"(cada um: {kit})"
    )
