"""Indicadores e perfuração mensal de horas, sem rateio estimado por contrato."""
from collections import defaultdict
from decimal import Decimal
from datetime import timedelta

from workspace.providers.resultados import ProvedorJornada, ProvedorCarteira, obter, base_apontamentos
from workspace.graficos import series, formato as fmt

TIPOS = (
    ("horas_normais", "Horas normais"), ("he_total", "HE total"),
    ("he_servico_extra", "HE serviço extra"), ("he_sem_classificacao", "HE sem classificação"),
    ("he_ineficiencia", "HE ineficiência"), ("hora_escala", "Horas de escala"),
    ("hora_abono", "Abono"), ("hora_desconto", "Desconto"),
    ("hora_noturna", "Horas noturnas"), ("banco_horas_saldo", "Saldo do banco de horas"),
)
COMPARAR = ("he_ineficiencia", "hora_abono", "hora_desconto", "he_sem_classificacao")


def montar(escopo, filtros, metrica, url, ranking="volume"):
    provedor = obter(ProvedorJornada)
    if not provedor:
        return {"disponivel": False, "motivo": "Fonte de jornada não disponível."}
    ranking = ranking if ranking in ("volume", "proporcional") else "volume"
    anterior = (filtros.competencia.replace(day=1) - timedelta(days=1)).replace(day=1)
    linhas = provedor.serie_apontamentos(escopo, min(filtros.de, anterior), filtros.ate)
    base = base_apontamentos(linhas)
    mes = [l for l in base if (l.ano, l.mes) == (filtros.competencia.year, filtros.competencia.month)]
    metrica = metrica if metrica in dict(TIPOS) else "he_total"
    normais = sum((l.horas_normais for l in mes), Decimal(0))
    kpis = []
    for campo, titulo in TIPOS:
        valor = sum((getattr(l, campo) for l in mes), Decimal(0)) if mes else None
        kpis.append({"titulo": titulo, "valor": valor, "percentual": valor / normais * 100 if normais and valor is not None else None})
    por_mes = defaultdict(list)
    for l in base:
        por_mes[(l.ano, l.mes)].append(l)
    meses = []
    cursor = filtros.de.replace(day=1)
    while cursor <= filtros.ate:
        meses.append(cursor)
        cursor = cursor.replace(year=cursor.year + (cursor.month == 12), month=cursor.month % 12 + 1)
    valores = {campo: [sum((getattr(l, campo) for l in por_mes[(m.year, m.month)]), Decimal(0)) if (m.year, m.month) in por_mes else None for m in meses] for campo in COMPARAR}
    grafico = series.serie_temporal([(m.strftime("%m/%Y"), valores[COMPARAR[0]][i]) for i, m in enumerate(meses)], chave="jornada-mensal", titulo="HE de ineficiência, abono, desconto e HE sem classificação por mês", formatar=fmt.numero, formatar_tabela=fmt.numero)
    if grafico.option:
        grafico.option.pop("dataset", None)
        grafico.option["xAxis"]["data"] = [m.strftime("%m/%Y") for m in meses]
        grafico.option["legend"] = {"data": [dict(TIPOS)[c] for c in COMPARAR], "type": "scroll", "bottom": 0}
        grafico.option["grid"]["bottom"] = 40
        grafico.option["series"] = [{"name": dict(TIPOS)[c], "type": "bar", "data": [float(v) if v is not None else None for v in valores[c]]} for c in COMPARAR]
        grafico.colunas = [series.Coluna("Mês", numerica=False)] + [series.Coluna(dict(TIPOS)[c]) for c in COMPARAR]
        grafico.linhas = [[m.strftime("%m/%Y")] + [fmt.numero(valores[c][i], 2) for c in COMPARAR] for i, m in enumerate(meses)]
    rankings = []
    sem_base = 0
    for dimensao, titulo in (("area", "Por área"), ("centro_custo", "Por centro de custo"), ("contrato", "Por contrato")):
        fonte = mes if dimensao == "centro_custo" else [l for l in linhas if l.contrato and (l.ano, l.mes) == (filtros.competencia.year, filtros.competencia.month)]
        somas, normais_grupo, nomes = defaultdict(lambda: Decimal(0)), defaultdict(lambda: Decimal(0)), {}
        for l in fonte:
            codigo = getattr(l, dimensao)
            somas[codigo] += getattr(l, metrica)
            normais_grupo[codigo] += l.horas_normais
            nomes[codigo] = l.area_nome if dimensao == "area" else f"{l.contrato} · {l.cliente}" if dimensao == "contrato" else codigo
        if ranking == "proporcional":
            sem_base += sum(1 for c in somas if normais_grupo[c] <= 0)
            somas = {c: v / normais_grupo[c] * 100 for c, v in somas.items() if normais_grupo[c] > 0}
        parametro = "cc" if dimensao == "centro_custo" else dimensao
        pontos = [series.Ponto(rotulo=nomes[c], valor=v, url=url(**{parametro: c, "hora": metrica, "ranking": ranking})) for c, v in sorted(somas.items(), key=lambda i: -i[1])]
        rankings.append(series.barras_por_categoria(pontos, chave="jornada-" + dimensao, titulo=titulo + " — " + dict(TIPOS)[metrica] + (" por 100 h normais" if ranking == "proporcional" else ""), rotulo_serie="Horas por 100 h normais" if ranking == "proporcional" else "Horas", formatar=fmt.numero, formatar_tabela=lambda v: fmt.numero(v, 2), altura=max(300, min(900, len(pontos) * 35))))
    from workspace.services.jornada_analise import analisar
    provedor_carteira = obter(ProvedorCarteira)
    carteira = provedor_carteira.contratos(escopo, filtros.competencia) if provedor_carteira else []
    analise = analisar(linhas, base, carteira, filtros.competencia, anterior, meses, metrica, dict(TIPOS)[metrica])
    return {**analise, "carteira": carteira, "titulo_metrica": dict(TIPOS)[metrica], "ranking": ranking, "sem_base": sem_base,
            "url_volume": url(hora=metrica, ranking="volume"), "url_proporcional": url(hora=metrica, ranking="proporcional"),
            "disponivel": any((l.ano, l.mes) >= (filtros.de.year, filtros.de.month) for l in linhas), "motivo": "Sem apontamentos no período e recorte selecionados.",
            "kpis": kpis, "mensal": grafico, "rankings": rankings, "metrica": metrica,
            "opcoes": [{"titulo": t, "url": url(hora=c, ranking=ranking), "ativa": c == metrica} for c, t in TIPOS],
            "sem_vinculo": any(not l.contrato for l in mes),
            "filtrado": bool(filtros.area or filtros.contrato),
            "url_voltar": url(area="", contrato="", cc="", hora=metrica, ranking=ranking)}
