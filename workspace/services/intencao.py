"""Assistente de ação — "quero solicitar férias" abre o pedido de férias.

## Por que sem IA, e por que isso não é limitação

A tentação é mandar a frase para um modelo. Mas o problema aqui não é
compreensão de linguagem: é **casar 19 nomes de item**. Um modelo resolveria
isso, e traria latência de rede, custo por tecla digitada, dependência de serviço
externo no caminho crítico da navegação, e uma resposta que às vezes inventa um
serviço que não existe.

Três regras resolvem o mesmo problema de forma determinística:

1. **Verbo de ação em qualquer posição.** "quero", "preciso de", "solicitar" —
   e não só no começo, porque ninguém escreve "quero reembolso": escreve
   "gastei com uber, quero reembolso".
2. **Verbo de leitura barra a ação.** "preciso VER a política de férias" tem
   "preciso" e "férias", e ofereceria abrir um pedido. Quem queria a regra sairia
   com um pedido — o erro mais caro daqui, porque gera trabalho para outra pessoa.
3. **Termos curados.** `ItemCatalogo.termos` guarda `laptop`, `computador`,
   `máquina` para Notebook. É onde mora o conhecimento de como a empresa fala, e
   um termo cadastrado vale como sinal forte por si: alguém o escreveu ali de
   propósito.

O que isto NÃO faz e deliberadamente não tenta: extrair valor da frase. "quero 3
dias de férias em setembro" abre o formulário de férias sem preencher nada.
Interpretar quantidade e data erra em silêncio, e pedido de férias com data errada
é pior que pedido vazio — o formulário mostra o que vai ser enviado; o palpite
não.

## Quando a onda F chegar

O assistente de conhecimento (RAG) responde "qual é a política de férias?". Este
responde "quero férias". São perguntas diferentes e continuam separados: um lê,
o outro faz. O roteamento entre os dois é invisível ao usuário, como manda o
Blueprint §1.2 discordância nº 4.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from workspace.models.catalogo import ItemCatalogo
from workspace.services.indice import normalizar

# Verbos de AGIR. Procurados em qualquer posição, não só no começo: ninguém
# escreve "quero reembolso" — escreve "gastei com uber, quero reembolso".
#
# Ordenados do mais longo para o mais curto: remover "solicitar" antes de
# "gostaria de solicitar" deixaria "gostaria de" para trás.
VERBOS_DE_ACAO = (
    "gostaria de solicitar",
    "gostaria de pedir",
    "gostaria de",
    "como faco para solicitar",
    "como faco para pedir",
    "como faco para",
    "como solicito",
    "como peco",
    "onde solicito",
    "onde peco",
    "preciso solicitar",
    "preciso pedir",
    "preciso de",
    "preciso",
    "quero solicitar",
    "quero pedir",
    "quero",
    "solicitar",
    "solicito",
    "pedir",
    "peco",
    "requisitar",
    "abrir",
    "reservar",
)

# Verbos de LER. Quando aparecem, a pessoa quer a regra e não o pedido, e
# nenhuma ação é oferecida.
#
# "preciso VER a política de férias" tem "preciso" e "férias", e sem esta lista
# ofereceria abrir um pedido de férias. Quem queria a regra sairia com um pedido —
# o erro mais caro que este módulo pode cometer, porque gera trabalho para
# outra pessoa.
VERBOS_DE_LEITURA = (
    "consultar",
    "consulto",
    "ver ",
    "vendo",
    "ler ",
    "leitura",
    "saber",
    "entender",
    "qual ",
    "quais",
    "quanto",
    "quando",
    "onde fica",
    "onde esta",
    "como funciona",
)

# Substantivos que sinalizam leitura E são conteúdo ao mesmo tempo.
#
# A separação é necessária: "política" indica que a pessoa quer a regra, então
# barra a ação — mas é também a palavra que ENCONTRA o documento. Se estivesse
# na lista de cima, `termos_significativos()` a removeria e "qual a política de
# viagens" não acharia a política de viagens. Que foi exatamente o que aconteceu.
SUBSTANTIVOS_DE_NORMA = (
    "politica",
    "norma",
    "regra",
    "procedimento",
    "pop ",
    "manual",
    "instrucao",
)

# Palavras que não são nem verbo nem conteúdo: sobram na frase e, com a busca
# combinando os termos por E, fazem a consulta não achar nada. "minha nr-35 esta
# vencendo" não achava a reciclagem porque nenhum texto contém "esta".
PALAVRAS_VAZIAS = (
    "esta", "estao", "esse", "essa", "isso", "aqui", "ainda", "ja", "sobre",
    "muito", "urgente", "novo", "nova", "favor", "por favor", "que", "mas",
)

# Ruído: "de um notebook" → "notebook".
ARTIGOS = (
    "de um", "de uma", "de", "do", "da", "com", "para", "no", "na",
    "um", "uma", "o", "a", "os", "as", "meu", "minha", "e",
)

MIN_TERMO = 3


@dataclass(frozen=True)
class Acao:
    """Um item de catálogo que responde à intenção da frase."""

    item: ItemCatalogo
    # O que casou. Vai para a tela: "achei por 'laptop'" explica ao usuário por
    # que este item apareceu, e é o que permite ele confiar ou corrigir.
    termo: str
    # `True` quando a frase tinha prefixo de intenção. Sem prefixo, o casamento
    # é palpite razoável; com prefixo, é resposta.
    explicita: bool

    @property
    def rotulo(self) -> str:
        return f"Pedir: {self.item.nome}"


def quer_ler(consulta: str) -> bool:
    """A frase pede a REGRA, não o pedido."""
    texto = normalizar(consulta) + " "
    return any(v in texto for v in VERBOS_DE_LEITURA + SUBSTANTIVOS_DE_NORMA)


def _analisar(consulta: str) -> tuple[str, bool]:
    """Devolve `(o que sobrou, havia verbo de ação)`.

    Remove os verbos de ação de QUALQUER posição, depois os artigos, depois a
    pontuação. O que sobra é o que a pessoa quer — e é sobre isso que o
    casamento com o catálogo acontece.
    """
    texto = normalizar(consulta)
    havia_verbo = False

    for verbo in VERBOS_DE_ACAO:
        # `\b` nas duas pontas: "pedir" não pode casar dentro de "pedirei", nem
        # "abrir" dentro de "abrirei".
        padrao = rf"\b{re.escape(verbo.strip())}\b"
        if re.search(padrao, texto):
            havia_verbo = True
            texto = re.sub(padrao, " ", texto)

    for artigo in ARTIGOS:
        texto = re.sub(rf"\b{re.escape(artigo)}\b", " ", texto)

    texto = re.sub(r"[^\w\s-]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip(), havia_verbo


def termos_significativos(consulta: str) -> list[str]:
    """As palavras que valem busca — sem verbo, artigo nem pontuação.

    Usado pela busca de conteúdo. Sem isto, `texto__contains` recebia a FRASE
    inteira: procurar "quero solicitar ferias" não achava a política de férias,
    porque nenhum documento contém essa frase. A busca por linguagem natural
    devolvia a ação certa e zero conhecimento.
    """
    resto, _ = _analisar(consulta)
    for vazia in VERBOS_DE_LEITURA + PALAVRAS_VAZIAS:
        resto = re.sub(rf"\b{re.escape(vazia.strip())}\b", " ", resto)
    return [p for p in resto.split() if len(p) >= MIN_TERMO]


def _candidatos() -> list[ItemCatalogo]:
    """Todos os itens ativos, sem filtro de permissão.

    De propósito: o catálogo MOSTRA o item fora do alcance marcado "Sem acesso",
    porque saber que o serviço existe é o que faz a pessoa parar de mandar
    e-mail. Esconder aqui contradiria a tela — e a tela de pedido recusa com o
    motivo à vista, que é onde a recusa pertence.
    """
    return list(ItemCatalogo.objects.filter(ativo=True))


def _reduzir(texto: str) -> str:
    """Normaliza e tira artigos — nas DUAS pontas da comparação.

    Sem isto, "parou de funcionar" (termo do catálogo) não casava com
    "equipamento parou funcionar" (a frase, já sem artigos): o "de" havia sido
    removido de um lado só.
    """
    reduzido = normalizar(texto)
    for artigo in ARTIGOS:
        reduzido = re.sub(rf"\b{re.escape(artigo)}\b", " ", reduzido)
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s-]", " ", reduzido)).strip()


def _casa_item(resto: str, item: ItemCatalogo) -> tuple[int, str, bool, bool] | None:
    """`(peso, termo, curado, direto)` do melhor casamento, ou `None`.

    `curado` diz se o que casou foi um `termos` cadastrado, e não o nome ou a
    chave do item. Isso vale como sinal FORTE independentemente do tamanho:
    alguém escreveu "nr-35" naquele campo justamente para que essa frase levasse
    a este item. Peso por tamanho trataria "nr-35" como sinal fraco, quando é o
    mais específico que existe.

    Duas direções, com pesos DIFERENTES — e a diferença corrige um erro meu:

    - **Termo dentro da frase** ("quero um notebook novo" contém "notebook"):
      peso = tamanho do termo. Termo longo achado na frase é sinal forte.
    - **Frase dentro do termo** ("acesso" está em "acesso a sistema"): peso =
      tamanho da FRASE. O sinal vale só o que a pessoa digitou.

    Pesar a segunda direção pelo tamanho do termo fazia "quero acesso" escolher
    "Acesso a sistema" em vez de reconhecer o empate com "Acesso VPN": o
    casamento mais vago ganhava por ter o nome mais comprido.
    """
    curados = {_reduzir(x) for x in (item.termos or [])}
    alvos = [item.nome, *(item.termos or []), item.chave.replace("-", " ")]
    melhor: tuple[int, str, bool, bool] | None = None
    for alvo in alvos:
        normal = _reduzir(alvo)
        if len(normal) < MIN_TERMO:
            continue

        if normal in resto:
            peso, direto = len(normal), True
        elif len(resto) >= MIN_TERMO and resto in normal:
            peso, direto = len(resto), False
        else:
            continue

        candidato = (peso, normal, normal in curados, direto)
        if melhor is None or candidato[0] > melhor[0]:
            melhor = candidato
    return melhor


def interpretar(consulta: str) -> Acao | None:
    """A ação que a frase pede, ou `None`.

    `None` é a resposta certa na maioria das buscas — "reembolso" sozinho é
    consulta, não intenção. Oferecer ação para toda palavra digitada faria o
    bloco de ação virar ruído permanente no topo dos resultados.
    """
    if quer_ler(consulta):
        return None

    resto, explicita = _analisar(consulta)
    if len(resto) < MIN_TERMO:
        # "quero" sozinho não diz o que. Melhor não adivinhar.
        return None

    achados: list[tuple[int, str, bool, bool, ItemCatalogo]] = []
    for item in _candidatos():
        casamento = _casa_item(resto, item)
        if casamento:
            peso, termo, curado, direto = casamento
            achados.append((peso, termo, curado, direto, item))

    if not achados:
        return None

    # Empate é ambiguidade, e ambiguidade não vira ação.
    #
    # "acesso" casa `acesso-vpn` E `acesso-sistema` com o mesmo peso. Escolher
    # um dos dois acerta metade das vezes; não escolher deixa os dois nos
    # resultados de busca, onde a pessoa decide em um clique.
    achados.sort(key=lambda t: -t[0])
    if len(achados) > 1 and achados[0][0] == achados[1][0]:
        return None

    peso, termo, curado, direto, item = achados[0]

    # Sem verbo de ação, exige sinal forte — mas não exige quase-igualdade.
    #
    # A regra era "o termo cobre 80% da frase", e ela existia para barrar
    # "preciso ver a política de férias". Desde que `quer_ler()` existe, isso
    # está barrado antes de chegar aqui, e a regra de 80% passou a bloquear caso
    # legítimo: "meu equipamento parou de funcionar" é intenção clara sem verbo
    # de ação nenhum.
    #
    # Sinal forte, sem verbo de ação:
    #
    # - termo CURADO (`ItemCatalogo.termos`) — alguém escreveu "nr-35" ali de
    #   propósito, e tamanho não mede especificidade;
    # - termo de várias palavras ACHADO na frase — "parou funcionar" é frase
    #   específica por si;
    # - ou cobertura de metade da frase.
    #
    # No casamento REVERSO (a frase é fragmento do termo) a regra é outra, e a
    # separação é necessária: ali `peso` é sempre igual ao tamanho da frase, então
    # a regra de cobertura passava SEMPRE — digitar "ace" oferecia "Pedir: Acesso
    # a sistema". Reverso exige que o fragmento cubra a maior parte do termo:
    # "ferias" é o item inteiro; "ace" é alguém no meio de digitar.
    if not explicita:
        if direto:
            forte = curado or " " in termo or peso >= len(resto) * 0.5
        else:
            forte = curado or peso >= len(termo) * 0.6
        if not forte:
            return None

    return Acao(item=item, termo=termo, explicita=explicita)
