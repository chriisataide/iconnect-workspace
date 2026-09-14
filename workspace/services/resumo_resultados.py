"""Agrupa os sinais e vincula focos ao mesmo indicador, mês e recorte."""
from dataclasses import asdict
from hashlib import sha256
import json


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
