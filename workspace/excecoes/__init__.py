"""Gestão por exceção — as regras, e o registro delas.

    proprias.py    as dez sobre o dado do próprio Workspace
    espelho.py     as seis que a ingestão destravou (contratos, projetos, NPS)
    ingestao.py    as duas que vigiam o mecanismo, e não o negócio

A lógica é código; se a regra está ligada é dado. Ver `base.py` para o porquê.
"""

from .base import (
    Ocorrencia,
    Regra,
    RegraBase,
    limpar,
    quem_responde,
    regra_de,
    registrar,
    titulares,
    todas,
)

__all__ = [
    "Ocorrencia",
    "Regra",
    "RegraBase",
    "limpar",
    "quem_responde",
    "regra_de",
    "registrar",
    "semear",
    "titulares",
    "todas",
]


def semear() -> None:
    """Registra os avaliadores. Chamado no `ready()` do app.

    Registra TODOS, inclusive os que dependem de fonte ausente neste ambiente:
    quem responde por isso é `disponivel()`, e a diferença importa. Um avaliador
    fora do registro faria a regra aparecer como "sem avaliador escrito" — uma
    frase sobre o produto. `disponivel() == False` diz "a fonte não está no ar",
    que é uma frase sobre o ambiente, e é a verdadeira.
    """
    from . import espelho, ingestao, proprias

    avaliadores = (
        proprias.LotacaoSemCentroDeCusto(),
        proprias.PessoaSemPapelVigente(),
        proprias.PapelVencendo(),
        proprias.SolicitacaoParada(),
        proprias.AprovacaoPendente(),
        proprias.LeituraObrigatoriaNaoConfirmada(),
        proprias.NormativoSemRevisao(),
        proprias.CentroDeCustoSemOrcamento(),
        proprias.CentroDeCustoComprometido(),
        proprias.ReservaSemUso(),
        espelho.MargemAbaixoDoMinimo(),
        espelho.ContratoVencendoSemVisita(),
        espelho.LayerTresSemApresentacao(),
        espelho.DetratorSemTratativa(),
        espelho.ProjetoBloqueadoHaMuito(),
        espelho.MarcoVencidoSemReplanejamento(),
        ingestao.FonteAtrasada(),
        ingestao.DivergenciaEntreFontes(),
    )
    for avaliador in avaliadores:
        try:
            registrar(avaliador)
        except ValueError:
            # Já registrado: `ready()` pode rodar mais de uma vez conforme o
            # servidor, e a segunda passada não pode derrubar a subida.
            continue
