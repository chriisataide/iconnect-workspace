"""Explicações do razão, calculadas apenas sobre os DTOs já autorizados."""

from collections import defaultdict
from decimal import Decimal


def analisar(linhas, anteriores, sinal):
    """Desvio positivo melhora o resultado; orçamento incompleto não compara."""
    atual = sum((l.realizado_ajustado * sinal(l.natureza) for l in linhas), Decimal(0))
    orcados = [l.orcado * sinal(l.natureza) for l in linhas if l.orcado is not None]
    completo = bool(linhas) and len(orcados) == len(linhas)
    orcado = sum(orcados, Decimal(0)) if completo else None
    desvio = atual - orcado if orcado is not None else None
    anterior = (
        sum((l.realizado_ajustado * sinal(l.natureza) for l in anteriores), Decimal(0))
        if anteriores else None
    )
    variacao = atual - anterior if anterior is not None else None
    composicao = defaultdict(lambda: Decimal(0))
    ajustes = []
    for l in linhas:
        composicao[(l.contrato, l.centro_custo)] += l.realizado_ajustado * sinal(l.natureza)
        if l.ajustes:
            ajustes.append({"codigo": l.codigo, "contrato": l.contrato,
                            "centro_custo": l.centro_custo,
                            "valor": l.ajustes * sinal(l.natureza),
                            "procedencia": l.procedencia})
    cargas = [l.procedencia.carregado_em for l in linhas if l.procedencia.carregado_em]
    situacao = "nao_classificado"
    if desvio is not None and not any(l.desconhecida for l in linhas):
        situacao = "favoravel" if desvio > 0 else "desfavoravel" if desvio < 0 else "previsto"
    return {
        "desvio": desvio,
        "desvio_pct": desvio / abs(orcado) * 100 if orcado else None,
        "situacao": situacao,
        "orcamento_parcial": bool(orcados) and not completo,
        "anterior": anterior, "variacao": variacao,
        "variacao_pct": variacao / abs(anterior) * 100 if anterior else None,
        "composicao": [{"contrato": c, "centro_custo": cc, "valor": v}
                       for (c, cc), v in sorted(composicao.items())],
        "ajustes": ajustes,
        "fontes": sorted({l.procedencia.fonte for l in linhas if l.procedencia.fonte}),
        "ultima_carga": max(cargas) if cargas else None,
        "primeira_carga": min(cargas) if cargas else None,
        "cargas_incompletas": len(cargas) != len(linhas),
    }


def enriquecer(grupos, totais, linhas, anteriores, sinal):
    """Indexa uma vez; nenhuma consulta adicional por grupo ou conta."""
    atuais_por_grupo, anteriores_por_grupo = defaultdict(list), defaultdict(list)
    atuais_por_conta, anteriores_por_conta = defaultdict(list), defaultdict(list)
    for origem, por_grupo, por_conta in (
        (linhas, atuais_por_grupo, atuais_por_conta),
        (anteriores, anteriores_por_grupo, anteriores_por_conta),
    ):
        for l in origem:
            por_grupo[l.grupo_codigo].append(l)
            por_conta[(l.grupo_codigo, l.codigo)].append(l)
    for grupo in grupos:
        codigo = grupo["codigo"]
        grupo["analise"] = analisar(atuais_por_grupo[codigo], anteriores_por_grupo[codigo], sinal)
        for conta in grupo["contas"]:
            chave = (codigo, conta["codigo"])
            conta["analise"] = analisar(atuais_por_conta[chave], anteriores_por_conta[chave], sinal)
    totais["analise"] = analisar(linhas, anteriores, sinal)
