"""Comparações e composição a partir de apontamentos autorizados."""
from collections import defaultdict
from decimal import Decimal
from hashlib import sha256

from workspace.graficos import formato as fmt

PARTES = (("he_servico_extra", "Serviço extra"), ("he_ineficiencia", "Ineficiência"), ("he_sem_classificacao", "Sem classificação"))


def total(linhas, campo):
    return sum((getattr(l, campo) for l in linhas), Decimal(0)) if linhas else None


def comparar(atual, anterior):
    diferenca = atual - anterior if atual is not None and anterior is not None else None
    return {"anterior": anterior, "diferenca": diferenca,
            "variacao": diferenca / abs(anterior) * 100 if diferenca is not None and anterior else None}


def analisar(linhas, base, carteira, competencia, anterior, meses, metrica, titulo):
    do_mes = [l for l in base if (l.ano, l.mes) == (competencia.year, competencia.month)]
    antes = [l for l in base if (l.ano, l.mes) == (anterior.year, anterior.month)]
    comparacao = comparar(total(do_mes, metrica), total(antes, metrica))
    leitura = "Sem dados comparáveis nos dois meses para calcular a variação."
    if comparacao["diferenca"] is not None:
        d = comparacao["diferenca"]
        movimento = "aumentou" if d > 0 else "diminuiu" if d < 0 else "não mudou"
        leitura = f"{titulo}: {movimento} em relação a {anterior:%m/%Y}"
        if d:
            leitura += f" em {fmt.numero(abs(d), 2)} h"
        if comparacao["variacao"] is not None:
            leitura += f" ({fmt.percentual(comparacao['variacao'])})"
        leitura += ". A comparação usa os registros disponíveis em cada mês; mudanças de cobertura também afetam a variação."
    agrupados = defaultdict(list)
    for l in linhas:
        if l.contrato:
            agrupados[l.contrato].append(l)
    detalhes = []
    for codigo, registros in sorted(agrupados.items()):
        atuais = [l for l in registros if (l.ano, l.mes) == (competencia.year, competencia.month)]
        antigos = [l for l in registros if (l.ano, l.mes) == (anterior.year, anterior.month)]
        he = total(atuais, "he_total")
        partes = [{"titulo": nome, "valor": total(atuais, campo),
                   "percentual": total(atuais, campo) / he * 100 if he else None} for campo, nome in PARTES]
        soma_partes = sum((p["valor"] for p in partes), Decimal(0)) if atuais else None
        detalhes.append({"codigo": codigo, "cliente": registros[-1].cliente,
            "atual": total(atuais, metrica), **comparar(total(atuais, metrica), total(antigos, metrica)),
            "partes": partes, "he_total": he,
            "diferenca_composicao": he - soma_partes if he is not None else None,
            "serie": [{"mes": m, "valor": total([l for l in registros if (l.ano, l.mes) == (m.year, m.month)], metrica)} for m in meses],
            "chave": sha256(f"jornada|{codigo}|{competencia}".encode()).hexdigest(),
            "motivo": f"Analisar {titulo.lower()} do contrato {codigo} em {competencia:%m/%Y}.",
        })
    esperados = {c.codigo: c.nome_cliente for c in carteira}
    presentes = {l.contrato for l in linhas if l.contrato and (l.ano, l.mes) == (competencia.year, competencia.month)}
    cobertura = {"total": len(esperados), "com_dados": len(presentes & esperados.keys()),
                 "sem_dados": [{"codigo": c, "cliente": n} for c, n in esperados.items() if c not in presentes]}
    cobertura["percentual"] = Decimal(cobertura["com_dados"]) / cobertura["total"] * 100 if cobertura["total"] else None
    altas = sorted([d for d in detalhes if d["diferenca"] is not None and d["diferenca"] > 0], key=lambda d: -d["diferenca"])
    if altas:
        leitura += " Entre os contratos com dados nos dois meses, maiores aumentos: " + "; ".join(
            f"{d['codigo']} · {d['cliente']} (+{fmt.numero(d['diferenca'], 2)} h)" for d in altas[:2]) + "."
    return {"comparacao": comparacao, "mes_anterior": anterior, "leitura": leitura,
            "detalhes": detalhes, "cobertura": cobertura}
