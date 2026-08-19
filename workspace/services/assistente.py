"""O assistente do portal — responde, e só encaminha quando não sabe.

## O fluxo do §3, na ordem certa

    pergunta → a base de conhecimento responde?
             → sim: responde, e oferece o caminho
             → não: identifica a ÁREA e oferece o que dá para fazer nela

A ordem importa mais que qualquer das duas partes. Um assistente que encaminha
primeiro é uma árvore de menus: a pessoa escolhe "R.H." e recebe a mesma lista
que já estava na tela. Um que responde primeiro tira a pergunta do setor, que é
o objetivo declarado.

## Determinístico, e por quê

Mesma decisão de `intencao`, pelo mesmo motivo: o problema aqui não é
compreender linguagem, é casar termos que alguém cadastrou de propósito. Um
modelo de linguagem traria latência por tecla, custo por pergunta, dependência
externa no caminho crítico — e, o pior, respostas inventadas sobre política
interna, que é justamente o assunto em que errar custa caro.

O provedor de IA entra depois, e num lugar só: as perguntas que a base NÃO
cobre, hoje respondidas com "não sei, fale com a área". Essas ficam registradas
para virar FAQ nova — que é como a base cresce sozinha.

## O que este módulo NÃO faz

Não abre pedido. Ele oferece o link; quem clica é a pessoa. Assistente que
executa em nome de alguém a partir de texto livre é o jeito mais rápido de
alguém pedir férias sem querer.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from workspace.models.faq import AreaFAQ, PerguntaFrequente
from workspace.services.indice import normalizar

#: Abaixo disto não vale procurar. "oi" e "ok" casariam com meia base.
MIN_PERGUNTA = 4

#: Quantas sugestões cabem numa resposta antes de virar lista para ler.
MAX_SUGESTOES = 3

#: Palavras que aparecem em quase toda pergunta e não distinguem nada. Sem esta
#: lista, "como" casa com toda FAQ que tenha "como" no título — que são todas.
VAZIAS = frozenset(
    """a o as os um uma de do da dos das em no na nos nas por para com que
    e ou se meu minha meus minhas eu voce onde quando qual quais quem como
    faco fazer posso pode preciso quero gostaria sobre isso
    pedir peco solicitar solicito abrir consultar saber ver mostrar
    funciona feito tem ha vai""".split()
)


@dataclass
class Resposta:
    """O que o assistente devolve. Sempre os três campos, mesmo vazios."""

    texto: str = ""
    faq: PerguntaFrequente | None = None
    #: `[{"rotulo": ..., "url": ...}]` — o que dá para fazer a seguir.
    acoes: list[dict] = field(default_factory=list)
    #: A área identificada, quando não houve resposta direta.
    area: str = ""
    #: `True` quando a base não cobriu — é o que alimenta a fila de FAQ nova.
    sem_resposta: bool = False
    #: `True` quando quem respondeu foi o provedor de IA, e não a base curada.
    #:
    #: A tela PRECISA distinguir: resposta escrita e conferida por alguém da
    #: empresa tem outro peso que resposta gerada por aproximação, e apagar a
    #: diferença é o que faz uma pessoa citar o portal numa reunião com uma
    #: informação que ninguém revisou.
    de_ia: bool = False


def _palavras(texto: str) -> set[str]:
    """As palavras que valem, normalizadas e sem as vazias."""
    return {p for p in normalizar(texto).split() if len(p) > 2 and p not in VAZIAS}


#: A partir deste tamanho, um prefixo conta como casamento — "reembols" acha
#: "reembolsos". Abaixo disso, só palavra inteira.
MIN_PREFIXO = 5

#: Quanto vale um termo CADASTRADO contra uma palavra do título.
#:
#: Dois para um, e a diferença é a que separa uma base curada de uma busca por
#: texto: quem escreveu "capacete" na lista de palavras-chave sabia que alguém
#: perguntaria assim. Quem escreveu "Como pedir acesso a um sistema?" só estava
#: escrevendo português.
PESO_CURADO = 2
PESO_TITULO = 1


def _pontuar(pergunta: PerguntaFrequente, palavras: set[str]) -> int:
    """Quantas palavras da frase aparecem nos termos cadastrados.

    Casamento por PALAVRA, e não por substring. A primeira versão fazia
    `palavra in " ".join(termos)`, e "qual a **cor** do céu" respondia sobre
    **cor**respondência — com toda a confiança do mundo. Num assistente, esse
    erro é pior que não responder: a pessoa lê uma resposta plausível sobre
    outro assunto e vai embora achando que perguntou errado.

    Prefixo ainda vale para palavra longa, senão "reembolsos" não acharia
    "reembolso" e a base precisaria cadastrar todo plural à mão.

    Contagem simples e não similaridade: a base é curada, e o que interessa é
    "quantos sinais desta frase alguém já previu". Uma métrica mais fina daria
    resultados diferentes para frases equivalentes, e a diferença seria
    impossível de explicar a quem mantém a FAQ.
    """
    curados = {p for termo in pergunta.termos_curados for p in termo.split()}
    do_titulo = {p for termo in pergunta.termos_do_titulo for p in termo.split()}

    pontos = 0
    for palavra in palavras:
        if _casa(palavra, curados):
            pontos += PESO_CURADO
        elif _casa(palavra, do_titulo):
            pontos += PESO_TITULO
    return pontos


def _casa(palavra: str, termos: set[str]) -> bool:
    """Palavra inteira, ou prefixo quando as duas são longas."""
    if palavra in termos:
        return True
    if len(palavra) < MIN_PREFIXO:
        return False
    return any(
        t.startswith(palavra) or palavra.startswith(t)
        for t in termos
        if len(t) >= MIN_PREFIXO
    )


def responder(texto: str, area: str = "") -> Resposta:
    """A resposta para uma pergunta em texto livre."""
    texto = (texto or "").strip()
    if len(texto) < MIN_PERGUNTA:
        return Resposta(
            texto="Escreva um pouco mais — o que você precisa saber?",
            sem_resposta=True,
        )

    palavras = _palavras(texto)
    if not palavras:
        return Resposta(
            texto="Não consegui entender. Tente com as palavras do assunto.",
            sem_resposta=True,
        )

    consulta = PerguntaFrequente.objects.ativas()
    if area:
        consulta = consulta.da_area(area)

    achados = []
    for pergunta in consulta:
        pontos = _pontuar(pergunta, palavras)
        if pontos:
            achados.append((pontos, pergunta.prioridade, pergunta))

    if not achados:
        return _encaminhar(texto, palavras)

    achados.sort(key=lambda t: (-t[0], -t[1]))
    melhor = achados[0][2]

    acoes = []
    if melhor.url_acao:
        acoes.append(
            {"rotulo": melhor.rotulo_acao or "Abrir", "url": melhor.url_acao}
        )
    # As outras que casaram viram sugestão — a pergunta certa costuma ser a
    # segunda quando a primeira erra, e obrigar a reescrever perde a pessoa.
    for _, _, outra in achados[1 : 1 + MAX_SUGESTOES]:
        acoes.append({"rotulo": outra.pergunta, "url": f"?p={outra.pk}"})

    return Resposta(texto=melhor.resposta, faq=melhor, acoes=acoes, area=melhor.area)


def _encaminhar(texto: str, palavras: set[str]) -> Resposta:
    """Sem resposta na base: identifica a área e oferece o que dá para fazer.

    É o segundo degrau do §3, e ele usa o motor que já existe — `intencao` sabe
    casar "notebook" com o item de catálogo desde a primeira onda. Reimplementar
    isso aqui criaria duas verdades sobre como a empresa fala.
    """
    from workspace.services import intencao

    acao = intencao.interpretar(texto)
    if acao is None:
        return _ultimo_degrau(texto)

    item = acao.item
    area = item.dominio.split(".", 1)[0]
    rotulo_area = dict(AreaFAQ.choices).get(area, "")
    onde = f" Isso é de {rotulo_area}." if rotulo_area else ""

    return Resposta(
        texto=(
            f"Não tenho um texto sobre isso, mas encontrei o serviço "
            f"“{item.nome}”.{onde} Quer abrir?"
        ),
        acoes=[
            {"rotulo": f"Pedir: {item.nome}", "url": f"/workspace/servicos/{item.chave}/"}
        ],
        area=area,
        sem_resposta=True,
    )


def _ultimo_degrau(texto: str) -> Resposta:
    """O terceiro degrau: a IA, QUANDO houver — §3 e §56.

    A ordem é deliberada e não muda: base curada primeiro, motor de intenção
    depois, IA por último. Inverter faria o assistente responder por
    aproximação uma pergunta que tem resposta escrita e conferida — e a
    resposta conferida é a razão de a base existir.

    Sem provedor registrado, este degrau simplesmente não acontece, e a
    resposta é a mesma de sempre. É o ponto do §56: nenhuma tela depende de IA.
    """
    from workspace.providers import ia

    resposta = ia.responder(texto, contexto=_contexto_do_portal())
    if resposta:
        return Resposta(
            texto=resposta,
            acoes=[{"rotulo": "Ver o catálogo", "url": "/workspace/servicos/"}],
            # `sem_resposta` continua verdadeiro: a base NÃO tinha isto, e é o
            # sinal que diz a quem mantém a FAQ qual pergunta falta escrever.
            sem_resposta=True,
            de_ia=True,
        )

    return Resposta(
        texto=(
            "Ainda não tenho essa resposta. Diga a área e eu te mostro o que "
            "dá para pedir — ou procure no catálogo de serviços."
        ),
        acoes=[{"rotulo": "Ver o catálogo", "url": "/workspace/servicos/"}],
        sem_resposta=True,
    )


def _contexto_do_portal() -> str:
    """As áreas que o portal atende, para o provedor não inventar setor.

    Curto de propósito: mandar a base inteira num contexto seria enviar para
    fora todo o conteúdo interno a cada pergunta.
    """
    return "Áreas do portal: " + ", ".join(rotulo for _, rotulo in AreaFAQ.choices)


def por_area() -> list[dict]:
    """A base inteira agrupada, para a tela de FAQ e para o painel do bot.

    Área sem pergunta fica FORA: uma lista de treze áreas em que nove estão
    vazias ensina que o assistente não sabe nada, mesmo quando ele sabe.
    """
    rotulos = dict(AreaFAQ.choices)
    grupos: dict[str, list] = {}
    for pergunta in PerguntaFrequente.objects.ativas():
        grupos.setdefault(pergunta.area, []).append(pergunta)

    return [
        {"area": area, "rotulo": rotulos.get(area, area), "perguntas": perguntas}
        for area, perguntas in sorted(
            grupos.items(), key=lambda kv: [a for a, _ in AreaFAQ.choices].index(kv[0])
        )
    ]


def sugestoes_iniciais(limite: int = 6) -> list[PerguntaFrequente]:
    """O que o painel mostra ANTES de a pessoa digitar.

    Campo de texto vazio com um cursor piscando é a interface que faz a pessoa
    fechar o chat: ela não sabe o que o bot sabe. As mais prioritárias respondem
    isso sem custo nenhum.
    """
    return list(PerguntaFrequente.objects.ativas().order_by("-prioridade")[:limite])


# ── A administração da base (§3) ────────────────────────────────────

PERMISSAO_MANTER = "faq.manter"


class FAQError(Exception):
    """A pergunta não pode ser gravada assim."""


def pode_manter(pessoa, cache: dict | None = None) -> bool:
    from identidade.services.autorizacao import pode

    return pode(pessoa, PERMISSAO_MANTER, cache=cache)


def salvar_pergunta(
    pessoa,
    pergunta: PerguntaFrequente | None = None,
    *,
    area: str,
    titulo: str,
    resposta: str,
    palavras_chave=(),
    url_acao: str = "",
    rotulo_acao: str = "",
    prioridade: int = 0,
    ativo: bool = True,
    cache: dict | None = None,
) -> PerguntaFrequente:
    """Cria ou edita uma pergunta da base."""
    if not pode_manter(pessoa, cache=cache):
        raise FAQError("Você não pode manter a base de conhecimento.")

    titulo = (titulo or "").strip()
    resposta = (resposta or "").strip()
    if not titulo:
        raise FAQError("A pergunta é obrigatória.")
    if not resposta:
        # Pergunta sem resposta é pior que pergunta ausente: ela aparece na
        # lista, a pessoa clica, e recebe o vazio — e conclui que o assistente
        # não funciona.
        raise FAQError("A resposta é obrigatória.")
    if area not in AreaFAQ.values:
        raise FAQError("Área inválida.")
    if url_acao and not url_acao.startswith("/"):
        # Só caminho interno. Um link para fora daqui envelhece sem ninguém
        # perceber; o interno, quando quebra, dá 404 na cara de quem mantém.
        raise FAQError("O link tem de ser um caminho interno, começando com “/”.")

    novo = pergunta is None
    pergunta = pergunta or PerguntaFrequente()
    pergunta.area = area
    pergunta.pergunta = titulo[:200]
    pergunta.resposta = resposta
    pergunta.palavras_chave = [t.strip() for t in palavras_chave if t and t.strip()]
    pergunta.url_acao = url_acao.strip()[:300]
    pergunta.rotulo_acao = (rotulo_acao or "").strip()[:60]
    pergunta.prioridade = int(prioridade or 0)
    pergunta.ativo = bool(ativo)
    if novo:
        pergunta.criado_por = pessoa
    pergunta.save()
    return pergunta


def excluir_pergunta(pergunta: PerguntaFrequente, pessoa, cache=None) -> None:
    """Apaga de vez.

    Aqui apagar É o certo, ao contrário do comunicado: FAQ não é registro do que
    a empresa disse num dia — é a resposta corrente. Uma resposta errada que fica
    arquivada continua sendo encontrada por quem procura no admin, e alguém a
    reativa achando que era boa.
    """
    if not pode_manter(pessoa, cache=cache):
        raise FAQError("Você não pode manter a base de conhecimento.")
    pergunta.delete()


def todas_para_manutencao(pessoa, cache: dict | None = None):
    """A base inteira, INCLUSIVE as desativadas — é a lista de quem mantém."""
    if not pode_manter(pessoa, cache=cache):
        raise FAQError("Você não pode manter a base de conhecimento.")
    return PerguntaFrequente.objects.select_related("criado_por").all()
