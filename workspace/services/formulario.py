"""FRM — as regras do formulário dinâmico: ramo, passo e escolha.

Três mecanismos pequenos que juntos evitam o formulário genérico, aquele que
mostra todas as perguntas de todos os casos e deixa a pessoa decidir quais
ignorar:

**Ramo (`quando`).** Um campo pode existir só quando outro tem certo valor. Os
dados do técnico terceiro na reciclagem de NR só aparecem para quem respondeu
que é para um terceiro; para todo mundo mais, eles não existem — nem na tela,
nem na validação, nem no que é gravado.

**Passo (`passo`).** O formulário pode ser dividido em etapas. A divisão é do
NAVEGADOR: uma requisição só, um POST só. Wizard de verdade, com estado no
servidor entre telas, exigiria guardar arquivo enviado pela metade — e o
formulário de prestação de contas é justamente o que mais anexa. Sem JS, os
passos aparecem todos e a página continua funcionando.

**Escolha (`opcoes`).** Lista fechada em vez de texto livre. "Qual sistema você
precisa acessar" escrito à mão produz `iconnect`, `IConnect`, `sistema da
operadora` e `aquele portal` para a mesma coisa — e ninguém consegue medir nem
rotear em cima disso.

A regra que amarra os três: **o servidor decide**. A tela esconde o que não é
do ramo, mas quem ignora o valor de um campo fora do ramo, e quem recusa uma
escolha que não está na lista, é este módulo.
"""

from __future__ import annotations

from workspace.models.catalogo import TipoCampo


def condicao_satisfeita(campo: dict, dados: dict | None) -> bool:
    """Este campo existe, dado o que já foi respondido?

    Campo sem `quando` existe sempre. Com `quando`, existe quando o campo
    apontado tem um dos valores listados:

        {"campo": "origem", "igual": "externo"}
        {"campo": "origem", "igual": ["externo", "hibrido"]}
    """
    quando = campo.get("quando")
    if not quando:
        return True

    chave = quando.get("campo")
    if not chave:
        return True

    esperado = quando.get("igual")
    valores = esperado if isinstance(esperado, (list, tuple)) else [esperado]
    atual = (dados or {}).get(chave)
    return atual in [str(v) for v in valores]


def campos_ativos(item, dados: dict | None) -> list[dict]:
    """Os campos que existem para as respostas dadas até aqui."""
    return [c for c in item.campos if condicao_satisfeita(c, dados)]


def limpar_fora_do_ramo(item, dados: dict | None) -> dict:
    """Descarta o que foi digitado num ramo que a pessoa não escolheu.

    Sem JS a tela mostra todos os ramos, e alguém pode preencher os dois antes
    de decidir. Gravar os dois deixaria o pedido dizendo, ao mesmo tempo, que o
    curso é interno e que a instituição é a Fulana — e é o aprovador quem
    descobriria a contradição.
    """
    dados = dados or {}
    vivos = {c["chave"] for c in campos_ativos(item, dados)}
    return {k: v for k, v in dados.items() if k in vivos}


def valor_e_exigido(item, dados: dict | None) -> bool:
    """O campo de valor aparece para estas respostas?

    Curso interno da empresa não tem preço a informar. Um "Valor *" obrigatório
    num ramo que não tem valor trava o pedido inteiro num campo impossível de
    responder certo.
    """
    if not item.exige_valor:
        return False
    condicao = getattr(item, "valor_quando", None)
    if not condicao:
        return True
    return condicao_satisfeita({"quando": condicao}, dados)


# ── Escolha ─────────────────────────────────────────────────────────


def opcoes_de(campo: dict) -> list[dict]:
    """Normaliza `opcoes` para `[{valor, rotulo}]`.

    Aceita a forma curta (lista de textos) porque a maioria das listas tem o
    mesmo texto para valor e rótulo, e obrigar a forma longa faria o catálogo
    inicial ficar ilegível por causa da minoria que precisa dela.
    """
    normalizadas: list[dict] = []
    for opcao in campo.get("opcoes") or []:
        if isinstance(opcao, dict):
            valor = str(opcao.get("valor", ""))
            normalizadas.append({"valor": valor, "rotulo": opcao.get("rotulo") or valor})
        else:
            normalizadas.append({"valor": str(opcao), "rotulo": str(opcao)})
    return normalizadas


def escolha_invalida(campo: dict, valor) -> bool:
    """Valor que não está na lista. Vem do cliente, então é conferido aqui."""
    if campo.get("tipo") != TipoCampo.ESCOLHA:
        return False
    if not valor:
        return False
    return valor not in {o["valor"] for o in opcoes_de(campo)}


# ── Passos ──────────────────────────────────────────────────────────


def passos_de(item) -> list[dict]:
    """A trilha do stepper, já numerada. Vazia quando o item é de uma tela só.

    Passo marcado `apos_envio` acontece em OUTRA tela — o acerto do
    adiantamento é o caso. Ele aparece na trilha mesmo assim: esconder que
    ainda falta uma etapa é o que faz a pessoa achar que terminou.
    """
    declarados = list(getattr(item, "passos", None) or [])
    if not declarados:
        return []
    return [
        {
            "numero": numero,
            "titulo": passo.get("titulo", f"Passo {numero}"),
            "apos_envio": bool(passo.get("apos_envio")),
        }
        for numero, passo in enumerate(declarados, start=1)
    ]


def passo_do_campo(campo: dict) -> int:
    """Campo sem `passo` declarado mora no primeiro — assim um item ganha
    passos sem que todos os seus campos precisem ser reescritos."""
    try:
        return max(1, int(campo.get("passo", 1)))
    except (TypeError, ValueError):
        return 1
