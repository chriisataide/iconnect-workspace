"""Agrupa os sinais e vincula focos ao mesmo indicador, mês e recorte."""
from dataclasses import asdict
from hashlib import sha256
import json
from datetime import timedelta
from workspace.graficos import formato as fmt


def organizar(cartoes, concentracoes, competencia, escopo):
    grupos = [
        {"titulo": "Destaques", "descricao": "O que foi bem nos resultados e contratos.", "itens": []},
        {"titulo": "Pontos de atenção", "descricao": "O que exige cuidado ou avaliação.", "itens": []},
    ]
    focos = {f.alerta_chave: f for f in concentracoes if f.alerta_chave}
    recorte = json.dumps(asdict(escopo), sort_keys=True)
    for c in cartoes:
        chave = sha256(f"{c.chave}|{competencia}|{recorte}".encode()).hexdigest()
        grupos[0 if c.severidade == "bom" else 1]["itens"].append({
            "sinal": c, "chave": chave, "foco": focos.get(chave),
            "referencia": c.titulo[:60],
            "motivo": f"{c.titulo}: {c.valor}. {c.detalhe} ({competencia:%m/%Y}).",
        })
    return grupos


def organizar_contratos(carteira, concentracoes, competencia, url_contrato):
    """Uma linha por contrato; classificações usam somente dados da carteira autorizada."""
    grupos = [
        {"titulo": "Contratos em destaque", "descricao": "Contratos com margem de contribuição de pelo menos 20%.", "itens": []},
        {"titulo": "Contratos que precisam de atenção", "descricao": "Margem abaixo de 10% ou vencimento nos próximos 30 dias da competência.", "itens": []},
    ]
    focos = {}
    for foco in concentracoes:
        if foco.origem_tipo == "contrato":
            focos.setdefault(foco.origem_ref, foco)
    for c in carteira:
        margem = c.margem_contribuicao_pct
        motivos = []
        if margem is not None and (margem < 0 or (c.layer != "sem_amostra" and margem < 10)):
            motivos.append(f"{'Deficitário' if margem < 0 else 'Margem abaixo de 10%'}: {fmt.percentual(margem)}")
        if c.fim_vigencia and competencia <= c.fim_vigencia <= competencia + timedelta(days=30):
            motivos.append(f"Vigência termina em {c.fim_vigencia:%d/%m/%Y}")
        categorias = []
        if margem is not None and c.layer != "sem_amostra" and margem >= 20:
            categorias.append((0, f"Margem de contribuição de {fmt.percentual(margem)}", "bom"))
        if motivos:
            categorias.append((1, "; ".join(motivos), "critico" if c.deficitario else "atencao"))
        for indice, motivo, severidade in categorias:
            titulo = f"{c.codigo} · {c.nome_cliente or 'Cliente não informado'}"
            grupos[indice]["itens"].append({
                "sinal": {"titulo": titulo, "valor": motivo, "severidade": severidade,
                          "detalhe": f"Valor mensal contratado: {fmt.moeda(c.valor_mensal)}", "ancora": "rentabilidade"},
                "url": url_contrato(c.codigo), "tipo": "contrato", "referencia": c.codigo,
                "chave": sha256(f"contrato|{c.codigo}|{competencia}".encode()).hexdigest(),
                "foco": focos.get(c.codigo), "motivo": f"{motivo} ({competencia:%m/%Y}).",
            })
    grupos[1]["itens"].sort(key=lambda i: i["sinal"]["severidade"] != "critico")
    return grupos
